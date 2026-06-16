"""Rule Deployment Service for IMPROVE-001.

Deploys approved rule changes with rollback capability.

WHO: improvement-pipeline:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (IMPROVE-001)
"""

import logging
import shutil
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.services.improvement.outcome_schema import (
    RuleProposal,
    RuleChange,
    ProposalStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class DeploymentResult:
    """Result of a deployment operation."""

    proposal_id: str
    success: bool
    deployed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Details
    changes_applied: int = 0
    changes_failed: int = 0
    error_message: str = ""

    # Backup info
    backup_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "success": self.success,
            "deployed_at": self.deployed_at,
            "changes_applied": self.changes_applied,
            "changes_failed": self.changes_failed,
            "error_message": self.error_message,
            "backup_path": self.backup_path,
        }


@dataclass
class RollbackResult:
    """Result of a rollback operation."""

    proposal_id: str
    success: bool
    rolled_back_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Details
    files_restored: int = 0
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "success": self.success,
            "rolled_back_at": self.rolled_back_at,
            "files_restored": self.files_restored,
            "error_message": self.error_message,
        }


@dataclass
class RuleDeploymentConfig:
    """Configuration for rule deployment."""

    backup_dir: str = ".backups/rule_deployments"
    dry_run: bool = True  # Default to dry run for safety
    verify_changes: bool = True
    max_rollback_age_days: int = 30


