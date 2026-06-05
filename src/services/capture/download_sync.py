"""Download Sync Service for CAPTURE-001.

Handles downloading ephemeral buffers from Railway to Home PC.

WHO: ephemeral-buffer:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-001)
"""

import os
import asyncio
import aiofiles
import aiohttp
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
import logging
import hashlib

from src.integrations.ephemeral_buffer_schema import (
    EphemeralBuffer,
    BufferStatus,
    BufferType,
    compute_file_checksum,
)
from src.services.capture.railway_buffer import RailwayBufferService

logger = logging.getLogger(__name__)


@dataclass
class DownloadConfig:
    """Configuration for download sync service."""

    # Local download directory
    download_path: str = ""

    # Organize by date
    organize_by_date: bool = True

    # Organize by type
    organize_by_type: bool = True

    # Maximum concurrent downloads
    max_concurrent: int = 3

    # Download timeout (seconds)
    timeout: float = 300.0

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 5.0

    # Auto-delete after verification
    auto_verify: bool = True

    # Sync interval (seconds) for background sync
    sync_interval: float = 300.0

    # Network settings
    chunk_size: int = 8192

    def __post_init__(self):
        if not self.download_path:
            self.download_path = os.path.join(
                os.path.expanduser("~"),
                "Downloads",
                "ephemeral-captures"
            )


@dataclass
class DownloadResult:
    """Result of a download operation."""

    buffer_id: str
    success: bool
    local_path: Optional[str] = None
    checksum: Optional[str] = None
    checksum_verified: bool = False
    error_message: Optional[str] = None
    download_time_seconds: float = 0.0
    file_size_bytes: int = 0


@dataclass
class SyncProgress:
    """Progress of sync operation."""

    total_pending: int = 0
    downloaded: int = 0
    failed: int = 0
    skipped: int = 0
    in_progress: int = 0
    current_buffer_id: Optional[str] = None
    current_progress_percent: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def is_complete(self) -> bool:
        """Check if sync is complete."""
        return self.downloaded + self.failed + self.skipped >= self.total_pending


