# Design

## Context

The repository is greenfield: it contains only the OpenSpec setup. There is no backend, no Compose file, and no database yet. Motivation and scope are in proposal.md; required behavior is in the seven delta specs under `specs/`.

Environment facts observed on the primary development machine (Windows 11): Python 3.14 via the `py` launcher, uv 0.13, Node 24. Docker is not installed yet and is required by this change. Teammates may use macOS or Linux.

## Goals / Non-Goals

**Goals:**
- A layout and set of conventions that every later feature module copies without rethinking.
- Request handling where permission checks, the data change, and its audit entry cannot drift apart.
- A test harness on real PostgreSQL that later changes extend with one fixture call per role.

**Non-Goals:**
- Record-level scope rules beyond a hook (no scoped entities exist yet).
- Async database access, a separate migration database role, horizontal scaling, or production hardening.
- No workflow transitions are introduced in this change, so there is no transition table yet.

## Decisions

### D1. Repository layout

```
docker-compose.yml        .env.example        .gitignore        .gitattributes
backend/
  Dockerfile  pyproject.toml  uv.lock  alembic.ini  README.md
  alembic/  env.py  versions/0001_baseline.py
  app/
    main.py               create_app(): middleware, handlers, routers
    core/                 config, db, security, errors, pagination, request_id, logging, clock
    health/               router, service
    auth/                 router, service, schemas, dependencies, models (refresh_tokens)
    access/               roles, permissions, role map, require_permission, scope hook
    users/                router, service, repository, models, schemas
    audit/                router, service, repository, models, schemas
    seed/                 __main__.py, data.py
    api_v1.py             mounts every module router under /api/v1
  tests/
    conftest.py  factories.py
    unit/  integration/  api/  migrations/
```

A `frontend/` directory is reserved for later. Each feature module follows the `router -> service -> repository -> models` direction. Modules call each other only through services; the `audit` service is the one shared dependency every writing service uses.

### D2. Runtime and pinned dependencies

Python **3.13** is pinned with `requires-python = ">=3.13,<3.14"` and `.python-version`, so uv installs it automatically and the 3.14 already on the machine doesn't matter. The resolver produced identical versions for 3.12, 3.13 and 3.14. 3.13 has had wheels for every dependency for longer, and `python:3.13-slim` is the Docker base. Exact versions are locked in `uv.lock`. The lower bounds below are what uv resolved on 2026-10-31:

| Package | Version | Why |
|---|---|---|
| fastapi | 0.162.0 | API framework; generates OpenAPI |
| uvicorn[standard] | 0.54.0 | ASGI server |
| sqlalchemy | 2.1.6 | ORM, `Mapped[]` typed models |
| psycopg[binary] | 3.3.6 | PostgreSQL driver, prebuilt wheels on Windows |
| alembic | 1.20.1 | Migrations, autogenerate drift check |
| pydantic | 2.14.2 | Request/response validation |
| pydantic-settings | 2.16.2 | Env-based settings with validation |
| email-validator | 2.3.0 | `EmailStr` validation |
| pyjwt | 2.15.1 | JWT. Chosen over python-jose (stale) |
| argon2-cffi | 25.1.0 | Argon2id hashing. Chosen over passlib (unmaintained, bcrypt breakage) |
| pytest / pytest-cov | 9.2.0 / 7.1.0 | Tests and coverage (dev) |
| httpx | 0.28.1 | Used by FastAPI's TestClient for API tests (dev) |
| ruff | 0.17.3 | Lint and format (dev) |

PostgreSQL **17** (`postgres:17` image) is used for both development and test databases.

### D3. Sync SQLAlchemy and one transaction per request

The database layer is sync SQLAlchemy 2.1 with psycopg 3. FastAPI runs sync endpoints in a thread pool, and sync code keeps the services and test fixtures simpler for a small team. The alternative was async SQLAlchemy plus asyncpg: more ceremony, harder session handling in tests, and no benefit at demo scale.

The `get_session` dependency opens one session per request inside `session.begin()`. It commits if the endpoint returns and rolls back if it raises. Services `flush()` but never `commit()`. The audit service writes into the same session, so a change and its audit entry are saved together or not at all.

**Exception: security events on rejected requests.** A failed login, a denied write, and refresh-token reuse must leave an audit entry even though the request fails. These checks always run before any data is changed. The code path writes the audit entry (and, for reuse, revokes the token family), calls `session.commit()` explicitly, and then raises. This is the only place outside the request boundary that commits.

### D4. Data model (migration `0001_baseline`)

```
users 1 ---* refresh_tokens
users 1 ---* audit_logs (actor_id, nullable)
```

