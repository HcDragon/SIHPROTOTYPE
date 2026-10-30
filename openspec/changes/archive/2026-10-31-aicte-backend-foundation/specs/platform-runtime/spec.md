# Spec Delta

## Purpose

Defines how the FlowGuard backend is configured, started, checked for health, and run with its PostgreSQL database in a reproducible local environment.

## ADDED Requirements

### Requirement: Environment-based configuration
The backend SHALL read all configuration, including database connection settings and signing secrets, from environment variables (optionally loaded from a local `.env` file). The repository SHALL contain only a `.env.example` with placeholder values and SHALL NOT contain real secrets.

#### Scenario: Configuration from environment
- **WHEN** the backend starts with database and secret settings provided as environment variables
- **THEN** it uses those values and no value is taken from source code defaults for secrets

#### Scenario: Secrets are not committed
- **WHEN** the repository contents are inspected
- **THEN** `.env` files are ignored by version control and `.env.example` contains only placeholders

### Requirement: Startup refuses unsafe configuration
The backend SHALL refuse to start, with an error message naming the problem, when a required setting is missing or when the token signing secret is shorter than 32 characters or equals the `.env.example` placeholder outside the `development` and `test` environments.

#### Scenario: Missing database URL
- **WHEN** the backend starts without a database connection setting
- **THEN** startup fails with an error naming the missing setting

#### Scenario: Placeholder secret outside development
- **WHEN** the backend starts with environment `production` and the placeholder signing secret
- **THEN** startup fails with an error stating that the signing secret must be changed

### Requirement: Liveness health check
The system SHALL expose `GET /api/v1/health`, which requires no authentication and returns HTTP 200 with `{"status": "ok"}` whenever the process is serving requests, without contacting the database.

#### Scenario: Liveness
- **WHEN** a client requests `GET /api/v1/health`
- **THEN** the system responds with HTTP 200 and `{"status": "ok"}`

### Requirement: Database readiness health check
The system SHALL expose `GET /api/v1/health/db`, which requires no authentication and reports whether the database is reachable and whether its schema is at the latest migration. It SHALL return HTTP 200 when both hold and HTTP 503 otherwise, without revealing connection details.

#### Scenario: Database ready
- **WHEN** the database is reachable and fully migrated
- **THEN** `GET /api/v1/health/db` returns HTTP 200 with `{"status": "ok", "database": "ok", "migrations": "current"}`

#### Scenario: Database unreachable
- **WHEN** the database cannot be reached
- **THEN** `GET /api/v1/health/db` returns HTTP 503 with `database` set to `unavailable` and no host, user, or password in the body

#### Scenario: Pending migrations
- **WHEN** the database is reachable but not at the latest migration
- **THEN** `GET /api/v1/health/db` returns HTTP 503 with `migrations` set to `pending`

### Requirement: Migration-managed schema
The database schema SHALL be created and changed only by versioned migrations. Applying all migrations to an empty PostgreSQL database SHALL produce the complete schema, and every migration SHALL be reversible.

#### Scenario: Fresh database
- **WHEN** all migrations are applied to an empty PostgreSQL database
- **THEN** the readiness check reports `migrations` as `current` and all application tables exist

#### Scenario: Reversible migrations
- **WHEN** all migrations are applied, then fully reverted, then applied again
- **THEN** each step succeeds and the final schema is identical to the first

### Requirement: Reproducible containerized runtime
The project SHALL provide a Docker Compose configuration that starts PostgreSQL with a persistent data volume and a health check, and the backend service built from the backend Dockerfile, which waits for a healthy database and exposes its own health check. A separate test database SHALL be available that does not share data with the development database.

#### Scenario: One-command startup
- **WHEN** a developer with Docker installed copies `.env.example` to `.env` and runs `docker compose up`
- **THEN** PostgreSQL and the backend start, the backend container becomes healthy, and `GET /api/v1/health/db` returns HTTP 200 after migrations are applied

#### Scenario: Data persists across restarts
- **WHEN** the Compose services are stopped and started again without removing volumes
- **THEN** previously stored data is still present

#### Scenario: Test database isolation
- **WHEN** the automated test suite runs
- **THEN** it uses the test database only and the development database contents are unchanged
