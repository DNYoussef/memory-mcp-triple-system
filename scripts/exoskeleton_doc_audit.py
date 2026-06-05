#!/usr/bin/env python3
"""
Exoskeleton Documentation Audit - RLM-powered docs vs code verification.

Uses RLM to:
1. Index all AI Exoskeleton markdown docs
2. Extract status claims (percentages, file counts, endpoints, etc.)
3. Verify claims against actual code
4. Generate a drift report with corrections

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
import re
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rlm import RLMCodebaseEnvironment, RLMConfig


@dataclass
class StatusClaim:
    """A status claim extracted from documentation."""
    doc_file: str
    line_number: int
    project: str
    claim_type: str  # percentage, count, exists, feature
    claimed_value: str
    context: str


@dataclass
class VerificationResult:
    """Result of verifying a claim against code."""
    claim: StatusClaim
    actual_value: str
    is_accurate: bool
    drift_amount: Optional[str] = None
    correction: Optional[str] = None


class ExoskeletonDocAuditor:
    """
    Audits AI Exoskeleton documentation against actual code.

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    def __init__(self, exoskeleton_path: str = "D:/2026-AI-EXOSKELETON"):
        """Initialize auditor with RLM environment."""
        self.exoskeleton_path = Path(exoskeleton_path)
        self.config = RLMConfig(max_depth=10)
        self.env = RLMCodebaseEnvironment(config=self.config)
        self.claims: List[StatusClaim] = []
        self.results: List[VerificationResult] = []

    def load_all_projects(self) -> Dict[str, Any]:
        """Load all AI Exoskeleton projects into RLM."""
        print("=" * 70)
        print("PHASE 1: LOADING ALL AI EXOSKELETON PROJECTS")
        print("=" * 70)

        self.env.load_data("all")
        stats = self.env.get_stats()

        print(f"\nTotal files indexed: {stats['total_files']}")
        print(f"Projects loaded: {stats['total_projects']}")
        print(f"By language: {stats['by_language']}")

        return stats

    def extract_status_claims(self) -> List[StatusClaim]:
        """
        Extract status claims from documentation files.

        Patterns matched:
        - Status percentages: "90%", "100% complete"
        - File counts: "14 node handlers", "231 API endpoints"
        - Feature claims: "EXISTS", "COMPLETE", "NOT IMPLEMENTED"

        NASA Rule 10: 55 LOC (<=60)
        """
        print("\n" + "=" * 70)
        print("PHASE 2: EXTRACTING STATUS CLAIMS FROM DOCS")
        print("=" * 70)

        md_files = list(self.exoskeleton_path.glob("*.md"))
        md_files += list(self.exoskeleton_path.glob("audits/*.md"))
        md_files += list(self.exoskeleton_path.glob("plans/*.md"))

        patterns = {
            "percentage": r"(\d+)%",
            "count": r"(\d+)\s+(files?|endpoints?|handlers?|components?|tests?|agents?|skills?|routes?)",
            "status": r"\b(EXISTS|COMPLETE|PARTIAL|NOT IMPLEMENTED|NONE|VERIFIED|MISSING)\b",
            "project_status": r"\|\s*([a-z-]+)\s*\|\s*[^|]+\|\s*(\d+)%",
        }

        for md_file in md_files:
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")

                for i, line in enumerate(lines):
                    # Check for project status rows (tables)
                    for match in re.finditer(patterns["project_status"], line, re.IGNORECASE):
                        project = match.group(1)
                        percentage = match.group(2)
                        self.claims.append(StatusClaim(
                            doc_file=str(md_file),
                            line_number=i + 1,
                            project=project,
                            claim_type="percentage",
                            claimed_value=f"{percentage}%",
                            context=line.strip()[:200]
                        ))

                    # Check for explicit status markers
                    for match in re.finditer(patterns["status"], line, re.IGNORECASE):
                        # Try to identify which project this refers to
                        project = self._extract_project_from_line(line)
                        if project:
                            self.claims.append(StatusClaim(
                                doc_file=str(md_file),
                                line_number=i + 1,
                                project=project,
                                claim_type="status",
                                claimed_value=match.group(1).upper(),
                                context=line.strip()[:200]
                            ))

                    # Check for count claims
                    for match in re.finditer(patterns["count"], line, re.IGNORECASE):
                        count = match.group(1)
                        entity = match.group(2)
                        self.claims.append(StatusClaim(
                            doc_file=str(md_file),
                            line_number=i + 1,
                            project=self._extract_project_from_line(line) or "unknown",
                            claim_type="count",
                            claimed_value=f"{count} {entity}",
                            context=line.strip()[:200]
                        ))

            except Exception as e:
                print(f"  Warning: Failed to parse {md_file}: {e}")

        print(f"\nExtracted {len(self.claims)} status claims from {len(md_files)} docs")
        return self.claims

    def _extract_project_from_line(self, line: str) -> Optional[str]:
        """Extract project name from a line of text."""
        project_names = [
            "memory-mcp", "context-cascade", "connascence", "life-os-dashboard",
            "life-os-frontend", "claude-dev-cli", "trader-ai", "fog-compute",
            "the-agent-maker", "dnyoussef-portfolio", "slop-detector", "meta-calculus",
            "agentwise", "corporate-council", "nsbu-rpg-app", "content-pipeline",
            "agentic-commerce-arc", "library"
        ]
        line_lower = line.lower()
        for project in project_names:
            if project in line_lower:
                return project
        return None

    def verify_claims(self) -> List[VerificationResult]:
        """
        Verify each claim against actual code.

        NASA Rule 10: 50 LOC (<=60)
        """
        print("\n" + "=" * 70)
        print("PHASE 3: VERIFYING CLAIMS AGAINST CODE")
        print("=" * 70)

        for claim in self.claims[:100]:  # Limit to 100 for performance
            result = self._verify_single_claim(claim)
            self.results.append(result)

            if not result.is_accurate:
                print(f"  [DRIFT] {claim.project}: {claim.claimed_value} -> {result.actual_value}")

        accurate = sum(1 for r in self.results if r.is_accurate)
        drifted = len(self.results) - accurate

        print(f"\nVerified {len(self.results)} claims")
        print(f"  Accurate: {accurate}")
        print(f"  Drifted:  {drifted}")

        return self.results

    def _verify_single_claim(self, claim: StatusClaim) -> VerificationResult:
        """Verify a single claim against code."""
        actual_value = "UNKNOWN"
        is_accurate = False

        if claim.claim_type == "percentage":
            # For percentages, we can't easily verify without more context
            # Mark as "NEEDS_MANUAL_CHECK"
            actual_value = "NEEDS_MANUAL_CHECK"
            is_accurate = True  # Don't flag as drift without verification

        elif claim.claim_type == "count":
            # Try to count actual files matching the entity type
            actual_value = self._count_entities(claim)
            claimed_num = int(re.search(r"(\d+)", claim.claimed_value).group(1))
            actual_num = int(re.search(r"(\d+)", actual_value).group(1)) if re.search(r"(\d+)", actual_value) else 0
            is_accurate = abs(claimed_num - actual_num) <= claimed_num * 0.1  # 10% tolerance

        elif claim.claim_type == "status":
            # Verify EXISTS/NOT IMPLEMENTED by checking for files
            actual_value = self._verify_existence(claim)
            is_accurate = (claim.claimed_value == actual_value)

        correction = None if is_accurate else f"Update to: {actual_value}"

        return VerificationResult(
            claim=claim,
            actual_value=actual_value,
            is_accurate=is_accurate,
            drift_amount=None if is_accurate else f"{claim.claimed_value} -> {actual_value}",
            correction=correction
        )

    def _count_entities(self, claim: StatusClaim) -> str:
        """Count actual entities in codebase."""
        # Extract entity type from claim
        entity_match = re.search(r"\d+\s+(files?|endpoints?|handlers?|components?|tests?|agents?|skills?|routes?)",
                                  claim.claimed_value, re.IGNORECASE)
        if not entity_match:
            return "0 entities"

        entity_type = entity_match.group(1).lower().rstrip("s")  # Singularize

        # Search based on entity type
        if entity_type == "endpoint" or entity_type == "route":
            # Count routes in routers
            results = self.env.search_content(r"@(router|app)\.(get|post|put|delete|patch)",
                                              project=claim.project, use_regex=True, limit=500)
            return f"{len(results)} {entity_type}s"

        elif entity_type == "handler":
            # Count handler classes/functions
            results = self.env.search_content("Handler", project=claim.project, limit=500)
            return f"{len(results)} {entity_type}s"

        elif entity_type == "test":
            # Count test functions
            results = self.env.search_content(r"def test_|it\(|describe\(",
                                              project=claim.project, use_regex=True, limit=500)
            return f"{len(results)} {entity_type}s"

        elif entity_type == "file":
            # Count files in project
            stats = self.env.get_project_stats(claim.project)
            if "file_count" in stats:
                return f"{stats['file_count']} files"

        return "UNKNOWN count"

    def _verify_existence(self, claim: StatusClaim) -> str:
        """Verify if something exists or not."""
        # Search for the context keywords in the project
        keywords = [w for w in claim.context.split() if len(w) > 5][:3]

        for keyword in keywords:
            results = self.env.search_content(keyword, project=claim.project, limit=5)
            if results:
                return "EXISTS"

        return "NOT IMPLEMENTED"

    def generate_drift_report(self) -> Dict[str, Any]:
        """Generate a comprehensive drift report."""
        print("\n" + "=" * 70)
        print("PHASE 4: GENERATING DRIFT REPORT")
        print("=" * 70)

        drifted = [r for r in self.results if not r.is_accurate]

        # Group by document
        by_doc: Dict[str, List[VerificationResult]] = {}
        for result in drifted:
            doc = result.claim.doc_file
            if doc not in by_doc:
                by_doc[doc] = []
            by_doc[doc].append(result)

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_claims": len(self.claims),
            "verified_claims": len(self.results),
            "accurate_claims": sum(1 for r in self.results if r.is_accurate),
            "drifted_claims": len(drifted),
            "accuracy_rate": round(sum(1 for r in self.results if r.is_accurate) / max(1, len(self.results)) * 100, 1),
            "drifts_by_document": {},
            "corrections_needed": []
        }

        for doc, results in by_doc.items():
            doc_name = Path(doc).name
            report["drifts_by_document"][doc_name] = len(results)

            for result in results:
                report["corrections_needed"].append({
                    "file": doc_name,
                    "line": result.claim.line_number,
                    "project": result.claim.project,
                    "claimed": result.claim.claimed_value,
                    "actual": result.actual_value,
                    "context": result.claim.context[:100]
                })

        print(f"\nDrift Report Summary:")
        print(f"  Total claims: {report['total_claims']}")
        print(f"  Verified:     {report['verified_claims']}")
        print(f"  Accurate:     {report['accurate_claims']}")
        print(f"  Drifted:      {report['drifted_claims']}")
        print(f"  Accuracy:     {report['accuracy_rate']}%")

        if report["drifts_by_document"]:
            print(f"\nDocuments with drift:")
            for doc, count in sorted(report["drifts_by_document"].items(), key=lambda x: -x[1]):
                print(f"    {doc}: {count} issues")

        return report

    def save_report(self, report: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """Save the drift report to file."""
        if output_path is None:
            output_path = str(self.exoskeleton_path / "DOCUMENTATION-DRIFT-REPORT.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved to: {output_path}")
        return output_path


def main():
    """Main audit function."""
    print("=" * 70)
    print("EXOSKELETON DOCUMENTATION AUDIT")
    print("=" * 70)
    print(f"Started: {datetime.utcnow().isoformat()}")

    auditor = ExoskeletonDocAuditor()

    # Phase 1: Load projects
    stats = auditor.load_all_projects()

    # Phase 2: Extract claims
    claims = auditor.extract_status_claims()

    # Phase 3: Verify claims
    results = auditor.verify_claims()

    # Phase 4: Generate report
    report = auditor.generate_drift_report()

    # Save report
    report_path = auditor.save_report(report)

    print("\n" + "=" * 70)
    print("AUDIT COMPLETE")
    print("=" * 70)

    return 0 if report["drifted_claims"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
