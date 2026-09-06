# GATES: memory-mcp bayesian_inference + beads database (2026-09-06)

Unit of delivery: both broken MCP tools return real results from a fresh server process.

- [x] G1: bd from a neutral cwd with the User-scope BEADS_DIR returns the seeded canary issue
  CHECK: cd /tmp && export BEADS_DIR="$(powershell -NoProfile -c "[Environment]::GetEnvironmentVariable('BEADS_DIR','User')")" && echo "BEADS_DIR=$BEADS_DIR" && /c/Users/17175/AppData/Local/beads/bd.exe list --json | grep -c '"id": "mem-0rn"'
  EXPECT: 1
  CWD: ..
  EVIDENCE: exit=0; shell=C:\Program Files\Git\bin\bash.exe; cwd=D:\Projects\memory-mcp-triple-system; path=53ab4bbfb421/90 entries; EXPECT=matched; output-sha256=75ce2756cf455eee35c31cf754c257fa326ab79ffd5bd811183695edaf1d3343; output-bytes=129

- [x] G2: memory-mcp launch env in claude.json carries BEADS_DIR so /mcp reconnect works without a terminal restart
  CHECK: python -c "import json,os;e=json.load(open(r'C:/Users/17175/.claude.json',encoding='utf-8'))['mcpServers']['memory-mcp']['env'];d=e.get('BEADS_DIR','');print('BEADS_ENV_'+('PRESENT' if os.path.isfile(os.path.join(d,'beads.db')) else 'ABSENT'))"
  EXPECT: BEADS_ENV_PRESENT
  CWD: ..
  EVIDENCE: exit=0; shell=C:\Program Files\Git\bin\bash.exe; cwd=D:\Projects\memory-mcp-triple-system; path=53ab4bbfb421/90 entries; EXPECT=matched; output-sha256=16e221dd994e87b2b665b0b1618e77b91795396fd7ccf53862bcf9bdf1dd916c; output-bytes=19

- [x] G3: handler drops non-node evidence, coerces bools, reports ignored keys (fail-first tests, seen red before the fix)
  CHECK: ./venv-memory/Scripts/python.exe -m pytest tests/unit/test_request_router_handlers.py -q -k evidence --no-cov -p no:cacheprovider
  EXPECT: 2 passed
  CWD: ..
  EVIDENCE: exit=0; shell=C:\Program Files\Git\bin\bash.exe; cwd=D:\Projects\memory-mcp-triple-system; path=53ab4bbfb421/90 entries; EXPECT=matched; output-sha256=dac06e20c51ec4500901c6d2cc7af953ef1110141b7e57d673515ab3d89ec905; output-bytes=698

- [x] G4: router + bayesian unit suites have no regression
  CHECK: ./venv-memory/Scripts/python.exe -m pytest tests/unit/test_request_router_handlers.py tests/unit/test_bayesian_inference_cache.py tests/unit/test_bayesian_network_builder.py tests/unit/test_bayesian_background_build.py tests/unit/test_bayesian_evidence_e2e.py -q --no-cov -p no:cacheprovider; echo PYTEST_EXIT=$?
  EXPECT: PYTEST_EXIT=0
  CWD: ..
  EVIDENCE: exit=0; shell=C:\Program Files\Git\bin\bash.exe; cwd=D:\Projects\memory-mcp-triple-system; path=53ab4bbfb421/90 entries; EXPECT=matched; output-sha256=76edde1b0a863123cc1d5bf79fcb6a9719e260a8f11c23024c945dcd202df159; output-bytes=1008

- [x] G5: real NetworkBuilder + pgmpy engine + handler (no mocks): bogus key and bool evidence still yield probabilities, and a positive control proves the raw engine still rejects the bogus key
  CHECK: ./venv-memory/Scripts/python.exe -m pytest tests/unit/test_bayesian_evidence_e2e.py -q --no-cov -p no:cacheprovider; echo E2E_EXIT=$?
  EXPECT: E2E_EXIT=0
  CWD: ..
  EVIDENCE: exit=0; shell=C:\Program Files\Git\bin\bash.exe; cwd=D:\Projects\memory-mcp-triple-system; path=53ab4bbfb421/90 entries; EXPECT=matched; output-sha256=e962df6e325b70271f4cf61fab8439832fa9132913a50e9dee35adea53092870; output-bytes=680

- [x] G6: a FRESH stdio server process (launched with the claude.json env) answers bayesian_inference and beads_ready_tasks without isError
  CHECK: ./venv-memory/Scripts/python.exe "C:/Users/17175/AppData/Local/Temp/claude/C--Users-17175/3d5526a7-28c3-48e8-83f0-e7148d4f105a/scratchpad/fresh_server_probe.py"
  EXPECT: FRESH_SERVER_OK
  CWD: ..
  EVIDENCE: exit=0; shell=C:\Program Files\Git\bin\bash.exe; cwd=D:\Projects\memory-mcp-triple-system; path=53ab4bbfb421/90 entries; EXPECT=matched; output-sha256=f54cef2a52f06ca5a79259a8e7f52f79f97b289aca16a2645acde2e83ae6f338; output-bytes=342
