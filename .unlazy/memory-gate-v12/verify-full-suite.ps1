$ErrorActionPreference = 'Stop'
$env:CUDA_VISIBLE_DEVICES = '-1'
$repo = 'D:\Projects\_crucible\memory-gate-v12'
Push-Location $repo
try {
    & 'D:\Projects\memory-mcp-triple-system\venv-memory\Scripts\python.exe' -m pytest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output 'MEMORY GATE FULL SUITE PASS'
}
finally {
    Pop-Location
}
