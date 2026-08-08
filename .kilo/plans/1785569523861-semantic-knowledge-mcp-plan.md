# Plan: Semantic Knowledge / RAG MCP Capability for Kilo (Revised)

## Objective

Enable Kilo Code to selectively retrieve relevant architectural and implementation knowledge from the aiassistant Markdown corpus via semantic search over Qdrant, delivered through an MCP server. The authoritative documents remain the source of truth; RAG is a discovery/context mechanism only.

---

## A. Architectural Corrections

1. **Capability name**: The platform capability is `knowledge-mcp`. The upstream project `ragpilot` is an implementation detail and must not leak into platform naming. All contracts, configuration, and binary names use `knowledge-mcp` or `knowledge`.

2. **Configuration contract**: The platform must use `contracts/knowledge/v1/` for knowledge-mcp behavioral configuration. There is no `contracts/ragpilot/v1/`. The existing ragpilot project remains independent and unchanged.

3. **Separation of concerns**: knowledge-mcp is a knowledge-domain capability. It must not retain code-intelligence concepts (symbols, AST parsing, call graphs, impact analysis, semantic code diff, source-code skeletons).

4. **Configuration Manager coupling**: For v1, knowledge-mcp follows the existing platform convention and instantiates `DotEnvProvider()` directly. This is documented as an architectural gap but not solved in v1.

---

## B. Revised Capability / File Naming

| Old Name | New Name | Scope |
|----------|----------|-------|
| `ragpilot/v1/contract.yaml` | `knowledge/v1/contract.yaml` | Platform contract |
| `RagpilotConfiguration` | `KnowledgeConfiguration` | Python model |
| `packages/ragpilot/` | `packages/knowledge-mcp/` | Implementation |
| `RAGPILOT_*` env vars | `KNOWLEDGE_*` env vars | Configuration |
| `ragpilot` binary | `knowledge-mcp` binary | Executable |
| `.rag/` directory | `.knowledge/` directory | Local state |
| `platform_knowledge` collection | `platform_knowledge` (unchanged) | Qdrant collection |

**Note:** The upstream `ragpilot` project is untouched. The fork lives entirely in `packages/knowledge-mcp/`.

---

## C. Revised Phased Implementation Plan

### Phase 1: Configuration + Minimal Skeleton

**Goal:** Establish the configuration contracts and create a minimal knowledge-mcp binary that can start, resolve configuration, and expose an empty MCP server.

**Files changed:**
- Create `contracts/knowledge/v1/contract.yaml`
- Create `contracts/knowledge/v1/mapping.yaml`
- Create `packages/configuration/src/configuration/contracts/v1/knowledge.py`
- Create `packages/knowledge-mcp/Cargo.toml`
- Create `packages/knowledge-mcp/src/main.rs`
- Create `packages/knowledge-mcp/src/lib.rs`
- Create `packages/knowledge-mcp/src/mcp/mod.rs` (minimal stdio loop)
- Create `packages/knowledge-mcp/src/mcp/protocol.rs` (copied from ragpilot)
- Create `packages/knowledge-mcp/src/mcp/tools/mod.rs` (empty tool list)

**Tests:**
- Contract tests: `knowledge` contract loads and validates
- Contract tests: `KnowledgeConfiguration` resolves from `.env` via `ConfigurationManager`
- Rust: MCP server starts, responds to `initialize` and `tools/list` with empty tool list

**Acceptance criteria:**
- `knowledge-mcp --mcp-server` starts without error
- `initialize` returns protocol version and empty capabilities
- `tools/list` returns empty tools array
- Configuration Manager resolves `KnowledgeConfiguration` and `QdrantConfiguration` successfully

**Dependencies:** None. This phase is self-contained.

---

### Phase 2: Markdown Parser + Heading-Aware Chunking

**Goal:** Implement the Markdown ingestion pipeline: parse, chunk, and produce `KnowledgeChunk` structs with heading breadcrumbs and provenance.

