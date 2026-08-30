$ErrorActionPreference = 'Stop'
$repo = 'D:\Projects\memory-mcp-triple-system'
Push-Location $repo
try {
    & 'C:\Python312\python.exe' -m ruff check src\hooks tests\integration\test_codex_memory_gate_hooks.py tests\unit\test_stdio_server.py .unlazy\memory-gate-codex\verify-codex-hook-config.py .unlazy\memory-gate-codex\verify-live-codex-hooks.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & py -3.11 -m black --check src\hooks tests\integration\test_codex_memory_gate_hooks.py tests\unit\test_stdio_server.py .unlazy\memory-gate-codex\verify-codex-hook-config.py .unlazy\memory-gate-codex\verify-live-codex-hooks.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output 'CODEX MEMORY GATE FORMAT PASS'
}
finally {
    Pop-Location
}
