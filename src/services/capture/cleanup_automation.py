"""Cleanup Automation Service for CAPTURE-001.

Automates ephemeral buffer cleanup based on configurable rules.
Rules: Delete after 1 week OR home PC download, verify transcription before deletion.

WHO: ephemeral-buffer:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-001)
"""

import os
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
import logging

from src.integrations.ephemeral_buffer_schema import (
    EphemeralBuffer,
    BufferStatus,
    DeletionRule,
    DeleteReason,
    DEFAULT_DELETION_RULES,
)
from src.services.capture.railway_buffer import RailwayBufferService

logger = logging.getLogger(__name__)


@dataclass
class CleanupConfig:
    """Configuration for cleanup automation."""

    # Cleanup check interval (seconds)
    check_interval: float = 3600.0  # 1 hour

    # Enable automatic cleanup
    auto_cleanup: bool = True

    # Dry run mode (log but don't delete)
    dry_run: bool = False

    # Maximum deletions per run
    max_deletions_per_run: int = 50

    # Require transcription verification before delete
    require_transcription_verification: bool = True

    # Grace period after transcription (hours)
    grace_period_hours: int = 24

    # Delete local copies after Railway deletion
    delete_local_copies: bool = False

    # Custom deletion rules
    custom_rules: List[DeletionRule] = field(default_factory=list)


@dataclass
class CleanupResult:
    """Result of a cleanup run."""

    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    buffers_checked: int = 0
    buffers_deleted: int = 0
    buffers_skipped: int = 0
    buffers_errored: int = 0
    bytes_freed: int = 0
    deletion_reasons: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "buffers_checked": self.buffers_checked,
            "buffers_deleted": self.buffers_deleted,
            "buffers_skipped": self.buffers_skipped,
            "buffers_errored": self.buffers_errored,
            "bytes_freed": self.bytes_freed,
            "mb_freed": round(self.bytes_freed / (1024 * 1024), 2),
            "deletion_reasons": self.deletion_reasons,
            "errors": self.errors,
            "dry_run": self.dry_run,
        }


@dataclass
class DeletionCandidate:
    """A buffer candidate for deletion."""

    buffer: EphemeralBuffer
    rule: DeletionRule
    reason: DeleteReason
    can_delete: bool = True
    skip_reason: Optional[str] = None