| Table | Columns | Constraints and indexes |
|---|---|---|
| `users` | `id uuid pk`, `email varchar(320)`, `full_name varchar(200)`, `password_hash text`, `role varchar(40)`, `is_active bool default true`, `created_at timestamptz`, `updated_at timestamptz` | `email` stored lowercased and unique; `role` CHECK against the seven values; index on `role` |
| `refresh_tokens` | `id uuid pk`, `user_id uuid fk`, `family_id uuid`, `token_hash char(64)`, `expires_at timestamptz`, `created_at timestamptz`, `revoked_at timestamptz null`, `replaced_by_id uuid null` | `token_hash` unique; indexes on `user_id` and `family_id` |
| `audit_logs` | `id bigint identity pk`, `occurred_at timestamptz`, `actor_id uuid null fk`, `actor_role varchar(40) null`, `action varchar(100)`, `target_type varchar(50) null`, `target_id varchar(64) null`, `outcome varchar(10)`, `before jsonb null`, `after jsonb null`, `details jsonb null`, `request_id varchar(64) null` | `outcome` CHECK; indexes on `(target_type, target_id)`, `actor_id`, `action`, `occurred_at desc` |

- **Email uniqueness.** Lowercasing emails before they are stored is simpler than the `citext` extension and keeps the schema free of extensions.
- **Audit ids.** `audit_logs.id` is a bigint identity, so entries have a natural order. It isn't a client-facing reference. `target_id` is text, so later targets of any type fit.
- **Naming conventions.** All constraints follow a naming convention on `MetaData` (`pk_`, `fk_`, `uq_`, `ix_`, `ck_`), so autogenerate and downgrade produce stable names.
- **Reversibility.** The migration is fully reversible. Downgrade drops the triggers, then the trigger function, then the tables in reverse dependency order.

### D5. Append-only audit log

The baseline migration creates a PL/pgSQL function `audit_logs_reject_change()`, which raises an exception, and attaches it to `audit_logs` in two triggers:
- A `BEFORE UPDATE OR DELETE ... FOR EACH ROW` trigger.
- A `BEFORE TRUNCATE ... FOR EACH STATEMENT` trigger.

A trigger is used rather than a revoked privilege. Triggers fire for the table owner too, and in the demo the app connects as the owner. There is only one database role to manage.

The repository exposes `add()` and query methods only. The router defines `GET` only. Tests clean up by transaction rollback, so they never need `TRUNCATE`.

Residual risk is described under Risks.

### D6. Authentication

**Passwords**
- Hashed with `argon2.PasswordHasher` using library defaults (Argon2id). `check_needs_rehash` runs after a successful login so parameters can be upgraded later.
- In the `test` environment the time and memory costs are reduced through settings to keep the suite fast. The algorithm stays Argon2id.

**Uniform login failure**
- When the email is unknown, the service still verifies the password against a fixed dummy hash. This keeps response timing similar to the wrong-password case.
- Every failure, including an inactive account, returns the same `invalid_credentials` error.

**Access tokens**
- HS256 JWTs signed with `JWT_SECRET`.
- Claims: `sub` (user id), `role`, `iat`, `exp`, `jti`, `typ="access"`.
- Decoding pins `algorithms=["HS256"]`, requires `exp`, `iat`, `sub` and `typ`, and allows no leeway.
- The default lifetime is 15 minutes, set by `ACCESS_TOKEN_TTL_MINUTES`.

**Current user**
- `get_current_user` uses FastAPI's `HTTPBearer(auto_error=False)`, so the 401 responses follow the standard error format.
- After decoding, it loads the user by `sub` and rejects missing or inactive users.
- The `role` claim is ignored for authorization.

**Refresh tokens**
- Each token is `secrets.token_urlsafe(32)`, stored as a SHA-256 hex digest. A fast hash is enough because the tokens are high-entropy.
- Lifetime is 7 days, set by `REFRESH_TOKEN_TTL_DAYS`.
- Login starts a new `family_id`.
- Refresh, when the presented token is valid: set `revoked_at` on it, insert a new token in the same family, and link the two with `replaced_by_id`.
- Refresh, when the presented token is already revoked: revoke every token in the family, audit `auth.refresh_reuse_detected`, commit (D3), then return 401.
- `POST /auth/logout` takes `{refresh_token}`, revokes its family and returns 204. It requires a valid access token.
- Deactivating a user revokes all of that user's tokens. Their access tokens die on the next request because of the per-request user reload.
- The alternative considered was refresh tokens as JWTs. They were rejected because they can't be revoked without server-side state, and that state is needed anyway.

### D7. Authorization

