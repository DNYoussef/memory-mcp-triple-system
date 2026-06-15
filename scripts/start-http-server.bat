@echo off
REM Start Memory MCP HTTP Server for Terminal Manager integration
echo Starting Memory MCP HTTP Server...
pushd "%~dp0.."
set PYTHONIOENCODING=utf-8
set MEMORY_MCP_HTTP_HOST=127.0.0.1
set MEMORY_MCP_HTTP_PORT=8080
set CHROMA_PERSIST_DIR=./chroma_data
chcp 65001 >nul 2>&1
"%~dp0..\venv-memory\Scripts\python.exe" -m src.mcp.http_server
popd
pause
