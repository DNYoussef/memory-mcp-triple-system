# Phase 2 audit finding trace

This ledger retains the thirteen findings from the first Phase 2 Claude Opus
audit so a later auditor can verify closure by identifier.

1. F1: PowerShell 5 did not support the string split expression used by the
   live verifier. Resolved with escaped regex match counts.
2. F2: A one-turn smoke could pass through the one-shot edit retry instead of a
   retrieval receipt. Resolved with two turns and an assertion that the current
   prompt has a receipt but no nudge key.
3. F3: The focused-test count was stale. Resolved to the collected 22 tests.
4. F4: PreToolUse trusted only the settings matcher. Resolved with an explicit
   edit-tool allowlist in the handler and a non-edit test.
5. F5: Stale receipt prompt scoping was not tested. Resolved by rotating the
   prompt marker and proving the old receipt does not allow an edit.
6. F6: The latency oracle missed deep work, wide input, active denial, and four
   hook processes. Resolved with deep and wide controls and all six processes.
7. F7: The audit artifact was self-certifying. Resolved by binding it to the
   current commit and rejecting tracked implementation differences.
8. F8: List-shaped MCP responses lack a reliable error bit. Retrieval remains
   fail-open; memory_store now requires the repository's fixed success prefix.
9. F9: Repository-only guidance did not cover global hooks. Resolved by making
   global CLAUDE.md deployment and verification part of the live gate.
10. F10: The deny message advertised the one-shot bypass. Resolved by removing
    the bypass instruction while retaining the anti-deadlock behavior.
11. F11: The Stop remedy omitted lazy tool loading. Resolved by naming
    ToolSearch before memory_store or kv_set.
12. F12: User settings create a global blast radius. This scope is intentional,
    documented, tested from the D-drive repository, and bounded by fail-open
    hook errors plus the one-shot edit nudge.
13. F13: Gate scripts relied on the caller's working directory and a fixed
    timestamp. Resolved with explicit repository location and dynamic UTC test
    timestamps.

The follow-up audit additionally found list-shaped failed saves, ambiguous Stop
wording, clean-session waiver consumption, ignored oracles, and a stale latency
docstring. Each was corrected before the Phase 2 commit.