`access/roles.py` defines a `Role` StrEnum with the seven values. `access/permissions.py` defines:
- A `Permission` StrEnum, where each permission has a `category`: `system`, `audit` or `business`.
- `ROLE_PERMISSIONS: dict[Role, frozenset[Permission]]`.

The permission matrix for this change:

| Permission | Category | super_admin | aicte_admin | regional_officer | scrutiny_officer | evc_coordinator | institution_representative | auditor |
|---|---|---|---|---|---|---|---|---|
| `users.read` | system | ✓ | | | | | | |
| `users.manage` | system | ✓ | | | | | | |
| `audit.read` | audit | ✓ | ✓ | | | | | ✓ |

All roles can use `/auth/me`, `/auth/refresh` and `/auth/logout`. Health endpoints are public.

**Enforcement**
- Endpoints use `require_permission(Permission.X, audit_action="users.update")`. The dependency resolves the current user, checks the map and returns the user.
- On denial for a write endpoint (`audit_action` set), it records an entry with outcome `denied` (D3), then raises `PermissionDenied`, which returns 403 `permission_denied`.
- Services take the acting user as an argument and call `authorize(actor, permission)` again before changing anything. This is the second layer the spec requires.
- `require_permission` stores the permission on the route through `openapi_extra`. The RBAC test reads the route table, so a protected route missing from the test matrix fails the build.

**Super Admin rule.** A unit test asserts that no `business` category permission is ever granted to `super_admin`. Later changes add business permissions under the same guard.

**Scope hook.** `access/scope.py` defines a `Scope` value: the acting user's id, role, and placeholder `institution_id` and `region_id` fields, both `None` for now. Repositories for later scoped entities take a `Scope` and apply filters. A lookup that matches nothing raises `NotFound`, so a record outside the caller's scope gets 404. No scoped entities exist in this change.

### D8. Errors, validation, and conventions

**Errors**
- `core/errors.py` defines `AppError(code, message, status, details)` and subclasses: `NotFound` (404), `Conflict` (409), `PermissionDenied` (403), `NotAuthenticated` / `InvalidToken` / `InvalidCredentials` (401), and `ServiceUnavailable` (503).
- Four handlers convert errors into the standard format:
  - `AppError`.
  - `RequestValidationError`: 422, with `details` built from Pydantic's location and message only, not the input values.
  - Starlette `HTTPException`: covers unknown paths (404) and wrong methods (405).
  - A catch-all `Exception` handler: 500 with code `internal_error`. It logs the stack trace server-side only.
- Database `IntegrityError` on a unique constraint becomes `Conflict`.

**Request ids.** Middleware accepts an incoming `X-Request-ID` (at most 64 characters, `[A-Za-z0-9-]`) or generates a UUID4. It stores the id in a contextvar for logs and audit entries and echoes it in the response header.

**Request models.** Request models set `model_config = ConfigDict(extra="forbid")`.

**Pagination**
- `core/pagination.py` provides `PageParams` (page ≥ 1; 1 ≤ page_size ≤ 100) and a generic `Page[T]` response.
- `SortParam` checks `sort` against each endpoint's allowed fields and accepts `-` for descending.

**Timestamps.** All timestamps are `timestamptz`. `core/clock.py` provides `utcnow()`, which tests can override, and responses serialize aware UTC datetimes.

**Logging.** A logging filter removes values whose keys match `password|token|secret|authorization|hash`.

**CORS.** `CORS_ORIGINS` (default `http://localhost:5173`) is set ahead of the future frontend.

### D9. Configuration

`core/config.py` defines a `Settings(BaseSettings)` with these settings:
- `APP_ENV` (`development` | `test` | `production`)
- `DATABASE_URL`
- `TEST_DATABASE_URL` (tests only)
- `JWT_SECRET`
- `ACCESS_TOKEN_TTL_MINUTES`
- `REFRESH_TOKEN_TTL_DAYS`
- `DEMO_PASSWORD`
- `CORS_ORIGINS`
- `LOG_LEVEL`
- `RUN_MIGRATIONS_ON_START`
- Argon2 cost overrides.

A model validator enforces the startup rules in the `platform-runtime` spec: the secret must be at least 32 characters and must not be the placeholder outside development and test. `create_app()` instantiates the settings, so the app fails fast on startup.

### D10. Health checks

- `/api/v1/health` returns a static response.
- `/api/v1/health/db` runs `SELECT 1` with a 2-second statement timeout. It compares `alembic_version` in the database with the head of Alembic's script directory, and returns 503 if the database is unreachable or the revisions differ. Driver error messages are logged, never returned.

### D11. Docker and Compose

**Backend Dockerfile**
- Two stages:
  - A uv builder stage copies `uv` from `ghcr.io/astral-sh/uv` and runs `uv sync --frozen --no-dev` into `/app/.venv`.
  - A `python:3.13-slim` runtime stage copies the venv and the app and runs as a non-root user.
