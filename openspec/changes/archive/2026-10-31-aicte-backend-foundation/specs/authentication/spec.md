# Spec Delta

## Purpose

Defines how FlowGuard users prove their identity: password login, short-lived access tokens, rotating refresh tokens, logout, and identifying the current user on every request.

## ADDED Requirements

### Requirement: Secure password storage
The system SHALL store user passwords only as Argon2id hashes with a per-password salt and SHALL never return, log, or audit a password or password hash.

#### Scenario: Password is hashed
- **WHEN** a user account is created with a password
- **THEN** the stored credential is an Argon2id hash and does not contain the plaintext password

#### Scenario: Hash not exposed
- **WHEN** any user record is returned by the API or written to the audit log
- **THEN** it contains neither the password nor the password hash

### Requirement: Password login
The system SHALL provide `POST /api/v1/auth/login` accepting an email (case-insensitive) and password. On success it SHALL return an access token, a refresh token, the token type `bearer`, and the access token lifetime in seconds.

#### Scenario: Successful login
- **WHEN** an active user submits their correct email and password
- **THEN** the system responds with HTTP 200 containing `access_token`, `refresh_token`, `token_type` = `bearer`, and `expires_in`

#### Scenario: Successful login is audited
- **WHEN** a user logs in successfully
- **THEN** an audit entry is recorded with action `auth.login`, the user as actor and target, and outcome `success`

### Requirement: Uniform login failure
Login SHALL fail with HTTP 401, code `invalid_credentials`, and an identical message whether the email is unknown, the password is wrong, or the account is deactivated, so responses do not reveal which accounts exist.

#### Scenario: Wrong password
- **WHEN** a user submits a valid email with an incorrect password
- **THEN** the system responds with HTTP 401 and code `invalid_credentials`

#### Scenario: Unknown email
- **WHEN** a client submits an email that belongs to no account
- **THEN** the response status, code, and message are identical to the wrong-password case

#### Scenario: Deactivated account
- **WHEN** a deactivated user submits correct credentials
- **THEN** the system responds with HTTP 401 and code `invalid_credentials` and issues no tokens

#### Scenario: Failed login is audited
- **WHEN** a login attempt fails
- **THEN** an audit entry is recorded with action `auth.login`, outcome `failure`, no actor, and the submitted email in the details, but never the submitted password

### Requirement: Access tokens
Access tokens SHALL be signed JWTs containing the user id, role, issue time, expiry, and a unique token id, with a configurable lifetime defaulting to 15 minutes. Protected endpoints SHALL accept them only as an `Authorization: Bearer` header.

#### Scenario: Valid token accepted
- **WHEN** a client calls a protected endpoint with a valid, unexpired access token
- **THEN** the request is processed as the token's user

#### Scenario: Missing token
- **WHEN** a client calls a protected endpoint without an `Authorization` header
- **THEN** the system responds with HTTP 401, code `not_authenticated`, and a `WWW-Authenticate: Bearer` header

#### Scenario: Expired, tampered, or malformed token
- **WHEN** a client calls a protected endpoint with an expired token, a token with an altered payload or signature, a token signed with a different algorithm, or a malformed value
- **THEN** the system responds with HTTP 401 and code `invalid_token`

### Requirement: Current user resolved on every request
For every authenticated request the system SHALL load the user from the database and SHALL treat a deactivated or deleted user as unauthenticated. Authorization SHALL use the role stored in the database, not the role claim in the token.

#### Scenario: User deactivated after token issued
- **WHEN** a user's account is deactivated and they then use a previously issued, unexpired access token
- **THEN** the system responds with HTTP 401 and code `invalid_token`

#### Scenario: Role changed after token issued
- **WHEN** a user's role is changed and they then use a previously issued access token
- **THEN** permissions are evaluated using the new role

### Requirement: Current user endpoint
The system SHALL provide `GET /api/v1/auth/me` returning the authenticated user's id, email, full name, role, and the list of permissions that role grants.

#### Scenario: Any role reads own profile
- **WHEN** an authenticated user of any role requests `GET /api/v1/auth/me`
- **THEN** the system returns that user's profile and permissions

#### Scenario: Anonymous request
- **WHEN** an unauthenticated client requests `GET /api/v1/auth/me`
- **THEN** the system responds with HTTP 401

### Requirement: Refresh token storage
Refresh tokens SHALL be opaque, high-entropy random values with a configurable lifetime defaulting to 7 days. The system SHALL store only a SHA-256 hash of each refresh token, together with its user, family, expiry, and revocation state.

#### Scenario: Only hash stored
- **WHEN** a refresh token is issued
- **THEN** the database contains its hash and not the token value

### Requirement: Refresh token rotation
The system SHALL provide `POST /api/v1/auth/refresh`, which exchanges a valid refresh token for a new access token and a new refresh token and immediately revokes the presented refresh token.

#### Scenario: Successful refresh
- **WHEN** a client presents a valid, unexpired, unrevoked refresh token of an active user
- **THEN** the system returns a new access token and a new refresh token, and the presented refresh token can no longer be used

#### Scenario: Expired refresh token
- **WHEN** a client presents an expired refresh token
- **THEN** the system responds with HTTP 401 and code `invalid_token`

#### Scenario: Refresh for deactivated user
- **WHEN** a client presents a refresh token belonging to a deactivated user
- **THEN** the system responds with HTTP 401 and code `invalid_token`

### Requirement: Refresh token reuse detection
If an already-rotated refresh token is presented again, the system SHALL treat it as possible theft: it SHALL reject the request and revoke every refresh token in that token's family.

#### Scenario: Reuse of rotated token
- **WHEN** a client presents a refresh token that was already exchanged
- **THEN** the system responds with HTTP 401, the newest refresh token from the same family also stops working, and an audit entry is recorded with action `auth.refresh_reuse_detected`

### Requirement: Logout and revocation
The system SHALL provide `POST /api/v1/auth/logout`, which revokes the presented refresh token's family. Deactivating a user SHALL revoke all of that user's refresh tokens.

#### Scenario: Logout
- **WHEN** an authenticated user logs out with their refresh token
- **THEN** the system responds with HTTP 204, that refresh token can no longer be used, and an audit entry is recorded with action `auth.logout`

#### Scenario: Deactivation revokes sessions
- **WHEN** a user is deactivated
- **THEN** every refresh token issued to that user is rejected afterwards
