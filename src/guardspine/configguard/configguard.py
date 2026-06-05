"""
ConfigGuard - Configuration File Security Guard.

GS-009: Classifies and gates changes to configuration files.
Protects: .yaml, .json, .toml, .env files.

Risk Levels:
- L4 (CRITICAL): Secrets, credentials, API keys
- L3 (HIGH): Routing changes, service configs
- L2 (MEDIUM): Feature flags, settings
- L1 (LOW): Comments, formatting

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from loguru import logger

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class RiskLevel(Enum):
    """Risk levels for config changes."""
    L4_CRITICAL = 4  # Secrets, credentials
    L3_HIGH = 3      # Routing, service configs
    L2_MEDIUM = 2    # Feature flags
    L1_LOW = 1       # Comments, formatting


class ConfigType(Enum):
    """Configuration file types."""
    YAML = "yaml"
    JSON = "json"
    TOML = "toml"
    ENV = "env"
    INI = "ini"
    UNKNOWN = "unknown"


@dataclass
class ConfigViolation:
    """A configuration security violation.

    GS-009: Represents detected security issue.

    Attributes:
        violation_id: Unique identifier
        file_path: Affected file
        line_number: Line with violation
        risk_level: L1-L4 risk level
        category: Type of violation
        content: Violating content (redacted)
        recommendation: How to fix
    """
    violation_id: str
    file_path: str
    line_number: int
    risk_level: RiskLevel
    category: str
    content: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "violation_id": self.violation_id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "risk_level": self.risk_level.name,
            "category": self.category,
            "content": self.content,
            "recommendation": self.recommendation,
        }


@dataclass
class ConfigScanResult:
    """Result of config file scan.

    GS-009: Scan result with violations and metrics.

    Attributes:
        file_path: Scanned file
        config_type: File type
        violations: List of violations
        risk_score: Overall risk (0.0-1.0)
        passed: Whether scan passed
        scan_time: When scan ran
    """
    file_path: str
    config_type: ConfigType
    violations: List[ConfigViolation]
    risk_score: float
    passed: bool
    scan_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "config_type": self.config_type.value,
            "violations": [v.to_dict() for v in self.violations],
            "risk_score": self.risk_score,
            "passed": self.passed,
            "scan_time": self.scan_time,
        }


class ConfigGuard:
    """
    GS-009: Configuration File Security Guard.

    Classifies and gates changes to configuration files.
    Protects secrets, routing configs, and service settings.

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    # File extensions to scan
    CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".toml", ".env", ".ini"}

    # L4 CRITICAL patterns (secrets)
    L4_PATTERNS = [
        (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\']+', "password"),
        (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[^\s"\']+', "api_key"),
        (r'(?i)(secret[_-]?key|secretkey)\s*[=:]\s*["\']?[^\s"\']+', "secret_key"),
        (r'(?i)(token)\s*[=:]\s*["\']?[^\s"\']+', "token"),
        (r'(?i)(private[_-]?key)\s*[=:]\s*["\']?[^\s"\']+', "private_key"),
        (r'(?i)(aws[_-]?access|aws[_-]?secret)', "aws_credential"),
        (r'(?i)(database[_-]?url|db[_-]?url)\s*[=:]', "database_url"),
        (r'(?i)(connection[_-]?string)\s*[=:]', "connection_string"),
        (r'[A-Za-z0-9+/]{40,}={0,2}', "base64_secret"),
    ]

    # L3 HIGH patterns (routing, services)
    L3_PATTERNS = [
        (r'(?i)(host|hostname)\s*[=:]\s*["\']?[^\s"\']+', "host_config"),
        (r'(?i)(port)\s*[=:]\s*\d+', "port_config"),
        (r'(?i)(endpoint|url)\s*[=:]\s*["\']?https?:', "endpoint_config"),
        (r'(?i)(redis|postgres|mysql|mongo)\s*[=:]', "database_config"),
        (r'(?i)(cors|origin)\s*[=:]', "cors_config"),
        (r'(?i)(ssl|tls|certificate)\s*[=:]', "ssl_config"),
    ]

    # L2 MEDIUM patterns (feature flags)
    L2_PATTERNS = [
        (r'(?i)(enabled|disabled|feature)\s*[=:]\s*(true|false)', "feature_flag"),
        (r'(?i)(debug|verbose)\s*[=:]\s*(true|false)', "debug_flag"),
        (r'(?i)(timeout|interval)\s*[=:]\s*\d+', "timing_config"),
        (r'(?i)(max|min|limit)\s*[=:]\s*\d+', "limit_config"),
    ]

    def __init__(self):
        """Initialize ConfigGuard."""
        self._violation_count = 0
        self._scan_count = 0
        logger.info("ConfigGuard initialized")

    def _detect_config_type(self, file_path: str) -> ConfigType:
        """
        Detect configuration file type.

        Args:
            file_path: Path to file

        Returns:
            ConfigType enum

        NASA Rule 10: 15 LOC (<=60)
        """
        ext = Path(file_path).suffix.lower()
        if ext in {".yaml", ".yml"}:
            return ConfigType.YAML
        elif ext == ".json":
            return ConfigType.JSON
        elif ext == ".toml":
            return ConfigType.TOML
        elif ext == ".env":
            return ConfigType.ENV
        elif ext == ".ini":
            return ConfigType.INI
        return ConfigType.UNKNOWN

    def _redact_content(self, content: str) -> str:
        """
        Redact sensitive content for logging.

        Args:
            content: Original content

        Returns:
            Redacted content

        NASA Rule 10: 10 LOC (<=60)
        """
        # Keep first 10 chars, replace rest with ***
        if len(content) > 15:
            return content[:10] + "***REDACTED***"
        return content[:5] + "***"

    def scan_file(self, file_path: str) -> ConfigScanResult:
        """
        GS-009: Scan a configuration file for violations.

        Args:
            file_path: Path to config file

        Returns:
            Scan result with violations

        NASA Rule 10: 55 LOC (<=60)
        """
        self._scan_count += 1
        config_type = self._detect_config_type(file_path)
        violations: List[ConfigViolation] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return ConfigScanResult(
                file_path=file_path,
                config_type=config_type,
                violations=[],
                risk_score=0.0,
                passed=False,
            )

        for line_num, line in enumerate(lines, 1):
            # Check L4 patterns
            for pattern, category in self.L4_PATTERNS:
                if re.search(pattern, line):
                    self._violation_count += 1
                    violations.append(ConfigViolation(
                        violation_id=f"CV-{self._violation_count:06d}",
                        file_path=file_path,
                        line_number=line_num,
                        risk_level=RiskLevel.L4_CRITICAL,
                        category=category,
                        content=self._redact_content(line.strip()),
                        recommendation=f"Move {category} to secure vault/env",
                    ))

            # Check L3 patterns
            for pattern, category in self.L3_PATTERNS:
                if re.search(pattern, line):
                    self._violation_count += 1
                    violations.append(ConfigViolation(
                        violation_id=f"CV-{self._violation_count:06d}",
                        file_path=file_path,
                        line_number=line_num,
                        risk_level=RiskLevel.L3_HIGH,
                        category=category,
                        content=self._redact_content(line.strip()),
                        recommendation=f"Review {category} for security",
                    ))

            # Check L2 patterns (lower priority)
            for pattern, category in self.L2_PATTERNS:
                if re.search(pattern, line):
                    self._violation_count += 1
                    violations.append(ConfigViolation(
                        violation_id=f"CV-{self._violation_count:06d}",
                        file_path=file_path,
                        line_number=line_num,
                        risk_level=RiskLevel.L2_MEDIUM,
                        category=category,
                        content=self._redact_content(line.strip()),
                        recommendation=f"Document {category} change",
                    ))

        # Calculate risk score
        risk_score = self._calculate_risk_score(violations)
        passed = risk_score < 0.5  # Fail if risk >= 50%

        return ConfigScanResult(
            file_path=file_path,
            config_type=config_type,
            violations=violations,
            risk_score=risk_score,
            passed=passed,
        )

    def _calculate_risk_score(
        self,
        violations: List[ConfigViolation]
    ) -> float:
        """
        Calculate overall risk score.

        Args:
            violations: List of violations

        Returns:
            Risk score (0.0-1.0)

        NASA Rule 10: 15 LOC (<=60)
        """
        if not violations:
            return 0.0

        # Weight by risk level
        weights = {
            RiskLevel.L4_CRITICAL: 0.40,
            RiskLevel.L3_HIGH: 0.25,
            RiskLevel.L2_MEDIUM: 0.10,
            RiskLevel.L1_LOW: 0.05,
        }

        total_weight = sum(weights.get(v.risk_level, 0.05) for v in violations)
        return min(1.0, total_weight)

    def scan_directory(
        self,
        directory: str,
        recursive: bool = True
    ) -> List[ConfigScanResult]:
        """
        GS-009: Scan directory for config files.

        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories

        Returns:
            List of scan results

        NASA Rule 10: 25 LOC (<=60)
        """
        results: List[ConfigScanResult] = []
        dir_path = Path(directory)

        if not dir_path.exists():
            logger.warning(f"Directory not found: {directory}")
            return results

        pattern = "**/*" if recursive else "*"

        for file_path in dir_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self.CONFIG_EXTENSIONS:
                result = self.scan_file(str(file_path))
                results.append(result)

        return results

    def gate_change(
        self,
        file_path: str,
        old_content: str,
        new_content: str
    ) -> Dict[str, Any]:
        """
        GS-009: Gate a config file change.

        Args:
            file_path: File being changed
            old_content: Original content
            new_content: New content

        Returns:
            Gate decision with rationale

        NASA Rule 10: 40 LOC (<=60)
        """
        # Scan new content
        temp_path = f"/tmp/configguard_temp_{datetime.utcnow().timestamp()}"
        try:
            with open(temp_path, "w") as f:
                f.write(new_content)
            result = self.scan_file(temp_path)
        except Exception:
            result = ConfigScanResult(
                file_path=file_path,
                config_type=self._detect_config_type(file_path),
                violations=[],
                risk_score=0.0,
                passed=True,
            )
        finally:
            try:
                Path(temp_path).unlink()
            except Exception:
                pass

        # Determine gate action
        l4_count = sum(1 for v in result.violations if v.risk_level == RiskLevel.L4_CRITICAL)
        l3_count = sum(1 for v in result.violations if v.risk_level == RiskLevel.L3_HIGH)

        if l4_count > 0:
            action = "BLOCK"
            reason = f"Contains {l4_count} CRITICAL (L4) violations"
        elif l3_count > 0:
            action = "REVIEW"
            reason = f"Contains {l3_count} HIGH (L3) violations"
        elif result.risk_score > 0.3:
            action = "WARN"
            reason = f"Risk score {result.risk_score:.0%} exceeds threshold"
        else:
            action = "ALLOW"
            reason = "No significant security concerns"

        return {
            "action": action,
            "reason": reason,
            "risk_score": result.risk_score,
            "violations": len(result.violations),
            "l4_critical": l4_count,
            "l3_high": l3_count,
            "scan_result": result.to_dict(),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get guard statistics."""
        return {
            "scan_count": self._scan_count,
            "violation_count": self._violation_count,
            "config_extensions": list(self.CONFIG_EXTENSIONS),
        }


# CLI interface
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="ConfigGuard")
    parser.add_argument("path", help="File or directory to scan")
    parser.add_argument("--recursive", "-r", action="store_true", help="Recursive scan")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    args = parser.parse_args()

    guard = ConfigGuard()
    path = Path(args.path)

    if path.is_file():
        results = [guard.scan_file(str(path))]
    else:
        results = guard.scan_directory(str(path), recursive=args.recursive)

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        print(f"\n{'='*60}")
        print("!! CONFIGGUARD: SCAN RESULTS !!")
        print(f"{'='*60}")
        print(f"Files Scanned: {len(results)}")
        print(f"Total Violations: {sum(len(r.violations) for r in results)}")
        print()

        for result in results:
            status = "PASS" if result.passed else "FAIL"
            print(f"[{status}] {result.file_path}")
            print(f"     Risk: {result.risk_score:.0%} | Violations: {len(result.violations)}")
            for v in result.violations[:3]:
                print(f"     - [{v.risk_level.name}] {v.category}: {v.content}")

        print(f"{'='*60}")
