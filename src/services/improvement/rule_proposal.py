"""Rule Proposal Generator for IMPROVE-001.

Generates rule update proposals based on detected patterns.

WHO: improvement-pipeline:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-001)
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from src.services.improvement.outcome_schema import (
    Pattern,
    RuleProposal,
    RuleChange,
    ProposalStatus,
)
from src.services.improvement.pattern_detection import PatternType

logger = logging.getLogger(__name__)


# Rule templates for different pattern types
RULE_TEMPLATES = {
    PatternType.FAILURE_CLUSTER: {
        "title_template": "Reduce failures in {category}",
        "risk_level": "medium",
        "change_suggestions": [
            "Add input validation",
            "Improve pattern matching",
            "Add fallback handling",
            "Increase confidence threshold",
        ],
    },
    PatternType.CORRECTION_TREND: {
        "title_template": "Address corrections in {category}",
        "risk_level": "low",
        "change_suggestions": [
            "Update training examples",
            "Refine classification rules",
            "Add edge case handling",
        ],
    },
    PatternType.CONFIDENCE_DROP: {
        "title_template": "Restore confidence levels",
        "risk_level": "medium",
        "change_suggestions": [
            "Review scoring weights",
            "Calibrate thresholds",
            "Add confidence boosters",
        ],
    },
    PatternType.ESCALATION_SPIKE: {
        "title_template": "Reduce escalations in {category}",
        "risk_level": "medium",
        "change_suggestions": [
            "Lower escalation threshold",
            "Add intermediate classification",
            "Improve ambiguity handling",
        ],
    },
    PatternType.INPUT_PATTERN: {
        "title_template": "Handle failing input patterns",
        "risk_level": "low",
        "change_suggestions": [
            "Add pattern-specific rules",
            "Expand input preprocessing",
            "Add special case handling",
        ],
    },
    PatternType.CATEGORY_DRIFT: {
        "title_template": "Address category drift in {category}",
        "risk_level": "high",
        "change_suggestions": [
            "Retrain category boundaries",
            "Update feature weights",
            "Review category definitions",
        ],
    },
}


@dataclass
class RuleProposalConfig:
    """Configuration for rule proposal generation."""

    min_pattern_confidence: float = 0.65
    min_pattern_impact: float = 0.3
    max_changes_per_proposal: int = 5
    auto_generate: bool = True


class RuleProposalGenerator:
    """Generates rule update proposals from patterns.

    Analyzes detected patterns and generates concrete
    proposals for rule updates that address issues.
    """

    def __init__(self, config: Optional[RuleProposalConfig] = None):
        """Initialize rule proposal generator.

        Args:
            config: Generator configuration
        """
        self.config = config or RuleProposalConfig()

        # Generated proposals
        self._proposals: Dict[str, RuleProposal] = {}

        # Statistics
        self._stats = {
            "proposals_generated": 0,
            "by_pattern_type": {},
        }

    def generate_proposal(self, pattern: Pattern) -> Optional[RuleProposal]:
        """Generate a rule proposal from a pattern.

        Args:
            pattern: Pattern to generate proposal for

        Returns:
            Rule proposal or None if pattern not significant enough
        """
        # Check thresholds
        if pattern.confidence < self.config.min_pattern_confidence:
            logger.debug(f"Pattern confidence too low: {pattern.confidence}")
            return None

        if pattern.impact < self.config.min_pattern_impact:
            logger.debug(f"Pattern impact too low: {pattern.impact}")
            return None

        # Get template for pattern type
        template = RULE_TEMPLATES.get(pattern.pattern_type, {})

        if not template:
            logger.warning(f"No template for pattern type: {pattern.pattern_type}")
            return None

        # Generate title
        title = template.get("title_template", "Rule update proposal").format(
            category=pattern.affected_category or "general"
        )

        # Generate changes based on pattern
        changes = self._generate_changes(pattern, template)

        # Calculate expected improvement
        expected_improvement = self._calculate_expected_improvement(pattern, changes)

        # Create proposal
        proposal = RuleProposal(
            status=ProposalStatus.PENDING,
            pattern_id=pattern.pattern_id,
            pattern_confidence=pattern.confidence,
            title=title,
            description=self._generate_description(pattern),
            impact_assessment=self._generate_impact_assessment(pattern),
            risk_level=template.get("risk_level", "medium"),
            changes=changes,
            expected_improvement=expected_improvement,
        )

        # Store proposal
        self._proposals[proposal.proposal_id] = proposal

        # Update stats
        self._stats["proposals_generated"] += 1
        self._stats["by_pattern_type"][pattern.pattern_type] = (
            self._stats["by_pattern_type"].get(pattern.pattern_type, 0) + 1
        )

        logger.info(f"Generated proposal {proposal.proposal_id}: {title}")

        return proposal

    def generate_proposals_from_patterns(
        self,
        patterns: List[Pattern],
    ) -> List[RuleProposal]:
        """Generate proposals for multiple patterns.

        Args:
            patterns: List of patterns

        Returns:
            List of generated proposals
        """
        proposals = []

        # Sort by impact to prioritize most impactful
        sorted_patterns = sorted(
            patterns,
            key=lambda p: p.impact * p.confidence,
            reverse=True,
        )

        for pattern in sorted_patterns:
            proposal = self.generate_proposal(pattern)
            if proposal:
                proposals.append(proposal)

        return proposals

    def _generate_changes(
        self,
        pattern: Pattern,
        template: Dict[str, Any],
    ) -> List[RuleChange]:
        """Generate specific rule changes for a pattern.

        Args:
            pattern: Pattern to address
            template: Rule template

        Returns:
            List of rule changes
        """
        changes = []
        suggestions = template.get("change_suggestions", [])

        # Generate changes based on pattern type
        if pattern.pattern_type == PatternType.FAILURE_CLUSTER:
            changes.extend(self._generate_failure_fixes(pattern, suggestions))

        elif pattern.pattern_type == PatternType.CORRECTION_TREND:
            changes.extend(self._generate_correction_fixes(pattern, suggestions))

        elif pattern.pattern_type == PatternType.CONFIDENCE_DROP:
            changes.extend(self._generate_confidence_fixes(pattern, suggestions))

        elif pattern.pattern_type == PatternType.ESCALATION_SPIKE:
            changes.extend(self._generate_escalation_fixes(pattern, suggestions))

        elif pattern.pattern_type == PatternType.INPUT_PATTERN:
            changes.extend(self._generate_input_pattern_fixes(pattern, suggestions))

        elif pattern.pattern_type == PatternType.CATEGORY_DRIFT:
            changes.extend(self._generate_drift_fixes(pattern, suggestions))

        return changes[: self.config.max_changes_per_proposal]

    def _generate_failure_fixes(
        self,
        pattern: Pattern,
        suggestions: List[str],
    ) -> List[RuleChange]:
        """Generate fixes for failure clusters."""
        changes = []
        category = pattern.affected_category

        # Add validation rule
        if "Add input validation" in suggestions:
            changes.append(
                RuleChange(
                    rule_path=f"src/services/confidence/{category.replace('_', '/')}_validator.py",
                    rule_section="validation_rules",
                    current_value="# No additional validation",
                    proposed_value=f"# Added validation for {category}\nif not self._validate_input(text):\n    return self._handle_invalid_input(text)",
                    change_type="add",
                    rationale=f"Add input validation to reduce failures in {category} (failure rate: {pattern.frequency:.1%})",
                )
            )

        # Add fallback handling
        if "Add fallback handling" in suggestions:
            changes.append(
                RuleChange(
                    rule_path=f"src/services/confidence/{category.replace('_', '/')}.py",
                    rule_section="error_handling",
                    current_value="raise ClassificationError(message)",
                    proposed_value="logger.warning(message)\nreturn self._fallback_classification(text)",
                    change_type="modify",
                    rationale="Add fallback handling instead of raising errors",
                )
            )

        return changes

    def _generate_correction_fixes(
        self,
        pattern: Pattern,
        suggestions: List[str],
    ) -> List[RuleChange]:
        """Generate fixes for correction trends."""
        changes = []
        category = pattern.affected_category

        # Update classification rules
        changes.append(
            RuleChange(
                rule_path=f"src/services/confidence/{category.replace('_', '/')}.py",
                rule_section="classification_rules",
                current_value="# Current classification logic",
                proposed_value="# Updated classification with correction feedback\n# Patterns from user corrections incorporated",
                change_type="modify",
                rationale=f"Incorporate correction feedback into classification rules (correction rate: {pattern.frequency:.1%})",
            )
        )

        return changes

    def _generate_confidence_fixes(
        self,
        pattern: Pattern,
        suggestions: List[str],
    ) -> List[RuleChange]:
        """Generate fixes for confidence drops."""
        changes = []
        evidence = pattern.evidence or {}

        # Recalibrate thresholds
        if "Calibrate thresholds" in suggestions:
            first_avg = evidence.get("first_half_avg", 0.7)
            second_avg = evidence.get("second_half_avg", 0.5)

            changes.append(
                RuleChange(
                    rule_path="src/integrations/confidence_scoring_schema.py",
                    rule_section="thresholds",
                    current_value=f"ESCALATION_THRESHOLD = {second_avg:.2f}",
                    proposed_value=f"ESCALATION_THRESHOLD = {(first_avg + second_avg) / 2:.2f}",
                    change_type="modify",
                    rationale=f"Recalibrate threshold after confidence drop from {first_avg:.2f} to {second_avg:.2f}",
                )
            )

        return changes

    def _generate_escalation_fixes(
        self,
        pattern: Pattern,
        suggestions: List[str],
    ) -> List[RuleChange]:
        """Generate fixes for escalation spikes."""
        changes = []
        category = pattern.affected_category

        # Add intermediate classification
        if "Add intermediate classification" in suggestions:
            changes.append(
                RuleChange(
                    rule_path=f"src/services/confidence/{category.replace('_', '/')}.py",
                    rule_section="classification",
                    current_value="# Binary classification",
                    proposed_value="# Ternary classification with 'uncertain' category\n# Reduces escalations by handling ambiguous cases",
                    change_type="modify",
                    rationale=f"Add intermediate 'uncertain' classification to reduce escalations ({pattern.frequency:.1%})",
                )
            )

        return changes

    def _generate_input_pattern_fixes(
        self,
        pattern: Pattern,
        suggestions: List[str],
    ) -> List[RuleChange]:
        """Generate fixes for problematic input patterns."""
        changes = []
        evidence = pattern.evidence or {}
        common_words = evidence.get("common_words", {})

        if common_words:
            word_list = ", ".join(list(common_words.keys())[:5])

            # Add pattern-specific rules
            changes.append(
                RuleChange(
                    rule_path="src/services/confidence/mode_detector.py",
                    rule_section="MODE_PATTERNS",
                    current_value="# Current pattern definitions",
                    proposed_value=f"# Added patterns for common failing inputs: {word_list}",
                    change_type="add",
                    rationale=f"Add handling for common failing input patterns: {word_list}",
                )
            )

        return changes

    def _generate_drift_fixes(
        self,
        pattern: Pattern,
        suggestions: List[str],
    ) -> List[RuleChange]:
        """Generate fixes for category drift."""
        changes = []
        category = pattern.affected_category
        evidence = pattern.evidence or {}

        # Update feature weights
        if "Update feature weights" in suggestions:
            drift = evidence.get("drift", 0)
            direction = "decreased" if drift > 0 else "increased"

            changes.append(
                RuleChange(
                    rule_path=f"src/services/confidence/{category.replace('_', '/')}.py",
                    rule_section="weights",
                    current_value="# Current feature weights",
                    proposed_value=f"# Adjusted weights to address {direction} performance in {category}",
                    change_type="modify",
                    rationale=f"Rebalance feature weights after {abs(drift):.1%} {direction} in {category}",
                )
            )

        return changes

    def _generate_description(self, pattern: Pattern) -> str:
        """Generate proposal description from pattern."""
        return (
            f"This proposal addresses the detected {pattern.pattern_type} pattern.\n\n"
            f"Pattern Details:\n"
            f"- Description: {pattern.description}\n"
            f"- Confidence: {pattern.confidence:.1%}\n"
            f"- Impact: {pattern.impact:.1%}\n"
            f"- Trend: {pattern.trend}\n"
            f"- Sample Size: {pattern.sample_size}\n"
        )

    def _generate_impact_assessment(self, pattern: Pattern) -> str:
        """Generate impact assessment from pattern."""
        if pattern.impact >= 0.7:
            severity = "HIGH"
        elif pattern.impact >= 0.4:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return (
            f"Impact Assessment: {severity}\n\n"
            f"This pattern affects {pattern.affected_category or 'multiple categories'} "
            f"with an estimated impact of {pattern.impact:.1%}.\n"
            f"If unaddressed, this could lead to continued {pattern.pattern_type.replace('_', ' ')}."
        )

    def _calculate_expected_improvement(
        self,
        pattern: Pattern,
        changes: List[RuleChange],
    ) -> Dict[str, float]:
        """Calculate expected improvement from changes."""
        # Estimate 30-50% reduction in issue frequency
        expected_reduction = pattern.frequency * 0.4

        return {
            "primary_metric": pattern.affected_category or "general",
            "expected_reduction": round(expected_reduction, 4),
            "confidence": round(pattern.confidence * 0.8, 4),
            "change_count": len(changes),
        }

    def get_proposal(self, proposal_id: str) -> Optional[RuleProposal]:
        """Get proposal by ID."""
        return self._proposals.get(proposal_id)

    def get_pending_proposals(self, limit: int = 50) -> List[RuleProposal]:
        """Get pending proposals."""
        pending = [
            p for p in self._proposals.values() if p.status == ProposalStatus.PENDING
        ]
        return sorted(pending, key=lambda p: p.created_at, reverse=True)[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get generator statistics."""
        return {
            "proposals_generated": self._stats["proposals_generated"],
            "proposals_stored": len(self._proposals),
            "by_pattern_type": self._stats["by_pattern_type"],
            "pending_count": len(
                [
                    p
                    for p in self._proposals.values()
                    if p.status == ProposalStatus.PENDING
                ]
            ),
        }
