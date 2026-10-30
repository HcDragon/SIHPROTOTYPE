# AICTE FlowGuard backend

FastAPI modular monolith for the AICTE FlowGuard prototype (Smart India Hackathon 2026).
All data is fictional. This backend does not connect to any real AICTE system.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Docker Desktop | 29+ with Compose v2 | Windows: use the WSL 2 backend |
| uv | 0.13+ | Installs the pinned Python 3.13 automatically |

You don't need to install Python yourself; `uv` downloads the version pinned in `.python-version`.

## First-time setup

Run these from the repository root (the folder that contains `docker-compose.yml`).

```sh
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
```

Edit `.env` and replace every `change-me-...` value. To generate a signing secret:

```sh
cd backend
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then put it in `JWT_SECRET`. Use only letters and digits in the database passwords, because they are placed inside connection URLs.

## Run everything in Docker

```sh
docker compose up -d --build                     # db, db_test and backend
docker compose exec backend python -m app.seed   # demo users (safe to run again)
```

- API: <http://localhost:8000/api/v1>
- Interactive docs: <http://localhost:8000/api/v1/docs>
- Readiness: <http://localhost:8000/api/v1/health/db>

The backend container applies migrations when it starts. Set `RUN_MIGRATIONS_ON_START=false` to turn that off.

To stop the services, run `docker compose down`. Data stays in the `pgdata` volume. To also delete the data, run `docker compose down -v`.

## Run the backend on your machine (for development)

```sh
docker compose up -d db db_test
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn --factory app.main:create_app --reload
```

## Tests

The tests use only the `db_test` database on port 5433. It keeps its data in memory and is wiped when the container restarts, and the suite never touches the development database.

```sh
docker compose up -d db_test
cd backend
uv run pytest                    # whole suite
uv run pytest --cov=app          # with coverage
uv run pytest tests/unit         # no database needed
uv run ruff check . && uv run ruff format --check .
```

| Folder | Covers |
|---|---|
| `tests/unit` | Settings validation, hashing, JWT, permission map, pagination, errors, log redaction |
| `tests/integration` | PostgreSQL: transactions, constraints, append-only audit trigger, services, seed |
| `tests/api` | HTTP endpoints, validation errors, authentication, RBAC matrix, audit API |
| `tests/migrations` | Upgrade, downgrade and upgrade again on a fresh database; models and migrations match |

To run a smoke test against a running stack, after seeding:

```sh
cd backend
uv run python scripts/smoke_test.py      # BASE_URL defaults to http://localhost:8000
```

## Demo logins

Every demo user's password is the `DEMO_PASSWORD` value in `.env`.

| Role | Email |
|---|---|
| Super Admin | `super.admin@flowguard.example.org` |
| AICTE Admin | `aicte.admin@flowguard.example.org` |
| Regional Officer | `regional.officer@flowguard.example.org` |
| Scrutiny Officer | `scrutiny.officer@flowguard.example.org` |
| EVC Coordinator | `evc.coordinator@flowguard.example.org` |
| Institution Representative | `institution.rep@flowguard.example.org` |
| Auditor | `auditor@flowguard.example.org` |
| (deactivated, cannot log in) | `inactive.officer@flowguard.example.org` |

## Permission matrix

| Permission | Super Admin | AICTE Admin | Regional Officer | Scrutiny Officer | EVC Coordinator | Institution Representative | Auditor |
|---|---|---|---|---|---|---|---|
| `users.read` | ✓ | | | | | | |
| `users.manage` | ✓ | | | | | | |
| `audit.read` | ✓ | ✓ | | | | | ✓ |

- Every authenticated user can call `/auth/me`, `/auth/refresh` and `/auth/logout`.
- `/health`, `/health/db` and `/auth/login` are public.
- Super Admin never gets business workflow permissions.

When you add a protected route, declare its permission with `**requires(Permission.X, ...)`. `tests/api/test_rbac_matrix.py` fails for any route that doesn't declare one.

## API conventions

- **Errors** are always `{"error": {"code", "message", "details", "request_id"}}`. `request_id` matches the `X-Request-ID` response header.
- **Status codes:** 401 when not authenticated, 403 when the permission is missing, 404 when the record is missing or outside the user's scope, 409 for conflicts, and 422 for validation errors.
- **Lists** accept `page`, `page_size` (at most 100) and `sort=field` or `sort=-field`. They return `{"items", "total", "page", "page_size"}`.
- **Tokens:**
  - The access token lasts 15 minutes and is sent as `Authorization: Bearer <access_token>`.
  - The refresh token lasts 7 days. Each refresh replaces it with a new one, and the server stores only its hash.
  - Reusing an old refresh token revokes all of that session's tokens.
- **Audit log:** the database rejects UPDATE, DELETE and TRUNCATE on `audit_logs`.

## Layout

```
app/
  core/      config, db session, errors, security, pagination, request id, logging, clock
  health/    liveness and readiness
  auth/      login, tokens, current user
  access/    roles, permissions, requires(), scope hook
  users/     user administration
  audit/     append-only audit log
  seed/      fictional demo data
alembic/     migrations (the only way to change the schema)
```

Each module has `router -> service -> repository -> models`, plus `schemas`. Services `flush()` and never `commit()`; each request is one transaction (`app/core/db.py`).

## Troubleshooting

- **`docker: command not found` on Windows right after installing:** open a new terminal so it picks up the updated PATH.
- **Readiness returns `"migrations": "pending"`:** run `uv run alembic upgrade head`.
- **Tests fail to connect:** run `docker compose up -d db_test`, and check that `TEST_DATABASE_URL` in `.env` matches the `TEST_POSTGRES_*` values.
