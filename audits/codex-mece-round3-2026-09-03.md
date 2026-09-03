## A. KEEP rule

1. **MAJOR - Import reachability over-keeps the unused visual stack.** The KEEP rule treats every transitive import as live ([plan:30](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:30)). `service_wiring` imports the visual embedder, service, indexer, and router ([service_wiring.py:64](D:/Projects/memory-mcp-triple-system/src/mcp/service_wiring.py:64)), but they are reachable only through unused properties ([service_wiring.py:254](D:/Projects/memory-mcp-triple-system/src/mcp/service_wiring.py:254)); no visual tool is registered ([tool_registry.py:15](D:/Projects/memory-mcp-triple-system/src/mcp/tool_registry.py:15)). Use handler/documented-script reachability, then delete the visual stack and its four test files.

2. **MAJOR - `ci_drift_validator.py` is kept after deleting its entire implementation.** The plan says to keep the script while removing its ownership import/check ([plan:184](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:184)), but initialization, scanning, reporting, and fixing all use `OwnershipRegistry` ([ci_drift_validator.py:29](D:/Projects/memory-mcp-triple-system/scripts/ci_drift_validator.py:29), [ci_drift_validator.py:92](D:/Projects/memory-mcp-triple-system/scripts/ci_drift_validator.py:92)). Delete the script or keep its backend; a no-op validator must not survive.

No live DELETE target was found through the current-facing documented scripts, Dockerfiles, `railway.toml`, or `.github`.

## B. P0.2 and P0.3

3. **MAJOR - The manifest runner cannot enforce "same probe."** It only observes `SELF_TEST_REJECTED` ([plan:45](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:45), [GATES:22](D:/Projects/memory-mcp-triple-system/audits/GATES-2026-09-03.md:22)). A gate can branch on `--self-test` and print the token without invoking its probe. At minimum, the runner must require return code 0 and stdout exactly equal to the expected single line; source review must verify the shared probe call.

4. **MINOR - Baseline creation needs exclusive file creation.** "Refuses overwrite" is underspecified ([plan:51](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:51)); an existence-check followed by ordinary writing has a race. Require `open(..., "x")` or equivalent. Verification should parse the exact acceptance summary and require `12 PASS`, `0 XFAIL`, `0 FAIL`, `of 12`, and exit 0. Reprinting immutable benchmark/coverage values is otherwise appropriate for a baseline.

## C. P0.6 collection floor

5. **BLOCKER - `HEAD~1` stops identifying the pre-deletion tree after the next commit.** The algorithm assumes HEAD is permanently the deletion commit ([plan:65](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:65)). During final Phase 4/5 reverify, HEAD and HEAD~1 are both post-deletion, so subtracting the closure count fails spuriously. Record the pre-deletion commit SHA and verify against that immutable SHA.

6. **MINOR - Count collected node IDs, not source functions.** The current listed deletion files contain no parametrized tests, so their present item/function counts happen to agree; skips also remain collected. The formulation is still fragile if closure changes. Derive deleted node IDs from the pre-deletion `--collect-only` output, which naturally handles parametrization and collection hooks.

## D. P1c

7. **MAJOR - The status keyword breaks nine existing monkeypatches.** `process()` reaches tier methods through `recall()` ([processor.py:319](D:/Projects/memory-mcp-triple-system/src/nexus/processor.py:319), [processor.py:428](D:/Projects/memory-mcp-triple-system/src/nexus/processor.py:428)). The cited lambdas accept only `(q, k)` ([test_nexus_processor.py:133](D:/Projects/memory-mcp-triple-system/tests/unit/test_nexus_processor.py:133), [test_nexus_processor.py:162](D:/Projects/memory-mcp-triple-system/tests/unit/test_nexus_processor.py:162), [test_nexus_processor.py:189](D:/Projects/memory-mcp-triple-system/tests/unit/test_nexus_processor.py:189)). Passing `status=` from `process()` raises `TypeError`. Update those lambdas to accept `status=None`.

8. **BLOCKER - Stdio `vector_search` still reports success when all tiers degrade.** The plan keeps it on unchanged `execute()` while only `unified_search` and `context_retrieve` consume status ([plan:105](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:105)). Its handler currently always returns `isError: False` ([request_router.py:175](D:/Projects/memory-mcp-triple-system/src/mcp/request_router.py:175), [request_router.py:208](D:/Projects/memory-mcp-triple-system/src/mcp/request_router.py:208)). Make this handler call `execute_with_status()` and update its existing `execute()` assertions ([test_stdio_server.py:159](D:/Projects/memory-mcp-triple-system/tests/unit/test_stdio_server.py:159)).

