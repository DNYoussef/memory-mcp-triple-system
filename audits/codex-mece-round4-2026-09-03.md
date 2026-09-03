## A. KEEP rule

1. **BLOCKER - Dead source modules remain classified as KEEP.** The four clauses do not reach `external_import_schema.py`, `frontmatter_mapper.py`, `property_inheritance.py`, `loop_interfaces.py`, or `metadata_sync.py`. The last is imported only by the package facade and its dedicated test ([integrations/__init__.py:4](D:/Projects/memory-mcp-triple-system/src/integrations/__init__.py:4)); frontmatter/property are reached only by tests ([test_nexus_integration.py:28](D:/Projects/memory-mcp-triple-system/tests/integration/test_nexus_integration.py:28)); loop interfaces only by an unqualified manual script ([test_bead_implementations.py:110](D:/Projects/memory-mcp-triple-system/scripts/test_bead_implementations.py:110)). `src/stores/event_log.py.init` is also an unreferenced artifact. This violates the stated delete-every-unreachable-source outcome ([plan:14](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:14)).

2. **MAJOR - Section 5 does not operationalize the KEEP rule for scripts.** All 67 current `scripts/` files were checked. Ten have current-doc or CI evidence, 18 are scheduled for deletion, `populate_memory_mcp.py` is explicitly kept despite having no qualifying reference, and 38 remain unclassified. The latter include `audit_memory.py`, `bootstrap_graph.py`, `compact_graph.py`, `extract_graph_entities.py`, `find_agents.py`, the three migration scripts, `populate_knowledge_base.py`, `promotion_pipeline.py`, `query_bb_beads.py`, `repair_metadata.py`, both server test wrappers, both startup PowerShell scripts, three remaining verifier scripts, `weekly_hygiene.py`, and `test_bead_implementations.py`. Compare the narrow KEEP list ([plan:31](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:31)) with the partial deletion list ([plan:190](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:190)). No v5-deleted script was found to satisfy clauses (a)-(d).

No live deletion was found in `src/hooks`, `src/models`, `src/universal_components.py`, the nonvisual indexing modules, or the real KV/event stores.

## B. AST-backed self-tests

3. **BLOCKER - A script can still pass without executing the real probe.** AST proves syntax, not execution or data flow. A script can place `probe(...)` under `if False`, ignore another probe result, and print the exact expected line. The runner then accepts both stdout and the AST shape described at [plan:46](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:46). The check is implementable only if v5 mandates a canonical AST shape that consumes the result, such as `assert not probe(bad_fixture)`, and separately proves the normal branch's result controls exit/token emission. Also, two branch calls across 12 modules do not naturally equal the advertised `ast_probe_calls=12` ([GATES:23](D:/Projects/memory-mcp-triple-system/audits/GATES-2026-09-03.md:23)); that value can only mean "12 modules accepted," not actual calls.

The Railway self-test can avoid Docker: a client-shaped shared probe can accept a FastAPI `TestClient` during self-test and an HTTP client during the real run. That part is implementable as written ([plan:53](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:53)).

## C. Baseline and nodeid floor

4. **BLOCKER - The immutable baseline has a chicken-and-egg contradiction.** Phase 0 exclusively creates and commits the baseline ([plan:55](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:55)), but `pre_deletion_sha` is the parent of a future Phase 3 commit and is written by Phase 3 ([plan:72](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:72)). Phase 3 must therefore modify the supposedly immutable file, while a second `--write` must fail. Put the SHA in a separately exclusive-created Phase 3 artifact.

5. **MAJOR - P0-5 does not verify its immutability claims.** `--verify` checks only the acceptance summary ([plan:61](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:61)); its EXPECT has no exclusive-create refusal, baseline fingerprint, or `pre_deletion_sha` field ([GATES:18](D:/Projects/memory-mcp-triple-system/audits/GATES-2026-09-03.md:18)). A modified baseline can pass.

6. **MINOR - Temporary Git worktree cleanup is unspecified.** `git worktree add` registers repository metadata; removing only the temporary directory leaves stale registrations. `deletion_closure.py` needs `git worktree remove` in `finally`. Apart from the SHA ownership problem, current-working-tree versus immutable-SHA nodeid set comparison is reverify-stable.

