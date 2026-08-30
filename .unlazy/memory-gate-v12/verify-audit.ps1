$ErrorActionPreference = 'Stop'
$repo = 'D:\Projects\_crucible\memory-gate-v12'
$path = Join-Path $PSScriptRoot 'FINAL-AUDIT.md'
if (-not (Test-Path -LiteralPath $path)) { throw 'Final audit artifact is missing' }
$text = Get-Content -Raw -LiteralPath $path
$head = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve audited commit' }
foreach ($line in @(
    'VERDICT: PASS',
    'MODEL: claude-opus',
    'FINDINGS: 0',
    "COMMIT: $head",
    'CANARY: FINAL_AUDIT_COMPLETE'
)) {
    if ($text -notmatch [regex]::Escape($line)) { throw "Audit artifact lacks $line" }
}
$tracked = & git -C $repo status --porcelain --untracked-files=no
if ($LASTEXITCODE -ne 0 -or $tracked) { throw 'Tracked worktree differs from audited commit' }
Write-Output 'INDEPENDENT AUDIT ARTIFACT PASS'