9. **MAJOR - Raising HTTP 503 inside either route becomes 500.** Both target routes catch every `Exception` and translate it to 500 ([http_server.py:794](D:/Projects/memory-mcp-triple-system/src/mcp/http_server.py:794), [http_server.py:905](D:/Projects/memory-mcp-triple-system/src/mcp/http_server.py:905)). Add `except HTTPException: raise` before those catches or return a 503 response directly.

The proposed per-call dictionary itself is request-local; no remaining shared degradation-status state was found.

## E. P2a

No finding. After the facade delegates through `_handle_call_tool`, both paths converge on the single trace site ([protocol_handler.py:55](D:/Projects/memory-mcp-triple-system/src/mcp/protocol_handler.py:55), [stdio_server.py:144](D:/Projects/memory-mcp-triple-system/src/mcp/stdio_server.py:144)). Removing the vector handler's old trace and asserting `rows == 2 * tools` correctly catches both missing and duplicate writes. `QueryTrace.log()` inserts exactly one row per call ([query_trace.py:194](D:/Projects/memory-mcp-triple-system/src/debug/query_trace.py:194)).

## F. P2b

10. **MAJOR - `MemoryIngestionService` has no service-owned KV store.** Its constructor accepts no `kv_store` ([memory_ingestion_service.py:34](D:/Projects/memory-mcp-triple-system/src/services/memory_ingestion_service.py:34)). Both HTTP and stdio constructors must inject the existing KV instance ([http_server.py:262](D:/Projects/memory-mcp-triple-system/src/mcp/http_server.py:262), [request_router.py:284](D:/Projects/memory-mcp-triple-system/src/mcp/request_router.py:284)); tests need `kv_store=None` in their fixture.

11. **MAJOR - A day bucket is not "older than 24h."** The plan states both contracts ([plan:135](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:135)). Calendar buckets permit two runs minutes apart across midnight. Choose either rolling 24 hours with an atomic timestamp claim or explicitly redefine the contract as once per UTC calendar day.

12. **MAJOR - The expired-entry assertion can pass without scheduled cleanup.** `KVStore.get()` itself deletes expired entries ([kv_store.py:234](D:/Projects/memory-mcp-triple-system/src/stores/kv_store.py:234)). Therefore checking the canary with `get()` after ingestion proves nothing about `cleanup_expired()`. Inspect `keys()` or raw SQL before/after and separately spy the cleanup call.

## G. DELETE closure

13. **BLOCKER - The listed closure leaves collection-breaking importers.** Four omitted files directly import deleted backends: [test_ontology_bridge.py:23](D:/Projects/memory-mcp-triple-system/tests/test_ontology_bridge.py:23), [test_ownership_registry.py:14](D:/Projects/memory-mcp-triple-system/tests/test_ownership_registry.py:14), [test_quality_gate.py:14](D:/Projects/memory-mcp-triple-system/tests/unit/test_quality_gate.py:14), and [test_tag_scorer.py:1](D:/Projects/memory-mcp-triple-system/tests/unit/test_tag_scorer.py:1). They contain 35 collected tests. The mixed-file instruction also explicitly keeps two capture-dependent tests while deleting `src/services/capture/` ([plan:175](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:175), [test_phase5_memory_mcp_tail.py:9](D:/Projects/memory-mcp-triple-system/tests/unit/test_phase5_memory_mcp_tail.py:9), [test_phase5_memory_mcp_tail.py:88](D:/Projects/memory-mcp-triple-system/tests/unit/test_phase5_memory_mcp_tail.py:88)).

14. **MAJOR - Four orphan schema modules and one dedicated test remain.** Add `ontology_schema.py`, `proactive_schema.py`, `ephemeral_buffer_schema.py`, and `confidence_scoring_schema.py` to DELETE. Their consumers are all in the planned deletion closure, except `ci_drift_validator`, whose dependency contradiction is finding 2. Also delete [test_proactive_schema.py:12](D:/Projects/memory-mcp-triple-system/tests/test_proactive_schema.py:12).

15. **MINOR - `verify_wiring.py` becomes a stale oracle.** P2a removes handler-local trace logging, but this script requires that exact source pattern ([verify_wiring.py:43](D:/Projects/memory-mcp-triple-system/scripts/verify_wiring.py:43)). Update it to inspect the central router or delete it under the Section 1 rule.

