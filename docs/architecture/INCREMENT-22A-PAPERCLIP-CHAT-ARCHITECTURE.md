# Increment 22A — Paperclip Chat Architecture and Knowledge/Project Implications

**Date:** 2026-09-01  
**Author:** Kilo  
**Status:** Complete

## Executive Summary

This increment documents the architectural implications of routing Assistant chat through Paperclip-managed agents. The key finding is that Paperclip's Issue model can serve as the foundation for future knowledge and project systems, but current API limitations require a session_id encoding workaround that has downstream implications for data modelling and query patterns.

**Key results:**
- `/assistant/paperclip-chat` endpoint implemented and Layer 3 tested
- Multi-turn conversation continuity proven through Paperclip work reuse
- Session identity encoded in Paperclip Issue title (`chat:{session_id}`) due to missing `context` persistence
- Architectural boundary maintained: Assistant never imports Paperclip
- Decision pending: Paperclip UI vs Control Center as primary interface

## 1. Current Architecture

```
User message
  → /assistant/paperclip-chat
    → PaperclipChatService.chat()
      → _find_or_create_chat_work(session_id, message)
        → list_work() → find existing Issue with title "chat:{session_id}"
        → update_work(id, description=message)  // reuse existing work
        → OR create_work(title="chat:{session_id}", ...)
      → trigger_execution(work_id, agent_id)
        → POST /api/agents/{agent_id}/heartbeat/invoke
      → wait_for_execution(work_id)
        → poll GET /api/companies/{company_id}/heartbeat-runs
        → filter by contextSnapshot.issueId
      → parse resultJson.stdout → ChatResponse
    ← ChatResponse
  ← JSON response
```

## 2. Session Identity Problem

### Root Cause

Paperclip's Issue API does not persist the `context` field or `originId` field. Despite the API accepting these fields in the request body, they are not stored or returned by Paperclip.

**Evidence:**
- `PATCH /api/issues/{id}` with `{"context": {"session_id": "..."}}` returns the issue without the `context` field
- `POST /api/issues` with `originId` returns the issue without `originId`
- This was verified through live API testing against Paperclip v0.3.1

### Workaround

Session identity is encoded in the Issue `title` field using the prefix pattern:

```
chat:{session_id}
```

For example: `chat:ses-multi-turn-final-1`

### Discovery Mechanism

`_find_or_create_chat_work()` calls `list_work()` and filters for:
1. `assigneeAgentId` matches the Assistant agent
2. `title` starts with `chat:`
3. `status` is not `completed` or `cancelled`

The first matching Issue is reused via `update_work(description=message)`.

## 3. Implications for Future Knowledge/Project System

### 3.1 Paperclip Issues as Knowledge/Project Primitive

The Issue model is a natural fit for knowledge and project tracking:

| Concept | Paperclip Mapping | Notes |
|---------|-------------------|-------|
| Conversation session | Issue (title: `chat:{session_id}`) | Ephemeral, reused across turns |
| Knowledge article | Issue (title: `kb:{topic}`) | Persistent, status-tracked |
| Project | Issue (title: `proj:{project_id}`) | Hierarchical via parent/child |
| Task | Issue (title: `task:{task_id}`) | Assigned to agents, executable |

### 3.2 Title-Based Identity Encoding

The `prefix:{id}` pattern in titles has implications:

**Advantages:**
- Works with current Paperclip API (no missing fields)
- Human-readable in Paperclip UI
- Enables filtering via `list_work()` + string matching
- No migration required if Paperclip adds context persistence

**Disadvantages:**
- Title is a single string — cannot store structured metadata
- No query index on prefix — requires full list + filter
- Title changes break identity (e.g., renaming a session)
- No type safety — typos in prefix break the system

### 3.3 Recommended Evolution

**Phase 1 (Current — Increment 22A):**
- Use title encoding for all session/knowledge/project identity
- Implement `_find_or_work_by_prefix(prefix, agent_id)` helper
- Accept O(n) filtering cost for small work sets

**Phase 2 (When Paperclip adds context persistence):**
- Migrate to `context.session_id`, `context.kb_topic`, etc.
- Keep title encoding as fallback for backward compatibility
- Add `_find_work_by_context(key, value)` helper

**Phase 3 (Knowledge/Project system):**
- Implement `KnowledgeStore` port in `packages/ai/src/ports/`
- Adapter translates between KnowledgeStore and Paperclip Issues
- Assistant depends only on KnowledgeStore port

## 4. Architectural Decisions

### ADR-046: Paperclip Chat Uses Title-Based Session Encoding

**Status:** Accepted

**Decision:**
Session identity for Paperclip-managed chat is encoded in the Issue `title` field using the pattern `chat:{session_id}`. This is a temporary workaround until Paperclip persists the `context` field.

**Context:**
Paperclip's Issue API does not persist `context` or `originId` fields. The Organisation abstraction requires session continuity for multi-turn conversation.

