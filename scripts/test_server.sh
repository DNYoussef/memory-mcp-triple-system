#!/bin/bash
# Test script for memory-mcp-triple-system MCP server
# Ensures proper environment configuration before startup

echo "Testing Memory MCP Triple System..."
echo ""

# Set environment variables
export PYTHONIOENCODING=utf-8
export HF_HOME=$HOME/.cache/huggingface
export ENVIRONMENT=development
export LOG_LEVEL=INFO

# Test imports first
echo "[1/3] Testing imports..."
python scripts/fix_imports.py
if [ $? -ne 0 ]; then
    echo "ERROR: Import test failed!"
    exit 1
fi

echo ""
echo "[2/3] Testing server module..."
python -c "import sys; sys.path.insert(0, '.'); from src.mcp.stdio_server import main; print('Server module loaded successfully')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: Server module import failed!"
    exit 1
fi

echo ""
echo "[3/3] Server ready to start"
echo ""
echo "To start the MCP server, run:"
echo "  python -m src.mcp.stdio_server"
echo ""
echo "Or use with Claude Code:"
echo "  claude mcp add memory-mcp python -m src.mcp.stdio_server"
echo ""
