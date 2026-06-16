"""
RLM-Powered Learning Aggregator.

RLM-015: Enhances Loop 3 meta-optimization with recursive learning aggregation.
Aggregates ALL expertise:{} and findings:{} entries recursively.

Key Features:
- Recursive namespace traversal
- Pattern clustering across learnings
- Expertise gap detection
- Optimization recommendations

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from collections import defaultdict
from loguru import logger

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


@dataclass
class AggregatedLearning:
    """Aggregated learning from multiple sources.

    RLM-015: Combines similar learnings into clusters.

    Attributes:
        cluster_id: Unique cluster identifier
        representative: Representative learning content
        count: Number of learnings in cluster
        avg_confidence: Average confidence
        sources: List of source sessions
        namespaces: Namespaces contributing to cluster
        domains: Domains involved
    """
    cluster_id: str
    representative: str
    count: int
    avg_confidence: float
    sources: List[str] = field(default_factory=list)
    namespaces: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cluster_id": self.cluster_id,
            "representative": self.representative,
            "count": self.count,
            "avg_confidence": self.avg_confidence,
            "sources": self.sources,
            "namespaces": self.namespaces,
            "domains": self.domains,
        }


@dataclass
class ExpertiseGap:
    """A detected gap in expertise coverage.

    RLM-015: Identifies areas with low/no coverage.

    Attributes:
        domain: Domain with gap
        topic: Specific topic
        gap_type: missing, outdated, or low_confidence
        recommendation: Suggested action
    """
    domain: str
    topic: str
    gap_type: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "domain": self.domain,
            "topic": self.topic,
            "gap_type": self.gap_type,
            "recommendation": self.recommendation,
        }


@dataclass
class OptimizationRecommendation:
    """Recommendation for Loop 3 optimization.

    RLM-015: Actionable optimization based on aggregation.

    Attributes:
        priority: HIGH, MEDIUM, or LOW
        category: cascade, skill, agent, or mode
        action: What to do
        rationale: Why this is recommended
        affected_components: Components affected
    """
    priority: str
    category: str
    action: str
    rationale: str
    affected_components: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "priority": self.priority,
            "category": self.category,
            "action": self.action,
            "rationale": self.rationale,
            "affected_components": self.affected_components,
        }


class RLMLearningAggregator:
    """
    RLM-015: RLM-powered learning aggregator for Loop 3.

    Recursively aggregates learnings from expertise:{} and findings:{}
    namespaces to power meta-optimization cycles.

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    # Memory MCP paths (env-first, portable fallbacks; no hardcoded host paths)
    MEMORY_MCP_DATA_PATH = os.getenv("MEMORY_MCP_DATA_DIR") or str(Path.home() / ".claude" / "memory-mcp-data")
    MEMORY_MCP_PROJECT_PATH = os.getenv("MEMORY_MCP_PROJECT_DIR") or str(Path(__file__).resolve().parents[3])

    # Namespaces to aggregate
    AGGREGATE_NAMESPACES = [
        "expertise",
        "findings",
        "sessions/reflect",
        "skills",
        "decisions",
    ]

    def __init__(self):
        """Initialize learning aggregator."""
        self._kv_store = None
        self._aggregation_count = 0

        logger.info("RLMLearningAggregator initialized")

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

    def aggregate_all(
        self,
        days: int = 30,
        min_confidence: float = 0.3
    ) -> Dict[str, Any]:
        """
        RLM-015: Recursively aggregate all learnings.

        Args:
            days: How far back to aggregate
            min_confidence: Minimum confidence threshold

        Returns:
            Dict with aggregated learnings, clusters, and stats

        NASA Rule 10: 50 LOC (<=60)
        """
        kv = self._get_kv_store()
        if not kv:
            return {"error": "KV store not available"}

        self._aggregation_count += 1
        all_entries: List[Dict[str, Any]] = []
        namespace_counts: Dict[str, int] = defaultdict(int)

        cutoff = datetime.utcnow() - timedelta(days=days)

        # Recursively collect from all namespaces
        for ns in self.AGGREGATE_NAMESPACES:
            try:
                keys = kv.list_keys(ns)
                for key in keys[:1000]:  # Limit per namespace
                    value = kv.get(key)
                    if not value:
                        continue

                    # Filter by confidence
                    conf = value.get("confidence", 0.5)
                    if conf < min_confidence:
                        continue

                    # Filter by date
                    timestamp = value.get("WHEN", value.get("timestamp", ""))
                    if timestamp:
                        try:
                            ts = datetime.fromisoformat(timestamp.replace("Z", ""))
                            if ts < cutoff:
                                continue
                        except Exception:
                            pass

                    value["_namespace"] = ns
                    value["_key"] = key
                    all_entries.append(value)
                    namespace_counts[ns] += 1

            except Exception as e:
                logger.debug(f"Error scanning namespace {ns}: {e}")

        # Cluster similar entries
        clusters = self._cluster_learnings(all_entries)

        return {
            "total_entries": len(all_entries),
            "namespace_counts": dict(namespace_counts),
            "clusters": [c.to_dict() for c in clusters],
            "cluster_count": len(clusters),
            "days_aggregated": days,
            "min_confidence": min_confidence,
        }

    def _cluster_learnings(
        self,
        entries: List[Dict[str, Any]],
        similarity_threshold: float = 0.4
    ) -> List[AggregatedLearning]:
        """
        Cluster similar learnings together.

        Args:
            entries: List of learning entries
            similarity_threshold: Min similarity for clustering

        Returns:
            List of aggregated learning clusters

        NASA Rule 10: 55 LOC (<=60)
        """
        if not entries:
            return []

        clusters: List[AggregatedLearning] = []
        used: Set[int] = set()

        for i, entry in enumerate(entries):
            if i in used:
                continue

            content = str(entry.get("content", entry.get("learning", "")))
            content_words = set(content.lower().split())

            if not content_words:
                continue

            # Find similar entries
            cluster_entries = [entry]
            cluster_sources = [entry.get("session_id", entry.get("WHO", "unknown"))]
            cluster_namespaces = [entry.get("_namespace", "unknown")]
            cluster_domains = [entry.get("domain", "unknown")]
            used.add(i)

            for j, other in enumerate(entries[i + 1:], i + 1):
                if j in used:
                    continue

                other_content = str(other.get("content", other.get("learning", "")))
                other_words = set(other_content.lower().split())

                if not other_words:
                    continue

                # Calculate similarity
                common = content_words.intersection(other_words)
                union = content_words.union(other_words)
                similarity = len(common) / len(union) if union else 0

                if similarity >= similarity_threshold:
                    cluster_entries.append(other)
                    cluster_sources.append(other.get("session_id", other.get("WHO", "unknown")))
                    cluster_namespaces.append(other.get("_namespace", "unknown"))
                    cluster_domains.append(other.get("domain", "unknown"))
                    used.add(j)

            # Create cluster
            avg_conf = sum(e.get("confidence", 0.5) for e in cluster_entries) / len(cluster_entries)

            clusters.append(AggregatedLearning(
                cluster_id=f"CL-{len(clusters):04d}",
                representative=content[:200],
                count=len(cluster_entries),
                avg_confidence=avg_conf,
                sources=list(set(cluster_sources))[:10],
                namespaces=list(set(cluster_namespaces)),
                domains=list(set(cluster_domains)),
            ))

        # Sort by count (most common first)
        clusters.sort(key=lambda c: c.count, reverse=True)
        return clusters[:100]  # Limit clusters

    def detect_expertise_gaps(
        self,
        expected_domains: Optional[List[str]] = None
    ) -> List[ExpertiseGap]:
        """
        RLM-015: Detect gaps in expertise coverage.

        Args:
            expected_domains: Expected domains to check

        Returns:
            List of detected expertise gaps

        NASA Rule 10: 45 LOC (<=60)
        """
        kv = self._get_kv_store()
        if not kv:
            return []

        gaps: List[ExpertiseGap] = []

        # Default expected domains
        if not expected_domains:
            expected_domains = [
                "coding", "python", "typescript", "testing",
                "architecture", "security", "performance",
                "documentation", "communication", "workflow"
            ]

        # Check what domains exist
        try:
            keys = kv.list_keys("expertise")
            existing_domains = set()

            for key in keys:
                parts = key.split(":")
                if len(parts) >= 2:
                    existing_domains.add(parts[1])

        except Exception:
            existing_domains = set()

        # Find missing domains
        for domain in expected_domains:
            if domain not in existing_domains:
                gaps.append(ExpertiseGap(
                    domain=domain,
                    topic="general",
                    gap_type="missing",
                    recommendation=f"Create expertise entries for {domain} domain"
                ))

        # Check for outdated entries (older than 30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)
        for key in keys[:500] if 'keys' in dir() else []:
            try:
                value = kv.get(key)
                if not value:
                    continue

                timestamp = value.get("WHEN", "")
                if timestamp:
                    ts = datetime.fromisoformat(timestamp.replace("Z", ""))
                    if ts < cutoff:
                        parts = key.split(":")
                        gaps.append(ExpertiseGap(
                            domain=parts[1] if len(parts) > 1 else "unknown",
                            topic=parts[2] if len(parts) > 2 else "unknown",
                            gap_type="outdated",
                            recommendation="Update or refresh this expertise entry"
                        ))
            except Exception:
                continue

        return gaps

    def generate_recommendations(
        self,
        aggregation_result: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """
        RLM-015: Generate optimization recommendations.

        Args:
            aggregation_result: Output from aggregate_all()

        Returns:
            List of optimization recommendations

        NASA Rule 10: 55 LOC (<=60)
        """
        recommendations: List[OptimizationRecommendation] = []
        clusters = aggregation_result.get("clusters", [])

        # High-frequency patterns -> skill updates
        for cluster in clusters[:10]:
            if cluster.get("count", 0) >= 5:
                recommendations.append(OptimizationRecommendation(
                    priority="HIGH",
                    category="skill",
                    action=f"Add to LEARNED PATTERNS: {cluster.get('representative', '')[:80]}",
                    rationale=f"Pattern appeared {cluster.get('count')} times",
                    affected_components=cluster.get("domains", []),
                ))

        # Cross-namespace patterns -> cascade updates
        for cluster in clusters:
            if len(cluster.get("namespaces", [])) >= 3:
                recommendations.append(OptimizationRecommendation(
                    priority="MEDIUM",
                    category="cascade",
                    action="Update cascade config based on cross-domain pattern",
                    rationale=f"Pattern spans {len(cluster.get('namespaces', []))} namespaces",
                    affected_components=cluster.get("namespaces", []),
                ))

        # Low total entries -> increase reflection
        total = aggregation_result.get("total_entries", 0)
        if total < 10:
            recommendations.append(OptimizationRecommendation(
                priority="HIGH",
                category="mode",
                action="Enable auto-reflection (/reflect-on)",
                rationale=f"Only {total} learnings captured - increase session reflection",
                affected_components=["reflect-skill"],
            ))

        # Namespace imbalance -> targeted learning
        ns_counts = aggregation_result.get("namespace_counts", {})
        if ns_counts:
            max_ns = max(ns_counts.values()) if ns_counts else 0
            for ns, count in ns_counts.items():
                if count < max_ns * 0.1:  # Less than 10% of max
                    recommendations.append(OptimizationRecommendation(
                        priority="LOW",
                        category="agent",
                        action=f"Increase {ns} namespace contributions",
                        rationale=f"Only {count} entries vs {max_ns} in other namespaces",
                        affected_components=[ns],
                    ))

        # Sort by priority
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 3))

        return recommendations

    def prepare_loop3_input(
        self,
        days: int = 3
    ) -> Dict[str, Any]:
        """
        RLM-015: Prepare complete input for Loop 3 cycle.

        Args:
            days: Days to aggregate

        Returns:
            Complete input for meta-optimization

        NASA Rule 10: 25 LOC (<=60)
        """
        aggregation = self.aggregate_all(days=days)
        gaps = self.detect_expertise_gaps()
        recommendations = self.generate_recommendations(aggregation)

        return {
            "aggregation": aggregation,
            "expertise_gaps": [g.to_dict() for g in gaps],
            "recommendations": [r.to_dict() for r in recommendations],
            "summary": {
                "total_learnings": aggregation.get("total_entries", 0),
                "clusters_found": aggregation.get("cluster_count", 0),
                "gaps_detected": len(gaps),
                "recommendations_count": len(recommendations),
                "high_priority_count": sum(1 for r in recommendations if r.priority == "HIGH"),
            },
            "prepared_at": datetime.utcnow().isoformat(),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregator statistics."""
        return {
            "aggregation_count": self._aggregation_count,
            "kv_connected": self._kv_store is not None,
            "namespaces_scanned": len(self.AGGREGATE_NAMESPACES),
        }


# CLI interface
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="RLM Learning Aggregator")
    parser.add_argument("--days", "-d", type=int, default=3, help="Days to aggregate")
    parser.add_argument("--full", "-f", action="store_true", help="Full Loop 3 input")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    args = parser.parse_args()

    aggregator = RLMLearningAggregator()

    if args.full:
        result = aggregator.prepare_loop3_input(days=args.days)
    else:
        result = aggregator.aggregate_all(days=args.days)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'='*60}")
        print("!! RLM LOOP 3 LEARNING AGGREGATION !!")
        print(f"{'='*60}")
        print(f"Total Entries: {result.get('aggregation', result).get('total_entries', result.get('total_entries', 0))}")
        print(f"Clusters Found: {result.get('aggregation', result).get('cluster_count', result.get('cluster_count', 0))}")

        if "recommendations" in result:
            print(f"\nRecommendations ({len(result['recommendations'])}):")
            for r in result["recommendations"][:5]:
                print(f"  [{r['priority']}] {r['action'][:60]}...")

        print(f"{'='*60}")
