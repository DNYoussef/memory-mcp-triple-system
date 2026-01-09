#!/usr/bin/env python3
"""
Memory MCP Weekly Hygiene Script

Automated maintenance that runs weekly to:
1. Run full audit of all three tiers
2. Clean up low-confidence memories (<0.3)
3. Reinforce high-usage memories
4. Export statistics to dashboard
5. Send summary notification

Schedule: Sundays at 3:00 AM (cron: 0 3 * * 0)

Usage:
    python weekly_hygiene.py              # Full run
    python weekly_hygiene.py --dry-run    # Preview only
    python weekly_hygiene.py --notify     # Also send notification
"""

import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import Counter

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import chromadb
from chromadb.config import Settings


def load_config():
    """Load configuration."""
    import yaml
    config_path = Path(__file__).parent.parent / "config" / "memory-mcp.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def run_audit() -> Dict[str, Any]:
    """Run the audit script and get results."""
    print("--- Step 1: Running Full Audit ---")

    audit_script = Path(__file__).parent / "audit_memory.py"
    result = subprocess.run(
        [sys.executable, str(audit_script)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Audit script error: {result.stderr}")
        return {}

    # Find latest audit report
    reports_dir = Path(__file__).parent.parent / "reports"
    audit_files = sorted(reports_dir.glob("audit-*.json"), reverse=True)

    if audit_files:
        with open(audit_files[0]) as f:
            return json.load(f)

    return {}


def cleanup_low_confidence(dry_run: bool = True) -> Dict[str, Any]:
    """Remove memories with very low confidence (<0.2)."""
    print("\n--- Step 2: Cleanup Low Confidence ---")

    config = load_config()
    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])
    collection_name = config['storage']['vector_db']['collection_name']

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    collection = client.get_collection(name=collection_name)

    # Find low confidence memories
    results = collection.get(
        limit=10000,
        include=["metadatas"]
    )

    low_conf_ids = []
    for doc_id, meta in zip(results.get("ids", []), results.get("metadatas", [])):
        conf = meta.get("confidence", 0.5)
        if conf < 0.2:  # Very low threshold
            low_conf_ids.append(doc_id)

    stats = {
        "found": len(low_conf_ids),
        "deleted": 0
    }

    if low_conf_ids:
        print(f"Found {len(low_conf_ids)} memories with confidence < 0.2")

        if not dry_run:
            # Batch delete (ChromaDB supports batch operations)
            collection.delete(ids=low_conf_ids)
            stats["deleted"] = len(low_conf_ids)
            print(f"Deleted {stats['deleted']} low-confidence memories")
        else:
            print("[DRY RUN] Would delete these memories")
    else:
        print("No low-confidence memories to clean up")

    return stats


def reinforce_active_memories(dry_run: bool = True) -> Dict[str, Any]:
    """Boost confidence of frequently accessed memories."""
    print("\n--- Step 3: Reinforce Active Memories ---")

    # This would integrate with access logging if available
    # For now, reinforce recent high-confidence ecosystem memories

    config = load_config()
    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])
    collection_name = config['storage']['vector_db']['collection_name']

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    collection = client.get_collection(name=collection_name)

    # Get ecosystem-population memories
    results = collection.get(
        where={"WHO": "ecosystem-population:1.0"},
        include=["metadatas"]
    )

    reinforced = 0
    for doc_id, meta in zip(results.get("ids", []), results.get("metadatas", [])):
        # Mark as reinforced
        if not meta.get("reinforced", False):
            if not dry_run:
                collection.update(
                    ids=[doc_id],
                    metadatas=[{**meta, "reinforced": True}]
                )
            reinforced += 1

    print(f"Reinforced {reinforced} ecosystem memories")
    return {"reinforced": reinforced}


def calculate_decay_scores() -> Dict[str, Any]:
    """Apply temporal decay to all memories based on age."""
    print("\n--- Step 4: Calculate Decay Scores ---")

    config = load_config()
    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])
    collection_name = config['storage']['vector_db']['collection_name']

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    collection = client.get_collection(name=collection_name)

    # Sample for statistics
    sample = collection.get(
        limit=1000,
        include=["metadatas"]
    )

    import math
    now = datetime.now()

    layer_counts = Counter()

    for meta in sample.get("metadatas", []):
        when = meta.get("WHEN", "")

        try:
            if when:
                timestamp = datetime.fromisoformat(when.replace("Z", "+00:00").split("+")[0])
                days_old = (now - timestamp).days
            else:
                days_old = 30  # Default to mid-term
        except:
            days_old = 30

        # Decay formula: e^(-days/30)
        decay = math.exp(-days_old / 30)

        # Categorize by layer
        if decay >= 0.9:  # <3 days
            layer_counts["short-term"] += 1
        elif decay >= 0.7:  # <11 days
            layer_counts["mid-term"] += 1
        else:
            layer_counts["long-term"] += 1

    print(f"Layer distribution (sample of 1000):")
    print(f"  Short-term (decay >= 0.9): {layer_counts['short-term']}")
    print(f"  Mid-term (0.7-0.9): {layer_counts['mid-term']}")
    print(f"  Long-term (< 0.7): {layer_counts['long-term']}")

    return dict(layer_counts)


