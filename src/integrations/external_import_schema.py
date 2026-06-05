"""External Import Schema for CAPTURE-002.

Defines data models for external import tagging automation.
Sources: Discord, Meta, Amazon, Google Takeout
Schema: WHO/WHEN/PROJECT/WHY auto-derived from source metadata

WHO: external-import:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-002)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
import hashlib
import uuid
import re
from pathlib import Path


class ImportSource(Enum):
    """Source platform for imported data."""

    DISCORD = "discord"
    META_FACEBOOK = "meta-facebook"
    META_INSTAGRAM = "meta-instagram"
    AMAZON = "amazon"
    GOOGLE_TAKEOUT = "google-takeout"
    TWITTER_X = "twitter-x"
    LINKEDIN = "linkedin"
    GITHUB = "github"
    SLACK = "slack"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    UNKNOWN = "unknown"


class ContentType(Enum):
    """Type of imported content."""

    MESSAGE = "message"
    POST = "post"
    COMMENT = "comment"
    REACTION = "reaction"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    ORDER = "order"
    SEARCH = "search"
    LOCATION = "location"
    ACTIVITY = "activity"
    CONTACT = "contact"
    CALENDAR = "calendar"
    EMAIL = "email"
    BOOKMARK = "bookmark"
    NOTE = "note"
    OTHER = "other"


class ImportStatus(Enum):
    """Status of an import job."""

    PENDING = "pending"
    SCANNING = "scanning"
    PROCESSING = "processing"
    TAGGING = "tagging"
    COMPLETE = "complete"
    FAILED = "failed"
    PARTIAL = "partial"


class TagConfidence(Enum):
    """Confidence level for auto-derived tags."""

    HIGH = "high"      # Explicit in source metadata
    MEDIUM = "medium"  # Inferred from context
    LOW = "low"        # Best guess


@dataclass
class WHOTag:
    """WHO tag: identifies the actor/author of content."""

    username: str
    display_name: Optional[str] = None
    platform_id: Optional[str] = None
    email: Optional[str] = None
    confidence: TagConfidence = TagConfidence.HIGH
    source_field: str = ""  # Which field this was derived from

    def to_canonical(self) -> str:
        """Return canonical WHO string."""
        if self.display_name:
            return f"{self.display_name} (@{self.username})"
        return f"@{self.username}"


@dataclass
class WHENTag:
    """WHEN tag: timestamp of content creation."""

    timestamp: datetime
    timezone_name: Optional[str] = None
    confidence: TagConfidence = TagConfidence.HIGH
    source_field: str = ""  # Which field this was derived from

    def to_canonical(self) -> str:
        """Return ISO8601 string."""
        return self.timestamp.isoformat()


@dataclass
class PROJECTTag:
    """PROJECT tag: categorization of content."""

    name: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    confidence: TagConfidence = TagConfidence.MEDIUM
    source_field: str = ""
    auto_derived: bool = True

    def to_canonical(self) -> str:
        """Return canonical PROJECT string."""
        parts = [self.name]
        if self.category:
            parts.append(self.category)
        if self.subcategory:
            parts.append(self.subcategory)
        return "/".join(parts)


@dataclass
class WHYTag:
    """WHY tag: purpose/intent classification."""

    intent: str  # communication, transaction, research, etc.
    action: Optional[str] = None  # sent, received, purchased, searched
    context: Optional[str] = None  # personal, work, hobby
    confidence: TagConfidence = TagConfidence.MEDIUM
    source_field: str = ""
    auto_derived: bool = True

    def to_canonical(self) -> str:
        """Return canonical WHY string."""
        parts = [self.intent]
        if self.action:
            parts.append(self.action)
        if self.context:
            parts.append(self.context)
        return ":".join(parts)


@dataclass
class DerivedTags:
    """Complete WHO/WHEN/PROJECT/WHY tag set."""

    who: WHOTag
    when: WHENTag
    project: PROJECTTag
    why: WHYTag

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "WHO": {
                "canonical": self.who.to_canonical(),
                "username": self.who.username,
                "display_name": self.who.display_name,
                "platform_id": self.who.platform_id,
                "confidence": self.who.confidence.value,
            },
            "WHEN": {
                "canonical": self.when.to_canonical(),
                "timestamp": self.when.timestamp.isoformat(),
                "timezone": self.when.timezone_name,
                "confidence": self.when.confidence.value,
            },
            "PROJECT": {
                "canonical": self.project.to_canonical(),
                "name": self.project.name,
                "category": self.project.category,
                "subcategory": self.project.subcategory,
                "confidence": self.project.confidence.value,
            },
            "WHY": {
                "canonical": self.why.to_canonical(),
                "intent": self.why.intent,
                "action": self.why.action,
                "context": self.why.context,
                "confidence": self.why.confidence.value,
            },
        }


@dataclass
class ImportedItem:
    """A single imported item from an external source."""

    item_id: str
    source: ImportSource
    content_type: ContentType
    tags: DerivedTags

    # Raw content
    raw_content: str = ""
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    # File references
    source_file: str = ""
    attachments: List[str] = field(default_factory=list)

    # Processing metadata
    imported_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str = ""
    word_count: int = 0

    # Additional tags
    labels: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        source: ImportSource,
        content_type: ContentType,
        tags: DerivedTags,
        raw_content: str = "",
        raw_metadata: Optional[Dict[str, Any]] = None,
    ) -> "ImportedItem":
        """Create a new imported item."""
        item_id = str(uuid.uuid4())
        content_hash = hashlib.sha256(raw_content.encode()).hexdigest()[:16]
        word_count = len(raw_content.split()) if raw_content else 0

        return cls(
            item_id=item_id,
            source=source,
            content_type=content_type,
            tags=tags,
            raw_content=raw_content,
            raw_metadata=raw_metadata or {},
            content_hash=content_hash,
            word_count=word_count,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "item_id": self.item_id,
            "source": self.source.value,
            "content_type": self.content_type.value,
            "tags": self.tags.to_dict(),
            "raw_content": self.raw_content[:1000] if self.raw_content else "",
            "raw_metadata": self.raw_metadata,
            "source_file": self.source_file,
            "attachments": self.attachments,
            "imported_at": self.imported_at.isoformat(),
            "content_hash": self.content_hash,
            "word_count": self.word_count,
            "labels": self.labels,
            "mentions": self.mentions,
            "links": self.links,
        }


@dataclass
class ImportJob:
    """An import job for processing external data."""

    job_id: str
    source: ImportSource
    status: ImportStatus
    source_path: str

    # Progress tracking
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0

    # Results
    items: List[ImportedItem] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Error tracking
    errors: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(cls, source: ImportSource, source_path: str) -> "ImportJob":
        """Create a new import job."""
        return cls(
            job_id=str(uuid.uuid4()),
            source=source,
            status=ImportStatus.PENDING,
            source_path=source_path,
        )

    def start(self) -> None:
        """Mark job as started."""
        self.status = ImportStatus.SCANNING
        self.started_at = datetime.now(timezone.utc)

    def complete(self) -> None:
        """Mark job as complete."""
        if self.failed_items > 0 and self.processed_items > 0:
            self.status = ImportStatus.PARTIAL
        elif self.failed_items > 0:
            self.status = ImportStatus.FAILED
        else:
            self.status = ImportStatus.COMPLETE
        self.completed_at = datetime.now(timezone.utc)

    def add_item(self, item: ImportedItem) -> None:
        """Add a processed item."""
        self.items.append(item)
        self.processed_items += 1

    def add_error(self, error: str, file_path: str = "") -> None:
        """Add an error."""
        self.errors.append({
            "error": error,
            "file_path": file_path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.failed_items += 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "job_id": self.job_id,
            "source": self.source.value,
            "status": self.status.value,
            "source_path": self.source_path,
            "progress": {
                "total_items": self.total_items,
                "processed_items": self.processed_items,
                "failed_items": self.failed_items,
                "skipped_items": self.skipped_items,
                "percentage": (
                    round(self.processed_items / self.total_items * 100, 1)
                    if self.total_items > 0 else 0
                ),
            },
            "timestamps": {
                "created_at": self.created_at.isoformat(),
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            },
            "item_count": len(self.items),
            "error_count": len(self.errors),
        }


# Tag derivation rules for each source

DISCORD_PROJECT_MAPPING = {
    "direct-message": ("personal", "communication", "dm"),
    "server-message": ("community", "communication", "server"),
    "voice-channel": ("community", "communication", "voice"),
}

META_PROJECT_MAPPING = {
    "post": ("social", "sharing", "post"),
    "story": ("social", "sharing", "story"),
    "message": ("personal", "communication", "message"),
    "comment": ("social", "engagement", "comment"),
    "reaction": ("social", "engagement", "reaction"),
}

AMAZON_PROJECT_MAPPING = {
    "order": ("shopping", "transaction", "purchase"),
    "review": ("shopping", "feedback", "review"),
    "wishlist": ("shopping", "planning", "wishlist"),
    "browse-history": ("shopping", "research", "browse"),
}

GOOGLE_PROJECT_MAPPING = {
    "search": ("research", "search", "web"),
    "youtube": ("media", "entertainment", "video"),
    "gmail": ("personal", "communication", "email"),
    "calendar": ("productivity", "planning", "calendar"),
    "drive": ("productivity", "storage", "files"),
    "photos": ("media", "memories", "photos"),
    "location": ("personal", "tracking", "location"),
    "chrome": ("research", "browsing", "history"),
}


def derive_project_tag(
    source: ImportSource,
    content_type: ContentType,
    metadata: Dict[str, Any],
) -> PROJECTTag:
    """Derive PROJECT tag from source and content type."""

    mapping = {
        ImportSource.DISCORD: DISCORD_PROJECT_MAPPING,
        ImportSource.META_FACEBOOK: META_PROJECT_MAPPING,
        ImportSource.META_INSTAGRAM: META_PROJECT_MAPPING,
        ImportSource.AMAZON: AMAZON_PROJECT_MAPPING,
        ImportSource.GOOGLE_TAKEOUT: GOOGLE_PROJECT_MAPPING,
    }

    source_mapping = mapping.get(source, {})

    # Try to match content type
    type_key = content_type.value.replace("_", "-")
    if type_key in source_mapping:
        name, category, subcategory = source_mapping[type_key]
        return PROJECTTag(
            name=name,
            category=category,
            subcategory=subcategory,
            confidence=TagConfidence.MEDIUM,
            source_field="content_type",
        )

    # Default based on source
    source_defaults = {
        ImportSource.DISCORD: ("discord", "communication", None),
        ImportSource.META_FACEBOOK: ("facebook", "social", None),
        ImportSource.META_INSTAGRAM: ("instagram", "social", None),
        ImportSource.AMAZON: ("amazon", "shopping", None),
        ImportSource.GOOGLE_TAKEOUT: ("google", "digital-life", None),
    }

    name, category, subcategory = source_defaults.get(
        source, ("external", "import", None)
    )

    return PROJECTTag(
        name=name,
        category=category,
        subcategory=subcategory,
        confidence=TagConfidence.LOW,
        source_field="source_default",
        auto_derived=True,
    )


def derive_why_tag(
    source: ImportSource,
    content_type: ContentType,
    metadata: Dict[str, Any],
) -> WHYTag:
    """Derive WHY tag from content type and context."""

    # Map content types to intents
    intent_mapping = {
        ContentType.MESSAGE: ("communication", "sent"),
        ContentType.POST: ("sharing", "posted"),
        ContentType.COMMENT: ("engagement", "commented"),
        ContentType.REACTION: ("engagement", "reacted"),
        ContentType.PHOTO: ("capture", "photographed"),
        ContentType.VIDEO: ("capture", "recorded"),
        ContentType.ORDER: ("transaction", "purchased"),
        ContentType.SEARCH: ("research", "searched"),
        ContentType.LOCATION: ("tracking", "visited"),
        ContentType.EMAIL: ("communication", "emailed"),
        ContentType.BOOKMARK: ("curation", "saved"),
    }

    if content_type in intent_mapping:
        intent, action = intent_mapping[content_type]
    else:
        intent, action = "activity", "performed"

    # Determine context from metadata or source
    context = "personal"  # Default
    if metadata.get("is_work") or metadata.get("channel_type") == "work":
        context = "work"
    elif metadata.get("is_group") or metadata.get("participants", 0) > 2:
        context = "group"

    return WHYTag(
        intent=intent,
        action=action,
        context=context,
        confidence=TagConfidence.MEDIUM,
        source_field="content_type",
        auto_derived=True,
    )


@dataclass
class ImportStats:
    """Statistics for import operations."""

    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0

    total_items: int = 0
    by_source: Dict[str, int] = field(default_factory=dict)
    by_content_type: Dict[str, int] = field(default_factory=dict)

    total_bytes_processed: int = 0
    avg_items_per_job: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "jobs": {
                "total": self.total_jobs,
                "completed": self.completed_jobs,
                "failed": self.failed_jobs,
            },
            "items": {
                "total": self.total_items,
                "by_source": self.by_source,
                "by_content_type": self.by_content_type,
            },
            "metrics": {
                "total_bytes_processed": self.total_bytes_processed,
                "avg_items_per_job": round(self.avg_items_per_job, 2),
            },
        }


# Helper functions for parsing common formats

def parse_iso_timestamp(ts_string: str) -> Optional[datetime]:
    """Parse ISO8601 timestamp string."""
    if not ts_string:
        return None

    # Handle various ISO formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(ts_string, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    return None


def parse_unix_timestamp(ts: Any) -> Optional[datetime]:
    """Parse Unix timestamp (seconds or milliseconds)."""
    if ts is None:
        return None

    try:
        ts_num = float(ts)
        # Detect milliseconds vs seconds
        if ts_num > 1e12:  # Likely milliseconds
            ts_num = ts_num / 1000
        return datetime.fromtimestamp(ts_num, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def extract_mentions(text: str) -> List[str]:
    """Extract @mentions from text."""
    if not text:
        return []
    return re.findall(r"@(\w+)", text)


def extract_links(text: str) -> List[str]:
    """Extract URLs from text."""
    if not text:
        return []
    url_pattern = r"https?://[^\s<>\"{}|\\^`\[\]]+"
    return re.findall(url_pattern, text)


def extract_hashtags(text: str) -> List[str]:
    """Extract #hashtags from text."""
    if not text:
        return []
    return re.findall(r"#(\w+)", text)


def compute_content_hash(content: str) -> str:
    """Compute hash for deduplication."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]
