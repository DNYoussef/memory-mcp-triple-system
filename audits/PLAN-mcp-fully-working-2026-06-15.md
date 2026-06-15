# Plan v2: Memory MCP - all parts and layers working (2026-06-15)

v2 = my phase skeleton collapsed with Codex's adversarial MECE pass (the rival
read the v1 plan + MECE doc + source and attacked it; accepted findings folded in).

## Goal (definition of done)
A hermetic acceptance harness passes when run by **both** Claude (stdio MCP) and
**Codex** (CLI/HTTP) against a defined capability contract. "Explain each part"
is a non-gating review note, not a test.

## Acceptance harness (P0 artifact, the contract)
`scripts/acceptance_all_parts.py`:
- Spins up a FRESH temp `MEMORY_MCP_DATA_DIR`, clears `CHROMA_PERSIST_DIR`.
- Seeds unique canary memories (random ids/text), then for each capability asserts the canary comes back (by id/text), not just "non-empty".
- Tears down.
- Capabilities probed (each starts as xfail, flipped green by its phase): store, vector, graph/HippoRAG, unified fusion, lifecycle aging, KV, broader-recall (was "creative"), context retrieval (was "injection").
- Runs against ONE canonical capability contract = the common surface both transports can serve; surface gaps are recorded honestly, not faked.

## Process (de-ritualized per Codex)
- Per phase: 1 fail-first test + 1 black-box acceptance probe (flip its xfail). 
- Codex zero-trust audit at phase EXIT only (not every micro-step).
- Ponytail/Headroom/Sequential-Thinking used where they earn it, not as ritual gates.
- Shared-surface changes are SERIALIZED; only isolated unit tests + docs run parallel.

---

## Phases (reordered per Codex)

### P0 - Harness + capability contract  [do first]
- Build the hermetic `acceptance_all_parts.py` (above) with every capability xfailed.
- Define the canonical capability contract + audit the stdio (14 tools) vs HTTP surfaces; pick the common set (or add thin adapters). KV + others get added in P2.
- Exit gate: harness runs, all capabilities xfail for the right reason (recorded), green path proven on `store` only.

### P1 - Storage + write-path metadata  [blocks all reads]
- A1: ONE shared chroma-dir resolver used by BOTH HTTP `get_indexer()` and stdio `VectorSearchTool.indexer`; default `<MEMORY_MCP_DATA_DIR>/chroma`, keep `CHROMA_PERSIST_DIR` override.
- A3: validate collection embedding dim vs configured model on startup.
- Write path writes numeric `last_accessed_ts` + `stage` so demotion is possible.
- Exit gate: store->retrieve round-trips to the same root under a custom data dir on both transports; a freshly stored chunk carries demotion-ready metadata. Flip vector/store canaries green.

### P2 - Canonical surface parity
- Expose the agreed common tool set on both transports; B4: register `kv_get/kv_set/kv_delete` (or drop from contract).
- B3: per dormant subsystem (sweeper/drift/weekly/quality) - wire into contract or quarantine to `experimental/` + doc. Default: quarantine (ponytail).
- Exit gate: KV + graph + unified canaries green on both transports.

### P3 - Lifecycle ages  [depends on P1 metadata]
- A2: lifecycle maintenance runs under stdio too (transport-neutral start or on-startup catch-up sweep), bounded so short sessions don't over-demote.
- Exit gate: a chunk with an old `last_accessed_ts` demotes without restart/backfill; a fresh one does not. Flip lifecycle canary green.

### P4 - Bayesian: honest by default  [HIGH RISK]
- Default: B1 honest 2-tier. `bayesian_inference` returns an explicit "disabled (no trained model)" - NOT a timeout; Nexus renormalizes vector/graph weights when Bayesian is absent. Add the one rule: skip Bayesian unless mode/query is explicitly probabilistic (NOT the mismatched QueryRouter).
- Only if a real observations/training path exists: build it + a calibration fixture proving `P(X|Y)` behaves, and gate on a Bayesian contribution/trace object (pseudo-docs are dropped, so `bayesian_score` in results is not a valid gate).
- Exit gate: either calibrated inference fixture passes, OR the system cleanly reports 2-tier and weights renormalize. Docs match whichever.

### P5 - Broader-recall + context retrieval (was creative/injection)
- Broader-recall: brainstorming returns strictly more results AND more distinct entities/source-tiers than execution, else rename to "broader recall" and drop the "creative" claim.
- Context retrieval: prove a manual trigger returns relevant context for a query (the injector's real, testable behavior); do not claim auto-injection unless a registered tool does it.
- Exit gate: both probes green or the claim is renamed/cut.

### P6 - Honest docs, then self-ingestion
- Generate the current contract (entrypoints, tools, routes, auth, storage env) from `tool_registry.py` + FastAPI routes; move v1/v7/planning to `docs/project-history/`.
- THEN fix self-ingestion (D1) to load only current docs with authority metadata.
- Exit gate: docs match the harness contract; self-ingest pulls only current docs.

---

## Premortem (assume shipped and failed)
1. Acceptance passes on stale data -> hermetic temp dir + canary assertions (P0).
2. "Both models work" but different surfaces -> canonical contract defined P0, gaps recorded honestly.
3. Storage unified but stdio path still diverges -> one shared resolver, tested on both transports (P1).
4. Lifecycle can't demote because ingestion never wrote the timestamp -> P1 write-path fix precedes P3.
5. Bayesian "on" but synthetic/garbage -> honest 2-tier default; real path needs a calibration fixture.
6. Multi-agent edits to shared surface collide -> serialize P1-P4; worktree-per-phase; merge at boundaries.

## Isolation / safety
- All code in dedicated worktrees off `origin/main`; never touch the user's 6 uncommitted working-tree files.
- `codex -C <worktree> --dangerously-bypass-approvals-and-sandbox` confined to its worktree; read-only `codex exec` for audits.

## Status
v2 collapsed. Next: execute P0 (build the hermetic harness + contract) in worktree `../mmts-a1`.
The original single-fix A1 is now folded into P1.
