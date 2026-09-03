# Service Wiring Quick Reference

**Phase 6 Stream A - C3.2, C3.3, C3.4**

---

## ObsidianClient (C3.2)

**File**: `src/mcp/obsidian_client.py`
**Wiring**: `src/mcp/stdio_server.py` lines 89-108

### Configuration
```yaml
storage:
  obsidian_vault: ~/Documents/Memory-Vault
```

### MCP Tool
```json
{
  "name": "obsidian_sync",
  "arguments": {
    "file_extensions": [".md", ".txt"]
  }
}
```

### Code Usage
```python
# Lazy initialization
client = tool.obsidian_client  # Returns None if not configured

# Manual sync
if client:
    result = client.sync_vault([".md"])
    print(f"Synced {result['files_synced']} files")
```

---

## EventLog (C3.3)

**File**: `src/stores/event_log.py`
**Wiring**: `src/mcp/stdio_server.py` lines 70, 110-128
**Database**: `./data/events.db`

### Event Types
- `QUERY_EXECUTED` - Search queries
- `CHUNK_ADDED` - Memory storage
- `CHUNK_UPDATED` - Memory updates
- `CHUNK_DELETED` - Memory deletions
- `ENTITY_CONSOLIDATED` - Graph ops
- `LIFECYCLE_TRANSITION` - Hot/cold moves

### Code Usage
```python
# Log event
tool.log_event("vector_search", {
    "query": "Python tutorial",
    "mode": "execution",
    "results_count": 5,
    "latency_ms": 42
})

# Query events
from datetime import datetime
events = tool.event_log.query_by_timerange(
    start_time=datetime(2025, 11, 26, 0, 0),
    end_time=datetime(2025, 11, 26, 23, 59)
)
```

---

## KVStore (C3.4)

**File**: `src/stores/kv_store.py`
**Wiring**: `src/mcp/stdio_server.py` lines 73, 130-137
**Database**: `./data/kv_store.db`

### Key Patterns
- `session:*` - Session state (mode, limit, context)
- `user:*` - User preferences (theme, style)
- `feature:*` - Feature flags (enable/disable)

### Code Usage
```python
# Store session state
tool.kv_store.set("session:last_query_mode", "planning")
tool.kv_store.set("user:coding_style", "functional")

# Retrieve with default
mode = tool.get_session_preference("last_query_mode", "execution")

# Direct KV access
tool.kv_store.set("feature:hipporag_enabled", "true")
enabled = tool.kv_store.get("feature:hipporag_enabled")
```

---

## Integration Points

### vector_search Handler
```python
# Session state (C3.4)
tool.kv_store.set("session:last_query_mode", mode)

# Query trace (C3.6)
trace = tool.create_query_trace(query, mode)

# Event logging (C3.3)
tool.log_event("vector_search", {...})
```

### memory_store Handler
```python
# Lifecycle classification (C3.5)
classification = tool.hot_cold_classifier.classify(text, metadata)

# Event logging (C3.3)
tool.log_event("memory_store", {...})
```

### obsidian_sync Handler
```python
# Vault sync (C3.2)
result = tool.obsidian_client.sync_vault(file_extensions)

# Event logging (C3.3)
tool.log_event("chunk_added", {...})
```

---

## Database Files

All stored in `./data/` directory:

```
./data/
├── events.db          # EventLog (C3.3)
├── kv_store.db        # KVStore (C3.4)
└── query_traces.db    # QueryTrace (C3.6)
```

Configure in `config/memory-mcp.yaml`:
```yaml
storage:
  data_dir: ./data
```

---

## Error Handling

All services use graceful degradation:

```python
# ObsidianClient - Returns None if not configured
if tool.obsidian_client:
    tool.obsidian_client.sync_vault()
else:
    # Vault not configured, skip sync

# EventLog - Warns on failure, continues
try:
    tool.log_event("event_type", data)
except Exception as e:
    logger.warning(f"Event logging failed: {e}")
    # Operation continues

# KVStore - Returns default on failure
value = tool.get_session_preference("key", default="fallback")
```

---

## Testing Commands

### Check Event Log
```bash
sqlite3 ./data/events.db "SELECT * FROM event_log ORDER BY timestamp DESC LIMIT 10;"
```

### Check KV Store
```bash
sqlite3 ./data/kv_store.db "SELECT key, value FROM kv_store WHERE key LIKE 'session:%';"
```

### Test Obsidian Sync
```python
from mcp.stdio_server import NexusSearchTool, load_config

config = load_config()
tool = NexusSearchTool(config)

if tool.obsidian_client:
    result = tool.obsidian_client.sync_vault()
    print(result)
```

---

## Service Status

| Service | Status | Database | LOC | NASA Rule 10 |
|---------|--------|----------|-----|--------------|
| ObsidianClient | ✅ Wired | N/A | 52 | ✅ ≤60 |
| EventLog | ✅ Wired | events.db | 40 | ✅ ≤60 |
| KVStore | ✅ Wired | kv_store.db | 8 | ✅ ≤60 |

All services production-ready with graceful error handling.