## D. P1c

7. **BLOCKER - Bayesian timeout/skip remains unrecorded.** The plan records exceptions and missing-service early returns, but `_query_bayesian_tier()` also returns `None` when an existing engine returns no result ([tier_queries.py:145](D:/Projects/memory-mcp-triple-system/src/nexus/tier_queries.py:145)). With vector and graph unavailable, that leaves only two degraded keys, so all-three-down still reports success.

8. **BLOCKER - Three live retrieval paths remain outside P1c.** Registered stdio `graph_query` and `hipporag_retrieve` still use status-discarding `execute()` fallbacks and return `isError: False` ([request_router.py:354](D:/Projects/memory-mcp-triple-system/src/mcp/request_router.py:354), [request_router.py:431](D:/Projects/memory-mcp-triple-system/src/mcp/request_router.py:431)). HTTP `/tools/unified_retrieve` calls the degrading router and always returns a normal response ([http_server.py:938](D:/Projects/memory-mcp-triple-system/src/mcp/http_server.py:938), [unified_router.py:84](D:/Projects/memory-mcp-triple-system/src/routing/unified_router.py:84)). P1c covers only stdio vector/unified/context and HTTP vector/search.

9. **MAJOR - Existing vector tests remain broken.** The fixture configures only `execute.return_value` ([test_stdio_server.py:102](D:/Projects/memory-mcp-triple-system/tests/unit/test_stdio_server.py:102)). Both default and custom-limit tests assert calls to `execute()` ([test_stdio_server.py:159](D:/Projects/memory-mcp-triple-system/tests/unit/test_stdio_server.py:159), [test_stdio_server.py:165](D:/Projects/memory-mcp-triple-system/tests/unit/test_stdio_server.py:165)). V5 names only the first assertion and does not specify an `execute_with_status.return_value` tuple.

The nine tier monkeypatch lambdas are the only two-argument overrides found; updating those nine closes that specific compatibility issue.

## E. P2b

10. **BLOCKER - `INSERT OR IGNORE` does not implement expiring claims.** `key` is a valid primary key ([kv_store.py:113](D:/Projects/memory-mcp-triple-system/src/stores/kv_store.py:113)), and SQLite rowcount was measured as 1 for insertion and 0 for conflict. But expiry is application metadata; SQLite does not delete an expired row. Only `get()` performs lazy deletion ([kv_store.py:234](D:/Projects/memory-mcp-triple-system/src/stores/kv_store.py:234)). Therefore the claim can be acquired once and never again. `set_if_absent` must atomically delete the same key when `expires_at <= now`, then insert within one transaction.

The proposed injections are otherwise correct: HTTP should pass `get_kv_store()` at [http_server.py:262](D:/Projects/memory-mcp-triple-system/src/mcp/http_server.py:262), and stdio should pass `tool.kv_store` at [request_router.py:284](D:/Projects/memory-mcp-triple-system/src/mcp/request_router.py:284). The raw-SQL plus spy gate is suitable after claim expiry is fixed.

## F. DELETE closure

11. **BLOCKER - The service-wiring surgery ranges are syntactically incomplete.** The visual imports start at line 64, including `Qwen3VLEmbedder` at line 66, not line 67 ([service_wiring.py:64](D:/Projects/memory-mcp-triple-system/src/mcp/service_wiring.py:64)). `_init_visual_memory` continues through line 317; deleting only 255-305 leaves the middle of a call and its exception block ([service_wiring.py:273](D:/Projects/memory-mcp-triple-system/src/mcp/service_wiring.py:273)). The closure must remove 64-77 and 254-317 as coherent units.

12. **BLOCKER - Two visual importers are still missed.** `tests/unit/test_qwen3vl_embedder.py` directly imports the deleted embedder ([test_qwen3vl_embedder.py:19](D:/Projects/memory-mcp-triple-system/tests/unit/test_qwen3vl_embedder.py:19)). `tests/integration/test_nexus_integration.py` imports deleted visualization code at line 33 and contains visual-only and mixed visual tests from lines 272-485 ([test_nexus_integration.py:33](D:/Projects/memory-mcp-triple-system/tests/integration/test_nexus_integration.py:33), [test_nexus_integration.py:272](D:/Projects/memory-mcp-triple-system/tests/integration/test_nexus_integration.py:272)). Both cause collection failure after deletion unless removed or surgically trimmed.

