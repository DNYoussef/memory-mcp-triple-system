The plan is not safe to collapse or execute.

1. [BLOCKER] The triage rule is backwards. `docs/CURRENT.md` describes observed behavior and explicitly warns that older material may be aspirational; its "Known remaining" section is not a product specification (`docs/CURRENT.md:3-8`, `docs/CURRENT.md:68-73`). Therefore a false sentence should normally be corrected, not automatically WIREd as required by the plan (`audits/COMPLETION-PLAN-2026-09-03.md:23-29`). `CLAUDE.md` only specifies memory-hook behavior, not these subsystems (`CLAUDE.md:1-9`). Use KEEP for required/reachable code, FIX/WIRE for owner-approved behavior, DELETE for an entire unreachable dependency closure, and HANDOFF for unresolved owner decisions.

2. [BLOCKER] The completion invariant contradicts the deferred phase. The plan requires every unreachable module to receive an explicit KEEP decision (`audits/COMPLETION-PLAN-2026-09-03.md:13-16`), but then leaves thousands of lines under `src/` awaiting later archive PRs or owner decisions (`audits/COMPLETION-PLAN-2026-09-03.md:151-159`). DEFER is not completion; these choices must be resolved before the branch can be green.

3. [MAJOR] Not wiring `src/sleep` is the correct ponytail verdict, but P2b still duplicates existing work. Every ingestion already invokes lifecycle maintenance (`src/services/memory_ingestion_service.py:145-146`, `src/services/memory_ingestion_service.py:265-273`), and an existing test asserts demotion and archival (`tests/unit/test_memory_ingestion_service.py:90-93`). HTTP already uses the separate, functional `src/memory/lifecycle_scheduler.py` (`src/memory/lifecycle_scheduler.py:23-43`, `src/mcp/http_server.py:729-744`). The proposed ingest throttle neither implements a scheduler nor runs during read-only stdio sessions (`audits/COMPLETION-PLAN-2026-09-03.md:99-108`). Delete the placeholder `src/sleep` implementation; only wire the existing lifecycle scheduler if background operation is an explicit requirement.

4. [BLOCKER] The DELETE list is not dependency-closed:

   - `query_router.py` is imported at HTTP module load and exposed through a getter (`src/mcp/http_server.py:45`, `src/mcp/http_server.py:338-345`). Seven integration tests instantiate it (`tests/integration/test_mcp_tools_e2e.py:450-589`).
   - `cytoscape_exporter.py` is exported by its package (`src/bridges/__init__.py:8-17`) and tested directly (`tests/integration/test_nexus_integration.py:24-100`).
   - `mode_aware_router.py` is exercised by `scripts/test_bead_implementations.py:21-28`.
   - `improvement_tools.py` is imported by `scripts/test_improve001_real_data.py:371-377`.
   - Telemetry has direct unit coverage (`tests/unit/test_namespace_router.py:3-34`).

   `src/__init__.py`, `conftest.py`, and both Dockerfiles add no equivalent imports (`src/__init__.py:1-16`, `conftest.py:1-7`, `Dockerfile:38-39`, `Dockerfile.railway:56`), but the HTTP/test/script callers above already disprove "zero callers, zero tests" (`audits/COMPLETION-PLAN-2026-09-03.md:116-133`).

5. [MAJOR] "Delete the six matching test files" is unsafe. `test_mcp_tools_e2e.py` contains a QueryRouter section inside a larger mixed integration file (`tests/integration/test_mcp_tools_e2e.py:450-589`), and `test_nexus_integration.py` similarly contains the Cytoscape tests inside a broader file (`tests/integration/test_nexus_integration.py:1-40`). A `grep -l` file list is not proof that an entire test file tests only deleted code, contrary to `audits/COMPLETION-PLAN-2026-09-03.md:132-133`.

6. [MAJOR] P1a omits a third Bayesian fake-success branch. A timeout or failed inference returning `None` still calls `_text_result` without `is_error=True` (`src/mcp/request_router.py:636-639`). An existing test explicitly requires the old false-success result (`tests/unit/test_request_router_handlers.py:120-131`). P1a only names the no-network and unknown-node branches (`audits/COMPLETION-PLAN-2026-09-03.md:50-57`).

7. [MAJOR] P1c cannot reliably detect "all tiers degraded." It records only vector and HippoRAG exceptions (`audits/COMPLETION-PLAN-2026-09-03.md:67-75`), while Bayesian errors return `None` separately (`src/nexus/tier_queries.py:188-193`). Worse, `_degraded_tiers` would be mutable request state on a singleton processor (`src/mcp/http_server.py:426-459`) used concurrently through worker threads (`src/mcp/http_server.py:577-579`). Degradation must travel in the request-local return value, not on `self`.

