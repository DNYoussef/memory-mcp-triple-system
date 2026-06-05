#!/usr/bin/env python3
"""Generate dead code report from vulture and pyflakes output."""
import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def parse_vulture_line(line: str) -> dict | None:
    """Parse a vulture output line."""
    # Format: file.py:line: unused item 'name' (XX% confidence)
    match = re.match(r'^(.+?):(\d+): (.+?) \((\d+)% confidence\)$', line.strip())
    if match:
        filepath, line_num, description, confidence = match.groups()
        # Extract item type and name
        item_match = re.match(r"unused (\w+) '(\w+)'", description)
        if item_match:
            item_type, item_name = item_match.groups()
        else:
            item_type = "unknown"
            item_name = description
        return {
            "file": filepath.replace("\\", "/"),
            "line": int(line_num),
            "item_type": item_type,
            "item_name": item_name,
            "confidence": int(confidence),
            "description": description,
            "source": "vulture"
        }
    return None

def parse_pyflakes_line(line: str) -> dict | None:
    """Parse a pyflakes output line."""
    # Format: file.py:line:col: 'module' imported but unused
    # Or: file.py:line:col: local variable 'x' is assigned to but never used
    match = re.match(r"^(.+?):(\d+):(\d+): (.+)$", line.strip())
    if match:
        filepath, line_num, col, description = match.groups()
        # Determine item type
        if "imported but unused" in description:
            item_type = "import"
            name_match = re.search(r"'([^']+)'", description)
            item_name = name_match.group(1) if name_match else "unknown"
        elif "local variable" in description:
            item_type = "variable"
            name_match = re.search(r"'([^']+)'", description)
            item_name = name_match.group(1) if name_match else "unknown"
        elif "undefined name" in description:
            item_type = "undefined"
            name_match = re.search(r"'([^']+)'", description)
            item_name = name_match.group(1) if name_match else "unknown"
        else:
            item_type = "other"
            item_name = description
        return {
            "file": filepath.replace("\\", "/"),
            "line": int(line_num),
            "column": int(col),
            "item_type": item_type,
            "item_name": item_name,
            "description": description,
            "confidence": 100 if item_type == "import" else 90,
            "source": "pyflakes"
        }
    return None

def categorize_finding(finding: dict) -> str:
    """Categorize finding: definitely_unused, probably_unused, investigate."""
    confidence = finding.get("confidence", 0)
    item_type = finding.get("item_type", "")

    # Unused imports are always definitely unused
    if item_type == "import":
        return "definitely_unused"

    # 100% confidence = definitely unused
    if confidence >= 100:
        return "definitely_unused"

    # 80-99% = probably unused
    if confidence >= 80:
        return "probably_unused"

    # 60-79% = needs investigation
    return "investigate"

def main():
    audits_dir = Path(__file__).parent

    # Parse vulture output
    vulture_findings = []
    vulture_file = audits_dir / "vulture-raw.txt"
    if vulture_file.exists():
        for line in vulture_file.read_text().splitlines():
            finding = parse_vulture_line(line)
            if finding:
                finding["category"] = categorize_finding(finding)
                vulture_findings.append(finding)

    # Parse pyflakes output
    pyflakes_findings = []
    pyflakes_file = audits_dir / "pyflakes-raw.txt"
    if pyflakes_file.exists():
        for line in pyflakes_file.read_text().splitlines():
            finding = parse_pyflakes_line(line)
            if finding:
                finding["category"] = categorize_finding(finding)
                pyflakes_findings.append(finding)

    # Combine and dedupe
    all_findings = vulture_findings + pyflakes_findings

    # Group by category
    by_category = defaultdict(list)
    for f in all_findings:
        by_category[f["category"]].append(f)

    # Group by file
    by_file = defaultdict(list)
    for f in all_findings:
        by_file[f["file"]].append(f)

    # Group by item type
    by_type = defaultdict(list)
    for f in all_findings:
        by_type[f["item_type"]].append(f)

    # Summary stats
    report = {
        "generated_at": datetime.now().isoformat(),
        "project": "memory-mcp-triple-system",
        "summary": {
            "total_findings": len(all_findings),
            "by_category": {k: len(v) for k, v in by_category.items()},
            "by_type": {k: len(v) for k, v in by_type.items()},
            "files_affected": len(by_file),
            "vulture_findings": len(vulture_findings),
            "pyflakes_findings": len(pyflakes_findings)
        },
        "top_affected_files": sorted(
            [(f, len(findings)) for f, findings in by_file.items()],
            key=lambda x: -x[1]
        )[:20],
        "findings": {
            "definitely_unused": by_category["definitely_unused"],
            "probably_unused": by_category["probably_unused"],
            "investigate": by_category["investigate"]
        }
    }

    # Write report
    report_file = audits_dir / "dead-code-report.json"
    report_file.write_text(json.dumps(report, indent=2))
    print(f"Report saved to {report_file}")

    # Print summary
    print(f"\n=== DEAD CODE AUDIT SUMMARY ===")
    print(f"Total findings: {report['summary']['total_findings']}")
    print(f"\nBy category:")
    for cat, count in report['summary']['by_category'].items():
        print(f"  {cat}: {count}")
    print(f"\nBy type:")
    for t, count in sorted(report['summary']['by_type'].items(), key=lambda x: -x[1]):
        print(f"  {t}: {count}")
    print(f"\nTop affected files:")
    for f, count in report['top_affected_files'][:10]:
        print(f"  {count:3d} findings: {f}")

if __name__ == "__main__":
    main()
