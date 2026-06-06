# Connascence Scan Summary

- Project: `memory-mcp-triple-system`
- Path: `D:\Projects\memory-mcp-triple-system`
- Git branch: `main`
- Git commit: `46c5f0f5c561ef7eda26d65fe65e2882553e1234`
- Dirty before scan: `True`
- Scan succeeded: `True`
- Python files staged: `398`

## Commands Run
- `C:\Python312\python.exe -m analyzer C:\Users\17175\Desktop\_SCRATCH\connascence-portfolio-scan-2026-06-06\raw-results\memory-mcp-triple-system\mirror --format json --output C:\Users\17175\Desktop\_SCRATCH\connascence-portfolio-scan-2026-06-06\raw-results\memory-mcp-triple-system\connascence.raw.json --no-duplication --compliance-threshold 0 --max-god-objects 999999` (exit 0)
- `connascence_portfolio_runner.py generate-sarif-from-json D:\Projects\memory-mcp-triple-system\docs\connascence\scan-2026-06-06\connascence.json` (exit 0)
- `C:\Python312\python.exe -m analyzer.ast_engine --path C:\Users\17175\Desktop\_SCRATCH\connascence-portfolio-scan-2026-06-06\raw-results\memory-mcp-triple-system\mirror --analyzer god_object --output C:\Users\17175\Desktop\_SCRATCH\connascence-portfolio-scan-2026-06-06\raw-results\memory-mcp-triple-system\god-object.raw.json` (exit 0)

## Counts By Severity

- low: 16099
- medium: 1443
- critical: 90
- high: 76

## Counts By Type

- connascence_of_meaning: 14508
- CoV: 1438
- connascence_of_convention: 687
- CoP: 335
- connascence_of_execution: 296
- connascence_of_type: 178
- connascence_of_algorithm: 125
- god_object: 84
- connascence_of_timing: 35
- CoA: 21
- connascence_of_identity: 1

## Top Files

- `D:\Projects\memory-mcp-triple-system\src\mcp\request_router.py`: 545
- `D:\Projects\memory-mcp-triple-system\src\mcp\tools\beads_tools.py`: 347
- `D:\Projects\memory-mcp-triple-system\src\mcp\tool_registry.py`: 328
- `D:\Projects\memory-mcp-triple-system\src\mcp\tools\improvement_tools.py`: 304
- `D:\Projects\memory-mcp-triple-system\scripts\populate_knowledge_base.py`: 303
- `D:\Projects\memory-mcp-triple-system\src\mcp\tools\confidence_tools.py`: 301
- `D:\Projects\memory-mcp-triple-system\scripts\ingest_complete_system_knowledge.py`: 288
- `D:\Projects\memory-mcp-triple-system\src\validation\quality_validator.py`: 279
- `D:\Projects\memory-mcp-triple-system\src\mcp\http_server.py`: 257
- `D:\Projects\memory-mcp-triple-system\scripts\audit_memory.py`: 251

## Top 10 Actionable Findings

1. `D:\Projects\memory-mcp-triple-system\src\woundhealer\woundhealer_core.py:164` - Class 'WoundHealer' is a God Object (config context): Very low cohesion (0.16)
2. `D:\Projects\memory-mcp-triple-system\src\woundhealer\rlm_client.py:126` - Class 'RLMClient' is a God Object (config context): Very low cohesion (0.15)
3. `D:\Projects\memory-mcp-triple-system\src\validation\spec_validation.py:930` - Class 'ImplementationPlanValidator' is a God Object (test context): Very low cohesion (0.29)
4. `D:\Projects\memory-mcp-triple-system\src\validation\quality_validator.py:297` - Class 'QualityValidator' is a God Object: 21 methods, ~565 lines
5. `D:\Projects\memory-mcp-triple-system\src\stores\kv_store.py:22` - Class 'KVStore' is a God Object (config context): Very low cohesion (0.21)
6. `D:\Projects\memory-mcp-triple-system\src\stores\event_log.py:32` - Class 'EventLog' is a God Object (config context): Very low cohesion (0.39)
7. `D:\Projects\memory-mcp-triple-system\src\sleep\consolidation_scheduler.py:75` - Class 'ConsolidationScheduler' is a God Object (config context): Very low cohesion (0.25)
8. `D:\Projects\memory-mcp-triple-system\src\sleep\activity_monitor.py:49` - Class 'ActivityMonitor' is a God Object (config context): Very low cohesion (0.29)
9. `D:\Projects\memory-mcp-triple-system\src\services\weekly_review\weekly_coordinator.py:50` - Class 'WeeklyReviewCoordinator' is a God Object (api_controller context): Very low cohesion (0.21)
10. `D:\Projects\memory-mcp-triple-system\src\services\weekly_review\usage_aggregator.py:29` - Class 'UsageAggregator' is a God Object (config context): Very low cohesion (0.28)

## Tool Limitations

- Connascence currently analyzes Python files only; non-Python coupling is not covered.
- Source-bearing fields and literal values were stripped or redacted before writing artifacts.
- Excluded directories and sensitive data patterns were not staged into the scan mirror.

## Next Cleanup Recommendations

### 1. Quick Wins
- Add type annotations at public function boundaries with the highest CoT counts.
- Replace repeated or magic literals with named constants or configuration keys.

### 2. Medium Refactors
- Convert high-parameter functions to keyword-only APIs or parameter objects.
- Split complex functions and consolidate duplicated algorithmic branches.
- Start with the top files by violation count and keep each change behavior-preserving.

### 3. Large Architectural Work
- Split god objects into cohesive classes around stable domain responsibilities.
- Use module or service boundaries to isolate recurring high-count hotspots.