**Files changed:**
- Create `packages/knowledge-mcp/src/parser/markdown_parser.rs`
- Create `packages/knowledge-mcp/src/parser/mod.rs`
- Create `packages/knowledge-mcp/src/store/mod.rs` (`KnowledgeChunk` struct)
- Create `packages/knowledge-mcp/src/indexer.rs` (scanning + chunking)
- Create `packages/knowledge-mcp/src/orchestrator.rs` (index orchestration)

**Tests:**
- `markdown_parser::test_extract_headings` — ATX heading extraction with line numbers
- `markdown_parser::test_build_breadcrumb` — heading breadcrumb construction
- `markdown_parser::test_split_sections` — document split by heading
- `markdown_parser::test_extract_frontmatter` — YAML frontmatter extraction
- `markdown_parser::test_extract_references` — Markdown link extraction
- `markdown_parser::test_no_headings` — document without headings
- `markdown_parser::test_nested_headings` — 3+ level heading hierarchy
- `chunking::test_section_single_chunk` — short section as one chunk
- `chunking::test_section_multiple_chunks` — long section splits at paragraphs
- `chunking::test_breadcrumb_prepended` — breadcrumb in chunk content
- `chunking::test_overlap` — consecutive chunks have correct overlap
- `payload::test_chunk_serialization` — Qdrant payload includes all fields
- `payload::test_references_extraction` — Markdown links populate `references`

**Acceptance criteria:**
- Given a Markdown file with headings, the parser produces chunks with correct `section_heading` breadcrumbs
- Given a Markdown file without headings, the parser produces a single chunk with `section_heading = None`
- Given a Markdown file with frontmatter, the parser extracts `document_metadata`
- Given a Markdown file with links, the parser extracts `references`
- Chunk overlap is correct between consecutive chunks

**Dependencies:** Phase 1 (configuration contracts).

---

### Phase 3: Qdrant Indexing + Semantic Search

**Goal:** Embed chunks, store them in Qdrant, and retrieve them via semantic search.

**Files changed:**
- Create `packages/knowledge-mcp/src/embedder/mod.rs` (copied from ragpilot)
- Create `packages/knowledge-mcp/src/embedder/local.rs` (copied from ragpilot)
- Create `packages/knowledge-mcp/src/store/qdrant.rs` (copied from ragpilot, extended payload)
- Update `packages/knowledge-mcp/src/orchestrator.rs` (add embedding + Qdrant upsert)
- Create `packages/knowledge-mcp/src/mcp/tools/rag.rs` (adapted from ragpilot)

**Tests:**
- `test_index_corpus` — index 3-5 Markdown files, verify chunks in Qdrant
- `test_semantic_search` — query returns expected chunks for known queries
- `test_filter_by_knowledge_type` — `knowledge_type` filter restricts results
- `test_filter_by_document_path` — `document_path` filter restricts results
- `test_incremental_update` — modify a file, re-index, verify only changed file updated
- `test_deleted_file` — delete a file, re-index, verify chunks removed
- `test_provenance` — retrieved chunks contain correct `source`, `start_line`, `end_line`, `section_heading`
- `test_heading_breadcrumbs` — chunks from nested headings have correct breadcrumb trails
- `test_frontmatter_metadata` — document metadata extracted and stored in payload
- `test_staleness_warning` — search includes `index_may_be_stale` when dirty files exist

**Acceptance criteria:**
- `knowledge-mcp init` indexes a corpus of 3-5 Markdown files into Qdrant
- `knowledge_search(query="configuration management")` returns relevant chunks with correct provenance
- Filtering by `knowledge_type` and `document_path` works correctly
- Incremental re-index only touches changed files
- Deleted files are removed from Qdrant

**Dependencies:** Phase 2 (Markdown parsing + chunking).

---

### Phase 4: MCP Integration + Kilo Consumption

**Goal:** Expose `knowledge_search` as an MCP tool and verify Kilo can consume it.

**Files changed:**
- Update `packages/knowledge-mcp/src/mcp/tools/rag.rs` (rename/extend to `knowledge_search`)
- Update `packages/knowledge-mcp/src/mcp/tools/mod.rs` (register `knowledge_search`)
- Create `packages/knowledge-mcp/src/agents.rs` (Kilo MCP registration)

