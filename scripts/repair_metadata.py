#!/usr/bin/env python3
"""
Memory MCP Metadata Repair Script

Fixes critical issues found in audit:
1. Adds WHO/WHEN/PROJECT/WHY metadata to all memories
2. Adds confidence scores for Bayesian tier
3. Reports progress

Usage:
    python repair_metadata.py --dry-run     # Preview changes
    python repair_metadata.py --execute     # Apply changes
"""

import sys
import json
import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
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


def infer_project_from_content(text: str) -> str:
    """Infer project name from memory content."""
    # Known project patterns
    project_patterns = {
        r'memory[_-]?mcp|chromadb|hipporag|bayesian': 'memory-mcp-triple-system',
        r'life[_-]?os[_-]?dashboard|fastapi.*dashboard': 'life-os-dashboard',
        r'life[_-]?os[_-]?frontend|react.*dashboard': 'life-os-frontend',
        r'claude[_-]?dev[_-]?cli|quality.*suite': 'claude-dev-cli',
        r'trader[_-]?ai|dual[_-]?momentum|barbell': 'trader-ai',
        r'context[_-]?cascade|verilingua|verix': 'context-cascade',
        r'connascence|nasa.*safety|mece|six.*sigma': 'connascence',
        r'portfolio|dnyoussef|astro': 'dnyoussef-portfolio',
        r'slop[_-]?detect': 'slop-detector',
        r'fog[_-]?compute|distributed': 'fog-compute',
        r'meta[_-]?calculus': 'meta-calculus-toolkit',
        r'nsbu|rpg[_-]?app': 'nsbu-rpg-app',
        r'agent[_-]?maker|agent[_-]?forge': 'the-agent-maker',
    }

    text_lower = text.lower()
    for pattern, project in project_patterns.items():
        if re.search(pattern, text_lower):
            return project

    return 'general'


def infer_why_from_content(text: str) -> str:
    """Infer WHY (intent) from memory content."""
    text_lower = text.lower()

    # Intent patterns
    if any(word in text_lower for word in ['fix', 'bug', 'error', 'issue', 'debug']):
        return 'bugfix'
    elif any(word in text_lower for word in ['refactor', 'cleanup', 'improve', 'optimize']):
        return 'refactor'
    elif any(word in text_lower for word in ['test', 'spec', 'assert', 'expect']):
        return 'testing'
    elif any(word in text_lower for word in ['doc', 'readme', 'comment', 'explain']):
        return 'documentation'
    elif any(word in text_lower for word in ['plan', 'design', 'architect', 'decision']):
        return 'planning'
    elif any(word in text_lower for word in ['research', 'explore', 'investigate']):
        return 'research'
    elif any(word in text_lower for word in ['implement', 'add', 'create', 'build', 'feature']):
        return 'implementation'
    elif any(word in text_lower for word in ['config', 'setup', 'install', 'deploy']):
        return 'configuration'
    elif any(word in text_lower for word in ['session', 'conversation', 'chat']):
        return 'session-context'
    else:
        return 'general'


def calculate_confidence(text: str, existing_metadata: Dict) -> float:
    """Calculate confidence score based on content quality indicators."""
    score = 0.5  # Base confidence

    # Content length bonus (longer = more detailed = higher confidence)
    length = len(text)
    if length > 2000:
        score += 0.15
    elif length > 1000:
        score += 0.10
    elif length > 500:
        score += 0.05
    elif length < 100:
        score -= 0.10

    # Code presence bonus (code snippets indicate specific knowledge)
    if '```' in text or 'def ' in text or 'function ' in text or 'class ' in text:
        score += 0.10

    # Structure bonus (headers, lists indicate organized knowledge)
    if re.search(r'^#+\s', text, re.MULTILINE):  # Markdown headers
        score += 0.05
    if re.search(r'^\s*[-*]\s', text, re.MULTILINE):  # Lists
        score += 0.05

    # File path presence (specific references)
    if re.search(r'[A-Za-z]:[/\\]|/[a-z]+/', text):
        score += 0.05

    # Clamp to valid range
    return max(0.1, min(0.95, round(score, 2)))


