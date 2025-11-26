@echo off
REM Start Memory MCP HTTP Server for Terminal Manager integration
echo Starting Memory MCP HTTP Server...
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set MEMORY_MCP_HTTP_HOST=0.0.0.0
set MEMORY_MCP_HTTP_PORT=8080
set CHROMA_PERSIST_DIR=./chroma_data
chcp 65001 >nul 2>&1
"%~dp0venv-memory\Scripts\python.exe" -m src.mcp.http_server
pause
