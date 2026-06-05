"""
RLM-Powered Session Search Tool.

RLM-014: Enhances /reflect skill with cross-session pattern search.
Finds similar corrections and learnings across entire session history.

Key Features:
- Search Memory MCP for past session learnings
- Find similar corrections using pattern matching
- Aggregate learnings by skill and confidence
- Detect patterns across session history

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


@dataclass
class SessionLearning:
    """A learning extracted from a past session.

    RLM-014: Represents stored learnings from /reflect.

    Attributes:
        skill_name: Skill the learning applies to
        content: The actual learning content
        confidence: Confidence level (0.55-0.90)
        category: HIGH/MEDIUM/LOW
        ground: Evidence source
        session_id: Source session ID
        timestamp: When learning was captured
        project: Project context
    """
    skill_name: str
    content: str
    confidence: float
    category: str
    ground: str
    session_id: str
    timestamp: str
    project: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "skill_name": self.skill_name,
            "content": self.content,
            "confidence": self.confidence,
            "category": self.category,
            "ground": self.ground,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "project": self.project,
        }


@dataclass
class SimilarLearning:
    """A learning similar to the current query.

    RLM-014: Result of similarity search.

    Attributes:
        learning: The matched learning
        similarity_score: How similar (0.0-1.0)
        match_reason: Why it matched
    """
    learning: SessionLearning
    similarity_score: float
    match_reason: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            **self.learning.to_dict(),
            "similarity_score": self.similarity_score,
            "match_reason": self.match_reason,
        }


class RLMSessionSearch:
    """
    RLM-014: RLM-powered session search for /reflect skill.

    Searches across all past session learnings to find similar
    corrections, detect recurring patterns, and aggregate insights.

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    # Memory MCP paths
    MEMORY_MCP_DATA_PATH = "C:/Users/17175/.claude/memory-mcp-data"
    MEMORY_MCP_PROJECT_PATH = "D:/Projects/memory-mcp-triple-system"

    # Namespace prefixes for reflect learnings
    REFLECT_NAMESPACE = "sessions/reflect"
    SKILLS_NAMESPACE = "skills"

    def __init__(self):
        """Initialize session search tool."""
        self._kv_store = None
        self._graph_service = None
        self._search_count = 0

        logger.info("RLMSessionSearch initialized")

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

    def search_similar(
        self,
        query: str,
        skill_name: Optional[str] = None,
        days: int = 30,
        limit: int = 10
    ) -> List[SimilarLearning]:
        """
        RLM-014: Search for similar past learnings.

        Args:
            query: The correction or learning to match
            skill_name: Filter by skill (None = all skills)
            days: How far back to search
            limit: Maximum results

        Returns:
            List of similar learnings

        NASA Rule 10: 55 LOC (<=60)
        """
        kv = self._get_kv_store()
        if not kv:
            return []

        self._search_count += 1
        query_lower = query.lower()
        query_words = set(query_lower.split())

        results: List[SimilarLearning] = []

        # Get all reflect session keys
        prefix = self.REFLECT_NAMESPACE
        if skill_name:
            prefix = f"{self.REFLECT_NAMESPACE}/{skill_name}"

        try:
            keys = kv.list_keys(prefix)
        except Exception:
            keys = []

        cutoff = datetime.utcnow() - timedelta(days=days)

        for key in keys[:500]:  # Limit scan
            try:
                value = kv.get(key)
                if not value:
                    continue

                # Check timestamp
                timestamp_str = value.get("WHEN", value.get("timestamp", ""))
                if timestamp_str:
                    ts = datetime.fromisoformat(timestamp_str.replace("Z", ""))
                    if ts < cutoff:
                        continue

                # Extract learnings from value
                learnings = value.get("x-learnings", [])
                if not learnings:
                    continue

                for learning_data in learnings:
                    content = learning_data.get("content", "")
                    content_lower = content.lower()
                    content_words = set(content_lower.split())

                    # Calculate similarity
                    common = query_words.intersection(content_words)
                    if not common:
                        continue

                    similarity = len(common) / max(len(query_words), len(content_words))

                    if similarity >= 0.3:  # Minimum threshold
                        learning = SessionLearning(
                            skill_name=value.get("x-skill", "unknown"),
                            content=content,
                            confidence=learning_data.get("confidence", 0.5),
                            category=learning_data.get("category", "LOW"),
                            ground=learning_data.get("ground", "unknown"),
                            session_id=value.get("WHO", "").split(":")[-1],
                            timestamp=timestamp_str,
                            project=value.get("PROJECT", "unknown"),
                        )

                        results.append(SimilarLearning(
                            learning=learning,
                            similarity_score=similarity,
                            match_reason=f"Common words: {', '.join(sorted(common)[:5])}",
                        ))

            except Exception:
                continue

        # Sort by similarity
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results[:limit]

    def get_skill_learnings(
        self,
        skill_name: str,
        days: int = 90,
        limit: int = 50
    ) -> List[SessionLearning]:
        """
        RLM-014: Get all learnings for a specific skill.

        Args:
            skill_name: Skill to get learnings for
            days: How far back to search
            limit: Maximum results

        Returns:
            List of learnings for the skill

        NASA Rule 10: 40 LOC (<=60)
        """
        kv = self._get_kv_store()
        if not kv:
            return []

        results: List[SessionLearning] = []
        prefix = f"{self.REFLECT_NAMESPACE}/"

        try:
            keys = kv.list_keys(prefix)
        except Exception:
            return []

        cutoff = datetime.utcnow() - timedelta(days=days)

        for key in keys[:500]:
            try:
                value = kv.get(key)
                if not value:
                    continue

                if value.get("x-skill") != skill_name:
                    continue

                timestamp_str = value.get("WHEN", "")
                if timestamp_str:
                    ts = datetime.fromisoformat(timestamp_str.replace("Z", ""))
                    if ts < cutoff:
                        continue

                for learning_data in value.get("x-learnings", []):
                    results.append(SessionLearning(
                        skill_name=skill_name,
                        content=learning_data.get("content", ""),
                        confidence=learning_data.get("confidence", 0.5),
                        category=learning_data.get("category", "LOW"),
                        ground=learning_data.get("ground", "unknown"),
                        session_id=value.get("WHO", "").split(":")[-1],
                        timestamp=timestamp_str,
                        project=value.get("PROJECT", "unknown"),
                    ))

            except Exception:
                continue

        return results[:limit]

    def detect_recurring_patterns(
        self,
        threshold: int = 3,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        RLM-014: Detect patterns that appear multiple times.

        Finds corrections that have been made repeatedly,
        indicating persistent issues or user preferences.

        Args:
            threshold: Minimum occurrences to be considered a pattern
            days: How far back to search

        Returns:
            List of recurring patterns with occurrence counts

        NASA Rule 10: 50 LOC (<=60)
        """
        kv = self._get_kv_store()
        if not kv:
            return []

        # Group learnings by normalized content
        content_groups: Dict[str, List[SessionLearning]] = {}
        prefix = self.REFLECT_NAMESPACE

        try:
            keys = kv.list_keys(prefix)
        except Exception:
            return []

        cutoff = datetime.utcnow() - timedelta(days=days)

        for key in keys[:500]:
            try:
                value = kv.get(key)
                if not value:
                    continue

                timestamp_str = value.get("WHEN", "")
                if timestamp_str:
                    ts = datetime.fromisoformat(timestamp_str.replace("Z", ""))
                    if ts < cutoff:
                        continue

                for learning_data in value.get("x-learnings", []):
                    content = learning_data.get("content", "").strip().lower()
                    # Normalize: remove punctuation, extra spaces
                    normalized = " ".join(content.split())

                    if normalized not in content_groups:
                        content_groups[normalized] = []

                    content_groups[normalized].append(SessionLearning(
                        skill_name=value.get("x-skill", "unknown"),
                        content=learning_data.get("content", ""),
                        confidence=learning_data.get("confidence", 0.5),
                        category=learning_data.get("category", "LOW"),
                        ground=learning_data.get("ground", "unknown"),
                        session_id=value.get("WHO", "").split(":")[-1],
                        timestamp=timestamp_str,
                        project=value.get("PROJECT", "unknown"),
                    ))

            except Exception:
                continue

        # Filter to threshold
        recurring = []
        for content, learnings in content_groups.items():
            if len(learnings) >= threshold:
                recurring.append({
                    "pattern": learnings[0].content,
                    "occurrences": len(learnings),
                    "skills": list(set(l.skill_name for l in learnings)),
                    "avg_confidence": sum(l.confidence for l in learnings) / len(learnings),
                    "first_seen": min(l.timestamp for l in learnings if l.timestamp),
                    "last_seen": max(l.timestamp for l in learnings if l.timestamp),
                })

        # Sort by occurrence count
        recurring.sort(key=lambda x: x["occurrences"], reverse=True)
        return recurring

    def suggest_escalations(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        RLM-014: Suggest learnings to escalate to higher confidence.

        When a LOW/MEDIUM learning appears multiple times,
        suggest escalating it to a higher confidence level.

        Args:
            days: How far back to search

        Returns:
            List of escalation suggestions

        NASA Rule 10: 30 LOC (<=60)
        """
        patterns = self.detect_recurring_patterns(threshold=2, days=days)

        suggestions = []
        for pattern in patterns:
            avg_conf = pattern.get("avg_confidence", 0.5)
            occurrences = pattern.get("occurrences", 1)

            # Suggest escalation based on occurrence count
            if avg_conf < 0.90 and occurrences >= 3:
                new_conf = min(0.90, avg_conf + 0.15)
                suggestions.append({
                    "pattern": pattern["pattern"],
                    "current_confidence": avg_conf,
                    "suggested_confidence": new_conf,
                    "reason": f"Appeared {occurrences} times across {len(pattern['skills'])} skills",
                    "skills": pattern["skills"],
                })

        return suggestions

    def get_stats(self) -> Dict[str, Any]:
        """Get search statistics."""
        return {
            "search_count": self._search_count,
            "kv_connected": self._kv_store is not None,
            "graph_connected": self._graph_service is not None,
        }


def format_search_results(results: List[SimilarLearning]) -> str:
    """Format search results for display."""
    if not results:
        return "No similar learnings found in past sessions."

    lines = [
        "=" * 60,
        "!! RLM SESSION SEARCH: SIMILAR LEARNINGS !!",
        "=" * 60,
        "",
    ]

    for i, result in enumerate(results, 1):
        lines.extend([
            f"[{i}] Skill: {result.learning.skill_name}",
            f"    Content: {result.learning.content[:100]}...",
            f"    Confidence: {result.learning.category} ({result.learning.confidence:.0%})",
            f"    Similarity: {result.similarity_score:.0%}",
            f"    Match: {result.match_reason}",
            f"    From: {result.learning.session_id} ({result.learning.timestamp[:10]})",
            "",
        ])

    lines.extend([
        "=" * 60,
        f"Found {len(results)} similar learnings",
        "=" * 60,
    ])

    return "\n".join(lines)


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RLM Session Search")
    parser.add_argument("query", help="Learning or correction to search for")
    parser.add_argument("--skill", "-s", help="Filter by skill name")
    parser.add_argument("--days", "-d", type=int, default=30, help="Days to search back")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    args = parser.parse_args()

    searcher = RLMSessionSearch()
    results = searcher.search_similar(
        query=args.query,
        skill_name=args.skill,
        days=args.days
    )

    if args.json:
        import json
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        print(format_search_results(results))
