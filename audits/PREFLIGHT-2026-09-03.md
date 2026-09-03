# Completion preflight - 2026-09-03

## Model identity and isolation

- Claude Code 2.1.259, requested `opus`, reported canonical model `claude-opus-5`.
- Claude canary: `CRUCIBLE_OPUS5_CANARY_20260903`.
- Gemini CLI 0.58.0, requested and reported main model `gemini-3.8-flash`.
- Gemini canary: `CRUCIBLE_GEMINI38FLASH_CANARY_20260903`.
- Both audits ran read-only and reported zero file additions and removals.
- Gemini made one denied read outside the isolated workspace and completed with its required canary.
- Gemini retried three quota responses and completed on the requested main model. Its internal loop
  detector used `gemini-3-flash-preview`; that utility model did not author the findings.

## Findings folded into plan v8

1. Delete only the Bayesian TypeError fallback, not its containing method.
2. Define lightweight Bayesian failure and helper-method parity.
3. Remove the complete vector trace block and isolate trace-write failures from tool results.
4. Preserve HTTP 503 through all three tri-tier routes, including unified retrieval.
5. Propagate unified-router degradation and Beads errors through the actual HTTP response.
6. Define absolute `src.*` import resolution in computed reachability.
7. Run edge-removing surgery before the authoritative dead-set report.
8. Derive deleted test nodeids from imports and mixed-test bodies, not the prose list.
9. Keep `MetadataSync`; it is import-live, publicly exported, tested, and currently documented.
10. Keep `CytoscapeExporter` as an explicit tested public compatibility root.
11. Remove additional computed-dead offline modules and their derived test closures.
12. Correct the phase5-tail surgery so it retains the GraphService import and no partial tests.
13. Benchmark `memory_store` directly in addition to `unified_search`.
14. Move `checkpoint_clean` evidence from the baseline gate to the Phase 3 gate.
15. Add lint and non-Python artifact checks to Phase 3.
16. Pin KV claim timestamp format and contention behavior; remove the unused service clock.
17. Make the embedding stub batch-aware.
18. Add the missed deployment-guide stale entrypoint to documentation cleanup.
19. Keep the coverage-ratchet comment outside pytest's multi-line `addopts` value.
20. Commit the copied audit inputs before Phase 0 so cleanliness assertions are meaningful.

No model finding overrides a red gate. Every accepted item above is represented in the plan or
ledger before product implementation starts.

## v8 convergence

Gemini 3.8 Flash returned PASS. Opus 5 found four blocking specification defects and two unowned
evidence paths. v9 corrects the Bayesian try unwrapping, request-router trace range, phase5-tail
line range, deleted-nodeid derivation, processor-exception degradation status, and checkpoint
evidence location. Gemini passed v9; Opus then found test-surgery orphaned imports that made the
lint gate unreachable. v10 applies the orphan-import sweep to every test surgery. Both auditors are
re-run against v10 before Phase 0 begins.

Final convergence: PASS from canonical `claude-opus-5` with canary
`OPUS5_V10_CONVERGENCE_COMPLETE_20260903`; PASS from `gemini-3.8-flash` with canary
`GEMINI38_V10_CONVERGENCE_COMPLETE_20260903`. Both runs were read-only.
