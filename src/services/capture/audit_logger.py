"""Audit Logger Service for CAPTURE-001.

Provides comprehensive audit logging for all ephemeral buffer operations.
Maintains audit trail for compliance and debugging.

WHO: ephemeral-buffer:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-001)
"""

import os
import json
import asyncio
import aiofiles
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path
import logging

from src.integrations.ephemeral_buffer_schema import (
    EphemeralBuffer,
    BufferStatus,
    AuditAction,
    AuditLogEntry,
    DeleteReason,
)

logger = logging.getLogger(__name__)


@dataclass
class AuditConfig:
    """Configuration for audit logging."""

    # Audit log storage path
    log_path: str = ""

    # Log rotation settings
    rotate_daily: bool = True
    retention_days: int = 90

    # Log format
    format: str = "jsonl"  # jsonl or json

    # Include checksums in audit entries
    include_checksums: bool = True

    # Enable real-time log streaming
    stream_logs: bool = False

    # Compression for older logs
    compress_after_days: int = 7

    # Maximum entries per file (for rotation)
    max_entries_per_file: int = 10000

    def __post_init__(self):
        if not self.log_path:
            self.log_path = os.path.join(
                os.path.expanduser("~"), ".claude", "ephemeral-audit"
            )


@dataclass
class AuditReport:
    """Audit report summary."""

    report_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    total_entries: int
    by_action: Dict[str, int] = field(default_factory=dict)
    by_actor: Dict[str, int] = field(default_factory=dict)
    success_count: int = 0
    error_count: int = 0
    buffers_created: int = 0
    buffers_deleted: int = 0
    total_bytes_deleted: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "total_entries": self.total_entries,
            "by_action": self.by_action,
            "by_actor": self.by_actor,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "buffers_created": self.buffers_created,
            "buffers_deleted": self.buffers_deleted,
            "total_bytes_deleted": self.total_bytes_deleted,
            "mb_deleted": round(self.total_bytes_deleted / (1024 * 1024), 2),
        }


