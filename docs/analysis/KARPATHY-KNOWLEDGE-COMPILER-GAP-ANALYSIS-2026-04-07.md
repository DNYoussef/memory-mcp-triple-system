# Karpathy Knowledge Compiler Gap Analysis

**Date**: 2026-04-07  
**Target**: `D:/Projects/memory-mcp-triple-system`  
**Standard**: critical architecture review, biased toward root cause over surface fixes

---

## Verdict

`memory-mcp-triple-system` is not currently a compiled knowledge base.

It is a retrieval-heavy memory service with several strong side systems:

- lifecycle retention
- vector plus graph retrieval
- session hooks and observation capture
- ontology and graph primitives
- vault sync and file watching
- drift and promotion experiments

Those are useful pieces. They are not the missing center of gravity.

The missing center is a canonical synthesis layer:

- immutable sources
- parsed claims with provenance
- disambiguated entity registry
- compiled wiki pages
- contradiction handling
- promoted questions and decision memos
- knowledge tests

Right now the indices are too close to being treated as truth. That is the core design error.

---

## What The Repo Actually Is Today

The repo mixes at least three architecture stories:

1. `README.md` and `docs/README.md` sell a triple-layer short/mid/long-term memory system.
2. `docs/ARCHITECTURE.md` and `docs/ARCHITECTURE-DECISION.md` define a unified retrieval stack: vector + HippoRAG + Bayesian.
3. `src/stores/kv_store.py` and `src/stores/event_log.py` implement a separate 5-tier polyglot storage story with observations and sessions.

That is already a warning sign. The codebase has components, but not one canonical mental model.

---

## What We Already Have

These are real assets worth keeping:

- Auto-capture hooks already exist:
  - `src/hooks/session_start_handler.py`
  - `src/hooks/post_tool_handler.py`
  - `src/hooks/stop_handler.py`
- Structured observations and sessions already exist in `src/stores/kv_store.py`.
- Temporal event logging already exists in `src/stores/event_log.py`.
- Vault sync and file watching already exist:
  - `src/mcp/vault_sync_service.py`
  - `src/utils/file_watcher.py`
  - `src/services/trigger_watchers/`
- Entity extraction and graph indexing already exist:
  - `src/services/entity_service.py`
  - `src/services/graph_service.py`
  - `src/services/graph_query_engine.py`
- Ontology primitives already exist in `src/integrations/ontology_schema.py`.
- Promotion and drift building blocks already exist:
  - `src/memory/memory_promoter.py`
  - `scripts/promotion_pipeline.py`
  - `src/memory/drift_detector.py`
- Unified routing exists, but at the wrong abstraction layer:
  - `src/routing/query_router.py`
  - `src/routing/unified_router.py`
  - `src/services/unified_search_router.py`

This matters because the redesign should reuse these primitives instead of pretending we are starting from zero.

---

## What Is Missing

### 1. Immutable source layer

`vault_sync_service.py` chunks live markdown and pushes it directly toward embeddings. That is ingestion, not source control.

Missing:

- immutable source snapshots
- source manifests
- durable source ids
- source-level provenance and import logs
- raw-source diffing before recompilation

### 2. Parse and claim layer

The repo extracts entities, but it does not maintain a first-class claim ledger.

Missing:

- atomic claims
- claim ids
- source span provenance
- confidence and freshness at claim level
- normalization status
- novelty vs reinforcement vs conflict classification

### 3. Canonical compiled pages

The system syncs markdown into memory, but it does not compile canonical pages from claims.

Missing:

- canonical topic pages
- comparison pages
- entity pages
- decision memos
- machine-readable page manifests linking every paragraph back to claims

### 4. Conflict layer

`drift_detector.py` detects staleness and embedding movement. That is not the same thing as contradiction management.

Missing:

- contradiction pages
- contested claim groups
- freshness windows
- confidence decay for unsupported claims
- adversarial challenge prompts
- stale synthesis detection

