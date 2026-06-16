"""Tag Assignment Confidence Scorer for CAPTURE-003.

Scores confidence for WHO/WHEN/PROJECT/WHY tag assignments.

WHO: confidence-scoring:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-003)
"""

import copy
import hashlib
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.integrations.confidence_scoring_schema import (
    ClassificationResult,
    ClassificationType,
    EscalationReason,
    combine_confidences,
    ESCALATION_THRESHOLD,
)

logger = logging.getLogger(__name__)


class TagType:
    """Types of tags in WHO/WHEN/PROJECT/WHY schema."""
    WHO = "who"
    WHEN = "when"
    PROJECT = "project"
    WHY = "why"


# WHY categories with keywords
WHY_CATEGORIES = {
    "implementation": {
        "keywords": ["implement", "create", "build", "develop", "add", "new feature"],
        "weight": 0.9,
    },
    "bugfix": {
        "keywords": ["fix", "bug", "error", "issue", "problem", "crash", "broken"],
        "weight": 0.95,
    },
    "refactor": {
        "keywords": ["refactor", "restructure", "reorganize", "clean", "improve code"],
        "weight": 0.85,
    },
    "testing": {
        "keywords": ["test", "spec", "coverage", "assertion", "unit test", "e2e"],
        "weight": 0.9,
    },
    "documentation": {
        "keywords": ["doc", "readme", "comment", "explain", "document"],
        "weight": 0.85,
    },
    "analysis": {
        "keywords": ["analyze", "investigate", "research", "study", "review"],
        "weight": 0.8,
    },
    "planning": {
        "keywords": ["plan", "design", "architect", "strategy", "roadmap"],
        "weight": 0.8,
    },
    "infrastructure": {
        "keywords": ["infra", "devops", "deploy", "ci/cd", "pipeline", "config"],
        "weight": 0.85,
    },
}


# Project patterns
PROJECT_PATTERNS = {
    "memory-mcp-triple-system": {
        "keywords": ["memory", "mcp", "triple", "chromadb", "vector", "hipporag"],
        "weight": 0.95,
    },
    "context-cascade": {
        "keywords": ["cascade", "skill", "agent", "workflow", "orchestrat"],
        "weight": 0.9,
    },
    "trader-ai": {
        "keywords": ["trader", "trading", "momentum", "gate", "market"],
        "weight": 0.9,
    },
    "life-os-dashboard": {
        "keywords": ["dashboard", "life-os", "fastapi", "react", "frontend"],
        "weight": 0.85,
    },
    "connascence": {
        "keywords": ["connascence", "coupling", "analyzer", "quality", "sarif"],
        "weight": 0.9,
    },
    "slop-detector": {
        "keywords": ["slop", "detector", "ai pattern", "banned phrase"],
        "weight": 0.85,
    },
    "fog-compute": {
        "keywords": ["fog", "distributed", "compute", "rust", "wasm"],
        "weight": 0.85,
    },
}


@dataclass
class TagAssignment:
    """A tag assignment with confidence score."""

    tag_type: str
    value: str
    confidence: float
    components: Dict[str, float] = field(default_factory=dict)
    alternatives: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "tag_type": self.tag_type,
            "value": self.value,
            "confidence": round(self.confidence, 4),
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "alternatives": self.alternatives,
        }


@dataclass
class TagAssignmentConfig:
    """Configuration for tag assignment scorer."""

    escalation_threshold: float = ESCALATION_THRESHOLD
    min_confidence: float = 0.3
    enable_caching: bool = True
    known_projects: List[str] = field(default_factory=list)
    known_agents: List[str] = field(default_factory=list)