def repair_memories(dry_run: bool = True, batch_size: int = 500) -> Dict[str, Any]:
    """Repair all memories with missing metadata and confidence."""
    print("=" * 60)
    print(f"Memory MCP Metadata Repair {'(DRY RUN)' if dry_run else '(EXECUTING)'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    config = load_config()
    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])
    collection_name = config['storage']['vector_db']['collection_name']

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )

    collection = client.get_collection(name=collection_name)
    total = collection.count()

    print(f"\nTotal memories to process: {total}")

    stats = {
        'processed': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
        'project_distribution': Counter(),
        'why_distribution': Counter(),
        'confidence_distribution': {
            'low': 0,      # < 0.3
            'medium': 0,   # 0.3-0.7
            'high': 0      # > 0.7
        }
    }

    # Process in batches
    offset = 0
    while offset < total:
        # Get batch
        results = collection.get(
            limit=batch_size,
            offset=offset,
            include=["documents", "metadatas"]
        )

        if not results.get("ids"):
            break

        batch_ids = results["ids"]
        batch_docs = results.get("documents", [])
        batch_metas = results.get("metadatas", [])

        # Process each memory
        ids_to_update = []
        metas_to_update = []

        for i, doc_id in enumerate(batch_ids):
            doc = batch_docs[i] if i < len(batch_docs) else ""
            meta = batch_metas[i] if i < len(batch_metas) else {}

            try:
                # Check if already has required fields
                has_who = "WHO" in meta and meta["WHO"]
                has_when = "WHEN" in meta and meta["WHEN"]
                has_project = "PROJECT" in meta and meta["PROJECT"]
                has_why = "WHY" in meta and meta["WHY"]
                has_confidence = "confidence" in meta and meta["confidence"] is not None

                if has_who and has_when and has_project and has_why and has_confidence:
                    stats['skipped'] += 1
                    continue

                # Build updated metadata
                updated_meta = dict(meta)

                if not has_who:
                    updated_meta["WHO"] = "legacy-import:1.0"

                if not has_when:
                    # Use existing timestamp if available, otherwise use epoch marker
                    if "timestamp" in meta:
                        updated_meta["WHEN"] = meta["timestamp"]
                    elif "created_at" in meta:
                        updated_meta["WHEN"] = meta["created_at"]
                    else:
                        updated_meta["WHEN"] = "2025-01-01T00:00:00"  # Legacy marker

                if not has_project:
                    project = infer_project_from_content(doc)
                    updated_meta["PROJECT"] = project
                    stats['project_distribution'][project] += 1

                if not has_why:
                    why = infer_why_from_content(doc)
                    updated_meta["WHY"] = why
                    stats['why_distribution'][why] += 1

                if not has_confidence:
                    confidence = calculate_confidence(doc, meta)
                    updated_meta["confidence"] = confidence
                    if confidence < 0.3:
                        stats['confidence_distribution']['low'] += 1
                    elif confidence < 0.7:
                        stats['confidence_distribution']['medium'] += 1
                    else:
                        stats['confidence_distribution']['high'] += 1

                ids_to_update.append(doc_id)
                metas_to_update.append(updated_meta)
                stats['updated'] += 1

            except Exception as e:
                print(f"  Error processing {doc_id}: {e}")
                stats['errors'] += 1

        # Apply updates
        if not dry_run and ids_to_update:
            try:
                collection.update(
                    ids=ids_to_update,
                    metadatas=metas_to_update
                )
            except Exception as e:
                print(f"  Batch update error: {e}")
                stats['errors'] += len(ids_to_update)
                stats['updated'] -= len(ids_to_update)

        stats['processed'] += len(batch_ids)
        offset += batch_size

        # Progress report
        pct = round(offset / total * 100, 1)
        print(f"  Progress: {min(offset, total)}/{total} ({pct}%) - Updated: {stats['updated']}")

    # Final report
    print("\n" + "=" * 60)
    print("REPAIR SUMMARY")
    print("=" * 60)
    print(f"\nTotal processed: {stats['processed']}")
    print(f"Updated: {stats['updated']}")
    print(f"Skipped (already complete): {stats['skipped']}")
    print(f"Errors: {stats['errors']}")

    print(f"\nProject Distribution (inferred):")
    for project, count in stats['project_distribution'].most_common(10):
        print(f"  - {project}: {count}")

    print(f"\nIntent Distribution (inferred):")
    for why, count in stats['why_distribution'].most_common(10):
        print(f"  - {why}: {count}")

    print(f"\nConfidence Distribution:")
    print(f"  - Low (<0.3): {stats['confidence_distribution']['low']}")
    print(f"  - Medium (0.3-0.7): {stats['confidence_distribution']['medium']}")
    print(f"  - High (>0.7): {stats['confidence_distribution']['high']}")

    if dry_run:
        print(f"\n[DRY RUN] No changes applied. Run with --execute to apply.")
    else:
        print(f"\n[COMPLETE] All changes applied.")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Repair Memory MCP metadata")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--execute", action="store_true", help="Apply changes")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for processing")

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Please specify --dry-run or --execute")
        sys.exit(1)

    dry_run = args.dry_run or not args.execute
    stats = repair_memories(dry_run=dry_run, batch_size=args.batch_size)

    # Save stats
    report_dir = Path(__file__).parent.parent / "reports"
    report_dir.mkdir(exist_ok=True)
    report_file = report_dir / f"repair-{'dryrun' if dry_run else 'executed'}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

    # Convert Counter to dict for JSON
    stats['project_distribution'] = dict(stats['project_distribution'])
    stats['why_distribution'] = dict(stats['why_distribution'])

    report_file.write_text(json.dumps(stats, indent=2))
    print(f"\nReport saved to: {report_file}")


if __name__ == "__main__":
    main()
