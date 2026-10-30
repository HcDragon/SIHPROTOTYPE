# Tasks

## 1. Workstation and repository scaffold

- [x] 1.1 Install Docker Desktop (WSL 2 backend on Windows) and confirm `docker --version` and `docker compose version` both succeed
- [x] 1.2 Add root `.gitignore` (`.env`, `.venv`, caches, coverage), `.gitattributes` (LF for `*.sh`, `*.py`, `Dockerfile`), and `.env.example` with placeholder values for every setting in design D9; verify `git check-ignore .env` reports it ignored
- [x] 1.3 Create `backend/pyproject.toml` with Python `>=3.13,<3.14`, `.python-version`, the dependencies and dev dependencies from design D2, and ruff/pytest config; run `uv sync` and verify `uv.lock` is created and `uv run python --version` prints 3.13
- [x] 1.4 Create the `backend/app/` module skeleton from design D1 (empty packages for core, health, auth, access, users, audit, seed) plus `tests/{unit,integration,api,migrations}`; verify `uv run ruff check .` and `uv run pytest` (zero tests) both exit cleanly

## 2. Core API conventions

- [x] 2.1 Implement `core/config.py` settings with the startup validation rules (required settings, secret length, placeholder rejected outside development/test, reduced Argon2 cost only in test); verify unit tests cover each rejection case
- [x] 2.2 Implement `core/errors.py` (AppError hierarchy and handlers for AppError, validation errors, HTTP 404/405, and unhandled exceptions) and `core/request_id.py` middleware; verify unit/API tests show the standard error body, `request_id` equal to the `X-Request-ID` header, and no stack trace in a 500 response
- [x] 2.3 Implement `create_app()` in `main.py` and `api_v1.py` mounting routers under `/api/v1`, with CORS from settings; verify an API test that `GET /api/v1/does-not-exist` returns 404 code `not_found` in the standard format
- [x] 2.4 Implement `core/pagination.py` (`PageParams`, `Page[T]`, allow-listed `SortParam`) and request-model base with `extra="forbid"`; verify unit tests for defaults, `page_size` > 100 rejected, unknown sort field rejected, and `-field` descending
- [x] 2.5 Implement `core/clock.py` (overridable `utcnow`) and the log redaction filter in `core/logging.py`; verify unit tests that UTC timestamps serialize with an explicit offset and that password/token/secret keys are redacted

## 3. Database, Compose, and health checks

- [x] 3.1 Add root `docker-compose.yml` with `db` (postgres:17, `pgdata` volume, `pg_isready` health check) and `db_test` (postgres:17, tmpfs, port 5433, separate credentials); verify `docker compose up -d db db_test` reports both services healthy
- [x] 3.2 Implement `core/db.py` (engine from settings, `MetaData` naming conventions, declarative `Base`, `get_session` dependency that commits on success and rolls back on error); verify an integration test that an exception inside a request leaves no row written
- [x] 3.3 Initialize Alembic (`alembic.ini`, `env.py` reading `DATABASE_URL` from settings and targeting `Base.metadata`); verify `uv run alembic current` connects to `db` without error
- [x] 3.4 Add the pytest database harness from design D12 (session-scoped `alembic upgrade head` on `TEST_DATABASE_URL`, per-test transaction with `create_savepoint` session, `client` fixture overriding `get_session`); verify a sample integration test's write is gone in the next test
- [x] 3.5 Implement `/api/v1/health` and `/api/v1/health/db` (reachability with 2s timeout, migration revision vs head, 503 without connection details); verify API tests for ok, database unavailable (bad URL), and pending migrations

## 4. Data model and baseline migration