class TagAssignmentScorer:
    """Confidence scorer for WHO/WHEN/PROJECT/WHY tag assignments.

    Analyzes content to determine appropriate tags and confidence scores.
    """

    def __init__(self, config: Optional[TagAssignmentConfig] = None):
        """Initialize tag assignment scorer.

        Args:
            config: Scorer configuration
        """
        self.config = config or TagAssignmentConfig()
        self._cache: Dict[str, Dict[str, TagAssignment]] = {}
        self._stats = {
            "total_assignments": 0,
            "by_tag": {},
            "low_confidence": 0,
            "escalations": 0,
        }

    def assign_tags(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, TagAssignment]:
        """Assign WHO/WHEN/PROJECT/WHY tags with confidence scores.

        Args:
            content: Content to analyze
            context: Optional context (agent_id, timestamp, etc.)

        Returns:
            Dictionary of tag assignments
        """
        context = context or {}

        # Check cache
        cache_key = self._cache_key(content, context)
        if self.config.enable_caching and cache_key in self._cache:
            return self._copy_assignments(self._cache[cache_key])

        # Assign each tag type
        tags = {
            TagType.WHO: self._assign_who(content, context),
            TagType.WHEN: self._assign_when(content, context),
            TagType.PROJECT: self._assign_project(content, context),
            TagType.WHY: self._assign_why(content, context),
        }

        # Update cache and stats
        if self.config.enable_caching:
            self._cache[cache_key] = self._copy_assignments(tags)

        self._update_stats(tags)

        return tags

    def _cache_key(self, content: str, context: Dict[str, Any]) -> str:
        """Build a cache key from every input that can affect tag assignment."""
        payload = {
            "content": content,
            "context": context,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _copy_assignments(
        self,
        tags: Dict[str, TagAssignment],
    ) -> Dict[str, TagAssignment]:
        """Return mutable tag assignments without sharing cache state."""
        return copy.deepcopy(tags)

    def assign_tags_with_result(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ClassificationResult:
        """Assign tags and return as ClassificationResult.

        Args:
            content: Content to analyze
            context: Optional context

        Returns:
            ClassificationResult with all tag assignments
        """
        tags = self.assign_tags(content, context)

        # Calculate overall confidence (geometric mean)
        confidences = [t.confidence for t in tags.values()]
        overall_confidence = combine_confidences(confidences, method="geometric_mean")

        # Build tag dict for result value
        tag_values = {k: v.to_dict() for k, v in tags.items()}

        return ClassificationResult.create(
            classification_type=ClassificationType.TAG_ASSIGNMENT,
            value=tag_values,
            confidence_score=overall_confidence,
            input_text=content,
            alternatives=[],
            confidence_components={
                "who_confidence": tags[TagType.WHO].confidence,
                "when_confidence": tags[TagType.WHEN].confidence,
                "project_confidence": tags[TagType.PROJECT].confidence,
                "why_confidence": tags[TagType.WHY].confidence,
            },
        )

    def _assign_who(
        self,
        content: str,
        context: Dict[str, Any],
    ) -> TagAssignment:
        """Assign WHO tag (agent/user identifier)."""
        components: Dict[str, float] = {}
        alternatives: List[Dict[str, Any]] = []

        # Check context for agent_id
        if "agent_id" in context:
            value = context["agent_id"]
            confidence = 0.95
            components["from_context"] = 0.95
        elif "user_id" in context:
            value = context["user_id"]
            confidence = 0.9
            components["from_context"] = 0.9
        else:
            # Try to extract from content
            value, confidence, extracted_components = self._extract_who_from_content(content)
            components.update(extracted_components)

        # Check against known agents
        if value and value in self.config.known_agents:
            confidence = min(1.0, confidence + 0.1)
            components["known_agent_boost"] = 0.1

        return TagAssignment(
            tag_type=TagType.WHO,
            value=value,
            confidence=confidence,
            components=components,
            alternatives=alternatives,
        )

    def _extract_who_from_content(
        self,
        content: str,
    ) -> Tuple[str, float, Dict[str, float]]:
        """Extract WHO from content text."""
        components: Dict[str, float] = {}

        # Look for agent patterns
        agent_pattern = r"\b([a-z]+-[a-z]+(?:-[a-z]+)*):(\d+\.\d+\.\d+)\b"
        match = re.search(agent_pattern, content.lower())
        if match:
            value = f"{match.group(1)}:{match.group(2)}"
            confidence = 0.85
            components["agent_pattern_match"] = 0.85
            return value, confidence, components

        # Look for user mentions
        user_pattern = r"\buser[:\s]+([A-Za-z0-9_-]+)\b"
        match = re.search(user_pattern, content, re.IGNORECASE)
        if match:
            value = match.group(1)
            confidence = 0.7
            components["user_mention"] = 0.7
            return value, confidence, components

        # Default to "unknown"
        return "unknown", 0.3, {"default": 0.3}

    def _assign_when(
        self,
        content: str,
        context: Dict[str, Any],
    ) -> TagAssignment:
        """Assign WHEN tag (timestamp)."""
        components: Dict[str, float] = {}

        # Check context for timestamp
        if "timestamp" in context:
            ts = context["timestamp"]
            if isinstance(ts, datetime):
                value = ts.isoformat()
            else:
                value = str(ts)
            confidence = 0.95
            components["from_context"] = 0.95
        else:
            # Try to extract from content
            value, confidence, extracted_components = self._extract_when_from_content(content)
            components.update(extracted_components)

        return TagAssignment(
            tag_type=TagType.WHEN,
            value=value,
            confidence=confidence,
            components=components,
        )

    def _extract_when_from_content(
        self,
        content: str,
    ) -> Tuple[str, float, Dict[str, float]]:
        """Extract WHEN from content text."""
        components: Dict[str, float] = {}

        # ISO format
        iso_pattern = r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\b"
        match = re.search(iso_pattern, content)
        if match:
            value = match.group(1)
            confidence = 0.95
            components["iso_format"] = 0.95
            return value, confidence, components

        # Date pattern
        date_pattern = r"\b(\d{4}-\d{2}-\d{2})\b"
        match = re.search(date_pattern, content)
        if match:
            value = match.group(1) + "T00:00:00Z"
            confidence = 0.8
            components["date_only"] = 0.8
            return value, confidence, components

        # Default to now
        value = datetime.now(timezone.utc).isoformat()
        return value, 0.5, {"default_now": 0.5}

    def _assign_project(
        self,
        content: str,
        context: Dict[str, Any],
    ) -> TagAssignment:
        """Assign PROJECT tag."""
        components: Dict[str, float] = {}
        alternatives: List[Dict[str, Any]] = []

        # Check context for project
        if "project" in context:
            value = context["project"]
            confidence = 0.95
            components["from_context"] = 0.95
            return TagAssignment(
                tag_type=TagType.PROJECT,
                value=value,
                confidence=confidence,
                components=components,
            )

        # Score each known project
        project_scores: List[Tuple[str, float, Dict[str, float]]] = []
        content_lower = content.lower()

        for project, config in PROJECT_PATTERNS.items():
            score, proj_components = self._score_project_match(
                content_lower, project, config
            )
            if score > 0.1:
                project_scores.append((project, score, proj_components))

        # Sort by score
        project_scores.sort(key=lambda x: x[1], reverse=True)

        if project_scores:
            value, confidence, components = project_scores[0]
            alternatives = [
                {"project": p, "confidence": round(s, 4)}
                for p, s, _ in project_scores[1:4]
            ]
        else:
            value = "unknown"
            confidence = 0.3
            components["no_match"] = 0.3

        # Check known projects list
        if value in self.config.known_projects:
            confidence = min(1.0, confidence + 0.05)
            components["known_project_boost"] = 0.05

        return TagAssignment(
            tag_type=TagType.PROJECT,
            value=value,
            confidence=confidence,
            components=components,
            alternatives=alternatives,
        )

    def _score_project_match(
        self,
        content: str,
        project: str,
        config: Dict[str, Any],
    ) -> Tuple[float, Dict[str, float]]:
        """Score how well content matches a project."""
        components: Dict[str, float] = {}

        # Direct name match
        if project in content:
            components["direct_match"] = 0.9
            return config["weight"], components

        # Keyword matching
        keywords = config["keywords"]
        matches = sum(1 for k in keywords if k.lower() in content)

        if matches == 0:
            return 0.0, {}

        keyword_score = min(1.0, matches / len(keywords)) * config["weight"]
        components["keyword_matches"] = matches
        components["keyword_score"] = keyword_score

        return keyword_score, components

    def _assign_why(
        self,
        content: str,
        context: Dict[str, Any],
    ) -> TagAssignment:
        """Assign WHY tag (reason/category)."""
        components: Dict[str, float] = {}
        alternatives: List[Dict[str, Any]] = []

        # Check context for why
        if "why" in context:
            value = context["why"]
            confidence = 0.95
            components["from_context"] = 0.95
            return TagAssignment(
                tag_type=TagType.WHY,
                value=value,
                confidence=confidence,
                components=components,
            )

        # Score each WHY category
        category_scores: List[Tuple[str, float, Dict[str, float]]] = []
        content_lower = content.lower()

        for category, config in WHY_CATEGORIES.items():
            score, cat_components = self._score_why_match(
                content_lower, category, config
            )
            if score > 0.1:
                category_scores.append((category, score, cat_components))

        # Sort by score
        category_scores.sort(key=lambda x: x[1], reverse=True)

        if category_scores:
            value, confidence, components = category_scores[0]
            alternatives = [
                {"category": c, "confidence": round(s, 4)}
                for c, s, _ in category_scores[1:4]
            ]
        else:
            value = "unknown"
            confidence = 0.3
            components["no_match"] = 0.3

        return TagAssignment(
            tag_type=TagType.WHY,
            value=value,
            confidence=confidence,
            components=components,
            alternatives=alternatives,
        )

    def _score_why_match(
        self,
        content: str,
        category: str,
        config: Dict[str, Any],
    ) -> Tuple[float, Dict[str, float]]:
        """Score how well content matches a WHY category."""
        components: Dict[str, float] = {}

        keywords = config["keywords"]
        matches = sum(1 for k in keywords if k.lower() in content)

        if matches == 0:
            return 0.0, {}

        keyword_score = min(1.0, matches / len(keywords)) * config["weight"]
        components["keyword_matches"] = matches
        components["keyword_score"] = keyword_score

        return keyword_score, components

    def _update_stats(self, tags: Dict[str, TagAssignment]) -> None:
        """Update internal statistics."""
        self._stats["total_assignments"] += 1

        for tag_type, assignment in tags.items():
            self._stats["by_tag"][tag_type] = (
                self._stats["by_tag"].get(tag_type, 0) + 1
            )

            if assignment.confidence < self.config.escalation_threshold:
                self._stats["low_confidence"] += 1
                self._stats["escalations"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get scorer statistics."""
        return {
            **self._stats,
            "cache_size": len(self._cache),
        }

    def clear_cache(self) -> None:
        """Clear the assignment cache."""
        self._cache.clear()

    def get_tags_needing_review(
        self,
        tags: Dict[str, TagAssignment],
    ) -> List[TagAssignment]:
        """Get tag assignments with low confidence."""
        return [
            tag for tag in tags.values()
            if tag.confidence < self.config.escalation_threshold
        ]

    def get_escalation_reason(
        self,
        assignment: TagAssignment,
    ) -> Optional[EscalationReason]:
        """Determine escalation reason for a tag assignment."""
        if assignment.confidence >= self.config.escalation_threshold:
            return None

        if assignment.value == "unknown":
            return EscalationReason.AMBIGUOUS_CLASSIFICATION

        if assignment.confidence < 0.4:
            return EscalationReason.LOW_CONFIDENCE

        if len(assignment.alternatives) > 2:
            return EscalationReason.CONFLICTING_SIGNALS

        return EscalationReason.MODEL_UNCERTAINTY
