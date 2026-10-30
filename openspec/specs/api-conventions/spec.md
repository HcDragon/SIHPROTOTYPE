# api-conventions Specification

## Purpose

Defines the shared conventions every FlowGuard API endpoint follows: versioned paths, a single error format, validation behavior, pagination, and published API documentation.

## Requirements

### Requirement: Versioned API paths
All business and system endpoints SHALL be served under the `/api/v1` path prefix. Requests to unknown paths SHALL return HTTP 404 in the standard error format.

#### Scenario: Versioned endpoint is reachable
- **WHEN** a client requests `GET /api/v1/health`
- **THEN** the system responds with HTTP 200

#### Scenario: Unknown path
- **WHEN** a client requests `GET /api/v1/does-not-exist`
- **THEN** the system responds with HTTP 404 and a body in the standard error format with code `not_found`

### Requirement: Standard error response format
Every error response SHALL be JSON of the form `{"error": {"code", "message", "details", "request_id"}}`, where `code` is a stable machine-readable string, `message` is human-readable, `details` is an object or list (possibly empty), and `request_id` matches the `X-Request-ID` response header.

#### Scenario: Error carries request id
- **WHEN** any request fails with an error
- **THEN** the response body follows the standard error format and `error.request_id` equals the `X-Request-ID` response header

#### Scenario: Unexpected server error
- **WHEN** an unhandled exception occurs while processing a request
- **THEN** the system responds with HTTP 500, code `internal_error`, a generic message, and no stack trace, SQL, or secret values in the body

### Requirement: Request validation
The system SHALL validate request bodies, path parameters, and query parameters before any business logic runs, and SHALL reject invalid input with HTTP 422, code `validation_error`, and `details` listing each invalid field and the reason.

#### Scenario: Invalid field
- **WHEN** a client sends a request body with a missing required field and a field of the wrong type
- **THEN** the system responds with HTTP 422, code `validation_error`, and one `details` entry per invalid field naming its location

#### Scenario: Unknown fields rejected
- **WHEN** a client sends a request body containing a field the endpoint does not accept
- **THEN** the system responds with HTTP 422 and does not apply any part of the request

### Requirement: Standard status codes
The system SHALL use HTTP 401 for missing or invalid authentication, 403 for an authenticated user lacking a permission, 404 for missing records or records outside the caller's scope, 409 for conflicts with current state, and 422 for invalid input.

#### Scenario: Conflict
- **WHEN** a request would create a record that violates a uniqueness rule, such as a duplicate user email
- **THEN** the system responds with HTTP 409 and code `conflict`

### Requirement: Paginated list responses
List endpoints SHALL accept `page` (default 1) and `page_size` (default 20, maximum 100) query parameters and SHALL return `{"items", "total", "page", "page_size"}`. List endpoints SHALL accept a `sort` parameter limited to documented fields, with a `-` prefix for descending order.

#### Scenario: Default pagination
- **WHEN** a client lists a collection without pagination parameters
- **THEN** the response contains at most 20 items, `page` is 1, `page_size` is 20, and `total` is the total number of matching records

#### Scenario: Page size limit
- **WHEN** a client requests `page_size=500`
- **THEN** the system responds with HTTP 422 and code `validation_error`

#### Scenario: Unsupported sort field
- **WHEN** a client requests sorting by a field that is not documented as sortable for that endpoint
- **THEN** the system responds with HTTP 422 and code `validation_error`

### Requirement: Generated API documentation
The system SHALL publish an OpenAPI document and interactive documentation describing every `/api/v1` endpoint, its request and response schemas, its error responses, and its bearer-token security requirement.

#### Scenario: OpenAPI document available
- **WHEN** a client requests the OpenAPI document
- **THEN** the system returns a valid OpenAPI document that lists every `/api/v1` endpoint and marks protected endpoints as requiring a bearer token

### Requirement: UTC timestamps
All timestamps in API responses SHALL be ISO 8601 strings in UTC with an explicit offset.

#### Scenario: Timestamp format
- **WHEN** any response includes a timestamp
- **THEN** the value is an ISO 8601 string ending in `Z` or `+00:00`
