"""MCP Tools for Trigger Watchers.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (RETRIEVE-001)
"""

from typing import Any, Dict, List, Optional
from loguru import logger

from ...services.trigger_watchers.watcher_manager import WatcherManager, WatcherManagerConfig
from ...services.trigger_watchers.time_scheduler import ScheduledTrigger, DayOfWeek
from ...services.trigger_watchers.activity_detector import ActivityType


class TriggerWatcherTools:
    """MCP tools for trigger watcher management.

    Tools:
    - watcher_start: Start all watchers
    - watcher_stop: Stop all watchers
    - watcher_stats: Get watcher statistics
    - watcher_add_path: Add a file/git watch path
    - watcher_add_schedule: Add a scheduled trigger
    - activity_record: Manually record an activity
    - activity_history: View activity history
    - activity_patterns: View detected patterns
    """

    def __init__(self, manager: WatcherManager):
        """Initialize trigger watcher tools.

        Args:
            manager: WatcherManager instance
        """
        self.manager = manager
        logger.info("TriggerWatcherTools initialized")

    async def start_watchers(self) -> Dict[str, Any]:
        """Start all configured watchers.

        Returns:
            Dict with start result
        """
        try:
            await self.manager.start()
            return {
                "success": True,
                "message": "Watchers started",
                "stats": self.manager.get_stats(),
            }
        except Exception as e:
            logger.error(f"Failed to start watchers: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def stop_watchers(self) -> Dict[str, Any]:
        """Stop all watchers.

        Returns:
            Dict with stop result
        """
        try:
            await self.manager.stop()
            return {
                "success": True,
                "message": "Watchers stopped",
            }
        except Exception as e:
            logger.error(f"Failed to stop watchers: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_watcher_stats(self) -> Dict[str, Any]:
        """Get statistics from all watchers.

        Returns:
            Dict with watcher statistics
        """
        try:
            return {
                "success": True,
                "stats": self.manager.get_stats(),
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def add_file_watch_path(self, path: str) -> Dict[str, Any]:
        """Add a path to file watching.

        Args:
            path: Directory path to watch

        Returns:
            Dict with result
        """
        try:
            success = self.manager.add_file_watch_path(path)
            return {
                "success": success,
                "path": path,
                "message": f"Added file watch path: {path}" if success else "Failed to add path",
            }
        except Exception as e:
            logger.error(f"Failed to add watch path: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def add_git_repo(self, repo_path: str) -> Dict[str, Any]:
        """Add a git repository to watch.

        Args:
            repo_path: Path to git repository

        Returns:
            Dict with result
        """
        try:
            success = self.manager.add_git_repo(repo_path)
            return {
                "success": success,
                "repo_path": repo_path,
                "message": f"Added git repo: {repo_path}" if success else "Failed to add repo",
            }
        except Exception as e:
            logger.error(f"Failed to add git repo: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def add_schedule(
        self,
        trigger_id: str,
        hour: int,
        minute: int = 0,
        days: Optional[List[str]] = None,
        context_query: str = "",
        priority: str = "medium",
    ) -> Dict[str, Any]:
        """Add a scheduled trigger.

        Args:
            trigger_id: Unique ID for the trigger
            hour: Hour (0-23)
            minute: Minute (0-59)
            days: List of day names (default: all weekdays)
            context_query: Context query for injection
            priority: Priority level

        Returns:
            Dict with result
        """
        try:
            from ...integrations.proactive_schema import ContextPriority

            # Parse days
            day_list = []
            if days:
                for day_name in days:
                    try:
                        day_list.append(DayOfWeek[day_name.upper()])
                    except KeyError:
                        pass

            if not day_list:
                day_list = [
                    DayOfWeek.MONDAY,
                    DayOfWeek.TUESDAY,
                    DayOfWeek.WEDNESDAY,
                    DayOfWeek.THURSDAY,
                    DayOfWeek.FRIDAY,
                ]

            schedule = ScheduledTrigger(
                trigger_id=trigger_id,
                hour=hour,
                minute=minute,
                days=day_list,
                context_query=context_query,
                priority=ContextPriority(priority),
            )

            self.manager.add_schedule(schedule)

            return {
                "success": True,
                "trigger_id": trigger_id,
                "schedule": {
                    "hour": hour,
                    "minute": minute,
                    "days": [d.name for d in day_list],
                    "context_query": context_query,
                },
            }
        except Exception as e:
            logger.error(f"Failed to add schedule: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def record_activity(
        self,
        activity_type: str,
        data: Optional[Dict[str, Any]] = None,
        project: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Manually record an activity.

        Args:
            activity_type: Type of activity
            data: Activity-specific data
            project: Project name
            file_path: File path

        Returns:
            Dict with result
        """
        try:
            act_type = ActivityType(activity_type)
            self.manager.record_activity(
                act_type,
                data=data,
                project=project,
                file_path=file_path,
            )

            return {
                "success": True,
                "activity_type": activity_type,
                "message": "Activity recorded",
            }
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid activity type: {activity_type}",
                "valid_types": [t.value for t in ActivityType],
            }
        except Exception as e:
            logger.error(f"Failed to record activity: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_activity_history(self, limit: int = 50) -> Dict[str, Any]:
        """Get recent activity history.

        Args:
            limit: Maximum activities to return

        Returns:
            Dict with activity history
        """
        try:
            if self.manager.activity_detector:
                history = self.manager.activity_detector.get_recent_activities(limit)
                return {
                    "success": True,
                    "count": len(history),
                    "activities": history,
                }
            else:
                return {
                    "success": False,
                    "error": "Activity detector not enabled",
                }
        except Exception as e:
            logger.error(f"Failed to get activity history: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_detected_patterns(self) -> Dict[str, Any]:
        """Get currently detected activity patterns.

        Returns:
            Dict with detected patterns
        """
        try:
            if self.manager.activity_detector:
                patterns = self.manager.activity_detector.get_detected_patterns()
                return {
                    "success": True,
                    "count": len(patterns),
                    "patterns": patterns,
                }
            else:
                return {
                    "success": False,
                    "error": "Activity detector not enabled",
                }
        except Exception as e:
            logger.error(f"Failed to get patterns: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def trigger_schedule_now(self, trigger_id: str) -> Dict[str, Any]:
        """Trigger a scheduled event immediately.

        Args:
            trigger_id: ID of scheduled trigger

        Returns:
            Dict with result
        """
        try:
            success = self.manager.trigger_scheduled_now(trigger_id)
            return {
                "success": success,
                "trigger_id": trigger_id,
                "message": "Triggered" if success else "Trigger not found",
            }
        except Exception as e:
            logger.error(f"Failed to trigger schedule: {e}")
            return {
                "success": False,
                "error": str(e),
            }


def register_trigger_watcher_tools(server: Any, manager: WatcherManager) -> None:
    """Register trigger watcher tools with MCP server.

    Args:
        server: MCP server instance
        manager: WatcherManager instance
    """
    tools = TriggerWatcherTools(manager)

    # Start watchers
    server.add_tool(
        name="watcher_start",
        description="Start all proactive context trigger watchers.",
        handler=tools.start_watchers,
        input_schema={"type": "object", "properties": {}},
    )

    # Stop watchers
    server.add_tool(
        name="watcher_stop",
        description="Stop all proactive context trigger watchers.",
        handler=tools.stop_watchers,
        input_schema={"type": "object", "properties": {}},
    )

    # Get stats
    server.add_tool(
        name="watcher_stats",
        description="Get statistics from all trigger watchers.",
        handler=tools.get_watcher_stats,
        input_schema={"type": "object", "properties": {}},
    )

    # Add file watch path
    server.add_tool(
        name="watcher_add_path",
        description="Add a directory path to file watching.",
        handler=tools.add_file_watch_path,
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to watch",
                },
            },
            "required": ["path"],
        },
    )

    # Add git repo
    server.add_tool(
        name="watcher_add_git",
        description="Add a git repository to watch for checkout events.",
        handler=tools.add_git_repo,
        input_schema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to git repository",
                },
            },
            "required": ["repo_path"],
        },
    )

    # Add schedule
    server.add_tool(
        name="watcher_add_schedule",
        description="Add a scheduled time-based trigger.",
        handler=tools.add_schedule,
        input_schema={
            "type": "object",
            "properties": {
                "trigger_id": {
                    "type": "string",
                    "description": "Unique identifier for the trigger",
                },
                "hour": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 23,
                    "description": "Hour of day (0-23)",
                },
                "minute": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 59,
                    "default": 0,
                    "description": "Minute (0-59)",
                },
                "days": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Days of week (e.g., ['MONDAY', 'TUESDAY'])",
                },
                "context_query": {
                    "type": "string",
                    "description": "Context query for injection",
                },
                "priority": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low", "background"],
                    "default": "medium",
                },
            },
            "required": ["trigger_id", "hour"],
        },
    )

    # Record activity
    server.add_tool(
        name="activity_record",
        description="Manually record a user activity for pattern detection.",
        handler=tools.record_activity,
        input_schema={
            "type": "object",
            "properties": {
                "activity_type": {
                    "type": "string",
                    "enum": [t.value for t in ActivityType],
                    "description": "Type of activity",
                },
                "data": {
                    "type": "object",
                    "description": "Activity-specific data",
                },
                "project": {
                    "type": "string",
                    "description": "Project name",
                },
                "file_path": {
                    "type": "string",
                    "description": "File path (if applicable)",
                },
            },
            "required": ["activity_type"],
        },
    )

    # Get activity history
    server.add_tool(
        name="activity_history",
        description="View recent activity history.",
        handler=tools.get_activity_history,
        input_schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 50,
                    "description": "Maximum activities to return",
                },
            },
        },
    )

    # Get patterns
    server.add_tool(
        name="activity_patterns",
        description="View currently detected activity patterns.",
        handler=tools.get_detected_patterns,
        input_schema={"type": "object", "properties": {}},
    )

    # Trigger schedule now
    server.add_tool(
        name="watcher_trigger_now",
        description="Trigger a scheduled event immediately.",
        handler=tools.trigger_schedule_now,
        input_schema={
            "type": "object",
            "properties": {
                "trigger_id": {
                    "type": "string",
                    "description": "ID of scheduled trigger",
                },
            },
            "required": ["trigger_id"],
        },
    )

    logger.info("Trigger watcher tools registered with MCP server")
