#!/usr/bin/env python3
"""
Reflect to Memory Bridge Script

Stores session learnings from the /reflect skill to Memory MCP.
Part of Loop 1.5 (Session Reflection) -> Loop 3 (Meta-Loop) pipeline.

Usage:
    python reflect_to_memory.py --session-id SESSION_123 --project my-project
    python reflect_to_memory.py --test  # Store test learning
    python reflect_to_memory.py --from-file learnings.json

WHO/WHEN/PROJECT/WHY Tagging:
    - WHO: reflect-skill:{session_id}
    - WHEN: ISO8601 timestamp
    - PROJECT: From env MEMORY_MCP_PROJECT or --project
    - WHY: session-learning
"""

import sys
import json
import argparse
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import hashlib

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
    """Get ChromaDB collection for memory storage."""
    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])
    collection_name = config['storage']['vector_db']['collection_name']

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    return client.get_collection(name=collection_name)


def store_single_learning(
    collection,
    learning: Dict[str, Any],
    session_id: str,
    project: str
) -> str:
    """
    Store a single learning entry to Memory MCP.

    Args:
        collection: ChromaDB collection
        learning: Learning dict with content, confidence, signal_type, skill
        session_id: Session identifier
        project: Project name

    Returns:
        Document ID of stored learning
    """
    now = datetime.utcnow()

    # Generate unique ID from content + session + timestamp
    content = learning.get('content', '')
    id_source = f"{session_id}:{content}:{now.isoformat()}"
    doc_id = hashlib.md5(id_source.encode()).hexdigest()[:16]

    # Build text content
    text = f"""Session Learning [{learning.get('signal_type', 'observation')}]

Skill: {learning.get('skill', 'unknown')}
Confidence: {learning.get('confidence', 0.55)}

Learning:
{content}

Context:
{learning.get('context', 'No additional context')}
"""

    # Build metadata with WHO/WHEN/PROJECT/WHY protocol
    metadata = {
        # WHO
        'agent': f"reflect-skill:{session_id}",
        'agent_category': 'tooling',

        # WHEN
        'timestamp': now.isoformat() + 'Z',
        'timestamp_unix': int(now.timestamp()),

        # PROJECT
        'project': project,

        # WHY
        'intent': 'session-learning',

        # Extended metadata for learnings
        'x-skill': learning.get('skill', 'unknown'),
        'x-confidence': learning.get('confidence', 0.55),
        'x-signal-type': learning.get('signal_type', 'observation'),
        'x-session-id': session_id,
        'x-ground': learning.get('ground', 'session-observation'),

        # Tagging protocol version
        '_tagging_version': '1.0.0',
        '_tagging_protocol': 'reflect-to-memory'
    }

    # Use sentence-transformers for embedding if available
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        embedding = model.encode([text])[0].tolist()

        collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata]
        )
    except ImportError:
        # Fallback: Let ChromaDB generate embeddings
        collection.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata]
        )

    return doc_id


