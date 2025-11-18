# Quick Start - Memory MCP Triple System

## ✅ Import Errors Fixed!

All import errors have been resolved. The system is ready for production use.

---

## Prerequisites

- Python 3.12
- All dependencies installed: `pip install -r requirements.txt`

---

## Verification

Run the diagnostic script to verify everything works:

```bash
cd C:\Users\17175\Desktop\memory-mcp-triple-system
python scripts/fix_imports.py
```

Expected output:
```
Testing imports for memory-mcp-triple-system...

============================================================
IMPORT TEST RESULTS
============================================================
✓ numpy                          1.26.4
✓ transformers                   4.45.0.dev0
✓ sentence_transformers          5.1.1
✓ EmbeddingPipeline              OK
✓ stdio_server                   OK
✓ chromadb                       1.0.20
✓ Python encoding                utf-8
============================================================

✅ All imports successful!
```

---

## Starting the MCP Server

### Option 1: Direct Python
```bash
cd C:\Users\17175\Desktop\memory-mcp-triple-system
set PYTHONIOENCODING=utf-8
set HF_HOME=C:\Users\17175\.cache\huggingface
python -m src.mcp.stdio_server
```

### Option 2: With Claude Code
```bash
claude mcp add memory-mcp python -m src.mcp.stdio_server --cwd C:\Users\17175\Desktop\memory-mcp-triple-system
```

### Option 3: Using .env file
The `.env` file already contains the required environment variables:
```bash
cd C:\Users\17175\Desktop\memory-mcp-triple-system
python -m src.mcp.stdio_server
```

---

## Environment Variables

The following environment variables are configured in `.env`:

- `PYTHONIOENCODING=utf-8` - Fixes Windows Unicode encoding issues
- `HF_HOME=C:\Users\17175\.cache\huggingface` - Sets HuggingFace cache location
- `ENVIRONMENT=development` - Development mode
- `LOG_LEVEL=INFO` - Logging level

---

## Testing the Server

### 1. Test Vector Search
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "vector_search",
    "arguments": {
      "query": "machine learning",
      "limit": 5
    }
  }
}
```

### 2. Test Memory Store
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "memory_store",
    "arguments": {
      "text": "Important information to remember",
      "metadata": {
        "key": "test_memory",
        "category": "testing"
      }
    }
  }
}
```

---

## Troubleshooting

### Import Errors
Run the diagnostic script:
```bash
python scripts/fix_imports.py
```

### Unicode Errors
Ensure `PYTHONIOENCODING=utf-8` is set:
```bash
set PYTHONIOENCODING=utf-8  # Windows
export PYTHONIOENCODING=utf-8  # Linux/Mac
```

### Module Not Found
Ensure you're in the project root:
```bash
cd C:\Users\17175\Desktop\memory-mcp-triple-system
```

### Transformers Warning
The FutureWarning about `TRANSFORMERS_CACHE` is cosmetic only and doesn't affect functionality. It's already addressed by setting `HF_HOME` in `.env`.

---

## Files Created/Modified

### Fixed Files
1. `.env` - Added `PYTHONIOENCODING=utf-8` and `HF_HOME`
2. `requirements.txt` - Specified stable transformers version
3. `scripts/fix_imports.py` - Diagnostic script
4. `docs/FIXES.md` - Detailed fix documentation
5. `docs/QUICK-START.md` - This file

---

## Next Steps

1. ✅ Verify imports work: `python scripts/fix_imports.py`
2. ✅ Start MCP server: `python -m src.mcp.stdio_server`
3. ✅ Test with Claude Code: `claude mcp add memory-mcp ...`
4. ✅ Run example queries (see Testing section above)

---

**Status**: System ready for production use! 🚀
