"""Training Data Recommender for IMPROVE-003.

Generates training data recommendations from failure clusters.

WHO: finetune:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-003)
"""

import logging
from typing import Dict, Any, List, Optional

from src.services.finetune.finetune_schema import (
    FailureRecord,
    FailureCategory,
    FailureCluster,
    TrainingCandidate,
    TrainingRecommendation,
    RecommendationPriority,
    DatasetType,
)

logger = logging.getLogger(__name__)


# Category to dataset type mapping
CATEGORY_DATASET_MAP = {
    FailureCategory.MODE_DETECTION: DatasetType.CLASSIFICATION,
    FailureCategory.ENTITY_EXTRACTION: DatasetType.EXTRACTION,
    FailureCategory.TAG_ASSIGNMENT: DatasetType.CLASSIFICATION,
    FailureCategory.CONFIDENCE_SCORING: DatasetType.RANKING,
    FailureCategory.GRAPH_QUERY: DatasetType.GENERATION,
    FailureCategory.RETRIEVAL: DatasetType.RANKING,
    FailureCategory.CLASSIFICATION: DatasetType.CLASSIFICATION,
    FailureCategory.UNKNOWN: DatasetType.CLASSIFICATION,
}


# Recommendation templates by category
RECOMMENDATION_TEMPLATES = {
    FailureCategory.MODE_DETECTION: {
        "title": "Mode detection training data",
        "description": "Examples for improving mode detection accuracy",
        "effort": "small",
        "improvement_estimate": 0.05,  # 5% expected improvement
    },
    FailureCategory.ENTITY_EXTRACTION: {
        "title": "Entity extraction training data",
        "description": "Examples for improving entity recognition",
        "effort": "medium",
        "improvement_estimate": 0.08,
    },
    FailureCategory.TAG_ASSIGNMENT: {
        "title": "Tag assignment training data",
        "description": "Examples for improving tag suggestions",
        "effort": "small",
        "improvement_estimate": 0.06,
    },
    FailureCategory.CONFIDENCE_SCORING: {
        "title": "Confidence calibration data",
        "description": "Examples for improving confidence score accuracy",
        "effort": "medium",
        "improvement_estimate": 0.10,
    },
    FailureCategory.GRAPH_QUERY: {
        "title": "Graph query training data",
        "description": "Examples for improving graph query generation",
        "effort": "large",
        "improvement_estimate": 0.12,
    },
    FailureCategory.RETRIEVAL: {
        "title": "Retrieval ranking data",
        "description": "Examples for improving retrieval relevance",
        "effort": "medium",
        "improvement_estimate": 0.07,
    },
    FailureCategory.CLASSIFICATION: {
        "title": "General classification data",
        "description": "Examples for improving classification accuracy",
        "effort": "small",
        "improvement_estimate": 0.05,
    },
}


