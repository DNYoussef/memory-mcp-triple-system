"""Confidence Scoring Services for CAPTURE-003.

WHO: confidence-scoring:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-003)
"""

from src.services.confidence.mode_detector import (
    ModeDetectionScorer,
    ModeDetectionConfig,
    Mode,
)
from src.services.confidence.entity_extractor import (
    EntityExtractionScorer,
    EntityExtractionConfig,
    ExtractedEntity,
    EntityType,
)
from src.services.confidence.quality_gate import (
    QualityGateAggregator,
    QualityGateConfig,
    GateCheck,
    GateType,
    GateStatus,
    create_memory_quality_gate,
    create_strict_quality_gate,
    create_lenient_quality_gate,
)
from src.services.confidence.tag_scorer import (
    TagAssignmentScorer,
    TagAssignmentConfig,
    TagAssignment,
    TagType,
)
from src.services.confidence.escalation_service import (
    EscalationService,
    EscalationQueueConfig,
)
from src.services.confidence.confidence_coordinator import (
    ConfidenceCoordinator,
    CoordinatorConfig,
    ScoringResult,
    get_coordinator,
    initialize_coordinator,
)

__all__ = [
    # Mode Detection
    "ModeDetectionScorer",
    "ModeDetectionConfig",
    "Mode",
    # Entity Extraction
    "EntityExtractionScorer",
    "EntityExtractionConfig",
    "ExtractedEntity",
    "EntityType",
    # Quality Gate
    "QualityGateAggregator",
    "QualityGateConfig",
    "GateCheck",
    "GateType",
    "GateStatus",
    "create_memory_quality_gate",
    "create_strict_quality_gate",
    "create_lenient_quality_gate",
    # Tag Assignment
    "TagAssignmentScorer",
    "TagAssignmentConfig",
    "TagAssignment",
    "TagType",
    # Escalation
    "EscalationService",
    "EscalationQueueConfig",
    # Coordinator
    "ConfidenceCoordinator",
    "CoordinatorConfig",
    "ScoringResult",
    "get_coordinator",
    "initialize_coordinator",
]