The whole `BeadsMemoryBridge` deletion is safe: the class starts at [beads_bridge.py:530](D:/Projects/memory-mcp-triple-system/src/integrations/beads_bridge.py:530) and has no external importer. The `rlm_adapter`, `use_rlm`, and `_process_rlm` removal is also closed once `public_api.py` and the named test are deleted.

## H. Phase 4

16. **BLOCKER - The negative-control root contains docs but no code.** The plan copies only README and `docs/`, while the new rule resolves modules under `--root` ([plan:203](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:203)). Every valid `src/...` reference then appears missing, or tool harvesting cannot import `src`. Separate `--docs-root` from `--code-root`, or copy `src/` into the fixture.

17. **MAJOR - The three patterns miss two actual target references.** The manifest uses `from nexus.public_api import`, without the `src.` prefix ([manifest:341](D:/Projects/memory-mcp-triple-system/docs/integration/BEADS-MEMORY-MCP-INTEGRATION-MANIFEST.md:341), [manifest:668](D:/Projects/memory-mcp-triple-system/docs/integration/BEADS-MEMORY-MCP-INTEGRATION-MANIFEST.md:668)). Package imports such as [README.md:458](D:/Projects/memory-mcp-triple-system/README.md:458) must resolve to `src/mcp/__init__.py`, while an external absolute path such as [manifest:661](D:/Projects/memory-mcp-triple-system/docs/integration/BEADS-MEMORY-MCP-INTEGRATION-MANIFEST.md:661) must not be interpreted as a local module.

## I. P6

18. **MAJOR - Host connectivity remains underspecified.** The override itself works: Docker defines API mode ([Dockerfile.railway:10](D:/Projects/memory-mcp-triple-system/Dockerfile.railway:10)), and the delegate reads `EMBEDDING_API_BASE` at construction ([embedding_pipeline_api.py:28](D:/Projects/memory-mcp-triple-system/src/indexing/embedding_pipeline_api.py:28)). However, Linux requires `--add-host=host.docker.internal:host-gateway`, and the stub must bind a host-reachable address such as `0.0.0.0`, not loopback. Put both requirements in `railway_smoke.py`, not only the workflow prose.

No intrinsic round-trip problem was found. The stub must use `hashlib`, return OpenAI-shaped `{"data": [{"index": ..., "embedding": [...]}]}`, accept `dimensions` and `encoding_format`, and emit a nonzero 384-dimensional vector. The client appends `/embeddings` ([embedding_pipeline_api.py:43](D:/Projects/memory-mcp-triple-system/src/indexing/embedding_pipeline_api.py:43)); identical store/query text will therefore produce identical Chroma vectors.

## J. EXPECT audit

19. **BLOCKER - P0-3 cannot currently produce `refs=0`.** The gate scans `docs/` while excluding only `audits/` and `archive/` ([plan:57](D:/Projects/memory-mcp-triple-system/audits/COMPLETION-PLAN-2026-09-03.md:57)). Tracked connascence artifacts contain 42 matching stale-oracle references, beginning at [connascence.json:3141](D:/Projects/memory-mcp-triple-system/docs/connascence/scan-2026-06-06/connascence.json:3141). Exclude point-in-time scan artifacts or remove them explicitly.

20. **MINOR - Several EXPECT fields do not pin their claimed multiplicity.** `handlers=3 modes=3` does not prove nine Beads combinations ([GATES:37](D:/Projects/memory-mcp-triple-system/audits/GATES-2026-09-03.md:37)); `concurrent_leak=0` and `concurrent_runs=1` do not prove any contender count ([GATES:42](D:/Projects/memory-mcp-triple-system/audits/GATES-2026-09-03.md:42), [GATES:52](D:/Projects/memory-mcp-triple-system/audits/GATES-2026-09-03.md:52)). Add `cases=9`, `threads=4`, and `contenders=2`, plus `vector_all_down=1`.

EXPECT coverage:

- P0-3: blocked by finding 19.
- P0-5 and P0-6: findings 3-4.
- P1d and P1a: no token-level defect found.
- P1b: finding 20.
- P1c: findings 7-9 and 20.
- P2a: sound if the script itself asserts the arithmetic.
- P2b: findings 10-12 and 20.
- P3: findings 5-6 and 13-15.
- P4: findings 16-17.
- P5: no token-level defect found.
- P6: sound after finding 18 is specified.

Verdict: NOT SAFE to start Phase 0 from v4.  
Blockers: 5.  
Phase 0 itself is blocked by P0-3's impossible refs=0 oracle.  
Later blockers are unstable HEAD~1, stdio vector false success, broken deletion closure, and the docs split-root.  
Revise those five and bind the major oracle details before authoring gates.
