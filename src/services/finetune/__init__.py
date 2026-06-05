"""Fine-tune Candidate Identification Module for IMPROVE-003.

Identifies candidates for model fine-tuning based on failure patterns.

WHO: finetune:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-003)
"""

from src.services.finetune.finetune_schema import (
    FailureRecord,
    FailureCategory,
    FailureCluster,
    TrainingCandidate,
    TrainingRecommendation,
    RecommendationPriority,
    DatasetType,
)
from src.services.finetune.failure_analyzer import FailurePatternAnalyzer
from src.services.finetune.failure_clustering import FailureClusteringService
from src.services.finetune.training_recommender import TrainingDataRecommender
from src.services.finetune.finetune_coordinator import (
    FineTuneCoordinator,
    get_finetune_coordinator,
    initialize_finetune_coordinator,
)

__all__ = [
    # Schema
    "FailureRecord",
    "FailureCategory",
    "FailureCluster",
    "TrainingCandidate",
    "TrainingRecommendation",
    "RecommendationPriority",
    "DatasetType",
    # Services
    "FailurePatternAnalyzer",
    "FailureClusteringService",
    "TrainingDataRecommender",
    "FineTuneCoordinator",
    # Functions
    "get_finetune_coordinator",
    "initialize_finetune_coordinator",
]
