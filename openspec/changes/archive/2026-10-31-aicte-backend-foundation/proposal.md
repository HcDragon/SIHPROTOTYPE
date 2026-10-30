# Proposal

## Why

AICTE FlowGuard has no code yet. Every planned feature (application tracking, scrutiny, EVC coordination, compliance, alerts) depends on the same foundation: a running backend on a reproducible database, authenticated users with roles, backend-enforced permissions, and an append-only audit trail. Building these once, first, means every later change inherits consistent security, error handling, and testability instead of reinventing them.

## What Changes

- Add a FastAPI backend (modular monolith) under `backend/` with separated routers, services, repositories, models, schemas, core configuration, authentication, authorization, and audit modules.
- Add Docker Compose with a PostgreSQL service (persistent volume, health check), a separate disposable test database, and a backend service built from a backend Dockerfile.
- Add environment-based configuration with a committed `.env.example`; the backend refuses to start without required secrets.
- Add SQLAlchemy 2.x database access and an Alembic baseline migration for users, refresh tokens, and audit logs.
- Add `/api/v1` routing, a single error response format, request validation, paginated list responses, and generated OpenAPI documentation.
- Add liveness and database-readiness health endpoints.
- Add password login with Argon2id hashing, short-lived JWT access tokens, rotating refresh tokens stored hashed, logout, and a current-user endpoint.
- Add the seven fixed roles with a role-to-permission map enforced in endpoints and services.
- Add minimal user administration for Super Admin (list, create, change role, deactivate) so RBAC and audit logging have real, demonstrable state changes.
- Add append-only audit logging, protected in the database, with a filtered read API for authorized roles.
- Add an idempotent seed command that creates fictional demo users, one or more per role.
- Add unit, API, PostgreSQL integration, authentication, RBAC, audit, and migration tests.

## Capabilities

### New Capabilities
- `api-conventions`: `/api/v1` versioning, error response format, validation errors, pagination, and API documentation.
- `platform-runtime`: environment configuration, startup checks, health endpoints, containerized runtime, and migration-managed schema.
- `authentication`: login, access and refresh tokens, token validation, logout, and the current-user endpoint.
- `access-control`: the seven roles, the role-permission map, and backend enforcement with consistent denial behavior.
- `user-management`: Super Admin administration of user accounts and roles.
- `audit-logging`: recording, protection, and querying of append-only audit entries.
- `demo-data`: reproducible, fictional seed data for demonstrations and manual testing.

### Modified Capabilities
None (no existing specs).

## Affected Roles

All seven roles can log in and see their own profile. Super Admin gains user administration. Super Admin, AICTE Admin, and Auditor can read the audit log. Other roles have no business capabilities yet; those arrive in later changes.

## Out of Scope

- Frontend implementation of any kind.
- Regions, institutions, applications, workflow transitions, scrutiny, EVC, compliance, alerts, documents, and AI features (later changes).
- Record-level scope rules (own institution, own region, assigned applications); they need entities that do not exist yet. This change provides only the hook for them.
- Self-service registration, password reset, email delivery, multi-factor authentication, and SSO.
- Multiple roles per user or runtime-editable roles and permissions.
- Rate limiting, production deployment, TLS termination, CI pipelines, and backups.
- Supabase, SQLite, managed databases, microservices, message brokers, and any real AICTE system or data.

## Impact

- New: `backend/` (application, migrations, tests), `docker-compose.yml`, `.env.example`, `.gitignore`.
- New API surface: `/api/v1/health*`, `/api/v1/auth/*`, `/api/v1/users*`, `/api/v1/audit-logs`.
- New pinned Python dependencies (see design.md).
- Developers need Docker Desktop (Windows: WSL 2 backend) and uv.
