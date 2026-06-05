"""Buffer Coordinator Service for CAPTURE-001.

Coordinates all ephemeral buffer services and provides unified interface.

WHO: ephemeral-buffer:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-001)
"""

import os
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

from src.integrations.ephemeral_buffer_schema import (
    EphemeralBuffer,
    BufferStatus,
    BufferType,
    BufferMetadata,
    DeletionRule,
    DeleteReason,
    BufferStats,
)
from src.services.capture.railway_buffer import (
    RailwayBufferService,
    RailwayConfig,
)
from src.services.capture.download_sync import (
    DownloadSyncService,
    DownloadConfig,
    DownloadResult,
)
from src.services.capture.transcription_verifier import (
    TranscriptionVerifier,
    TranscriptionConfig,
)
from src.services.capture.cleanup_automation import (
    CleanupAutomation,
    CleanupConfig,
    CleanupResult,
)
from src.services.capture.audit_logger import (
    AuditLogger,
    AuditConfig,
    AuditReport,
)

logger = logging.getLogger(__name__)


@dataclass
class CoordinatorConfig:
    """Configuration for buffer coordinator."""

    # Enable/disable services
    enable_railway: bool = True
    enable_download: bool = True
    enable_transcription: bool = True
    enable_cleanup: bool = True
    enable_audit: bool = True

    # Service configurations
    railway_config: Optional[RailwayConfig] = None
    download_config: Optional[DownloadConfig] = None
    transcription_config: Optional[TranscriptionConfig] = None
    cleanup_config: Optional[CleanupConfig] = None
    audit_config: Optional[AuditConfig] = None

    # Local mode for development
    local_mode: bool = False

    # Project name for tagging
    project_name: str = "memory-mcp-triple-system"


