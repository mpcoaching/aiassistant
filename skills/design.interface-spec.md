# Skill: Design Interface Specification

## Purpose
Create detailed interface specifications that define how components interact, including API contracts, message formats, and integration points.

## Inputs
- solution-architecture
- requirements
- adrs

## Process

### 1. Review Architecture and Requirements
Read:
- Solution architecture document
- Functional and non-functional requirements
- ADRs that impact interface design
- Existing system context

### 2. Identify Interfaces
For each component in the architecture:
- List all external interfaces
- Identify integration points with other systems
- Document communication patterns (REST, GraphQL, gRPC, message queue, etc.)

### 3. Define API Contracts
For each API endpoint:
- **HTTP Method**: GET, POST, PUT, DELETE, PATCH
- **Path**: `/api/v1/resource`
- **Description**: What this endpoint does
- **Request**:
  - Headers (Content-Type, Authorization, etc.)
  - Path parameters
  - Query parameters
  - Request body schema (JSON Schema)
- **Response**:
  - Success response (200, 201, etc.) with schema
  - Error responses (400, 401, 403, 404, 500, etc.) with error format
  - Response headers
- **Authentication**: Required auth method
- **Rate limiting**: Limits if applicable
- **Idempotency**: Whether the operation is idempotent

### 4. Define Message Formats
For asynchronous communication:
- Message schema (JSON, Avro, Protobuf, etc.)
- Message envelope (headers, metadata)
- Event types and their payloads
- Message versioning strategy

### 5. Specify Integration Interfaces
For external system integrations:
- Integration protocol (REST, SOAP, gRPC, etc.)
- Authentication mechanism
- Data mapping (source → target)
- Transformation rules
- Error handling strategy
- Retry and timeout policies

### 6. Document Error Handling
For each interface:
- Error codes and their meanings
- Error response format
- Retry strategy
- Fallback behavior
- Circuit breaker configuration (if applicable)

### 7. Define Edge Cases
Document how the interface handles:
- Invalid input
- Missing required fields
- Authorization failures
- Rate limit exceeded
- Service unavailable
- Partial failures

### 8. Create Interface Specification Document
Create `interface-specification.md` with:

```markdown
# Interface Specification

## Overview
[Brief description of the system and its interfaces]

## API Endpoints

### [Resource Name]

#### [Operation]
- **Method**: [HTTP method]
- **Path**: [endpoint path]
- **Description**: [what it does]
- **Authentication**: [auth requirement]
- **Request**: [schema]
- **Response**: [schema]
- **Errors**: [error codes and meanings]

## Message Formats

### [Event/Topic Name]
- **Schema**: [message schema]
- **Producer**: [component that produces]
- **Consumer**: [component that consumes]
- **Description**: [purpose]

## Integration Points

### [External System]
- **Protocol**: [integration protocol]
- **Authentication**: [auth method]
- **Data Mapping**: [source to target mapping]
- **Error Handling**: [strategy]

## Error Handling
[Common error patterns and responses]

## Versioning
[API versioning strategy]

## Security Considerations
[Security requirements for interfaces]
```

## Output
- interface-specification.md

## Quality Criteria
- **Completeness**: All interfaces are documented
- **Clarity**: Specifications are unambiguous
- **Consistency**: Naming and patterns are consistent
- **Testability**: Interfaces can be tested against the spec
- **Implementability**: Developers can implement from the spec