13. **BLOCKER - The `test_bead_implementations.py` ranges contradict the intended surgery.** The mode-router function occupies lines 21-55, not 21-28. Its invocation is only line 267, while deleting 267-282 removes all six invocations, including the five explicitly meant to stay ([test_bead_implementations.py:21](D:/Projects/memory-mcp-triple-system/scripts/test_bead_implementations.py:21), [test_bead_implementations.py:265](D:/Projects/memory-mcp-triple-system/scripts/test_bead_implementations.py:265)).

The phase5-tail "keep only GraphService" direction closes its top-level imports if followed literally. The Nexus RLM range is exact. Week7 must remove all five SchemaValidator-dependent tests, not merely the first. No over-deletion was found for `src/validation`, `src/cache`, `src/woundhealer`, or the four schema modules once the missed importers above are handled.

## G. Documentation oracle

14. **MAJOR - Split roots are sound, but the negative control does not prove the four-form parser or external-path exemption.** The fixture plants only the forward-slash path form ([plan:223](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:223)). It never plants backslash, `from src...`, bare local import, a package import, or a missing local-looking import inside an external absolute-path block. Bare imports are particularly contextual: the manifest contains local-looking imports inside both this repository's block and the external Life OS block ([manifest:335](D:/Projects/memory-mcp-triple-system/docs/integration/BEADS-MEMORY-MCP-INTEGRATION-MANIFEST.md:335), [manifest:661](D:/Projects/memory-mcp-triple-system/docs/integration/BEADS-MEMORY-MCP-INTEGRATION-MANIFEST.md:661)). Use separate planted cases plus an external-block nonviolation control.

## H. EXPECT tokens

15. **BLOCKER - P0-3 is impossible as written.** There are eight extant stale oracles, while both plan and EXPECT say seven ([plan:62](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:62), [GATES:13](D:/Projects/memory-mcp-triple-system/audits/GATES-2026-09-03.md:13)). A correct deletion prints `absent=8` and fails the regex. Also, `stale_oracles.py` must name its targets, so scanning `scripts/` while excluding only `.git`, audits, archive, and connascence finds its own references. `refs=0` requires excluding the oracle's manifest/source declaration. The connascence multiplicity is measurable and currently equals 42, so `excluded_scan_artifacts=[1-9]\d*` is viable.

16. **MAJOR - P1c multiplicities do not cover the claimed surface.** `all_down_http=503` can represent either HTTP route without proving both; no tokens cover stdio graph/hipporag or HTTP unified-retrieve. `threads=4` and `vector_all_down=1` are measurable, but insufficient for the complete live-path claim ([GATES:43](D:/Projects/memory-mcp-triple-system/audits/GATES-2026-09-03.md:43)).

17. **MAJOR - P3 can certify an incomplete manifest.** `deleted`, `kept`, and `tools` need only be nonzero, while expected nodeids are derived from the same closure manifest being audited ([GATES:58](D:/Projects/memory-mcp-triple-system/audits/GATES-2026-09-03.md:58)). Omitting a dead module and its tests from both sides remains green. Bind exact independently reviewed path/function manifests or their fingerprints.

`cases=9`, `threads=4`, `contenders=2`, and `vector_all_down=1` are directly measurable. `forms=4` and `ast_probe_calls=12` are currently self-reported rather than proven. P1b, P2a, P2b after the TTL fix, and P6 have workable EXPECT tokens if their scripts assert every described condition before printing. P1d, P1a, and P5 were not re-audited as instructed.

Verdict: NOT SAFE to start Phase 0.
BLOCKER findings: 10.
MAJOR findings: 6.
MINOR findings: 1.
Required first: revise P0.2/P0.3/P0.4, P1c, P2b, Phase 3 closure/ranges, and the P4 oracle.
