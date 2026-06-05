"""MCP Tools for IMPROVE-001 Rule Update Automation.

Provides 12 tools for outcome tracking, pattern detection,
proposal generation, approval, and deployment.

WHO: improvement-pipeline:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-001)
"""

import logging
from typing import Dict, Any, List, Optional

from src.services.improvement.improvement_coordinator import (
    get_improvement_coordinator,
)
from src.services.improvement.outcome_schema import (
    Outcome,
    OutcomeType,
    OutcomeSource,
)

logger = logging.getLogger(__name__)


# Tool definitions
IMPROVEMENT_TOOLS = [
    {
        "name": "record_outcome",
        "description": "Record an outcome for the improvement pipeline",
        "inputSchema": {
            "type": "object",
            "properties": {
                "outcome_type": {
                    "type": "string",
                    "enum": ["success", "failure", "partial", "escalated", "correction", "approval", "rejection"],
                    "description": "Type of outcome",
                },
                "source": {
                    "type": "string",
                    "enum": ["confidence_scoring", "user_feedback", "quality_gate", "agent_execution"],
                    "description": "Source of outcome",
                },
                "input_text": {
                    "type": "string",
                    "description": "Input text that was processed",
                },
                "output_text": {
                    "type": "string",
                    "description": "Output that was produced",
                },
                "category": {
                    "type": "string",
                    "description": "Category (e.g., mode_detection, entity_extraction)",
                },
                "confidence_score": {
                    "type": "number",
                    "description": "Confidence score (0-1)",
                },
            },
            "required": ["outcome_type", "input_text", "category"],
        },
    },
    {
        "name": "record_user_feedback",
        "description": "Record user feedback (correction, approval, rejection)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_text": {
                    "type": "string",
                    "description": "Original input",
                },
                "output_text": {
                    "type": "string",
                    "description": "System output",
                },
                "feedback_type": {
                    "type": "string",
                    "enum": ["correction", "approval", "rejection"],
                    "description": "Type of feedback",
                },
                "correct_output": {
                    "type": "string",
                    "description": "Correct output (for corrections)",
                },
                "category": {
                    "type": "string",
                    "description": "Category of the classification",
                },
            },
            "required": ["input_text", "output_text", "feedback_type"],
        },
    },
    {
        "name": "get_outcome_metrics",
        "description": "Get metrics for outcomes (success rate, correction rate, etc.)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter",
                },
                "hours": {
                    "type": "integer",
                    "default": 24,
                    "description": "Time window in hours",
                },
            },
        },
    },
    {
        "name": "detect_patterns",
        "description": "Detect patterns in recent outcomes",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter",
                },
                "hours": {
                    "type": "integer",
                    "default": 168,
                    "description": "Time window in hours (default 7 days)",
                },
            },
        },
    },
    {
        "name": "generate_proposals",
        "description": "Generate rule proposals from detected patterns",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter",
                },
            },
        },
    },
    {
        "name": "run_improvement_cycle",
        "description": "Run a full improvement cycle (outcomes -> patterns -> proposals)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category to focus on",
                },
            },
        },
    },
    {
        "name": "get_pending_approvals",
        "description": "Get proposals pending human approval",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 50,
                    "description": "Maximum results",
                },
            },
        },
    },
    {
        "name": "approve_proposal",
        "description": "Approve a rule proposal for deployment",
        "inputSchema": {
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "Proposal ID to approve",
                },
                "reviewer": {
                    "type": "string",
                    "description": "Reviewer identifier",
                },
                "notes": {
                    "type": "string",
                    "description": "Approval notes",
                },
            },
            "required": ["proposal_id", "reviewer"],
        },
    },
    {
        "name": "reject_proposal",
        "description": "Reject a rule proposal",
        "inputSchema": {
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "Proposal ID to reject",
                },
                "reviewer": {
                    "type": "string",
                    "description": "Reviewer identifier",
                },
                "reason": {
                    "type": "string",
                    "description": "Rejection reason",
                },
            },
            "required": ["proposal_id", "reviewer", "reason"],
        },
    },
    {
        "name": "deploy_proposal",
        "description": "Deploy an approved proposal (dry run by default)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "Proposal ID to deploy",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to do a dry run",
                },
            },
            "required": ["proposal_id"],
        },
    },
    {
        "name": "rollback_deployment",
        "description": "Rollback a deployed proposal",
        "inputSchema": {
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "Proposal ID to rollback",
                },
            },
            "required": ["proposal_id"],
        },
    },
    {
        "name": "get_improvement_stats",
        "description": "Get comprehensive improvement pipeline statistics",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


class ImprovementToolsHandler:
    """Handler for improvement MCP tools."""

    def __init__(self):
        """Initialize handler."""
        self._coordinator = None

    @property
    def coordinator(self):
        """Lazy load coordinator."""
        if self._coordinator is None:
            self._coordinator = get_improvement_coordinator()
        return self._coordinator

    async def handle_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle a tool call.

        Args:
            tool_name: Name of tool
            arguments: Tool arguments

        Returns:
            Tool result
        """
        handlers = {
            "record_outcome": self._record_outcome,
            "record_user_feedback": self._record_user_feedback,
            "get_outcome_metrics": self._get_outcome_metrics,
            "detect_patterns": self._detect_patterns,
            "generate_proposals": self._generate_proposals,
            "run_improvement_cycle": self._run_improvement_cycle,
            "get_pending_approvals": self._get_pending_approvals,
            "approve_proposal": self._approve_proposal,
            "reject_proposal": self._reject_proposal,
            "deploy_proposal": self._deploy_proposal,
            "rollback_deployment": self._rollback_deployment,
            "get_improvement_stats": self._get_improvement_stats,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return await handler(arguments)
        except Exception as e:
            logger.exception(f"Error in {tool_name}")
            return {"error": str(e)}

    async def _record_outcome(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Record an outcome."""
        outcome = Outcome(
            outcome_type=OutcomeType(args["outcome_type"]),
            source=OutcomeSource(args.get("source", "agent_execution")),
            input_text=args["input_text"],
            output_text=args.get("output_text", ""),
            category=args["category"],
            confidence_score=args.get("confidence_score", 0.0),
        )

        outcome_id = self.coordinator.record_outcome(outcome)

        return {
            "outcome_id": outcome_id,
            "outcome_type": outcome.outcome_type.value,
            "category": outcome.category,
        }

    async def _record_user_feedback(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Record user feedback."""
        outcome_id = self.coordinator.record_user_feedback(
            input_text=args["input_text"],
            output_text=args["output_text"],
            feedback_type=args["feedback_type"],
            correct_output=args.get("correct_output"),
            category=args.get("category", ""),
        )

        return {
            "outcome_id": outcome_id,
            "feedback_type": args["feedback_type"],
        }

    async def _get_outcome_metrics(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get outcome metrics."""
        return self.coordinator.get_metrics(
            category=args.get("category"),
            hours=args.get("hours", 24),
        )

    async def _detect_patterns(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Detect patterns."""
        patterns = self.coordinator.detect_patterns(
            category=args.get("category"),
            hours=args.get("hours", 168),
        )

        return {
            "patterns_detected": len(patterns),
            "patterns": [p.to_dict() for p in patterns],
        }

    async def _generate_proposals(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Generate proposals."""
        proposals = self.coordinator.generate_proposals()

        return {
            "proposals_generated": len(proposals),
            "proposals": [p.to_dict() for p in proposals],
        }

    async def _run_improvement_cycle(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Run improvement cycle."""
        result = self.coordinator.run_improvement_cycle(
            category=args.get("category"),
        )

        return result.to_dict()

    async def _get_pending_approvals(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get pending approvals."""
        requests = self.coordinator.get_pending_approvals(
            limit=args.get("limit", 50),
        )

        return {
            "pending_count": len(requests),
            "requests": requests,
        }

    async def _approve_proposal(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Approve a proposal."""
        result = self.coordinator.approve_proposal(
            proposal_id=args["proposal_id"],
            reviewer=args["reviewer"],
            notes=args.get("notes", ""),
        )

        if result:
            return {"success": True, **result}
        return {"success": False, "error": "Proposal not found or already processed"}

    async def _reject_proposal(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Reject a proposal."""
        result = self.coordinator.reject_proposal(
            proposal_id=args["proposal_id"],
            reviewer=args["reviewer"],
            reason=args["reason"],
        )

        if result:
            return {"success": True, **result}
        return {"success": False, "error": "Proposal not found or already processed"}

    async def _deploy_proposal(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy a proposal."""
        result = self.coordinator.deploy_proposal(
            proposal_id=args["proposal_id"],
            dry_run=args.get("dry_run", True),
        )

        if result:
            return result.to_dict()
        return {"success": False, "error": "Proposal not found or not approved"}

    async def _rollback_deployment(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Rollback a deployment."""
        return self.coordinator.rollback_deployment(args["proposal_id"])

    async def _get_improvement_stats(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get improvement statistics."""
        return self.coordinator.get_stats()


# Module-level handler instance
_handler: Optional[ImprovementToolsHandler] = None


def get_improvement_tools_handler() -> ImprovementToolsHandler:
    """Get the improvement tools handler."""
    global _handler
    if _handler is None:
        _handler = ImprovementToolsHandler()
    return _handler


async def handle_improvement_tool(
    tool_name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """Handle an improvement tool call.

    Args:
        tool_name: Name of tool
        arguments: Tool arguments

    Returns:
        Tool result
    """
    handler = get_improvement_tools_handler()
    return await handler.handle_tool(tool_name, arguments)
