# Project Restructure Plan

## Current state
- Code is duplicated across `agents/` and `agentic/src/`
- Test paths are hardcoded in `delivery/commands/test.py` (`agents/*/tests`)
- No clear convention for separating code from tests across Python and TypeScript
- `workflow-runner` Python code lives under `agentic/src/` but tests import `from models import ...` (relative to their own dir)
- `control-center-ui` exists in both `agents/` and `agentic/src/` with unclear contents

## Desired state
- Single source of truth under `agentic/src/`
- Convention-based test discovery: any directory named `tests` or `__tests__` is treated as a test root
- Python packages are standard `pyproject.toml`-based
- TypeScript/React UI is a standard Vite/React app under `control-center-ui/`
- `delivery/commands/test.py` discovers tests automatically instead of hardcoding paths

## Proposed structure

```
agentic/
  src/
    workflow-runner/
      pyproject.toml
      models.py
      chain.py
      compiler.py
      composer.py
      handlers.py
      loader.py
      registry.py
      skill_runtime.py
      state.py
      tests/
        __init__.py
        test_models.py
        test_chain.py
        ...
      README.md

    langgraph/
      pyproject.toml
      graph.py
      state.py
      ...
      tests/
        __init__.py
        test_graph.py
        ...

    control-center-ui/
      package.json
      tsconfig.json
      vite.config.ts
      src/
        main.tsx
        App.tsx
        components/
        pages/
      tests/
        unit/
          api.test.ts
        e2e/
          ...
      README.md
```

## Rules
1. **Code detection**: any file matching `*.py` outside a `tests`/`__tests__` directory is application code
2. **Test detection**: any directory named `tests` or `__tests__` is a test root; `pytest` for Python, `vitest` for TypeScript
3. **One `pyproject.toml` per Python package** under `agentic/src/<package>/`
4. **No duplication**: `agents/` becomes a symlink or is removed entirely; `agentic/src/` is the only source
5. **Build commands**: `delivery build workflow-runner` builds the Python package; `delivery build control-center-ui` builds the TypeScript app
6. **Test commands**: `delivery test unit` runs all `pytest` and `vitest` suites; `delivery test integration` runs integration tests

## Changes needed
1. Reorganize directories under `agentic/src/`
2. Remove or symlink `agents/`
3. Update `delivery/commands/test.py` to discover tests by convention
4. Update `.gitea/workflows/main.yml` to run both Python and TypeScript tests
5. Update `docs/target-state.md` to reflect new structure

## Migration steps
1. Move `agentic/src/workflow-runner/tests/` files to current location (already correct)
2. Move `agentic/src/control-center-ui/` TypeScript files into `agentic/src/control-center-ui/src/`
3. Create `pyproject.toml` for `workflow-runner` and `langgraph`
4. Create `package.json`/`tsconfig.json`/`vite.config.ts` for `control-center-ui`
5. Delete `agents/` or replace with symlinks
6. Update `delivery/commands/test.py`
7. Update workflows
8. Push and verify
