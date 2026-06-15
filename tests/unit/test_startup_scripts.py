from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_http_startup_uses_commandline_process_detection_and_health_gate():
    script = _read("scripts/startup/start-memory-mcp.ps1")

    assert "Get-CimInstance Win32_Process" in script
    assert "src.mcp.http_server" in script
    assert "Test-MemoryMcpHealth" in script
    assert "already healthy" in script
    assert "already running but health check failed" in script
    assert "Warning: Could not verify server health" not in script


def test_tunnel_startup_requires_local_health_before_exposing_public_url():
    script = _read("scripts/startup/start-memory-tunnel.ps1")

    assert "Get-CimInstance Win32_Process" in script
    assert "Test-MemoryMcpHealth" in script
    assert "Refusing to start tunnel because Memory MCP server is not healthy" in script
    assert "starting tunnel anyway" not in script
    assert "Test-TunnelHealth" in script
    assert "Remove-Item -Path $TunnelUrlFile" in script


def test_tunnel_startup_uses_resolved_cloudflared_and_unique_output_file():
    script = _read("scripts/startup/start-memory-tunnel.ps1")

    assert '-FilePath $cloudflared.Source' in script
    assert "[System.IO.Path]::GetTempFileName()" in script
    assert 'Join-Path $env:TEMP "cloudflared-output.txt"' not in script


def test_batch_startup_runs_from_repo_root_not_scripts_directory():
    script = _read("scripts/start-http-server.bat")

    assert 'pushd "%~dp0.."' in script
    assert '"%~dp0..\\venv-memory\\Scripts\\python.exe"' in script
    assert 'cd /d "%~dp0"' not in script
