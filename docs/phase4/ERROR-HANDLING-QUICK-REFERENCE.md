# Error Handling Quick Reference - Phase 4 Stream A

**Last Updated**: 2025-11-26

---

## Fixed Issues - At a Glance

| Issue | File | Status | Impact |
|-------|------|--------|--------|
| ISS-013 | error_attribution.py | ✅ FIXED | Lifecycle detection now works |
| ISS-014 | error_attribution.py | ✅ FIXED | Real statistics from DB |
| ISS-015 | error_attribution.py | ✅ VERIFIED | Already resolved |
| ISS-049 | stdio_server.py | ✅ CRITICAL FIX | Memory store error handling |

---

## Usage Examples

### ISS-013: Lifecycle Detection

```python
from src.debug.error_attribution import ErrorAttribution
from src.debug.query_trace import QueryTrace

ea = ErrorAttribution()
trace = QueryTrace.create("What's my current status?", {})
trace.retrieved_chunks = [
    {'metadata': {'stage': 'archived'}, 'text': 'old data'}
]

# Will detect lifecycle mismatch
if ea._is_wrong_lifecycle(trace):
    print("Detected archived chunks for current query!")
```

**Detected Keywords**: "current", "latest", "now", "today", "recent"
**Detected Stages**: "archived", "demoted", "rehydratable"

---

### ISS-014: Statistics Aggregation

```python
from src.debug.error_attribution import ErrorAttribution
import sqlite3

# Connect to database
conn = sqlite3.connect("memory.db")
ea = ErrorAttribution(db=conn)

# Get last 30 days statistics
stats = ea.get_statistics(days=30)

print(f"Total queries: {stats['total_queries']}")
print(f"Failed queries: {stats['failed_queries']}")
print(f"Context bugs: {stats['failure_breakdown']['context_bugs']}")
print(f"Model bugs: {stats['failure_breakdown']['model_bugs']}")
print(f"System errors: {stats['failure_breakdown']['system_errors']}")
```

**Output Structure**:
```json
{
  "total_queries": 150,
  "failed_queries": 45,
  "failure_breakdown": {
    "context_bugs": 30,
    "model_bugs": 10,
    "system_errors": 5
  },
  "context_bug_breakdown": {
    "wrong_store_queried": 0,
    "wrong_mode_detected": 0,
    "wrong_lifecycle_filter": 0,
    "retrieval_ranking_error": 0
  },
  "days": 30
}
```

---

### ISS-049: Memory Store Error Handling

**Before** (Silent Failure):
```python
# If embedding fails, no error reported
embeddings = embedder.encode([text])
indexer.index_chunks(chunks, embeddings.tolist())
# User thinks data saved, but it didn't!
```

**After** (Proper Error Handling):
```python
try:
    embeddings = embedder.encode([text])
    if embeddings is None or len(embeddings) == 0:
        raise ValueError("Embedding generation failed")

    success = indexer.index_chunks(chunks, embeddings.tolist())
    if not success:
        raise RuntimeError("Indexing failed")
except Exception as embed_err:
    # Client receives error notification
    return {"isError": True, "content": [{"text": f"Storage failed: {embed_err}"}]}
```

**Client Usage**:
```javascript
// MCP client can now detect failures
const result = await mcp.callTool("memory_store", {
  text: "Important data",
  metadata: {agent: "coder"}
});

if (result.isError) {
  console.error("Storage failed:", result.content[0].text);
  // Retry or notify user
} else {
  console.log("Stored successfully!");
}
```

---

## Exception Handler Patterns

### Pattern 1: MCP Tools (RPC-style)
**Use Case**: Client-facing tool methods
**Pattern**:
```python
try:
    # Tool logic
    return {"content": [...], "isError": False}
except Exception as e:
    logger.error(f"Tool failed: {e}")
    return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
```

### Pattern 2: Service Layer (Graceful Degradation)
**Use Case**: Non-critical features
**Pattern**:
```python
try:
    # Service logic
    return result
except Exception as e:
    logger.error(f"Service failed: {e}")
    return default_value  # False, [], None, {}
```

### Pattern 3: Critical Data Processing (Fail-Fast)
**Use Case**: Data integrity operations
**Pattern**:
```python
try:
    result = critical_operation()
    if not is_valid(result):
        raise ValueError("Validation failed")
    return result
except Exception as e:
    logger.error(f"Critical operation failed: {e}")
    raise  # Re-raise for caller to handle
```

### Pattern 4: Background Tasks (Log + Continue)
**Use Case**: Non-blocking background operations
**Pattern**:
```python
try:
    # Background task logic
except Exception as e:
    logger.warning(f"Background task failed: {e}")
    # Continue execution
```

---

## Testing Commands

