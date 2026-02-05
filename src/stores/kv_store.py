"""
Key-Value Store (Tier 1 of 5-Tier Architecture)

SQLite-backed KV store optimized for O(1) preference lookups.
Also hosts observations and sessions tables for auto-capture.

Query patterns: "What's my X?" (e.g., "What's my coding style?")

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from loguru import logger


class KVStore:
    """
    SQLite-backed key-value store for O(1) lookups.

    Tier 1 of 5-tier polyglot storage architecture.
    Optimized for user preferences and simple lookups.

    Performance targets:
    - Lookup latency: <1ms
    - Write latency: <2ms

    Usage:
        store = KVStore("memory.db")
        store.set("coding_style", "functional")
        style = store.get("coding_style")  # O(1) lookup
        print(style)  # "functional"
    """

    def __init__(self, db_path: str = "memory.db"):
        """
        Initialize KV store with SQLite backend.

        Args:
            db_path: Path to SQLite database file

        NASA Rule 10: 11 LOC (<=60)
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._local = threading.local()
        self._create_table()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get or create thread-local database connection.

        NASA Rule 10: 10 LOC (<=60)
        """
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    @contextmanager
    def _transaction(self):
        """Thread-safe transaction context manager."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _create_table(self) -> None:
        """
        Create kv_store table if not exists.

        Schema:
            - key (TEXT PRIMARY KEY): Unique key
            - value (TEXT): JSON-serialized value
            - created_at (DATETIME): Creation timestamp
            - updated_at (DATETIME): Last update timestamp
            - expires_at (DATETIME): Expiration timestamp (NULL = no expiry)

        NASA Rule 10: 30 LOC (<=60)
        """
        with self._transaction() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME
                )
            """)

            # Index for prefix queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kv_key_prefix
                ON kv_store(key)
            """)

            # Index for expiration cleanup
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kv_expires_at
                ON kv_store(expires_at)
            """)

            # Observations table (auto-capture from PostToolUse)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS observations (
                    observation_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    obs_type TEXT NOT NULL DEFAULT 'tool_use',
                    concept TEXT NOT NULL DEFAULT 'implementation',
                    tool_name TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    who TEXT NOT NULL DEFAULT 'auto-capture:1.0.0',
                    project TEXT NOT NULL DEFAULT '',
                    why TEXT NOT NULL DEFAULT 'observation',
                    entities TEXT NOT NULL DEFAULT '[]',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_obs_session
                ON observations(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_obs_created
                ON observations(created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_obs_project
                ON observations(project)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_obs_type
                ON observations(obs_type)
            """)

            # Sessions table (lifecycle tracking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    ended_at DATETIME,
                    tool_count INTEGER NOT NULL DEFAULT 0,
                    project TEXT NOT NULL DEFAULT '',
                    branch TEXT NOT NULL DEFAULT '',
                    working_dir TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT ''
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_project
                ON sessions(project)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_started
                ON sessions(started_at)
            """)

    def get(self, key: str) -> Optional[str]:
        """
        Get value by key (O(1) lookup).
        Returns None if key doesn't exist or has expired.

        Args:
            key: Lookup key

        Returns:
            Value if found and not expired, None otherwise

        NASA Rule 10: 30 LOC (<=60)
        """
        try:
            with self._transaction() as cursor:
                cursor.execute(
                    "SELECT value, expires_at FROM kv_store WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()

                if not row:
                    return None

                # Check if expired
                if row["expires_at"]:
                    expires_at = datetime.fromisoformat(row["expires_at"])
                    if datetime.now() > expires_at:
                        # Lazy cleanup: delete expired entry
                        cursor.execute("DELETE FROM kv_store WHERE key = ?", (key,))
                        return None

                return row["value"]

        except sqlite3.Error as e:
            logger.error(f"KV get failed for key '{key}': {e}")
            return None

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """
        Set key-value pair with optional TTL.

        Args:
            key: Storage key
            value: Value to store (will be JSON-serialized if dict/list)
            ttl: Time-to-live in seconds (None = never expires)

        Returns:
            True if successful, False otherwise

        NASA Rule 10: 42 LOC (<=60)
        """
        # Serialize value if needed
        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        # Calculate expiration time
        now = datetime.now()
        expires_at = None
        if ttl is not None:
            expires_at = (now + timedelta(seconds=ttl)).isoformat()

        try:
            with self._transaction() as cursor:
                cursor.execute("""
                    INSERT INTO kv_store (key, value, created_at, updated_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at
                """, (
                    key,
                    value,
                    now.isoformat(),
                    now.isoformat(),
                    expires_at
                ))
            return True

        except sqlite3.Error as e:
            logger.error(f"KV set failed for key '{key}': {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key-value pair.

        Args:
            key: Key to delete

        Returns:
            True if deleted, False otherwise

        NASA Rule 10: 20 LOC (<=60)
        """
        try:
            with self._transaction() as cursor:
                cursor.execute(
                    "DELETE FROM kv_store WHERE key = ?",
                    (key,)
                )
                return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"KV delete failed for key '{key}': {e}")
            return False

    def list_keys(self, prefix: str = "") -> List[str]:
        """
        List all keys with optional prefix filter.

        Args:
            prefix: Key prefix filter (e.g., "user:") (optional)

        Returns:
            List of matching keys

        NASA Rule 10: 22 LOC (<=60)
        """
        try:
            with self._transaction() as cursor:
                if prefix:
                    cursor.execute(
                        "SELECT key FROM kv_store WHERE key LIKE ? ORDER BY key",
                        (f"{prefix}%",)
                    )
                else:
                    cursor.execute("SELECT key FROM kv_store ORDER BY key")

                return [row["key"] for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"KV list_keys failed: {e}")
            return []

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get value as JSON dict.

        Args:
            key: Lookup key

        Returns:
            Parsed JSON dict if found and valid, None otherwise

        NASA Rule 10: 19 LOC (<=60)
        """
        value = self.get(key)
        if value is None:
            return None

        try:
            parsed: Dict[str, Any] = json.loads(value)
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON for key '{key}': {e}")
            return None

    def set_json(self, key: str, value: Dict[str, Any]) -> bool:
        """
        Set value as JSON dict.

        Args:
            key: Storage key
            value: Dict to store as JSON

        Returns:
            True if successful, False otherwise

        NASA Rule 10: 10 LOC (<=60)
        """
        return self.set(key, json.dumps(value))

    def exists(self, key: str) -> bool:
        """
        Check if key exists.

        Args:
            key: Key to check

        Returns:
            True if key exists, False otherwise

        NASA Rule 10: 10 LOC (<=60)
        """
        return self.get(key) is not None

    def count(self) -> int:
        """
        Get total number of keys in store.

        Returns:
            Total key count

        NASA Rule 10: 14 LOC (<=60)
        """
        try:
            with self._transaction() as cursor:
                cursor.execute("SELECT COUNT(*) as count FROM kv_store")
                row = cursor.fetchone()
                return int(row["count"]) if row else 0
        except sqlite3.Error as e:
            logger.error(f"KV count failed: {e}")
            return 0

    # --- Observation CRUD ---

    def store_observation(self, obs_dict: Dict[str, Any]) -> bool:
        """Store a single observation.

        Args:
            obs_dict: Observation.to_dict() output

        Returns:
            True if stored successfully
        """
        try:
            with self._transaction() as cursor:
                cursor.execute("""
                    INSERT OR REPLACE INTO observations
                    (observation_id, session_id, obs_type, concept,
                     tool_name, content, metadata, who, project,
                     why, entities, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    obs_dict["observation_id"],
                    obs_dict["session_id"],
                    obs_dict["obs_type"],
                    obs_dict["concept"],
                    obs_dict["tool_name"],
                    obs_dict["content"],
                    json.dumps(obs_dict.get("metadata", {})),
                    obs_dict.get("who", "auto-capture:1.0.0"),
                    obs_dict.get("project", ""),
                    obs_dict.get("why", "observation"),
                    json.dumps(obs_dict.get("entities", [])),
                    obs_dict.get("created_at", datetime.now().isoformat()),
                ))
            return True
        except sqlite3.Error as e:
            logger.error(f"store_observation failed: {e}")
            return False

    def get_observations(
        self,
        session_id: Optional[str] = None,
        project: Optional[str] = None,
        obs_type: Optional[str] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Query observations with optional filters.

        Args:
            session_id: Filter by session
            project: Filter by project
            obs_type: Filter by observation type
            after: ISO timestamp lower bound (inclusive)
            before: ISO timestamp upper bound (inclusive)
            limit: Max results

        Returns:
            List of observation dicts, newest first
        """
        try:
            with self._transaction() as cursor:
                sql = "SELECT * FROM observations WHERE 1=1"
                params: List[Any] = []

                if session_id:
                    sql += " AND session_id = ?"
                    params.append(session_id)
                if project:
                    sql += " AND project = ?"
                    params.append(project)
                if obs_type:
                    sql += " AND obs_type = ?"
                    params.append(obs_type)
                if after:
                    sql += " AND created_at >= ?"
                    params.append(after)
                if before:
                    sql += " AND created_at <= ?"
                    params.append(before)

                sql += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)

                cursor.execute(sql, params)
                rows = cursor.fetchall()
                return [self._row_to_obs_dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"get_observations failed: {e}")
            return []

    def count_observations(self, session_id: str) -> int:
        """Count observations in a session."""
        try:
            with self._transaction() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM observations WHERE session_id = ?",
                    (session_id,)
                )
                row = cursor.fetchone()
                return int(row["cnt"]) if row else 0
        except sqlite3.Error as e:
            logger.error(f"count_observations failed: {e}")
            return 0

    def observation_exists(self, session_id: str, content_hash: str) -> bool:
        """Check if a similar observation exists in this session (dedup)."""
        try:
            with self._transaction() as cursor:
                cursor.execute(
                    "SELECT 1 FROM observations "
                    "WHERE session_id = ? AND content = ? LIMIT 1",
                    (session_id, content_hash)
                )
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logger.error(f"observation_exists check failed: {e}")
            return False

    @staticmethod
    def _row_to_obs_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a Row to an observation dict."""
        d = dict(row)
        d["metadata"] = json.loads(d.get("metadata", "{}"))
        d["entities"] = json.loads(d.get("entities", "[]"))
        return d

    # --- Session CRUD ---

    def create_session(self, session_dict: Dict[str, Any]) -> bool:
        """Create a new session record.

        Args:
            session_dict: Session.to_dict() output

        Returns:
            True if created successfully
        """
        try:
            with self._transaction() as cursor:
                cursor.execute("""
                    INSERT OR REPLACE INTO sessions
                    (session_id, started_at, ended_at, tool_count,
                     project, branch, working_dir, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_dict["session_id"],
                    session_dict["started_at"],
                    session_dict.get("ended_at"),
                    session_dict.get("tool_count", 0),
                    session_dict.get("project", ""),
                    session_dict.get("branch", ""),
                    session_dict.get("working_dir", ""),
                    session_dict.get("summary", ""),
                ))
            return True
        except sqlite3.Error as e:
            logger.error(f"create_session failed: {e}")
            return False

    def end_session(
        self, session_id: str, summary: str = "", tool_count: int = 0
    ) -> bool:
        """Mark a session as ended with summary."""
        try:
            with self._transaction() as cursor:
                cursor.execute("""
                    UPDATE sessions
                    SET ended_at = ?, summary = ?, tool_count = ?
                    WHERE session_id = ?
                """, (
                    datetime.now().isoformat(),
                    summary,
                    tool_count,
                    session_id,
                ))
            return True
        except sqlite3.Error as e:
            logger.error(f"end_session failed: {e}")
            return False

    def increment_tool_count(self, session_id: str) -> bool:
        """Increment tool_count for a session by 1."""
        try:
            with self._transaction() as cursor:
                cursor.execute("""
                    UPDATE sessions
                    SET tool_count = tool_count + 1
                    WHERE session_id = ?
                """, (session_id,))
            return True
        except sqlite3.Error as e:
            logger.error(f"increment_tool_count failed: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID."""
        try:
            with self._transaction() as cursor:
                cursor.execute(
                    "SELECT * FROM sessions WHERE session_id = ?",
                    (session_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"get_session failed: {e}")
            return None

    def get_recent_sessions(
        self,
        project: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get recent sessions, optionally filtered by project."""
        try:
            with self._transaction() as cursor:
                if project:
                    cursor.execute(
                        "SELECT * FROM sessions WHERE project = ? "
                        "ORDER BY started_at DESC LIMIT ?",
                        (project, limit)
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM sessions "
                        "ORDER BY started_at DESC LIMIT ?",
                        (limit,)
                    )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"get_recent_sessions failed: {e}")
            return []

    def get_last_session(
        self, project: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent completed session."""
        sessions = self.get_recent_sessions(project=project, limit=1)
        return sessions[0] if sessions else None

    def close(self) -> None:
        """
        Close database connection.

        NASA Rule 10: 5 LOC (<=60)
        """
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None

    def __enter__(self) -> "KVStore":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the store.

        Returns:
            Number of entries deleted

        NASA Rule 10: 23 LOC (<=60)
        """
        try:
            with self._transaction() as cursor:
                cursor.execute("""
                    DELETE FROM kv_store
                    WHERE expires_at IS NOT NULL
                    AND expires_at < ?
                """, (datetime.now().isoformat(),))

                deleted = cursor.rowcount

                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} expired entries")

                return deleted

        except sqlite3.Error as e:
            logger.error(f"KV cleanup_expired failed: {e}")
            return 0
