"""
Query Trace - Context Assembly Debugger Foundation (Week 7)

100% query logging for deterministic replay and error attribution.
Mitigates PREMORTEM Risk #13: "40% of AI failures are context-assembly bugs."

Part of incremental debugger implementation:
- Week 7: Query logging infrastructure ✅
- Week 8: Replay capability
- Week 11: Error attribution

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

import sqlite3
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from pathlib import Path
from loguru import logger


@dataclass
class QueryTrace:
    """
    Query trace record for 100% query logging.

    Stored in SQLite `query_traces` table with 30-day retention.
    Enables:
    - Debugging failed queries (replay with same context)
    - Error attribution (context bugs vs model bugs)
    - Performance monitoring (latency breakdown)

    PREMORTEM Risk #13 Mitigation:
    - 100% logging (no sampling)
    - Deterministic replay (same context → same output)
    - Error attribution (70% context bugs, 30% model bugs)

    Usage:
        trace = QueryTrace.create(
            query="What is NASA Rule 10?",
            user_context={"session_id": "abc123"}
        )
        trace.mode_detected = "execution"
        trace.stores_queried = ["vector", "relational"]
        trace.output = "NASA Rule 10: ≤60 LOC per function"
        trace.total_latency_ms = 195
        trace.log()  # Save to SQLite
    """

    # Identifiers
    query_id: UUID
    timestamp: datetime

    # Input
    query: str
    user_context: Dict[str, Any]

    # Mode Detection
    mode_detected: str  # "execution" | "planning" | "brainstorming"
    mode_confidence: float  # 0.0-1.0
    mode_detection_ms: int

    # Routing
    stores_queried: List[str]  # ["vector", "relational"], etc.
    routing_logic: str  # "KV skip (simple query)", "Bayesian skip (execution mode)"

    # Retrieval
    retrieved_chunks: List[Dict[str, Any]]  # [{"id": ..., "score": ..., "source": ...}]
    retrieval_ms: int

    # Verification (if execution mode)
    verification_result: Optional[Dict[str, Any]]  # {"verified": True/False, ...}
    verification_ms: int

    # Output
    output: str
    total_latency_ms: int

    # Error Attribution
    error: Optional[str]  # NULL if success, error message if failure
    error_type: Optional[str]  # "context_bug" | "model_bug" | "system_error"

    @classmethod
    def create(cls, query: str, user_context: Dict[str, Any]) -> "QueryTrace":
        """
        Create new query trace with defaults.

        Args:
            query: User query string
            user_context: Context dict (session_id, user_id, etc.)

        Returns:
            QueryTrace instance with initialized fields

        NASA Rule 10: 28 LOC (≤60) ✅
        """
        return cls(
            query_id=uuid4(),
            timestamp=datetime.now(),
            query=query,
            user_context=user_context,
            mode_detected="",
            mode_confidence=0.0,
            mode_detection_ms=0,
            stores_queried=[],
            routing_logic="",
            retrieved_chunks=[],
            retrieval_ms=0,
            verification_result=None,
            verification_ms=0,
            output="",
            total_latency_ms=0,
            error=None,
            error_type=None
        )

    @classmethod
    def init_schema(cls, db_path: str = "memory.db") -> bool:
        """
        ISS-051 FIX: Initialize query_traces table schema.

        Creates table if not exists. Call on startup or before first log.

        Args:
            db_path: Path to SQLite database

        Returns:
            True if successful, False otherwise

        NASA Rule 10: 35 LOC (<=60)
        """
        db = Path(db_path)
        db.parent.mkdir(parents=True, exist_ok=True)

        try:
            conn = sqlite3.connect(str(db))
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS query_traces (
                    query_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    query TEXT NOT NULL,
                    user_context TEXT,
                    mode_detected TEXT,
                    mode_confidence REAL,
                    mode_detection_ms INTEGER,
                    stores_queried TEXT,
                    routing_logic TEXT,
                    retrieved_chunks TEXT,
                    retrieval_ms INTEGER,
                    verification_result TEXT,
                    verification_ms INTEGER,
                    output TEXT,
                    total_latency_ms INTEGER,
                    error TEXT,
                    error_type TEXT
                )
            """)
            conn.commit()
            conn.close()
            logger.info(f"QueryTrace schema initialized in {db_path}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to init QueryTrace schema: {e}")
            return False

    def log(self, db_path: str = "memory.db") -> bool:
        """
        Save trace to SQLite `query_traces` table.

        Args:
            db_path: Path to SQLite database

        Returns:
            True if successful, False otherwise

        NASA Rule 10: 50 LOC (<=60)
        """
        db = Path(db_path)
        db.parent.mkdir(parents=True, exist_ok=True)

        try:
            conn = sqlite3.connect(str(db))
            cursor = conn.cursor()

            # ISS-051 FIX: Ensure schema exists before insert
            self.init_schema(db_path)

            cursor.execute("""
                INSERT INTO query_traces (
                    query_id, timestamp, query, user_context,
                    mode_detected, mode_confidence, mode_detection_ms,
                    stores_queried, routing_logic,
                    retrieved_chunks, retrieval_ms,
                    verification_result, verification_ms,
                    output, total_latency_ms,
                    error, error_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(self.query_id),
                self.timestamp.isoformat(),
                self.query,
                json.dumps(self.user_context),
                self.mode_detected,
                self.mode_confidence,
                self.mode_detection_ms,
                json.dumps(self.stores_queried),
                self.routing_logic,
                json.dumps(self.retrieved_chunks),
                self.retrieval_ms,
                json.dumps(self.verification_result) if self.verification_result else None,
                self.verification_ms,
                self.output,
                self.total_latency_ms,
                self.error,
                self.error_type
            ))

            conn.commit()
            conn.close()
            return True

        except sqlite3.Error as e:
            logger.error(f"Failed to log query trace {self.query_id}: {e}")
            return False

    @classmethod
    def get_trace(cls, query_id: UUID, db_path: str = "memory.db") -> Optional["QueryTrace"]:
        """
        Retrieve trace by query_id.

        Args:
            query_id: UUID of query trace
            db_path: Path to SQLite database

        Returns:
            QueryTrace if found, None otherwise

        NASA Rule 10: 44 LOC (≤60) ✅
        """
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM query_traces WHERE query_id = ?",
                (str(query_id),)
            )

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return cls(
                query_id=UUID(row["query_id"]),
                timestamp=datetime.fromisoformat(row["timestamp"]),
                query=row["query"],
                user_context=json.loads(row["user_context"]),
                mode_detected=row["mode_detected"] or "",
                mode_confidence=row["mode_confidence"] or 0.0,
                mode_detection_ms=row["mode_detection_ms"] or 0,
                stores_queried=json.loads(row["stores_queried"]) if row["stores_queried"] else [],
                routing_logic=row["routing_logic"] or "",
                retrieved_chunks=json.loads(row["retrieved_chunks"]) if row["retrieved_chunks"] else [],
                retrieval_ms=row["retrieval_ms"] or 0,
                verification_result=json.loads(row["verification_result"]) if row["verification_result"] else None,
                verification_ms=row["verification_ms"] or 0,
                output=row["output"] or "",
                total_latency_ms=row["total_latency_ms"] or 0,
                error=row["error"],
                error_type=row["error_type"]
            )

        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Failed to retrieve query trace {query_id}: {e}")
            return None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert trace to dictionary.

        Returns:
            Dict representation of trace

        NASA Rule 10: 14 LOC (≤60) ✅
        """
        data = asdict(self)
        data["query_id"] = str(self.query_id)
        data["timestamp"] = self.timestamp.isoformat()
        return data
