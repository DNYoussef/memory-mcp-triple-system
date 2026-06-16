"""Failure Clustering Service for IMPROVE-003.

Clusters similar failures for training data generation.

WHO: finetune:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-003)
"""

import logging
import re
from collections import defaultdict
from typing import Dict, Any, List, Optional, Set

from src.services.finetune.finetune_schema import (
    FailureRecord,
    FailureCategory,
    FailureCluster,
)

logger = logging.getLogger(__name__)


class FailureClusteringService:
    """Clusters similar failures for fine-tuning.

    Uses multiple signals:
    - Error type similarity
    - Input text similarity (simple token overlap)
    - Category matching
    - Temporal proximity
    """

    def __init__(
        self,
        similarity_threshold: float = 0.3,
        min_cluster_size: int = 2,
    ):
        """Initialize clustering service.

        Args:
            similarity_threshold: Minimum similarity for clustering
            min_cluster_size: Minimum failures per cluster
        """
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
        self._clusters: List[FailureCluster] = []

    def cluster_failures(
        self,
        failures: List[FailureRecord],
    ) -> List[FailureCluster]:
        """Cluster similar failures.

        Args:
            failures: Failures to cluster

        Returns:
            List of failure clusters
        """
        if not failures:
            return []

        # Group by category first
        by_category: Dict[FailureCategory, List[FailureRecord]] = defaultdict(list)
        for failure in failures:
            by_category[failure.category].append(failure)

        clusters = []

        for category, cat_failures in by_category.items():
            # Sub-cluster by error type
            by_error_type: Dict[str, List[FailureRecord]] = defaultdict(list)
            for failure in cat_failures:
                by_error_type[failure.error_type].append(failure)

            for error_type, type_failures in by_error_type.items():
                # Further cluster by input similarity
                sub_clusters = self._cluster_by_similarity(type_failures)

                for sub_cluster in sub_clusters:
                    if len(sub_cluster) >= self.min_cluster_size:
                        cluster = self._create_cluster(
                            failures=sub_cluster,
                            category=category,
                            error_type=error_type,
                        )
                        clusters.append(cluster)

        # Sort by impact score
        clusters.sort(key=lambda c: c.impact_score, reverse=True)

        self._clusters = clusters
        return clusters

    def _cluster_by_similarity(
        self,
        failures: List[FailureRecord],
    ) -> List[List[FailureRecord]]:
        """Cluster failures by input similarity.

        Uses simple greedy clustering with token overlap.

        Args:
            failures: Failures to cluster

        Returns:
            List of failure groups
        """
        if len(failures) <= 1:
            return [failures] if failures else []

        # Tokenize inputs
        tokenized = []
        for failure in failures:
            tokens = set(self._tokenize(failure.input_text))
            tokenized.append((failure, tokens))

        # Greedy clustering
        clusters: List[List[FailureRecord]] = []
        used: Set[str] = set()

        for i, (failure, tokens) in enumerate(tokenized):
            if failure.failure_id in used:
                continue

            cluster = [failure]
            used.add(failure.failure_id)

            for j, (other_failure, other_tokens) in enumerate(tokenized[i + 1 :]):
                if other_failure.failure_id in used:
                    continue

                similarity = self._jaccard_similarity(tokens, other_tokens)
                if similarity >= self.similarity_threshold:
                    cluster.append(other_failure)
                    used.add(other_failure.failure_id)

            clusters.append(cluster)

        return clusters

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for similarity comparison.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        if not text:
            return []

        # Simple word tokenization
        words = re.findall(r"\b\w+\b", text.lower())

        # Filter short words and stopwords
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "to", "of", "and", "in"}
        return [w for w in words if len(w) > 2 and w not in stopwords]

    def _jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """Calculate Jaccard similarity between two sets.

        Args:
            set1: First set
            set2: Second set

        Returns:
            Similarity score 0-1
        """
        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _create_cluster(
        self,
        failures: List[FailureRecord],
        category: FailureCategory,
        error_type: str,
    ) -> FailureCluster:
        """Create a failure cluster from grouped failures.

        Args:
            failures: Failures in cluster
            category: Failure category
            error_type: Error type

        Returns:
            Created cluster
        """
        timestamps = [f.timestamp for f in failures]

        # Calculate impact score
        # Higher for: more failures, lower confidence, recent occurrence
        avg_confidence = sum(f.confidence for f in failures) / len(failures)
        recency_factor = 1.0  # Could calculate based on timestamps
        impact_score = len(failures) * (1 - avg_confidence) * recency_factor

        # Extract common features
        common_features = self._extract_common_features(failures)

        # Generate pattern description
        pattern_desc = self._generate_pattern_description(
            category=category,
            error_type=error_type,
            count=len(failures),
            common_features=common_features,
        )

        return FailureCluster(
            category=category,
            pattern_description=pattern_desc,
            failure_ids=[f.failure_id for f in failures],
            count=len(failures),
            first_seen=min(timestamps),
            last_seen=max(timestamps),
            similarity_score=self._calculate_cluster_similarity(failures),
            common_features=common_features,
            impact_score=impact_score,
        )

    def _extract_common_features(
        self,
        failures: List[FailureRecord],
    ) -> Dict[str, Any]:
        """Extract common features from failures.

        Args:
            failures: Failures to analyze

        Returns:
            Common features dictionary
        """
        features: Dict[str, Any] = {}

        # Common tokens in inputs
        all_tokens: List[Set[str]] = [
            set(self._tokenize(f.input_text)) for f in failures
        ]
        if all_tokens:
            common_tokens = all_tokens[0]
            for tokens in all_tokens[1:]:
                common_tokens &= tokens
            features["common_input_tokens"] = list(common_tokens)[:10]

        # Average input length
        lengths = [len(f.input_text) for f in failures if f.input_text]
        if lengths:
            features["avg_input_length"] = sum(lengths) / len(lengths)

        # Correction rate
        corrected = sum(1 for f in failures if f.was_corrected)
        features["correction_rate"] = corrected / len(failures)

        # Average confidence
        confidences = [f.confidence for f in failures]
        features["avg_confidence"] = sum(confidences) / len(confidences)

        return features

    def _calculate_cluster_similarity(
        self,
        failures: List[FailureRecord],
    ) -> float:
        """Calculate average pairwise similarity in cluster.

        Args:
            failures: Cluster failures

        Returns:
            Average similarity score
        """
        if len(failures) < 2:
            return 1.0

        tokenized = [set(self._tokenize(f.input_text)) for f in failures]
        similarities = []

        for i in range(len(tokenized)):
            for j in range(i + 1, len(tokenized)):
                sim = self._jaccard_similarity(tokenized[i], tokenized[j])
                similarities.append(sim)

        return sum(similarities) / len(similarities) if similarities else 0.0

    def _generate_pattern_description(
        self,
        category: FailureCategory,
        error_type: str,
        count: int,
        common_features: Dict[str, Any],
    ) -> str:
        """Generate human-readable pattern description.

        Args:
            category: Failure category
            error_type: Error type
            count: Number of failures
            common_features: Common features

        Returns:
            Pattern description
        """
        parts = [f"{count} {category.value} failures"]

        if error_type:
            parts.append(f"with error type '{error_type}'")

        common_tokens = common_features.get("common_input_tokens", [])
        if common_tokens:
            parts.append(f"containing tokens: {', '.join(common_tokens[:3])}")

        avg_conf = common_features.get("avg_confidence", 0)
        if avg_conf < 0.5:
            parts.append("(low confidence)")

        return " ".join(parts)

    def get_significant_clusters(
        self,
        min_impact: float = 0.5,
    ) -> List[FailureCluster]:
        """Get clusters with significant impact.

        Args:
            min_impact: Minimum impact score

        Returns:
            Significant clusters
        """
        return [c for c in self._clusters if c.impact_score >= min_impact]

    def get_cluster_by_id(self, cluster_id: str) -> Optional[FailureCluster]:
        """Get cluster by ID.

        Args:
            cluster_id: Cluster ID

        Returns:
            Cluster or None
        """
        for cluster in self._clusters:
            if cluster.cluster_id == cluster_id:
                return cluster
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get clustering statistics."""
        return {
            "total_clusters": len(self._clusters),
            "significant_clusters": len(self.get_significant_clusters()),
            "avg_cluster_size": (
                sum(c.count for c in self._clusters) / len(self._clusters)
                if self._clusters
                else 0
            ),
        }

    def clear(self) -> None:
        """Clear all clusters."""
        self._clusters.clear()
