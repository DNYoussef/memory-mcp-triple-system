# MCP Server Quick Start Guide

## Prerequisites

1. Python 3.12+ installed
2. Dependencies installed: `pip install -r requirements.txt`
3. (Optional) Docker Desktop running for full functionality

## Starting the Server

### Method 1: Direct Python Execution
```bash
cd C:\Users\17175\Desktop\memory-mcp-triple-system
python -m uvicorn src.mcp.server:create_app --factory --host localhost --port 8080
```

Expected output:
```
INFO:     Started server process
INFO:     Waiting for application startup.
2025-10-17 23:50:00.000 | INFO | src.mcp.server:load_config:43 - Loaded config from config/memory-mcp.yaml
2025-10-17 23:50:00.000 | INFO | src.mcp.server:create_app:125 - MCP server initialized
INFO:     Application startup complete.
INFO:     Uvicorn running on http://localhost:8080
```

### Method 2: Via Claude Desktop (Auto-Start)
1. Copy `.claude/mcp-config.json` to your Claude Desktop config directory:
   - Windows: `%APPDATA%\Claude\config\`
   - macOS: `~/Library/Application Support/Claude/config/`
   - Linux: `~/.config/claude/`

2. Restart Claude Desktop

3. Server starts automatically when Claude Desktop launches

## Testing the Server

### 1. Health Check
```bash
curl http://localhost:8080/health
```

Expected response (when Docker not running):
```json
{
  "status": "degraded",
  "services": {
    "qdrant": "unavailable",
    "embeddings": "available"
  }
}
```

Expected response (when Docker running):
```json
{
  "status": "healthy",
  "services": {
    "qdrant": "available",
    "embeddings": "available"
  }
}
```

### 2. List Available Tools
```bash
curl http://localhost:8080/tools
```

Expected response:
```json
{
  "tools": [
    {
      "name": "vector_search",
      "description": "Search memory vault using semantic similarity",
      "parameters": {
        "query": {
          "type": "string",
          "description": "Search query text"
        },
        "limit": {
          "type": "integer",
          "description": "Number of results to return",
          "default": 5
        }
      }
    }
  ]
}
```

### 3. Execute Vector Search
```bash
curl -X POST "http://localhost:8080/tools/vector_search?query=machine+learning&limit=3"
```

Expected response (requires Qdrant running):
```json
{
  "results": [
    {
      "text": "Machine learning is a subset of artificial intelligence...",
      "file_path": "/path/to/file.md",
      "chunk_index": 0,
      "score": 0.95,
      "metadata": {
        "title": "Introduction to ML"
      }
    }
  ]
}
```

## Enabling Full Functionality (Docker Services)

### Step 1: Enable Virtualization (BIOS)
**Required for Docker Desktop on Windows**

1. Restart computer and enter BIOS (usually F2, F12, or Del key)
2. Navigate to CPU Configuration or Advanced Settings
3. Enable "Intel VT-x" or "AMD-V" (virtualization technology)
4. Save and exit BIOS

### Step 2: Start Docker Desktop
```bash
# Verify Docker is running
docker --version

# Start services via docker-compose
cd C:\Users\17175\Desktop\memory-mcp-triple-system
docker-compose up -d
```

Expected output:
```
Creating network "memory-mcp-triple-system_default" with the default driver
Creating memory-mcp-triple-system_qdrant_1 ... done
Creating memory-mcp-triple-system_neo4j_1  ... done
Creating memory-mcp-triple-system_redis_1  ... done
```

### Step 3: Download Embeddings Model
```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Step 4: Verify Services
```bash
# Check Qdrant
curl http://localhost:6333/collections

# Check Neo4j
curl http://localhost:7474

# Check Redis
redis-cli ping
```

### Step 5: Restart MCP Server
```bash
# Stop current server (Ctrl+C)
# Restart
python -m uvicorn src.mcp.server:create_app --factory --host localhost --port 8080
```

Health check should now show:
```json
{
  "status": "healthy",
  "services": {
    "qdrant": "available",
    "embeddings": "available"
  }
}
```

## Using from Claude Desktop

Once the server is running:

1. Open Claude Desktop
2. Type queries that need memory search
3. Claude will automatically call the `vector_search` tool

Example conversation:
```
User: "What did I write about machine learning?"
Claude: [Calls vector_search tool with query="machine learning"]
Claude: "Based on your notes, you wrote about..."
```

## Troubleshooting

### Server Won't Start
**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

### Port Already in Use
**Error**: `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8080)`

**Solution**: Change port or kill existing process
```bash
# Use different port
python -m uvicorn src.mcp.server:create_app --factory --host localhost --port 8081

# Or kill process using port 8080 (Windows)
netstat -ano | findstr :8080
taskkill /PID <process_id> /F
```

### Qdrant Unavailable
**Error**: Health check shows `"qdrant": "unavailable"`

**Solution**: Start Docker services
```bash
docker-compose up -d
```

### Embeddings Model Not Found
**Error**: `OSError: sentence-transformers/all-MiniLM-L6-v2 does not exist`

**Solution**: Download model (requires internet)
```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

## Running Tests

### Unit Tests (No Docker Required)
```bash
pytest tests/unit/test_mcp_server.py tests/unit/test_vector_search.py -v
```

### Integration Tests (Requires Docker)
```bash
# Start Docker services first
docker-compose up -d

# Run integration tests
pytest tests/integration/test_end_to_end_search.py -v
```

### All Tests with Coverage
```bash
pytest tests/unit/ -v --cov=src/mcp --cov-report=html
```

## Configuration

### Changing Server Port
Edit `config/memory-mcp.yaml`:
```yaml
mcp:
  server:
    host: localhost
    port: 8080  # Change this
```

### Changing Qdrant Connection
Edit `config/memory-mcp.yaml`:
```yaml
storage:
  vector_db:
    host: localhost  # Change to remote Qdrant host
    port: 6333
    collection_name: memory_embeddings
```

### Changing Embeddings Model
Edit `config/memory-mcp.yaml`:
```yaml
embeddings:
  model: sentence-transformers/all-MiniLM-L6-v2  # Change model
  dimension: 384  # Must match model output dimension
```

## API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health status |
| `/tools` | GET | List available MCP tools |
| `/tools/vector_search` | POST | Execute semantic search |

### `/tools/vector_search` Parameters
- `query` (string, required): Search query text
- `limit` (integer, optional, default=5): Number of results (max 100)

### Response Format
```json
{
  "results": [
    {
      "text": "Chunk text content",
      "file_path": "/path/to/file.md",
      "chunk_index": 0,
      "score": 0.95,
      "metadata": {
        "title": "Document Title",
        "tags": ["tag1", "tag2"]
      }
    }
  ]
}
```

## Development Mode

### Enable Debug Logging
```bash
# Set environment variable
export LOG_LEVEL=DEBUG  # Linux/macOS
set LOG_LEVEL=DEBUG     # Windows

# Restart server
python -m uvicorn src.mcp.server:create_app --factory --host localhost --port 8080 --log-level debug
```

### Auto-Reload on Code Changes
```bash
python -m uvicorn src.mcp.server:create_app --factory --host localhost --port 8080 --reload
```

### Interactive API Documentation
Once server is running, visit:
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

## Next Steps

1. Enable Docker services for full functionality
2. Index your Obsidian vault (Week 1 file watcher)
3. Test vector search with real documents
4. Integrate with Claude Desktop for conversational memory retrieval

---

**Last Updated**: 2025-10-17
**Week**: 2 (MCP Server Implementation)
**Status**: Production-Ready ✅
