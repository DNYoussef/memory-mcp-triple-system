"""
RLM Client for WoundHealer Pattern Matching.

GS-017: Implements RLM (Retrieval Language Model) client for querying Memory MCP.
Queries: findings:* for similar issues, fixes:* for successful solutions,
graph traversal for error->fix paths.

Key Features:
- Query findings namespace for similar issues
- Query fixes namespace for successful solutions
- Graph traversal for error->fix relationships
- Cosine similarity for pattern matching

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict
from loguru import logger

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class Finding:
    """A finding from Memory MCP.

    GS-017: Represents stored issue/error records.

    Attributes:
        finding_id: Unique finding identifier
        agent: Agent that reported finding
        severity: HIGH, MEDIUM, or LOW
        content: Finding description
        timestamp: When found
        project: Project context
        metadata: Additional metadata
    """
    finding_id: str
    agent: str
    severity: str
    content: str
    timestamp: str
    project: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "finding_id": self.finding_id,
            "agent": self.agent,
            "severity": self.severity,
            "content": self.content,
            "timestamp": self.timestamp,
            "project": self.project,
            "metadata": self.metadata,
        }


@dataclass
class Fix:
    """A fix from Memory MCP.

    GS-017: Represents stored fix/solution records.

    Attributes:
        fix_id: Unique fix identifier
        finding_id: Related finding ID
        content: Fix description
        confidence: Success confidence
        timestamp: When applied
        verified: Whether fix was verified
    """
    fix_id: str
    finding_id: str
    content: str
    confidence: float
    timestamp: str
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "fix_id": self.fix_id,
            "finding_id": self.finding_id,
            "content": self.content,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "verified": self.verified,
        }


@dataclass
class PatternMatch:
    """A pattern match result.

    GS-017: Result of pattern matching query.

    Attributes:
        finding: Matched finding
        fix: Associated fix (if any)
        similarity: Cosine similarity score (0.0-1.0)
        match_type: findings, fixes, or graph
    """
    finding: Finding
    fix: Optional[Fix]
    similarity: float
    match_type: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "finding": self.finding.to_dict(),
            "fix": self.fix.to_dict() if self.fix else None,
            "similarity": self.similarity,
            "match_type": self.match_type,
        }


class RLMClient:
    """
    GS-017: RLM Client for WoundHealer pattern matching.

    Queries Memory MCP for similar issues and successful fixes.
    Uses cosine similarity for pattern matching confidence.

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    # Memory MCP paths
    MEMORY_MCP_DATA_PATH = "C:/Users/17175/.claude/memory-mcp-data"
    MEMORY_MCP_PROJECT_PATH = "D:/Projects/memory-mcp-triple-system"

    # Namespace prefixes
    FINDINGS_NAMESPACE = "findings"
    FIXES_NAMESPACE = "fixes"
    GUARD_EVENTS_NAMESPACE = "guard:events"

    def __init__(self):
        """Initialize RLM client."""
        self._kv_store = None
        self._graph_service = None
        self._query_count = 0

        logger.info("RLMClient initialized for WoundHealer")

    def _get_kv_store(self):
        """Lazy load KV store."""
        if self._kv_store is None:
            try:
                sys.path.insert(0, self.MEMORY_MCP_PROJECT_PATH)
                from src.stores.kv_store import KVStore

                db_path = Path(self.MEMORY_MCP_DATA_PATH) / "agent_kv.db"
                self._kv_store = KVStore(str(db_path))
                logger.info(f"KV store loaded: {db_path}")

            except Exception as e:
                logger.error(f"Failed to load KV store: {e}")
                self._kv_store = None

        return self._kv_store

    def _get_graph_service(self):
        """Lazy load graph service."""
        if self._graph_service is None:
            try:
                sys.path.insert(0, self.MEMORY_MCP_PROJECT_PATH)
                from src.services.graph_service import GraphService

                self._graph_service = GraphService(
                    data_dir=self.MEMORY_MCP_DATA_PATH
                )
                self._graph_service.load_graph()
                logger.info("Graph service loaded")

            except Exception as e:
                logger.error(f"Failed to load graph service: {e}")
                self._graph_service = None

        return self._graph_service

    def _cosine_similarity(
        self,
        text1: str,
        text2: str
    ) -> float:
        """
        Calculate cosine similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0.0-1.0)

        NASA Rule 10: 20 LOC (<=60)
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        # Term frequency vectors
        all_words = words1.union(words2)
        vec1 = [1 if w in words1 else 0 for w in all_words]
        vec2 = [1 if w in words2 else 0 for w in all_words]

        # Cosine similarity
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        mag1 = math.sqrt(sum(a * a for a in vec1))
        mag2 = math.sqrt(sum(b * b for b in vec2))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)

    def query_similar_findings(
        self,
        error_description: str,
        severity_filter: Optional[str] = None,
        days: int = 30,
        limit: int = 10
    ) -> List[PatternMatch]:
        """
        GS-017: Query for similar findings/issues.

        Args:
            error_description: Current error to match against
            severity_filter: Filter by severity (HIGH/MEDIUM/LOW)
            days: How far back to search
            limit: Maximum results

        Returns:
            List of pattern matches sorted by similarity

        NASA Rule 10: 55 LOC (<=60)
        """
        kv = self._get_kv_store()
        if not kv:
            return []

        self._query_count += 1
        results: List[PatternMatch] = []
        cutoff = datetime.utcnow() - timedelta(days=days)

        try:
            keys = kv.list_keys(self.FINDINGS_NAMESPACE)
        except Exception:
            keys = []

        for key in keys[:500]:  # Limit scan
            try:
                value = kv.get(key)
                if not value:
                    continue

                # Filter by severity
                sev = value.get("severity", "LOW")
                if severity_filter and sev != severity_filter:
                    continue

                # Filter by date
                timestamp_str = value.get("WHEN", value.get("timestamp", ""))
                if timestamp_str:
                    try:
                        ts = datetime.fromisoformat(timestamp_str.replace("Z", ""))
                        if ts < cutoff:
                            continue
                    except Exception:
                        pass

                # Calculate similarity
                content = str(value.get("content", value.get("description", "")))
                similarity = self._cosine_similarity(error_description, content)

                if similarity >= 0.3:  # Minimum threshold
                    finding = Finding(
                        finding_id=key,
                        agent=value.get("WHO", "").split(":")[-1] if value.get("WHO") else "unknown",
                        severity=sev,
                        content=content,
                        timestamp=timestamp_str,
                        project=value.get("PROJECT", "unknown"),
                        metadata=value.get("metadata", {}),
                    )

                    # Try to find associated fix
                    fix = self._find_fix_for_finding(key)

                    results.append(PatternMatch(
                        finding=finding,
                        fix=fix,
                        similarity=similarity,
                        match_type="findings",
                    ))

            except Exception:
                continue

        # Sort by similarity
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:limit]

    def _find_fix_for_finding(
        self,
        finding_id: str
    ) -> Optional[Fix]:
        """
        Find a fix associated with a finding.

        Args:
            finding_id: Finding ID to search for

        Returns:
            Associated fix or None

        NASA Rule 10: 30 LOC (<=60)
        """
        kv = self._get_kv_store()
        if not kv:
            return None

        try:
            # Search fixes namespace
            keys = kv.list_keys(self.FIXES_NAMESPACE)
            for key in keys[:200]:
                value = kv.get(key)
                if not value:
                    continue

                if value.get("finding_id") == finding_id:
                    return Fix(
                        fix_id=key,
                        finding_id=finding_id,
                        content=str(value.get("content", value.get("fix", ""))),
                        confidence=value.get("confidence", 0.5),
                        timestamp=value.get("WHEN", ""),
                        verified=value.get("verified", False),
                    )

        except Exception:
            pass

        return None

    def query_fixes_by_pattern(
        self,
        error_pattern: str,
        min_confidence: float = 0.5,
        limit: int = 10
    ) -> List[Fix]:
        """
        GS-017: Query successful fixes by error pattern.

        Args:
            error_pattern: Error pattern to match
            min_confidence: Minimum fix confidence
            limit: Maximum results

        Returns:
            List of fixes sorted by confidence

        NASA Rule 10: 40 LOC (<=60)
        """
        kv = self._get_kv_store()
        if not kv:
            return []

        results: List[Fix] = []

        try:
            keys = kv.list_keys(self.FIXES_NAMESPACE)
        except Exception:
            return []

        for key in keys[:500]:
            try:
                value = kv.get(key)
                if not value:
                    continue

                conf = value.get("confidence", 0.5)
                if conf < min_confidence:
                    continue

                # Check if fix matches error pattern
                fix_content = str(value.get("content", value.get("fix", "")))
                error_context = str(value.get("error_context", ""))

                # Match against error pattern
                similarity = max(
                    self._cosine_similarity(error_pattern, fix_content),
                    self._cosine_similarity(error_pattern, error_context)
                )

                if similarity >= 0.3:
                    results.append(Fix(
                        fix_id=key,
                        finding_id=value.get("finding_id", ""),
                        content=fix_content,
                        confidence=conf,
                        timestamp=value.get("WHEN", ""),
                        verified=value.get("verified", False),
                    ))

            except Exception:
                continue

        # Sort by confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:limit]

    def traverse_error_fix_paths(
        self,
        error_type: str,
        max_hops: int = 3
    ) -> List[Dict[str, Any]]:
        """
        GS-017: Graph traversal for error->fix relationships.

        Args:
            error_type: Error type to start from
            max_hops: Maximum graph hops

        Returns:
            List of paths from error to fix

        NASA Rule 10: 45 LOC (<=60)
        """
        graph = self._get_graph_service()
        if not graph:
            return []

        paths: List[Dict[str, Any]] = []

        try:
            # Find nodes matching error type
            error_nodes = []
            for node in graph._graph.nodes():
                node_data = graph._graph.nodes[node]
                node_type = node_data.get("type", "")
                if "error" in node_type.lower() or "finding" in node_type.lower():
                    node_label = node_data.get("label", "")
                    if error_type.lower() in node_label.lower():
                        error_nodes.append(node)

            # BFS to find fix nodes
            for start_node in error_nodes[:10]:
                visited = {start_node}
                queue = [(start_node, [start_node], 0)]

                while queue:
                    current, path, depth = queue.pop(0)
                    if depth >= max_hops:
                        continue

                    # Check neighbors
                    for neighbor in graph._graph.neighbors(current):
                        if neighbor in visited:
                            continue

                        visited.add(neighbor)
                        new_path = path + [neighbor]

                        neighbor_data = graph._graph.nodes[neighbor]
                        neighbor_type = neighbor_data.get("type", "")

                        # Found a fix node
                        if "fix" in neighbor_type.lower():
                            paths.append({
                                "error_node": start_node,
                                "fix_node": neighbor,
                                "path": new_path,
                                "hops": depth + 1,
                                "fix_label": neighbor_data.get("label", ""),
                            })
                        else:
                            queue.append((neighbor, new_path, depth + 1))

        except Exception as e:
            logger.debug(f"Graph traversal error: {e}")

        return paths

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "query_count": self._query_count,
            "kv_connected": self._kv_store is not None,
            "graph_connected": self._graph_service is not None,
        }


# CLI interface
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="RLM Client for WoundHealer")
    parser.add_argument("error", help="Error description to search for")
    parser.add_argument("--severity", "-s", help="Filter by severity")
    parser.add_argument("--days", "-d", type=int, default=30, help="Days to search")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    args = parser.parse_args()

    client = RLMClient()
    matches = client.query_similar_findings(
        error_description=args.error,
        severity_filter=args.severity,
        days=args.days
    )

    if args.json:
        print(json.dumps([m.to_dict() for m in matches], indent=2))
    else:
        print(f"\n{'='*60}")
        print("!! RLM CLIENT: SIMILAR FINDINGS !!")
        print(f"{'='*60}")
        print(f"Query: {args.error[:50]}...")
        print(f"Found: {len(matches)} matches")
        print()

        for i, match in enumerate(matches, 1):
            print(f"[{i}] {match.finding.finding_id}")
            print(f"    Similarity: {match.similarity:.0%}")
            print(f"    Severity: {match.finding.severity}")
            print(f"    Content: {match.finding.content[:60]}...")
            if match.fix:
                print(f"    Fix: {match.fix.content[:60]}...")
            print()

        print(f"{'='*60}")
