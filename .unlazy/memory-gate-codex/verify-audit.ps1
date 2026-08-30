$ErrorActionPreference = 'Stop'
$repo = 'D:\Projects\memory-mcp-triple-system'
$path = Join-Path $PSScriptRoot 'FINAL-AUDIT.md'
if (-not (Test-Path -LiteralPath $path)) { throw 'Final audit artifact is missing' }
$lines = Get-Content -LiteralPath $path
$head = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve audited commit' }
foreach ($line in @(
    'VERDICT: PASS',
    'MODEL: claude-opus',
    'FINDINGS: 0',
    "COMMIT: $head",
    'CANARY: FINAL_CODEX_AUDIT_COMPLETE'
)) {
    if ($lines -notcontains $line) { throw "Audit artifact lacks exact line: $line" }
}
$tracked = & git -C $repo status --porcelain --untracked-files=no -- . ':(exclude).unlazy/memory-gate-codex/GATES.md'
if ($LASTEXITCODE -ne 0 -or $tracked) { throw 'Tracked worktree differs from audited commit' }
Write-Output 'INDEPENDENT CODEX AUDIT ARTIFACT PASS'