### 5. Question promotion layer

`memory_promoter.py` and `promotion_pipeline.py` currently think in terms of retention expiry and archive promotion. That is too small.

Missing:

- promoted questions as durable objects
- answer lineage
- saved research traces
- explicit promotion from query result to canonical artifact
- staged external research before promotion to canon

### 6. Trust-first query router

`query_router.py` routes by regex to storage tiers. That is a storage router, not a knowledge router.

Missing:

- cheapest trustworthy layer first
- claim-ledger lookup before embeddings
- canonical page retrieval before raw chunk retrieval for synthesis queries
- historical evolution mode from git/logs
- graph mode for relationship questions
- staging mode for web-augmented answers

---

## Comparison Against The Knowledge-Compiler Pattern

| Target layer | Current state | Gap |
|---|---|---|
| Immutable sources | partial via vault sync and file watchers | no source registry, no immutable snapshots, no compile manifest |
| Parsing + claims + entities + provenance | entities exist; chunks have metadata | no atomic claim ledger, no claim provenance model, no parse artifacts as first-class outputs |
| Compiled wiki / canonical pages | absent | no compiled topic/entity/comparison pages |
| Retrieval indices | strong | currently too close to source of truth |
| Conflict / drift / test layer | drift detector exists; some tests exist | no contradiction registry, no knowledge assertions, no adversarial maintenance |
| Query + research + promotion loop | hooks and search exist | no staged promotion pipeline from query to durable artifact |

---

## Root Cause Analysis

The repo optimized for retrieval before it established what counts as durable truth.

That produced predictable consequences:

- multiple storage stories with no single authority
- embeddings and graph nodes standing in for claims
- markdown sync without a compiled page model
- retention logic treated as memory architecture rather than maintenance policy
- promotion treated as archival mechanics instead of epistemic value
- routing aimed at storage engines instead of trustworthy knowledge surfaces

This is why the system can be sophisticated and still be wrong in the important way.

---

## Immediate Production Repair

This is the short path to stop the live breakage without pretending the architecture problem is solved.

### P0: Stabilize the deployed service

- Salvage the unique auth hardening diff from `D:/Projects/memory-mcp-triple-system-deploy/src/mcp/http_server.py`.
- Commit the real lifecycle fixes from the dev repo to the canonical repo.
- Add a metadata backfill or defensive fallback for chunks missing numeric `*_ts` fields.
- Verify `MCP_API_KEY` is actually configured in Railway before declaring tool routes protected.
- Redeploy from Git, not from detached local state.

### P0 acceptance

- no `cleanup_expired` `AttributeError`
- no Chroma `$lt` type errors
- no detached deploy worktree in the production story
- `/tools/*` auth behavior is verified in the live environment

---

## Required Design Correction

The correct target is a knowledge compiler with retrieval as one consumer.

### Target vault layout

This layout belongs to the knowledge corpus, not to the app source tree:

```text
sources/
parse/
wiki/
registry/claims/
registry/entities/
conflicts/
questions/
tests/
logs/
indices/
staging/
```

### Meaning of each surface

- `sources/`: immutable raw inputs and manifests
- `parse/`: extracted chunks, claims, entities, citations, timestamps, chunk maps
- `wiki/`: canonical human-readable pages compiled from claims
- `registry/claims/`: atomic normalized claims with provenance and freshness
- `registry/entities/`: disambiguated entity records and aliases
- `conflicts/`: contradiction groups, contested claims, challenge notes
- `questions/`: promoted query outputs and decision memos
- `tests/`: knowledge assertions, ontology invariants, regression prompts
- `logs/`: ingest, compile, merge, demotion, promotion, migration events
- `indices/`: embeddings, BM25, graph edges, recency indexes
- `staging/`: external-web or untrusted research before promotion

---

## Mapping Current Components To The New Architecture

