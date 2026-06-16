"""
Seed Archive Manager - Persistent memory archive for promoted memories.

SEED-001: Create seed_archive directory structure.

Directory Structure:
    ~/.claude/memory-mcp-data/seed_archive/
        YYYY-MM/
            week-NN.jsonl       # Weekly memory snapshots
        index.json              # Master index of all archives
        promoted/
            log.jsonl           # Promotion audit log

Purpose:
- Archive high-value memories that survive decay
- Support memory promotion from Triple-Layer to permanent storage
- Provide retrieval API for archived memories

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class ArchiveEntry:
    """A single archived memory entry."""

    id: str
    text: str
    metadata: Dict[str, Any]
    importance: float
    decay_score: float
    promoted_at: str
    source_tier: str  # short-term, mid-term, long-term
    promotion_reason: str


@dataclass
class PromotionLog:
    """Log entry for memory promotion."""

    memory_id: str
    promoted_at: str
    source_tier: str
    importance: float
    decay_score: float
    reason: str
    archive_path: str


class SeedArchive:
    """
    Manages the seed_archive for promoted memories.

    Provides:
    - Directory structure initialization
    - Weekly archive file management
    - Promotion logging
    - Index maintenance
    """

    def __init__(self, data_dir: str = None):
        """
        Initialize seed archive.

        Args:
            data_dir: Base data directory (default: ~/.claude/memory-mcp-data)

        NASA Rule 10: 20 LOC (<=60)
        """
        if data_dir is None:
            data_dir = Path.home() / ".claude" / "memory-mcp-data"
        else:
            data_dir = Path(data_dir)

        self.base_dir = data_dir / "seed_archive"
        self.promoted_dir = self.base_dir / "promoted"
        self.index_path = self.base_dir / "index.json"
        self.promotion_log_path = self.promoted_dir / "log.jsonl"

        # Initialize directory structure
        self._init_directories()

        logger.info(f"SeedArchive initialized at {self.base_dir}")

    def _init_directories(self) -> None:
        """
        Create directory structure if not exists.

        NASA Rule 10: 15 LOC (<=60)
        """
        # Create base and promoted directories
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.promoted_dir.mkdir(parents=True, exist_ok=True)

        # Create index file if not exists
        if not self.index_path.exists():
            self._write_index(
                {
                    "archives": [],
                    "total_entries": 0,
                    "created_at": datetime.utcnow().isoformat(),
                }
            )

        # Create promotion log if not exists
        if not self.promotion_log_path.exists():
            self.promotion_log_path.touch()

        logger.debug("Seed archive directories initialized")

    def _get_week_path(self, dt: datetime = None) -> Path:
        """
        Get archive file path for a given week.

        Args:
            dt: Datetime (default: now)

        Returns:
            Path to weekly archive file

        NASA Rule 10: 15 LOC (<=60)
        """
        if dt is None:
            dt = datetime.utcnow()

        year_month = dt.strftime("%Y-%m")
        week_num = (dt.day - 1) // 7 + 1

        month_dir = self.base_dir / year_month
        month_dir.mkdir(parents=True, exist_ok=True)

        return month_dir / f"week-{week_num:02d}.jsonl"

    def _read_index(self) -> Dict[str, Any]:
        """Read the master index."""
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return {"archives": [], "total_entries": 0}

    def _write_index(self, index: Dict[str, Any]) -> None:
        """Write the master index."""
        index["updated_at"] = datetime.utcnow().isoformat()
        self.index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    def promote_memory(
        self,
        memory_id: str,
        text: str,
        metadata: Dict[str, Any],
        importance: float,
        decay_score: float,
        source_tier: str,
        reason: str = "High importance",
    ) -> bool:
        """
        Promote a memory to the seed archive.

        Args:
            memory_id: Unique memory identifier
            text: Memory content
            metadata: Memory metadata
            importance: Importance score (0-1)
            decay_score: Decay score at promotion time
            source_tier: Source tier (short-term, mid-term, long-term)
            reason: Promotion reason

        Returns:
            True if promoted successfully

        NASA Rule 10: 45 LOC (<=60)
        """
        try:
            now = datetime.utcnow()

            # Create archive entry
            entry = ArchiveEntry(
                id=memory_id,
                text=text,
                metadata=metadata,
                importance=importance,
                decay_score=decay_score,
                promoted_at=now.isoformat(),
                source_tier=source_tier,
                promotion_reason=reason,
            )

            # Write to weekly archive
            archive_path = self._get_week_path(now)
            with open(archive_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry)) + "\n")

            # Log promotion
            self._log_promotion(
                memory_id=memory_id,
                source_tier=source_tier,
                importance=importance,
                decay_score=decay_score,
                reason=reason,
                archive_path=str(archive_path),
            )

            # Update index
            self._update_index(archive_path)

            logger.info(f"Promoted memory {memory_id} to {archive_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to promote memory {memory_id}: {e}")
            return False

    def _log_promotion(
        self,
        memory_id: str,
        source_tier: str,
        importance: float,
        decay_score: float,
        reason: str,
        archive_path: str,
    ) -> None:
        """
        Log a promotion event.

        NASA Rule 10: 20 LOC (<=60)
        """
        log_entry = PromotionLog(
            memory_id=memory_id,
            promoted_at=datetime.utcnow().isoformat(),
            source_tier=source_tier,
            importance=importance,
            decay_score=decay_score,
            reason=reason,
            archive_path=archive_path,
        )

        with open(self.promotion_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(log_entry)) + "\n")

    def _update_index(self, archive_path: Path) -> None:
        """
        Update the master index with archive info.

        NASA Rule 10: 25 LOC (<=60)
        """
        index = self._read_index()

        archive_str = str(archive_path.relative_to(self.base_dir))

        # Add archive if not already tracked
        if archive_str not in index["archives"]:
            index["archives"].append(archive_str)

        # Update count
        index["total_entries"] = index.get("total_entries", 0) + 1

        self._write_index(index)

    def get_archive_stats(self) -> Dict[str, Any]:
        """
        Get archive statistics.

        Returns:
            Dict with archive stats

        NASA Rule 10: 25 LOC (<=60)
        """
        index = self._read_index()

        # Count promotion log entries
        log_count = 0
        if self.promotion_log_path.exists():
            log_count = sum(1 for _ in open(self.promotion_log_path, encoding="utf-8"))

        return {
            "base_dir": str(self.base_dir),
            "archives_count": len(index.get("archives", [])),
            "total_entries": index.get("total_entries", 0),
            "promotion_log_entries": log_count,
            "created_at": index.get("created_at"),
            "updated_at": index.get("updated_at"),
        }

    def list_archives(self) -> List[str]:
        """
        List all archive files.

        Returns:
            List of archive paths relative to base_dir

        NASA Rule 10: 8 LOC (<=60)
        """
        index = self._read_index()
        return index.get("archives", [])

    def retrieve_from_archive(
        self, archive_path: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve entries from an archive file.

        Args:
            archive_path: Path relative to base_dir
            limit: Maximum entries to return

        Returns:
            List of archive entries

        NASA Rule 10: 25 LOC (<=60)
        """
        full_path = self.base_dir / archive_path
        if not full_path.exists():
            logger.warning(f"Archive not found: {archive_path}")
            return []

        entries = []
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                    entries.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to read archive {archive_path}: {e}")

        return entries

    def search_archives(
        self,
        query: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        SEED-004: Search archives by keyword, date range, and/or tags.

        Args:
            query: Optional keyword search query
            start_date: Optional start date (ISO format)
            end_date: Optional end date (ISO format)
            tags: Optional list of tags to filter by
            limit: Maximum results

        Returns:
            List of matching entries

        NASA Rule 10: 50 LOC (<=60)
        """
        results = []
        query_lower = query.lower() if query else None

        for archive_rel in self.list_archives():
            archive_path = self.base_dir / archive_rel
            if not archive_path.exists():
                continue

            try:
                with open(archive_path, "r", encoding="utf-8") as f:
                    for line in f:
                        entry = json.loads(line)

                        # SEED-004: Check date range
                        if start_date or end_date:
                            entry_date = entry.get("promoted_at", "")
                            if start_date and entry_date < start_date:
                                continue
                            if end_date and entry_date > end_date:
                                continue

                        # SEED-004: Check tags
                        if tags:
                            entry_tags = entry.get("metadata", {}).get("tags", [])
                            if not any(t in entry_tags for t in tags):
                                continue

                        # Check keyword
                        if query_lower:
                            if query_lower not in entry.get("text", "").lower():
                                continue

                        results.append(entry)
                        if len(results) >= limit:
                            return results

            except Exception as e:
                logger.warning(f"Error searching {archive_rel}: {e}")

        return results
