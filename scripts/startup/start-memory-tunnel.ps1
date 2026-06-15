# Cloudflare Tunnel for Memory MCP
# Creates an opt-in quick tunnel to expose Memory MCP on port 8080.

$ErrorActionPreference = "Stop"

$ClaudeHome = if ($env:CLAUDE_HOME) { $env:CLAUDE_HOME } else { Join-Path $env:USERPROFILE ".claude" }
$LogFile = Join-Path $ClaudeHome "logs\memory-tunnel.log"
$TunnelUrlFile = Join-Path $ClaudeHome "runtime\memory-mcp-tunnel-url.txt"

$LogDir = Split-Path $LogFile -Parent
$RuntimeDir = Split-Path $TunnelUrlFile -Parent
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
if (-not (Test-Path $RuntimeDir)) { New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogFile -Value "[$timestamp] Starting Cloudflare tunnel for Memory MCP..."

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

function Test-TunnelHealth {
    param([string]$TunnelUrl)

    try {
        $healthUrl = "$($TunnelUrl.TrimEnd('/'))/health"
        $response = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 5 -ErrorAction Stop
        return $response.status -eq "healthy"
    } catch {
        return $false
    }
}

function Wait-TunnelHealth {
    param(
        [string]$TunnelUrl,
        [int]$MaxWaitSeconds = 30
    )

    $waited = 0
    while ($waited -lt $MaxWaitSeconds) {
        if (Test-TunnelHealth -TunnelUrl $TunnelUrl) {
            return $true
        }
        Start-Sleep -Seconds 2
        $waited += 2
    }
    return $false
}

function Get-MemoryMcpTunnelProcess {
    param([string]$Port)

    $needle = "http://localhost:$Port"
    $processes = Get-CimInstance Win32_Process -Filter "Name LIKE 'cloudflared%'" -ErrorAction SilentlyContinue
    return @($processes | Where-Object { $_.CommandLine -like "*$needle*" })
}

if ($env:MEMORY_MCP_ENABLE_PUBLIC_TUNNEL -ne "true") {
    Add-Content -Path $LogFile -Value "[$timestamp] Public tunnel disabled. Set MEMORY_MCP_ENABLE_PUBLIC_TUNNEL=true to enable."
    exit 0
}

if (-not $env:MCP_API_KEY -and -not $env:MEMORY_MCP_API_KEY) {
    Add-Content -Path $LogFile -Value "[$timestamp] ERROR: Refusing public tunnel without MCP_API_KEY or MEMORY_MCP_API_KEY"
    exit 1
}

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    Add-Content -Path $LogFile -Value "[$timestamp] ERROR: cloudflared not found in PATH"
    exit 1
}

$PortValue = if ($env:MEMORY_MCP_HTTP_PORT) { $env:MEMORY_MCP_HTTP_PORT } else { "8080" }
$HealthUrl = "http://127.0.0.1:$PortValue/health"

$existingTunnel = Get-MemoryMcpTunnelProcess -Port $PortValue

if ($existingTunnel) {
    $pids = $existingTunnel.ProcessId -join ", "
    Add-Content -Path $LogFile -Value "[$timestamp] Tunnel already running (PID: $pids)"

    if (Test-Path $TunnelUrlFile) {
        $url = (Get-Content $TunnelUrlFile -Raw).Trim()
        if ($url -and (Test-TunnelHealth -TunnelUrl $url)) {
            Add-Content -Path $LogFile -Value "[$timestamp] Existing tunnel URL verified: $url"
            Write-Host "Memory MCP Tunnel: $url"
            exit 0
        }

        Add-Content -Path $LogFile -Value "[$timestamp] Existing tunnel URL is missing or unhealthy; removing stale URL file"
        Remove-Item -Path $TunnelUrlFile -Force -ErrorAction SilentlyContinue
    }

    Add-Content -Path $LogFile -Value "[$timestamp] ERROR: Tunnel process exists but no healthy URL is available; not starting a duplicate"
    exit 1
}

if (Wait-MemoryMcpHealth -Url $HealthUrl -MaxWaitSeconds 30) {
    Add-Content -Path $LogFile -Value "[$timestamp] Memory MCP server is healthy"
} else {
    Add-Content -Path $LogFile -Value "[$timestamp] ERROR: Refusing to start tunnel because Memory MCP server is not healthy"
    exit 1
}

$tunnelOutput = [System.IO.Path]::GetTempFileName()
$process = Start-Process -FilePath $cloudflared.Source -ArgumentList @(
    "tunnel",
    "--url", "http://localhost:$PortValue"
) -RedirectStandardError $tunnelOutput -WindowStyle Hidden -PassThru

Add-Content -Path $LogFile -Value "[$timestamp] Started cloudflared (PID: $($process.Id))"

$tunnelUrl = $null
$waited = 0
while ($waited -lt 45 -and -not $tunnelUrl) {
    Start-Sleep -Seconds 2
    $waited += 2
    $output = Get-Content $tunnelOutput -Raw
    $match = [regex]::Match($output, 'https://[a-z0-9-]+\.trycloudflare\.com')
    if ($match.Success) {
        $tunnelUrl = $match.Value
    }
}

if (-not $tunnelUrl) {
    Add-Content -Path $LogFile -Value "[$timestamp] ERROR: Could not parse tunnel URL from cloudflared output"
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

if (-not (Wait-TunnelHealth -TunnelUrl $tunnelUrl -MaxWaitSeconds 30)) {
    Add-Content -Path $LogFile -Value "[$timestamp] ERROR: Tunnel URL did not pass health check: $tunnelUrl"
    Remove-Item -Path $TunnelUrlFile -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

Set-Content -Path $TunnelUrlFile -Value $tunnelUrl
Add-Content -Path $LogFile -Value "[$timestamp] Tunnel URL verified: $tunnelUrl"
Write-Host "Memory MCP Tunnel: $tunnelUrl"
Add-Content -Path $LogFile -Value "[$timestamp] Tunnel startup complete"
