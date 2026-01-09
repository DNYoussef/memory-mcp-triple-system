#!/usr/bin/env python3
"""
Memory MCP Population Script

Phase 4 of Ecosystem Management: Insert validated triple-tier entities.

Reads entities from phase3-entities.json and populates:
1. Vector RAG tier (ChromaDB) - text + metadata
2. HippoRAG tier (NetworkX) - entity nodes + relationship edges
3. Bayesian tier - confidence scores in metadata

Usage:
    python populate_memory_mcp.py --dry-run     # Preview insertions
    python populate_memory_mcp.py --execute     # Apply insertions
"""

import sys
import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple
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


def load_entities() -> Dict[str, Any]:
    """Load entities from phase3-entities.json."""
    entities_path = Path(__file__).parent.parent / "data" / "phase3-entities.json"
    with open(entities_path) as f:
        return json.load(f)


def generate_entity_id(path: str) -> str:
    """Generate deterministic UUID-like ID from path."""
    # Use hash to generate consistent IDs for same paths
    h = hashlib.sha256(path.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def validate_entity(entity: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate entity for triple-tier optimization.
    Returns (is_valid, list_of_issues).
    """
    issues = []

    # Required fields
    if "path" not in entity:
        issues.append("Missing required field: path")

    if "content" not in entity:
        issues.append("Missing required field: content")
    elif "text" not in entity.get("content", {}):
        issues.append("Missing content.text")

    # Content length for Vector RAG (should be substantial)
    text = entity.get("content", {}).get("text", "")
    if len(text) < 100:
        issues.append(f"Content too short ({len(text)} chars) for Vector RAG")

    # Relationships for HippoRAG
    relationships = entity.get("relationships", {})
    links = relationships.get("links_to", [])
    if len(links) == 0:
        issues.append("No links_to relationships for HippoRAG tier")

    # Confidence for Bayesian tier
    probabilistic = entity.get("probabilistic", {})
    confidence = probabilistic.get("confidence")
    if confidence is None:
        issues.append("Missing confidence score for Bayesian tier")
    elif not (0.0 <= confidence <= 1.0):
        issues.append(f"Invalid confidence score: {confidence}")

    # Tags for metadata
    tags = relationships.get("tags", [])
    if len(tags) == 0:
        issues.append("No tags for metadata filtering")

    return len(issues) == 0, issues


def transform_to_memory_format(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Transform entity to Memory MCP storage format."""
    path = entity["path"]
    content = entity["content"]
    relationships = entity.get("relationships", {})
    probabilistic = entity.get("probabilistic", {})
    retention = entity.get("retention", {})

    # Extract project from path
    parts = path.split("/")
    project = "general"
    if len(parts) >= 2:
        if parts[0] == "projects":
            project = parts[1]
        elif parts[0] == "systems":
            project = parts[1]
        elif parts[0] == "streams":
            project = parts[1]
        elif parts[0] == "infrastructure":
            project = parts[1]

    # Determine intent from content type
    content_type = content.get("type", "general")
    intent_map = {
        "project_overview": "documentation",
        "architecture": "documentation",
        "system_overview": "documentation",
        "stream_overview": "documentation",
        "infrastructure_overview": "documentation",
        "pattern": "implementation",
        "decision": "planning",
        "bugfix": "bugfix",
        "test": "testing"
    }
    intent = intent_map.get(content_type, "documentation")

    # Build text with wiki links embedded for HippoRAG entity extraction
    wiki_links = relationships.get("wiki_links", [])
    text = content["text"]
    if wiki_links:
        text += f"\n\nRelated: {', '.join(wiki_links)}"

    # Build metadata
    metadata = {
        # WHO/WHEN/PROJECT/WHY Protocol
        "WHO": "ecosystem-population:1.0",
        "WHEN": datetime.now().isoformat(),
        "PROJECT": project,
        "WHY": intent,

        # Bayesian tier confidence
        "confidence": probabilistic.get("confidence", 0.5),

        # Additional metadata
        "path": path,
        "type": content_type,
        "summary": content.get("summary", ""),
        "source_reliability": probabilistic.get("source_reliability", "medium"),
        "last_verified": probabilistic.get("last_verified", datetime.now().strftime("%Y-%m-%d")),

        # Retention layer
        "retention_layer": retention.get("layer", "long"),
        "reinforced": retention.get("reinforced", False),

        # Tags as comma-separated string (ChromaDB limitation)
        "tags": ",".join(relationships.get("tags", []))
    }

    return {
        "id": generate_entity_id(path),
        "text": text,
        "metadata": metadata,
        "relationships": relationships.get("links_to", [])
    }


def check_existing(collection, entity_id: str) -> bool:
    """Check if entity already exists in collection."""
    try:
        result = collection.get(ids=[entity_id])
        return len(result.get("ids", [])) > 0
    except Exception:
        return False


def populate_memories(dry_run: bool = True) -> Dict[str, Any]:
    """Populate Memory MCP with validated entities."""
    print("=" * 60)
    print(f"Memory MCP Population {'(DRY RUN)' if dry_run else '(EXECUTING)'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    # Load data
    entities_data = load_entities()
    entities = entities_data.get("entities", [])
    print(f"\nLoaded {len(entities)} entities from phase3-entities.json")

    config = load_config()
    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])
    collection_name = config['storage']['vector_db']['collection_name']

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    collection = client.get_collection(name=collection_name)

    stats = {
        'total': len(entities),
        'valid': 0,
        'invalid': 0,
        'inserted': 0,
        'skipped_existing': 0,
        'errors': 0,
        'validation_issues': [],
        'project_distribution': Counter(),
        'type_distribution': Counter(),
        'confidence_distribution': {
            'low': 0,      # < 0.7
            'medium': 0,   # 0.7-0.85
            'high': 0      # > 0.85
        }
    }

    # Phase 1: Validation
    print("\n--- Phase 1: Validation ---")
    valid_entities = []

    for entity in entities:
        is_valid, issues = validate_entity(entity)

        if is_valid:
            stats['valid'] += 1
            valid_entities.append(entity)
        else:
            stats['invalid'] += 1
            stats['validation_issues'].append({
                'path': entity.get('path', 'unknown'),
                'issues': issues
            })
            print(f"  INVALID: {entity.get('path', 'unknown')}")
            for issue in issues:
                print(f"    - {issue}")

    print(f"\nValidation: {stats['valid']}/{stats['total']} valid")

    # Phase 2: Transform and Insert
    print("\n--- Phase 2: Transform & Insert ---")

    ids_to_insert = []
    texts_to_insert = []
    metas_to_insert = []
    relationships_to_add = []

    for entity in valid_entities:
        memory = transform_to_memory_format(entity)

        # Check if exists
        if check_existing(collection, memory['id']):
            stats['skipped_existing'] += 1
            print(f"  SKIP (exists): {entity['path']}")
            continue

        # Track stats
        stats['project_distribution'][memory['metadata']['PROJECT']] += 1
        stats['type_distribution'][memory['metadata']['type']] += 1

        conf = memory['metadata']['confidence']
        if conf < 0.7:
            stats['confidence_distribution']['low'] += 1
        elif conf < 0.85:
            stats['confidence_distribution']['medium'] += 1
        else:
            stats['confidence_distribution']['high'] += 1

        # Queue for batch insert
        ids_to_insert.append(memory['id'])
        texts_to_insert.append(memory['text'])
        metas_to_insert.append(memory['metadata'])
        relationships_to_add.append({
            'id': memory['id'],
            'path': entity['path'],
            'links': memory['relationships']
        })

        print(f"  READY: {entity['path']} (conf: {conf:.2f})")

    # Phase 3: Execute insertions
    print("\n--- Phase 3: Execute ---")

    if dry_run:
        print(f"\n[DRY RUN] Would insert {len(ids_to_insert)} memories")
        stats['inserted'] = 0  # Nothing actually inserted
    else:
        if ids_to_insert:
            try:
                # Batch insert to ChromaDB
                collection.add(
                    ids=ids_to_insert,
                    documents=texts_to_insert,
                    metadatas=metas_to_insert
                )
                stats['inserted'] = len(ids_to_insert)
                print(f"\nInserted {stats['inserted']} memories to Vector RAG tier")

                # Note: HippoRAG graph edges would be added by entity extraction
                # during the normal memory store flow. For pre-populated entities,
                # we log the relationship data for manual graph enhancement.

                relationships_file = Path(__file__).parent.parent / "data" / "pending-relationships.json"
                relationships_file.write_text(json.dumps(relationships_to_add, indent=2))
                print(f"Saved {len(relationships_to_add)} relationships to {relationships_file}")

            except Exception as e:
                print(f"ERROR inserting batch: {e}")
                stats['errors'] = len(ids_to_insert)

    # Summary Report
    print("\n" + "=" * 60)
    print("POPULATION SUMMARY")
    print("=" * 60)
    print(f"\nTotal entities: {stats['total']}")
    print(f"Valid: {stats['valid']}")
    print(f"Invalid: {stats['invalid']}")
    print(f"Inserted: {stats['inserted']}")
    print(f"Skipped (existing): {stats['skipped_existing']}")
    print(f"Errors: {stats['errors']}")

    print(f"\nProject Distribution:")
    for project, count in stats['project_distribution'].most_common(15):
        print(f"  - {project}: {count}")

    print(f"\nType Distribution:")
    for type_name, count in stats['type_distribution'].most_common():
        print(f"  - {type_name}: {count}")

    print(f"\nConfidence Distribution:")
    print(f"  - Low (<0.7): {stats['confidence_distribution']['low']}")
    print(f"  - Medium (0.7-0.85): {stats['confidence_distribution']['medium']}")
    print(f"  - High (>0.85): {stats['confidence_distribution']['high']}")

    if stats['validation_issues']:
        print(f"\nValidation Issues ({len(stats['validation_issues'])}):")
        for issue in stats['validation_issues'][:5]:
            print(f"  - {issue['path']}: {', '.join(issue['issues'][:2])}")
        if len(stats['validation_issues']) > 5:
            print(f"  ... and {len(stats['validation_issues']) - 5} more")

    if dry_run:
        print(f"\n[DRY RUN] No changes applied. Run with --execute to apply.")
    else:
        print(f"\n[COMPLETE] Population finished.")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Populate Memory MCP with validated entities")
    parser.add_argument("--dry-run", action="store_true", help="Preview insertions without applying")
    parser.add_argument("--execute", action="store_true", help="Apply insertions")

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Please specify --dry-run or --execute")
        sys.exit(1)

    dry_run = args.dry_run or not args.execute
    stats = populate_memories(dry_run=dry_run)

    # Save stats
    report_dir = Path(__file__).parent.parent / "reports"
    report_dir.mkdir(exist_ok=True)
    report_file = report_dir / f"population-{'dryrun' if dry_run else 'executed'}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

    # Convert Counter to dict for JSON
    stats['project_distribution'] = dict(stats['project_distribution'])
    stats['type_distribution'] = dict(stats['type_distribution'])

    report_file.write_text(json.dumps(stats, indent=2))
    print(f"\nReport saved to: {report_file}")


if __name__ == "__main__":
    main()