def export_dashboard_stats(audit_results: Dict, cleanup_stats: Dict) -> str:
    """Export statistics for dashboard consumption."""
    print("\n--- Step 5: Export Dashboard Stats ---")

    config = load_config()
    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])
    collection_name = config['storage']['vector_db']['collection_name']

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    collection = client.get_collection(name=collection_name)

    stats = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_memories": collection.count(),
            "health_score": audit_results.get("recommendations", {}).get("summary", {}).get("health_score", 0),
            "graph_nodes": audit_results.get("hipporag", {}).get("nodes", 0),
            "graph_edges": audit_results.get("hipporag", {}).get("edges", 0),
            "graph_connectivity": audit_results.get("hipporag", {}).get("connectivity", {}).get("largest_component_pct", 0),
            "avg_confidence": audit_results.get("bayesian", {}).get("confidence_analysis", {}).get("avg_confidence", 0)
        },
        "cleanup": cleanup_stats,
        "vector_rag": audit_results.get("vector_rag", {}),
        "hipporag": audit_results.get("hipporag", {}),
        "bayesian": audit_results.get("bayesian", {})
    }

    # Export to dashboard data directory
    dashboard_file = Path(__file__).parent.parent / "data" / "dashboard-stats.json"
    dashboard_file.write_text(json.dumps(stats, indent=2))

    print(f"Exported dashboard stats to: {dashboard_file}")
    return str(dashboard_file)


def send_notification(summary: Dict[str, Any], notify: bool = False) -> None:
    """Send summary notification (optional)."""
    if not notify:
        return

    print("\n--- Step 6: Send Notification ---")

    # Format summary for notification
    msg = f"""Memory MCP Weekly Hygiene Complete

Total Memories: {summary.get('total', 0)}
Health Score: {summary.get('health_score', 0)}/100
Cleaned: {summary.get('cleaned', 0)}
Reinforced: {summary.get('reinforced', 0)}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""

    # Could integrate with Windows toast, email, or webhook
    print(msg)
    print("(Notification would be sent if webhook configured)")


def run_weekly_hygiene(dry_run: bool = True, notify: bool = False) -> Dict[str, Any]:
    """Run full weekly hygiene routine."""
    print("=" * 60)
    print(f"Memory MCP Weekly Hygiene {'(DRY RUN)' if dry_run else '(EXECUTING)'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    # Step 1: Run audit
    audit_results = run_audit()

    # Step 2: Cleanup low confidence
    cleanup_stats = cleanup_low_confidence(dry_run=dry_run)

    # Step 3: Reinforce active memories
    reinforce_stats = reinforce_active_memories(dry_run=dry_run)

    # Step 4: Calculate decay scores
    decay_stats = calculate_decay_scores()

    # Step 5: Export dashboard stats
    dashboard_file = export_dashboard_stats(audit_results, cleanup_stats)

    # Summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "total": audit_results.get("vector_rag", {}).get("total", 0),
        "health_score": audit_results.get("recommendations", {}).get("summary", {}).get("health_score", 0),
        "cleaned": cleanup_stats.get("deleted", 0),
        "reinforced": reinforce_stats.get("reinforced", 0),
        "layer_distribution": decay_stats,
        "dashboard_export": dashboard_file
    }

    # Step 6: Send notification
    send_notification(summary, notify=notify)

    # Final report
    print("\n" + "=" * 60)
    print("WEEKLY HYGIENE SUMMARY")
    print("=" * 60)
    print(f"\nTotal memories: {summary['total']}")
    print(f"Health score: {summary['health_score']}/100")
    print(f"Low-conf cleaned: {summary['cleaned']}")
    print(f"Reinforced: {summary['reinforced']}")

    if dry_run:
        print(f"\n[DRY RUN] No changes applied. Run without --dry-run to execute.")
    else:
        print(f"\n[COMPLETE] Weekly hygiene finished.")

    # Save report
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_file = reports_dir / f"hygiene-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    report_file.write_text(json.dumps(summary, indent=2))
    print(f"\nReport saved to: {report_file}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Memory MCP Weekly Hygiene")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--notify", action="store_true", help="Send notification")

    args = parser.parse_args()

    run_weekly_hygiene(dry_run=args.dry_run, notify=args.notify)


if __name__ == "__main__":
    main()