class RuleDeploymentService:
    """Service for deploying rule changes.

    Handles:
    - Pre-deployment backup
    - Rule file updates
    - Post-deployment verification
    - Rollback capability
    """

    def __init__(
        self,
        config: Optional[RuleDeploymentConfig] = None,
        base_path: Optional[str] = None,
    ):
        """Initialize rule deployment service.

        Args:
            config: Service configuration
            base_path: Base path for file operations
        """
        self.config = config or RuleDeploymentConfig()
        self.base_path = Path(base_path) if base_path else Path.cwd()

        # Deployment history
        self._deployments: Dict[str, DeploymentResult] = {}

        # Expected occurrence count after each remove, so _verify_change can
        # prove a single-occurrence remove actually happened (set by
        # _apply_change; absent -> verification cannot be proven post-hoc).
        self._expected_remove_counts: Dict[tuple, int] = {}
        self._rollbacks: Dict[str, RollbackResult] = {}

        # Statistics
        self._stats = {
            "deployments_attempted": 0,
            "deployments_succeeded": 0,
            "deployments_failed": 0,
            "rollbacks_executed": 0,
        }

    def deploy(
        self,
        proposal: RuleProposal,
        dry_run: Optional[bool] = None,
    ) -> DeploymentResult:
        """Deploy a rule proposal.

        Args:
            proposal: Approved proposal to deploy
            dry_run: Override config dry_run setting

        Returns:
            Deployment result
        """
        use_dry_run = dry_run if dry_run is not None else self.config.dry_run

        self._stats["deployments_attempted"] += 1

        # Verify proposal is approved
        if proposal.status != ProposalStatus.APPROVED:
            return DeploymentResult(
                proposal_id=proposal.proposal_id,
                success=False,
                error_message=f"Proposal not approved (status: {proposal.status.value})",
            )

        # Create backup
        backup_path = None
        if not use_dry_run:
            backup_path = self._create_backup(proposal)

        # Apply changes
        applied = 0
        failed = 0
        errors = []

        for change in proposal.changes:
            success, error = self._apply_change(change, use_dry_run)
            if success:
                applied += 1
            else:
                failed += 1
                errors.append(error)

        # Determine success
        success = failed == 0 and applied > 0

        if success:
            self._stats["deployments_succeeded"] += 1
            proposal.status = ProposalStatus.DEPLOYED
            proposal.deployed_at = datetime.now(timezone.utc).isoformat()
            logger.info(f"Deployed proposal {proposal.proposal_id} ({applied} changes)")
        else:
            self._stats["deployments_failed"] += 1
            # Rollback on failure
            if backup_path and not use_dry_run:
                self._restore_backup(proposal.proposal_id, backup_path)
            logger.error(f"Deployment failed for {proposal.proposal_id}: {errors}")

        result = DeploymentResult(
            proposal_id=proposal.proposal_id,
            success=success,
            changes_applied=applied,
            changes_failed=failed,
            error_message="; ".join(errors) if errors else "",
            backup_path=backup_path,
        )

        self._deployments[proposal.proposal_id] = result

        return result

    def rollback(self, proposal_id: str) -> RollbackResult:
        """Rollback a deployed proposal.

        Args:
            proposal_id: Proposal ID to rollback

        Returns:
            Rollback result
        """
        deployment = self._deployments.get(proposal_id)

        if not deployment:
            return RollbackResult(
                proposal_id=proposal_id,
                success=False,
                error_message="Deployment not found",
            )

        if not deployment.backup_path:
            return RollbackResult(
                proposal_id=proposal_id,
                success=False,
                error_message="No backup available for rollback",
            )

        # Restore from backup
        files_restored, error = self._restore_backup(
            proposal_id, deployment.backup_path
        )

        success = files_restored > 0 and not error

        if success:
            self._stats["rollbacks_executed"] += 1
            logger.info(f"Rolled back proposal {proposal_id} ({files_restored} files)")
        else:
            logger.error(f"Rollback failed for {proposal_id}: {error}")

        result = RollbackResult(
            proposal_id=proposal_id,
            success=success,
            files_restored=files_restored,
            error_message=error or "",
        )

        self._rollbacks[proposal_id] = result

        return result

    def verify_deployment(self, proposal: RuleProposal) -> Dict[str, Any]:
        """Verify a deployment was applied correctly.

        Args:
            proposal: Deployed proposal to verify

        Returns:
            Verification results
        """
        results = {
            "proposal_id": proposal.proposal_id,
            "verified": True,
            "checks": [],
        }

        for change in proposal.changes:
            check = self._verify_change(change)
            results["checks"].append(check)
            if not check.get("verified", False):
                results["verified"] = False

        return results

    def _create_backup(self, proposal: RuleProposal) -> Optional[str]:
        """Create backup before deployment.

        Args:
            proposal: Proposal being deployed

        Returns:
            Backup directory path or None
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = (
            self.base_path
            / self.config.backup_dir
            / f"{proposal.proposal_id}_{timestamp}"
        )

        try:
            backup_dir.mkdir(parents=True, exist_ok=True)

            for change in proposal.changes:
                src_path = self.base_path / change.rule_path
                if src_path.exists():
                    # Preserve directory structure
                    rel_path = Path(change.rule_path)
                    dst_path = backup_dir / rel_path
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dst_path)

            return str(backup_dir)

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None

    def _restore_backup(
        self,
        proposal_id: str,
        backup_path: str,
    ) -> tuple[int, Optional[str]]:
        """Restore files from backup.

        Args:
            proposal_id: Proposal ID
            backup_path: Path to backup directory

        Returns:
            Tuple of (files_restored, error_message)
        """
        backup_dir = Path(backup_path)

        if not backup_dir.exists():
            return 0, "Backup directory not found"

        restored = 0

        try:
            for backup_file in backup_dir.rglob("*"):
                if backup_file.is_file():
                    rel_path = backup_file.relative_to(backup_dir)
                    dst_path = self.base_path / rel_path

                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, dst_path)
                    restored += 1

            return restored, None

        except Exception as e:
            return restored, str(e)

    def _apply_change(
        self,
        change: RuleChange,
        dry_run: bool = True,
    ) -> tuple[bool, str]:
        """Apply a single rule change.

        Args:
            change: Change to apply
            dry_run: Whether this is a dry run

        Returns:
            Tuple of (success, error_message)
        """
        file_path = self.base_path / change.rule_path

        if dry_run:
            # Dry run - just validate
            if change.change_type == "add":
                # Check parent directory exists
                if not file_path.parent.exists():
                    return False, f"Parent directory does not exist: {file_path.parent}"
                return True, ""

            elif change.change_type in ("modify", "remove"):
                # Check file exists
                if not file_path.exists():
                    return False, f"File does not exist: {file_path}"

                # Both target current_value; it must be present or the op
                # no-ops. H4: remove used to validate only file existence here.
                # remove also requires non-empty (empty-modify is a separate
                # pre-existing issue, left as-is to match the real modify path).
                if change.change_type == "remove" and not change.current_value:
                    return False, "remove requires a non-empty current_value"
                content = file_path.read_text(encoding="utf-8")
                if change.current_value not in content:
                    return False, f"Current value not found in {file_path}"

                return True, ""

            return False, f"Unknown change type: {change.change_type}"

        # Actual deployment
        try:
            if change.change_type == "add":
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Append or create
                if file_path.exists():
                    content = file_path.read_text(encoding="utf-8")
                    content += "\n\n" + change.proposed_value
                else:
                    content = change.proposed_value

                file_path.write_text(content, encoding="utf-8")

            elif change.change_type == "modify":
                content = file_path.read_text(encoding="utf-8")

                if change.current_value not in content:
                    return False, f"Current value not found in {file_path}"

                content = content.replace(change.current_value, change.proposed_value)
                file_path.write_text(content, encoding="utf-8")

            elif change.change_type == "remove":
                content = file_path.read_text(encoding="utf-8")

                # H4: guard the remove like modify does. An empty or absent
                # current_value would no-op (silent false success); replacing
                # all occurrences would strip the value file-wide.
                if not change.current_value:
                    return False, "Remove requires a non-empty current_value"
                if change.current_value not in content:
                    return False, f"Current value not found in {file_path}"

                # Remove a single occurrence, not every match.
                content = content.replace(change.current_value, "", 1)
                file_path.write_text(content, encoding="utf-8")
                self._expected_remove_counts[
                    (change.rule_path, change.current_value)
                ] = content.count(change.current_value)

            return True, ""

        except Exception as e:
            return False, str(e)

    def _verify_change(self, change: RuleChange) -> Dict[str, Any]:
        """Verify a change was applied.

        Args:
            change: Change to verify

        Returns:
            Verification result
        """
        file_path = self.base_path / change.rule_path

        result = {
            "rule_path": change.rule_path,
            "change_type": change.change_type,
            "verified": False,
            "reason": "",
        }

        if not file_path.exists():
            if change.change_type == "remove":
                result["verified"] = True
            else:
                result["reason"] = "File does not exist"
            return result

        try:
            content = file_path.read_text(encoding="utf-8")

            if change.change_type in ("add", "modify"):
                if change.proposed_value in content:
                    result["verified"] = True
                else:
                    result["reason"] = "Proposed value not found in file"

            elif change.change_type == "remove":
                # remove deletes ONE occurrence (H4), so a remaining match is
                # not a failure. Verify against the count _apply_change recorded
                # right after removing; without that record (e.g. verify called
                # standalone) a single-occurrence remove can't be proven post-hoc.
                key = (change.rule_path, change.current_value)
                if key in self._expected_remove_counts:
                    expected = self._expected_remove_counts[key]
                    if content.count(change.current_value) == expected:
                        result["verified"] = True
                    else:
                        result["reason"] = "Remove count does not match expected"
                else:
                    result["reason"] = "No recorded remove to verify"

        except Exception as e:
            result["reason"] = str(e)

        return result

    def get_deployment_history(
        self,
        limit: int = 50,
    ) -> List[DeploymentResult]:
        """Get deployment history.

        Args:
            limit: Maximum results

        Returns:
            List of deployment results
        """
        results = list(self._deployments.values())
        results.sort(key=lambda r: r.deployed_at, reverse=True)
        return results[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get deployment statistics."""
        return {
            **self._stats,
            "total_deployments": len(self._deployments),
            "total_rollbacks": len(self._rollbacks),
            "success_rate": round(
                self._stats["deployments_succeeded"]
                / max(1, self._stats["deployments_attempted"]),
                4,
            ),
        }
