"""MCP Tools for Ephemeral Buffer Capture System (CAPTURE-001).

Provides MCP tool interfaces for buffer management operations.

WHO: ephemeral-buffer:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-001)
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from src.integrations.ephemeral_buffer_schema import (
    BufferStatus,
    BufferType,
    BufferMetadata,
    DeletionRule,
    DeleteReason,
)
from src.services.capture.buffer_coordinator import (
    BufferCoordinator,
    get_buffer_coordinator,
)


class CaptureTools:
    """MCP tool implementations for ephemeral buffer capture system."""

    def __init__(
        self,
        coordinator: Optional[BufferCoordinator] = None,
    ):
        """Initialize capture tools.

        Args:
            coordinator: Buffer coordinator (uses global if not provided)
        """
        self._coordinator = coordinator

    @property
    def coordinator(self) -> BufferCoordinator:
        """Get coordinator instance."""
        if self._coordinator:
            return self._coordinator
        return get_buffer_coordinator()

    # Buffer Management Tools

    async def buffer_upload(
        self,
        file_path: str,
        buffer_type: str = "audio-recording",
        expires_in_days: int = 7,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Upload a file to ephemeral buffer storage.

        Args:
            file_path: Path to file to upload
            buffer_type: Type of content (audio-recording, video-recording, voice-memo, etc.)
            expires_in_days: Days until auto-expiration (default 7)
            tags: Optional tags for organization

        Returns:
            Upload result with buffer_id
        """
        try:
            # Parse buffer type
            try:
                btype = BufferType(buffer_type)
            except ValueError:
                btype = BufferType.OTHER

            # Create metadata with tags
            import os
            metadata = BufferMetadata(
                original_filename=os.path.basename(file_path),
                file_size_bytes=os.path.getsize(file_path),
                tags=tags or [],
            )

            buffer = await self.coordinator.upload_buffer(
                file_path,
                btype,
                metadata,
                expires_in_days,
            )

            return {
                "success": True,
                "buffer_id": buffer.buffer_id,
                "status": buffer.status.value,
                "railway_url": buffer.railway_url,
                "expires_at": buffer.expires_at.isoformat() if buffer.expires_at else None,
            }

        except FileNotFoundError:
            return {
                "success": False,
                "error": f"File not found: {file_path}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def buffer_upload_bytes(
        self,
        data_base64: str,
        filename: str,
        buffer_type: str = "audio-recording",
        expires_in_days: int = 7,
    ) -> Dict[str, Any]:
        """Upload bytes (base64 encoded) to ephemeral buffer storage.

        Args:
            data_base64: Base64 encoded file content
            filename: Filename for the buffer
            buffer_type: Type of content
            expires_in_days: Days until expiration

        Returns:
            Upload result with buffer_id
        """
        try:
            import base64
            data = base64.b64decode(data_base64)

            try:
                btype = BufferType(buffer_type)
            except ValueError:
                btype = BufferType.OTHER

            buffer = await self.coordinator.upload_bytes(
                data,
                filename,
                btype,
                expires_in_days=expires_in_days,
            )

            return {
                "success": True,
                "buffer_id": buffer.buffer_id,
                "status": buffer.status.value,
                "size_bytes": len(data),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def buffer_get(
        self,
        buffer_id: str,
    ) -> Dict[str, Any]:
        """Get buffer details by ID.

        Args:
            buffer_id: Buffer ID to retrieve

        Returns:
            Buffer details
        """
        try:
            buffer = await self.coordinator.get_buffer(buffer_id)
            if not buffer:
                return {
                    "success": False,
                    "error": "Buffer not found",
                }

            return {
                "success": True,
                "buffer": buffer.to_dict(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def buffer_list(
        self,
        status: Optional[str] = None,
        buffer_type: Optional[str] = None,
        include_expired: bool = False,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List buffers with optional filtering.

        Args:
            status: Filter by status (uploaded, downloaded, transcribed, etc.)
            buffer_type: Filter by type
            include_expired: Include expired buffers
            limit: Maximum results (default 50)

        Returns:
            List of buffers
        """
        try:
            # Parse filters
            status_filter = None
            if status:
                try:
                    status_filter = BufferStatus(status)
                except ValueError:
                    pass

            type_filter = None
            if buffer_type:
                try:
                    type_filter = BufferType(buffer_type)
                except ValueError:
                    pass

            buffers = await self.coordinator.list_buffers(
                status=status_filter,
                buffer_type=type_filter,
                include_expired=include_expired,
                limit=limit,
            )

            return {
                "success": True,
                "count": len(buffers),
                "buffers": [b.to_dict() for b in buffers],
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def buffer_download(
        self,
        buffer_id: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Download a buffer to local machine.

        Args:
            buffer_id: Buffer ID to download
            force: Force re-download if already downloaded

        Returns:
            Download result
        """
        try:
            result = await self.coordinator.download_buffer(buffer_id, force)
            if not result:
                return {
                    "success": False,
                    "error": "Download failed",
                }

            return {
                "success": result.success,
                "buffer_id": result.buffer_id,
                "local_path": result.local_path,
                "checksum_verified": result.checksum_verified,
                "download_time_seconds": result.download_time_seconds,
                "file_size_bytes": result.file_size_bytes,
                "error": result.error_message,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def buffer_transcribe(
        self,
        buffer_id: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Transcribe a buffer (audio/video).

        Args:
            buffer_id: Buffer ID to transcribe
            force: Force re-transcription

        Returns:
            Transcription result
        """
        try:
            result = await self.coordinator.transcribe_buffer(buffer_id, force)
            if not result:
                return {
                    "success": False,
                    "error": "Transcription failed",
                }

            return {
                "success": True,
                "transcript_id": result.transcript_id,
                "transcript_path": result.transcript_path,
                "word_count": result.word_count,
                "confidence_score": result.confidence_score,
                "language": result.language,
                "is_verified": result.is_verified(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def buffer_delete(
        self,
        buffer_id: str,
        reason: str = "manual-delete",
    ) -> Dict[str, Any]:
        """Delete a buffer.

        Args:
            buffer_id: Buffer ID to delete
            reason: Deletion reason

        Returns:
            Deletion result
        """
        try:
            try:
                delete_reason = DeleteReason(reason)
            except ValueError:
                delete_reason = DeleteReason.MANUAL_DELETE

            success = await self.coordinator.delete_buffer(buffer_id, delete_reason)

            return {
                "success": success,
                "buffer_id": buffer_id,
                "reason": delete_reason.value,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    # Sync and Cleanup Tools

    async def sync_downloads(self) -> Dict[str, Any]:
        """Sync all pending downloads from Railway to local.

        Returns:
            Sync progress
        """
        try:
            progress = await self.coordinator.sync_downloads()
            if not progress:
                return {
                    "success": False,
                    "error": "Sync failed",
                }

            return {
                "success": True,
                "total_pending": progress.total_pending,
                "downloaded": progress.downloaded,
                "failed": progress.failed,
                "skipped": progress.skipped,
                "is_complete": progress.is_complete(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def run_cleanup(
        self,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Run cleanup automation.

        Args:
            dry_run: If True, simulate without actual deletion (default True for safety)

        Returns:
            Cleanup result
        """
        try:
            result = await self.coordinator.run_cleanup(dry_run)
            if not result:
                return {
                    "success": False,
                    "error": "Cleanup failed",
                }

            return {
                "success": True,
                "run_id": result.run_id,
                "dry_run": result.dry_run,
                "buffers_checked": result.buffers_checked,
                "buffers_deleted": result.buffers_deleted,
                "buffers_skipped": result.buffers_skipped,
                "buffers_errored": result.buffers_errored,
                "bytes_freed": result.bytes_freed,
                "mb_freed": round(result.bytes_freed / (1024 * 1024), 2),
                "deletion_reasons": result.deletion_reasons,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    # Stats and Reporting Tools

    async def get_buffer_stats(self) -> Dict[str, Any]:
        """Get ephemeral buffer statistics.

        Returns:
            Buffer statistics
        """
        try:
            stats = self.coordinator.get_buffer_stats()
            if not stats:
                return {
                    "success": False,
                    "error": "Stats not available",
                }

            return {
                "success": True,
                "stats": stats.to_dict(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def get_coordinator_stats(self) -> Dict[str, Any]:
        """Get comprehensive coordinator statistics.

        Returns:
            Full coordinator stats
        """
        try:
            stats = self.coordinator.get_stats()
            return {
                "success": True,
                **stats,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def generate_audit_report(
        self,
        days_back: int = 7,
    ) -> Dict[str, Any]:
        """Generate audit report for recent period.

        Args:
            days_back: Number of days to include (default 7)

        Returns:
            Audit report
        """
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days_back)

            report = await self.coordinator.generate_audit_report(
                start_date,
                end_date,
            )

            if not report:
                return {
                    "success": False,
                    "error": "Report generation failed",
                }

            return {
                "success": True,
                "report": report.to_dict(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def export_audit_log(
        self,
        output_path: str,
        days_back: int = 30,
    ) -> Dict[str, Any]:
        """Export audit log for compliance.

        Args:
            output_path: Path for export file
            days_back: Days to include (default 30)

        Returns:
            Export result
        """
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days_back)

            path = await self.coordinator.export_audit_log(
                start_date,
                end_date,
                output_path,
            )

            if not path:
                return {
                    "success": False,
                    "error": "Export failed",
                }

            return {
                "success": True,
                "export_path": path,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    # Rule Management Tools

    async def list_deletion_rules(self) -> Dict[str, Any]:
        """List all deletion rules.

        Returns:
            List of rules
        """
        try:
            rules = self.coordinator.list_deletion_rules()

            return {
                "success": True,
                "count": len(rules),
                "rules": [
                    {
                        "rule_id": r.rule_id,
                        "name": r.name,
                        "description": r.description,
                        "enabled": r.enabled,
                        "max_age_days": r.max_age_days,
                        "require_download": r.require_download,
                        "require_transcription": r.require_transcription,
                        "priority": r.priority,
                    }
                    for r in rules
                ],
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def add_deletion_rule(
        self,
        rule_id: str,
        name: str,
        max_age_days: int = 7,
        require_download: bool = True,
        require_transcription: bool = True,
        priority: int = 5,
    ) -> Dict[str, Any]:
        """Add a custom deletion rule.

        Args:
            rule_id: Unique rule identifier
            name: Rule name
            max_age_days: Days before deletion
            require_download: Require download before deletion
            require_transcription: Require transcription before deletion
            priority: Rule priority (higher = checked first)

        Returns:
            Result
        """
        try:
            rule = DeletionRule(
                rule_id=rule_id,
                name=name,
                description=f"Custom rule: {name}",
                max_age_days=max_age_days,
                require_download=require_download,
                require_transcription=require_transcription,
                require_verification=require_transcription,
                enabled=True,
                priority=priority,
            )

            self.coordinator.add_deletion_rule(rule)

            return {
                "success": True,
                "rule_id": rule_id,
                "message": f"Rule '{name}' added successfully",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def remove_deletion_rule(
        self,
        rule_id: str,
    ) -> Dict[str, Any]:
        """Remove a deletion rule.

        Args:
            rule_id: Rule ID to remove

        Returns:
            Result
        """
        try:
            success = self.coordinator.remove_deletion_rule(rule_id)

            return {
                "success": success,
                "rule_id": rule_id,
                "message": "Rule removed" if success else "Rule not found",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


# Tool registration for MCP server
def get_capture_tools() -> List[Dict[str, Any]]:
    """Get tool definitions for MCP server registration.

    Returns:
        List of tool definitions
    """
    return [
        {
            "name": "capture_buffer_upload",
            "description": "Upload a file to ephemeral buffer storage (Railway temp)",
            "parameters": {
                "file_path": {"type": "string", "required": True},
                "buffer_type": {"type": "string", "default": "audio-recording"},
                "expires_in_days": {"type": "integer", "default": 7},
            },
        },
        {
            "name": "capture_buffer_list",
            "description": "List ephemeral buffers with optional filtering",
            "parameters": {
                "status": {"type": "string", "required": False},
                "buffer_type": {"type": "string", "required": False},
                "include_expired": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "default": 50},
            },
        },
        {
            "name": "capture_buffer_get",
            "description": "Get buffer details by ID",
            "parameters": {
                "buffer_id": {"type": "string", "required": True},
            },
        },
        {
            "name": "capture_buffer_download",
            "description": "Download a buffer from Railway to local machine",
            "parameters": {
                "buffer_id": {"type": "string", "required": True},
                "force": {"type": "boolean", "default": False},
            },
        },
        {
            "name": "capture_buffer_transcribe",
            "description": "Transcribe an audio/video buffer",
            "parameters": {
                "buffer_id": {"type": "string", "required": True},
                "force": {"type": "boolean", "default": False},
            },
        },
        {
            "name": "capture_buffer_delete",
            "description": "Delete a buffer from storage",
            "parameters": {
                "buffer_id": {"type": "string", "required": True},
                "reason": {"type": "string", "default": "manual-delete"},
            },
        },
        {
            "name": "capture_sync_downloads",
            "description": "Sync all pending downloads from Railway to local",
            "parameters": {},
        },
        {
            "name": "capture_run_cleanup",
            "description": "Run cleanup automation (dry_run=True by default for safety)",
            "parameters": {
                "dry_run": {"type": "boolean", "default": True},
            },
        },
        {
            "name": "capture_stats",
            "description": "Get ephemeral buffer statistics",
            "parameters": {},
        },
        {
            "name": "capture_audit_report",
            "description": "Generate audit report for recent period",
            "parameters": {
                "days_back": {"type": "integer", "default": 7},
            },
        },
        {
            "name": "capture_list_rules",
            "description": "List all deletion rules",
            "parameters": {},
        },
        {
            "name": "capture_add_rule",
            "description": "Add a custom deletion rule",
            "parameters": {
                "rule_id": {"type": "string", "required": True},
                "name": {"type": "string", "required": True},
                "max_age_days": {"type": "integer", "default": 7},
                "require_download": {"type": "boolean", "default": True},
                "require_transcription": {"type": "boolean", "default": True},
            },
        },
    ]
