"""
RLM Trajectory Logger.

RLM-004: Trajectory logging for RLM operations.
Outputs to JSONL files for analysis and visualizer integration.

Key Features:
- JSONL output format for trajectory analysis
- Timestamped entries with depth tracking
- Visualizer integration (localhost:3001)
- Aggregated statistics

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List
from loguru import logger


class TrajectoryEventType(Enum):
    """Types of trajectory events."""

    QUERY_START = "query_start"
    QUERY_END = "query_end"
    SEARCH = "search"
    RECURSE = "recurse"
    RESULT = "result"
    ERROR = "error"
    COST = "cost"


@dataclass
class TrajectoryEvent:
    """A single trajectory event.

    Attributes:
        event_type: Type of event
        depth: Recursion depth at event
        query: Query string if applicable
        data: Event-specific data
        tokens: Tokens used if applicable
        timestamp: ISO8601 timestamp
    """

    event_type: TrajectoryEventType
    depth: int
    query: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    tokens: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    session_id: Optional[str] = None
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_type": self.event_type.value,
            "depth": self.depth,
            "query": self.query,
            "data": self.data,
            "tokens": self.tokens,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class TrajectoryStats:
    """Aggregated statistics for a trajectory."""

    total_events: int = 0
    max_depth: int = 0
    total_tokens: int = 0
    total_searches: int = 0
    total_recurses: int = 0
    errors: int = 0
    duration_ms: int = 0


class RLMLogger:
    """
    RLM-004: Trajectory logger for RLM operations.

    Logs all RLM events to JSONL files for analysis.
    Supports integration with visualizer at localhost:3001.

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    def __init__(
        self,
        output_dir: Optional[str] = None,
        session_id: Optional[str] = None,
        enable_visualizer: bool = True,
    ):
        """
        Initialize RLM logger.

        Args:
            output_dir: Directory for JSONL output
            session_id: Session identifier
            enable_visualizer: Enable visualizer integration

        NASA Rule 10: 20 LOC (<=60)
        """
        self.output_dir = Path(output_dir or "logs/rlm_trajectories")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = session_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.enable_visualizer = enable_visualizer
        self.visualizer_port = 3001

        self._events: List[TrajectoryEvent] = []
        self._current_trace_id: Optional[str] = None
        self._trace_counter = 0
        self._file_handle = None

        # Open log file
        self._log_path = self.output_dir / f"trajectory_{self.session_id}.jsonl"
        logger.info(f"RLMLogger initialized: {self._log_path}")

    def start_trace(self, query: str) -> str:
        """
        Start a new trace for a query.

        Args:
            query: Initial query string

        Returns:
            Trace ID

        NASA Rule 10: 15 LOC (<=60)
        """
        self._trace_counter += 1
        self._current_trace_id = f"trace_{self.session_id}_{self._trace_counter}"

        self.log_event(
            TrajectoryEventType.QUERY_START,
            depth=0,
            query=query,
            data={"trace_id": self._current_trace_id},
        )

        return self._current_trace_id

    def end_trace(self, result: Any, tokens: int = 0) -> None:
        """
        End the current trace.

        Args:
            result: Final result
            tokens: Total tokens used

        NASA Rule 10: 12 LOC (<=60)
        """
        self.log_event(
            TrajectoryEventType.QUERY_END,
            depth=0,
            data={
                "result_type": type(result).__name__,
                "result_count": len(result) if hasattr(result, "__len__") else 1,
            },
            tokens=tokens,
        )
        self._current_trace_id = None

    def log_event(
        self,
        event_type: TrajectoryEventType,
        depth: int,
        query: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        tokens: int = 0,
    ) -> TrajectoryEvent:
        """
        Log a trajectory event.

        Args:
            event_type: Type of event
            depth: Current recursion depth
            query: Query string if applicable
            data: Event-specific data
            tokens: Tokens used

        Returns:
            The logged event

        NASA Rule 10: 25 LOC (<=60)
        """
        event = TrajectoryEvent(
            event_type=event_type,
            depth=depth,
            query=query,
            data=data,
            tokens=tokens,
            session_id=self.session_id,
            trace_id=self._current_trace_id,
        )

        self._events.append(event)

        # Write to JSONL file
        self._write_event(event)

        # Log to console
        logger.debug(f"RLM Event: {event_type.value} depth={depth} tokens={tokens}")

        return event

    def log_search(self, query: str, depth: int, result_count: int) -> None:
        """Log a search operation."""
        self.log_event(
            TrajectoryEventType.SEARCH,
            depth=depth,
            query=query,
            data={"result_count": result_count},
        )

    def log_recurse(self, query: str, depth: int) -> None:
        """Log a recursion."""
        self.log_event(TrajectoryEventType.RECURSE, depth=depth, query=query)

    def log_error(self, error: str, depth: int) -> None:
        """Log an error."""
        self.log_event(TrajectoryEventType.ERROR, depth=depth, data={"error": error})

    def log_cost(self, tokens: int, cost_usd: float, depth: int) -> None:
        """Log cost information."""
        self.log_event(
            TrajectoryEventType.COST,
            depth=depth,
            tokens=tokens,
            data={"cost_usd": cost_usd},
        )

    def _write_event(self, event: TrajectoryEvent) -> None:
        """
        Write event to JSONL file.

        NASA Rule 10: 12 LOC (<=60)
        """
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(event.to_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to write event to log: {e}")

    def get_stats(self) -> TrajectoryStats:
        """
        Get aggregated statistics for the session.

        NASA Rule 10: 25 LOC (<=60)
        """
        stats = TrajectoryStats()
        stats.total_events = len(self._events)

        start_time = None
        end_time = None

        for event in self._events:
            stats.max_depth = max(stats.max_depth, event.depth)
            stats.total_tokens += event.tokens

            if event.event_type == TrajectoryEventType.SEARCH:
                stats.total_searches += 1
            elif event.event_type == TrajectoryEventType.RECURSE:
                stats.total_recurses += 1
            elif event.event_type == TrajectoryEventType.ERROR:
                stats.errors += 1

            # Track timing
            if event.event_type == TrajectoryEventType.QUERY_START:
                start_time = datetime.fromisoformat(event.timestamp)
            elif event.event_type == TrajectoryEventType.QUERY_END:
                end_time = datetime.fromisoformat(event.timestamp)

        if start_time and end_time:
            stats.duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return stats

    def get_visualizer_url(self) -> str:
        """Get URL for visualizer integration."""
        return f"http://localhost:{self.visualizer_port}/trajectory/{self.session_id}"

    def export_for_visualizer(self) -> Dict[str, Any]:
        """
        Export trajectory data for visualizer.

        Returns:
            Dict with events, stats, and metadata

        NASA Rule 10: 15 LOC (<=60)
        """
        return {
            "session_id": self.session_id,
            "log_path": str(self._log_path),
            "events": [e.to_dict() for e in self._events],
            "stats": asdict(self.get_stats()),
            "visualizer_url": self.get_visualizer_url()
            if self.enable_visualizer
            else None,
        }

    def close(self) -> None:
        """Close the logger and finalize output."""
        stats = self.get_stats()
        logger.info(
            f"RLMLogger closed: {stats.total_events} events, "
            f"max_depth={stats.max_depth}, tokens={stats.total_tokens}"
        )