class CleanupAutomation:
    """Service for automating ephemeral buffer cleanup.

    This service handles:
    - Periodic cleanup checks
    - Rule-based deletion decisions
    - Transcription verification before deletion
    - Audit trail generation
    - Dry-run mode for testing
    """

    def __init__(
        self,
        railway_service: RailwayBufferService,
        config: Optional[CleanupConfig] = None,
        on_pre_delete: Optional[Callable[[EphemeralBuffer, DeleteReason], Awaitable[bool]]] = None,
        on_delete: Optional[Callable[[EphemeralBuffer, DeleteReason], Awaitable[None]]] = None,
        on_delete_error: Optional[Callable[[EphemeralBuffer, str], Awaitable[None]]] = None,
    ):
        """Initialize cleanup automation.

        Args:
            railway_service: Railway buffer service instance
            config: Cleanup configuration
            on_pre_delete: Pre-delete callback (return False to cancel)
            on_delete: Post-delete callback
            on_delete_error: Error callback
        """
        self.railway = railway_service
        self.config = config or CleanupConfig()
        self._on_pre_delete = on_pre_delete
        self._on_delete = on_delete
        self._on_delete_error = on_delete_error

        # Deletion rules (default + custom)
        self._rules: Dict[str, DeletionRule] = {}
        for rule in DEFAULT_DELETION_RULES:
            self._rules[rule.rule_id] = rule
        for rule in self.config.custom_rules:
            self._rules[rule.rule_id] = rule

        # Cleanup history
        self._cleanup_history: List[CleanupResult] = []
        self._run_counter = 0

        # Running state
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the cleanup automation service."""
        if self._running:
            return

        self._running = True

        if self.config.auto_cleanup:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info(
            f"CleanupAutomation started, "
            f"auto_cleanup={self.config.auto_cleanup}, "
            f"dry_run={self.config.dry_run}"
        )

    async def stop(self) -> None:
        """Stop the cleanup automation service."""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        logger.info("CleanupAutomation stopped")

    async def _cleanup_loop(self) -> None:
        """Background loop for periodic cleanup."""
        while self._running:
            try:
                await asyncio.sleep(self.config.check_interval)
                await self.run_cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def run_cleanup(
        self,
        dry_run: Optional[bool] = None,
    ) -> CleanupResult:
        """Run a cleanup cycle.

        Args:
            dry_run: Override config dry_run setting

        Returns:
            Cleanup result
        """
        self._run_counter += 1
        is_dry_run = dry_run if dry_run is not None else self.config.dry_run

        result = CleanupResult(
            run_id=f"cleanup_{self._run_counter}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            started_at=datetime.now(timezone.utc),
            dry_run=is_dry_run,
        )

        logger.info(f"Starting cleanup run {result.run_id} (dry_run={is_dry_run})")

        try:
            # Get all non-deleted buffers
            buffers = await self.railway.list_buffers(
                include_expired=True,
                limit=1000,
            )

            # Find deletion candidates
            candidates = self._find_candidates(buffers)
            result.buffers_checked = len(buffers)

            # Process candidates
            deleted_count = 0
            for candidate in candidates:
                if deleted_count >= self.config.max_deletions_per_run:
                    logger.info(f"Reached max deletions per run ({self.config.max_deletions_per_run})")
                    break

                if not candidate.can_delete:
                    result.buffers_skipped += 1
                    continue

                # Process deletion
                success = await self._process_deletion(
                    candidate,
                    is_dry_run,
                    result,
                )

                if success:
                    deleted_count += 1

        except Exception as e:
            logger.error(f"Cleanup run error: {e}")
            result.errors.append(str(e))

        result.completed_at = datetime.now(timezone.utc)
        self._cleanup_history.append(result)

        logger.info(
            f"Cleanup run {result.run_id} complete: "
            f"{result.buffers_deleted} deleted, "
            f"{result.buffers_skipped} skipped, "
            f"{result.buffers_errored} errors, "
            f"{result.bytes_freed / (1024 * 1024):.2f} MB freed"
        )

        return result

    def _find_candidates(
        self,
        buffers: List[EphemeralBuffer],
    ) -> List[DeletionCandidate]:
        """Find buffers eligible for deletion.

        Args:
            buffers: List of buffers to check

        Returns:
            List of deletion candidates
        """
        candidates = []
        now = datetime.now(timezone.utc)

        for buffer in buffers:
            # Skip already deleted
            if buffer.status == BufferStatus.DELETED:
                continue

            # Check each rule
            for rule in self._rules.values():
                if not rule.enabled:
                    continue

                can_delete, reason = rule.can_delete(buffer, now)
                if can_delete:
                    candidate = DeletionCandidate(
                        buffer=buffer,
                        rule=rule,
                        reason=reason,
                    )

                    # Additional verification checks
                    skip_reason = self._check_deletion_prerequisites(buffer, now)
                    if skip_reason:
                        candidate.can_delete = False
                        candidate.skip_reason = skip_reason

                    candidates.append(candidate)
                    break  # First matching rule wins

        # Sort by rule priority (higher first)
        candidates.sort(key=lambda c: c.rule.priority, reverse=True)

        return candidates

    def _check_deletion_prerequisites(
        self,
        buffer: EphemeralBuffer,
        now: datetime,
    ) -> Optional[str]:
        """Check if buffer meets deletion prerequisites.

        Args:
            buffer: Buffer to check
            now: Current time

        Returns:
            Skip reason if should skip, None if can delete
        """
        # Check transcription verification requirement
        if self.config.require_transcription_verification:
            if buffer.status == BufferStatus.TRANSCRIBED:
                if buffer.transcription:
                    if not buffer.transcription.is_verified():
                        return "Transcription not verified"
                else:
                    return "No transcription result"
            elif buffer.status not in [BufferStatus.EXPIRED]:
                # Not expired and not transcribed
                return "Not transcribed yet"

        # Check grace period after transcription
        if buffer.transcribed_at:
            grace_end = buffer.transcribed_at + timedelta(
                hours=self.config.grace_period_hours
            )
            if now < grace_end:
                hours_left = (grace_end - now).total_seconds() / 3600
                return f"In grace period ({hours_left:.1f}h remaining)"

        return None

    async def _process_deletion(
        self,
        candidate: DeletionCandidate,
        dry_run: bool,
        result: CleanupResult,
    ) -> bool:
        """Process a deletion candidate.

        Args:
            candidate: Deletion candidate
            dry_run: Whether this is a dry run
            result: Result to update

        Returns:
            True if deleted successfully
        """
        buffer = candidate.buffer
        reason = candidate.reason

        try:
            # Pre-delete callback
            if self._on_pre_delete:
                should_continue = await self._on_pre_delete(buffer, reason)
                if not should_continue:
                    result.buffers_skipped += 1
                    return False

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would delete buffer {buffer.buffer_id} "
                    f"({buffer.metadata.original_filename}) - {reason.value}"
                )
                result.buffers_deleted += 1
                result.bytes_freed += buffer.metadata.file_size_bytes
                result.deletion_reasons[reason.value] = \
                    result.deletion_reasons.get(reason.value, 0) + 1
                return True

            # Mark for deletion
            buffer.mark_pending_delete()
            await self.railway.update_buffer_status(
                buffer.buffer_id,
                BufferStatus.PENDING_DELETE
            )

            # Delete from Railway
            success = await self.railway.delete_buffer(
                buffer.buffer_id,
                force=True,
            )

            if success:
                result.buffers_deleted += 1
                result.bytes_freed += buffer.metadata.file_size_bytes
                result.deletion_reasons[reason.value] = \
                    result.deletion_reasons.get(reason.value, 0) + 1

                # Delete local copy if configured
                if self.config.delete_local_copies and buffer.local_path:
                    if os.path.exists(buffer.local_path):
                        os.remove(buffer.local_path)
                        logger.info(f"Deleted local copy: {buffer.local_path}")

                # Post-delete callback
                if self._on_delete:
                    await self._on_delete(buffer, reason)

                logger.info(
                    f"Deleted buffer {buffer.buffer_id} "
                    f"({buffer.metadata.original_filename}) - {reason.value}"
                )

                return True

            else:
                result.buffers_errored += 1
                result.errors.append(f"Failed to delete {buffer.buffer_id}")
                return False

        except Exception as e:
            result.buffers_errored += 1
            result.errors.append(f"Error deleting {buffer.buffer_id}: {e}")

            if self._on_delete_error:
                await self._on_delete_error(buffer, str(e))

            logger.error(f"Deletion error for {buffer.buffer_id}: {e}")
            return False

    # Rule management

    def add_rule(self, rule: DeletionRule) -> None:
        """Add a deletion rule.

        Args:
            rule: Rule to add
        """
        self._rules[rule.rule_id] = rule
        logger.info(f"Added deletion rule: {rule.rule_id}")

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a deletion rule.

        Args:
            rule_id: Rule ID to remove

        Returns:
            True if removed
        """
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info(f"Removed deletion rule: {rule_id}")
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a deletion rule.

        Args:
            rule_id: Rule ID to enable

        Returns:
            True if enabled
        """
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a deletion rule.

        Args:
            rule_id: Rule ID to disable

        Returns:
            True if disabled
        """
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False
            return True
        return False

    def list_rules(self) -> List[DeletionRule]:
        """List all deletion rules.

        Returns:
            List of rules
        """
        return list(self._rules.values())

    # Manual deletion

    async def force_delete(
        self,
        buffer_id: str,
        reason: DeleteReason = DeleteReason.MANUAL_DELETE,
    ) -> bool:
        """Force delete a buffer immediately.

        Args:
            buffer_id: Buffer ID to delete
            reason: Deletion reason

        Returns:
            True if deleted
        """
        buffer = await self.railway.get_buffer(buffer_id)
        if not buffer:
            return False

        # Pre-delete callback
        if self._on_pre_delete:
            should_continue = await self._on_pre_delete(buffer, reason)
            if not should_continue:
                return False

        # Delete
        success = await self.railway.delete_buffer(buffer_id, force=True)

        if success:
            # Delete local copy if configured
            if self.config.delete_local_copies and buffer.local_path:
                if os.path.exists(buffer.local_path):
                    os.remove(buffer.local_path)

            # Callback
            if self._on_delete:
                await self._on_delete(buffer, reason)

        return success

    async def schedule_deletion(
        self,
        buffer_id: str,
    ) -> bool:
        """Schedule a buffer for deletion in next cleanup run.

        Args:
            buffer_id: Buffer ID to schedule

        Returns:
            True if scheduled
        """
        buffer = await self.railway.get_buffer(buffer_id)
        if not buffer:
            return False

        buffer.mark_pending_delete()
        await self.railway.update_buffer_status(
            buffer_id,
            BufferStatus.PENDING_DELETE
        )

        logger.info(f"Scheduled buffer {buffer_id} for deletion")
        return True

    # Stats and history

    def get_cleanup_history(
        self,
        limit: int = 10,
    ) -> List[CleanupResult]:
        """Get cleanup run history.

        Args:
            limit: Maximum results

        Returns:
            List of cleanup results
        """
        return self._cleanup_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get cleanup service statistics.

        Returns:
            Statistics dictionary
        """
        total_deleted = sum(r.buffers_deleted for r in self._cleanup_history)
        total_bytes = sum(r.bytes_freed for r in self._cleanup_history)
        total_errors = sum(r.buffers_errored for r in self._cleanup_history)

        # Aggregate deletion reasons
        all_reasons: Dict[str, int] = {}
        for r in self._cleanup_history:
            for reason, count in r.deletion_reasons.items():
                all_reasons[reason] = all_reasons.get(reason, 0) + count

        return {
            "running": self._running,
            "auto_cleanup": self.config.auto_cleanup,
            "dry_run": self.config.dry_run,
            "rules_count": len(self._rules),
            "enabled_rules": len([r for r in self._rules.values() if r.enabled]),
            "cleanup_runs": len(self._cleanup_history),
            "total_deleted": total_deleted,
            "total_bytes_freed": total_bytes,
            "total_mb_freed": round(total_bytes / (1024 * 1024), 2),
            "total_errors": total_errors,
            "deletion_reasons": all_reasons,
            "config": {
                "check_interval": self.config.check_interval,
                "max_deletions_per_run": self.config.max_deletions_per_run,
                "require_transcription_verification": self.config.require_transcription_verification,
                "grace_period_hours": self.config.grace_period_hours,
            },
        }

    async def get_deletion_preview(
        self,
        limit: int = 20,
    ) -> List[DeletionCandidate]:
        """Preview what would be deleted in next cleanup.

        Args:
            limit: Maximum candidates to return

        Returns:
            List of deletion candidates
        """
        buffers = await self.railway.list_buffers(
            include_expired=True,
            limit=500,
        )

        candidates = self._find_candidates(buffers)
        return candidates[:limit]
