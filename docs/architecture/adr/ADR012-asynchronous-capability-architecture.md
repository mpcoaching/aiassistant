## ADR-005: Asynchronous Capability Architecture


The platform will use synchronous calls for local execution and immediate responses, but capability coordination, lifecycle management, state changes, and cross-component communication should use asynchronous event-driven patterns.