**Tests:**
- `test_mcp_knowledge_search` — MCP `tools/call` for `knowledge_search` returns valid JSON
- `test_mcp_tools_list` — `tools/list` includes `knowledge_search`
- `test_mcp_initialize` — handshake succeeds
- `test_kilo_registration` — Kilo config snippet is correct

**Acceptance criteria:**
- `knowledge-mcp --mcp-server` responds to `tools/list` with `knowledge_search`
- `knowledge_search` returns chunks with `source`, `section_heading`, `start_line`, `end_line`, `score`, `snippet`
- Kilo can register and call `knowledge_search` via stdio JSON-RPC
- Search results include `index_may_be_stale` flag when appropriate

**Dependencies:** Phase 3 (Qdrant indexing + search).

---

### Phase 5: Retrieval Evaluation and Tuning

**Goal:** Evaluate retrieval quality against real architecture documents and tune chunking/embedding parameters.

**Tests:**
- `evaluation::test_query_set` — 20-30 queries from actual corpus, graded for Precision@3 and MRR
- `evaluation::test_section_hit_rate` — correct section retrieved, not just document
- `evaluation::test_chunking_ablation` — heading-aware vs naive chunking

**Acceptance criteria:**
- Precision@3 ≥ 0.6 on the evaluation query set
- Section hit rate ≥ 0.5 (correct section appears in top-5)
- Heading-aware chunking outperforms naive character chunking on the same corpus
- Retrieval quality is sufficient for Kilo to find relevant architecture knowledge

**Dependencies:** Phase 4 (MCP integration).

---

### Phase 6: Secondary Capabilities

**Goal:** Add document/section retrieval, incremental indexing, watcher, and relationship metadata.

**Tools added:**
- `knowledge_get_document` — list all chunks for a document
- `knowledge_get_section` — retrieve chunks for a specific heading
- `knowledge_list_documents` — list indexed documents with metadata

**Features added:**
- File watcher (optional)
- Incremental re-indexing via `knowledge_ensure_index`
- Markdown `references` extraction and storage
- Document-level metadata in `knowledge_list_documents`

**Acceptance criteria:**
- `knowledge_get_document` returns all sections for a known document
- `knowledge_get_section` returns chunks for a specific heading
- `knowledge_list_documents` returns all indexed documents with metadata
- File watcher detects changes and triggers re-index
- `knowledge_ensure_index` performs incremental re-index

**Dependencies:** Phase 4 (MCP integration).

---

## D. First Vertical Slice Acceptance Criteria

The first vertical slice (Phases 1-4) is complete when:

1. **End-to-end path works:** Kilo can ask `knowledge_search("How does the platform handle configuration?")` and receive relevant architectural knowledge from `agentic/docs/` with correct provenance.

2. **Provenance is preserved:** Every result includes `source` (file path), `start_line`, `end_line`, and `section_heading`.

3. **Heading-aware chunking works:** Chunks respect Markdown heading boundaries and include breadcrumb context.

4. **Qdrant integration works:** Chunks are embedded with BGE-small-en-v1.5 and stored in the `platform_knowledge` collection.

5. **Configuration Manager integration works:** knowledge-mcp resolves Qdrant URL and API key via the Configuration Manager contracts, not via direct `.env` reads.

6. **MCP interface is correct:** `knowledge_search` accepts `query`, `knowledge_type`, `document_path`, and `k` parameters and returns structured results.

7. **Staleness is signaled:** When the index is stale, search results include a warning.

8. **No code-intelligence concepts remain:** The binary contains no symbol graph, call graph, impact analysis, or AST parsing code.

---

## E. Remaining Decisions Requiring Human Input

1. **Corpus root scope:** Is `agentic/docs/` the complete corpus for v1, or should `docs/`, `README.md`, and other top-level Markdown files be included? This affects the initial index and `knowledge_list_documents` results.

