"""Git Watcher for Proactive Context Injection.

Monitors git operations and triggers context injection on branch checkouts.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (RETRIEVE-001)
"""

import asyncio
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from loguru import logger

from ..proactive_context_injector import ProactiveContextInjector
from ...integrations.proactive_schema import TriggerEvent, TriggerType, ContextPriority


@dataclass
class GitWatchConfig:
    """Configuration for git watching."""

    repo_paths: List[str] = field(default_factory=list)
    poll_interval: float = 10.0  # Seconds between polling
    track_checkout: bool = True
    track_merge: bool = True
    track_rebase: bool = True
    track_stash: bool = False


@dataclass
class GitRepoState:
    """State tracking for a git repository."""

    path: str
    current_branch: str = ""
    current_commit: str = ""
    last_checked: Optional[datetime] = None
    stash_count: int = 0
    is_rebasing: bool = False
    is_merging: bool = False


class GitWatcher:
    """Git watcher for proactive context injection.

    Monitors git repositories for branch changes, merges, rebases,
    and triggers context injection accordingly.

    Usage:
        watcher = GitWatcher(injector, config)
        await watcher.start()
        # ... later
        await watcher.stop()
    """

    def __init__(
        self,
        injector: ProactiveContextInjector,
        config: Optional[GitWatchConfig] = None,
    ):
        """Initialize git watcher.

        Args:
            injector: ProactiveContextInjector for triggering context injection
            config: Watch configuration (optional)
        """
        self.injector = injector
        self.config = config or GitWatchConfig()
        self._repo_states: Dict[str, GitRepoState] = {}
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None

        logger.info(f"GitWatcher initialized for {len(self.config.repo_paths)} repos")

    def _run_git_command(
        self,
        repo_path: str,
        args: List[str],
    ) -> Optional[str]:
        """Run a git command in a repository.

        Args:
            repo_path: Path to git repository
            args: Git command arguments

        Returns:
            Command output or None on error
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.debug(f"Git command failed: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.warning(f"Git command timed out in {repo_path}")
            return None
        except FileNotFoundError:
            logger.warning("Git not found in PATH")
            return None
        except Exception as e:
            logger.error(f"Git command error: {e}")
            return None

    def _get_current_branch(self, repo_path: str) -> Optional[str]:
        """Get current branch name."""
        return self._run_git_command(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])

    def _get_current_commit(self, repo_path: str) -> Optional[str]:
        """Get current commit hash."""
        return self._run_git_command(repo_path, ["rev-parse", "HEAD"])

    def _get_stash_count(self, repo_path: str) -> int:
        """Get number of stashes."""
        result = self._run_git_command(repo_path, ["stash", "list"])
        if result:
            return len(result.split("\n")) if result else 0
        return 0

    def _is_rebasing(self, repo_path: str) -> bool:
        """Check if repository is in rebase state."""
        git_dir = Path(repo_path) / ".git"
        return (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()

    def _is_merging(self, repo_path: str) -> bool:
        """Check if repository is in merge state."""
        git_dir = Path(repo_path) / ".git"
        return (git_dir / "MERGE_HEAD").exists()

    def _get_project_name(self, repo_path: str) -> str:
        """Extract project name from repo path."""
        return Path(repo_path).name

    async def _check_repo(self, repo_path: str) -> None:
        """Check a repository for changes and trigger injections."""
        if not os.path.exists(os.path.join(repo_path, ".git")):
            logger.debug(f"Not a git repository: {repo_path}")
            return

        # Get or create state
        state = self._repo_states.get(repo_path)
        if not state:
            state = GitRepoState(path=repo_path)
            self._repo_states[repo_path] = state

        # Get current state
        current_branch = self._get_current_branch(repo_path)
        current_commit = self._get_current_commit(repo_path)
        is_rebasing = self._is_rebasing(repo_path)
        is_merging = self._is_merging(repo_path)
        stash_count = self._get_stash_count(repo_path) if self.config.track_stash else 0

        if not current_branch or not current_commit:
            return

        project_name = self._get_project_name(repo_path)

        # Check for branch change (checkout)
        if self.config.track_checkout and state.current_branch:
            if current_branch != state.current_branch:
                logger.info(
                    f"Branch changed in {project_name}: "
                    f"{state.current_branch} -> {current_branch}"
                )
                await self._trigger_checkout(
                    repo_path,
                    project_name,
                    state.current_branch,
                    current_branch,
                )

        # Check for rebase start/end
        if self.config.track_rebase:
            if is_rebasing and not state.is_rebasing:
                logger.info(f"Rebase started in {project_name}")
                await self._trigger_rebase_start(repo_path, project_name, current_branch)
            elif not is_rebasing and state.is_rebasing:
                logger.info(f"Rebase completed in {project_name}")
                await self._trigger_rebase_complete(repo_path, project_name, current_branch)

        # Check for merge start/end
        if self.config.track_merge:
            if is_merging and not state.is_merging:
                logger.info(f"Merge started in {project_name}")
                await self._trigger_merge_start(repo_path, project_name, current_branch)
            elif not is_merging and state.is_merging:
                logger.info(f"Merge completed in {project_name}")
                await self._trigger_merge_complete(repo_path, project_name, current_branch)

        # Check for stash changes
        if self.config.track_stash and stash_count != state.stash_count:
            if stash_count > state.stash_count:
                logger.info(f"Stash created in {project_name}")
            else:
                logger.info(f"Stash applied/dropped in {project_name}")

        # Update state
        state.current_branch = current_branch
        state.current_commit = current_commit
        state.is_rebasing = is_rebasing
        state.is_merging = is_merging
        state.stash_count = stash_count
        state.last_checked = datetime.utcnow()

    async def _trigger_checkout(
        self,
        repo_path: str,
        project_name: str,
        from_branch: str,
        to_branch: str,
    ) -> None:
        """Trigger context injection for branch checkout."""
        try:
            event = TriggerEvent.from_git_checkout(
                branch=to_branch,
                project=project_name,
            )
            event.metadata["from_branch"] = from_branch
            event.metadata["repo_path"] = repo_path

            context = await self.injector.handle_trigger(event)

            if context:
                logger.info(
                    f"Injected checkout context for {project_name}:{to_branch}: "
                    f"{len(context.chunks)} chunks"
                )

        except Exception as e:
            logger.error(f"Failed to trigger checkout injection: {e}")

    async def _trigger_rebase_start(
        self,
        repo_path: str,
        project_name: str,
        branch: str,
    ) -> None:
        """Trigger context injection for rebase start."""
        try:
            event = TriggerEvent(
                trigger_type=TriggerType.GIT_CHECKOUT,
                detected_at=datetime.utcnow(),
                source_data={
                    "branch": branch,
                    "project": project_name,
                    "operation": "rebase_start",
                    "repo_path": repo_path,
                },
                context_query=f"rebase branch:{branch} project:{project_name}",
                priority=ContextPriority.HIGH,
            )

            context = await self.injector.handle_trigger(event)

            if context:
                logger.info(
                    f"Injected rebase context for {project_name}: "
                    f"{len(context.chunks)} chunks"
                )

        except Exception as e:
            logger.error(f"Failed to trigger rebase injection: {e}")

    async def _trigger_rebase_complete(
        self,
        repo_path: str,
        project_name: str,
        branch: str,
    ) -> None:
        """Trigger context injection for rebase completion."""
        pass  # Optional: inject summary context after rebase

    async def _trigger_merge_start(
        self,
        repo_path: str,
        project_name: str,
        branch: str,
    ) -> None:
        """Trigger context injection for merge start."""
        try:
            # Get merge head info
            merge_head = self._run_git_command(repo_path, ["rev-parse", "MERGE_HEAD"])
            merge_branch = None

            if merge_head:
                # Try to find branch name for merge head
                branches = self._run_git_command(
                    repo_path,
                    ["branch", "--contains", merge_head[:8]],
                )
                if branches:
                    merge_branch = branches.split("\n")[0].strip().lstrip("* ")

            event = TriggerEvent(
                trigger_type=TriggerType.GIT_CHECKOUT,
                detected_at=datetime.utcnow(),
                source_data={
                    "branch": branch,
                    "project": project_name,
                    "operation": "merge_start",
                    "merge_branch": merge_branch,
                    "repo_path": repo_path,
                },
                context_query=f"merge branch:{branch} merging:{merge_branch or 'unknown'} project:{project_name}",
                priority=ContextPriority.HIGH,
            )

            context = await self.injector.handle_trigger(event)

            if context:
                logger.info(
                    f"Injected merge context for {project_name}: "
                    f"{len(context.chunks)} chunks"
                )

        except Exception as e:
            logger.error(f"Failed to trigger merge injection: {e}")

    async def _trigger_merge_complete(
        self,
        repo_path: str,
        project_name: str,
        branch: str,
    ) -> None:
        """Trigger context injection for merge completion."""
        pass  # Optional: inject summary context after merge

    async def _poll_repos(self) -> None:
        """Poll repositories for changes."""
        while self._running:
            for repo_path in self.config.repo_paths:
                try:
                    await self._check_repo(repo_path)
                except Exception as e:
                    logger.error(f"Error checking repo {repo_path}: {e}")

            await asyncio.sleep(self.config.poll_interval)

    async def start(self) -> None:
        """Start git watching."""
        if self._running:
            logger.warning("GitWatcher already running")
            return

        self._running = True

        # Initialize state for all repos
        for repo_path in self.config.repo_paths:
            if os.path.exists(os.path.join(repo_path, ".git")):
                branch = self._get_current_branch(repo_path)
                commit = self._get_current_commit(repo_path)

                if branch and commit:
                    self._repo_states[repo_path] = GitRepoState(
                        path=repo_path,
                        current_branch=branch,
                        current_commit=commit,
                        last_checked=datetime.utcnow(),
                    )
                    logger.info(f"Initialized git state for {repo_path}: {branch}")

        # Start polling task
        self._poll_task = asyncio.create_task(self._poll_repos())

        logger.info(
            f"GitWatcher started, monitoring {len(self._repo_states)} repositories"
        )

    async def stop(self) -> None:
        """Stop git watching."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        logger.info("GitWatcher stopped")

    def add_repo(self, repo_path: str) -> bool:
        """Add a repository to watch.

        Args:
            repo_path: Path to git repository

        Returns:
            True if successfully added
        """
        if not os.path.exists(os.path.join(repo_path, ".git")):
            logger.warning(f"Not a git repository: {repo_path}")
            return False

        if repo_path in self.config.repo_paths:
            return True

        self.config.repo_paths.append(repo_path)

        # Initialize state if running
        if self._running:
            branch = self._get_current_branch(repo_path)
            commit = self._get_current_commit(repo_path)

            if branch and commit:
                self._repo_states[repo_path] = GitRepoState(
                    path=repo_path,
                    current_branch=branch,
                    current_commit=commit,
                    last_checked=datetime.utcnow(),
                )

        logger.info(f"Added repository: {repo_path}")
        return True

    def remove_repo(self, repo_path: str) -> bool:
        """Remove a repository from watching.

        Args:
            repo_path: Path to git repository

        Returns:
            True if successfully removed
        """
        if repo_path not in self.config.repo_paths:
            return False

        self.config.repo_paths.remove(repo_path)
        self._repo_states.pop(repo_path, None)

        logger.info(f"Removed repository: {repo_path}")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get watcher statistics.

        Returns:
            Dict with watcher stats
        """
        return {
            "running": self._running,
            "repo_count": len(self.config.repo_paths),
            "repos": [
                {
                    "path": state.path,
                    "branch": state.current_branch,
                    "is_rebasing": state.is_rebasing,
                    "is_merging": state.is_merging,
                    "last_checked": state.last_checked.isoformat() if state.last_checked else None,
                }
                for state in self._repo_states.values()
            ],
        }

    def trigger_manual_check(self, repo_path: str) -> None:
        """Trigger a manual check for a repository.

        Args:
            repo_path: Path to git repository
        """
        if repo_path in self._repo_states:
            asyncio.create_task(self._check_repo(repo_path))
