# Acceptance gate design

This is the required pre-probe reasoning pass. Each requirement is paired with
an oracle that a lazy or partial implementation can fail.

1. Runtime response truth
   - Oracle: a retained structural record from a real memory_store PostToolUse.
   - Failure mode caught: tests inventing a dict response that production never
     delivers.
   - Known limitation: no real business-failure payload was captured, so list
     responses fail open instead of using a text heuristic.
2. Session identity and handoff lifetime
   - Oracle: hermetic tests create two hook session ids and require distinct
     handoff files while observation ids remain internally generated.
   - Failure mode caught: fixed-file races, Stop cleanup, or conflating hook and
     observation session ids.
3. Structured redaction and live response fields
   - Oracle: a dict-valued tool_response with multiple secret keys, secret keys
     used as keys, auth headers, escaped quoted values, and secret tool input is
     captured through the real handler and read back from SQLite.
   - Failure mode caught: redacting after str(), reading stale tool_output first,
     unstable key placeholders, and leaving tool input unredacted.
4. Per-prompt recall nudge
   - Oracle: no marker fails open; marker without receipt denies exactly once;
     the retry fails open; a matching receipt allows immediately; a receipt for
     another marker does not satisfy the prompt.
   - Positive control: marker without receipt must emit the exact deny decision.
   - Failure mode caught: stale receipts, permanent denial loops, and vacuous
     fail-open tests.
5. Receipt and dirty/save state
   - Oracle: the real PostTool handler writes a receipt for retrieval, including
     a successful list response whose recalled text contains words such as
     error and failed; it does not write for a dict with isError true. Edit and
     memory_store calls independently update UTC timestamp keys.
   - Failure mode caught: the audited false-deny word heuristic, None fallback
     errors, and unchecked KVStore.set failures.
6. Stop behavior
   - Oracle: edit newer than save exits 2; save newer than edit passes; skip is
     consumed even when stop_hook_active is true; successful deletion advances
     last_save_at; failed deletion does not; summarization uses the internal id.
   - Positive control: the dirty state must block before the clean controls run.
   - Failure mode caught: unreachable waivers, replaying skips, swallowing the
     intended SystemExit, or summarizing under the wrong id.
7. Session-start and prompt injection health
   - Oracle: ARMED is present even with no prior context; missing DB and store
     errors emit DOWN; the script fallback emits only relevant prior activity
     and never writes gate receipts.
   - Failure mode caught: silent health absence or an injection hook that
     accidentally self-satisfies the gate.
8. Configuration and documentation
   - Oracle: JSON validation requires one registration for every hook in loaded
     user settings and zero duplicate hook blocks in home local settings. A live
     Claude debug run from the D-drive project must show the handlers executing.
   - Known-bad control: the pre-install D-drive debug trace found no memory hook.
   - Failure mode caught: JSON grep tests over files Claude does not load.
9. Regression and performance
   - Oracle: focused integration tests, the repository regression gate, Ruff and
     Black checks, plus a measured hook latency check against the documented
     budget or an explicit measured handoff if the existing runtime cannot meet
     it.
   - The measured budgets are under 100 ms for the new many-entry redaction
     logic and under 350 ms end to end for each process on this host. The latter
     includes the existing roughly 180 ms Python process startup floor.
   - Failure mode caught: a locally green state machine that breaks capture,
     summary storage, formatting, or materially increases hook startup cost.
10. Independent verification
   - Oracle: Codex reruns the ledger after the final edit; Claude Opus reruns the
     underlying checks and audits the diff and gate for theater.
   - Independence statement: author not in verifiers.
