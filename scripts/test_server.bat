@echo off
REM Test script for memory-mcp-triple-system MCP server
REM Ensures proper environment configuration before startup

echo Testing Memory MCP Triple System...
echo.

REM Set environment variables
set PYTHONIOENCODING=utf-8
REM Use standard HuggingFace cache location (portable)
if not defined HF_HOME set HF_HOME=%USERPROFILE%\.cache\huggingface
set ENVIRONMENT=development
set LOG_LEVEL=INFO

REM Test imports first
echo [1/3] Testing imports...
python scripts\fix_imports.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Import test failed!
    exit /b 1
)

echo.
echo [2/3] Testing server module...
python -c "import sys; sys.path.insert(0, '.'); from src.mcp.stdio_server import main; print('Server module loaded successfully')" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Server module import failed!
    exit /b 1
)

echo.
echo [3/3] Server ready to start
echo.
echo To start the MCP server, run:
echo   python -m src.mcp.stdio_server
echo.
echo Or use with Claude Code:
echo   claude mcp add memory-mcp python -m src.mcp.stdio_server
echo.
