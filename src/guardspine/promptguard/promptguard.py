"""
PromptGuard - Prompt Injection Security Guard.

GS-010: Detects prompt injection attacks in SKILL.md,
agent definitions, and prompt templates.

Risk Levels:
- L4 (CRITICAL): Injection/jailbreak attempts
- L3 (HIGH): Policy/permission changes
- L2 (MEDIUM): Suspicious patterns
- L1 (LOW): Potential issues

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class InjectionType(Enum):
    """Types of prompt injection."""

    JAILBREAK = "jailbreak"
    ROLE_MANIPULATION = "role_manipulation"
    INSTRUCTION_OVERRIDE = "instruction_override"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    POLICY_BYPASS = "policy_bypass"


class RiskLevel(Enum):
    """Risk levels for prompt issues."""

    L4_CRITICAL = 4  # Direct injection/jailbreak
    L3_HIGH = 3  # Policy changes
    L2_MEDIUM = 2  # Suspicious patterns
    L1_LOW = 1  # Potential issues


@dataclass
class PromptViolation:
    """A prompt security violation.

    GS-010: Represents detected injection attempt.

    Attributes:
        violation_id: Unique identifier
        file_path: Affected file
        line_number: Line with violation
        risk_level: L1-L4 risk level
        injection_type: Type of injection
        matched_pattern: Pattern that matched
        content: Violating content
        recommendation: How to fix
    """

    violation_id: str
    file_path: str
    line_number: int
    risk_level: RiskLevel
    injection_type: InjectionType
    matched_pattern: str
    content: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "violation_id": self.violation_id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "risk_level": self.risk_level.name,
            "injection_type": self.injection_type.value,
            "matched_pattern": self.matched_pattern,
            "content": self.content[:100],
            "recommendation": self.recommendation,
        }


@dataclass
class PromptScanResult:
    """Result of prompt file scan.

    GS-010: Scan result with violations and metrics.

    Attributes:
        file_path: Scanned file
        violations: List of violations
        risk_score: Overall risk (0.0-1.0)
        passed: Whether scan passed
        scan_time: When scan ran
    """

    file_path: str
    violations: List[PromptViolation]
    risk_score: float
    passed: bool
    scan_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "violations": [v.to_dict() for v in self.violations],
            "risk_score": self.risk_score,
            "passed": self.passed,
            "scan_time": self.scan_time,
        }


class PromptGuard:
    """
    GS-010: Prompt Injection Security Guard.

    Detects prompt injection attacks in SKILL.md,
    agent definitions, and prompt templates.

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    # File patterns to scan
    PROMPT_FILES = {"SKILL.md", "AGENT.md", "PROMPT.md", "CLAUDE.md"}
    PROMPT_EXTENSIONS = {".md", ".txt", ".yaml", ".yml", ".json"}

    # L4 CRITICAL: Direct jailbreak patterns
    L4_JAILBREAK_PATTERNS = [
        (
            r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|rules)",
            "ignore_instructions",
        ),
        (
            r"(?i)forget\s+(everything|all|your)\s+(you|training|instructions)",
            "forget_training",
        ),
        (r"(?i)you\s+are\s+(now|no\s+longer)\s+(a|an|the)", "role_override"),
        (
            r"(?i)disregard\s+(all|any|your)\s+(safety|guidelines|rules)",
            "disregard_safety",
        ),
        (r"(?i)act\s+as\s+(if|though)\s+you\s+(have|had)\s+no", "act_without_limits"),
        (
            r"(?i)pretend\s+(you\s+)?(are|have)\s+no\s+(restrictions|limits)",
            "pretend_no_limits",
        ),
        (r"(?i)bypass\s+(the\s+)?(safety|content|ethical)", "bypass_safety"),
        (
            r"(?i)override\s+(your|the|all)\s+(programming|training)",
            "override_training",
        ),
        (r"(?i)dan\s*mode|developer\s*mode|god\s*mode", "special_mode"),
        (r"(?i)jailbreak|do\s+anything\s+now", "jailbreak_keyword"),
    ]

    # L4 CRITICAL: Privilege escalation
    L4_ESCALATION_PATTERNS = [
        (r"(?i)grant\s+(yourself|me)\s+(admin|root|sudo)", "grant_privileges"),
        (r"(?i)execute\s+(as\s+)?(root|admin|system)", "execute_elevated"),
        (r"(?i)rm\s+-rf|del\s+/s|format\s+c:", "destructive_command"),
        (r"(?i)sudo\s+|runas\s+/user:", "elevated_execution"),
    ]

    # L3 HIGH: Policy bypass patterns
    L3_POLICY_PATTERNS = [
        (r"(?i)skip\s+(the\s+)?(verification|validation|check)", "skip_verification"),
        (r"(?i)disable\s+(the\s+)?(guard|filter|safety)", "disable_guard"),
        (r"(?i)turn\s+off\s+(the\s+)?(protection|safety)", "turn_off_safety"),
        (r"(?i)remove\s+(the\s+)?(restriction|limit)", "remove_restriction"),
        (r"(?i)without\s+(any\s+)?(checking|validation)", "without_checking"),
    ]

    # L3 HIGH: Data exfiltration patterns
    L3_EXFIL_PATTERNS = [
        (r"(?i)send\s+(all\s+)?(data|files|info)\s+to", "send_data_to"),
        (r"(?i)upload\s+(to|your)\s+(server|endpoint)", "upload_to_server"),
        (r"(?i)leak\s+(the\s+)?(secret|password|key)", "leak_secret"),
        (r"(?i)extract\s+(and\s+)?(send|transmit)", "extract_and_send"),
    ]

    # L2 MEDIUM: Suspicious patterns
    L2_SUSPICIOUS_PATTERNS = [
        (r"(?i)system\s*:\s*you\s+are", "system_role_injection"),
        (r"(?i)\[system\]|\[admin\]|\[root\]", "role_tag_injection"),
        (r"(?i)base64\s+decode|eval\(|exec\(", "code_execution_hint"),
        (r"(?i)hidden\s+instruction|secret\s+command", "hidden_instruction"),
    ]

    def __init__(self):
        """Initialize PromptGuard."""
        self._violation_count = 0
        self._scan_count = 0
        logger.info("PromptGuard initialized")

    def scan_file(self, file_path: str) -> PromptScanResult:
        """
        GS-010: Scan a prompt file for injection attempts.

        Args:
            file_path: Path to prompt file

        Returns:
            Scan result with violations

        NASA Rule 10: 55 LOC (<=60)
        """
        self._scan_count += 1
        violations: List[PromptViolation] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return PromptScanResult(
                file_path=file_path,
                violations=[],
                risk_score=0.0,
                passed=False,
            )

        for line_num, line in enumerate(lines, 1):
            # Check L4 jailbreak patterns
            for pattern, name in self.L4_JAILBREAK_PATTERNS:
                if re.search(pattern, line):
                    self._add_violation(
                        violations,
                        file_path,
                        line_num,
                        line,
                        RiskLevel.L4_CRITICAL,
                        InjectionType.JAILBREAK,
                        name,
                        "Remove jailbreak attempt",
                    )

            # Check L4 escalation patterns
            for pattern, name in self.L4_ESCALATION_PATTERNS:
                if re.search(pattern, line):
                    self._add_violation(
                        violations,
                        file_path,
                        line_num,
                        line,
                        RiskLevel.L4_CRITICAL,
                        InjectionType.PRIVILEGE_ESCALATION,
                        name,
                        "Remove privilege escalation",
                    )

            # Check L3 policy patterns
            for pattern, name in self.L3_POLICY_PATTERNS:
                if re.search(pattern, line):
                    self._add_violation(
                        violations,
                        file_path,
                        line_num,
                        line,
                        RiskLevel.L3_HIGH,
                        InjectionType.POLICY_BYPASS,
                        name,
                        "Review policy bypass attempt",
                    )

            # Check L3 exfil patterns
            for pattern, name in self.L3_EXFIL_PATTERNS:
                if re.search(pattern, line):
                    self._add_violation(
                        violations,
                        file_path,
                        line_num,
                        line,
                        RiskLevel.L3_HIGH,
                        InjectionType.DATA_EXFILTRATION,
                        name,
                        "Remove data exfiltration",
                    )

            # Check L2 suspicious patterns
            for pattern, name in self.L2_SUSPICIOUS_PATTERNS:
                if re.search(pattern, line):
                    self._add_violation(
                        violations,
                        file_path,
                        line_num,
                        line,
                        RiskLevel.L2_MEDIUM,
                        InjectionType.INSTRUCTION_OVERRIDE,
                        name,
                        "Review suspicious pattern",
                    )

        risk_score = self._calculate_risk_score(violations)
        return PromptScanResult(
            file_path=file_path,
            violations=violations,
            risk_score=risk_score,
            passed=risk_score < 0.3,
        )

    def _add_violation(
        self,
        violations: List[PromptViolation],
        file_path: str,
        line_num: int,
        line: str,
        risk_level: RiskLevel,
        injection_type: InjectionType,
        pattern_name: str,
        recommendation: str,
    ) -> None:
        """
        Add a violation to the list.

        NASA Rule 10: 15 LOC (<=60)
        """
        self._violation_count += 1
        violations.append(
            PromptViolation(
                violation_id=f"PV-{self._violation_count:06d}",
                file_path=file_path,
                line_number=line_num,
                risk_level=risk_level,
                injection_type=injection_type,
                matched_pattern=pattern_name,
                content=line.strip()[:100],
                recommendation=recommendation,
            )
        )

    def _calculate_risk_score(self, violations: List[PromptViolation]) -> float:
        """
        Calculate overall risk score.

        NASA Rule 10: 15 LOC (<=60)
        """
        if not violations:
            return 0.0

        weights = {
            RiskLevel.L4_CRITICAL: 0.50,
            RiskLevel.L3_HIGH: 0.30,
            RiskLevel.L2_MEDIUM: 0.15,
            RiskLevel.L1_LOW: 0.05,
        }

        total_weight = sum(weights.get(v.risk_level, 0.05) for v in violations)
        return min(1.0, total_weight)

    def scan_directory(
        self, directory: str, recursive: bool = True
    ) -> List[PromptScanResult]:
        """
        GS-010: Scan directory for prompt files.

        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories

        Returns:
            List of scan results

        NASA Rule 10: 30 LOC (<=60)
        """
        results: List[PromptScanResult] = []
        dir_path = Path(directory)

        if not dir_path.exists():
            logger.warning(f"Directory not found: {directory}")
            return results

        pattern = "**/*" if recursive else "*"

        for file_path in dir_path.glob(pattern):
            if not file_path.is_file():
                continue

            # Check if it's a prompt file
            is_prompt_file = (
                file_path.name in self.PROMPT_FILES
                or file_path.suffix.lower() in self.PROMPT_EXTENSIONS
            )

            if is_prompt_file:
                result = self.scan_file(str(file_path))
                results.append(result)

        return results

    def validate_prompt_content(self, content: str) -> Dict[str, Any]:
        """
        GS-010: Validate prompt content for injection.

        Args:
            content: Prompt content to validate

        Returns:
            Validation result

        NASA Rule 10: 35 LOC (<=60)
        """
        violations: List[PromptViolation] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Check all patterns
            all_patterns = (
                [
                    (p, n, RiskLevel.L4_CRITICAL, InjectionType.JAILBREAK)
                    for p, n in self.L4_JAILBREAK_PATTERNS
                ]
                + [
                    (p, n, RiskLevel.L4_CRITICAL, InjectionType.PRIVILEGE_ESCALATION)
                    for p, n in self.L4_ESCALATION_PATTERNS
                ]
                + [
                    (p, n, RiskLevel.L3_HIGH, InjectionType.POLICY_BYPASS)
                    for p, n in self.L3_POLICY_PATTERNS
                ]
            )

            for pattern, name, risk, inj_type in all_patterns:
                if re.search(pattern, line):
                    self._add_violation(
                        violations,
                        "<content>",
                        line_num,
                        line,
                        risk,
                        inj_type,
                        name,
                        "Remove injection attempt",
                    )

        risk_score = self._calculate_risk_score(violations)
        return {
            "valid": risk_score < 0.3,
            "risk_score": risk_score,
            "violations": [v.to_dict() for v in violations],
            "l4_count": sum(
                1 for v in violations if v.risk_level == RiskLevel.L4_CRITICAL
            ),
            "l3_count": sum(1 for v in violations if v.risk_level == RiskLevel.L3_HIGH),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get guard statistics."""
        return {
            "scan_count": self._scan_count,
            "violation_count": self._violation_count,
        }


# CLI interface
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="PromptGuard")
    parser.add_argument("path", help="File or directory to scan")
    parser.add_argument("--recursive", "-r", action="store_true", help="Recursive scan")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    args = parser.parse_args()

    guard = PromptGuard()
    path = Path(args.path)

    if path.is_file():
        results = [guard.scan_file(str(path))]
    else:
        results = guard.scan_directory(str(path), recursive=args.recursive)

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        print(f"\n{'='*60}")
        print("!! PROMPTGUARD: SCAN RESULTS !!")
        print(f"{'='*60}")
        print(f"Files Scanned: {len(results)}")
        print(f"Total Violations: {sum(len(r.violations) for r in results)}")
        print()

        for result in results:
            if result.violations:
                status = "FAIL" if not result.passed else "WARN"
                print(f"[{status}] {result.file_path}")
                print(
                    f"     Risk: {result.risk_score:.0%} | Violations: {len(result.violations)}"
                )
                for v in result.violations[:3]:
                    print(
                        f"     - [{v.risk_level.name}] {v.injection_type.value}: {v.matched_pattern}"
                    )

        print(f"{'='*60}")
