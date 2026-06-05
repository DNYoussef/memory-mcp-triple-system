"""Fine-tune Coordinator for IMPROVE-003.

Orchestrates fine-tune candidate identification pipeline.

WHO: finetune:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-003)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from src.services.finetune.finetune_schema import (
    FailureRecord,
    FailureCategory,
    FailureCluster,
    TrainingCandidate,
    TrainingRecommendation,
    RecommendationPriority,
)
from src.services.finetune.failure_analyzer import FailurePatternAnalyzer
from src.services.finetune.failure_clustering import FailureClusteringService
from src.services.finetune.training_recommender import TrainingDataRecommender

logger = logging.getLogger(__name__)


@dataclass
class FineTuneReport:
    """Complete fine-tuning opportunity report."""

    report_id: str = ""
    generated_at: str = ""
    total_failures: int = 0
    total_clusters: int = 0
    significant_clusters: int = 0
    total_recommendations: int = 0
    total_candidates: int = 0
    pattern_analysis: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[TrainingRecommendation] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "total_failures": self.total_failures,
            "total_clusters": self.total_clusters,
            "significant_clusters": self.significant_clusters,
            "total_recommendations": self.total_recommendations,
            "total_candidates": self.total_candidates,
            "pattern_analysis": self.pattern_analysis,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "summary": self.summary,
        }

    def format_markdown(self) -> str:
        """Format report as markdown."""
        lines = [
            f"# Fine-Tune Candidate Report",
            f"",
            f"**Report ID:** {self.report_id}",
            f"**Generated:** {self.generated_at}",
            f"",
            f"## Summary",
            f"",
            f"{self.summary}",
            f"",
            f"## Statistics",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Failures | {self.total_failures} |",
            f"| Total Clusters | {self.total_clusters} |",
            f"| Significant Clusters | {self.significant_clusters} |",
            f"| Recommendations | {self.total_recommendations} |",
            f"| Training Candidates | {self.total_candidates} |",
            f"",
        ]

        if self.pattern_analysis.get("high_impact_categories"):
            lines.extend(
                [
                    f"## High-Impact Categories",
                    f"",
                ]
            )
            for cat in self.pattern_analysis["high_impact_categories"]:
                lines.append(
                    f"- **{cat['category']}**: {cat['count']} failures "
                    f"(impact: {cat['impact_score']:.1f})"
                )
            lines.append("")

        if self.recommendations:
            lines.extend(
                [
                    f"## Recommendations",
                    f"",
                ]
            )
            for rec in self.recommendations:
                lines.extend(
                    [
                        f"### [{rec.priority.name}] {rec.title}",
                        f"",
                        f"- **Category:** {rec.category.value}",
                        f"- **Dataset Type:** {rec.dataset_type.value}",
                        f"- **Candidates:** {rec.candidate_count}",
                        f"- **Est. Examples:** {rec.estimated_examples}",
                        f"- **Est. Improvement:** {rec.estimated_improvement:.1%}",
                        f"- **Effort:** {rec.effort_level}",
                        f"",
                        f"**Rationale:** {rec.rationale}",
                        f"",
                    ]
                )

        return "\n".join(lines)


@dataclass
class FineTuneConfig:
    """Configuration for fine-tune coordinator."""

    analysis_days: int = 7
    min_cluster_size: int = 2
    similarity_threshold: float = 0.3
    auto_generate_recommendations: bool = True


class FineTuneCoordinator:
    """Coordinates fine-tune candidate identification.

    Orchestrates:
    - Failure pattern analysis
    - Failure clustering
    - Training data recommendation
    """

    def __init__(self, config: Optional[FineTuneConfig] = None):
        """Initialize fine-tune coordinator.

        Args:
            config: Coordinator configuration
        """
        self.config = config or FineTuneConfig()

        # Initialize components
        self.failure_analyzer = FailurePatternAnalyzer()
        self.clustering_service = FailureClusteringService(
            similarity_threshold=self.config.similarity_threshold,
            min_cluster_size=self.config.min_cluster_size,
        )
        self.training_recommender = TrainingDataRecommender()

        # Report history
        self._reports: List[FineTuneReport] = []

    def record_failure(
        self,
        category: str,
        error_type: str,
        error_message: str,
        input_text: str,
        expected_output: Optional[str] = None,
        actual_output: Optional[str] = None,
        confidence: float = 0.0,
        context: Optional[Dict[str, Any]] = None,
        was_corrected: bool = False,
        correction: Optional[str] = None,
    ) -> FailureRecord:
        """Record a failure for analysis.

        Args:
            category: Failure category
            error_type: Error type
            error_message: Error message
            input_text: Input that caused failure
            expected_output: Expected output
            actual_output: Actual output
            confidence: Confidence at failure
            context: Additional context
            was_corrected: Whether corrected by user
            correction: User's correction

        Returns:
            Recorded failure
        """
        return self.failure_analyzer.record_failure(
            category=category,
            error_type=error_type,
            error_message=error_message,
            input_text=input_text,
            expected_output=expected_output,
            actual_output=actual_output,
            confidence=confidence,
            context=context,
            was_corrected=was_corrected,
            correction=correction,
        )

    def generate_report(
        self,
        days: Optional[int] = None,
    ) -> FineTuneReport:
        """Generate a complete fine-tune candidate report.

        Args:
            days: Days to analyze

        Returns:
            Complete report
        """
        analysis_days = days or self.config.analysis_days

        logger.info(f"Generating fine-tune report for {analysis_days} days")

        # Analyze patterns
        pattern_analysis = self.failure_analyzer.analyze_patterns(
            days=analysis_days,
            min_occurrences=self.config.min_cluster_size,
        )

        # Get failures for clustering
        failures = []
        for category in FailureCategory:
            cat_failures = self.failure_analyzer.get_failures_by_category(
                category=category,
                days=analysis_days,
            )
            failures.extend(cat_failures)

        # Cluster failures
        clusters = self.clustering_service.cluster_failures(failures)

        # Generate recommendations
        recommendations = []
        if self.config.auto_generate_recommendations:
            recommendations = self.training_recommender.generate_recommendations(
                clusters=clusters,
                failures=failures,
            )

        # Count significant clusters
        significant = self.clustering_service.get_significant_clusters()

        # Count total candidates
        total_candidates = sum(len(r.candidates) for r in recommendations)

        # Generate summary
        summary = self._generate_summary(
            total_failures=pattern_analysis["total_failures"],
            total_clusters=len(clusters),
            significant_clusters=len(significant),
            recommendations=recommendations,
        )

        # Create report
        import uuid

        report = FineTuneReport(
            report_id=f"ft-{uuid.uuid4().hex[:8]}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_failures=pattern_analysis["total_failures"],
            total_clusters=len(clusters),
            significant_clusters=len(significant),
            total_recommendations=len(recommendations),
            total_candidates=total_candidates,
            pattern_analysis=pattern_analysis,
            recommendations=recommendations,
            summary=summary,
        )

        self._reports.append(report)

        logger.info(
            f"Generated report {report.report_id} with "
            f"{len(recommendations)} recommendations"
        )

        return report

    def _generate_summary(
        self,
        total_failures: int,
        total_clusters: int,
        significant_clusters: int,
        recommendations: List[TrainingRecommendation],
    ) -> str:
        """Generate report summary.

        Args:
            total_failures: Total failures analyzed
            total_clusters: Total clusters found
            significant_clusters: Significant clusters
            recommendations: Generated recommendations

        Returns:
            Summary text
        """
        if total_failures == 0:
            return "No failures recorded in the analysis period."

        parts = [f"Analyzed {total_failures} failures"]

        if total_clusters > 0:
            parts.append(f"found {total_clusters} clusters ({significant_clusters} significant)")

        critical = [r for r in recommendations if r.priority == RecommendationPriority.CRITICAL]
        high = [r for r in recommendations if r.priority == RecommendationPriority.HIGH]

        if critical:
            parts.append(f"{len(critical)} critical fine-tuning opportunities identified")
        elif high:
            parts.append(f"{len(high)} high-priority fine-tuning opportunities identified")
        elif recommendations:
            parts.append(f"{len(recommendations)} fine-tuning opportunities identified")
        else:
            parts.append("no significant fine-tuning opportunities at this time")

        return "; ".join(parts) + "."

    def get_top_recommendations(
        self,
        count: int = 5,
    ) -> List[TrainingRecommendation]:
        """Get top training recommendations.

        Args:
            count: Number to return

        Returns:
            Top recommendations
        """
        return self.training_recommender.get_top_recommendations(count)

    def export_training_data(
        self,
        recommendation_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Export training data from recommendations.

        Args:
            recommendation_id: Specific recommendation or all

        Returns:
            Training examples
        """
        return self.training_recommender.export_training_data(recommendation_id)

    def get_recent_reports(self, count: int = 5) -> List[FineTuneReport]:
        """Get recent reports.

        Args:
            count: Number of reports

        Returns:
            Recent reports
        """
        return self._reports[-count:]

    def get_stats(self) -> Dict[str, Any]:
        """Get coordinator statistics."""
        return {
            "reports_generated": len(self._reports),
            "failure_analyzer": self.failure_analyzer.get_stats(),
            "clustering_service": self.clustering_service.get_stats(),
            "training_recommender": self.training_recommender.get_stats(),
        }


# Singleton instance
_coordinator: Optional[FineTuneCoordinator] = None


def get_finetune_coordinator() -> FineTuneCoordinator:
    """Get the global fine-tune coordinator."""
    global _coordinator
    if _coordinator is None:
        _coordinator = FineTuneCoordinator()
    return _coordinator


def initialize_finetune_coordinator(
    config: Optional[FineTuneConfig] = None,
) -> FineTuneCoordinator:
    """Initialize the global coordinator.

    Args:
        config: Coordinator configuration

    Returns:
        Initialized coordinator
    """
    global _coordinator
    _coordinator = FineTuneCoordinator(config)
    return _coordinator
