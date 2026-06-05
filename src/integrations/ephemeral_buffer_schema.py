"""Ephemeral Buffer Schema for CAPTURE-001.

Defines data models for ephemeral buffer cleanup automation.
Flow: Railway temp buffer -> Home PC download -> Transcribe -> DELETE cloud copy

WHO: ephemeral-buffer:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-001)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
import hashlib
import uuid


class BufferStatus(Enum):
    """Status of an ephemeral buffer item."""

    PENDING_UPLOAD = "pending-upload"
    UPLOADED = "uploaded"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    PENDING_DELETE = "pending-delete"
    DELETED = "deleted"
    ERROR = "error"
    EXPIRED = "expired"


class BufferType(Enum):
    """Type of ephemeral buffer content."""

    AUDIO_RECORDING = "audio-recording"
    VIDEO_RECORDING = "video-recording"
    SCREEN_CAPTURE = "screen-capture"
    VOICE_MEMO = "voice-memo"
    MEETING_RECORDING = "meeting-recording"
    PODCAST_CAPTURE = "podcast-capture"
    OTHER = "other"


class DeleteReason(Enum):
    """Reason for buffer deletion."""

    DOWNLOADED_AND_TRANSCRIBED = "downloaded-and-transcribed"
    EXPIRED_ONE_WEEK = "expired-one-week"
    MANUAL_DELETE = "manual-delete"
    STORAGE_CLEANUP = "storage-cleanup"
    ERROR_CLEANUP = "error-cleanup"


class AuditAction(Enum):
    """Audit log action types."""

    CREATED = "created"
    UPLOADED = "uploaded"
    DOWNLOAD_STARTED = "download-started"
    DOWNLOAD_COMPLETED = "download-completed"
    TRANSCRIPTION_STARTED = "transcription-started"
    TRANSCRIPTION_COMPLETED = "transcription-completed"
    TRANSCRIPTION_VERIFIED = "transcription-verified"
    DELETION_SCHEDULED = "deletion-scheduled"
    DELETED = "deleted"
    ERROR = "error"
    STATUS_CHANGED = "status-changed"
    RETENTION_EXTENDED = "retention-extended"


@dataclass
class BufferMetadata:
    """Metadata for an ephemeral buffer item."""

    original_filename: str
    file_size_bytes: int
    duration_seconds: Optional[float] = None
    mime_type: str = "application/octet-stream"
    source_device: str = "unknown"
    source_application: str = "unknown"
    tags: List[str] = field(default_factory=list)
    custom_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TranscriptionResult:
    """Result of transcription verification."""

    transcript_id: str
    transcript_path: str
    word_count: int
    confidence_score: float
    language: str = "en"
    transcription_service: str = "whisper"
    verified_at: Optional[datetime] = None
    verification_method: str = "checksum"
    checksum: str = ""

    def is_verified(self) -> bool:
        """Check if transcription has been verified."""
        return self.verified_at is not None and self.confidence_score >= 0.8


@dataclass
class DeletionRule:
    """Rule for when to delete a buffer item."""

    rule_id: str
    name: str
    description: str
    max_age_days: int = 7
    require_download: bool = True
    require_transcription: bool = True
    require_verification: bool = True
    enabled: bool = True
    priority: int = 0

    def can_delete(
        self,
        buffer: "EphemeralBuffer",
        now: Optional[datetime] = None
    ) -> tuple[bool, Optional[DeleteReason]]:
        """Check if buffer can be deleted according to this rule.

        Returns:
            Tuple of (can_delete, reason)
        """
        if not self.enabled:
            return False, None

        now = now or datetime.now(timezone.utc)
        age_days = (now - buffer.created_at).days

        # Rule 1: Delete after max_age_days regardless of other conditions
        if age_days >= self.max_age_days:
            return True, DeleteReason.EXPIRED_ONE_WEEK

        # Rule 2: Delete if downloaded AND transcribed (if required)
        conditions_met = True

        if self.require_download and buffer.status not in [
            BufferStatus.DOWNLOADED,
            BufferStatus.TRANSCRIBING,
            BufferStatus.TRANSCRIBED,
            BufferStatus.PENDING_DELETE,
        ]:
            conditions_met = False

        if self.require_transcription and buffer.status != BufferStatus.TRANSCRIBED:
            conditions_met = False

        if self.require_verification and buffer.transcription:
            if not buffer.transcription.is_verified():
                conditions_met = False

        if conditions_met and buffer.downloaded_at is not None:
            return True, DeleteReason.DOWNLOADED_AND_TRANSCRIBED

        return False, None


@dataclass
class EphemeralBuffer:
    """An ephemeral buffer item in Railway temp storage."""

    buffer_id: str
    buffer_type: BufferType
    status: BufferStatus
    metadata: BufferMetadata

    # Storage locations
    railway_path: str
    railway_url: Optional[str] = None
    local_path: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uploaded_at: Optional[datetime] = None
    downloaded_at: Optional[datetime] = None
    transcribed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Checksums for verification
    railway_checksum: str = ""
    local_checksum: Optional[str] = None

    # Transcription
    transcription: Optional[TranscriptionResult] = None

    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    @classmethod
    def create(
        cls,
        railway_path: str,
        buffer_type: BufferType,
        metadata: BufferMetadata,
        expires_in_days: int = 7,
    ) -> "EphemeralBuffer":
        """Create a new ephemeral buffer item."""
        now = datetime.now(timezone.utc)
        buffer_id = str(uuid.uuid4())

        return cls(
            buffer_id=buffer_id,
            buffer_type=buffer_type,
            status=BufferStatus.PENDING_UPLOAD,
            metadata=metadata,
            railway_path=railway_path,
            created_at=now,
            expires_at=now + timedelta(days=expires_in_days),
        )

    def mark_uploaded(self, railway_url: str, checksum: str) -> None:
        """Mark buffer as uploaded to Railway."""
        self.status = BufferStatus.UPLOADED
        self.uploaded_at = datetime.now(timezone.utc)
        self.railway_url = railway_url
        self.railway_checksum = checksum

    def mark_downloading(self) -> None:
        """Mark buffer as being downloaded."""
        self.status = BufferStatus.DOWNLOADING

    def mark_downloaded(self, local_path: str, checksum: str) -> None:
        """Mark buffer as downloaded to local machine."""
        self.status = BufferStatus.DOWNLOADED
        self.downloaded_at = datetime.now(timezone.utc)
        self.local_path = local_path
        self.local_checksum = checksum

    def mark_transcribing(self) -> None:
        """Mark buffer as being transcribed."""
        self.status = BufferStatus.TRANSCRIBING

    def mark_transcribed(self, transcription: TranscriptionResult) -> None:
        """Mark buffer as transcribed."""
        self.status = BufferStatus.TRANSCRIBED
        self.transcribed_at = datetime.now(timezone.utc)
        self.transcription = transcription

    def mark_pending_delete(self) -> None:
        """Mark buffer for deletion."""
        self.status = BufferStatus.PENDING_DELETE

    def mark_deleted(self) -> None:
        """Mark buffer as deleted."""
        self.status = BufferStatus.DELETED
        self.deleted_at = datetime.now(timezone.utc)

    def mark_error(self, message: str) -> None:
        """Mark buffer with an error."""
        self.status = BufferStatus.ERROR
        self.error_message = message
        self.retry_count += 1

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """Check if buffer has expired."""
        now = now or datetime.now(timezone.utc)
        if self.expires_at is None:
            return False
        return now >= self.expires_at

    def can_retry(self) -> bool:
        """Check if buffer can be retried after error."""
        return self.retry_count < self.max_retries

    def verify_checksum(self) -> bool:
        """Verify that local checksum matches Railway checksum."""
        if self.local_checksum is None:
            return False
        return self.local_checksum == self.railway_checksum

    def to_dict(self) -> Dict[str, Any]:
        """Serialize buffer to dictionary."""
        return {
            "buffer_id": self.buffer_id,
            "buffer_type": self.buffer_type.value,
            "status": self.status.value,
            "metadata": {
                "original_filename": self.metadata.original_filename,
                "file_size_bytes": self.metadata.file_size_bytes,
                "duration_seconds": self.metadata.duration_seconds,
                "mime_type": self.metadata.mime_type,
                "source_device": self.metadata.source_device,
                "source_application": self.metadata.source_application,
                "tags": self.metadata.tags,
            },
            "railway_path": self.railway_path,
            "railway_url": self.railway_url,
            "local_path": self.local_path,
            "railway_checksum": self.railway_checksum,
            "local_checksum": self.local_checksum,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "downloaded_at": self.downloaded_at.isoformat() if self.downloaded_at else None,
            "transcribed_at": self.transcribed_at.isoformat() if self.transcribed_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired(),
            "transcription": {
                "transcript_id": self.transcription.transcript_id,
                "word_count": self.transcription.word_count,
                "confidence_score": self.transcription.confidence_score,
                "is_verified": self.transcription.is_verified(),
            } if self.transcription else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EphemeralBuffer":
        """Deserialize buffer from dictionary."""
        metadata = BufferMetadata(
            original_filename=data["metadata"]["original_filename"],
            file_size_bytes=data["metadata"]["file_size_bytes"],
            duration_seconds=data["metadata"].get("duration_seconds"),
            mime_type=data["metadata"].get("mime_type", "application/octet-stream"),
            source_device=data["metadata"].get("source_device", "unknown"),
            source_application=data["metadata"].get("source_application", "unknown"),
            tags=data["metadata"].get("tags", []),
        )

        transcription = None
        if data.get("transcription"):
            transcription = TranscriptionResult(
                transcript_id=data["transcription"]["transcript_id"],
                transcript_path="",
                word_count=data["transcription"]["word_count"],
                confidence_score=data["transcription"]["confidence_score"],
            )

        def parse_dt(s: Optional[str]) -> Optional[datetime]:
            if s is None:
                return None
            return datetime.fromisoformat(s)

        return cls(
            buffer_id=data["buffer_id"],
            buffer_type=BufferType(data["buffer_type"]),
            status=BufferStatus(data["status"]),
            metadata=metadata,
            railway_path=data["railway_path"],
            railway_url=data.get("railway_url"),
            local_path=data.get("local_path"),
            created_at=parse_dt(data.get("created_at")) or datetime.now(timezone.utc),
            uploaded_at=parse_dt(data.get("uploaded_at")),
            downloaded_at=parse_dt(data.get("downloaded_at")),
            transcribed_at=parse_dt(data.get("transcribed_at")),
            deleted_at=parse_dt(data.get("deleted_at")),
            expires_at=parse_dt(data.get("expires_at")),
            railway_checksum=data.get("railway_checksum", ""),
            local_checksum=data.get("local_checksum"),
            transcription=transcription,
            error_message=data.get("error_message"),
            retry_count=data.get("retry_count", 0),
        )


@dataclass
class AuditLogEntry:
    """Audit log entry for buffer operations."""

    entry_id: str
    buffer_id: str
    action: AuditAction
    timestamp: datetime
    actor: str
    details: Dict[str, Any] = field(default_factory=dict)
    previous_status: Optional[BufferStatus] = None
    new_status: Optional[BufferStatus] = None
    success: bool = True
    error_message: Optional[str] = None

    @classmethod
    def create(
        cls,
        buffer_id: str,
        action: AuditAction,
        actor: str,
        details: Optional[Dict[str, Any]] = None,
        previous_status: Optional[BufferStatus] = None,
        new_status: Optional[BufferStatus] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> "AuditLogEntry":
        """Create a new audit log entry."""
        return cls(
            entry_id=str(uuid.uuid4()),
            buffer_id=buffer_id,
            action=action,
            timestamp=datetime.now(timezone.utc),
            actor=actor,
            details=details or {},
            previous_status=previous_status,
            new_status=new_status,
            success=success,
            error_message=error_message,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "entry_id": self.entry_id,
            "buffer_id": self.buffer_id,
            "action": self.action.value,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "details": self.details,
            "previous_status": self.previous_status.value if self.previous_status else None,
            "new_status": self.new_status.value if self.new_status else None,
            "success": self.success,
            "error_message": self.error_message,
        }


@dataclass
class BufferStats:
    """Statistics for ephemeral buffer system."""

    total_buffers: int = 0
    pending_upload: int = 0
    uploaded: int = 0
    downloaded: int = 0
    transcribed: int = 0
    deleted: int = 0
    errors: int = 0
    expired: int = 0

    total_size_bytes: int = 0
    railway_size_bytes: int = 0
    local_size_bytes: int = 0

    oldest_buffer_age_days: int = 0
    avg_processing_time_hours: float = 0.0
    deletion_rate_per_day: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_buffers": self.total_buffers,
            "by_status": {
                "pending_upload": self.pending_upload,
                "uploaded": self.uploaded,
                "downloaded": self.downloaded,
                "transcribed": self.transcribed,
                "deleted": self.deleted,
                "errors": self.errors,
                "expired": self.expired,
            },
            "storage": {
                "total_size_bytes": self.total_size_bytes,
                "railway_size_bytes": self.railway_size_bytes,
                "local_size_bytes": self.local_size_bytes,
                "total_size_mb": round(self.total_size_bytes / (1024 * 1024), 2),
            },
            "metrics": {
                "oldest_buffer_age_days": self.oldest_buffer_age_days,
                "avg_processing_time_hours": round(self.avg_processing_time_hours, 2),
                "deletion_rate_per_day": round(self.deletion_rate_per_day, 2),
            },
        }


# Default deletion rules
DEFAULT_DELETION_RULES: List[DeletionRule] = [
    DeletionRule(
        rule_id="standard-cleanup",
        name="Standard Cleanup",
        description="Delete after download and transcription verified",
        max_age_days=7,
        require_download=True,
        require_transcription=True,
        require_verification=True,
        enabled=True,
        priority=10,
    ),
    DeletionRule(
        rule_id="expiration-cleanup",
        name="Expiration Cleanup",
        description="Delete after 7 days regardless of status",
        max_age_days=7,
        require_download=False,
        require_transcription=False,
        require_verification=False,
        enabled=True,
        priority=0,
    ),
    DeletionRule(
        rule_id="quick-cleanup",
        name="Quick Cleanup",
        description="Delete immediately after download (no transcription required)",
        max_age_days=30,
        require_download=True,
        require_transcription=False,
        require_verification=False,
        enabled=False,
        priority=5,
    ),
]


def compute_file_checksum(file_path: str) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_bytes_checksum(data: bytes) -> str:
    """Compute SHA-256 checksum of bytes."""
    return hashlib.sha256(data).hexdigest()