- [x] 4.1 Add SQLAlchemy models for `users`, `refresh_tokens`, and `audit_logs` per design D4 (lowercased unique email, role and outcome CHECK constraints, indexes); verify `uv run python -c "import app.users.models, app.auth.models, app.audit.models"` succeeds
- [x] 4.2 Write migration `0001_baseline` creating the three tables plus the `audit_logs_reject_change()` function and its row-level UPDATE/DELETE and statement-level TRUNCATE triggers, with a full downgrade; verify `alembic upgrade head` then `alembic downgrade base` succeed against `db`
- [x] 4.3 Add migration tests that create a temporary database, run upgrade â†’ downgrade â†’ upgrade, and assert `compare_metadata` reports no drift; verify they pass with `uv run pytest tests/migrations`
- [x] 4.4 Add integration tests that UPDATE, DELETE, and TRUNCATE on `audit_logs` are rejected by the database and that a duplicate email in any letter case violates uniqueness; verify they pass

## 5. Audit recording

- [x] 5.1 Implement the audit repository (`add` and query methods only) and `AuditService.record(...)` writing actor, role, action, target, outcome, before/after, details, and request id into the current session; verify integration tests that an entry rolls back together with the change it records
- [x] 5.2 Implement sensitive-value scrubbing in `AuditService` (drop password, hash, and token keys from before/after/details); verify a unit test that a payload containing those keys is stored without them

## 6. Authentication

- [x] 6.1 Implement password hashing in `core/security.py` (Argon2id `PasswordHasher`, `verify`, `needs_rehash`, dummy-hash verification for unknown emails); verify unit tests that hashes are Argon2id and never equal the plaintext
- [x] 6.2 Implement access-token creation and decoding (HS256, required claims, pinned algorithm, no leeway); verify unit tests for valid, expired, tampered payload, tampered signature, `alg` changed, and malformed tokens
- [x] 6.3 Implement `POST /api/v1/auth/login` with uniform `invalid_credentials` failures and success/failure audit entries (failure committed before raising, per design D3); verify API tests for success, wrong password, unknown email, deactivated user, identical failure bodies, and both audit entries without the password
- [x] 6.4 Implement `get_current_user` (bearer header, decode, reload user, reject inactive) and `GET /api/v1/auth/me` returning profile and permissions; verify API tests for missing header (401 `not_authenticated` with `WWW-Authenticate`), invalid token (401 `invalid_token`), deactivated-after-issue (401), and role-changed-after-issue (new role used)

## 7. Refresh tokens and logout

- [x] 7.1 Implement refresh-token issuance on login (random value, SHA-256 hash stored, new family, configurable TTL); verify an integration test that the database holds the hash and never the token value
- [x] 7.2 Implement `POST /api/v1/auth/refresh` with rotation; verify API tests for successful rotation (old token rejected afterwards), expired token, and deactivated user
- [x] 7.3 Implement reuse detection (revoke the whole family, audit `auth.refresh_reuse_detected`, commit, then 401); verify an API test that reusing a rotated token also kills the newest token in the family and writes the audit entry
- [x] 7.4 Implement `POST /api/v1/auth/logout` (revoke family, 204, audit `auth.logout`); verify API tests that the refresh token stops working and the audit entry exists

## 8. Authorization

- [x] 8.1 Implement `access/roles.py` and `access/permissions.py` (Role enum, Permission enum with category, `ROLE_PERMISSIONS` per the matrix in design D7); verify unit tests that each role's set matches the matrix and that `super_admin` holds no `business` permission
- [x] 8.2 Implement `require_permission(permission, audit_action=None)` and `authorize(actor, permission)`, recording a committed `denied` audit entry for write endpoints and storing the permission on the route via `openapi_extra`; verify unit and API tests with a test-only router that a denied write returns 403 `permission_denied`, writes the audit entry, and changes nothing
- [x] 8.3 Add `access/scope.py` (`Scope` value and `NotFound` convention for out-of-scope lookups) as the hook for later modules; verify a unit test that an empty scoped lookup raises `NotFound` with the same body as a missing record
- [x] 8.4 Add the route-table-driven RBAC matrix test (`tests/api/test_rbac_matrix.py`) covering every protected route Ã— every role, failing for any protected route not in the matrix; verify it passes for the auth routes and fails when a dummy unlisted protected route is registered