class TrainingDataRecommender:
    """Generates training data recommendations.

    Takes failure clusters and generates:
    - Training candidate examples
    - Priority-ranked recommendations
    - Dataset type suggestions
    """

    def __init__(self):
        """Initialize training data recommender."""
        self._recommendations: List[TrainingRecommendation] = []
        self._generated_count = 0

    def generate_recommendations(
        self,
        clusters: List[FailureCluster],
        failures: List[FailureRecord],
    ) -> List[TrainingRecommendation]:
        """Generate training recommendations from clusters.

        Args:
            clusters: Failure clusters
            failures: Original failure records

        Returns:
            List of training recommendations
        """
        recommendations = []

        # Create failure lookup
        failure_lookup = {f.failure_id: f for f in failures}

        for cluster in clusters:
            if not cluster.is_significant:
                continue

            recommendation = self._generate_recommendation(
                cluster=cluster,
                failure_lookup=failure_lookup,
            )

            if recommendation:
                recommendations.append(recommendation)
                self._generated_count += 1

        # Sort by priority
        recommendations.sort(key=lambda r: r.priority.value)

        self._recommendations = recommendations
        return recommendations

    def _generate_recommendation(
        self,
        cluster: FailureCluster,
        failure_lookup: Dict[str, FailureRecord],
    ) -> Optional[TrainingRecommendation]:
        """Generate recommendation for a single cluster.

        Args:
            cluster: Failure cluster
            failure_lookup: Failure ID to record lookup

        Returns:
            Training recommendation or None
        """
        # Get template
        template = RECOMMENDATION_TEMPLATES.get(
            cluster.category,
            RECOMMENDATION_TEMPLATES[FailureCategory.CLASSIFICATION],
        )

        # Determine dataset type
        dataset_type = CATEGORY_DATASET_MAP.get(
            cluster.category,
            DatasetType.CLASSIFICATION,
        )

        # Calculate priority based on impact
        priority = self._calculate_priority(cluster)

        # Generate training candidates
        candidates = self._generate_candidates(
            cluster=cluster,
            failure_lookup=failure_lookup,
            dataset_type=dataset_type,
        )

        if not candidates:
            return None

        # Calculate estimated examples
        # Typically want 3-5x examples per cluster member
        estimated_examples = len(candidates) * 4

        # Adjust improvement estimate based on cluster size
        base_improvement = template["improvement_estimate"]
        size_multiplier = min(1.0 + (cluster.count / 20), 2.0)
        estimated_improvement = base_improvement * size_multiplier

        # Generate rationale
        rationale = self._generate_rationale(cluster, candidates)

        return TrainingRecommendation(
            priority=priority,
            cluster_id=cluster.cluster_id,
            category=cluster.category,
            dataset_type=dataset_type,
            title=f"{template['title']} ({cluster.count} failures)",
            description=template["description"],
            rationale=rationale,
            candidates=candidates,
            estimated_examples=estimated_examples,
            estimated_improvement=estimated_improvement,
            effort_level=template["effort"],
        )

    def _calculate_priority(self, cluster: FailureCluster) -> RecommendationPriority:
        """Calculate recommendation priority.

        Args:
            cluster: Failure cluster

        Returns:
            Priority level
        """
        # Critical: high impact, many failures
        if cluster.impact_score > 5.0 and cluster.count >= 10:
            return RecommendationPriority.CRITICAL

        # High: significant impact
        if cluster.impact_score > 3.0 or cluster.count >= 7:
            return RecommendationPriority.HIGH

        # Medium: moderate impact
        if cluster.impact_score > 1.5 or cluster.count >= 4:
            return RecommendationPriority.MEDIUM

        # Low: minor impact
        return RecommendationPriority.LOW

    def _generate_candidates(
        self,
        cluster: FailureCluster,
        failure_lookup: Dict[str, FailureRecord],
        dataset_type: DatasetType,
    ) -> List[TrainingCandidate]:
        """Generate training candidates from cluster.

        Args:
            cluster: Failure cluster
            failure_lookup: Failure ID to record lookup
            dataset_type: Dataset type

        Returns:
            List of training candidates
        """
        candidates = []
        seen_inputs: set = set()

        for failure_id in cluster.failure_ids:
            failure = failure_lookup.get(failure_id)
            if not failure:
                continue

            # Skip duplicate inputs
            input_key = failure.input_text[:100] if failure.input_text else ""
            if input_key in seen_inputs:
                continue
            seen_inputs.add(input_key)

            # Determine correct output
            correct_output = self._determine_correct_output(failure, dataset_type)
            if not correct_output:
                continue

            # Calculate quality score
            quality_score = self._calculate_quality_score(failure)

            # Calculate diversity score (simple)
            diversity_score = 1.0 - (len(seen_inputs) / (cluster.count + 1))

            candidate = TrainingCandidate(
                cluster_id=cluster.cluster_id,
                input_text=failure.input_text,
                correct_output=correct_output,
                incorrect_output=failure.actual_output,
                dataset_type=dataset_type,
                quality_score=quality_score,
                diversity_score=diversity_score,
                metadata={
                    "failure_id": failure_id,
                    "category": failure.category.value,
                    "original_confidence": failure.confidence,
                },
            )

            candidates.append(candidate)

        # Sort by combined score
        candidates.sort(key=lambda c: c.combined_score, reverse=True)

        return candidates

    def _determine_correct_output(
        self,
        failure: FailureRecord,
        dataset_type: DatasetType,
    ) -> Optional[str]:
        """Determine the correct output for training.

        Args:
            failure: Failure record
            dataset_type: Dataset type

        Returns:
            Correct output string or None
        """
        # If user provided correction, use that
        if failure.was_corrected and failure.correction:
            return failure.correction

        # If expected output is known, use that
        if failure.expected_output:
            return failure.expected_output

        # For correction dataset, need both wrong and right
        if dataset_type == DatasetType.CORRECTION:
            return None

        # Can't determine correct output
        return None

    def _calculate_quality_score(self, failure: FailureRecord) -> float:
        """Calculate quality score for a training candidate.

        Args:
            failure: Failure record

        Returns:
            Quality score 0-1
        """
        score = 0.5  # Base score

        # Boost for user correction
        if failure.was_corrected:
            score += 0.3

        # Boost for expected output
        if failure.expected_output:
            score += 0.1

        # Boost for longer, more informative input
        if failure.input_text and len(failure.input_text) > 50:
            score += 0.1

        return min(score, 1.0)

    def _generate_rationale(
        self,
        cluster: FailureCluster,
        candidates: List[TrainingCandidate],
    ) -> str:
        """Generate rationale for recommendation.

        Args:
            cluster: Failure cluster
            candidates: Training candidates

        Returns:
            Rationale string
        """
        parts = [f"{cluster.count} failures in {cluster.category.value} category"]

        avg_quality = (
            sum(c.quality_score for c in candidates) / len(candidates)
            if candidates
            else 0
        )

        if avg_quality > 0.7:
            parts.append("with high-quality correction data")
        elif avg_quality > 0.5:
            parts.append("with moderate-quality correction data")
        else:
            parts.append("(may need manual review)")

        correction_rate = cluster.common_features.get("correction_rate", 0)
        if correction_rate > 0.5:
            parts.append(f"({correction_rate:.0%} user-corrected)")

        return "; ".join(parts)

    def get_by_priority(
        self,
        priority: RecommendationPriority,
    ) -> List[TrainingRecommendation]:
        """Get recommendations by priority.

        Args:
            priority: Priority level

        Returns:
            Matching recommendations
        """
        return [r for r in self._recommendations if r.priority == priority]

    def get_critical(self) -> List[TrainingRecommendation]:
        """Get critical recommendations."""
        return self.get_by_priority(RecommendationPriority.CRITICAL)

    def get_top_recommendations(
        self,
        count: int = 5,
    ) -> List[TrainingRecommendation]:
        """Get top N recommendations.

        Args:
            count: Number to return

        Returns:
            Top recommendations
        """
        return self._recommendations[:count]

    def export_training_data(
        self,
        recommendation_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Export training data from recommendations.

        Args:
            recommendation_id: Specific recommendation ID or all

        Returns:
            List of training examples
        """
        examples = []

        recs = self._recommendations
        if recommendation_id:
            recs = [r for r in recs if r.recommendation_id == recommendation_id]

        for rec in recs:
            for candidate in rec.candidates:
                example = candidate.to_training_example()
                example["metadata"] = {
                    "recommendation_id": rec.recommendation_id,
                    "category": rec.category.value,
                    "dataset_type": rec.dataset_type.value,
                }
                examples.append(example)

        return examples

    def get_stats(self) -> Dict[str, Any]:
        """Get recommender statistics."""
        by_priority = {}
        for p in RecommendationPriority:
            by_priority[p.name] = len(self.get_by_priority(p))

        by_category = {}
        for rec in self._recommendations:
            cat = rec.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total_recommendations": len(self._recommendations),
            "total_candidates": sum(
                len(r.candidates) for r in self._recommendations
            ),
            "by_priority": by_priority,
            "by_category": by_category,
        }

    def clear(self) -> None:
        """Clear all recommendations."""
        self._recommendations.clear()
        self._generated_count = 0