class DownloadSyncService:
    """Service for downloading ephemeral buffers to Home PC.

    This service handles:
    - Downloading buffers from Railway temp storage
    - Checksum verification after download
    - Organized file storage (by date/type)
    - Background sync with configurable intervals
    - Progress tracking and reporting
    """

    def __init__(
        self,
        railway_service: RailwayBufferService,
        config: Optional[DownloadConfig] = None,
        on_download_complete: Optional[Callable[[EphemeralBuffer, DownloadResult], Awaitable[None]]] = None,
        on_download_error: Optional[Callable[[EphemeralBuffer, str], Awaitable[None]]] = None,
    ):
        """Initialize download sync service.

        Args:
            railway_service: Railway buffer service instance
            config: Download configuration
            on_download_complete: Callback on successful download
            on_download_error: Callback on download error
        """
        self.railway = railway_service
        self.config = config or DownloadConfig()
        self._on_complete = on_download_complete
        self._on_error = on_download_error

        # Download tracking
        self._active_downloads: Dict[str, asyncio.Task] = {}
        self._download_history: List[DownloadResult] = []
        self._progress = SyncProgress()

        # Semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)

        # Running state
        self._running = False
        self._sync_task: Optional[asyncio.Task] = None

        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        """Start the download sync service."""
        if self._running:
            return

        # Ensure download directory exists
        os.makedirs(self.config.download_path, exist_ok=True)

        # Create HTTP session for remote downloads
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )

        self._running = True

        # Start background sync task
        self._sync_task = asyncio.create_task(self._sync_loop())

        logger.info(f"DownloadSyncService started, path: {self.config.download_path}")

    async def stop(self) -> None:
        """Stop the download sync service."""
        self._running = False

        # Cancel sync task
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self._sync_task = None

        # Cancel active downloads
        for task in self._active_downloads.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._active_downloads.clear()

        # Close HTTP session
        if self._session:
            await self._session.close()
            self._session = None

        logger.info("DownloadSyncService stopped")

    async def _sync_loop(self) -> None:
        """Background sync loop."""
        while self._running:
            try:
                await self.sync_pending()
                await asyncio.sleep(self.config.sync_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(60)  # Wait before retry

    async def sync_pending(self) -> SyncProgress:
        """Sync all pending downloads.

        Returns:
            Sync progress summary
        """
        # Get pending buffers
        pending = await self.railway.get_pending_downloads()

        self._progress = SyncProgress(
            total_pending=len(pending),
            started_at=datetime.now(timezone.utc),
        )

        if not pending:
            self._progress.completed_at = datetime.now(timezone.utc)
            return self._progress

        # Download each buffer with concurrency control
        tasks = []
        for buffer in pending:
            task = asyncio.create_task(self._download_with_semaphore(buffer))
            tasks.append(task)
            self._active_downloads[buffer.buffer_id] = task

        # Wait for all downloads
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                self._progress.failed += 1
            elif isinstance(result, DownloadResult):
                if result.success:
                    self._progress.downloaded += 1
                else:
                    self._progress.failed += 1

        self._progress.completed_at = datetime.now(timezone.utc)
        self._active_downloads.clear()

        return self._progress

    async def _download_with_semaphore(self, buffer: EphemeralBuffer) -> DownloadResult:
        """Download with semaphore for concurrency control."""
        async with self._semaphore:
            self._progress.in_progress += 1
            self._progress.current_buffer_id = buffer.buffer_id

            try:
                result = await self.download_buffer(buffer.buffer_id)
                return result
            finally:
                self._progress.in_progress -= 1

    async def download_buffer(
        self,
        buffer_id: str,
        force: bool = False,
    ) -> DownloadResult:
        """Download a single buffer.

        Args:
            buffer_id: Buffer ID to download
            force: Force re-download even if already downloaded

        Returns:
            Download result
        """
        start_time = datetime.now(timezone.utc)

        # Get buffer
        buffer = await self.railway.get_buffer(buffer_id)
        if not buffer:
            return DownloadResult(
                buffer_id=buffer_id,
                success=False,
                error_message="Buffer not found",
            )

        # Check if already downloaded
        if not force and buffer.status in [
            BufferStatus.DOWNLOADED,
            BufferStatus.TRANSCRIBING,
            BufferStatus.TRANSCRIBED,
        ]:
            return DownloadResult(
                buffer_id=buffer_id,
                success=True,
                local_path=buffer.local_path,
                checksum=buffer.local_checksum,
                checksum_verified=True,
            )

        # Determine local path
        local_path = self._get_local_path(buffer)

        try:
            # Mark as downloading
            buffer.mark_downloading()
            await self.railway.update_buffer_status(buffer_id, BufferStatus.DOWNLOADING)

            # Download content
            content = await self._download_content(buffer)
            if content is None:
                raise Exception("Failed to download content")

            # Write to local file
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            async with aiofiles.open(local_path, "wb") as f:
                await f.write(content)

            # Compute checksum
            local_checksum = compute_file_checksum(local_path)

            # Verify checksum
            checksum_verified = local_checksum == buffer.railway_checksum
            if not checksum_verified:
                logger.warning(
                    f"Checksum mismatch for {buffer_id}: "
                    f"{local_checksum} != {buffer.railway_checksum}"
                )

            # Update buffer status
            buffer.mark_downloaded(local_path, local_checksum)
            await self.railway.update_buffer_status(buffer_id, BufferStatus.DOWNLOADED)

            # Calculate download time
            download_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            result = DownloadResult(
                buffer_id=buffer_id,
                success=True,
                local_path=local_path,
                checksum=local_checksum,
                checksum_verified=checksum_verified,
                download_time_seconds=download_time,
                file_size_bytes=len(content),
            )

            # Store in history
            self._download_history.append(result)

            # Callback
            if self._on_complete:
                await self._on_complete(buffer, result)

            logger.info(
                f"Downloaded buffer {buffer_id} to {local_path} "
                f"({len(content)} bytes, {download_time:.1f}s)"
            )

            return result

        except Exception as e:
            error_msg = str(e)
            buffer.mark_error(error_msg)
            await self.railway.update_buffer_status(buffer_id, BufferStatus.ERROR)

            result = DownloadResult(
                buffer_id=buffer_id,
                success=False,
                error_message=error_msg,
            )

            self._download_history.append(result)

            if self._on_error:
                await self._on_error(buffer, error_msg)

            logger.error(f"Failed to download buffer {buffer_id}: {e}")

            return result

    def _get_local_path(self, buffer: EphemeralBuffer) -> str:
        """Get local path for downloaded buffer.

        Args:
            buffer: Buffer to download

        Returns:
            Local file path
        """
        path_parts = [self.config.download_path]

        # Organize by date
        if self.config.organize_by_date:
            date_str = buffer.created_at.strftime("%Y-%m-%d")
            path_parts.append(date_str)

        # Organize by type
        if self.config.organize_by_type:
            type_dir = buffer.buffer_type.value.replace("-", "_")
            path_parts.append(type_dir)

        # Add filename
        path_parts.append(buffer.metadata.original_filename)

        return os.path.join(*path_parts)

    async def _download_content(self, buffer: EphemeralBuffer) -> Optional[bytes]:
        """Download buffer content.

        Args:
            buffer: Buffer to download

        Returns:
            Content bytes or None
        """
        # Try file:// URL (local/same-machine)
        if buffer.railway_url and buffer.railway_url.startswith("file://"):
            file_path = buffer.railway_url[7:]  # Remove file:// prefix
            if os.path.exists(file_path):
                async with aiofiles.open(file_path, "rb") as f:
                    return await f.read()

        # Try direct Railway path
        if os.path.exists(buffer.railway_path):
            async with aiofiles.open(buffer.railway_path, "rb") as f:
                return await f.read()

        # Try HTTP URL
        if buffer.railway_url and buffer.railway_url.startswith("http"):
            return await self._download_http(buffer.railway_url)

        # Try reading from service
        return await self.railway.read_buffer(buffer.buffer_id)

    async def _download_http(self, url: str) -> Optional[bytes]:
        """Download content from HTTP URL.

        Args:
            url: HTTP URL

        Returns:
            Content bytes or None
        """
        if not self._session:
            return None

        for attempt in range(self.config.max_retries):
            try:
                async with self._session.get(url) as response:
                    if response.status == 200:
                        return await response.read()

                    logger.warning(f"HTTP {response.status} for {url}")

            except Exception as e:
                logger.warning(f"HTTP error (attempt {attempt + 1}): {e}")

            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(self.config.retry_delay)

        return None

    async def verify_download(self, buffer_id: str) -> bool:
        """Verify a downloaded buffer's integrity.

        Args:
            buffer_id: Buffer ID to verify

        Returns:
            True if verification passed
        """
        buffer = await self.railway.get_buffer(buffer_id)
        if not buffer or not buffer.local_path:
            return False

        if not os.path.exists(buffer.local_path):
            return False

        local_checksum = compute_file_checksum(buffer.local_path)
        return local_checksum == buffer.railway_checksum

    async def get_downloaded_buffers(self) -> List[EphemeralBuffer]:
        """Get all downloaded buffers.

        Returns:
            List of downloaded buffers
        """
        return await self.railway.list_buffers(status=BufferStatus.DOWNLOADED)

    def get_progress(self) -> SyncProgress:
        """Get current sync progress.

        Returns:
            Current progress
        """
        return self._progress

    def get_download_history(
        self,
        limit: int = 100,
        success_only: bool = False,
    ) -> List[DownloadResult]:
        """Get download history.

        Args:
            limit: Maximum results
            success_only: Only successful downloads

        Returns:
            List of download results
        """
        history = self._download_history[-limit:]

        if success_only:
            history = [r for r in history if r.success]

        return history

    def get_stats(self) -> Dict[str, Any]:
        """Get download service statistics.

        Returns:
            Statistics dictionary
        """
        total_downloaded = sum(1 for r in self._download_history if r.success)
        total_failed = sum(1 for r in self._download_history if not r.success)
        total_bytes = sum(
            r.file_size_bytes
            for r in self._download_history
            if r.success
        )
        avg_time = 0.0
        if total_downloaded > 0:
            avg_time = sum(
                r.download_time_seconds
                for r in self._download_history
                if r.success
            ) / total_downloaded

        return {
            "running": self._running,
            "download_path": self.config.download_path,
            "active_downloads": len(self._active_downloads),
            "history": {
                "total_downloaded": total_downloaded,
                "total_failed": total_failed,
                "total_bytes": total_bytes,
                "total_mb": round(total_bytes / (1024 * 1024), 2),
                "average_time_seconds": round(avg_time, 2),
            },
            "progress": {
                "total_pending": self._progress.total_pending,
                "downloaded": self._progress.downloaded,
                "failed": self._progress.failed,
                "in_progress": self._progress.in_progress,
            },
            "config": {
                "max_concurrent": self.config.max_concurrent,
                "sync_interval": self.config.sync_interval,
                "organize_by_date": self.config.organize_by_date,
                "organize_by_type": self.config.organize_by_type,
            },
        }
