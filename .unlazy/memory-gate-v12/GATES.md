# Gates: memory gate v12

Scope: globally enforce per-prompt recall and end-of-session save nudges without hook deadlocks or secret capture. The user-level hooks intentionally apply outside this repository; the one-shot edit nudge fails open when memory is unavailable.

- [ ] G0: this ledger states outcomes that can fail
  CHECK: node C:\Users\17175\.codex\skills\unlazy\scripts\gate-lint.mjs --strict D:\Projects\_crucible\memory-gate-v12\.unlazy\memory-gate-v12\GATES.md
  EXPECT: LINT OK
  EVIDENCE: pending

- [ ] G1: the hook state machines, redaction, session ids, health output, settings, and documentation satisfy the corrected contract
  CHECK: D:\Projects\memory-mcp-triple-system\venv-memory\Scripts\python.exe -m pytest -q --no-cov tests\integration\test_memory_gate_hooks.py tests\integration\test_observation_pipeline_wiring.py tests\integration\test_phase4_security.py
  EXPECT: 22 passed
  EVIDENCE: pending

- [ ] G2: hook logic and real processes remain within measured host budgets
  CHECK: D:\Projects\memory-mcp-triple-system\venv-memory\Scripts\python.exe scripts\verify_memory_gate_latency.py
  EXPECT: MEMORY HOOK LATENCY PASS
  EVIDENCE: pending

- [ ] G3: changed Python code passes Ruff
  CHECK: C:\Python312\python.exe -m ruff check src\hooks tests\integration scripts\verify_memory_gate_latency.py
  EXPECT: All checks passed!
  EVIDENCE: pending

- [ ] G4: changed Python code matches Black formatting
  CHECK: py -3.11 -m black --check src\hooks tests\integration scripts\verify_memory_gate_latency.py
  EXPECT: would be left unchanged
  EVIDENCE: pending

- [ ] G5: the full repository regression suite passes on the CPU-safe runtime
  CHECK: powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\_crucible\memory-gate-v12\.unlazy\memory-gate-v12\verify-full-suite.ps1
  EXPECT: MEMORY GATE FULL SUITE PASS
  EVIDENCE: pending

- [ ] G6: loaded Claude settings activate each hook exactly once and the live state machine recovers from its deliberate first denial
  CHECK: powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\_crucible\memory-gate-v12\.unlazy\memory-gate-v12\verify-live-hooks.ps1
  EXPECT: MEMORY GATE LIVE HOOKS PASS
  EVIDENCE: pending

- [ ] G7: the retained independent Claude Opus audit artifact records zero findings
  CHECK: powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\_crucible\memory-gate-v12\.unlazy\memory-gate-v12\verify-audit.ps1
  EXPECT: INDEPENDENT AUDIT ARTIFACT PASS
  EVIDENCE: pending