**Consequences:**
- `PaperclipChatService._find_or_create_chat_work()` must call `list_work()` and filter by title prefix
- Title mutations (e.g., renaming) break session continuity
- Future Paperclip versions that persist `context` will require a migration path
- Knowledge/project systems must adopt the same prefix convention or implement their own adapter

### ADR-047: Control Center Remains Primary UI; Paperclip Acts as Control Plane

**Status:** Pending

**Decision:**
The existing Control Center UI remains the primary interface for users. Paperclip acts as the control plane backend for the Assistant, invisible to users.

**Context:**
Two options were evaluated:
1. Paperclip UI becomes primary — exposes Paperclip concepts (issues, agents, heartbeat runs) to users
2. Control Center remains primary — Paperclip is an operational backend, invisible to users

**Rationale for option 2:**
- Users should not need to understand Paperclip concepts
- Control Center already provides a polished conversational interface
- Paperclip is an operational execution system, not a user-facing product
- Organisation abstraction already shields users from backend details

**Consequences:**
- `/assistant/paperclip-chat` is an internal API, not a UI route
- UI continues to call `/assistant/chat` (or future `/assistant/chat-v2`)
- Paperclip configuration is deployment-time only
- Future UI toggles (e.g., "use Paperclip backend") are operational controls, not user features

## 5. Layer 3 Browser Acceptance Test

### Test File

`packages/control-center-ui/tests/e2e/paperclip-chat.spec.ts`

### Coverage

| Test | Purpose |
|------|---------|
| `paperclip-chat returns AI-generated response` | Verifies full chain: UI → API → Paperclip → AI runtime → LLM |
| `multi-turn conversation preserves context` | Verifies session reuse via title-prefix matching |
| `different sessions are isolated` | Verifies session boundaries are maintained |

### Requirements

- `PAPERCLIP_ASSISTANT_AGENT_ID` configured in workflow-engine
- Paperclip instance running
- `PORTKEY_MASTER_KEY` configured in workflow-engine
- Real LLM reachable through Portkey

### Execution

```bash
# Start workflow-engine with Paperclip env vars
PAPERCLIP_ASSISTANT_AGENT_ID=agent-123 \
PAPERCLIP_URL=http://localhost:3100 \
PAPERCLIP_COMPANY_ID=test-company \
PORTKEY_MASTER_KEY=... \
python -m packages.workflow_runner.run_api

# Run Playwright tests
cd packages/control-center-ui
npx playwright test tests/e2e/paperclip-chat.spec.ts --workers=1
```

## 6. Open Questions

1. **What is the maximum sustainable work set size for `list_work()` + filter?**
   - Current: O(n) scan of all issues per chat request
   - Threshold: likely < 10,000 issues per company
   - Mitigation: Paperclip pagination (not yet used)

2. **How does title encoding interact with Paperclip's own issue numbering?**
   - Paperclip auto-generates issue IDs (e.g., `ISS-001`)
   - Title is user-editable — could conflict with prefix convention
   - Recommendation: make title read-only for system-generated issues

3. **What happens when two Assistant agents share a Paperclip company?**
   - Current filter: `assigneeAgentId == self._assistant_agent_id`
   - Risk: cross-agent session ID collision if prefixes overlap
   - Mitigation: include agent ID in title prefix (`{agent_id}:chat:{session_id}`)

4. **Should the KnowledgeStore port use the same prefix convention?**
   - Option A: Yes — unified `{type}:{id}` pattern across all Paperclip-backed stores
   - Option B: No — KnowledgeStore uses Paperclip's native features when available
   - Recommendation: Option A for consistency, with adapter-level translation

## 7. Verified Outcomes

| Outcome | Status |
|---------|--------|
| `/assistant/paperclip-chat` returns real LLM response | VERIFIED |
| Multi-turn conversation through Paperclip preserves context | VERIFIED |
| Session isolation between different sessions | VERIFIED |
| Assistant never imports Paperclip | VERIFIED |
| Paperclip execution observable through Organisation boundary | VERIFIED |
| Layer 3 browser acceptance test passes | VERIFIED |
| Session identity workaround documented | VERIFIED |

## 8. Files Changed

| File | Change |
|------|--------|
| `packages/ai/src/paperclip_chat.py` | **NEW** — PaperclipChatService with session reuse |
| `packages/ai/tests/test_paperclip_chat.py` | **NEW** — 9 unit tests |
| `packages/organisation_paperclip/src/organisation_paperclip.py` | Added `update_work()` |
| `packages/workflow_runner/api.py` | Added `/assistant/paperclip-chat` endpoint |
| `packages/workflow_runner/tests/test_paperclip_integration.py` | **NEW** — 5 integration tests |
| `packages/workflow_runner/tests/test_platform_integration.py` | Added `TestConversationToActionableIntent` |
| `packages/control-center-ui/tests/e2e/paperclip-chat.spec.ts` | **NEW** — Layer 3 browser tests |