2. **Embedding model:** BGE-small-en-v1.5 (dim=384) is the default candidate. Should we evaluate BGE-base (dim=768) during Phase 5 if retrieval quality is insufficient?

3. **Chunk size tuning:** Is 500 characters / 120 overlap a reasonable starting point, or should we measure actual document lengths and tune before Phase 3?

4. **Staleness policy for v1:** Should `knowledge_search` always allow stale results with a warning, or should there be a `require_fresh` parameter that blocks when dirty files exist?

5. **Collection name:** `platform_knowledge` is proposed. Is this acceptable, or does the platform have a naming convention that should be followed?

6. **Configuration scope:** The `knowledge` contract currently includes behavioral configuration (chunk size, overlap, watcher, etc.). Should these be platform-wide defaults in the contract, or should knowledge-mcp use sensible hardcoded defaults and only use the Configuration Manager for Qdrant credentials?

---

## Implementation Files Summary

### Phase 1: Configuration + Skeleton
- `contracts/knowledge/v1/contract.yaml` — Create
- `contracts/knowledge/v1/mapping.yaml` — Create
- `packages/configuration/src/configuration/contracts/v1/knowledge.py` — Create
- `packages/knowledge-mcp/Cargo.toml` — Create
- `packages/knowledge-mcp/src/main.rs` — Create
- `packages/knowledge-mcp/src/lib.rs` — Create
- `packages/knowledge-mcp/src/mcp/mod.rs` — Create
- `packages/knowledge-mcp/src/mcp/protocol.rs` — Create
- `packages/knowledge-mcp/src/mcp/tools/mod.rs` — Create

### Phase 2: Markdown Parser + Chunking
- `packages/knowledge-mcp/src/parser/markdown_parser.rs` — Create
- `packages/knowledge-mcp/src/parser/mod.rs` — Create
- `packages/knowledge-mcp/src/store/mod.rs` — Create
- `packages/knowledge-mcp/src/indexer.rs` — Create
- `packages/knowledge-mcp/src/orchestrator.rs` — Create

### Phase 3: Qdrant + Search
- `packages/knowledge-mcp/src/embedder/mod.rs` — Create
- `packages/knowledge-mcp/src/embedder/local.rs` — Create
- `packages/knowledge-mcp/src/store/qdrant.rs` — Create
- `packages/knowledge-mcp/src/mcp/tools/rag.rs` — Create

### Phase 4: MCP Integration
- `packages/knowledge-mcp/src/mcp/tools/mod.rs` — Modify
- `packages/knowledge-mcp/src/agents.rs` — Create

### Phase 6: Secondary Capabilities
- `packages/knowledge-mcp/src/mcp/tools/knowledge.rs` — Create (document/section/list tools)

### Not Created (ragpilot code removed from fork)
- `src/parser/regex_parser.rs`
- `src/parser/tree_sitter_parser.rs`
- `src/store/symbol_graph.rs`
- `src/store/project_tree.rs`
- `src/store/impact_index.rs`
- `src/store/sqlite.rs`
- `src/skeleton.rs`
- `src/semantic_diff.rs`
- `src/config.rs`

---

## Risks and Known Limitations (unchanged from prior plan)

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Small corpus noise** | Medium | Use metadata filters. Accept as inherent to corpus size. |
| **Prose embedding quality** | Medium | Evaluate in Phase 5. Upgrade to BGE-base if needed. |
| **Heading detection failures** | Low | Use `pulldown-cmark` if regex proves insufficient. |
| **Knowledge type misclassification** | Low | Keep optional. Don't filter strictly unless requested. |
| **Chunk context loss** | Medium | Increase overlap. Consider larger chunks for dense ADRs. |
| **Staleness** | Medium | Watcher for dev; deployment re-index for prod. Warning in results. |
| **Fork maintenance** | Low | Document fork. Re-evaluate sharing for v2. |
| **Configuration Manager coupling** | Medium | Document as architectural gap. Fix via provider factory in future. |
| **No conflict detection** | Low | Reviewer/agent resolves using provenance metadata. |
| **Embedding model lock-in** | Medium | Document. Pin model version in configuration. |
