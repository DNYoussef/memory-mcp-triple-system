"""
RLM Search Tools for Memory MCP.

RLM-006: Search tools for Memory MCP integration.
Provides specialized search functions for RLM recursive queries.

Key Tools:
- search_by_namespace(): Search by Memory MCP namespace prefix
- search_by_time_range(): Search by creation/modification time
- search_by_content(): Full-text content search
- search_graph_edges(): Search graph edges by relation type

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from loguru import logger


@dataclass
class SearchResult:
    """Result from a search tool.

    Attributes:
        id: Unique identifier
        content: Text content
        source: Source type (kv, graph, vector)
        namespace: Memory MCP namespace
        score: Relevance score (0-1)
        metadata: Additional metadata
        timestamp: When the item was created/modified
    """

    id: str
    content: str
    source: str
    namespace: str
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "namespace": self.namespace,
            "score": self.score,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class TimeRange:
    """Time range for temporal searches.

    Attributes:
        start: Start datetime (inclusive)
        end: End datetime (inclusive)
    """

    start: Optional[datetime] = None
    end: Optional[datetime] = None

    @classmethod
    def last_hours(cls, hours: int) -> "TimeRange":
        """Create range for last N hours."""
        now = datetime.utcnow()
        return cls(start=now - timedelta(hours=hours), end=now)

    @classmethod
    def last_days(cls, days: int) -> "TimeRange":
        """Create range for last N days."""
        now = datetime.utcnow()
        return cls(start=now - timedelta(days=days), end=now)

    def contains(self, timestamp: str) -> bool:
        """Check if timestamp falls within range."""
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", ""))
            if self.start and dt < self.start:
                return False
            if self.end and dt > self.end:
                return False
            return True
        except (ValueError, TypeError):
            return True  # Include if timestamp is invalid


@dataclass
class GraphEdgeFilter:
    """Filter for graph edge searches.

    Attributes:
        relation_type: Edge relation/label to match
        source_type: Source node type filter
        target_type: Target node type filter
        bidirectional: Search both directions
    """

    relation_type: Optional[str] = None
    source_type: Optional[str] = None
    target_type: Optional[str] = None
    bidirectional: bool = True


class RLMSearchTools:
    """
    RLM-006: Search tools for Memory MCP integration.

    Provides specialized search functions that can be used
    by RLM for recursive exploration of Memory MCP data.

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    def __init__(
        self,
        kv_data: Optional[Dict[str, Any]] = None,
        graph_data: Optional[Dict[str, Any]] = None,
        vector_search_fn: Optional[Callable] = None,
    ):
        """
        Initialize search tools.

        Args:
            kv_data: KV store data dictionary
            graph_data: Graph data with nodes/edges
            vector_search_fn: Optional vector search function

        NASA Rule 10: 12 LOC (<=60)
        """
        self._kv_data = kv_data or {}
        self._graph_data = graph_data or {}
        self._vector_search = vector_search_fn
        self._search_count = 0

        logger.info(
            f"RLMSearchTools initialized: kv={len(self._kv_data)}, graph_nodes={len(self._graph_data.get('nodes', []))}"
        )

    def search_by_namespace(
        self, namespace: str, limit: int = 50, exact_match: bool = False
    ) -> List[SearchResult]:
        """
        Search by Memory MCP namespace prefix.

        Namespaces follow pattern: category:subcategory:item
        Examples: expertise:python:patterns, findings:security:high

        Args:
            namespace: Namespace prefix to match
            limit: Maximum results
            exact_match: Require exact namespace match

        Returns:
            List of matching results

        NASA Rule 10: 30 LOC (<=60)
        """
        results = []
        namespace_lower = namespace.lower()

        for key, value in self._kv_data.items():
            key_lower = key.lower()

            # Match logic
            if exact_match:
                matches = key_lower == namespace_lower
            else:
                matches = key_lower.startswith(namespace_lower)

            if matches:
                content = json.dumps(value) if isinstance(value, dict) else str(value)
                ns_parts = key.split(":")
                results.append(
                    SearchResult(
                        id=key,
                        content=content[:1000],
                        source="kv",
                        namespace=ns_parts[0] if ns_parts else "default",
                        score=1.0 if exact_match else 0.9,
                        metadata={"full_key": key},
                        timestamp=value.get("created_at")
                        if isinstance(value, dict)
                        else None,
                    )
                )

                if len(results) >= limit:
                    break

        self._search_count += 1
        logger.debug(f"search_by_namespace({namespace}): {len(results)} results")
        return results

    def search_by_time_range(
        self,
        time_range: TimeRange,
        namespace_filter: Optional[str] = None,
        limit: int = 100,
    ) -> List[SearchResult]:
        """
        Search by creation/modification time range.

        Args:
            time_range: Time range to search within
            namespace_filter: Optional namespace prefix filter
            limit: Maximum results

        Returns:
            List of results within time range

        NASA Rule 10: 40 LOC (<=60)
        """
        results = []

        for key, value in self._kv_data.items():
            # Namespace filter
            if namespace_filter and not key.lower().startswith(
                namespace_filter.lower()
            ):
                continue

            # Extract timestamp
            timestamp = None
            if isinstance(value, dict):
                timestamp = (
                    value.get("created_at")
                    or value.get("timestamp")
                    or value.get("when")
                )

            # Check time range
            if timestamp and not time_range.contains(timestamp):
                continue

            content = json.dumps(value) if isinstance(value, dict) else str(value)
            ns_parts = key.split(":")
            results.append(
                SearchResult(
                    id=key,
                    content=content[:1000],
                    source="kv",
                    namespace=ns_parts[0] if ns_parts else "default",
                    score=0.8,
                    metadata={"full_key": key},
                    timestamp=timestamp,
                )
            )

            if len(results) >= limit:
                break

        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.timestamp or "", reverse=True)

        self._search_count += 1
        logger.debug(f"search_by_time_range: {len(results)} results")
        return results

    def search_by_content(
        self,
        query: str,
        case_sensitive: bool = False,
        use_regex: bool = False,
        limit: int = 50,
    ) -> List[SearchResult]:
        """
        Full-text content search across KV store.

        Args:
            query: Search query or regex pattern
            case_sensitive: Enable case-sensitive matching
            use_regex: Treat query as regex pattern
            limit: Maximum results

        Returns:
            List of matching results

        NASA Rule 10: 45 LOC (<=60)
        """
        results = []

        # Compile pattern
        if use_regex:
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                pattern = re.compile(query, flags)
            except re.error:
                logger.warning(f"Invalid regex: {query}")
                return []
        else:
            pattern = None
            if not case_sensitive:
                query = query.lower()

        for key, value in self._kv_data.items():
            content = json.dumps(value) if isinstance(value, dict) else str(value)
            search_content = content if case_sensitive else content.lower()

            # Match logic
            if pattern:
                match = pattern.search(content)
            else:
                match = query in search_content

            if match:
                ns_parts = key.split(":")
                results.append(
                    SearchResult(
                        id=key,
                        content=content[:1000],
                        source="kv",
                        namespace=ns_parts[0] if ns_parts else "default",
                        score=0.85,
                        metadata={
                            "full_key": key,
                            "match_type": "regex" if use_regex else "substring",
                        },
                        timestamp=value.get("created_at")
                        if isinstance(value, dict)
                        else None,
                    )
                )

                if len(results) >= limit:
                    break

        self._search_count += 1
        logger.debug(f"search_by_content({query[:30]}...): {len(results)} results")
        return results

    def search_graph_edges(
        self, edge_filter: GraphEdgeFilter, limit: int = 100
    ) -> List[SearchResult]:
        """
        Search graph edges by relation type and node filters.

        Args:
            edge_filter: Filter criteria for edges
            limit: Maximum results

        Returns:
            List of matching edge results

        NASA Rule 10: 50 LOC (<=60)
        """
        results = []
        edges = self._graph_data.get("edges", [])
        nodes = {str(n.get("id")): n for n in self._graph_data.get("nodes", [])}

        for edge in edges:
            source_id = str(edge.get("source", ""))
            target_id = str(edge.get("target", ""))
            relation = edge.get("label", "") or edge.get("relation", "")

            # Relation filter
            if edge_filter.relation_type:
                if edge_filter.relation_type.lower() not in relation.lower():
                    continue

            # Source type filter
            source_node = nodes.get(source_id, {})
            if edge_filter.source_type:
                if (
                    edge_filter.source_type.lower()
                    not in str(source_node.get("type", "")).lower()
                ):
                    continue

            # Target type filter
            target_node = nodes.get(target_id, {})
            if edge_filter.target_type:
                if (
                    edge_filter.target_type.lower()
                    not in str(target_node.get("type", "")).lower()
                ):
                    continue

            # Build result
            content = f"{source_node.get('label', source_id)} --[{relation}]--> {target_node.get('label', target_id)}"
            results.append(
                SearchResult(
                    id=f"edge:{source_id}:{target_id}",
                    content=content,
                    source="graph",
                    namespace="graph_edges",
                    score=0.9,
                    metadata={
                        "source_id": source_id,
                        "target_id": target_id,
                        "relation": relation,
                        "edge_data": edge,
                    },
                )
            )

            if len(results) >= limit:
                break

        self._search_count += 1
        logger.debug(f"search_graph_edges: {len(results)} results")
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get search tool statistics."""
        return {
            "search_count": self._search_count,
            "kv_items": len(self._kv_data),
            "graph_nodes": len(self._graph_data.get("nodes", [])),
            "graph_edges": len(self._graph_data.get("edges", [])),
            "has_vector_search": self._vector_search is not None,
        }


# Convenience functions for standalone use


def search_by_namespace(
    kv_data: Dict[str, Any], namespace: str, limit: int = 50, exact_match: bool = False
) -> List[SearchResult]:
    """Search by namespace prefix."""
    tools = RLMSearchTools(kv_data=kv_data)
    return tools.search_by_namespace(namespace, limit, exact_match)


def search_by_time_range(
    kv_data: Dict[str, Any],
    time_range: TimeRange,
    namespace_filter: Optional[str] = None,
    limit: int = 100,
) -> List[SearchResult]:
    """Search by time range."""
    tools = RLMSearchTools(kv_data=kv_data)
    return tools.search_by_time_range(time_range, namespace_filter, limit)


def search_by_content(
    kv_data: Dict[str, Any],
    query: str,
    case_sensitive: bool = False,
    use_regex: bool = False,
    limit: int = 50,
) -> List[SearchResult]:
    """Search by content."""
    tools = RLMSearchTools(kv_data=kv_data)
    return tools.search_by_content(query, case_sensitive, use_regex, limit)


def search_graph_edges(
    graph_data: Dict[str, Any], edge_filter: GraphEdgeFilter, limit: int = 100
) -> List[SearchResult]:
    """Search graph edges."""
    tools = RLMSearchTools(graph_data=graph_data)
    return tools.search_graph_edges(edge_filter, limit)
