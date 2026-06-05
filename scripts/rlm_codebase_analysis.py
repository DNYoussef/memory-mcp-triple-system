#!/usr/bin/env python3
"""
RLM Codebase Analysis - Dogfooding the RLM tools.

Uses RLM to analyze Memory MCP and Context Cascade codebases
to find inconsistencies and bugs.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rlm import (
    RLMCodebaseEnvironment,
    RLMMemoryEnvironment,
    RLMLogger,
    CostTracker,
    CostConfig,
    RLMConfig,
)
from src.rlm.tools import RLMSearchTools, SearchResult


def load_codebases():
    """Load Memory MCP and Context Cascade codebases."""
    print("=" * 70)
    print("PHASE 1: LOADING CODEBASES INTO RLM ENVIRONMENT")
    print("=" * 70)

    config = RLMConfig(max_depth=10)
    env = RLMCodebaseEnvironment(config=config)

    # Load both projects
    print("\nLoading memory-mcp...")
    env.load_data("memory-mcp")

    print("Loading context-cascade...")
    env.load_data("context-cascade")

    stats = env.get_stats()
    print(f"\nTotal files indexed: {stats['total_files']}")
    print(f"Projects loaded: {stats['total_projects']}")
    print(f"By language: {stats['by_language']}")

    return env


def search_integration_points(env: RLMCodebaseEnvironment):
    """Search for integration points between the two systems."""
    print("\n" + "=" * 70)
    print("PHASE 2: SEARCHING FOR INTEGRATION POINTS")
    print("=" * 70)

    findings = []

    # Search for Memory MCP references in Context Cascade
    print("\n[1] Searching for 'memory' references...")
    memory_refs = env.search("memory", limit=20)
    print(f"   Found {len(memory_refs)} files referencing 'memory'")

    # Search for namespace patterns
    print("\n[2] Searching for namespace patterns...")
    namespace_refs = env.search("namespace", limit=20)
    print(f"   Found {len(namespace_refs)} files referencing 'namespace'")

    # Search for telemetry patterns
    print("\n[3] Searching for 'telemetry' references...")
    telemetry_refs = env.search("telemetry", limit=20)
    print(f"   Found {len(telemetry_refs)} files referencing 'telemetry'")

    # Search for loop references (Loop 1, 1.5, 2, 3)
    print("\n[4] Searching for loop patterns...")
    loop_refs = env.search("loop", limit=20)
    print(f"   Found {len(loop_refs)} files referencing 'loop'")

    # Content search for specific patterns
    print("\n[5] Searching file contents for integration patterns...")

    # Look for WHO/WHEN/PROJECT/WHY pattern
    who_when_refs = env.search_content("WHO", limit=10)
    print(f"   WHO/WHEN/PROJECT pattern: {len(who_when_refs)} files")

    # Look for confidence scores
    confidence_refs = env.search_content("confidence", limit=10)
    print(f"   'confidence' references: {len(confidence_refs)} files")

    # Look for NASA Rule 10 compliance markers
    nasa_refs = env.search_content("NASA Rule 10", limit=10)
    print(f"   NASA Rule 10 markers: {len(nasa_refs)} files")

    return {
        "memory_refs": memory_refs,
        "namespace_refs": namespace_refs,
        "telemetry_refs": telemetry_refs,
        "loop_refs": loop_refs,
        "who_when_refs": who_when_refs,
        "confidence_refs": confidence_refs,
        "nasa_refs": nasa_refs,
    }


def identify_inconsistencies(env: RLMCodebaseEnvironment, findings: Dict):
    """Identify potential inconsistencies."""
    print("\n" + "=" * 70)
    print("PHASE 3: IDENTIFYING POTENTIAL INCONSISTENCIES")
    print("=" * 70)

    hypotheses = []

    # Hypothesis 1: Signal confidence values might be inconsistent
    print("\n[Hypothesis 1] Signal confidence values")
    print("   Memory MCP defines: CORRECTION=0.90, RULE=0.90, APPROVAL=0.75, OBSERVATION=0.55")
    print("   Checking if Context Cascade uses same values...")

    confidence_in_cascade = [f for f in findings.get("confidence_refs", [])
                            if "context-cascade" in f.get("path", "")]
    confidence_in_memory = [f for f in findings.get("confidence_refs", [])
                           if "memory-mcp" in f.get("path", "")]

    hypotheses.append({
        "id": "H1",
        "title": "Signal confidence values inconsistency",
        "description": "Context Cascade may define different confidence values than Memory MCP",
        "memory_mcp_files": len(confidence_in_memory),
        "context_cascade_files": len(confidence_in_cascade),
        "falsifiable_test": "Search for 0.90, 0.75, 0.55 values in both codebases and compare",
    })

    # Hypothesis 2: Namespace patterns might differ
    print("\n[Hypothesis 2] Namespace format consistency")
    print("   Memory MCP uses: expertise:{domain}:{topic}")
    print("   Checking if Context Cascade follows same pattern...")

    hypotheses.append({
        "id": "H2",
        "title": "Namespace format inconsistency",
        "description": "Namespace patterns may differ between Memory MCP and Context Cascade",
        "falsifiable_test": "Extract all namespace patterns from both codebases and diff",
    })

    # Hypothesis 3: Loop interface might be incomplete
    print("\n[Hypothesis 3] Loop interface completeness")
    print("   Memory MCP has Loop15StorageInterface, Loop3QueryInterface")
    print("   Context Cascade should have corresponding consumers...")

    loop_in_cascade = [f for f in findings.get("loop_refs", [])
                      if "context-cascade" in f.get("path", "")]

    hypotheses.append({
        "id": "H3",
        "title": "Loop interface consumer missing",
        "description": "Context Cascade may not properly consume Loop 1.5/3 interfaces",
        "context_cascade_loop_files": len(loop_in_cascade),
        "falsifiable_test": "Check for Loop15StorageInterface/Loop3QueryInterface imports in Context Cascade",
    })

    # Hypothesis 4: NASA Rule 10 compliance gaps
    print("\n[Hypothesis 4] NASA Rule 10 compliance")
    print("   Memory MCP marks functions with LOC counts")
    print("   Context Cascade may not follow same pattern...")

    nasa_in_cascade = [f for f in findings.get("nasa_refs", [])
                      if "context-cascade" in f.get("path", "")]
    nasa_in_memory = [f for f in findings.get("nasa_refs", [])
                     if "memory-mcp" in f.get("path", "")]

    hypotheses.append({
        "id": "H4",
        "title": "NASA Rule 10 compliance gap",
        "description": "Context Cascade may have functions exceeding 60 LOC",
        "memory_mcp_nasa_markers": len(nasa_in_memory),
        "context_cascade_nasa_markers": len(nasa_in_cascade),
        "falsifiable_test": "Count functions >60 LOC in both codebases",
    })

    # Hypothesis 5: Telemetry packet schema usage
    print("\n[Hypothesis 5] Telemetry packet schema usage")
    print("   Memory MCP defines TelemetryPacket with WHO/WHEN/PROJECT/WHY")
    print("   Context Cascade should use this for all telemetry...")

    hypotheses.append({
        "id": "H5",
        "title": "Telemetry packet schema not used",
        "description": "Context Cascade may not use Memory MCP's telemetry packet schema",
        "falsifiable_test": "Search for TelemetryPacket imports in Context Cascade",
    })

    return hypotheses


def run_falsifiable_tests(env: RLMCodebaseEnvironment, hypotheses: List[Dict]):
    """Run falsifiable tests for each hypothesis."""
    print("\n" + "=" * 70)
    print("PHASE 4: RUNNING FALSIFIABLE TESTS")
    print("=" * 70)

    results = []

    for h in hypotheses:
        print(f"\n[{h['id']}] Testing: {h['title']}")
        print(f"   Test: {h['falsifiable_test']}")

        result = {"hypothesis": h["id"], "title": h["title"]}

        if h["id"] == "H1":
            # Test: Search for confidence value literals
            val_090 = env.search_content("0.90", limit=50)
            val_075 = env.search_content("0.75", limit=50)
            val_055 = env.search_content("0.55", limit=50)

            cascade_090 = len([f for f in val_090 if "context-cascade" in f.get("path", "")])
            cascade_075 = len([f for f in val_075 if "context-cascade" in f.get("path", "")])
            cascade_055 = len([f for f in val_055 if "context-cascade" in f.get("path", "")])

            memory_090 = len([f for f in val_090 if "memory-mcp" in f.get("path", "")])

            result["findings"] = {
                "memory_mcp_0.90_refs": memory_090,
                "context_cascade_0.90_refs": cascade_090,
                "context_cascade_0.75_refs": cascade_075,
                "context_cascade_0.55_refs": cascade_055,
            }
            result["verdict"] = "POTENTIAL_ISSUE" if cascade_090 == 0 else "CONSISTENT"
            print(f"   Result: Memory MCP has {memory_090} refs to 0.90, Context Cascade has {cascade_090}")

        elif h["id"] == "H2":
            # Test: Search for namespace patterns
            expertise_pattern = env.search_content("expertise:", limit=20)
            findings_pattern = env.search_content("findings:", limit=20)

            cascade_expertise = [f for f in expertise_pattern if "context-cascade" in f.get("path", "")]
            cascade_findings = [f for f in findings_pattern if "context-cascade" in f.get("path", "")]

            result["findings"] = {
                "context_cascade_expertise_refs": len(cascade_expertise),
                "context_cascade_findings_refs": len(cascade_findings),
            }
            result["verdict"] = "POTENTIAL_GAP" if len(cascade_expertise) == 0 else "CONSISTENT"
            print(f"   Result: Context Cascade has {len(cascade_expertise)} expertise: refs, {len(cascade_findings)} findings: refs")

        elif h["id"] == "H3":
            # Test: Search for Loop interface imports
            loop15_import = env.search_content("Loop15StorageInterface", limit=20)
            loop3_import = env.search_content("Loop3QueryInterface", limit=20)

            cascade_loop15 = [f for f in loop15_import if "context-cascade" in f.get("path", "")]
            cascade_loop3 = [f for f in loop3_import if "context-cascade" in f.get("path", "")]

            result["findings"] = {
                "context_cascade_loop15_imports": len(cascade_loop15),
                "context_cascade_loop3_imports": len(cascade_loop3),
            }
            result["verdict"] = "INTEGRATION_GAP" if len(cascade_loop15) == 0 and len(cascade_loop3) == 0 else "INTEGRATED"
            print(f"   Result: Loop15 imports: {len(cascade_loop15)}, Loop3 imports: {len(cascade_loop3)}")

        elif h["id"] == "H4":
            # Test: Count NASA markers
            nasa_markers = env.search_content("NASA Rule 10", limit=100)

            cascade_nasa = [f for f in nasa_markers if "context-cascade" in f.get("path", "")]
            memory_nasa = [f for f in nasa_markers if "memory-mcp" in f.get("path", "")]

            result["findings"] = {
                "memory_mcp_nasa_markers": len(memory_nasa),
                "context_cascade_nasa_markers": len(cascade_nasa),
            }
            result["verdict"] = "COMPLIANCE_GAP" if len(cascade_nasa) < len(memory_nasa) // 2 else "COMPLIANT"
            print(f"   Result: Memory MCP: {len(memory_nasa)} markers, Context Cascade: {len(cascade_nasa)} markers")

        elif h["id"] == "H5":
            # Test: Search for TelemetryPacket usage
            telemetry_import = env.search_content("TelemetryPacket", limit=20)
            telemetry_builder = env.search_content("TelemetryPacketBuilder", limit=20)

            cascade_packet = [f for f in telemetry_import if "context-cascade" in f.get("path", "")]
            cascade_builder = [f for f in telemetry_builder if "context-cascade" in f.get("path", "")]

            result["findings"] = {
                "context_cascade_packet_refs": len(cascade_packet),
                "context_cascade_builder_refs": len(cascade_builder),
            }
            result["verdict"] = "NOT_INTEGRATED" if len(cascade_packet) == 0 else "INTEGRATED"
            print(f"   Result: TelemetryPacket refs: {len(cascade_packet)}, Builder refs: {len(cascade_builder)}")

        results.append(result)

    return results


def generate_report(hypotheses: List[Dict], test_results: List[Dict]):
    """Generate final analysis report."""
    print("\n" + "=" * 70)
    print("PHASE 5: ANALYSIS REPORT")
    print("=" * 70)

    issues_found = []

    for result in test_results:
        verdict = result.get("verdict", "UNKNOWN")

        if verdict in ["POTENTIAL_ISSUE", "POTENTIAL_GAP", "INTEGRATION_GAP", "COMPLIANCE_GAP", "NOT_INTEGRATED"]:
            issues_found.append(result)
            print(f"\n[!] {result['title']}")
            print(f"    Verdict: {verdict}")
            print(f"    Findings: {json.dumps(result.get('findings', {}), indent=2)}")

    print("\n" + "-" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"Total hypotheses tested: {len(hypotheses)}")
    print(f"Potential issues found: {len(issues_found)}")

    if issues_found:
        print("\nISSUES REQUIRING ATTENTION:")
        for i, issue in enumerate(issues_found, 1):
            print(f"  {i}. [{issue['hypothesis']}] {issue['title']} - {issue['verdict']}")
    else:
        print("\nNo critical inconsistencies found between codebases.")

    return {
        "total_hypotheses": len(hypotheses),
        "issues_found": len(issues_found),
        "issues": issues_found,
        "timestamp": datetime.utcnow().isoformat(),
    }


def main():
    """Main analysis function."""
    print("=" * 70)
    print("RLM CODEBASE ANALYSIS: Memory MCP vs Context Cascade")
    print("=" * 70)
    print(f"Started: {datetime.utcnow().isoformat()}")

    # Phase 1: Load codebases
    env = load_codebases()

    # Phase 2: Search for integration points
    findings = search_integration_points(env)

    # Phase 3: Identify inconsistencies
    hypotheses = identify_inconsistencies(env, findings)

    # Phase 4: Run falsifiable tests
    test_results = run_falsifiable_tests(env, hypotheses)

    # Phase 5: Generate report
    report = generate_report(hypotheses, test_results)

    # Save report
    report_path = Path(__file__).parent / "rlm_analysis_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {report_path}")

    return 0 if report["issues_found"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