class AuditLogger:
    """Service for audit logging of ephemeral buffer operations.

    This service handles:
    - Comprehensive logging of all buffer operations
    - Audit trail for deletions (compliance requirement)
    - Log rotation and retention
    - Query and reporting capabilities
    - Export for compliance audits
    """

    ACTOR_SYSTEM = "system"
    ACTOR_USER = "user"
    ACTOR_CLEANUP = "cleanup-automation"
    ACTOR_SYNC = "download-sync"
    ACTOR_TRANSCRIPTION = "transcription-verifier"

    def __init__(
        self,
        config: Optional[AuditConfig] = None,
    ):
        """Initialize audit logger.

        Args:
            config: Audit configuration
        """
        self.config = config or AuditConfig()

        # In-memory log buffer (for batching writes)
        self._buffer: List[AuditLogEntry] = []
        self._buffer_size = 100  # Flush after N entries

        # Current log file
        self._current_file: Optional[str] = None
        self._current_date: Optional[str] = None
        self._entry_count = 0

        # File lock for thread safety
        self._lock = asyncio.Lock()

        # Running state
        self._running = False
        self._flush_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the audit logger."""
        if self._running:
            return

        # Ensure log directory exists
        os.makedirs(self.config.log_path, exist_ok=True)

        # Initialize log file
        self._rotate_file_if_needed()

        self._running = True

        # Start background flush task
        self._flush_task = asyncio.create_task(self._flush_loop())

        logger.info(f"AuditLogger started, path: {self.config.log_path}")

    async def stop(self) -> None:
        """Stop the audit logger."""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self._flush_buffer()

        logger.info("AuditLogger stopped")

    async def _flush_loop(self) -> None:
        """Background loop for periodic flushing."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Flush every 30 seconds
                await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")

    def _rotate_file_if_needed(self) -> None:
        """Rotate log file if needed."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if self.config.rotate_daily and self._current_date != today:
            self._current_date = today
            self._current_file = os.path.join(
                self.config.log_path, f"audit_{today}.{self.config.format}"
            )
            self._entry_count = 0
        elif self._current_file is None:
            self._current_file = os.path.join(
                self.config.log_path, f"audit_{today}.{self.config.format}"
            )

        # Check entry count
        if self._entry_count >= self.config.max_entries_per_file:
            timestamp = datetime.now(timezone.utc).strftime("%H%M%S")
            self._current_file = os.path.join(
                self.config.log_path, f"audit_{today}_{timestamp}.{self.config.format}"
            )
            self._entry_count = 0

    async def _flush_buffer(self) -> None:
        """Flush buffered entries to disk."""
        if not self._buffer:
            return

        async with self._lock:
            entries = self._buffer.copy()
            self._buffer.clear()

        self._rotate_file_if_needed()

        try:
            async with aiofiles.open(self._current_file, "a") as f:
                for entry in entries:
                    if self.config.format == "jsonl":
                        await f.write(json.dumps(entry.to_dict()) + "\n")
                    else:
                        await f.write(json.dumps(entry.to_dict(), indent=2) + ",\n")

                    self._entry_count += 1

        except Exception as e:
            logger.error(f"Error flushing audit log: {e}")
            # Re-add entries to buffer
            self._buffer.extend(entries)

    # Logging methods

    async def log_created(
        self,
        buffer: EphemeralBuffer,
        actor: str = ACTOR_SYSTEM,
    ) -> AuditLogEntry:
        """Log buffer creation.

        Args:
            buffer: Created buffer
            actor: Actor who created it

        Returns:
            Created audit entry
        """
        entry = AuditLogEntry.create(
            buffer_id=buffer.buffer_id,
            action=AuditAction.CREATED,
            actor=actor,
            details={
                "filename": buffer.metadata.original_filename,
                "file_size": buffer.metadata.file_size_bytes,
                "buffer_type": buffer.buffer_type.value,
                "railway_path": buffer.railway_path,
                "expires_at": buffer.expires_at.isoformat()
                if buffer.expires_at
                else None,
            },
            new_status=BufferStatus.PENDING_UPLOAD,
        )

        await self._add_entry(entry)
        return entry

    async def log_uploaded(
        self,
        buffer: EphemeralBuffer,
        actor: str = ACTOR_SYSTEM,
    ) -> AuditLogEntry:
        """Log buffer upload.

        Args:
            buffer: Uploaded buffer
            actor: Actor who uploaded it

        Returns:
            Created audit entry
        """
        entry = AuditLogEntry.create(
            buffer_id=buffer.buffer_id,
            action=AuditAction.UPLOADED,
            actor=actor,
            details={
                "railway_url": buffer.railway_url,
                "checksum": buffer.railway_checksum
                if self.config.include_checksums
                else None,
            },
            previous_status=BufferStatus.PENDING_UPLOAD,
            new_status=BufferStatus.UPLOADED,
        )

        await self._add_entry(entry)
        return entry

    async def log_download_started(
        self,
        buffer: EphemeralBuffer,
        actor: str = ACTOR_SYNC,
    ) -> AuditLogEntry:
        """Log download start.

        Args:
            buffer: Buffer being downloaded
            actor: Actor initiating download

        Returns:
            Created audit entry
        """
        entry = AuditLogEntry.create(
            buffer_id=buffer.buffer_id,
            action=AuditAction.DOWNLOAD_STARTED,
            actor=actor,
            previous_status=buffer.status,
            new_status=BufferStatus.DOWNLOADING,
        )

        await self._add_entry(entry)
        return entry

    async def log_download_completed(
        self,
        buffer: EphemeralBuffer,
        local_path: str,
        checksum_verified: bool,
        actor: str = ACTOR_SYNC,
    ) -> AuditLogEntry:
        """Log download completion.

        Args:
            buffer: Downloaded buffer
            local_path: Local file path
            checksum_verified: Whether checksum matched
            actor: Actor who completed download

        Returns:
            Created audit entry
        """
        entry = AuditLogEntry.create(
            buffer_id=buffer.buffer_id,
            action=AuditAction.DOWNLOAD_COMPLETED,
            actor=actor,
            details={
                "local_path": local_path,
                "checksum_verified": checksum_verified,
                "local_checksum": buffer.local_checksum
                if self.config.include_checksums
                else None,
            },
            previous_status=BufferStatus.DOWNLOADING,
            new_status=BufferStatus.DOWNLOADED,
        )

        await self._add_entry(entry)
        return entry

    async def log_transcription_started(
        self,
        buffer: EphemeralBuffer,
        actor: str = ACTOR_TRANSCRIPTION,
    ) -> AuditLogEntry:
        """Log transcription start.

        Args:
            buffer: Buffer being transcribed
            actor: Actor initiating transcription

        Returns:
            Created audit entry
        """
        entry = AuditLogEntry.create(
            buffer_id=buffer.buffer_id,
            action=AuditAction.TRANSCRIPTION_STARTED,
            actor=actor,
            previous_status=buffer.status,
            new_status=BufferStatus.TRANSCRIBING,
        )

        await self._add_entry(entry)
        return entry

    async def log_transcription_completed(
        self,
        buffer: EphemeralBuffer,
        word_count: int,
        confidence: float,
        actor: str = ACTOR_TRANSCRIPTION,
    ) -> AuditLogEntry:
        """Log transcription completion.

        Args:
            buffer: Transcribed buffer
            word_count: Number of words
            confidence: Confidence score
            actor: Actor who completed transcription

        Returns:
            Created audit entry
        """
        entry = AuditLogEntry.create(
            buffer_id=buffer.buffer_id,
            action=AuditAction.TRANSCRIPTION_COMPLETED,
            actor=actor,
            details={
                "word_count": word_count,
                "confidence": confidence,
                "transcript_path": buffer.transcription.transcript_path
                if buffer.transcription
                else None,
            },
            previous_status=BufferStatus.TRANSCRIBING,
            new_status=BufferStatus.TRANSCRIBED,
        )

        await self._add_entry(entry)
        return entry

    async def log_transcription_verified(
        self,
        buffer: EphemeralBuffer,
        actor: str = ACTOR_TRANSCRIPTION,
    ) -> AuditLogEntry:
        """Log transcription verification.

        Args:
            buffer: Verified buffer
            actor: Actor who verified

        Returns:
            Created audit entry
        """
        entry = AuditLogEntry.create(
            buffer_id=buffer.buffer_id,
            action=AuditAction.TRANSCRIPTION_VERIFIED,
            actor=actor,
            details={
                "verified_at": buffer.transcription.verified_at.isoformat()
                if buffer.transcription and buffer.transcription.verified_at
                else None,
            },
        )

        await self._add_entry(entry)
        return entry

    async def log_deletion_scheduled(
        self,
        buffer: EphemeralBuffer,
        reason: DeleteReason,
        actor: str = ACTOR_CLEANUP,
    ) -> AuditLogEntry:
        """Log deletion scheduling.

        Args:
            buffer: Buffer scheduled for deletion
            reason: Deletion reason
            actor: Actor who scheduled

        Returns:
            Created audit entry
        """
        entry = AuditLogEntry.create(
            buffer_id=buffer.buffer_id,
            action=AuditAction.DELETION_SCHEDULED,
            actor=actor,
            details={
                "reason": reason.value,
            },
            previous_status=buffer.status,
            new_status=BufferStatus.PENDING_DELETE,
        )

        await self._add_entry(entry)
        return entry

    async def log_deleted(
        self,
        buffer: EphemeralBuffer,
        reason: DeleteReason,
        actor: str = ACTOR_CLEANUP,
    ) -> AuditLogEntry:
        """Log buffer deletion.

        CRITICAL: This is the key audit entry for compliance.

        Args:
            buffer: Deleted buffer
            reason: Deletion reason
            actor: Actor who deleted

        Returns:
            Created audit entry
        """
        entry = AuditLogEntry.create(
            buffer_id=buffer.buffer_id,
            action=AuditAction.DELETED,
            actor=actor,
            details={
                "reason": reason.value,
                "filename": buffer.metadata.original_filename,
                "file_size": buffer.metadata.file_size_bytes,
                "railway_path": buffer.railway_path,
                "local_path": buffer.local_path,
                "created_at": buffer.created_at.isoformat(),
                "uploaded_at": buffer.uploaded_at.isoformat()
                if buffer.uploaded_at
                else None,
                "downloaded_at": buffer.downloaded_at.isoformat()
                if buffer.downloaded_at
                else None,
                "transcribed_at": buffer.transcribed_at.isoformat()
                if buffer.transcribed_at
                else None,
                "was_transcribed": buffer.transcription is not None,
                "transcription_verified": buffer.transcription.is_verified()
                if buffer.transcription
                else False,
                "railway_checksum": buffer.railway_checksum
                if self.config.include_checksums
                else None,
                "local_checksum": buffer.local_checksum
                if self.config.include_checksums
                else None,
            },
            previous_status=buffer.status,
            new_status=BufferStatus.DELETED,
        )

        await self._add_entry(entry)

        # Log immediately for deletions
        await self._flush_buffer()

        logger.info(
            f"AUDIT: Deleted buffer {buffer.buffer_id} "
            f"({buffer.metadata.original_filename}) - {reason.value}"
        )

        return entry

    async def log_error(
        self,
        buffer: EphemeralBuffer,
        error_message: str,
        actor: str = ACTOR_SYSTEM,
    ) -> AuditLogEntry:
        """Log an error.

        Args:
            buffer: Buffer with error
            error_message: Error description
            actor: Actor where error occurred

        Returns:
            Created audit entry
        """
        entry = AuditLogEntry.create(
            buffer_id=buffer.buffer_id,
            action=AuditAction.ERROR,
            actor=actor,
            details={
                "error": error_message,
            },
            previous_status=buffer.status,
            new_status=BufferStatus.ERROR,
            success=False,
            error_message=error_message,
        )

        await self._add_entry(entry)
        return entry

    async def log_status_changed(
        self,
        buffer: EphemeralBuffer,
        previous_status: BufferStatus,
        new_status: BufferStatus,
        actor: str = ACTOR_SYSTEM,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        """Log a status change.

        Args:
            buffer: Buffer with status change
            previous_status: Previous status
            new_status: New status
            actor: Actor who changed status
            details: Additional details

        Returns:
            Created audit entry
        """
        entry = AuditLogEntry.create(
            buffer_id=buffer.buffer_id,
            action=AuditAction.STATUS_CHANGED,
            actor=actor,
            details=details or {},
            previous_status=previous_status,
            new_status=new_status,
        )

        await self._add_entry(entry)
        return entry

    async def _add_entry(self, entry: AuditLogEntry) -> None:
        """Add entry to buffer.

        Args:
            entry: Entry to add
        """
        async with self._lock:
            self._buffer.append(entry)

            if len(self._buffer) >= self._buffer_size:
                await self._flush_buffer()

    # Query methods

    async def query_entries(
        self,
        buffer_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        actor: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        """Query audit entries.

        Args:
            buffer_id: Filter by buffer ID
            action: Filter by action
            actor: Filter by actor
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results

        Returns:
            List of matching entries
        """
        results = []

        # Get log files in date range
        log_files = self._get_log_files(start_date, end_date)

        for log_file in log_files:
            try:
                async with aiofiles.open(log_file, "r") as f:
                    content = await f.read()

                    for line in content.strip().split("\n"):
                        if not line or line == ",":
                            continue

                        try:
                            data = json.loads(line.rstrip(","))
                            entry = self._entry_from_dict(data)

                            # Apply filters
                            if buffer_id and entry.buffer_id != buffer_id:
                                continue
                            if action and entry.action != action:
                                continue
                            if actor and entry.actor != actor:
                                continue
                            if start_date and entry.timestamp < start_date:
                                continue
                            if end_date and entry.timestamp > end_date:
                                continue

                            results.append(entry)

                            if len(results) >= limit:
                                return results

                        except json.JSONDecodeError:
                            continue

            except Exception as e:
                logger.warning(f"Error reading log file {log_file}: {e}")

        return results

    def _get_log_files(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[str]:
        """Get log files in date range.

        Args:
            start_date: Start of range
            end_date: End of range

        Returns:
            List of log file paths
        """
        files = []

        for entry in os.scandir(self.config.log_path):
            if entry.is_file() and entry.name.startswith("audit_"):
                # Extract date from filename
                parts = entry.name.split("_")
                if len(parts) >= 2:
                    try:
                        file_date = datetime.strptime(
                            parts[1].split(".")[0], "%Y-%m-%d"
                        )
                        file_date = file_date.replace(tzinfo=timezone.utc)

                        if start_date and file_date < start_date.replace(
                            hour=0, minute=0, second=0, microsecond=0
                        ):
                            continue
                        if end_date and file_date > end_date:
                            continue

                        files.append(entry.path)
                    except ValueError:
                        continue

        return sorted(files)

    def _entry_from_dict(self, data: Dict[str, Any]) -> AuditLogEntry:
        """Create entry from dictionary.

        Args:
            data: Entry data

        Returns:
            AuditLogEntry
        """
        return AuditLogEntry(
            entry_id=data["entry_id"],
            buffer_id=data["buffer_id"],
            action=AuditAction(data["action"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            actor=data["actor"],
            details=data.get("details", {}),
            previous_status=BufferStatus(data["previous_status"])
            if data.get("previous_status")
            else None,
            new_status=BufferStatus(data["new_status"])
            if data.get("new_status")
            else None,
            success=data.get("success", True),
            error_message=data.get("error_message"),
        )

    # Reporting

    async def generate_report(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> AuditReport:
        """Generate an audit report.

        Args:
            start_date: Report start date
            end_date: Report end date

        Returns:
            Audit report
        """
        entries = await self.query_entries(
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )

        report = AuditReport(
            report_id=f"report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            generated_at=datetime.now(timezone.utc),
            period_start=start_date,
            period_end=end_date,
            total_entries=len(entries),
        )

        for entry in entries:
            # Count by action
            action_key = entry.action.value
            report.by_action[action_key] = report.by_action.get(action_key, 0) + 1

            # Count by actor
            report.by_actor[entry.actor] = report.by_actor.get(entry.actor, 0) + 1

            # Success/error counts
            if entry.success:
                report.success_count += 1
            else:
                report.error_count += 1

            # Specific counts
            if entry.action == AuditAction.CREATED:
                report.buffers_created += 1
            elif entry.action == AuditAction.DELETED:
                report.buffers_deleted += 1
                if "file_size" in entry.details:
                    report.total_bytes_deleted += entry.details["file_size"]

        return report

    async def export_for_compliance(
        self,
        start_date: datetime,
        end_date: datetime,
        output_path: str,
    ) -> str:
        """Export audit log for compliance review.

        Args:
            start_date: Export start date
            end_date: Export end date
            output_path: Output file path

        Returns:
            Path to exported file
        """
        entries = await self.query_entries(
            start_date=start_date,
            end_date=end_date,
            limit=100000,
        )

        # Generate compliance report
        export_data = {
            "export_metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_entries": len(entries),
            },
            "entries": [e.to_dict() for e in entries],
        }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        async with aiofiles.open(output_path, "w") as f:
            await f.write(json.dumps(export_data, indent=2))

        logger.info(f"Exported {len(entries)} audit entries to {output_path}")

        return output_path

    def get_stats(self) -> Dict[str, Any]:
        """Get audit logger statistics.

        Returns:
            Statistics dictionary
        """
        log_files = list(Path(self.config.log_path).glob("audit_*"))

        return {
            "running": self._running,
            "log_path": self.config.log_path,
            "current_file": self._current_file,
            "buffer_size": len(self._buffer),
            "log_files_count": len(log_files),
            "config": {
                "format": self.config.format,
                "rotate_daily": self.config.rotate_daily,
                "retention_days": self.config.retention_days,
                "include_checksums": self.config.include_checksums,
            },
        }
