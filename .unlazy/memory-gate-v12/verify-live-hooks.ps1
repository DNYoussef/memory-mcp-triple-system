$ErrorActionPreference = 'Stop'

$repo = 'D:\Projects\memory-mcp-triple-system'
$claude = 'C:\Users\17175\.local\bin\claude.exe'
$python = Join-Path $repo 'venv-memory\Scripts\python.exe'
$settingsPath = 'C:\Users\17175\.claude\settings.json'
$localPath = 'C:\Users\17175\.claude\settings.local.json'
$debug = Join-Path $env:TEMP ('memory-gate-live-' + [guid]::NewGuid() + '.log')
$smoke = Join-Path $env:TEMP ('memory-gate-live-' + [guid]::NewGuid() + '.txt')
$sessionId = [guid]::NewGuid().ToString()

Push-Location $repo
try {
    $settings = Get-Content -Raw -LiteralPath $settingsPath | ConvertFrom-Json
    if (-not $settings.hooks) { throw 'Loaded user settings have no hooks' }
    if (Test-Path -LiteralPath $localPath) {
        $local = Get-Content -Raw -LiteralPath $localPath | ConvertFrom-Json
        if ($local.hooks) { throw 'Home-local hooks would duplicate registration' }
    }

    $blob = ($settings.hooks | ConvertTo-Json -Depth 20).Replace('\', '/')
    foreach ($name in @(
        'session_start_handler.py',
        'prompt_marker_handler.py',
        'user_prompt_memory_handler.py',
        'pre_tool_memory_gate.py',
        'post_tool_handler.py',
        'stop_handler.py'
    )) {
        if ([regex]::Matches($blob, [regex]::Escape($name)).Count -ne 1) {
            throw "Expected one loaded registration for $name"
        }
    }
    $preGroups = @($settings.hooks.PreToolUse)
    $exactGate = @($preGroups | Where-Object {
        $_.matcher -eq 'Write|Edit|NotebookEdit' -and
        (($_.hooks | ConvertTo-Json -Depth 10) -match 'pre_tool_memory_gate.py')
    })
    if ($exactGate.Count -ne 1) { throw 'PreToolUse memory gate matcher is not exact' }

    $globalClaude = 'C:\Users\17175\.claude\CLAUDE.md'
    if (-not (Test-Path -LiteralPath $globalClaude)) { throw 'Global CLAUDE.md is missing' }
    if ((Get-Content -Raw -LiteralPath $globalClaude) -notmatch '## Memory recall and save nudges') {
        throw 'Global CLAUDE.md lacks memory gate guidance'
    }

    $firstPrompt = @"
Call mcp__memory-mcp__unified_search once with query memory gate first live turn.
Use no other tools, then reply exactly MEMORY_GATE_FIRST_TURN_DONE.
"@
    $output = & $claude -p $firstPrompt --model opus `
        --allowedTools 'mcp__memory-mcp__unified_search' `
        --session-id $sessionId --setting-sources 'user,project,local' `
        --debug hooks --debug-file $debug
    if ($LASTEXITCODE -ne 0 -or $output -notmatch 'MEMORY_GATE_FIRST_TURN_DONE') {
        throw 'Claude first live smoke turn failed'
    }

    $secondPrompt = @"
Perform this live hook smoke in exact order:
1. Call mcp__memory-mcp__unified_search with query memory gate second live turn.
2. Use Write once to create $smoke containing exactly MEMORY_GATE_LIVE_SMOKE.
3. Call mcp__memory-mcp__kv_set with key skip:$sessionId, value live smoke, ttl 86400.
Use no more tools, then reply exactly MEMORY_GATE_LIVE_SMOKE_DONE.
"@
    $output = & $claude -p $secondPrompt --model opus `
        --allowedTools 'Write,mcp__memory-mcp__unified_search,mcp__memory-mcp__kv_set' `
        --resume $sessionId --setting-sources 'user,project,local' `
        --debug hooks --debug-file $debug
    if ($LASTEXITCODE -ne 0 -or $output -notmatch 'MEMORY_GATE_LIVE_SMOKE_DONE') {
        throw 'Claude second live smoke turn failed'
    }
    if (-not (Test-Path -LiteralPath $smoke)) { throw 'PreToolUse recovery did not produce smoke file' }
    if ((Get-Content -Raw -LiteralPath $smoke).Trim() -ne 'MEMORY_GATE_LIVE_SMOKE') {
        throw 'Smoke file content mismatch'
    }

    $stateCheck = @"
from src.stores.kv_store import KVStore
s = KVStore(r'C:\Users\17175\.claude\memory-mcp-data\agent_kv.db')
marker = s.get('prompt_marker:$sessionId')
assert marker, 'missing prompt marker'
assert s.get('recall:${sessionId}:' + marker) == '1', 'missing matching receipt'
assert s.get('recall_nudge:${sessionId}:' + marker) is None, 'edit used one-shot bypass instead of receipt'
assert s.get('last_edit_at:$sessionId'), 'missing edit timestamp'
assert s.get('last_save_at:$sessionId'), 'missing skip-consumption save timestamp'
assert s.get('skip:$sessionId') is None, 'skip key was not consumed'
s.close()
print('LIVE STATE OK')
"@
    $state = & $python -c $stateCheck
    if ($LASTEXITCODE -ne 0 -or $state -notcontains 'LIVE STATE OK') {
        throw 'Live gate state verification failed'
    }
    Write-Output 'MEMORY GATE LIVE HOOKS PASS'
}
finally {
    if (Test-Path -LiteralPath $smoke) { Remove-Item -LiteralPath $smoke }
    if (Test-Path -LiteralPath $debug) { Remove-Item -LiteralPath $debug }
    Pop-Location
}
