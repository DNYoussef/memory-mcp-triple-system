# Memory MCP HTTP Server Startup Script
# Starts the Memory MCP Triple System HTTP server on localhost:8080.

$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$VenvPath = Join-Path $RepoRoot "venv-memory\Scripts\Activate.ps1"
$ClaudeHome = if ($env:CLAUDE_HOME) { $env:CLAUDE_HOME } else { Join-Path $env:USERPROFILE ".claude" }
$LogFile = Join-Path $ClaudeHome "logs\memory-mcp-server.log"

$LogDir = Split-Path $LogFile -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogFile -Value "[$timestamp] Starting Memory MCP HTTP Server..."

$existingProcess = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*src.mcp.http_server*" -or $_.MainWindowTitle -like "*memory*"
}

if ($existingProcess) {
    Add-Content -Path $LogFile -Value "[$timestamp] Memory MCP already running (PID: $($existingProcess.Id))"
    exit 0
}

$HostValue = if ($env:MEMORY_MCP_HTTP_HOST) { $env:MEMORY_MCP_HTTP_HOST } else { "127.0.0.1" }
$PortValue = if ($env:MEMORY_MCP_HTTP_PORT) { $env:MEMORY_MCP_HTTP_PORT } else { "8080" }

try {
    Push-Location $RepoRoot

    $process = Start-Process -FilePath "powershell" -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "& { Set-Location '$RepoRoot'; & '$VenvPath'; `$env:MEMORY_MCP_HTTP_HOST='$HostValue'; `$env:MEMORY_MCP_HTTP_PORT='$PortValue'; python -m src.mcp.http_server }"
    ) -WindowStyle Hidden -PassThru

    Pop-Location

    Add-Content -Path $LogFile -Value "[$timestamp] Started Memory MCP server (PID: $($process.Id))"

    Start-Sleep -Seconds 5

    try {
        $response = Invoke-RestMethod -Uri "http://localhost:$PortValue/health" -TimeoutSec 5
        if ($response.status -eq "healthy") {
            Add-Content -Path $LogFile -Value "[$timestamp] Memory MCP server verified healthy"
        }
    } catch {
        Add-Content -Path $LogFile -Value "[$timestamp] Warning: Could not verify server health"
    }
} catch {
    Add-Content -Path $LogFile -Value "[$timestamp] ERROR: Failed to start Memory MCP: $_"
    exit 1
}
