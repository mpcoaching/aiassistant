PAT-016: Capability Plugin Pattern
Intent

Organise platform functionality as independent capabilities that can be registered, discovered, and replaced without affecting consumers.

Structure

Each capability contains:

Capability

    |
    +-- Contracts
    |
    +-- Implementations
    |
    +-- Providers
    |
    +-- Resolver/Factory
    |
    +-- Tests
    |
    +-- Metadata

Example:

configuration-capability

contains:

configuration/
    capability.yaml

    contracts/
        ConfigurationContract

    providers/
        DotEnvProvider
        VaultProvider

    resolver/
        ConfigurationResolver

    runtime/
        ConfigurationManager

The metadata becomes interesting:

capability:
  name: configuration
  version: 1.0

contracts:
  provides:
    - ConfigurationResolution

providers:
  - dotenv
  - vault

events:
  publishes:
    - ConfigurationResolved
    - ConfigurationFailed

Now the system can discover capabilities.

The factory question

You asked:

"Would we really structure as providers, factories and so on, as that adds very little value?"

Excellent question.

The answer is:

The factory should exist only where there is a choice.

Bad:

ConfigurationFactory.create()

that always returns:

DotEnvProvider()

That is ceremony.

Good:

ConfigurationResolver.resolve()

where it may choose:

Environment:

dev

Providers available:

1. Local cache
2. DotEnv
3. Config service

Resolution:

Local cache hit

Now the abstraction earns its keep.

The same applies to inheritance

We shouldn't create:

BaseCapability
    |
    BaseProvider
        |
        BaseDatabaseProvider
            |
            BasePostgresProvider

That is how systems become impossible to change.

Instead:

Capability
    |
    +-- Contract
    |
    +-- Providers
    |
    +-- Runtime Services

Composition.

This also aligns beautifully with your existing agentic architecture

You already have ideas around:

capability registry
agent registry
tool registry
event bus

This turns into:

                Capability Registry

                       |

       +---------------+---------------+

 Configuration     Model Gateway     Workflow Engine

       |                |                 |

 Contracts        Contracts         Contracts

       |

 Providers

       |

 Implementations