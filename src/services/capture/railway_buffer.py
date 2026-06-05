"""Railway Temp Buffer Service for CAPTURE-001.

Manages ephemeral buffer storage on Railway temp filesystem.

WHO: ephemeral-buffer:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-001)
"""

import os
import json
import asyncio
import hashlib
import hmac
import aiofiles
import aiohttp
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass
import logging

from src.integrations.ephemeral_buffer_schema import (
    EphemeralBuffer,
    BufferStatus,
    BufferType,
    BufferMetadata,
    BufferStats,
    compute_file_checksum,
    compute_bytes_checksum,
)

logger = logging.getLogger(__name__)


@dataclass
class RailwayConfig:
    """Configuration for Railway buffer service."""

    # Railway temp storage path (typically /tmp or configured volume)
    temp_storage_path: str = "/tmp/ephemeral-buffers"

    # Local fallback for development/testing
    local_storage_path: str = ""

    # Railway API settings (if using Railway API for file ops)
    railway_api_url: Optional[str] = None
    railway_api_token: Optional[str] = None

    # Storage limits
    max_buffer_size_mb: int = 500
    max_total_storage_mb: int = 5000

    # Retention
    default_expiry_days: int = 7

    # Polling interval for status checks (seconds)
    poll_interval: float = 60.0

    # Enable local mode for development
    local_mode: bool = False


