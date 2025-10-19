"""
Key-Value Store (Tier 1 of 5-Tier Architecture)

SQLite-backed KV store optimized for O(1) preference lookups.
Use cases: user_preferences, simple_lookups, session_state, feature_flags.

Query patterns: "What's my X?" (e.g., "What's my coding style?")

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging


logger = logging.getLogger(__name__)


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

        NASA Rule 10: 11 LOC (≤60) ✅
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: Optional[sqlite3.Connection] = None
        self._create_table()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get or create database connection.

        NASA Rule 10: 10 LOC (≤60) ✅
        """
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _create_table(self) -> None:
        """
        Create kv_store table if not exists.

        Schema:
            - key (TEXT PRIMARY KEY): Unique key
            - value (TEXT): JSON-serialized value
            - created_at (DATETIME): Creation timestamp
            - updated_at (DATETIME): Last update timestamp

        NASA Rule 10: 24 LOC (≤60) ✅
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for prefix queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_key_prefix
            ON kv_store(key)
        """)

        conn.commit()

    def get(self, key: str) -> Optional[str]:
        """
        Get value by key (O(1) lookup).

        Args:
            key: Lookup key

        Returns:
            Value if found, None otherwise

        NASA Rule 10: 18 LOC (≤60) ✅
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT value FROM kv_store WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            return row["value"] if row else None

        except sqlite3.Error as e:
            logger.error(f"KV get failed for key '{key}': {e}")
            return None

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """
        Set key-value pair.

        Args:
            key: Storage key
            value: Value to store (will be JSON-serialized if dict/list)
            ttl: Time-to-live in seconds (optional, for future use)

        Returns:
            True if successful, False otherwise

        NASA Rule 10: 32 LOC (≤60) ✅
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Serialize value if needed
        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        try:
            cursor.execute("""
                INSERT INTO kv_store (key, value, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, (
                key,
                value,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))

            conn.commit()
            return True

        except sqlite3.Error as e:
            logger.error(f"KV set failed for key '{key}': {e}")
            conn.rollback()
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key-value pair.

        Args:
            key: Key to delete

        Returns:
            True if deleted, False otherwise

        NASA Rule 10: 20 LOC (≤60) ✅
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM kv_store WHERE key = ?",
                (key,)
            )
            conn.commit()
            return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"KV delete failed for key '{key}': {e}")
            conn.rollback()
            return False

    def list_keys(self, prefix: str = "") -> List[str]:
        """
        List all keys with optional prefix filter.

        Args:
            prefix: Key prefix filter (e.g., "user:") (optional)

        Returns:
            List of matching keys

        NASA Rule 10: 22 LOC (≤60) ✅
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
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

        NASA Rule 10: 19 LOC (≤60) ✅
        """
        value = self.get(key)
        if value is None:
            return None

        try:
            return json.loads(value)
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

        NASA Rule 10: 10 LOC (≤60) ✅
        """
        return self.set(key, json.dumps(value))

    def exists(self, key: str) -> bool:
        """
        Check if key exists.

        Args:
            key: Key to check

        Returns:
            True if key exists, False otherwise

        NASA Rule 10: 10 LOC (≤60) ✅
        """
        return self.get(key) is not None

    def count(self) -> int:
        """
        Get total number of keys in store.

        Returns:
            Total key count

        NASA Rule 10: 14 LOC (≤60) ✅
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(*) as count FROM kv_store")
            return cursor.fetchone()["count"]
        except sqlite3.Error as e:
            logger.error(f"KV count failed: {e}")
            return 0

    def close(self) -> None:
        """
        Close database connection.

        NASA Rule 10: 5 LOC (≤60) ✅
        """
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