8. [MAJOR] P1b changes a wider contract than acknowledged. The method is `_run_command`, not `_run_bd` (`src/integrations/beads_bridge.py:282-310`), and timeout/generic-exception paths have no `stderr` suitable for the proposed constructor. The current unit test expects a nonzero CLI exit to return `[]` (`tests/unit/test_beads_bridge.py:55-68`). Stdio handlers will catch the new exception (`src/mcp/request_router.py:753-779`, `src/mcp/request_router.py:791-826`, `src/mcp/request_router.py:838-859`), but HTTP unified retrieval will still swallow it into `[]` (`src/routing/unified_router.py:65-82`) and report a successful response (`src/mcp/http_server.py:938-975`).

9. [BLOCKER] P2a does not produce one dispatch path. Canonical protocol dispatch already imports `request_router.handle_call_tool` directly (`src/mcp/protocol_handler.py:42-57`), so removing the stdio facade changes compatibility APIs rather than fixing canonical dispatch. Existing tests import and inspect that facade (`tests/unit/test_stdio_server.py:15-224`, `tests/integration/test_phase4_mcp_tools.py:94-138`). FastAPI routes remain independent wrappers (`src/mcp/http_server.py:757-905`), so "every tool call" remains false.

10. [BLOCKER] P2a's literal `trace.log()` writes to default `memory.db`, not `query_traces.db` (`src/debug/query_trace.py:172-185`). Existing code supplies the required database explicitly (`src/mcp/request_router.py:184-188`). `log()` also returns `False` rather than raising on SQLite errors (`src/debug/query_trace.py:229-235`), so a wrapper that ignores its return value can still report a trace was recorded.

11. [MAJOR] Phase ordering is wrong. P1d must precede P1c because the tier currently carries a two-signature `TypeError` adapter (`src/nexus/tier_queries.py:195-210`) and the lightweight result shape is incompatible with its consumer (`src/bayesian/lightweight_query_engine.py:38-65`, `src/nexus/tier_queries.py:154-186`). P0.2 and P3 both rewrite the same coverage threshold (`audits/COMPLETION-PLAN-2026-09-03.md:33-35`, `audits/COMPLETION-PLAN-2026-09-03.md:134-137`); lower-and-raise is double work. Tests are already runnable with `--no-cov`, as the plan itself proposes (`audits/COMPLETION-PLAN-2026-09-03.md:46-47`).

12. [MAJOR] P4 is incomplete. The same Loop, FrozenHarness, reflection, and three-day claims also appear outside both cited README ranges (`README.md:12-15`). The audited map lists additional false claims that the phase never resolves (`audits/SYSTEM-MAP-2026-09-03.md:100`). `check_docs.py` considers ten files current-facing (`scripts/check_docs.py:15-27`), while the plan edits only README, CURRENT, and one historical report (`audits/COMPLETION-PLAN-2026-09-03.md:139-149`). Checking that a line names an existing file cannot prove the described integration is wired.

13. [BLOCKER] Eight gate regexes contain literal ASCII backspace bytes instead of `\b`: `audits/GATES-2026-09-03.md:20`, `:25`, `:30`, `:35`, `:40`, `:45`, `:50`, and `:60`. They cannot match ordinary output as written.

14. [BLOCKER] P0-2 is fake-green. Pytest is piped into `grep`, so grep supplies the pipeline status, and the EXPECT only requires a `TOTAL` row (`audits/GATES-2026-09-03.md:8-10`). Coverage can print `TOTAL` and then fail the configured 40 percent threshold (`pytest.ini:10-13`).

15. [BLOCKER] P0-3 is both impossible and incomplete. Its recursive grep scans Markdown while the gate and plan themselves contain the searched filenames (`audits/GATES-2026-09-03.md:13-15`, `audits/COMPLETION-PLAN-2026-09-03.md:36-42`). It also tests the absence of only `gate0_verify.py`, `test_rlm_quick.py`, and `test_all_14_tools.py`, omitting the named `gate1_verify.py`, `gate2_verify.py`, and `gate4_verify.py` (`audits/GATES-2026-09-03.md:14`).

16. [MAJOR] P0-5 does not gate the declared baseline. It checks only the acceptance summary (`audits/GATES-2026-09-03.md:18-20`), omitting the no-coverage pytest count and both benchmark measurements required by the plan (`audits/COMPLETION-PLAN-2026-09-03.md:46-47`). Its `0 FAIL` text is not printed on an acceptance failure because the summary prints the actual failure count (`scripts/acceptance_all_parts.py:181-189`).

17. [MAJOR] The P1 gates are implementer-controlled assertion shells:

   - P1a can test only the two named branches and omit the `None` branch (`audits/GATES-2026-09-03.md:23-25`; `src/mcp/request_router.py:636-639`).
   - P1b does not require returncode, timeout, generic exception, all three stdio handlers, and HTTP behavior (`audits/GATES-2026-09-03.md:28-30`; `audits/COMPLETION-PLAN-2026-09-03.md:58-66`).
   - P1c can pass with only the proposed vector failure case, omitting HippoRAG, Bayesian, all-down, and concurrency (`audits/GATES-2026-09-03.md:33-35`; `audits/COMPLETION-PLAN-2026-09-03.md:73-75`).
   - P1d runs only lightweight despite the plan requiring both backends (`audits/GATES-2026-09-03.md:38-40`; `audits/COMPLETION-PLAN-2026-09-03.md:84-86`).

