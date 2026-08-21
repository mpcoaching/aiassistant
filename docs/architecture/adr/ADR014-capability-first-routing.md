# ADR-014: Capability-First Routing in Assistant

Status: Proposed

Decision

`AssistantChatService.chat()` MUST perform capability matching BEFORE strategy selection and reasoning. Capability execution short-circuits the reasoning pipeline.

Context

The current Assistant routing is:

  request → recognise() → decide() → Session → runtime.invoke()

This means every request enters the reasoning pipeline, even when a deterministic capability could satisfy it directly. This violates Principle 1 (recognition before reasoning) and Principle 2 (reason only when uncertainty exists).

The architecture defines capabilities as first-class execution assets, but the chat service does not currently check them.

Decision

Insert a CapabilityMatcher between recognise() and decide():

  request → recognise()
              ↓
       CapabilityMatcher.match()
              ↓
    ┌─────────┴─────────┐
    │                   │
  candidates           no candidates
    │                   │
    ↓                   ↓
 human selects      decide() → strategy → session
 execute capability

Rationale

1. Deterministic capabilities are the shortest path through the system.
2. Reasoning should occur when capability is absent or insufficient, not merely because every request enters the reasoning pipeline.
3. This preserves the existing reasoning pipeline for non-capability requests while making capability execution the preferred path.

Consequences

- `AssistantChatService.chat()` gains a capability check after `recognise()`.
- The reasoning pipeline (`decide() → Session → runtime`) is preserved for non-capability requests.
- Capability execution short-circuits to `CapabilityExecutor`.
- The existing `_find_previous_solution()` check is deferred until after capability execution is proven.

Related

- ADR-010: Provider-Based Architecture
- ADR-013: Capability-Oriented Repository Structure
- ADR-015: Human-as-Approval-Layer for Capability Specifications
