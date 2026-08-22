# ADR-042: Capability Execution Binding Separation

Status: Accepted

Decision

The `Capability` domain model must not carry operational execution metadata.

Context

The current `Capability` model in `packages/capability_registry/src/capabilities.py` carries
four fields that describe how a capability is invoked, not what the capability is:

- `execution_mode` (ai_mediated | compiled)
- `transport` (tier2_inprocess | tier3_bus)
- `ai_spec` (prompt composition adapter)
- `compiled_ref` (module path and entrypoint)

These fields are operational deployment bindings. The same capability can be `ai_mediated`
in dev and `compiled` in prod. The domain model must not encode deployment concerns.

Decision

1. `Capability` domain model retains only intrinsic properties:
   - `id`, `name`, `description`
   - `capability_kind` (tool | skill)
   - `interface` (inputs, outputs, errors)
   - `owns_durable_state` (structural property)
   - `standing_contract` (governance property)

2. `execution_mode`, `transport`, `ai_spec`, `compiled_ref` move to `CapabilityDeployment`.

3. `CapabilityDeployment` is keyed by `(capability_id, environment)`:
   - `capability_id: str`
   - `environment: str`
   - `execution_mode: ExecutionMode`
   - `transport: Transport`
   - `ai_spec: AiSpec | None`
   - `compiled_ref: CompiledRef | None`

4. `PatternRuntime` resolves the deployment for the current environment and reads execution
   metadata from there, not from the `Capability` domain record.

5. People/Capability may define the shape of deployment records; Operations owns runtime
   dispatch logic.

Rationale

1. Domain stability — `Capability` records survive recompilations and transport changes.
2. Multi-environment support — the same capability can have different deployments.
3. Clean runtime dispatch — `PatternRuntime` resolves deployment for the environment.
4. Preserves four-plane separation — execution metadata belongs to the operational layer.

Consequences

- `Capability` model is simplified and stabilised.
- `CapabilityRegistry` methods that touch execution metadata must use `CapabilityDeployment`.
- `PatternRuntime.invoke_step()` must resolve deployment before dispatching.
- Migration adapter `register_from_skill_record()` must create both `Capability` and
  `CapabilityDeployment` records.

Related

- ADR-013: Capability-Oriented Repository Structure
- ADR-020: Capability Ownership by People/Capability
- ADR-026: People/Capability as Peer Domain Plane
- ADR-041: People/Capability Plane Package Structure
