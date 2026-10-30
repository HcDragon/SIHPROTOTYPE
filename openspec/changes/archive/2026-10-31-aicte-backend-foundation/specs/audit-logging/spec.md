# Spec Delta

## Purpose

Provides a tamper-resistant, append-only record of important actions in FlowGuard, showing who did what to which record and when, with before and after values, for accountability and review.

## ADDED Requirements

### Requirement: Audit entry contents
Each audit entry SHALL record: a unique id, the UTC timestamp, the actor's user id and role (empty for anonymous actions), the action name, the target type and id, the outcome (`success`, `failure`, or `denied`), before and after values where relevant, and the request id.

#### Scenario: Entry for a change
- **WHEN** a Super Admin changes a user's role
- **THEN** the resulting audit entry contains the actor id and role, action `users.update`, target type `user` with the user's id, outcome `success`, before and after role values, the request id, and a UTC timestamp

### Requirement: Changes and their audit entries are atomic
A state-changing action and its audit entry SHALL be saved together: if either fails, neither is saved.

#### Scenario: Audit write fails
- **WHEN** recording the audit entry for a user update fails
- **THEN** the user update is not saved and the client receives an error

### Requirement: Sensitive values excluded
Audit entries SHALL NOT contain passwords, password hashes, tokens, token hashes, or signing secrets in any field.

#### Scenario: No secrets in audit
- **WHEN** audit entries produced by login, token refresh, logout, and user creation are inspected
- **THEN** none contains a password, hash, or token value

### Requirement: Append-only storage
Audit entries SHALL be immutable once written. The database SHALL reject any update or delete of audit entries made through the application's database account, and the API SHALL offer no endpoint to modify or delete them.

#### Scenario: Update rejected by database
- **WHEN** the application's database account attempts to update an existing audit entry
- **THEN** the database rejects the statement and the entry is unchanged

#### Scenario: Delete rejected by database
- **WHEN** the application's database account attempts to delete an audit entry
- **THEN** the database rejects the statement and the entry still exists

#### Scenario: No modification endpoint
- **WHEN** any user, including a Super Admin, sends `PUT`, `PATCH`, or `DELETE` to an audit-log path
- **THEN** the system responds with HTTP 405 or 404 and no entry changes

### Requirement: Query audit log
The system SHALL provide `GET /api/v1/audit-logs`, requiring `audit.read`, returning entries newest first by default, paginated, and filterable by actor id, action, target type, target id, outcome, and a from/to time range.

#### Scenario: Authorized reader filters entries
- **WHEN** an `auditor` requests audit entries filtered by target type `user` and a target id
- **THEN** the system returns only matching entries, newest first

#### Scenario: Unauthorized role denied
- **WHEN** a `scrutiny_officer` requests `GET /api/v1/audit-logs`
- **THEN** the system responds with HTTP 403 and code `permission_denied`

#### Scenario: Invalid time range
- **WHEN** a client requests entries with a `from` time later than its `to` time
- **THEN** the system responds with HTTP 422 and code `validation_error`
