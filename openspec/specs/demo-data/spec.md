# demo-data Specification

## Purpose

Provides reproducible, clearly fictional demonstration data so that FlowGuard can be demonstrated and manually tested from a fresh database with a single command.

## Requirements

### Requirement: Seed command
The project SHALL provide a seed command that loads demonstration data into a migrated database. It SHALL refuse to run when the environment is `production`.

#### Scenario: Seeding a fresh database
- **WHEN** the seed command runs against a freshly migrated development database
- **THEN** it completes successfully and reports how many records it created

#### Scenario: Production refused
- **WHEN** the seed command runs with environment `production`
- **THEN** it exits with an error and writes nothing

### Requirement: Idempotent seeding
Running the seed command more than once SHALL leave the same data as running it once, without errors or duplicate records.

#### Scenario: Second run
- **WHEN** the seed command runs twice in a row
- **THEN** the second run succeeds, creates no new records, and the record counts match those after the first run

### Requirement: Demo users for every role
The seed data SHALL include at least one active user for each of the seven roles, plus one deactivated user, so every role and the deactivation behavior can be demonstrated.

#### Scenario: Each role can log in
- **WHEN** the database has been seeded
- **THEN** a demo user of each role can log in with the documented demo password, and the deactivated demo user cannot

### Requirement: Clearly fictional data
All seeded names, email addresses, and identifiers SHALL be fictional and recognizable as such, using a reserved example domain for email addresses, and SHALL NOT reference real AICTE staff, institutions, or systems.

#### Scenario: Fictional emails
- **WHEN** seeded user records are inspected
- **THEN** every email address uses a reserved example domain such as `example.org`

### Requirement: Demo credentials are configurable
The demo password SHALL come from an environment variable with a documented development default, and the seed command SHALL NOT print passwords other than that configured demo password.

#### Scenario: Custom demo password
- **WHEN** the seed command runs with the demo password environment variable set
- **THEN** seeded users can log in with that password
