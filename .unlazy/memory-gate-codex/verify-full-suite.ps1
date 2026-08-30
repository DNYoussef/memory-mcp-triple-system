$ErrorActionPreference = 'Stop'
$env:CUDA_VISIBLE_DEVICES = '-1'
$repo = 'D:\Projects\memory-mcp-triple-system'
Push-Location $repo
try {
    & 'D:\Projects\memory-mcp-triple-system\venv-memory\Scripts\python.exe' -m pytest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output 'CODEX MEMORY GATE FULL SUITE PASS'
}
finally {
    Pop-Location
}
