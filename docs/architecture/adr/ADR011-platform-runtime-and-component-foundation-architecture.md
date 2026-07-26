ADR-XXX: Platform Runtime and Component Foundation Architecture
Status

Proposed

Decision

Platform components will be built on a shared runtime foundation that provides common platform capabilities.

Components will implement business or domain capabilities through defined contracts, while inheriting common operational behaviour from the platform runtime.

The runtime provides consistency without coupling components to specific infrastructure implementations.

Context

The platform will contain many independent capabilities:

workflow execution
AI agents
CI workers
model providers
configuration services
registries
orchestration components

Without a shared foundation, each component will independently solve:

configuration loading
logging
telemetry
health checks
lifecycle management
event publishing
service discovery
error reporting

This creates duplicated implementations and inconsistent behaviour.

Decision Principles
1. Capabilities are independent

A component should primarily implement:

"What capability does this provide?"

Example:

WorkflowRunner
AIModelProvider
ConfigurationResolver

It should not reimplement:

Logging
Configuration bootstrap
Health endpoints
Event transport
2. Common platform behaviour belongs in the runtime

The runtime provides:

Platform Runtime

    |
    +-- Configuration Client
    |
    +-- Event Bus Client
    |
    +-- Logging
    |
    +-- Metrics
    |
    +-- Health Checks
    |
    +-- Lifecycle Management
    |
    +-- Version Reporting
3. Runtime is composition, not inheritance everywhere

The platform should avoid deep inheritance hierarchies.

Preferred:

class WorkflowRunner:

    def __init__(
        self,
        runtime: PlatformRuntime
    ):
        self.runtime = runtime

rather than:

class EnterpriseWorkflowRunner(
    AdvancedPlatformComponent
):

The runtime provides services.

The component uses them.

Relationship Between Patterns

This ADR depends on:

PAT-001 Contract First Design

Components expose explicit contracts.

PAT-002 Provider Pattern

Implementations remain replaceable.

PAT-003 Factory Pattern

Implementations are selected through resolution.

PAT-008 Platform Runtime Pattern

Components execute within a standard environment.

Architecture Model
                  Component

                     |
                     |

             Capability Contract

                     |
                     |

            Platform Runtime

                     |
     +---------------+---------------+
     |               |               |

Configuration    Events        Observability


                     |

              Infrastructure

                     |
     +---------------+---------------+
     |               |               |

 Docker          Kubernetes       Local
Docker Relationship

Docker images are packaging mechanisms.

They are not the architecture.

Example:

FROM aiassistant-platform-runtime

COPY workflow-runner /

ENTRYPOINT ["workflow-runner"]

The image inherits:

runtime
libraries
operational behaviour

The component adds:

capability implementation
Testing Requirements

Every platform component must provide:

Contract tests

Does the capability behave correctly?

Runtime compatibility tests

Does it run correctly inside the platform runtime?

Provider substitution tests

Can implementations be swapped?

Example:

Production:

PortkeyModelProvider


Test:

MockModelProvider
Migration Strategy

Existing components migrate gradually.

Not:

Rewrite everything around the runtime.

Instead:

Create runtime package.
Add capability contracts.
Migrate components when touched.
Remove duplicated infrastructure code.
Consequences
Benefits
Faster component creation.
Consistent behaviour.
Easier automation.
Easier Kubernetes adoption later.
Less duplicated infrastructure code.
Costs
Runtime becomes a critical dependency.
Poor runtime design could create coupling.
Requires discipline around boundaries.

I would actually now see the architecture documentation tree becoming:

docs/architecture/

    principles/
        platform-principles.md

    decisions/
        ADR-001-provider-based-architecture.md
        ADR-002-platform-runtime.md
        ADR-003-event-driven-integration.md
        ADR-004-configuration-resolution.md

    patterns/
        PAT-001-contract-first.md
        PAT-002-provider.md
        PAT-003-factory.md
        PAT-004-capability-resolution.md
        PAT-005-adapter.md
        PAT-006-provider-chain.md
        PAT-007-event-publication.md
        PAT-008-platform-runtime.md

    capabilities/
        configuration-manager.md
        model-registry.md
        service-registry.md