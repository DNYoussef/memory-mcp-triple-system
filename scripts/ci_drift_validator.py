#!/usr/bin/env python3
"""CI Drift Validator - Detect ownership violations in CI pipeline.

Usage:
    python scripts/ci_drift_validator.py --manifest manifest.json --scan-paths path1 path2
    python scripts/ci_drift_validator.py --check  # Quick check of registered components
    python scripts/ci_drift_validator.py --fix --auto  # Auto-fix violations

Exit codes:
    0: No violations found
    1: Violations found (fails CI)
    2: Critical violations found (blocks merge)

WHO: ownership-registry:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (GRAPH-002)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.ownership_registry import OwnershipRegistry
from src.integrations.ontology_schema import OwnershipViolationType


def main():
    parser = argparse.ArgumentParser(
        description="CI Drift Validator - Detect ownership violations"
    )
    parser.add_argument(
        "--manifest",
        type=str,
        help="Path to component manifest JSON",
    )
    parser.add_argument(
        "--scan-paths",
        nargs="*",
        default=[],
        help="Paths to scan for duplicates",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data",
        help="Data directory for registry",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Quick check of registered components only",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to fix violations",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-fix without confirmation (use with --fix)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without changing files",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output violations to JSON file",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Fail CI on any violation (not just critical)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("CI DRIFT VALIDATOR")
    print(f"Time: {datetime.utcnow().isoformat()}")
    print("=" * 60)

    # Initialize registry
    registry = OwnershipRegistry(data_dir=args.data_dir)

    # Load manifest if provided
    if args.manifest:
        print(f"\nLoading manifest: {args.manifest}")
        imported = registry.import_manifest(args.manifest)
        print(f"Imported {imported} components from manifest")
    else:
        print("\nLoading existing registry...")
        registry.initialize()

    component_count = len(registry.list_components())
    print(f"Registered components: {component_count}")

    if component_count == 0:
        print("\n[WARNING] No components registered. Nothing to check.")
        print("Use --manifest to import a component manifest.")
        return 0

    # Detect drift
    print("\nRunning drift detection...")
    violations = registry.detect_drift(scan_paths=args.scan_paths if args.scan_paths else None)

    # Categorize violations
    critical = []
    high = []
    medium = []
    low = []

    for v in violations:
        if v.severity == "critical":
            critical.append(v)
        elif v.severity == "high":
            high.append(v)
        elif v.severity == "medium":
            medium.append(v)
        else:
            low.append(v)

    # Report
    print("\n" + "=" * 60)
    print("DRIFT DETECTION RESULTS")
    print("=" * 60)
    print(f"Total violations:    {len(violations)}")
    print(f"  Critical:          {len(critical)}")
    print(f"  High:              {len(high)}")
    print(f"  Medium:            {len(medium)}")
    print(f"  Low:               {len(low)}")

    if violations:
        print("\n" + "-" * 60)
        print("VIOLATIONS DETAIL")
        print("-" * 60)

        for v in violations:
            severity_icon = {
                "critical": "[CRITICAL]",
                "high": "[HIGH]",
                "medium": "[MEDIUM]",
                "low": "[LOW]",
            }.get(v.severity, "[?]")

            print(f"\n{severity_icon} {v.violation_type.value}")
            print(f"  Component:  {v.component_id}")
            print(f"  Canonical:  {v.canonical_path}")
            print(f"  Violating:  {v.violating_path}")
            print(f"  Fix Action: {v.fix_action}")
            print(f"  Auto-Fix:   {'Yes' if v.auto_fixable else 'No'}")

    # Output to file if requested
    if args.output:
        output_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_violations": len(violations),
            "by_severity": {
                "critical": len(critical),
                "high": len(high),
                "medium": len(medium),
                "low": len(low),
            },
            "violations": [
                {
                    "id": v.id,
                    "component_id": v.component_id,
                    "violation_type": v.violation_type.value,
                    "severity": v.severity,
                    "canonical_path": v.canonical_path,
                    "violating_path": v.violating_path,
                    "fix_action": v.fix_action,
                    "auto_fixable": v.auto_fixable,
                }
                for v in violations
            ],
        }
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nViolations written to: {args.output}")

    # Fix violations if requested
    if args.fix and violations:
        print("\n" + "-" * 60)
        print("FIXING VIOLATIONS")
        print("-" * 60)

        results = registry.fix_violations(
            violations,
            auto_fix=args.auto,
            dry_run=args.dry_run,
        )

        print(f"Fixed:   {len(results['fixed'])}")
        print(f"Skipped: {len(results['skipped'])}")
        print(f"Failed:  {len(results['failed'])}")

        if args.dry_run:
            print("\n[DRY RUN] No files were modified")

        # Save registry after fixes
        if not args.dry_run:
            registry.save()

    # Determine exit code
    print("\n" + "=" * 60)
    if critical:
        print("[FAIL] Critical violations found - blocking merge")
        return 2
    elif args.fail_on_warning and violations:
        print("[FAIL] Violations found (--fail-on-warning enabled)")
        return 1
    elif high:
        print("[WARN] High severity violations found")
        return 1 if args.fail_on_warning else 0
    elif violations:
        print("[WARN] Violations found but not blocking")
        return 0
    else:
        print("[PASS] No drift violations detected")
        return 0


if __name__ == "__main__":
    sys.exit(main())
