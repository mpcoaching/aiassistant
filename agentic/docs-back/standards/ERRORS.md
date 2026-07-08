Standard Envelope:

JSON
{
  "code": "FACTORY_ERR_001", 
  "message": "Human readable summary",
  "correlation_id": "UUID",
  "timestamp": "ISO8601",
  "retryable": boolean
}
Classification: Define the categories (e.g., VALIDATION, UNAUTHORIZED, DATABASE_FAILURE, DOWNSTREAM_TIMEOUT).

Propagation Rule: "Errors must be serialized into events if they are fatal, or returned as 4xx/5xx in synchronous API calls."