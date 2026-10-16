## Rintime Interface

This is the important abstraction.

# Runtime Interface

Every AI Runtime must implement:

start()

stop()

send()

add()

drop()

run()

For Aider:

send()

↓

terminal.sendText()
add()

↓

terminal.sendText("/add ...")

etc.

That's all this document says.

---

## Cognition Alignment

Canonical model: `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. This `Runtime Interface` is the contract for one **Pattern Runtime** adapter (the Aider-backed `workflow-runner`); see anchor doc §12 and `RUNTIME-MAPPING.md`. LangGraph is a second adapter implementing the same stable `PathwayRuntime` boundary. The interface executes **pattern steps / Capability calls** selected by Strategy Selection (§6).