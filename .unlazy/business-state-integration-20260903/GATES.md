# Gates: GuardSpine business-state integration

Scope: preserve the completed Memory-MCP runtime while staging the reviewed cross-service access, ingestion, retention, and trace contract

- [x] M0: this governed integration ledger is tracked in the Memory-MCP repository
  CHECK: git ls-files --full-name --error-unmatch ":(top).unlazy/business-state-integration-20260903/GATES.md"
  EXPECT: .unlazy/business-state-integration-20260903/GATES.md
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=D:\Projects\memory-mcp-triple-system\.unlazy\business-state-integration-20260903; path=e9f5f2d8f323/78 entries; EXPECT=matched; output-sha256=65f842c32aff703562d3c4a01ed145b534deae74ad4ce3032b95225d338d24a6; output-bytes=53

## Required leaf 1.2.6 replacement

Before user inspection or approval, leaf 1.2.6 must replace this staging gate
with final runnable checks for all four integration surfaces:

- caller capability and namespace access;
- structured ingestion and the shared secret/personal-data filter;
- retention, deletion, disclosure budgets, and inbox/outbox recovery; and
- signed trace linkage between memory, telemetry, and evidence bundles.

Changing this ledger invalidates every earlier Unlazy approval and signed
configuration receipt for it. This staging ledger does not claim that any of
the four integration surfaces is implemented.
