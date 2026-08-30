# Gates: Codex memory gate compatibility

Scope: make the existing Claude memory gate work through Codex lifecycle hooks
without duplicating the state machine or weakening Claude behavior. Codex edit
coverage is the native `apply_patch` event; shell-hidden writes are out of scope.

- [x] G0: this ledger states outcomes that can fail
  CHECK: node C:\Users\17175\.codex\skills\unlazy\scripts\gate-lint.mjs --strict D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex\GATES.md
  EXPECT: LINT OK
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex; path=02f36aa13f42/77 entries; EXPECT=matched; output-sha256=48630b7361dd44ee870917b12c3d19b9d7bdea738aaca16bb04d4cab83b772d2; output-bytes=8

- [x] G1: captured Codex payloads satisfy the edit, retrieval, save, and Stop contracts
  CHECK: D:\Projects\memory-mcp-triple-system\venv-memory\Scripts\python.exe -m pytest -q --no-cov D:\Projects\memory-mcp-triple-system\tests\integration\test_codex_memory_gate_hooks.py
  EXPECT: 3 passed
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex; path=02f36aa13f42/77 entries; EXPECT=matched; output-sha256=ea912e3193f761e925498f05ec4fdcff136f51f1a7b6a26bbb6439804d621bc7; output-bytes=1140

- [x] G2: the existing Claude memory gate contract remains green
  CHECK: D:\Projects\memory-mcp-triple-system\venv-memory\Scripts\python.exe -m pytest -q --no-cov D:\Projects\memory-mcp-triple-system\tests\integration\test_memory_gate_hooks.py D:\Projects\memory-mcp-triple-system\tests\integration\test_observation_pipeline_wiring.py D:\Projects\memory-mcp-triple-system\tests\integration\test_phase4_security.py
  EXPECT: 22 passed
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex; path=02f36aa13f42/77 entries; EXPECT=matched; output-sha256=f0f6da48dbb4f0d5bc526be0ed292d431a7abd4de5566d74424ba42135bb684a; output-bytes=5145

- [x] G3: changed Python code passes Ruff and Black
  CHECK: powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex\verify-format.ps1
  EXPECT: CODEX MEMORY GATE FORMAT PASS
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex; path=02f36aa13f42/77 entries; EXPECT=matched; output-sha256=49a8a9c75a90e004c4e7a270916a1ef3db9c45e27825d37c5c1af8f30ed312b9; output-bytes=122

- [x] G4: the installed Codex hooks match the reviewed template, are loaded exactly once, and are trusted at their current hashes
  CHECK: D:\Projects\memory-mcp-triple-system\venv-memory\Scripts\python.exe D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex\verify-codex-hook-config.py
  EXPECT: CODEX MEMORY HOOK CONFIG PASS
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex; path=02f36aa13f42/77 entries; EXPECT=matched; output-sha256=383fdcd4ff7564eb2fc8775b381683fb08f934ccb36aec9a823bcc9fc9030de4; output-bytes=31

- [x] G5: real Codex runs observe the first denial, retrieval credit, edit timestamp, and Stop recovery
  CHECK: D:\Projects\memory-mcp-triple-system\venv-memory\Scripts\python.exe D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex\verify-live-codex-hooks.py
  EXPECT: CODEX MEMORY GATE LIVE PASS
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex; path=02f36aa13f42/77 entries; EXPECT=matched; output-sha256=028434ba01e5548a6dd8329f643457f469ee0e59c0b0dce927a39f030559643c; output-bytes=29

- [x] G6: the full repository regression suite passes on the CPU-safe runtime
  CHECK: powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex\verify-full-suite.ps1
  EXPECT: CODEX MEMORY GATE FULL SUITE PASS
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex; path=02f36aa13f42/77 entries; EXPECT=matched; output-sha256=5314a9e5ee73a74466805dcd9b4552ec07fa4b77603123c94a1eab95e6cfbdb4; output-bytes=226459

- [x] G7: the session-local audit artifact has exact PASS, model, zero-findings, current-commit, and canary lines
  CHECK: powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex\verify-audit.ps1
  EXPECT: INDEPENDENT CODEX AUDIT ARTIFACT PASS
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=D:\Projects\memory-mcp-triple-system\.unlazy\memory-gate-codex; path=02f36aa13f42/77 entries; EXPECT=matched; output-sha256=49ef584e26fd331dfa5b557f8032726fbef947e9a1e0df5fe3191bce58da1695; output-bytes=39
