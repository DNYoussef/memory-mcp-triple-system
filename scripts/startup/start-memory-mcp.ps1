# Memory MCP HTTP Server Startup Script
# Starts the Memory MCP Triple System HTTP server on localhost:8080.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$PythonExe = Join-Path $RepoRoot "venv-memory\Scripts\python.exe"
$ClaudeHome = if ($env:CLAUDE_HOME) { $env:CLAUDE_HOME } else { Join-Path $env:USERPROFILE ".claude" }
$LogFile = Join-Path $ClaudeHome "logs\memory-mcp-server.log"
$HostValue = if ($env:MEMORY_MCP_HTTP_HOST) { $env:MEMORY_MCP_HTTP_HOST } else { "127.0.0.1" }
$PortValue = if ($env:MEMORY_MCP_HTTP_PORT) { $env:MEMORY_MCP_HTTP_PORT } else { "8080" }
$HealthUrl = "http://127.0.0.1:$PortValue/health"

function Test-MemoryMcpHealth {
    param([string]$Url)

    try {
        $response = Invoke-RestMethod -Uri $Url -TimeoutSec 2 -ErrorAction Stop
        return $response.status -eq "healthy"
    } catch {
        return $false
    }
}

function Wait-MemoryMcpHealth {
    param(
        [string]$Url,
        [int]$MaxWaitSeconds = 30
    )

    $waited = 0
    while ($waited -lt $MaxWaitSeconds) {
        if (Test-MemoryMcpHealth -Url $Url) {
            return $true
        }
        Start-Sleep -Seconds 2
        $waited += 2
    }
    return $false
}

function Get-MemoryMcpServerProcess {
    $processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" -ErrorAction SilentlyContinue
    return @($processes | Where-Object { $_.CommandLine -like "*src.mcp.http_server*" })
}

$LogDir = Split-Path $LogFile -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogFile -Value "[$timestamp] Starting Memory MCP HTTP Server..."

if (-not (Test-Path $PythonExe)) {
    Add-Content -Path $LogFile -Value "[$timestamp] ERROR: Python venv not found at $PythonExe"
    exit 1
}

if (Test-MemoryMcpHealth -Url $HealthUrl) {
    Add-Content -Path $LogFile -Value "[$timestamp] Memory MCP already healthy on $HealthUrl"
    exit 0
}

$existingProcess = Get-MemoryMcpServerProcess
if ($existingProcess) {
    $pids = $existingProcess.ProcessId -join ", "
    Add-Content -Path $LogFile -Value "[$timestamp] ERROR: Memory MCP already running but health check failed (PID: $pids)"
    exit 1
}

try {
    $env:MEMORY_MCP_HTTP_HOST = $HostValue
    $env:MEMORY_MCP_HTTP_PORT = $PortValue

    $process = Start-Process -FilePath $PythonExe -ArgumentList @(
        "-m",
        "src.mcp.http_server"
    ) -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru

    Add-Content -Path $LogFile -Value "[$timestamp] Started Memory MCP server (PID: $($process.Id))"

    if (Wait-MemoryMcpHealth -Url $HealthUrl -MaxWaitSeconds 30) {
        Add-Content -Path $LogFile -Value "[$timestamp] Memory MCP server verified healthy"
    } else {
        Add-Content -Path $LogFile -Value "[$timestamp] ERROR: Memory MCP server did not become healthy"
        exit 1
    }
} catch {
    Add-Content -Path $LogFile -Value "[$timestamp] ERROR: Failed to start Memory MCP: $_"
    exit 1
}
