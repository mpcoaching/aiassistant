# Test-Layer Contract

## Layer 1 — Unit
**What it proves:**
- Fast, deterministic behaviour of isolated units (routing, history, telemetry, boundaries).
- No external dependencies; mocked AI, mocked ports, mocked infrastructure.

**What it does NOT prove:**
- That HTTP requests reach a real LLM.
- That the API stack wires correctly end-to-end.
- That Docker/Podman services start or communicate.

**Canonical command:**
```bash
cd packages/ai && python -m pytest tests/test_assistant.py tests/test_architectural_boundaries.py -v
```

---

## Layer 2 — Application Integration
**What it proves:**
- Real FastAPI app, real `AssistantChatService`, real context formation, real validation/execution loops.
- Infrastructure dependencies (EventBus, Scheduler, Database) are mocked at the adapter boundary.
- Conversational routing, session-scoped history, telemetry propagation, and specialised deterministic paths (planning, analysis, capability) are exercised with real application code.

**What it does NOT prove:**
- That a real LLM generates the response (AI is mocked).
- That Portkey or any external gateway is reachable.
- That the browser → API → AI → LLM → browser path works in a running platform.

**Canonical command:**
```bash
cd packages/workflow_runner && python -m pytest tests/test_platform_integration.py -v -k "not CanonicalRealAISmoke"
```

---

## Layer 2b — Real AI Integration
**What it proves:**
- Actual HTTP path: `AIResponseService` → Portkey → configured LLM → response.
- `ai_invoked=True`, `ai_success=True`, `ai_model` populated, `ai_latency_ms` populated.
- Conversation history reaches the real LLM and affects subsequent responses.
- Separate sessions do not leak context.
- Different prompts produce materially different responses.

**What it does NOT prove:**
- That the browser can reach the API (uses direct Python HTTP client).
- That the full Docker/Podman platform stack is healthy.
- That Playwright E2E flows work.

**Opt-in required:**
```bash
REAL_AI_TESTS=1 pytest packages/ai/tests/test_ai_integration.py -v
```

**Skip conditions:**
- `REAL_AI_TESTS != 1` → skipped with clear reason.
- `PORTKEY_MASTER_KEY` missing → skipped with clear reason.
- Portkey unreachable → fails with connection error (not silently skipped).

---

## Layer 3 — Platform E2E
**What it proves:**
- Browser → control-center-ui → workflow-engine/FastAPI → AssistantChatService → AIResponseService → Portkey → LLM → response → browser.
- UI provenance (`data-runtime="ai_response_service"` on assistant bubbles).
- Session ID reuse across turns in the browser.
- Conversation continuity visible to the user.

**What it does NOT prove:**
- Anything when `VITE_API_TARGET` is `localhost` (tests are skipped).
- Unit-level routing logic (use Layer 1 for that).
- Application-level context formation without the UI (use Layer 2 for that).

**Canonical command:**
```bash
VITE_API_TARGET=http://dev-platform-gateway:4000 npx playwright test packages/control-center-ui/tests/e2e/assistant-conversation.spec.ts
```

---

## Failure-Behaviour Layer
**What it proves:**
- AI timeout/connection failure is observable in telemetry.
- The application does not crash on AI failure.
- Conversation history is not poisoned by failed requests.
- Subsequent requests can recover after an AI failure.

**What it does NOT prove:**
- That a real LLM failure mode is handled correctly (uses simulated exceptions).
- That Portkey's retry/fallback logic works (tests the app's catch block).

---

## Specialised-Path Isolation Layer
**What it proves:**
- Planning requests → deterministic planning path, NOT AI.
- Analysis requests → deterministic analysis path, NOT AI.
- Capability execution → deterministic capability/work path, NOT AI.
- Generic conversational requests → AI path, NOT deterministic patterns.

**Architectural rule:**
**Generic conversation is AI-driven; specialised actionable intents retain their specialised execution paths.**

---

## CI Integration
**How to enable real-AI tests in CI:**
1. Store `PORTKEY_MASTER_KEY`, `PORTKEY_BASE_URL`, and `AI_MODEL` as CI secrets.
2. Run the Layer 2b suite with `REAL_AI_TESTS=1` in a dedicated job.
3. Do NOT run real-AI tests on every developer PR — they are opt-in and may incur costs.

**Suggested CI job:**
```yaml
jobs:
  real-ai-integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run real AI tests
        env:
          REAL_AI_TESTS: 1
          PORTKEY_MASTER_KEY: ${{ secrets.PORTKEY_MASTER_KEY }}
          PORTKEY_BASE_URL: ${{ secrets.PORTKEY_BASE_URL }}
          AI_MODEL: ${{ secrets.AI_MODEL }}
        run: |
          cd packages/ai && python -m pytest tests/test_ai_integration.py -v
```
