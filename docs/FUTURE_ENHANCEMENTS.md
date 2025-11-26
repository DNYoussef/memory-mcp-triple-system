# Future Enhancements

This document tracks future enhancements identified during code quality audits but deferred due to low priority or resource constraints.

## ISS-052: Connection Pooling for SQLite Operations

**Priority**: LOW
**Effort**: 4-6 hours
**Status**: Deferred
**Affected Files**:
- `src/stores/kv_store.py`
- `src/stores/event_log.py`

### Current Implementation

Both `KVStore` and `EventLog` currently create new SQLite connections for operations:
- `KVStore`: Uses a single persistent connection via `_get_connection()`
- `EventLog`: Creates a new connection for each operation

### Problem

For high-throughput scenarios, this approach may lead to:
1. **Connection overhead**: Creating connections has overhead
2. **Potential contention**: Multiple operations may block on connection creation
3. **Resource inefficiency**: Not reusing connections optimally

### Proposed Solution

Implement a simple connection pool using one of these approaches:

#### Option 1: Simple Thread-Local Connections
```python
import threading

class ConnectionPool:
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._local = threading.local()

    def get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
        return self._local.conn
```

#### Option 2: Queue-Based Pool
```python
from queue import Queue
import sqlite3

class ConnectionPool:
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool = Queue(maxsize=pool_size)
        for _ in range(pool_size):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            self.pool.put(conn)

    @contextmanager
    def get_connection(self):
        conn = self.pool.get()
        try:
            yield conn
        finally:
            self.pool.put(conn)
```

#### Option 3: Third-Party Library
Consider using `sqlalchemy` with connection pooling:
```python
from sqlalchemy import create_engine, pool

engine = create_engine(
    f'sqlite:///{db_path}',
    poolclass=pool.QueuePool,
    pool_size=5,
    max_overflow=10
)
```

### Implementation Notes

1. **Thread Safety**: SQLite connections must use `check_same_thread=False` for pooling
2. **WAL Mode**: Enable Write-Ahead Logging for better concurrency:
   ```sql
   PRAGMA journal_mode=WAL;
   ```
3. **Timeout**: Set appropriate `timeout` parameter to handle contention:
   ```python
   sqlite3.connect(db_path, timeout=10.0)
   ```

### Performance Considerations

- **Current Performance**: Adequate for low-to-medium throughput
- **Expected Improvement**: 10-30% reduction in connection overhead for high-throughput scenarios
- **Trade-off**: Added complexity vs. marginal gains for current use cases

### Testing Strategy

When implementing:
1. Benchmark current connection creation time
2. Implement pooling with Option 1 (simplest)
3. Run load tests with concurrent operations
4. Measure improvement
5. Add unit tests for pool behavior

### Acceptance Criteria

- [ ] Connection pool implementation completed
- [ ] All existing tests pass
- [ ] New tests for pool behavior added
- [ ] Performance benchmarks show improvement
- [ ] Documentation updated
- [ ] No regression in error handling

### Related Issues

- ISS-016: TTL implementation (completed) - reduces pressure on connection creation
- Future: Consider migrating to async/await with `aiosqlite` for better concurrency

### Decision

**DEFERRED** - Current implementation is adequate for expected load. Implement only if:
1. Performance profiling shows connection overhead >10% of operation time
2. Application requires >100 operations/second sustained
3. Monitoring shows connection-related bottlenecks

---

**Last Updated**: 2025-11-26
**Reviewed By**: Phase 4 Stream B Code Quality Audit