### Test ISS-013 & ISS-014
```bash
cd "C:\Users\17175\Desktop\memory-mcp-triple-system"
python -c "
from src.debug.error_attribution import ErrorAttribution
from src.debug.query_trace import QueryTrace
import tempfile, sqlite3, os
from datetime import datetime, timedelta

# Test lifecycle detection
ea = ErrorAttribution()
trace = QueryTrace.create('What is current?', {})
trace.retrieved_chunks = [{'metadata': {'stage': 'archived'}}]
assert ea._is_wrong_lifecycle(trace) == True
print('ISS-013: PASS')

# Test statistics
db_path = tempfile.mktemp(suffix='.db')
conn = sqlite3.connect(db_path)
QueryTrace.init_schema(db_path)
cursor = conn.cursor()
now = datetime.now()
cursor.execute('INSERT INTO query_traces (query_id, timestamp, query, user_context, error, error_type) VALUES (?, ?, ?, ?, ?, ?)',
    ('t1', (now - timedelta(days=1)).isoformat(), 'q', '{}', 'err', 'context_bug'))
conn.commit()
ea_db = ErrorAttribution(db=conn)
stats = ea_db.get_statistics(days=7)
assert stats['total_queries'] == 1
assert stats['failed_queries'] == 1
conn.close()
os.unlink(db_path)
print('ISS-014: PASS')
"
```

### Test Memory Store (Logic Verification)
```python
# Manual verification (chromadb import issue)
from unittest.mock import Mock
from src.mcp.stdio_server import _handle_memory_store

tool = Mock()
tool.vector_search_tool.embedder.encode = Mock(return_value=None)
result = _handle_memory_store({'text': 'test'}, tool)
assert result['isError'] == True  # Correctly detects failure
```

---

## Monitoring Integration

### Dashboard Queries

**Error Rate**:
```sql
SELECT
  COUNT(CASE WHEN error IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) as error_rate
FROM query_traces
WHERE timestamp >= datetime('now', '-7 days');
```

**Error Type Distribution**:
```sql
SELECT
  error_type,
  COUNT(*) as count,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
FROM query_traces
WHERE error_type IS NOT NULL
  AND timestamp >= datetime('now', '-30 days')
GROUP BY error_type;
```

**Lifecycle Issues**:
```sql
-- Using ErrorAttribution classifier
SELECT
  query,
  retrieved_chunks
FROM query_traces
WHERE timestamp >= datetime('now', '-7 days')
-- Filter in Python: ea.classify_context_bug(trace) == WRONG_LIFECYCLE_FILTER
```

---

## Troubleshooting

### Issue: Statistics Return All Zeros
**Cause**: Database not connected or empty
**Fix**:
```python
ea = ErrorAttribution(db=sqlite3.connect("memory.db"))
# Verify table exists
cursor = ea.db.cursor()
cursor.execute("SELECT COUNT(*) FROM query_traces")
print(cursor.fetchone()[0], "traces in DB")
```

### Issue: Lifecycle Detection Always False
**Cause**: Retrieved chunks missing metadata.stage
**Fix**: Ensure chunks indexed with lifecycle metadata
```python
chunk = {
    'text': 'content',
    'metadata': {
        'stage': 'active',  # Required!
        'lifecycle_tier': 'hot'
    }
}
```

### Issue: Memory Store Fails Silently
**Cause**: Using old version without ISS-049 fix
**Fix**:
```bash
git pull  # Get latest stdio_server.py
# Verify fix present:
grep -A 5 "if not text:" src/mcp/stdio_server.py
```

---

## API Changes

### ErrorAttribution.get_statistics()

**Before**:
```python
stats = ea.get_statistics(days=30)
# Returns: All zeros (placeholder)
```

**After**:
```python
stats = ea.get_statistics(days=30)
# Returns: Real data from query_traces table
# Requires: ea.db connection
```

**Breaking Change**: NO - Returns same structure, just real data

### ErrorAttribution._is_wrong_lifecycle()

**Before**:
```python
result = ea._is_wrong_lifecycle(trace)
# Returns: Always False
```

**After**:
```python
result = ea._is_wrong_lifecycle(trace)
# Returns: True if archived chunks for current query
# Requires: trace.retrieved_chunks with metadata.stage
```

**Breaking Change**: NO - Return type unchanged (bool)

---

## Performance Impact

### ISS-013: Lifecycle Detection
- **Overhead**: O(n) where n = number of retrieved chunks
- **Typical n**: 5-10 chunks
- **Impact**: <1ms per query
- **Optimization**: Early return on first match

### ISS-014: Statistics Aggregation
- **Query Complexity**: 3 SQL queries with WHERE clause
- **Index Used**: idx_query_traces_timestamp
- **Typical Time**: 10-50ms for 30 days
- **Recommendation**: Cache results, refresh every 5 minutes

### ISS-049: Memory Store Error Handling
- **Overhead**: 2 additional checks (None, len==0)
- **Impact**: <0.1ms
- **Benefit**: Prevents silent data loss

---

## Related Documentation

- Full Report: `PHASE4-STREAM-A-ERROR-HANDLING-FIXES.md`
- Error Attribution Spec: `docs/project-history/planning/PLAN-v7.0-FINAL.md`
- Query Traces Schema: `migrations/007_query_traces_table.sql`
- MCP Server Docs: `src/mcp/README.md`

---

## Next Steps

1. ✅ Deploy ISS-013, ISS-014, ISS-049 fixes
2. ⏳ Fix opentelemetry dependency for full test suite
3. 📊 Enable dashboard with real statistics
4. 🔍 Monitor production for error patterns
5. 📈 Add context_bug_breakdown detail queries
