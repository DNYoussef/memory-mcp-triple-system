"""MCP Tools for Confidence Scoring Operations (CAPTURE-003).

Provides MCP tool interfaces for confidence scoring and human escalation.

WHO: confidence-scoring:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-003)
"""

import logging
from typing import Optional, Dict, Any, List

from src.integrations.confidence_scoring_schema import (
    ClassificationResult,
    EscalationReason,
)
from src.services.confidence import (
    ConfidenceCoordinator,
    CoordinatorConfig,
    initialize_coordinator,
    QualityGateAggregator,
    GateType,
)

logger = logging.getLogger(__name__)


class ConfidenceTools:
    """MCP tools for confidence scoring operations."""

    def __init__(
        self,
        coordinator: Optional[ConfidenceCoordinator] = None,
        config: Optional[CoordinatorConfig] = None,
    ):
        """Initialize confidence tools.

        Args:
            coordinator: Confidence coordinator instance
            config: Coordinator config if creating new coordinator
        """
        self._coordinator = coordinator
        self._config = config
        self._initialized = False

    def _ensure_initialized(self) -> ConfidenceCoordinator:
        """Ensure coordinator is initialized."""
        if self._coordinator is None:
            self._coordinator = initialize_coordinator(self._config)
            self._initialized = True
        return self._coordinator

    # === Comprehensive Scoring ===

    async def score_text(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform comprehensive confidence scoring on text.

        Runs mode detection, entity extraction, tag assignment,
        and quality gate aggregation.

        Args:
            text: Input text to score
            context: Optional context (agent_id, timestamp, project)

        Returns:
            Comprehensive scoring results
        """
        coordinator = self._ensure_initialized()
        result = coordinator.score_text(text, context)

        return {
            "success": True,
            "overall_confidence": result.overall_confidence,
            "needs_human_review": result.escalation is not None,
            "mode": {
                "value": result.mode.value,
                "confidence": result.mode.confidence.score,
            },
            "entities": {
                "count": len(result.entities.value) if isinstance(result.entities.value, list) else 0,
                "confidence": result.entities.confidence.score,
            },
            "tags": {
                "confidence": result.tags.confidence.score,
            },
            "quality_gate": {
                "passed": result.quality_gate.passed,
                "score": result.quality_gate.overall_score,
            },
            "escalation": result.escalation.to_dict() if result.escalation else None,
        }

    async def score_text_detailed(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform comprehensive scoring with full details.

        Args:
            text: Input text to score
            context: Optional context

        Returns:
            Full scoring results with all details
        """
        coordinator = self._ensure_initialized()
        result = coordinator.score_text(text, context)
        return result.to_dict()

    # === Individual Scorers ===

    async def detect_mode(
        self,
        text: str,
    ) -> Dict[str, Any]:
        """Detect operating mode from text.

        Determines if text is execution, planning, or brainstorming.

        Args:
            text: Input text to analyze

        Returns:
            Mode detection result
        """
        coordinator = self._ensure_initialized()
        result = coordinator.score_mode(text)

        return {
            "mode": result.value,
            "confidence": result.confidence.score,
            "level": result.confidence.level.value,
            "needs_escalation": result.confidence.needs_escalation(),
            "alternatives": result.alternatives,
            "components": result.confidence.components,
        }

    async def extract_entities(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Extract entities from text with confidence scores.

        Args:
            text: Input text to analyze
            entity_types: Optional list of entity types to extract

        Returns:
            Extracted entities with confidence scores
        """
        coordinator = self._ensure_initialized()
        result = coordinator.score_entities(text, entity_types)

        entities = result.value if isinstance(result.value, list) else []

        return {
            "count": len(entities),
            "overall_confidence": result.confidence.score,
            "entities": entities,
            "needs_escalation": result.confidence.needs_escalation(),
        }

    async def assign_tags(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Assign WHO/WHEN/PROJECT/WHY tags with confidence.

        Args:
            content: Content to analyze
            context: Optional context (agent_id, timestamp, project)

        Returns:
            Tag assignments with confidence scores
        """
        coordinator = self._ensure_initialized()
        result = coordinator.score_tags(content, context)

        return {
            "tags": result.value if isinstance(result.value, dict) else {},
            "overall_confidence": result.confidence.score,
            "needs_escalation": result.confidence.needs_escalation(),
            "components": result.confidence.components,
        }

    # === Quality Gates ===

    async def run_quality_gate(
        self,
        scores: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run quality gate on multiple confidence scores.

        Args:
            scores: List of {name: str, confidence: float} scores

        Returns:
            Quality gate result
        """
        gate = QualityGateAggregator()

        for score_data in scores:
            name = score_data.get("name", "unknown")
            confidence = score_data.get("confidence", 0.5)
            gate_type_str = score_data.get("type", "custom")

            try:
                gate_type = GateType(gate_type_str)
            except ValueError:
                gate_type = GateType.CUSTOM

            gate.add_confidence_score(
                gate_type=gate_type,
                name=name,
                confidence=confidence,
            )

        result = gate.evaluate_with_details()

        return {
            "passed": result["passed"],
            "overall_score": result["overall_score"],
            "threshold": result["threshold"],
            "total_checks": result["total_checks"],
            "failing_checks": result["failing_checks"],
            "warning_checks": result["warning_checks"],
            "needs_escalation": result["needs_escalation"],
        }

    # === Escalation Management ===

    async def create_escalation(
        self,
        classification_type: str,
        value: Any,
        confidence: float,
        input_text: str,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a human escalation request.

        Args:
            classification_type: Type of classification
            value: Classification value
            confidence: Confidence score
            input_text: Original input text
            reason: Escalation reason
            context: Additional context

        Returns:
            Created escalation request
        """
        coordinator = self._ensure_initialized()

        # Create a classification result
        from src.integrations.confidence_scoring_schema import ClassificationType
        try:
            class_type = ClassificationType(classification_type)
        except ValueError:
            class_type = ClassificationType.QUALITY_GATE

        result = ClassificationResult.create(
            classification_type=class_type,
            value=value,
            confidence_score=confidence,
            input_text=input_text,
        )

        # Parse reason
        try:
            esc_reason = EscalationReason(reason)
        except ValueError:
            esc_reason = EscalationReason.LOW_CONFIDENCE

        escalation = coordinator.create_escalation(result, esc_reason, context)

        return {
            "success": True,
            "request_id": escalation.request_id,
            "priority": escalation.priority,
            "status": escalation.status.value,
        }

    async def get_pending_escalations(
        self,
        priority_min: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Get pending escalations for review.

        Args:
            priority_min: Minimum priority filter
            limit: Maximum results

        Returns:
            List of pending escalations
        """
        coordinator = self._ensure_initialized()
        pending = coordinator.get_pending_escalations(limit)

        # Filter by priority
        pending = [e for e in pending if e.priority >= priority_min]

        return {
            "count": len(pending),
            "escalations": [e.to_dict() for e in pending],
        }

    async def get_next_escalation(self) -> Dict[str, Any]:
        """Get next escalation for human review.

        Returns:
            Next escalation or empty if none pending
        """
        coordinator = self._ensure_initialized()
        escalation = coordinator.escalation_service.get_next_for_review()

        if escalation is None:
            return {
                "found": False,
                "message": "No pending escalations",
            }

        return {
            "found": True,
            "escalation": escalation.to_dict(),
        }

    async def resolve_escalation(
        self,
        request_id: str,
        resolved_value: Any,
        resolved_by: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Resolve an escalation with human decision.

        Args:
            request_id: Escalation request ID
            resolved_value: Correct value
            resolved_by: Resolver identifier
            notes: Resolution notes

        Returns:
            Resolution result
        """
        coordinator = self._ensure_initialized()
        escalation = coordinator.resolve_escalation(
            request_id, resolved_value, resolved_by, notes
        )

        if escalation is None:
            return {
                "success": False,
                "error": f"Escalation not found: {request_id}",
            }

        return {
            "success": True,
            "request_id": request_id,
            "status": escalation.status.value,
            "resolved_by": resolved_by,
        }

    async def dismiss_escalation(
        self,
        request_id: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Dismiss an escalation without resolution.

        Args:
            request_id: Escalation request ID
            notes: Dismissal notes

        Returns:
            Dismissal result
        """
        coordinator = self._ensure_initialized()
        escalation = coordinator.escalation_service.dismiss(request_id, notes)

        if escalation is None:
            return {
                "success": False,
                "error": f"Escalation not found: {request_id}",
            }

        return {
            "success": True,
            "request_id": request_id,
            "status": escalation.status.value,
        }

    # === Statistics ===

    async def get_confidence_stats(self) -> Dict[str, Any]:
        """Get comprehensive confidence scoring statistics.

        Returns:
            Statistics from all components
        """
        coordinator = self._ensure_initialized()
        return coordinator.get_stats()

    async def get_escalation_stats(self) -> Dict[str, Any]:
        """Get escalation-specific statistics.

        Returns:
            Escalation statistics
        """
        coordinator = self._ensure_initialized()
        return coordinator.escalation_service.get_stats()

    async def export_training_data(
        self,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        """Export resolved escalations for model training.

        Args:
            limit: Maximum records

        Returns:
            Training data from resolved escalations
        """
        coordinator = self._ensure_initialized()
        data = coordinator.escalation_service.export_for_training(limit)

        return {
            "count": len(data),
            "training_data": data,
        }

    async def clear_caches(self) -> Dict[str, Any]:
        """Clear all scorer caches.

        Returns:
            Confirmation of cache clearing
        """
        coordinator = self._ensure_initialized()
        coordinator.clear_caches()

        return {
            "success": True,
            "message": "All caches cleared",
        }


# Tool definitions for MCP registration
CONFIDENCE_TOOLS = [
    {
        "name": "score_text",
        "description": "Comprehensive confidence scoring on text (mode, entities, tags, quality gate)",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Input text to score",
                },
                "context": {
                    "type": "object",
                    "description": "Optional context (agent_id, timestamp, project)",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "detect_mode",
        "description": "Detect operating mode (execution, planning, brainstorming)",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Input text to analyze",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "extract_entities",
        "description": "Extract entities (people, places, dates, etc.) with confidence",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Input text to analyze",
                },
                "entity_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Entity types to extract (person, place, project, etc.)",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "assign_tags",
        "description": "Assign WHO/WHEN/PROJECT/WHY tags with confidence",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Content to analyze",
                },
                "context": {
                    "type": "object",
                    "description": "Optional context",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "run_quality_gate",
        "description": "Run quality gate on multiple confidence scores",
        "parameters": {
            "type": "object",
            "properties": {
                "scores": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "confidence": {"type": "number"},
                            "type": {"type": "string"},
                        },
                        "required": ["name", "confidence"],
                    },
                    "description": "List of confidence scores to aggregate",
                },
            },
            "required": ["scores"],
        },
    },
    {
        "name": "create_escalation",
        "description": "Create human escalation for low-confidence classification",
        "parameters": {
            "type": "object",
            "properties": {
                "classification_type": {
                    "type": "string",
                    "description": "Type of classification",
                },
                "value": {
                    "type": "string",
                    "description": "Classification value",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score (0-1)",
                },
                "input_text": {
                    "type": "string",
                    "description": "Original input text",
                },
                "reason": {
                    "type": "string",
                    "enum": [
                        "low_confidence",
                        "ambiguous_classification",
                        "conflicting_signals",
                        "edge_case",
                        "quality_gate_failed",
                    ],
                    "description": "Escalation reason",
                },
                "context": {
                    "type": "object",
                    "description": "Additional context",
                },
            },
            "required": ["classification_type", "value", "confidence", "input_text", "reason"],
        },
    },
    {
        "name": "get_pending_escalations",
        "description": "Get pending escalations for human review",
        "parameters": {
            "type": "object",
            "properties": {
                "priority_min": {
                    "type": "integer",
                    "description": "Minimum priority (0-10)",
                    "default": 0,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results",
                    "default": 50,
                },
            },
        },
    },
    {
        "name": "get_next_escalation",
        "description": "Get next escalation for review (highest priority)",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "resolve_escalation",
        "description": "Resolve an escalation with human decision",
        "parameters": {
            "type": "object",
            "properties": {
                "request_id": {
                    "type": "string",
                    "description": "Escalation request ID",
                },
                "resolved_value": {
                    "type": "string",
                    "description": "Correct value",
                },
                "resolved_by": {
                    "type": "string",
                    "description": "Resolver identifier",
                },
                "notes": {
                    "type": "string",
                    "description": "Resolution notes",
                },
            },
            "required": ["request_id", "resolved_value", "resolved_by"],
        },
    },
    {
        "name": "dismiss_escalation",
        "description": "Dismiss an escalation without resolution",
        "parameters": {
            "type": "object",
            "properties": {
                "request_id": {
                    "type": "string",
                    "description": "Escalation request ID",
                },
                "notes": {
                    "type": "string",
                    "description": "Dismissal notes",
                },
            },
            "required": ["request_id"],
        },
    },
    {
        "name": "get_confidence_stats",
        "description": "Get comprehensive confidence scoring statistics",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "export_training_data",
        "description": "Export resolved escalations for model training",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum records",
                    "default": 1000,
                },
            },
        },
    },
]
