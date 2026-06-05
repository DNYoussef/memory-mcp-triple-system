"""Claude Code Hooks Integration for Proactive Context Injection.

Integrates with Claude Code's hook system to trigger proactive context.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (RETRIEVE-001)
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger


def get_claude_hooks_dir() -> Optional[Path]:
    """Get Claude Code hooks directory.

    Returns:
        Path to hooks directory or None if not found
    """
    # Check common locations
    candidates = [
        Path.home() / ".claude" / "hooks",
        Path.home() / ".config" / "claude" / "hooks",
        Path(os.environ.get("CLAUDE_HOOKS_DIR", "")) if os.environ.get("CLAUDE_HOOKS_DIR") else None,
    ]

    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate

    return None


def generate_pre_tool_hook(
    hook_name: str = "proactive-context-pre-tool",
    tool_patterns: Optional[List[str]] = None,
) -> str:
    """Generate a pre-tool hook script for proactive context injection.

    Args:
        hook_name: Name for the hook
        tool_patterns: List of tool name patterns to trigger on

    Returns:
        Hook script content
    """
    patterns = tool_patterns or ["Read", "Grep", "Glob"]
    pattern_check = " || ".join([f'[[ "$TOOL_NAME" == *"{p}"* ]]' for p in patterns])

    return f'''#!/bin/bash
# {hook_name} - Proactive Context Injection Hook
# WHO: proactive-injector:1.0.0
# WHEN: {datetime.utcnow().isoformat()}Z
# PROJECT: memory-mcp-triple-system
# WHY: implementation (RETRIEVE-001)

# This hook triggers proactive context injection before file access tools

TOOL_NAME="${{TOOL_INPUT_NAME:-}}"
TOOL_INPUT="${{TOOL_INPUT:-}}"

# Only trigger for specific tools
if {pattern_check}; then
    # Extract file path from tool input
    FILE_PATH=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('file_path', data.get('path', data.get('pattern', ''))))
except:
    pass
" 2>/dev/null)

    if [ -n "$FILE_PATH" ]; then
        # Trigger proactive context injection
        python3 -c "
import sys
sys.path.insert(0, r'D:\\Projects\\memory-mcp-triple-system')
try:
    from src.services.proactive_context_injector import get_proactive_injector
    from src.integrations.proactive_schema import TriggerEvent
    import asyncio

    async def trigger():
        injector = get_proactive_injector()
        event = TriggerEvent.from_file_open('$FILE_PATH')
        await injector.handle_trigger(event, dry_run=False)

    asyncio.run(trigger())
except Exception as e:
    pass  # Silent failure to not block tool execution
" 2>/dev/null &
    fi
fi

# Always allow the tool to proceed
exit 0
'''


def generate_session_start_hook(
    hook_name: str = "proactive-context-session-start",
) -> str:
    """Generate a session start hook for proactive context injection.

    Args:
        hook_name: Name for the hook

    Returns:
        Hook script content
    """
    return f'''#!/bin/bash
# {hook_name} - Session Start Context Injection Hook
# WHO: proactive-injector:1.0.0
# WHEN: {datetime.utcnow().isoformat()}Z
# PROJECT: memory-mcp-triple-system
# WHY: implementation (RETRIEVE-001)

# Get current working directory project name
PROJECT_NAME=$(basename "$(pwd)")
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

# Trigger session-start context injection
python3 -c "
import sys
sys.path.insert(0, r'D:\\Projects\\memory-mcp-triple-system')
try:
    from src.services.proactive_context_injector import get_proactive_injector
    from src.integrations.proactive_schema import TriggerEvent, TriggerType, ContextPriority
    from datetime import datetime
    import asyncio

    async def trigger():
        injector = get_proactive_injector()

        # Trigger project switch event
        event = TriggerEvent(
            trigger_type=TriggerType.PROJECT_SWITCH,
            detected_at=datetime.utcnow(),
            source_data={{
                'project': '$PROJECT_NAME',
                'branch': '$CURRENT_BRANCH',
                'working_dir': '$(pwd)',
            }},
            context_query='project:$PROJECT_NAME recent-work pending-tasks',
            priority=ContextPriority.HIGH,
        )
        context = await injector.handle_trigger(event)

        if context:
            print(f'[PROACTIVE] Loaded {{len(context.chunks)}} context chunks for $PROJECT_NAME')

    asyncio.run(trigger())
except Exception as e:
    print(f'[PROACTIVE] Context injection skipped: {{e}}')
" 2>/dev/null

exit 0
'''


def generate_git_post_checkout_hook(
    hook_name: str = "proactive-context-git-checkout",
) -> str:
    """Generate a git post-checkout hook for proactive context injection.

    Args:
        hook_name: Name for the hook

    Returns:
        Hook script content
    """
    return f'''#!/bin/bash
# {hook_name} - Git Post-Checkout Context Injection Hook
# WHO: proactive-injector:1.0.0
# WHEN: {datetime.utcnow().isoformat()}Z
# PROJECT: memory-mcp-triple-system
# WHY: implementation (RETRIEVE-001)

# Git passes: previous_ref new_ref flag (1=branch, 0=file)
PREV_REF="${{1:-}}"
NEW_REF="${{2:-}}"
FLAG="${{3:-0}}"

# Only trigger on branch checkouts
if [ "$FLAG" = "1" ]; then
    PROJECT_NAME=$(basename "$(pwd)")
    NEW_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

    python3 -c "
import sys
sys.path.insert(0, r'D:\\Projects\\memory-mcp-triple-system')
try:
    from src.services.proactive_context_injector import get_proactive_injector
    from src.integrations.proactive_schema import TriggerEvent
    import asyncio

    async def trigger():
        injector = get_proactive_injector()
        event = TriggerEvent.from_git_checkout(
            branch='$NEW_BRANCH',
            project='$PROJECT_NAME',
        )
        context = await injector.handle_trigger(event)

        if context:
            print(f'[PROACTIVE] Loaded {{len(context.chunks)}} context chunks for branch $NEW_BRANCH')

    asyncio.run(trigger())
except Exception as e:
    pass
" 2>/dev/null
fi

exit 0
'''


def generate_activity_hook(
    hook_name: str = "proactive-context-activity",
    event_types: Optional[List[str]] = None,
) -> str:
    """Generate an activity recording hook.

    Args:
        hook_name: Name for the hook
        event_types: List of event types to track

    Returns:
        Hook script content
    """
    types = event_types or ["PreToolUse", "PostToolUse", "Stop"]
    type_check = " || ".join([f'[[ "$EVENT_TYPE" == "{t}" ]]' for t in types])

    return f'''#!/bin/bash
# {hook_name} - Activity Recording Hook
# WHO: proactive-injector:1.0.0
# WHEN: {datetime.utcnow().isoformat()}Z
# PROJECT: memory-mcp-triple-system
# WHY: implementation (RETRIEVE-001)

EVENT_TYPE="${{HOOK_EVENT_TYPE:-}}"
TOOL_NAME="${{TOOL_INPUT_NAME:-}}"
PROJECT_NAME=$(basename "$(pwd)")

# Only record specific event types
if {type_check}; then
    python3 -c "
import sys
sys.path.insert(0, r'D:\\Projects\\memory-mcp-triple-system')
try:
    from src.services.trigger_watchers.activity_detector import ActivityType
    from src.services.trigger_watchers.watcher_manager import get_watcher_manager

    manager = get_watcher_manager()

    # Map event to activity type
    event_map = {{
        'PreToolUse': ActivityType.TOOL_USE,
        'PostToolUse': ActivityType.TOOL_USE,
        'Stop': ActivityType.TASK_COMPLETE,
    }}

    activity_type = event_map.get('$EVENT_TYPE', ActivityType.TOOL_USE)

    manager.record_activity(
        activity_type,
        data={{'event': '$EVENT_TYPE', 'tool': '$TOOL_NAME'}},
        project='$PROJECT_NAME',
    )
except Exception:
    pass
" 2>/dev/null &
fi

exit 0
'''


class ClaudeCodeHooksIntegration:
    """Manages Claude Code hooks for proactive context injection.

    Provides methods to install, configure, and manage hooks that
    integrate with Claude Code's hook system.
    """

    def __init__(self, hooks_dir: Optional[Path] = None):
        """Initialize hooks integration.

        Args:
            hooks_dir: Path to hooks directory (auto-detected if not provided)
        """
        self.hooks_dir = hooks_dir or get_claude_hooks_dir()

        if self.hooks_dir:
            logger.info(f"Claude Code hooks directory: {self.hooks_dir}")
        else:
            logger.warning("Claude Code hooks directory not found")

    def install_hook(
        self,
        hook_type: str,
        hook_name: str,
        content: str,
    ) -> bool:
        """Install a hook script.

        Args:
            hook_type: Type of hook (pre-tool, post-tool, session-start, etc.)
            hook_name: Name for the hook file
            content: Hook script content

        Returns:
            True if installed successfully
        """
        if not self.hooks_dir:
            logger.error("Hooks directory not configured")
            return False

        # Create hook type directory if needed
        hook_dir = self.hooks_dir / hook_type
        hook_dir.mkdir(parents=True, exist_ok=True)

        # Write hook script
        hook_path = hook_dir / f"{hook_name}.sh"

        try:
            hook_path.write_text(content)

            # Make executable on Unix
            if os.name != "nt":
                hook_path.chmod(0o755)

            logger.info(f"Installed hook: {hook_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to install hook: {e}")
            return False

    def install_all_hooks(self) -> Dict[str, bool]:
        """Install all proactive context injection hooks.

        Returns:
            Dict mapping hook names to success status
        """
        results = {}

        # Pre-tool hook for file access
        results["pre-tool-file-access"] = self.install_hook(
            "PreToolUse",
            "proactive-context-file-access",
            generate_pre_tool_hook(),
        )

        # Session start hook
        results["session-start"] = self.install_hook(
            "SessionStart",
            "proactive-context-session",
            generate_session_start_hook(),
        )

        # Activity recording hook
        results["activity-recorder"] = self.install_hook(
            "PostToolUse",
            "proactive-context-activity",
            generate_activity_hook(),
        )

        return results

    def uninstall_hook(self, hook_type: str, hook_name: str) -> bool:
        """Uninstall a hook script.

        Args:
            hook_type: Type of hook
            hook_name: Name of hook file

        Returns:
            True if uninstalled successfully
        """
        if not self.hooks_dir:
            return False

        hook_path = self.hooks_dir / hook_type / f"{hook_name}.sh"

        if hook_path.exists():
            try:
                hook_path.unlink()
                logger.info(f"Uninstalled hook: {hook_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to uninstall hook: {e}")
                return False

        return True  # Already doesn't exist

    def list_installed_hooks(self) -> List[Dict[str, Any]]:
        """List all installed proactive context hooks.

        Returns:
            List of installed hook info
        """
        hooks = []

        if not self.hooks_dir or not self.hooks_dir.exists():
            return hooks

        for hook_type_dir in self.hooks_dir.iterdir():
            if not hook_type_dir.is_dir():
                continue

            for hook_file in hook_type_dir.glob("proactive-context-*.sh"):
                hooks.append({
                    "type": hook_type_dir.name,
                    "name": hook_file.stem,
                    "path": str(hook_file),
                    "size": hook_file.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        hook_file.stat().st_mtime
                    ).isoformat(),
                })

        return hooks

    def generate_git_hooks(self, repo_path: str) -> Dict[str, bool]:
        """Generate git hooks for a repository.

        Args:
            repo_path: Path to git repository

        Returns:
            Dict mapping hook names to success status
        """
        results = {}
        git_hooks_dir = Path(repo_path) / ".git" / "hooks"

        if not git_hooks_dir.exists():
            logger.error(f"Git hooks directory not found: {git_hooks_dir}")
            return results

        # Post-checkout hook
        post_checkout_path = git_hooks_dir / "post-checkout"

        try:
            content = generate_git_post_checkout_hook()
            post_checkout_path.write_text(content)

            if os.name != "nt":
                post_checkout_path.chmod(0o755)

            results["post-checkout"] = True
            logger.info(f"Installed git post-checkout hook: {post_checkout_path}")

        except Exception as e:
            logger.error(f"Failed to install git hook: {e}")
            results["post-checkout"] = False

        return results


def install_proactive_hooks(
    hooks_dir: Optional[Path] = None,
    git_repos: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Convenience function to install all proactive context hooks.

    Args:
        hooks_dir: Claude Code hooks directory (auto-detected if not provided)
        git_repos: List of git repository paths to install git hooks

    Returns:
        Dict with installation results
    """
    integration = ClaudeCodeHooksIntegration(hooks_dir)

    results = {
        "claude_hooks": integration.install_all_hooks(),
        "git_hooks": {},
    }

    if git_repos:
        for repo in git_repos:
            results["git_hooks"][repo] = integration.generate_git_hooks(repo)

    return results
