1. A [BLOCKER] - The computed-reachability roots are incomplete and the graph semantics are underspecified.

   - Three scripts presented as runnable by current-facing docs are omitted: `scripts/fix_imports.py` at `docs/QUICK-START.md:22`, `scripts/ingest_documentation.py` at `docs/architecture/SELF-REFERENTIAL-MEMORY.md:80`, and `scripts/obsidian_sync.py` at `README.md:446`. Section 1 declares all unrooted scripts dead at `audits/COMPLETION-PLAN-2026-09-03.md:40-52`, so Phase 3 would delete them while leaving current docs false. Either root them or remove their current-facing claims.
   - `conftest.py` alone is not the pytest bootstrap closure. Pytest implicitly loads `tests/conftest.py:1-21` and `tests/unit/conftest.py:1-25`; the former dynamically loads `tests/fixtures/real_services.py` through `pytest_plugins = ["fixtures.real_services"]`. Their current source imports happen to duplicate already-live server dependencies, but the root design is still incomplete.
   - No production `importlib`, entry-point, plugin, or config-named source loading was found. The only string module loads are test-side imports of the already-rooted HTTP server. `pyproject.toml` defines no entry points.
   - The resolver must explicitly include every ancestor `__init__.py`. Python executes package initializers before a submodule, and this repository uses lazy re-exports in `src/mcp/__init__.py:22-44`, `src/nexus/__init__.py:11-21`, and `src/services/__init__.py:4-10`.
   - A context-insensitive AST walk also marks dead code live: `src/nexus/processor.py:160-164` imports RLM only inside an optional, soon-deleted path; `TYPE_CHECKING` imports occur at `src/mcp/request_router.py:22-23`; and lazy `__getattr__` branches expose modules that may never be requested. The graph therefore proves import-unreachability, not absence of all dead code.
   - I checked every `try/except ImportError` containing imports under `src/`. Only the two visual blocks at `src/mcp/service_wiring.py:65-77` qualify for the proposed non-edge. Beads at `:44-55` is registered and live; reranking at `:59-62` defaults enabled at `:420-423`; Bayesian fallbacks, ChromaDB, spaCy, and the other blocks are live or external-dependency choices. The exception is sound only if encoded as exact file plus imported-module identities, with validation that no other path reaches those modules. A generic "optional try-import" rule is unsafe.

2. B [BLOCKER] - The canonical AST check is improved but still bypassable.

   The AST requirements at `audits/COMPLETION-PLAN-2026-09-03.md:57-72` prove that `self_test()` contains `assert not probe(bad)` and that `main()` makes its probe load-bearing. They do not prove that the `--self-test` branch calls `self_test()`, or that the module entry point calls `main()`. A script can contain both dead canonical functions and simply print `SELF_TEST_REJECTED <id>`. The AST oracle must match the CLI branch calling `self_test()`, its result controlling exit, and `__main__` invoking `main()`.

   `modules_accepted=12` is numerically correct for the 12 executable gates other than `run_self_tests.py`. However, `audits/GATES-2026-09-03.md:4-9` incorrectly says every `scripts/gates/*.py` has that shape; helpers such as `reachability.py`, `_embed_stub.py`, and the runner need explicit exclusion. The fixed manifest must also be checked against the discovered executable-gate set so an omitted thirteenth gate cannot escape validation.

3. C [BLOCKER] - The artifact split is right, but both artifact specifications still have defects.

   - "A sha256 of its own canonical content" at `audits/COMPLETION-PLAN-2026-09-03.md:79-82` is self-referential if the digest field is included. Define canonical hashing as the JSON object with the `sha256` field omitted, then store that digest.
   - The Phase 3 artifact records a "parent commit SHA" at `:83`, while deletion comparison checks out that SHA at `:96-101`. The plan never requires Phase 0-2 changes to be committed before recording it. With uncommitted changes, the comparison checkout lacks the actual pre-deletion tests and source. Require a clean Phase 0-2 checkpoint commit, then exclusively create the artifact with exactly that current `HEAD` as `pre_deletion_sha`, before any deletion.
   - Once those rules are added, exclusive creation and final read-only verification are properly ordered. The baseline remains intentionally historical; the Phase 3 SHA remains the immutable deletion boundary.

4. D [MAJOR] - The stdio count is defensible, but the HTTP count is incomplete under the stated wording.

   All 18 registered stdio tools are at `src/mcp/tool_registry.py:15-36`: `vector_search`, `unified_search`, `memory_store`, `graph_query`, `bayesian_inference`, `entity_extraction`, `hipporag_retrieve`, `detect_mode`, `lifecycle_status`, `obsidian_sync`, `beads_ready_tasks`, `beads_task_detail`, `beads_query_tasks`, `observation_timeline`, `kv_get`, `kv_set`, `kv_delete`, and `context_retrieve`.

   The five stdio handlers using the fused retrieval path are correctly enumerated: `vector_search`, `unified_search`, `graph_query` fallback, `hipporag_retrieve` fallback, and `context_retrieve` at `src/mcp/request_router.py:161-208,354-385,431-479,644-699,995-1022`. Other read-like tools are separate contracts: Bayesian is covered by P1a; Beads by P1b; lifecycle, observation timeline, and KV reads do not invoke the three tiers.

   Four HTTP routes can return memory retrieval results:

   - `/tools/vector_search`, `src/mcp/http_server.py:757-796`
   - `/tools/graph_query`, `src/mcp/http_server.py:854-870`
   - `/tools/search`, `src/mcp/http_server.py:873-907`
   - `/tools/unified_retrieve`, `src/mcp/http_server.py:938-980`

   P1c and its `http_routes=3` token omit `/tools/graph_query`. That route already converts exceptions to HTTP 500 and does not aggregate three tiers, so it is not presently a fake-success path. Nevertheless, the gate cannot claim "every live retrieval path." Either include it as a fourth, single-tier case or narrow the requirement and token to "every tri-tier aggregation route."

   `causes=3` is correct if it means three cause classes in `src/nexus/tier_queries.py`: missing service at `:39-41,85-87,136-138`; runtime exception at `:70-72,116-118,188-193`; and present Bayesian engine returning no result at `:145-149`.

