Focus here is on correlation and metadata.

Log Format: JSON (Line-delimited).

Mandatory Fields:

timestamp: ISO8601.

correlation_id: Must be injected at the Gateway and propagated to every service call and event.

service_name: Identifies the source.

level: (DEBUG, INFO, WARN, ERROR, FATAL).

Policy: "Never log PII. Logs are for local diagnostics; Tracing/Telemetry is for system flow."