"""Fine-tune Schema for IMPROVE-003.

Data structures for fine-tune candidate identification.

WHO: finetune:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-003)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional
import uuid


class FailureCategory(Enum):
    """Categories of failures for analysis."""

    MODE_DETECTION = "mode_detection"
    ENTITY_EXTRACTION = "entity_extraction"
    TAG_ASSIGNMENT = "tag_assignment"
    CONFIDENCE_SCORING = "confidence_scoring"
    GRAPH_QUERY = "graph_query"
    RETRIEVAL = "retrieval"
    CLASSIFICATION = "classification"
    UNKNOWN = "unknown"


class RecommendationPriority(Enum):
    """Priority levels for training recommendations."""

    CRITICAL = 1  # High-impact, frequent failures
    HIGH = 2  # Significant pattern, needs attention
    MEDIUM = 3  # Notable cluster, worth addressing
    LOW = 4  # Minor pattern, opportunistic fix


class DatasetType(Enum):
    """Types of training datasets."""

    CLASSIFICATION = "classification"  # Input -> Category
    EXTRACTION = "extraction"  # Input -> Entities
    GENERATION = "generation"  # Input -> Output text
    RANKING = "ranking"  # Input -> Ranked outputs
    CORRECTION = "correction"  # Wrong output -> Correct output


@dataclass
class FailureRecord:
    """A record of a single failure for analysis."""

    failure_id: str = field(default_factory=lambda: f"fail-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    category: FailureCategory = FailureCategory.UNKNOWN
    error_type: str = ""
    error_message: str = ""
    input_text: str = ""
    expected_output: Optional[str] = None
    actual_output: Optional[str] = None
    confidence: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)
    was_corrected: bool = False
    correction: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "failure_id": self.failure_id,
            "timestamp": self.timestamp,
            "category": self.category.value,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "input_text": self.input_text,
            "expected_output": self.expected_output,
            "actual_output": self.actual_output,
            "confidence": self.confidence,
            "context": self.context,
            "was_corrected": self.was_corrected,
            "correction": self.correction,
        }


@dataclass
class FailureCluster:
    """A cluster of similar failures."""

    cluster_id: str = field(default_factory=lambda: f"cluster-{uuid.uuid4().hex[:8]}")
    category: FailureCategory = FailureCategory.UNKNOWN
    pattern_description: str = ""
    failure_ids: List[str] = field(default_factory=list)
    count: int = 0
    first_seen: str = ""
    last_seen: str = ""
    similarity_score: float = 0.0
    common_features: Dict[str, Any] = field(default_factory=dict)
    impact_score: float = 0.0  # Based on frequency and severity

    @property
    def is_significant(self) -> bool:
        """Check if cluster is significant enough for action."""
        return self.count >= 3 and self.impact_score >= 0.5

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cluster_id": self.cluster_id,
            "category": self.category.value,
            "pattern_description": self.pattern_description,
            "failure_ids": self.failure_ids,
            "count": self.count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "similarity_score": self.similarity_score,
            "common_features": self.common_features,
            "impact_score": self.impact_score,
        }


@dataclass
class TrainingCandidate:
    """A candidate example for training data."""

    candidate_id: str = field(default_factory=lambda: f"cand-{uuid.uuid4().hex[:8]}")
    cluster_id: str = ""
    input_text: str = ""
    correct_output: str = ""
    incorrect_output: Optional[str] = None
    dataset_type: DatasetType = DatasetType.CLASSIFICATION
    quality_score: float = 0.0
    diversity_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def combined_score(self) -> float:
        """Combined quality and diversity score."""
        return (self.quality_score * 0.6) + (self.diversity_score * 0.4)

    def to_training_example(self) -> Dict[str, Any]:
        """Convert to training example format."""
        example = {
            "input": self.input_text,
            "output": self.correct_output,
        }
        if self.incorrect_output:
            example["rejected"] = self.incorrect_output
        return example

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "candidate_id": self.candidate_id,
            "cluster_id": self.cluster_id,
            "input_text": self.input_text,
            "correct_output": self.correct_output,
            "incorrect_output": self.incorrect_output,
            "dataset_type": self.dataset_type.value,
            "quality_score": self.quality_score,
            "diversity_score": self.diversity_score,
            "metadata": self.metadata,
        }


@dataclass
class TrainingRecommendation:
    """A recommendation for training data generation."""

    recommendation_id: str = field(
        default_factory=lambda: f"rec-{uuid.uuid4().hex[:8]}"
    )
    priority: RecommendationPriority = RecommendationPriority.MEDIUM
    cluster_id: str = ""
    category: FailureCategory = FailureCategory.UNKNOWN
    dataset_type: DatasetType = DatasetType.CLASSIFICATION
    title: str = ""
    description: str = ""
    rationale: str = ""
    candidates: List[TrainingCandidate] = field(default_factory=list)
    estimated_examples: int = 0
    estimated_improvement: float = 0.0  # Expected accuracy improvement
    effort_level: str = "medium"  # small, medium, large
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def candidate_count(self) -> int:
        """Number of training candidates."""
        return len(self.candidates)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "recommendation_id": self.recommendation_id,
            "priority": self.priority.name,
            "cluster_id": self.cluster_id,
            "category": self.category.value,
            "dataset_type": self.dataset_type.value,
            "title": self.title,
            "description": self.description,
            "rationale": self.rationale,
            "candidates": [c.to_dict() for c in self.candidates],
            "estimated_examples": self.estimated_examples,
            "estimated_improvement": self.estimated_improvement,
            "effort_level": self.effort_level,
            "created_at": self.created_at,
        }

    def format_summary(self) -> str:
        """Format as summary text."""
        return (
            f"[{self.priority.name}] {self.title}\n"
            f"  Category: {self.category.value}\n"
            f"  Dataset Type: {self.dataset_type.value}\n"
            f"  Candidates: {self.candidate_count}\n"
            f"  Est. Examples: {self.estimated_examples}\n"
            f"  Est. Improvement: {self.estimated_improvement:.1%}\n"
            f"  Rationale: {self.rationale}"
        )
