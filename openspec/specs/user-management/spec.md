# user-management Specification

## Purpose

Lets a Super Admin administer FlowGuard user accounts: list and view users, create accounts, change names and roles, and deactivate or reactivate accounts.

## Requirements

### Requirement: List and view users
The system SHALL provide `GET /api/v1/users` (paginated, filterable by `role` and `is_active`, sortable by `email`, `full_name`, and `created_at`) and `GET /api/v1/users/{id}`, both requiring `users.read`. User responses SHALL include id, email, full name, role, active flag, and created and updated timestamps.

#### Scenario: Super Admin lists users
- **WHEN** a Super Admin requests `GET /api/v1/users?role=auditor`
- **THEN** the system returns a paginated list containing only users with role `auditor`

#### Scenario: Unauthorized role denied listing
- **WHEN** an `aicte_admin` requests `GET /api/v1/users`
- **THEN** the system responds with HTTP 403 and code `permission_denied`

#### Scenario: Unknown user
- **WHEN** a Super Admin requests `GET /api/v1/users/{id}` for an id that does not exist
- **THEN** the system responds with HTTP 404 and code `not_found`

### Requirement: Create user
The system SHALL provide `POST /api/v1/users`, requiring `users.manage`, accepting email, full name, role, and an initial password of at least 12 characters. Emails SHALL be unique case-insensitively.

#### Scenario: User created
- **WHEN** a Super Admin creates a user with a new email, valid role, and valid password
- **THEN** the system responds with HTTP 201 and the new user, who can then log in

#### Scenario: Creation is audited
- **WHEN** a user is created
- **THEN** an audit entry is recorded with action `users.create`, the Super Admin as actor, the new user as target, no before values, and after values containing email, full name, role, and active flag but no password or hash

#### Scenario: Duplicate email
- **WHEN** a Super Admin creates a user whose email matches an existing one in any letter case
- **THEN** the system responds with HTTP 409 and code `conflict`

#### Scenario: Weak password
- **WHEN** the initial password is shorter than 12 characters
- **THEN** the system responds with HTTP 422 and code `validation_error`

#### Scenario: Unauthorized role denied creation
- **WHEN** an `auditor` attempts `POST /api/v1/users`
- **THEN** the system responds with HTTP 403, no user is created, and an audit entry with outcome `denied` is recorded

### Requirement: Update user
The system SHALL provide `PATCH /api/v1/users/{id}`, requiring `users.manage`, to change a user's full name and role. Email and password SHALL NOT be changeable through this endpoint.

#### Scenario: Role changed
- **WHEN** a Super Admin changes a user's role from `scrutiny_officer` to `regional_officer`
- **THEN** the system returns the updated user and the user's next request is authorized with the new role

#### Scenario: Update is audited
- **WHEN** a user's role is changed
- **THEN** an audit entry is recorded with action `users.update`, the Super Admin as actor, the user as target, before values containing the old role, and after values containing the new role

#### Scenario: Unauthorized role denied update
- **WHEN** a `regional_officer` attempts `PATCH /api/v1/users/{id}`
- **THEN** the system responds with HTTP 403 and the user is unchanged

### Requirement: Deactivate and reactivate user
The system SHALL provide `POST /api/v1/users/{id}/deactivate` and `POST /api/v1/users/{id}/activate`, requiring `users.manage`. Users SHALL never be hard-deleted. Deactivation SHALL immediately invalidate the user's access and refresh tokens.

#### Scenario: Deactivation
- **WHEN** a Super Admin deactivates a user
- **THEN** the user's active flag becomes false, their existing tokens are rejected, and they cannot log in

#### Scenario: Deactivation is audited
- **WHEN** a user is deactivated or reactivated
- **THEN** an audit entry is recorded with action `users.deactivate` or `users.activate`, with before and after values of the active flag

#### Scenario: Unauthorized role denied deactivation
- **WHEN** an `aicte_admin` attempts to deactivate a user
- **THEN** the system responds with HTTP 403 and the user remains active

### Requirement: Super Admin lockout protection
A Super Admin SHALL NOT be able to deactivate their own account or change their own role, and the system SHALL reject any change that would leave no active Super Admin.

#### Scenario: Self-deactivation rejected
- **WHEN** a Super Admin attempts to deactivate their own account
- **THEN** the system responds with HTTP 409 and code `conflict` and the account stays active

#### Scenario: Last Super Admin protected
- **WHEN** a change would demote or deactivate the only active Super Admin
- **THEN** the system responds with HTTP 409 and code `conflict` and nothing changes
