PAT-010: Event-Driven Capability Communication

This one is important.

But I would refine the wording slightly.

I would not say:

synchronous code is not what we're aiming for

because synchronous code will always exist.

A better architectural decision:

Components communicate asynchronously where the interaction represents a business capability, state change, or workflow.

Intent

Separate components through events rather than direct invocation.

Problem

Direct calls create chains:

A
 |
 +--> B
       |
       +--> C
             |
             +--> D

Now:

startup order matters
failures cascade
testing becomes harder
Solution

Publish facts.

Example:

Instead of:

ConfigurationManager
      |
      |
Runner
      |
      |
Start

Use:

ConfigurationResolved Event

          |
          |
+---------+----------+
|                    |

Runner             Auditor

Events are statements of fact:

Good:

ConfigurationContractSatisfied

Bad:

StartRunnerNow

The first describes state.

The second creates coupling.