class RailwayBufferService:
    """Service for managing ephemeral buffers on Railway temp storage.

    This service handles:
    - Buffer upload and storage
    - Buffer status tracking
    - Buffer listing and querying
    - URL generation for downloads
    - Storage cleanup on Railway
    """

    def __init__(
        self,
        config: Optional[RailwayConfig] = None,
        on_upload: Optional[Callable[[EphemeralBuffer], Awaitable[None]]] = None,
        on_delete: Optional[Callable[[EphemeralBuffer], Awaitable[None]]] = None,
    ):
        """Initialize Railway buffer service.

        Args:
            config: Railway configuration
            on_upload: Callback when buffer is uploaded
            on_delete: Callback when buffer is deleted
        """
        self.config = config or RailwayConfig()
        self._on_upload = on_upload
        self._on_delete = on_delete

        # In-memory buffer registry (for session)
        self._buffers: Dict[str, EphemeralBuffer] = {}

        # Persistence path for buffer registry
        self._registry_path = os.path.join(
            self._get_storage_path(),
            "buffer_registry.json"
        )

        # Stats tracking
        self._stats = BufferStats()

        # Running state
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None

    def _get_storage_path(self) -> str:
        """Get the appropriate storage path based on mode."""
        if self.config.local_mode or not self.config.temp_storage_path:
            # Use local storage for development
            local_path = self.config.local_storage_path or os.path.join(
                os.path.expanduser("~"),
                ".claude",
                "ephemeral-buffers"
            )
            return local_path
        return self.config.temp_storage_path

    async def start(self) -> None:
        """Start the Railway buffer service."""
        if self._running:
            return

        # Ensure storage directory exists
        storage_path = self._get_storage_path()
        os.makedirs(storage_path, exist_ok=True)

        # Load existing buffer registry
        await self._load_registry()

        self._running = True

        # Start polling for expiration checks
        self._poll_task = asyncio.create_task(self._poll_loop())

        logger.info(f"RailwayBufferService started, storage: {storage_path}")

    async def stop(self) -> None:
        """Stop the Railway buffer service."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        # Save registry before stopping
        await self._save_registry()

        logger.info("RailwayBufferService stopped")

    async def _poll_loop(self) -> None:
        """Background loop for expiration checks."""
        while self._running:
            try:
                await asyncio.sleep(self.config.poll_interval)
                await self._check_expirations()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

    async def _check_expirations(self) -> None:
        """Check for expired buffers and mark them."""
        now = datetime.now(timezone.utc)
        expired = []

        for buffer in self._buffers.values():
            if buffer.is_expired(now) and buffer.status not in [
                BufferStatus.DELETED,
                BufferStatus.EXPIRED,
            ]:
                buffer.status = BufferStatus.EXPIRED
                expired.append(buffer)

        if expired:
            logger.info(f"Marked {len(expired)} buffers as expired")
            await self._save_registry()

    async def _load_registry(self) -> None:
        """Load buffer registry from disk."""
        if os.path.exists(self._registry_path):
            try:
                async with aiofiles.open(self._registry_path, "r") as f:
                    content = await f.read()
                    data = json.loads(content)

                    for buffer_data in data.get("buffers", []):
                        buffer = EphemeralBuffer.from_dict(buffer_data)
                        self._buffers[buffer.buffer_id] = buffer

                    logger.info(f"Loaded {len(self._buffers)} buffers from registry")
            except Exception as e:
                logger.error(f"Error loading registry: {e}")
                self._buffers = {}

    async def _save_registry(self) -> None:
        """Save buffer registry to disk."""
        try:
            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "buffers": [b.to_dict() for b in self._buffers.values()],
            }

            os.makedirs(os.path.dirname(self._registry_path), exist_ok=True)

            async with aiofiles.open(self._registry_path, "w") as f:
                await f.write(json.dumps(data, indent=2))

        except Exception as e:
            logger.error(f"Error saving registry: {e}")

    async def upload_buffer(
        self,
        file_path: str,
        buffer_type: BufferType,
        metadata: Optional[BufferMetadata] = None,
        expires_in_days: Optional[int] = None,
    ) -> EphemeralBuffer:
        """Upload a file to Railway temp storage.

        Args:
            file_path: Local path to file to upload
            buffer_type: Type of buffer content
            metadata: Optional metadata (auto-generated if not provided)
            expires_in_days: Days until expiration (default from config)

        Returns:
            Created EphemeralBuffer
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get file info
        file_stat = os.stat(file_path)
        file_size = file_stat.st_size

        # Check size limit
        max_size = self.config.max_buffer_size_mb * 1024 * 1024
        if file_size > max_size:
            raise ValueError(f"File too large: {file_size} > {max_size}")

        # Auto-generate metadata if not provided
        if metadata is None:
            metadata = BufferMetadata(
                original_filename=os.path.basename(file_path),
                file_size_bytes=file_size,
            )

        # Compute checksum
        checksum = compute_file_checksum(file_path)

        # Create buffer entry
        expiry = expires_in_days or self.config.default_expiry_days
        storage_path = self._get_storage_path()
        railway_path = os.path.join(
            storage_path,
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            os.path.basename(file_path)
        )

        buffer = EphemeralBuffer.create(
            railway_path=railway_path,
            buffer_type=buffer_type,
            metadata=metadata,
            expires_in_days=expiry,
        )

        # Copy file to Railway storage
        os.makedirs(os.path.dirname(railway_path), exist_ok=True)

        async with aiofiles.open(file_path, "rb") as src:
            content = await src.read()

        async with aiofiles.open(railway_path, "wb") as dst:
            await dst.write(content)

        # Generate URL (for Railway, this would be a signed URL)
        railway_url = f"file://{railway_path}"
        if self.config.railway_api_url:
            railway_url = f"{self.config.railway_api_url}/buffers/{buffer.buffer_id}"

        # Mark as uploaded
        buffer.mark_uploaded(railway_url, checksum)

        # Store in registry
        self._buffers[buffer.buffer_id] = buffer
        await self._save_registry()

        # Update stats
        self._stats.total_buffers += 1
        self._stats.uploaded += 1
        self._stats.railway_size_bytes += file_size

        # Callback
        if self._on_upload:
            await self._on_upload(buffer)

        logger.info(f"Uploaded buffer {buffer.buffer_id}: {metadata.original_filename}")

        return buffer

    async def upload_bytes(
        self,
        data: bytes,
        filename: str,
        buffer_type: BufferType,
        metadata: Optional[BufferMetadata] = None,
        expires_in_days: Optional[int] = None,
    ) -> EphemeralBuffer:
        """Upload bytes directly to Railway temp storage.

        Args:
            data: Bytes to upload
            filename: Name for the file
            buffer_type: Type of buffer content
            metadata: Optional metadata
            expires_in_days: Days until expiration

        Returns:
            Created EphemeralBuffer
        """
        # Check size limit
        max_size = self.config.max_buffer_size_mb * 1024 * 1024
        if len(data) > max_size:
            raise ValueError(f"Data too large: {len(data)} > {max_size}")

        # Auto-generate metadata
        if metadata is None:
            metadata = BufferMetadata(
                original_filename=filename,
                file_size_bytes=len(data),
            )

        # Compute checksum
        checksum = compute_bytes_checksum(data)

        # Create buffer
        expiry = expires_in_days or self.config.default_expiry_days
        storage_path = self._get_storage_path()
        railway_path = os.path.join(
            storage_path,
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            filename
        )

        buffer = EphemeralBuffer.create(
            railway_path=railway_path,
            buffer_type=buffer_type,
            metadata=metadata,
            expires_in_days=expiry,
        )

        # Write to storage
        os.makedirs(os.path.dirname(railway_path), exist_ok=True)

        async with aiofiles.open(railway_path, "wb") as f:
            await f.write(data)

        # Generate URL
        railway_url = f"file://{railway_path}"
        if self.config.railway_api_url:
            railway_url = f"{self.config.railway_api_url}/buffers/{buffer.buffer_id}"

        buffer.mark_uploaded(railway_url, checksum)

        self._buffers[buffer.buffer_id] = buffer
        await self._save_registry()

        self._stats.total_buffers += 1
        self._stats.uploaded += 1
        self._stats.railway_size_bytes += len(data)

        if self._on_upload:
            await self._on_upload(buffer)

        logger.info(f"Uploaded buffer {buffer.buffer_id}: {filename}")

        return buffer

    async def get_buffer(self, buffer_id: str) -> Optional[EphemeralBuffer]:
        """Get a buffer by ID.

        Args:
            buffer_id: Buffer ID to retrieve

        Returns:
            EphemeralBuffer if found, None otherwise
        """
        return self._buffers.get(buffer_id)

    async def list_buffers(
        self,
        status: Optional[BufferStatus] = None,
        buffer_type: Optional[BufferType] = None,
        include_expired: bool = False,
        limit: int = 100,
    ) -> List[EphemeralBuffer]:
        """List buffers with optional filtering.

        Args:
            status: Filter by status
            buffer_type: Filter by type
            include_expired: Include expired buffers
            limit: Maximum results

        Returns:
            List of matching buffers
        """
        results = []
        now = datetime.now(timezone.utc)

        for buffer in self._buffers.values():
            # Filter by status
            if status and buffer.status != status:
                continue

            # Filter by type
            if buffer_type and buffer.buffer_type != buffer_type:
                continue

            # Filter expired
            if not include_expired and buffer.is_expired(now):
                continue

            results.append(buffer)

            if len(results) >= limit:
                break

        # Sort by created_at descending
        results.sort(key=lambda b: b.created_at, reverse=True)

        return results

    async def get_download_url(
        self,
        buffer_id: str,
        expires_in_seconds: int = 3600,
    ) -> Optional[str]:
        """Get a temporary download URL for a buffer.

        Args:
            buffer_id: Buffer ID
            expires_in_seconds: URL expiration time

        Returns:
            Download URL if available
        """
        buffer = self._buffers.get(buffer_id)
        if not buffer:
            return None

        if buffer.status not in [
            BufferStatus.UPLOADED,
            BufferStatus.DOWNLOADING,
            BufferStatus.DOWNLOADED,
            BufferStatus.TRANSCRIBING,
            BufferStatus.TRANSCRIBED,
        ]:
            return None

        # For local mode, just return file:// URL
        if self.config.local_mode or not self.config.railway_api_url:
            return f"file://{buffer.railway_path}"

        if not self.config.railway_api_token:
            logger.error("Railway API token is required for signed download URLs")
            return None

        expires_at = int((datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).timestamp())
        path = f"/buffers/{buffer.buffer_id}/download"
        message = f"{buffer.buffer_id}:{buffer.railway_path}:{expires_at}".encode("utf-8")
        signature = hmac.new(
            self.config.railway_api_token.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()
        query = urlencode({"expires": expires_at, "signature": signature})
        return f"{self.config.railway_api_url.rstrip('/')}{path}?{query}"

    async def read_buffer(self, buffer_id: str) -> Optional[bytes]:
        """Read buffer contents.

        Args:
            buffer_id: Buffer ID

        Returns:
            Buffer contents as bytes
        """
        buffer = self._buffers.get(buffer_id)
        if not buffer:
            return None

        if not os.path.exists(buffer.railway_path):
            return None

        async with aiofiles.open(buffer.railway_path, "rb") as f:
            return await f.read()

    async def delete_buffer(
        self,
        buffer_id: str,
        force: bool = False,
    ) -> bool:
        """Delete a buffer from Railway storage.

        Args:
            buffer_id: Buffer ID to delete
            force: Force delete even if not marked for deletion

        Returns:
            True if deleted successfully
        """
        buffer = self._buffers.get(buffer_id)
        if not buffer:
            return False

        # Check status unless force
        if not force and buffer.status not in [
            BufferStatus.PENDING_DELETE,
            BufferStatus.EXPIRED,
        ]:
            logger.warning(f"Buffer {buffer_id} not marked for deletion")
            return False

        try:
            # Delete file from storage
            if os.path.exists(buffer.railway_path):
                os.remove(buffer.railway_path)

            # Update status
            buffer.mark_deleted()

            # Update stats
            self._stats.deleted += 1
            self._stats.railway_size_bytes -= buffer.metadata.file_size_bytes

            await self._save_registry()

            # Callback
            if self._on_delete:
                await self._on_delete(buffer)

            logger.info(f"Deleted buffer {buffer_id}")

            return True

        except Exception as e:
            logger.error(f"Error deleting buffer {buffer_id}: {e}")
            buffer.mark_error(str(e))
            return False

    async def update_buffer_status(
        self,
        buffer_id: str,
        status: BufferStatus,
    ) -> bool:
        """Update buffer status.

        Args:
            buffer_id: Buffer ID
            status: New status

        Returns:
            True if updated
        """
        buffer = self._buffers.get(buffer_id)
        if not buffer:
            return False

        buffer.status = status
        await self._save_registry()

        return True

    def get_stats(self) -> BufferStats:
        """Get current buffer statistics."""
        # Recalculate stats
        stats = BufferStats()

        now = datetime.now(timezone.utc)
        oldest_age = 0

        for buffer in self._buffers.values():
            stats.total_buffers += 1
            stats.total_size_bytes += buffer.metadata.file_size_bytes

            age = (now - buffer.created_at).days
            if age > oldest_age:
                oldest_age = age

            if buffer.status == BufferStatus.PENDING_UPLOAD:
                stats.pending_upload += 1
            elif buffer.status == BufferStatus.UPLOADED:
                stats.uploaded += 1
                stats.railway_size_bytes += buffer.metadata.file_size_bytes
            elif buffer.status in [BufferStatus.DOWNLOADED, BufferStatus.TRANSCRIBING]:
                stats.downloaded += 1
                stats.railway_size_bytes += buffer.metadata.file_size_bytes
                if buffer.local_path:
                    stats.local_size_bytes += buffer.metadata.file_size_bytes
            elif buffer.status == BufferStatus.TRANSCRIBED:
                stats.transcribed += 1
                stats.railway_size_bytes += buffer.metadata.file_size_bytes
                if buffer.local_path:
                    stats.local_size_bytes += buffer.metadata.file_size_bytes
            elif buffer.status == BufferStatus.DELETED:
                stats.deleted += 1
            elif buffer.status == BufferStatus.ERROR:
                stats.errors += 1
            elif buffer.status == BufferStatus.EXPIRED:
                stats.expired += 1

        stats.oldest_buffer_age_days = oldest_age

        return stats

    async def cleanup_deleted(self) -> int:
        """Remove deleted buffers from registry.

        Returns:
            Number of entries removed
        """
        to_remove = [
            buffer_id
            for buffer_id, buffer in self._buffers.items()
            if buffer.status == BufferStatus.DELETED
        ]

        for buffer_id in to_remove:
            del self._buffers[buffer_id]

        if to_remove:
            await self._save_registry()

        return len(to_remove)

    async def get_pending_downloads(self) -> List[EphemeralBuffer]:
        """Get buffers ready for download.

        Returns:
            List of buffers in UPLOADED status
        """
        return await self.list_buffers(status=BufferStatus.UPLOADED)

    async def get_pending_transcription(self) -> List[EphemeralBuffer]:
        """Get buffers ready for transcription.

        Returns:
            List of buffers in DOWNLOADED status
        """
        return await self.list_buffers(status=BufferStatus.DOWNLOADED)

    async def get_pending_deletion(self) -> List[EphemeralBuffer]:
        """Get buffers ready for deletion.

        Returns:
            List of buffers in PENDING_DELETE or EXPIRED status
        """
        pending = await self.list_buffers(status=BufferStatus.PENDING_DELETE)
        expired = await self.list_buffers(
            status=BufferStatus.EXPIRED,
            include_expired=True
        )
        return pending + expired