def store_session_learnings(
    learnings: List[Dict[str, Any]],
    session_id: str,
    project: str,
    skills_updated: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Store all session learnings to Memory MCP.

    Args:
        learnings: List of learning dicts
        session_id: Session identifier
        project: Project name
        skills_updated: List of skills that were updated

    Returns:
        Summary of storage operation
    """
    config = load_config()
    collection = get_collection(config)

    stored_ids = []
    errors = []

    for learning in learnings:
        try:
            doc_id = store_single_learning(
                collection,
                learning,
                session_id,
                project
            )
            stored_ids.append(doc_id)
            print(f"  Stored: {doc_id} [{learning.get('signal_type', 'observation')}]")
        except Exception as e:
            errors.append({
                'learning': learning.get('content', '')[:50],
                'error': str(e)
            })
            print(f"  Error: {e}")

    # Store summary entry
    if stored_ids:
        summary_learning = {
            'content': f"Session {session_id} reflection complete. Stored {len(stored_ids)} learnings.",
            'skill': 'reflect',
            'confidence': 0.95,
            'signal_type': 'session-summary',
            'context': f"Skills updated: {skills_updated or 'none'}"
        }
        try:
            summary_id = store_single_learning(
                collection,
                summary_learning,
                session_id,
                project
            )
            stored_ids.append(summary_id)
        except Exception as e:
            print(f"  Warning: Could not store summary: {e}")

    return {
        'session_id': session_id,
        'project': project,
        'learnings_stored': len(stored_ids),
        'stored_ids': stored_ids,
        'errors': errors,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }


def parse_learnings_from_file(file_path: str) -> List[Dict[str, Any]]:
    """Parse learnings from a JSON file."""
    with open(file_path) as f:
        data = json.load(f)

    # Handle different formats
    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and 'learnings' in data:
        return data['learnings']
    elif isinstance(data, dict) and 'signals' in data:
        return data['signals']
    else:
        return [data]


def create_test_learnings() -> List[Dict[str, Any]]:
    """Create test learnings for verification."""
    return [
        {
            'content': 'ALWAYS check for null pointer exceptions before accessing object properties',
            'skill': 'debug',
            'confidence': 0.90,
            'signal_type': 'correction',
            'ground': 'user-correction:2026-01-09',
            'context': 'User corrected approach during debugging session'
        },
        {
            'content': 'Use structured logging instead of console.log in production code',
            'skill': 'code',
            'confidence': 0.90,
            'signal_type': 'explicit_rule',
            'ground': 'user-rule:2026-01-09',
            'context': 'User explicitly stated logging preference'
        },
        {
            'content': 'Prefer early returns over nested conditionals for readability',
            'skill': 'code-review',
            'confidence': 0.75,
            'signal_type': 'approval',
            'ground': 'approval-pattern:2026-01-09',
            'context': 'User approved refactoring suggestion'
        }
    ]


def main():
    parser = argparse.ArgumentParser(
        description='Store session learnings to Memory MCP'
    )
    parser.add_argument(
        '--session-id',
        default=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        help='Session identifier'
    )
    parser.add_argument(
        '--project',
        default=os.environ.get('MEMORY_MCP_PROJECT', 'general'),
        help='Project name'
    )
    parser.add_argument(
        '--from-file',
        help='Load learnings from JSON file'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Store test learnings for verification'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without storing'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Reflect to Memory Bridge")
    print("=" * 60)
    print(f"Session ID: {args.session_id}")
    print(f"Project: {args.project}")
    print()

    # Get learnings from source
    if args.test:
        print("Using test learnings...")
        learnings = create_test_learnings()
    elif args.from_file:
        print(f"Loading from file: {args.from_file}")
        learnings = parse_learnings_from_file(args.from_file)
    else:
        # Check for learnings from stdin or recent reflect output
        print("No learnings source specified. Use --test or --from-file")
        print("Or pipe JSON learnings to stdin")

        # Try reading from stdin if not a TTY
        if not sys.stdin.isatty():
            try:
                data = json.load(sys.stdin)
                learnings = data if isinstance(data, list) else [data]
            except:
                print("No valid JSON on stdin")
                return 1
        else:
            return 1

    print(f"\nLearnings to store: {len(learnings)}")
    print()

    if args.dry_run:
        print("[DRY RUN] Would store:")
        for i, l in enumerate(learnings, 1):
            print(f"  {i}. [{l.get('signal_type', 'observation')}] {l.get('content', '')[:60]}...")
        return 0

    # Store learnings
    result = store_session_learnings(
        learnings=learnings,
        session_id=args.session_id,
        project=args.project
    )

    print()
    print("=" * 60)
    print("Storage Complete")
    print("=" * 60)
    print(f"Learnings stored: {result['learnings_stored']}")
    print(f"Errors: {len(result['errors'])}")

    if result['errors']:
        print("\nErrors:")
        for err in result['errors']:
            print(f"  - {err['learning']}: {err['error']}")

    # Save report
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_file = reports_dir / f"reflect-{args.session_id}.json"
    report_file.write_text(json.dumps(result, indent=2))
    print(f"\nReport saved: {report_file}")

    return 0 if not result['errors'] else 1


if __name__ == "__main__":
    sys.exit(main())
