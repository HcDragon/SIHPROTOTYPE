# Spec Delta

## Purpose

Defines FlowGuard's fixed roles, the permissions each role grants, and how the backend enforces them on every protected endpoint and service operation, independent of any frontend.

## ADDED Requirements

### Requirement: Fixed role set
Every user SHALL have exactly one of these roles: `super_admin`, `aicte_admin`, `regional_officer`, `scrutiny_officer`, `evc_coordinator`, `institution_representative`, `auditor`. Roles SHALL be defined by the system and SHALL NOT be created, renamed, or deleted at runtime.

#### Scenario: Unknown role rejected
- **WHEN** a request tries to assign a role outside the fixed set
- **THEN** the system responds with HTTP 422 and code `validation_error`

### Requirement: Role-permission map
Each role SHALL grant a fixed, documented set of named permissions. In this change the permissions are `users.read` and `users.manage` (granted to `super_admin` only) and `audit.read` (granted to `super_admin`, `aicte_admin`, and `auditor`). Every other role SHALL hold none of these.

#### Scenario: Permissions reported per role
- **WHEN** a user of each role requests `GET /api/v1/auth/me`
- **THEN** the returned permissions exactly match that role's documented set

### Requirement: Super Admin holds no business workflow permissions
The `super_admin` role SHALL be limited to system administration and audit reading and SHALL NOT be granted any permission that approves, rejects, transitions, or otherwise acts on applications, scrutiny, EVC, compliance, or alerts, in this or any later change.

#### Scenario: Business permission check
- **WHEN** the role-permission map is evaluated for `super_admin`
- **THEN** it contains no permission in a business workflow category

#### Scenario: Super Admin denied a business action
- **WHEN** a Super Admin calls any endpoint that requires a business workflow permission
- **THEN** the system responds with HTTP 403 and code `permission_denied`

### Requirement: Backend enforcement
Every protected endpoint SHALL declare the permission it requires and the backend SHALL check it before performing any work. Service operations that change data SHALL re-check the permission, so no code path can perform a protected action without it.

#### Scenario: Unauthorized role denied
- **WHEN** an authenticated user whose role lacks the required permission calls a protected endpoint, for example an `auditor` calling `POST /api/v1/users`
- **THEN** the system responds with HTTP 403 and code `permission_denied` and no data is changed

#### Scenario: Every protected endpoint covered
- **WHEN** the automated RBAC test runs every role against every protected endpoint
- **THEN** each response matches the documented permission matrix, and an endpoint missing from the matrix fails the test

### Requirement: Denied write attempts are audited
When an authenticated user is denied a state-changing action for lack of permission, the system SHALL record an audit entry with outcome `denied`, the actor, the attempted action, and the target if known. Denied read requests SHALL NOT be audited.

#### Scenario: Denied write recorded
- **WHEN** an `institution_representative` attempts `PATCH /api/v1/users/{id}`
- **THEN** the system responds with HTTP 403 and an audit entry is recorded with action `users.update`, outcome `denied`, and that user as actor

### Requirement: Record scope returns not found
When later capabilities restrict a role to a subset of records (own institution, own region, assigned items), a request for an existing record outside the caller's scope SHALL return HTTP 404 with code `not_found`, indistinguishable from a request for a record that does not exist.

#### Scenario: Out-of-scope record
- **WHEN** a user requests a record that exists but lies outside their scope
- **THEN** the response status, code, and message are identical to those for a nonexistent record