18. [MAJOR] The P2 gates are similarly weak. P2a may trace only the three calls named by the plan rather than all 18 registered tools or HTTP routes (`audits/GATES-2026-09-03.md:43-45`, `audits/COMPLETION-PLAN-2026-09-03.md:96-98`, `src/mcp/request_router.py:1032-1050`). P2b can pass without any implementation because ingestion already demotes and archives (`audits/GATES-2026-09-03.md:48-50`, `src/services/memory_ingestion_service.py:145-146`); it does not prove throttling, timestamp persistence, cleanup, or restart behavior.

19. [BLOCKER] P3a can pass after deleting only two targets. It checks `src/safety` and `visual_memory_tools.py`, not the rest of the DELETE list, and hardcodes 18 despite the plan demanding a harvested contract (`audits/GATES-2026-09-03.md:53-55`, `audits/COMPLETION-PLAN-2026-09-03.md:116-136`). Deleting `query_router.py` as planned also makes its own `import src.mcp.http_server` fail (`src/mcp/http_server.py:45`).

20. [BLOCKER] P3b hides pytest's exit code behind `tail` (`audits/GATES-2026-09-03.md:58-60`). Even after replacing the malformed backspaces with `\b`, a failure summary containing both "1 failed" and "1402 passed" satisfies the intended trailing `passed` expression; that exact mixed summary is already recorded (`audits/SYSTEM-MAP-2026-09-03.md:81-82`). It also allows tests to be deleted until one test passes, because no baseline count is asserted.

21. [MAJOR] P4 does not prove rejection. There is no planted stale claim or negative run (`audits/GATES-2026-09-03.md:63-65`). The current checker prints `OK: all current docs match code reality.` on success, not `DOCS_OK`, and prints violations on failure (`scripts/check_docs.py:96-105`). Changing only the success print could satisfy the gate without strengthening its semantics.

22. [MINOR] Several cited locations are inaccurate:

   - `test_rlm_quick.py:10-16` contains no `len(None)`; its environment initializes `projects`, `_index`, and `_by_project` as collections (`test_rlm_quick.py:10-16`, `src/rlm/rlm_codebase_env.py:378-387`).
   - The pgmpy public signature is at `src/bayesian/probabilistic_query_engine.py:61-66`; `:225-256` contains exception handling and result construction.
   - `src/mcp/http_server.py:470-472` constructs a bridge; it does not call `_run_command`.
   - The compact unified-search footer is at `src/mcp/request_router.py:676-683`, not line 683 alone.
   - P4's README ranges omit the duplicate stale block at `README.md:12-15`.

23. [BLOCKER] The worktree cannot run the gates on this machine as written. The plan creates a sibling Git worktree (`audits/COMPLETION-PLAN-2026-09-03.md:17-19`), but `venv-memory/` is ignored and therefore will not exist there (`.gitignore:23-27`, `.gitignore:79`), while every gate uses a worktree-relative `venv-memory/Scripts/python.exe` (`audits/GATES-2026-09-03.md:3`, `audits/GATES-2026-09-03.md:9-64`). On this host, Windows PowerShell 5.1 also cannot parse the plan's `&&` worktree command. Git Bash exists here, but the cross-model reverify command does not set the shell requirement declared only in prose (`audits/GATES-2026-09-03.md:4`, `audits/COMPLETION-PLAN-2026-09-03.md:161-163`).

24. [MAJOR] Local gates do not reproduce Railway. Both Docker images use Python 3.11 (`Dockerfile:2`, `Dockerfile.railway:4`), while this venv is Python 3.12. Railway excludes pgmpy and selects the lightweight path implicitly (`Dockerfile.railway:27-33`), yet no gate starts the HTTP server or image under that dependency set (`audits/GATES-2026-09-03.md:8-65`).

Corrected phase order:

1. Resolve owner requirements and every DEFER into KEEP, DELETE, or explicit handoff.
2. Rebuild portable, hermetic gates in the worktree and prove each can fail.
3. Fix Bayesian backend selection, signature, and result shape under both backends.
4. Fix all Bayesian and Beads false-success paths across stdio and HTTP.
5. Return request-local degradation state for all tiers; address decay ranking.
6. Decide tracing scope; preserve compatibility APIs and use the explicit trace DB.
7. Keep existing ingest maintenance; delete `src/sleep` unless background stdio scheduling is required.
8. Delete complete dependency closures, including exports and only targeted tests/scripts.
9. Synchronize every current-facing doc and add semantic negative controls.
10. Run full gates, Railway/HTTP smoke, then set the coverage ratchet once.

No files were changed, and no pytest or acceptance command was run.