class BufferCoordinator:
    """Coordinator service for ephemeral buffer automation.

    This service:
    - Orchestrates all buffer services
    - Provides unified API for buffer operations
    - Handles service lifecycle
    - Connects audit logging to all operations
    """

    def __init__(
        self,
        config: Optional[CoordinatorConfig] = None,
    ):
        """Initialize buffer coordinator.

        Args:
            config: Coordinator configuration
        """
        self.config = config or CoordinatorConfig()

        # Initialize services
        self._railway: Optional[RailwayBufferService] = None
        self._download: Optional[DownloadSyncService] = None
        self._transcription: Optional[TranscriptionVerifier] = None
        self._cleanup: Optional[CleanupAutomation] = None
        self._audit: Optional[AuditLogger] = None

        # Running state
        self._running = False

        # Service initialization tracking
        self._services_started = False

    async def start(self) -> None:
        """Start all coordinator services."""
        if self._running:
            return

        logger.info("Starting BufferCoordinator...")

        # Start audit logger first (for logging startup)
        if self.config.enable_audit:
            audit_config = self.config.audit_config or AuditConfig()
            self._audit = AuditLogger(audit_config)
            await self._audit.start()
            logger.info("  - AuditLogger started")

        # Start Railway buffer service
        if self.config.enable_railway:
            railway_config = self.config.railway_config or RailwayConfig(
                local_mode=self.config.local_mode
            )
            self._railway = RailwayBufferService(
                railway_config,
                on_upload=self._on_buffer_uploaded,
                on_delete=self._on_buffer_deleted,
            )
            await self._railway.start()
            logger.info("  - RailwayBufferService started")

        # Start download sync service
        if self.config.enable_download and self._railway:
            download_config = self.config.download_config or DownloadConfig()
            self._download = DownloadSyncService(
                self._railway,
                download_config,
                on_download_complete=self._on_download_complete,
                on_download_error=self._on_download_error,
            )
            await self._download.start()
            logger.info("  - DownloadSyncService started")

        # Start transcription verifier
        if self.config.enable_transcription and self._railway:
            transcription_config = self.config.transcription_config or TranscriptionConfig()
            self._transcription = TranscriptionVerifier(
                self._railway,
                transcription_config,
                on_transcription_complete=self._on_transcription_complete,
                on_transcription_error=self._on_transcription_error,
            )
            await self._transcription.start()
            logger.info("  - TranscriptionVerifier started")

        # Start cleanup automation
        if self.config.enable_cleanup and self._railway:
            cleanup_config = self.config.cleanup_config or CleanupConfig()
            self._cleanup = CleanupAutomation(
                self._railway,
                cleanup_config,
                on_pre_delete=self._on_pre_delete,
                on_delete=self._on_cleanup_delete,
                on_delete_error=self._on_delete_error,
            )
            await self._cleanup.start()
            logger.info("  - CleanupAutomation started")

        self._running = True
        self._services_started = True

        logger.info("BufferCoordinator started successfully")

    async def stop(self) -> None:
        """Stop all coordinator services."""
        if not self._running:
            return

        logger.info("Stopping BufferCoordinator...")

        # Stop in reverse order
        if self._cleanup:
            await self._cleanup.stop()
            logger.info("  - CleanupAutomation stopped")

        if self._transcription:
            await self._transcription.stop()
            logger.info("  - TranscriptionVerifier stopped")

        if self._download:
            await self._download.stop()
            logger.info("  - DownloadSyncService stopped")

        if self._railway:
            await self._railway.stop()
            logger.info("  - RailwayBufferService stopped")

        if self._audit:
            await self._audit.stop()
            logger.info("  - AuditLogger stopped")

        self._running = False

        logger.info("BufferCoordinator stopped")

    # Service callbacks

    async def _on_buffer_uploaded(self, buffer: EphemeralBuffer) -> None:
        """Handle buffer uploaded event."""
        if self._audit:
            await self._audit.log_uploaded(buffer)

    async def _on_buffer_deleted(self, buffer: EphemeralBuffer) -> None:
        """Handle buffer deleted event (from Railway service)."""
        # Logged by cleanup automation
        pass

    async def _on_download_complete(
        self,
        buffer: EphemeralBuffer,
        result: DownloadResult,
    ) -> None:
        """Handle download complete event."""
        if self._audit:
            await self._audit.log_download_completed(
                buffer,
                result.local_path or "",
                result.checksum_verified,
                actor=AuditLogger.ACTOR_SYNC,
            )

    async def _on_download_error(
        self,
        buffer: EphemeralBuffer,
        error: str,
    ) -> None:
        """Handle download error event."""
        if self._audit:
            await self._audit.log_error(
                buffer,
                f"Download error: {error}",
                actor=AuditLogger.ACTOR_SYNC,
            )

    async def _on_transcription_complete(
        self,
        buffer: EphemeralBuffer,
        result: Any,  # TranscriptionResult
    ) -> None:
        """Handle transcription complete event."""
        if self._audit:
            await self._audit.log_transcription_completed(
                buffer,
                result.word_count,
                result.confidence_score,
                actor=AuditLogger.ACTOR_TRANSCRIPTION,
            )

    async def _on_transcription_error(
        self,
        buffer: EphemeralBuffer,
        error: str,
    ) -> None:
        """Handle transcription error event."""
        if self._audit:
            await self._audit.log_error(
                buffer,
                f"Transcription error: {error}",
                actor=AuditLogger.ACTOR_TRANSCRIPTION,
            )

    async def _on_pre_delete(
        self,
        buffer: EphemeralBuffer,
        reason: DeleteReason,
    ) -> bool:
        """Handle pre-delete event. Return False to cancel deletion."""
        if self._audit:
            await self._audit.log_deletion_scheduled(buffer, reason)
        return True  # Allow deletion

    async def _on_cleanup_delete(
        self,
        buffer: EphemeralBuffer,
        reason: DeleteReason,
    ) -> None:
        """Handle cleanup deletion event."""
        if self._audit:
            await self._audit.log_deleted(
                buffer,
                reason,
                actor=AuditLogger.ACTOR_CLEANUP,
            )

    async def _on_delete_error(
        self,
        buffer: EphemeralBuffer,
        error: str,
    ) -> None:
        """Handle deletion error event."""
        if self._audit:
            await self._audit.log_error(
                buffer,
                f"Deletion error: {error}",
                actor=AuditLogger.ACTOR_CLEANUP,
            )

    # High-level buffer operations

    async def upload_buffer(
        self,
        file_path: str,
        buffer_type: BufferType,
        metadata: Optional[BufferMetadata] = None,
        expires_in_days: int = 7,
    ) -> EphemeralBuffer:
        """Upload a file to ephemeral buffer storage.

        Args:
            file_path: Path to file
            buffer_type: Type of content
            metadata: Optional metadata
            expires_in_days: Days until expiration

        Returns:
            Created EphemeralBuffer
        """
        if not self._railway:
            raise RuntimeError("Railway service not started")

        buffer = await self._railway.upload_buffer(
            file_path,
            buffer_type,
            metadata,
            expires_in_days,
        )

        if self._audit:
            await self._audit.log_created(buffer)

        return buffer

    async def upload_bytes(
        self,
        data: bytes,
        filename: str,
        buffer_type: BufferType,
        metadata: Optional[BufferMetadata] = None,
        expires_in_days: int = 7,
    ) -> EphemeralBuffer:
        """Upload bytes to ephemeral buffer storage.

        Args:
            data: Bytes to upload
            filename: Filename
            buffer_type: Type of content
            metadata: Optional metadata
            expires_in_days: Days until expiration

        Returns:
            Created EphemeralBuffer
        """
        if not self._railway:
            raise RuntimeError("Railway service not started")

        buffer = await self._railway.upload_bytes(
            data,
            filename,
            buffer_type,
            metadata,
            expires_in_days,
        )

        if self._audit:
            await self._audit.log_created(buffer)

        return buffer

    async def get_buffer(self, buffer_id: str) -> Optional[EphemeralBuffer]:
        """Get buffer by ID.

        Args:
            buffer_id: Buffer ID

        Returns:
            EphemeralBuffer if found
        """
        if not self._railway:
            return None
        return await self._railway.get_buffer(buffer_id)

    async def list_buffers(
        self,
        status: Optional[BufferStatus] = None,
        buffer_type: Optional[BufferType] = None,
        include_expired: bool = False,
        limit: int = 100,
    ) -> List[EphemeralBuffer]:
        """List buffers with filtering.

        Args:
            status: Filter by status
            buffer_type: Filter by type
            include_expired: Include expired buffers
            limit: Maximum results

        Returns:
            List of buffers
        """
        if not self._railway:
            return []
        return await self._railway.list_buffers(
            status,
            buffer_type,
            include_expired,
            limit,
        )

    async def download_buffer(
        self,
        buffer_id: str,
        force: bool = False,
    ) -> Optional[DownloadResult]:
        """Download a buffer to local machine.

        Args:
            buffer_id: Buffer ID
            force: Force re-download

        Returns:
            DownloadResult if successful
        """
        if not self._download:
            raise RuntimeError("Download service not started")

        if self._audit:
            buffer = await self._railway.get_buffer(buffer_id)
            if buffer:
                await self._audit.log_download_started(buffer)

        return await self._download.download_buffer(buffer_id, force)

    async def transcribe_buffer(
        self,
        buffer_id: str,
        force: bool = False,
    ) -> Optional[Any]:  # TranscriptionResult
        """Transcribe a buffer.

        Args:
            buffer_id: Buffer ID
            force: Force re-transcription

        Returns:
            TranscriptionResult if successful
        """
        if not self._transcription:
            raise RuntimeError("Transcription service not started")

        if self._audit:
            buffer = await self._railway.get_buffer(buffer_id)
            if buffer:
                await self._audit.log_transcription_started(buffer)

        return await self._transcription.transcribe_buffer(buffer_id, force)

    async def delete_buffer(
        self,
        buffer_id: str,
        reason: DeleteReason = DeleteReason.MANUAL_DELETE,
    ) -> bool:
        """Delete a buffer.

        Args:
            buffer_id: Buffer ID
            reason: Deletion reason

        Returns:
            True if deleted
        """
        if not self._cleanup:
            # Direct deletion via Railway
            if self._railway:
                buffer = await self._railway.get_buffer(buffer_id)
                success = await self._railway.delete_buffer(buffer_id, force=True)
                if success and self._audit and buffer:
                    await self._audit.log_deleted(buffer, reason, AuditLogger.ACTOR_USER)
                return success
            return False

        return await self._cleanup.force_delete(buffer_id, reason)

    async def run_cleanup(
        self,
        dry_run: bool = False,
    ) -> Optional[CleanupResult]:
        """Run cleanup manually.

        Args:
            dry_run: Simulate without deleting

        Returns:
            CleanupResult
        """
        if not self._cleanup:
            raise RuntimeError("Cleanup service not started")
        return await self._cleanup.run_cleanup(dry_run)

    async def sync_downloads(self) -> Optional[Any]:
        """Sync pending downloads.

        Returns:
            SyncProgress
        """
        if not self._download:
            raise RuntimeError("Download service not started")
        return await self._download.sync_pending()

    # Reporting and stats

    def get_buffer_stats(self) -> Optional[BufferStats]:
        """Get buffer statistics.

        Returns:
            BufferStats
        """
        if not self._railway:
            return None
        return self._railway.get_stats()

    async def generate_audit_report(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[AuditReport]:
        """Generate audit report.

        Args:
            start_date: Report start
            end_date: Report end

        Returns:
            AuditReport
        """
        if not self._audit:
            return None
        return await self._audit.generate_report(start_date, end_date)

    async def export_audit_log(
        self,
        start_date: datetime,
        end_date: datetime,
        output_path: str,
    ) -> Optional[str]:
        """Export audit log for compliance.

        Args:
            start_date: Export start
            end_date: Export end
            output_path: Output file path

        Returns:
            Path to exported file
        """
        if not self._audit:
            return None
        return await self._audit.export_for_compliance(
            start_date,
            end_date,
            output_path,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive coordinator stats.

        Returns:
            Stats dictionary
        """
        stats = {
            "running": self._running,
            "services_enabled": {
                "railway": self.config.enable_railway,
                "download": self.config.enable_download,
                "transcription": self.config.enable_transcription,
                "cleanup": self.config.enable_cleanup,
                "audit": self.config.enable_audit,
            },
        }

        if self._railway:
            stats["railway"] = self._railway.get_stats().to_dict()

        if self._download:
            stats["download"] = self._download.get_stats()

        if self._transcription:
            stats["transcription"] = self._transcription.get_stats()

        if self._cleanup:
            stats["cleanup"] = self._cleanup.get_stats()

        if self._audit:
            stats["audit"] = self._audit.get_stats()

        return stats

    # Deletion rule management

    def add_deletion_rule(self, rule: DeletionRule) -> None:
        """Add a deletion rule.

        Args:
            rule: Rule to add
        """
        if self._cleanup:
            self._cleanup.add_rule(rule)

    def remove_deletion_rule(self, rule_id: str) -> bool:
        """Remove a deletion rule.

        Args:
            rule_id: Rule ID

        Returns:
            True if removed
        """
        if self._cleanup:
            return self._cleanup.remove_rule(rule_id)
        return False

    def list_deletion_rules(self) -> List[DeletionRule]:
        """List deletion rules.

        Returns:
            List of rules
        """
        if self._cleanup:
            return self._cleanup.list_rules()
        return []


# Global coordinator instance
_coordinator: Optional[BufferCoordinator] = None


def get_buffer_coordinator() -> BufferCoordinator:
    """Get global buffer coordinator instance.

    Returns:
        BufferCoordinator instance
    """
    global _coordinator
    if _coordinator is None:
        _coordinator = BufferCoordinator()
    return _coordinator


async def initialize_coordinator(
    config: Optional[CoordinatorConfig] = None,
) -> BufferCoordinator:
    """Initialize and start the global coordinator.

    Args:
        config: Coordinator configuration

    Returns:
        Started BufferCoordinator
    """
    global _coordinator
    if _coordinator is not None:
        await _coordinator.stop()

    _coordinator = BufferCoordinator(config)
    await _coordinator.start()
    return _coordinator
