"""MCP Tools for Proactive Context Injection.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (RETRIEVE-001)
"""

from typing import Any, Dict, Optional
from loguru import logger

from ...services.proactive_context_injector import ProactiveContextInjector
from ...integrations.proactive_schema import TriggerEvent, TriggerType


class ProactiveTools:
    """MCP tools for proactive context injection.

    Tools:
    - proactive_trigger: Manually trigger context injection
    - proactive_stats: Get injection statistics
    - proactive_history: View injection history
    - proactive_rules_list: List injection rules
    - proactive_rule_enable: Enable a rule
    - proactive_rule_disable: Disable a rule
    """

    def __init__(self, injector: ProactiveContextInjector):
        """Initialize proactive tools.

        Args:
            injector: ProactiveContextInjector instance
        """
        self.injector = injector
        logger.info("ProactiveTools initialized")

    async def trigger_context_injection(
        self,
        trigger_type: str,
        source_data: Dict[str, Any],
        query: str,
        priority: str = "medium",
        mode: str = "execution",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Manually trigger proactive context injection.

        Args:
            trigger_type: Type of trigger (file-open, git-checkout, etc.)
            source_data: Trigger-specific data
            query: Context query string
            priority: Priority level (critical, high, medium, low, background)
            mode: Query mode (execution, planning, brainstorm)
            dry_run: Preview without injecting

        Returns:
            Dict with injection result
        """
        try:
            from ...integrations.proactive_schema import ContextPriority

            event = TriggerEvent(
                trigger_type=TriggerType(trigger_type),
                detected_at=datetime.utcnow(),
                source_data=source_data,
                context_query=query,
                priority=ContextPriority(priority),
            )

            context = await self.injector.handle_trigger(event, mode=mode, dry_run=dry_run)

            if context:
                return {
                    "success": True,
                    "injected": True,
                    "dry_run": dry_run,
                    "chunk_count": len(context.chunks),
                    "relevance_score": context.relevance_score,
                    "token_count": context.token_count,
                    "source_ontologies": context.source_ontologies,
                }
            else:
                return {
                    "success": True,
                    "injected": False,
                    "reason": "No relevant context found or suppressed by rules",
                }
        except Exception as e:
            logger.error(f"Trigger injection failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_injection_stats(self) -> Dict[str, Any]:
        """Get injection statistics.

        Returns:
            Dict with statistics
        """
        try:
            stats = self.injector.get_stats()
            return {
                "success": True,
                "stats": stats.to_dict(),
            }
        except Exception as e:
            logger.error(f"Get stats failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_injection_history(
        self,
        limit: int = 10,
        trigger_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get recent injection history.

        Args:
            limit: Max number of injections to return
            trigger_type: Filter by trigger type

        Returns:
            Dict with injection history
        """
        try:
            trigger = TriggerType(trigger_type) if trigger_type else None
            history = self.injector.get_injection_history(limit=limit, trigger_type=trigger)

            return {
                "success": True,
                "count": len(history),
                "history": [ctx.to_dict() for ctx in history],
            }
        except Exception as e:
            logger.error(f"Get history failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def list_injection_rules(self) -> Dict[str, Any]:
        """List all injection rules.

        Returns:
            Dict with rules list
        """
        try:
            rules = self.injector.list_rules()

            return {
                "success": True,
                "count": len(rules),
                "rules": [
                    {
                        "rule_id": r.rule_id,
                        "trigger_types": [t.value for t in r.trigger_types],
                        "enabled": r.enabled,
                        "min_relevance": r.min_relevance,
                        "max_tokens": r.max_tokens,
                        "cooldown_seconds": r.cooldown_seconds,
                    }
                    for r in rules
                ],
            }
        except Exception as e:
            logger.error(f"List rules failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def enable_injection_rule(self, rule_id: str) -> Dict[str, Any]:
        """Enable an injection rule.

        Args:
            rule_id: Rule ID to enable

        Returns:
            Dict with result
        """
        try:
            success = self.injector.enable_rule(rule_id)
            return {
                "success": success,
                "rule_id": rule_id,
                "enabled": True,
            }
        except Exception as e:
            logger.error(f"Enable rule failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def disable_injection_rule(self, rule_id: str) -> Dict[str, Any]:
        """Disable an injection rule.

        Args:
            rule_id: Rule ID to disable

        Returns:
            Dict with result
        """
        try:
            success = self.injector.disable_rule(rule_id)
            return {
                "success": success,
                "rule_id": rule_id,
                "enabled": False,
            }
        except Exception as e:
            logger.error(f"Disable rule failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }


def register_proactive_tools(server: Any, injector: ProactiveContextInjector) -> None:
    """Register proactive tools with MCP server.

    Args:
        server: MCP server instance
        injector: ProactiveContextInjector instance
    """
    tools = ProactiveTools(injector)

    # Trigger context injection
    server.add_tool(
        name="proactive_trigger",
        description="Manually trigger proactive context injection for testing or specific events.",
        handler=tools.trigger_context_injection,
        input_schema={
            "type": "object",
            "properties": {
                "trigger_type": {
                    "type": "string",
                    "enum": ["file-open", "git-checkout", "time-of-day", "activity-pattern", "project-switch", "beads-task-ready"],
                    "description": "Type of trigger event",
                },
                "source_data": {
                    "type": "object",
                    "description": "Trigger-specific data (file_path, branch, etc.)",
                },
                "query": {
                    "type": "string",
                    "description": "Context query string",
                },
                "priority": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low", "background"],
                    "default": "medium",
                },
                "mode": {
                    "type": "string",
                    "enum": ["execution", "planning", "brainstorm"],
                    "default": "execution",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview without injecting",
                    "default": False,
                },
            },
            "required": ["trigger_type", "source_data", "query"],
        },
    )

    # Get stats
    server.add_tool(
        name="proactive_stats",
        description="Get statistics for proactive context injections.",
        handler=tools.get_injection_stats,
        input_schema={"type": "object", "properties": {}},
    )

    # Get history
    server.add_tool(
        name="proactive_history",
        description="View recent proactive context injection history.",
        handler=tools.get_injection_history,
        input_schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max number of injections to return",
                    "default": 10,
                },
                "trigger_type": {
                    "type": "string",
                    "enum": ["file-open", "git-checkout", "time-of-day", "activity-pattern"],
                    "description": "Filter by trigger type",
                },
            },
        },
    )

    # List rules
    server.add_tool(
        name="proactive_rules_list",
        description="List all proactive context injection rules.",
        handler=tools.list_injection_rules,
        input_schema={"type": "object", "properties": {}},
    )

    # Enable rule
    server.add_tool(
        name="proactive_rule_enable",
        description="Enable a proactive injection rule.",
        handler=tools.enable_injection_rule,
        input_schema={
            "type": "object",
            "properties": {
                "rule_id": {
                    "type": "string",
                    "description": "Rule ID to enable",
                },
            },
            "required": ["rule_id"],
        },
    )

    # Disable rule
    server.add_tool(
        name="proactive_rule_disable",
        description="Disable a proactive injection rule.",
        handler=tools.disable_injection_rule,
        input_schema={
            "type": "object",
            "properties": {
                "rule_id": {
                    "type": "string",
                    "description": "Rule ID to disable",
                },
            },
            "required": ["rule_id"],
        },
    )

    logger.info("Proactive tools registered with MCP server")


# Import datetime at top
from datetime import datetime
