PAT-013: Contract Validation Before Execution

This one is probably one of the most important.

Intent

Fail before doing work.

Bad:

Application starts

30 minutes later:

Database password missing

Good:

Startup

↓

Load required contracts

↓

Validate

↓

Either:

READY

or:

CONFIGURATION_FAILED

This maps very nicely to Kubernetes later because Kubernetes already thinks in terms of:

readiness
liveness
startup checks