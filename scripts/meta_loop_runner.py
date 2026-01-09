#!/usr/bin/env python3
"""
Meta-Loop Runner (Loop 3)

Runs every 3 days to aggregate session learnings from Memory MCP
and generate optimization suggestions for skill improvements.

Usage:
    python meta_loop_runner.py              # Full run
    python meta_loop_runner.py --dry-run    # Preview only
    python meta_loop_runner.py --days 7     # Query last 7 days

Schedule: Every 3 days at 3:00 AM (Windows Task Scheduler)
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import chromadb
from chromadb.config import Settings
import yaml


def load_config() -> Dict[str, Any]:
    """Load Memory MCP configuration."""
    config_path = Path(__file__).parent.parent / "config" / "memory-mcp.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_collection(config: Dict[str, Any]):
    """Get ChromaDB collection."""
    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])
    collection_name = config['storage']['vector_db']['collection_name']

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    return client.get_collection(name=collection_name)


def query_session_learnings(days: int = 3) -> List[Dict[str, Any]]:
    """
    Query Memory MCP for session learnings from the last N days.

    Args:
        days: Number of days to look back

    Returns:
        List of learning entries with metadata
    """
    config = load_config()
    collection = get_collection(config)

    # Calculate cutoff timestamp
    cutoff = datetime.utcnow() - timedelta(days=days)
    cutoff_unix = int(cutoff.timestamp())

    # Query for session-learning intent
    # ChromaDB where clause for metadata filtering
    results = collection.get(
        where={"intent": "session-learning"},
        include=["documents", "metadatas"]
    )

    learnings = []
    for doc_id, doc, meta in zip(
        results.get("ids", []),
        results.get("documents", []),
        results.get("metadatas", [])
    ):
        # Filter by timestamp
        timestamp_unix = meta.get('timestamp_unix', 0)
        if timestamp_unix >= cutoff_unix:
            learnings.append({
                'id': doc_id,
                'content': doc,
                'metadata': meta
            })

    return learnings


def aggregate_by_skill(learnings: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
    """
    Group learnings by the skill they apply to.

    Args:
        learnings: List of learning entries

    Returns:
        Dict mapping skill name to list of learnings
    """
    by_skill = defaultdict(list)

    for learning in learnings:
        meta = learning.get('metadata', {})
        skill = meta.get('x-skill', 'unknown')
        by_skill[skill].append({
            'content': learning.get('content', ''),
            'confidence': meta.get('x-confidence', 0.55),
            'signal_type': meta.get('x-signal-type', 'observation'),
            'session_id': meta.get('x-session-id', 'unknown'),
            'timestamp': meta.get('timestamp', ''),
            'ground': meta.get('x-ground', '')
        })

    return dict(by_skill)


def identify_patterns(skill_learnings: Dict[str, List[Dict]]) -> List[Dict[str, Any]]:
    """
    Find recurring patterns that should be promoted to higher confidence.

    Rules:
    - Same correction appearing 2+ times -> Promote to HIGH
    - Multiple approvals of same pattern -> Confirm as MEDIUM
    - Conflicting learnings -> Flag for review

    Args:
        skill_learnings: Dict of skill -> learnings

    Returns:
        List of identified patterns with recommendations
    """
    patterns = []

    for skill, learnings in skill_learnings.items():
        # Skip summary entries
        learnings = [l for l in learnings if l.get('signal_type') != 'session-summary']

        if not learnings:
            continue

        # Group by similar content (simple text similarity)
        content_groups = defaultdict(list)
        for learning in learnings:
            # Extract key content (first 100 chars normalized)
            content = learning.get('content', '')
            # Extract the actual learning line
            if 'Learning:' in content:
                key = content.split('Learning:')[1].split('\n')[0].strip().lower()[:100]
            else:
                key = content[:100].lower()
            content_groups[key].append(learning)

        # Analyze each group
        for content_key, group in content_groups.items():
            if len(group) >= 2:
                # Recurring pattern found
                signal_types = [l.get('signal_type') for l in group]
                current_conf = max(l.get('confidence', 0.55) for l in group)

                # Determine promotion
                if signal_types.count('correction') >= 2:
                    promotion = 'HIGH' if current_conf < 0.90 else None
                    recommendation = 'Recurring correction - promote to HIGH confidence'
                elif signal_types.count('approval') >= 2:
                    promotion = 'MEDIUM' if current_conf < 0.75 else None
                    recommendation = 'Confirmed pattern - maintain MEDIUM confidence'
                else:
                    promotion = None
                    recommendation = 'Pattern observed, needs more evidence'

                if promotion or len(group) >= 3:
                    patterns.append({
                        'skill': skill,
                        'pattern': content_key[:80],
                        'occurrences': len(group),
                        'current_confidence': current_conf,
                        'signal_types': signal_types,
                        'confidence_promotion': f"{current_conf} -> {promotion}" if promotion else 'No change',
                        'recommendation': recommendation,
                        'sessions': list(set(l.get('session_id') for l in group))
                    })

    return patterns


def detect_conflicts(skill_learnings: Dict[str, List[Dict]]) -> List[Dict[str, Any]]:
    """
    Detect conflicting learnings within the same skill.

    Returns:
        List of conflicts requiring resolution
    """
    conflicts = []

    # Keywords that indicate potential conflicts
    conflict_indicators = [
        ('always', 'never'),
        ('use', 'avoid'),
        ('prefer', 'avoid'),
        ('should', 'should not')
    ]

    for skill, learnings in skill_learnings.items():
        contents = [l.get('content', '').lower() for l in learnings]

        for i, content_i in enumerate(contents):
            for j, content_j in enumerate(contents[i+1:], i+1):
                for pos, neg in conflict_indicators:
                    # Check if one says "always X" and another says "never X" or similar
                    if pos in content_i and neg in content_j:
                        if any(word in content_i and word in content_j for word in content_i.split() if len(word) > 4):
                            conflicts.append({
                                'skill': skill,
                                'learning_1': learnings[i].get('content', '')[:100],
                                'learning_2': learnings[j].get('content', '')[:100],
                                'type': 'potential_contradiction',
                                'recommendation': 'Manual review required'
                            })

    return conflicts


def generate_report(
    learnings: List[Dict],
    by_skill: Dict[str, List[Dict]],
    patterns: List[Dict],
    conflicts: List[Dict],
    days: int
) -> Dict[str, Any]:
    """Generate meta-loop optimization report."""
    return {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'period_days': days,
        'summary': {
            'total_learnings': len(learnings),
            'skills_affected': list(by_skill.keys()),
            'patterns_identified': len(patterns),
            'conflicts_detected': len(conflicts)
        },
        'by_skill': {
            skill: {
                'count': len(items),
                'signal_types': dict(defaultdict(int, {l.get('signal_type', 'observation'): 1 for l in items}))
            }
            for skill, items in by_skill.items()
        },
        'patterns': patterns,
        'conflicts': conflicts,
        'recommendations': [
            {
                'skill': p['skill'],
                'action': p['recommendation'],
                'priority': 'HIGH' if 'HIGH' in p.get('confidence_promotion', '') else 'MEDIUM'
            }
            for p in patterns
            if p.get('recommendation')
        ]
    }


def run_meta_loop(days: int = 3, dry_run: bool = False) -> Dict[str, Any]:
    """
    Execute the full meta-loop optimization cycle.

    Args:
        days: Number of days to analyze
        dry_run: Preview only, no actions

    Returns:
        Meta-loop report
    """
    print("=" * 60)
    print(f"Meta-Loop Optimization (Loop 3)")
    print(f"Period: Last {days} days")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 60)
    print()

    # Step 1: Query learnings
    print("Step 1: Querying session learnings...")
    learnings = query_session_learnings(days)
    print(f"  Found: {len(learnings)} learnings")

    if not learnings:
        print("\nNo session learnings found in the specified period.")
        print("Run /reflect in sessions to generate learnings.")
        return {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'period_days': days,
            'summary': {'total_learnings': 0, 'skills_affected': [], 'patterns_identified': 0, 'conflicts_detected': 0},
            'patterns': [],
            'conflicts': [],
            'recommendations': []
        }

    # Step 2: Aggregate by skill
    print("\nStep 2: Aggregating by skill...")
    by_skill = aggregate_by_skill(learnings)
    print(f"  Skills: {list(by_skill.keys())}")

    # Step 3: Identify patterns
    print("\nStep 3: Identifying patterns...")
    patterns = identify_patterns(by_skill)
    print(f"  Patterns found: {len(patterns)}")

    # Step 4: Detect conflicts
    print("\nStep 4: Detecting conflicts...")
    conflicts = detect_conflicts(by_skill)
    print(f"  Conflicts found: {len(conflicts)}")

    # Step 5: Generate report
    print("\nStep 5: Generating report...")
    report = generate_report(learnings, by_skill, patterns, conflicts, days)

    # Display summary
    print("\n" + "=" * 60)
    print("META-LOOP SUMMARY")
    print("=" * 60)
    print(f"\nTotal learnings analyzed: {report['summary']['total_learnings']}")
    print(f"Skills affected: {', '.join(report['summary']['skills_affected']) or 'none'}")
    print(f"Patterns identified: {report['summary']['patterns_identified']}")
    print(f"Conflicts detected: {report['summary']['conflicts_detected']}")

    if patterns:
        print("\n--- Patterns for Review ---")
        for p in patterns[:5]:  # Show top 5
            print(f"\n  Skill: {p['skill']}")
            print(f"  Pattern: {p['pattern'][:60]}...")
            print(f"  Occurrences: {p['occurrences']}")
            print(f"  Confidence: {p['confidence_promotion']}")
            print(f"  Action: {p['recommendation']}")

    if conflicts:
        print("\n--- Conflicts Requiring Resolution ---")
        for c in conflicts[:3]:  # Show top 3
            print(f"\n  Skill: {c['skill']}")
            print(f"  Learning 1: {c['learning_1'][:50]}...")
            print(f"  Learning 2: {c['learning_2'][:50]}...")
            print(f"  Action: {c['recommendation']}")

    if report['recommendations']:
        print("\n--- Recommendations ---")
        for r in report['recommendations'][:5]:
            print(f"  [{r['priority']}] {r['skill']}: {r['action']}")

    # Save report
    if not dry_run:
        reports_dir = Path(__file__).parent.parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        report_file = reports_dir / f"meta-loop-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        report_file.write_text(json.dumps(report, indent=2))
        print(f"\nReport saved: {report_file}")

    return report


def main():
    parser = argparse.ArgumentParser(description='Meta-Loop Optimization Runner')
    parser.add_argument(
        '--days',
        type=int,
        default=3,
        help='Number of days to analyze (default: 3)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without saving report'
    )

    args = parser.parse_args()

    report = run_meta_loop(days=args.days, dry_run=args.dry_run)

    # Exit code based on findings
    if report['summary']['conflicts_detected'] > 0:
        return 2  # Conflicts need resolution
    elif report['summary']['patterns_identified'] > 0:
        return 1  # Patterns found, review recommended
    return 0


if __name__ == "__main__":
    sys.exit(main())