5. E [BLOCKER] - Several corrected ranges are correct, but three remain unsafe or incomplete.

   - Correct: visual imports `src/mcp/service_wiring.py:64-77`; visual sidecar `:254-317`; Nexus lazy export `src/nexus/__init__.py:8,17-21`; Phase 5 tail imports/tests `tests/unit/test_phase5_memory_mcp_tail.py:7-14,33-53,56-85,88-119`; five Week 7 schema-dependent tests; bead script `scripts/test_bead_implementations.py:21-55,267`; and RLM test `tests/unit/test_nexus_processor.py:670-687`.
   - Unsafe: `src/nexus/processor.py:126-169` deletes the standard pipeline at `:140-152` and cuts through `_process_rlm`. The correct surgery is parameter/doc/assignment lines `:45,63,77`, argument `:101`, conditional block `:126-138`, and complete method `:154-177`.
   - Incomplete: `BeadsMemoryBridge` ends at `src/integrations/beads_bridge.py:763`, not `:748+`. Lines `:750-763` contain its cache methods.
   - Incomplete: `tests/integration/test_nexus_integration.py` must remove deleted-module imports at `:28-37`, not only the visual import at `:33`. Its class boundaries are `TestFrontmatterMapper :111-191`, `TestPropertyInheritanceChain :194-269`, `TestDashboardGraphVisualizer :272-392`, and `TestCrossModuleIntegration :395-485`. Both cross-module tests use deleted mapper/inheritance/visualizer classes, so the entire `:395-485` class should be deleted, not left for an unspecified audit.

6. F [MAJOR] - The four reference forms are appropriate, but the planted oracle is not implementable unambiguously as written.

   `scripts/check_docs.py:15-26` scans ten fixed relative documents. Pointing `--docs-root` at a temporary tree containing only a copied `docs/CURRENT.md` produces nine unrelated missing-document violations. The fixture must copy all ten `CURRENT_DOCS` paths into the temporary docs root, mutate only `docs/CURRENT.md`, and keep `--code-root` pointed at the real repository.

   Bare imports also need a precise local/external rule. Current docs contain third-party imports such as `typing`, `fastapi`, and `pydantic` at `docs/integration/BEADS-MEMORY-MCP-INTEGRATION-MANIFEST.md:339,665-666`. Treat a bare import as local only when its first package resolves under `code_root/src`; plant the violation under an existing local package. Define external-block boundaries from the absolute `Location` line through its associated fenced block. Then the four violations plus the Life OS non-violation at manifest `:661-668` form a valid oracle.

7. G [BLOCKER] - Nine EXPECT tokens are coherent; four inherit or expose gaps.

   Coherent as written: P0-3, P1d, P1a, P1b, P2a, P2b, P4, P5, and P6 at `audits/GATES-2026-09-03.md:15,30,35,40,50,55,65,70,75`.

   Problematic:

   - P0-5 `sha256_match=1` is undefined until the hash exclusion rule in C is specified.
   - P0-6 can report `modules_accepted=12 shape_violations=0` despite bypassing `self_test()`, as described in B.
   - P1c's `http_routes=3 http_all_down_503=3` conflicts with its universal retrieval-path wording.
   - P3 permits any `allowed_dead=[0-9]+` at `audits/GATES-2026-09-03.md:60`. Since v6 expects one named exception, require the exact expected count and identity/reason validation. Otherwise arbitrary dead files can be added to `ALLOWED_DEAD` while the token stays green.

8. H [MAJOR] - Keeping `universal_components.py` is currently the correct compatibility decision, but `ALLOWED_DEAD` is the wrong model.

   There are no internal calls beyond wrapper definitions, as recorded at `audits/COMPLETION-PLAN-2026-09-03.md:293-300`. However, the wrappers are deliberately exported as public compatibility names by `src/mcp/stdio_server.py:171-181`, and dynamic module attributes route through them at `:42-51`. Static internal call-unreachability is therefore insufficient evidence for deletion under the plan's backwards-compatibility rule.

   Because both servers import the module, it is inside the computed import closure and cannot simultaneously be an `ALLOWED_DEAD` exception to that closure. Keep it as import-live and record it separately as `ALLOWED_CALL_UNREACHABLE`, without affecting `dead_remaining`. Deletion would require an explicit compatibility/deprecation decision, not merely a Phase 3 call graph.

Safe to start Phase 0: NO.
Blocking gaps remain in reachability roots, gate self-test wiring, artifact hashing/checkpointing, and Phase 3 ranges.
A further planning round can close every identified blocker using the evidence above.
Executing Phase 0 is only needed to reveal the actual computed closure and environment measurements, not to resolve these specifications.
Recommended next action: issue v7 with these bounded corrections, then start Phase 0.