- `HEALTHCHECK` uses `python -c` with `urllib` against `/api/v1/health`, since `curl` isn't in the slim image.
- The command is `sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"` when `RUN_MIGRATIONS_ON_START=true`. Running migrations on start is acceptable for a single-instance demo.

**`docker-compose.yml` (repository root)**
- **`db`:** `postgres:17`. Named volume `pgdata`, a `pg_isready` health check, and the host port from `POSTGRES_PORT` (default 5432).
- **`db_test`:** `postgres:17`. Data on `tmpfs`, so it is disposable and wiped on restart, host port 5433, and its own credentials and database name. It never shares data with `db`.
- **`backend`:** built from `./backend`, with `env_file: .env` and `depends_on: db: condition: service_healthy`. It publishes port 8000 and has a health check.

**Line endings.** `.gitattributes` forces LF line endings for `*.sh`, `Dockerfile` and `*.py`. This stops Windows checkouts from breaking the container commands.

Tests run on the host with `uv run pytest`, against `db_test` on `localhost:5433`.

### D12. Test harness

**Database fixtures**
- A session fixture runs `alembic upgrade head` once against `TEST_DATABASE_URL`.
- Each test opens a connection and begins a transaction.
- It binds a `Session(join_transaction_mode="create_savepoint")`, so the request dependency's commits and the explicit security-event commits (D3) become savepoint releases.
- The outer transaction is rolled back at teardown, so every test sees a clean database without truncating anything.

**API client**
- API tests use FastAPI's `TestClient`, which is built on HTTPX, with `get_session` overridden to the test session.
- Fixtures: `client`, `user_factory(role=..., is_active=...)`, and `auth_headers(role)`, which creates a user and returns `{"Authorization": "Bearer ..."}`.

| Suite | Folder | Uses database | Covers |
|---|---|---|---|
| Unit | `tests/unit` | No | Settings validation, hashing, JWT encode/decode/expiry/tamper/`alg`, role map and the Super Admin guard, pagination and sort parsing, error formatting, log redaction |
| PostgreSQL integration | `tests/integration` | Yes | Repositories, email uniqueness, audit trigger rejects UPDATE/DELETE/TRUNCATE, refresh-token family revocation, seed idempotency |
| API | `tests/api` | Yes | Every endpoint and status code in the specs, error format, request id, OpenAPI document |
| RBAC matrix | `tests/api/test_rbac_matrix.py` | Yes | All roles × all protected routes, checked against the matrix in D7 and the route table |
| Migrations | `tests/migrations` | Its own temporary database | Upgrade → downgrade → upgrade on a freshly created database; `alembic check` / `compare_metadata` reports no drift |

### D13. Seed data

`uv run python -m app.seed`:
- Refuses to run in `production`.
- Upserts by email, so running it twice changes nothing.
- Creates one active user per role and one deactivated user, with emails such as `super.admin@flowguard.example.org` and plainly fictional names.
- Gives every demo user `DEMO_PASSWORD`.
- Writes a single `system.seed` audit entry, and only when it created something.
- Prints counts and the demo login emails.

## Risks / Trade-offs

- **[Docker is not installed on the primary machine]** → Installing Docker Desktop (WSL 2) is task 1.1 and blocks every database task. The README documents installation for each OS.
- **[Database owner or superuser can drop the audit trigger]** → This is acceptable for a demo and is documented. A later hardening change can split a migration role from a runtime role that has only INSERT and SELECT on `audit_logs`.
- **[A leaked HS256 secret allows forged tokens]** → The secret lives only in environment variables, the app refuses to start with a weak secret, and tokens are short-lived. Changing the secret invalidates all access tokens.
- **[Migrations on container start race with more than one replica]** → The demo runs a single instance only. The `RUN_MIGRATIONS_ON_START` flag can turn it off.
- **[Explicit commits on security events could save half-finished work]** → Those checks run before any data is changed. A test asserts that a denied write leaves the target row unchanged.
- **[Low-cost Argon2 settings could leak outside tests]** → The settings validator rejects reduced costs unless `APP_ENV=test`.
- **[The RBAC matrix gets out of date as modules are added]** → The matrix test is driven by the route table, so a new protected route fails the build until the matrix covers it.
- **[Developer machines differ (Windows/macOS/Linux)]** → uv pins Python, Compose pins Postgres, `.gitattributes` fixes line endings, and every README command is checked on Windows.

## Migration Plan

This is a new project with no existing data. To roll back, run `alembic downgrade base`, or delete the `pgdata` volume with `docker compose down -v`.
