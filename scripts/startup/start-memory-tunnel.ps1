# Cloudflare Tunnel for Memory MCP
# Creates an opt-in quick tunnel to expose Memory MCP on port 8080.

$ErrorActionPreference = "Continue"

$ClaudeHome = if ($env:CLAUDE_HOME) { $env:CLAUDE_HOME } else { Join-Path $env:USERPROFILE ".claude" }
$LogFile = Join-Path $ClaudeHome "logs\memory-tunnel.log"
$TunnelUrlFile = Join-Path $ClaudeHome "runtime\memory-mcp-tunnel-url.txt"

$LogDir = Split-Path $LogFile -Parent
$RuntimeDir = Split-Path $TunnelUrlFile -Parent
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
if (-not (Test-Path $RuntimeDir)) { New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogFile -Value "[$timestamp] Starting Cloudflare tunnel for Memory MCP..."

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

$existingTunnel = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*$PortValue*"
}

if ($existingTunnel) {
    Add-Content -Path $LogFile -Value "[$timestamp] Tunnel already running (PID: $($existingTunnel.Id))"

    if (Test-Path $TunnelUrlFile) {
        $url = Get-Content $TunnelUrlFile -Raw
        Add-Content -Path $LogFile -Value "[$timestamp] Existing tunnel URL: $url"
    }
    exit 0
}

$maxWait = 30
$waited = 0
while ($waited -lt $maxWait) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:$PortValue/health" -TimeoutSec 2
        if ($response.status -eq "healthy") {
            Add-Content -Path $LogFile -Value "[$timestamp] Memory MCP server is healthy"
            break
        }
    } catch {
        Start-Sleep -Seconds 2
        $waited += 2
    }
}

if ($waited -ge $maxWait) {
    Add-Content -Path $LogFile -Value "[$timestamp] WARNING: Memory MCP server not responding, starting tunnel anyway"
}

$tunnelOutput = Join-Path $env:TEMP "cloudflared-output.txt"
$process = Start-Process -FilePath "cloudflared" -ArgumentList @(
    "tunnel",
    "--url", "http://localhost:$PortValue"
) -RedirectStandardError $tunnelOutput -WindowStyle Hidden -PassThru

Add-Content -Path $LogFile -Value "[$timestamp] Started cloudflared (PID: $($process.Id))"

Start-Sleep -Seconds 10

if (Test-Path $tunnelOutput) {
    $output = Get-Content $tunnelOutput -Raw
    $match = [regex]::Match($output, 'https://[a-z0-9-]+\.trycloudflare\.com')
    if ($match.Success) {
        $tunnelUrl = $match.Value
        Set-Content -Path $TunnelUrlFile -Value $tunnelUrl
        Add-Content -Path $LogFile -Value "[$timestamp] Tunnel URL: $tunnelUrl"

        Write-Host "Memory MCP Tunnel: $tunnelUrl"
    } else {
        Add-Content -Path $LogFile -Value "[$timestamp] Could not parse tunnel URL from output"
    }
}

Add-Content -Path $LogFile -Value "[$timestamp] Tunnel startup complete"
