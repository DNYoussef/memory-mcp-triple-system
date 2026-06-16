"""
RLM Environment Base Class.

RLM-002: Abstract base class for recursive language model environments.
Provides methods for data loading, search, chunk retrieval, and recursive queries.

The RLM paradigm allows models to:
1. Search and retrieve relevant code/data
2. Execute recursive queries with depth control
3. Self-inspect and analyze patterns
4. Learn from telemetry feedback

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from loguru import logger


class ExecutionMode(Enum):
    """RLM execution modes."""

    SEARCH = "search"  # Search and retrieve
    ANALYZE = "analyze"  # Deep analysis
    RECURSIVE = "recursive"  # Recursive exploration
    INSPECT = "inspect"  # Self-inspection


@dataclass
class RLMConfig:
    """Configuration for RLM environment.

    Attributes:
        max_depth: Maximum recursion depth (default 10)
        max_tokens: Maximum tokens per query (default 8000)
        timeout_seconds: Query timeout (default 30)
        enable_caching: Cache query results (default True)
        sandbox_mode: Run in isolated sandbox (default True)
    """

    max_depth: int = 10
    max_tokens: int = 8000
    timeout_seconds: int = 30
    enable_caching: bool = True
    sandbox_mode: bool = True
    cost_limit_usd: float = 1.0
    projects_root: str = field(
        default_factory=lambda: os.getenv("MEMORY_MCP_PROJECTS_ROOT")
        or str(Path(__file__).resolve().parents[3])
    )


@dataclass
class ExecutionContext:
    """Context for RLM execution.

    Tracks recursion depth, tokens used, and execution path.
    """

    depth: int = 0
    tokens_used: int = 0
    path: List[str] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    parent_context: Optional["ExecutionContext"] = None

    def child(self, step: str) -> "ExecutionContext":
        """Create child context for recursive call."""
        return ExecutionContext(
            depth=self.depth + 1,
            tokens_used=self.tokens_used,
            path=self.path + [step],
            parent_context=self,
        )


@dataclass
class RLMResult:
    """Result from RLM query execution.

    Attributes:
        success: Whether query succeeded
        data: Result data
        depth_reached: Maximum depth reached
        tokens_used: Total tokens consumed
        duration_ms: Execution time in milliseconds
        error: Error message if failed
    """

    success: bool
    data: Any
    depth_reached: int
    tokens_used: int
    duration_ms: int
    error: Optional[str] = None
    context: Optional[ExecutionContext] = None


class RLMEnvironment(ABC):
    """
    Abstract base class for RLM environments.

    RLM-002: Provides interface for recursive language model operations.
    Subclasses implement specific data sources (Memory MCP, codebase, etc.)

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    def __init__(self, config: Optional[RLMConfig] = None):
        """
        Initialize RLM environment.

        Args:
            config: RLM configuration

        NASA Rule 10: 10 LOC (<=60)
        """
        self.config = config or RLMConfig()
        self._cache: Dict[str, Any] = {}
        self._query_count = 0
        self._total_tokens = 0

        logger.info(
            f"RLMEnvironment initialized with max_depth={self.config.max_depth}"
        )

    @abstractmethod
    def load_data(self, source: str) -> bool:
        """
        Load data from a source into the environment.

        Args:
            source: Data source identifier (path, URL, etc.)

        Returns:
            True if loaded successfully
        """
        pass

    @abstractmethod
    def search(
        self, query: str, limit: int = 10, context: Optional[ExecutionContext] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant items.

        Args:
            query: Search query string
            limit: Maximum results to return
            context: Execution context for tracking

        Returns:
            List of matching items with scores
        """
        pass

    @abstractmethod
    def get_chunk(
        self, chunk_id: str, context: Optional[ExecutionContext] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific chunk by ID.

        Args:
            chunk_id: Unique chunk identifier
            context: Execution context for tracking

        Returns:
            Chunk data or None if not found
        """
        pass

    def recursive_query(
        self,
        query: str,
        processor: Callable[[List[Dict]], str],
        context: Optional[ExecutionContext] = None,
        depth: int = 0,
    ) -> RLMResult:
        """
        Execute a recursive query with depth control.

        The processor function receives search results and returns
        either a follow-up query (continues recursion) or None (stops).

        Args:
            query: Initial search query
            processor: Function to process results and generate next query
            context: Execution context
            depth: Current recursion depth

        Returns:
            RLMResult with accumulated data

        NASA Rule 10: 45 LOC (<=60)
        """
        import time

        start_ms = int(time.time() * 1000)
        ctx = context or ExecutionContext()

        # Check depth limit
        if depth >= self.config.max_depth:
            logger.warning(f"Max recursion depth {self.config.max_depth} reached")
            return RLMResult(
                success=False,
                data=None,
                depth_reached=depth,
                tokens_used=ctx.tokens_used,
                duration_ms=int(time.time() * 1000) - start_ms,
                error=f"Max depth {self.config.max_depth} exceeded",
                context=ctx,
            )

        try:
            # Execute search
            results = self.search(query, context=ctx)
            self._query_count += 1

            # Process results
            next_query = processor(results)

            if next_query is None:
                # Base case: processing complete
                return RLMResult(
                    success=True,
                    data=results,
                    depth_reached=depth,
                    tokens_used=ctx.tokens_used,
                    duration_ms=int(time.time() * 1000) - start_ms,
                    context=ctx,
                )

            # Recursive case: continue with next query
            child_ctx = ctx.child(f"depth_{depth + 1}")
            return self.recursive_query(next_query, processor, child_ctx, depth + 1)

        except Exception as e:
            logger.error(f"Recursive query failed at depth {depth}: {e}")
            return RLMResult(
                success=False,
                data=None,
                depth_reached=depth,
                tokens_used=ctx.tokens_used,
                duration_ms=int(time.time() * 1000) - start_ms,
                error=str(e),
                context=ctx,
            )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get environment statistics.

        NASA Rule 10: 12 LOC (<=60)
        """
        return {
            "query_count": self._query_count,
            "total_tokens": self._total_tokens,
            "cache_size": len(self._cache),
            "config": {
                "max_depth": self.config.max_depth,
                "max_tokens": self.config.max_tokens,
                "sandbox_mode": self.config.sandbox_mode,
            },
        }

    def clear_cache(self) -> int:
        """Clear the query cache. Returns number of items cleared."""
        count = len(self._cache)
        self._cache = {}
        logger.debug(f"Cleared {count} cached items")
        return count