| Current component | Keep | New role |
|---|---|---|
| `vault_sync_service.py` | yes | source ingestion and incremental change detection |
| `file_watcher.py` and trigger watchers | yes | compile triggers |
| `entity_service.py` | yes | parse-stage entity extraction |
| `graph_service.py` | yes | one retrieval/index surface, not authority |
| `ontology_schema.py` | yes | schema and ontology versioning |
| `kv_store.py` observations and sessions | yes | operational memory and query trace support |
| `event_log.py` | yes | machine-readable lifecycle and compile log |
| `memory_promoter.py` | yes | promotion scoring for questions, claims, pages |
| `drift_detector.py` | yes | one input into conflict and freshness maintenance |
| `query_router.py` | rewrite | route by trustworthy knowledge surface, not storage tier regex alone |
| `promotion_pipeline.py` | rewrite | promote high-value questions and claims, not only expiring memories |

---

## Implementation Plan

### Phase 1: Canonical truth model

- Define `Claim`, `Entity`, `SourceDocument`, `CanonicalPage`, `ConflictSet`, and `PromotedQuestion` schemas.
- Add explicit schema versioning and migration metadata.
- Stop calling retrieval tiers “the architecture”. They are downstream indices.

### Phase 2: Compile pipeline

- Parse immutable sources into `parse/` artifacts.
- Extract claims and entities with provenance.
- Normalize entities, dates, units, and aliases.
- Compare against existing claim registry.
- Mark each candidate as new, reinforcing, or conflicting.
- Compile canonical pages from approved claims.

### Phase 3: Query router redesign

Route by intent and trust:

1. factual lookup -> claim registry then page snippets
2. conceptual synthesis -> canonical pages then comparison pages
3. historical evolution -> git and event logs
4. relationship questions -> graph index and entity registry
5. open-world research -> web to `staging/`, then explicit promotion

### Phase 4: Conflict and drift maintenance

- generate contradiction pages
- add freshness windows and claim decay
- flag stale pages when underlying claims move
- run adversarial challenge prompts against canonical pages
- add ontology migration tests

### Phase 5: Git semantics and evidence

- one commit per ingest or compile batch with machine-readable summary
- commit summaries must say which sources changed, which claims changed, and which pages changed
- treat schema migrations as first-class logged events

---

## Non-Negotiable Corrections To Existing Docs

The repo should stop claiming “production ready” as a blanket statement while:

- the live lifecycle scheduler is broken
- the deploy story depends on a detached worktree
- three architecture narratives coexist
- the claim/provenance/compiler layer does not exist

The honest framing is:

- `v1`: retrieval-centric memory service with partial capture and graph features
- `v2 target`: compiled knowledge operating system with claim provenance and maintenance layers

---

## Exit Criteria For A Defensible V2

Do not call the redesign complete until all of this is true:

- one canary source corpus ingests through `sources/` and `parse/`
- claims are stored separately from embeddings
- at least one compiled canonical page is generated from claims
- at least one contradiction page is generated from conflicting claims
- one promoted question is stored as a durable object
- the query router prefers claim/page surfaces before embeddings when appropriate
- a schema migration changes claim or entity shape without data loss
- one adversarial test run can break a stale page and force recompilation

---

## Practical Recommendation

Do not try to do the production rescue and the knowledge-compiler redesign in one branch.

Use two tracks:

- `Track P0`: production stabilization, tests, deployment truth
- `Track P1`: knowledge-compiler v2 behind a feature flag or separate branch

That is the only way to fix the live service without turning the repair effort into another pile of half-landed architecture.

---

## External Design References

- Karpathy LLM wiki gist: <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>
- Claudesidian: <https://github.com/heyitsnoah/claudesidian>
- DiffMem: <https://github.com/Growth-Kinetics/DiffMem>
- Khoj: <https://github.com/khoj-ai/khoj>
- Khoj knowledge graph: <https://github.com/khoj-ai/knowledge-graph>