## 9. User management

- [x] 9.1 Implement the users repository and service (list with role/is_active filters and allow-listed sort, get, create with case-insensitive uniqueness and 12-character minimum password, update full name/role, activate/deactivate with token revocation, lockout protection) with audit entries carrying before/after values; verify integration tests for each service operation and its audit entry
- [x] 9.2 Implement `GET /api/v1/users` and `GET /api/v1/users/{id}` requiring `users.read`; verify API tests for filtering, pagination, 404 for unknown id, and 403 for an `aicte_admin`
- [x] 9.3 Implement `POST /api/v1/users` and `PATCH /api/v1/users/{id}` requiring `users.manage`; verify API tests for 201 create, 409 duplicate email, 422 weak password and unknown role, 422 unknown field, role change applied on the user's next request, and 403 plus `denied` audit entry for an `auditor` and a `regional_officer`
- [x] 9.4 Implement `POST /api/v1/users/{id}/deactivate` and `/activate` requiring `users.manage`; verify API tests that deactivation blocks login and existing tokens, self-deactivation and last-Super-Admin changes return 409, and an `aicte_admin` gets 403
- [x] 9.5 Extend the RBAC matrix entries for all user routes; verify the matrix test passes

## 10. Audit query API

- [x] 10.1 Implement `GET /api/v1/audit-logs` requiring `audit.read` (newest first, pagination, filters for actor, action, target type/id, outcome, from/to with from â‰¤ to); verify API tests for an `auditor` filtering by target, 422 for an inverted range, and 403 for a `scrutiny_officer`
- [x] 10.2 Verify by API test that `PUT`, `PATCH`, and `DELETE` on audit-log paths return 405 or 404 for every role including Super Admin, then extend the RBAC matrix for the audit route and verify it passes

## 11. Demo seed data

- [x] 11.1 Implement `python -m app.seed` (refuse in production, upsert by email, one active user per role plus one deactivated user on `flowguard.example.org`, `DEMO_PASSWORD`, single `system.seed` audit entry only when records are created, printed counts); verify integration tests that two runs give identical counts and that production is refused
- [x] 11.2 Verify by API test that every seeded active user can log in with the demo password and the deactivated one cannot

## 12. Backend container and documentation

- [x] 12.1 Write `backend/Dockerfile` per design D11 (uv builder, `python:3.13-slim` runtime, non-root user, `HEALTHCHECK`, migrations on start when enabled) and add the `backend` service to Compose (depends on healthy `db`, `env_file`, health check); verify `docker compose up --build` shows the backend healthy and `GET http://localhost:8000/api/v1/health/db` returns 200
- [x] 12.2 Verify data persistence by creating a user, running `docker compose down` and `up`, and confirming the user still exists; then verify `docker compose down -v` removes it
- [x] 12.3 Write `backend/README.md` covering prerequisites (Docker, uv), copying `.env.example`, starting services, running migrations, seeding, running tests, demo logins, and the permission matrix; verify each documented command runs as written on Windows

## 13. Integration checks

- [x] 13.1 Run the full suite with coverage (`uv run pytest --cov=app`) against `db_test` and verify all tests pass and the development database contents are unchanged afterwards
- [x] 13.2 Run an end-to-end smoke script against the Compose stack: seed, log in as Super Admin, create a user, change its role, deactivate it, read the audit log as Auditor, and confirm the expected entries appear in order
- [x] 13.3 Verify the OpenAPI document lists every `/api/v1` endpoint with bearer security on protected ones, and run `openspec validate aicte-backend-foundation --strict`

## Workflow follow-up

- Review the implemented change against the specs, then archive it with `/opsx:archive` so the seven capabilities become the project's main specs.
