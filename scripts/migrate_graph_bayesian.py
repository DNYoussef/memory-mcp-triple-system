#!/usr/bin/env python3
"""
Migration Script: Backfill Graph with Bayesian Defaults

Phase 2: Edge Metadata Enhancement (Bead: EDG-005)
Phase 3: Node Metadata Enhancement (Bead: NOD-005)

This script backfills existing edges and nodes with default Bayesian attributes
per the GRAPH-BAYESIAN-REMEDIATION-PLAN.md

Edge Confidence Sources:
| Source | Initial Confidence | Notes |
|--------|-------------------|-------|
| Explicit user link | 0.9 | User explicitly created |
| Frontmatter hierarchy | 0.85 | Obsidian explicit hierarchy |
| Entity co-occurrence | 0.7 | Entities mentioned together |
| Semantic similarity >0.85 | 0.6 | Embedding-based |
| Semantic similarity 0.7-0.85 | 0.5 | Weaker embedding match |
| Inferred (2-hop) | 0.4 | Transitive inference |

Node Importance Formula:
  0.3 * connectivity + 0.3 * frequency + 0.2 * recency + 0.2 * explicit

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.services.graph_service import GraphService
from src.services.graph_edge_manager import (
    DEFAULT_EDGE_WEIGHT,
    DEFAULT_EDGE_CONFIDENCE,
    DEFAULT_EDGE_EVIDENCE,
    DEFAULT_EDGE_FREQUENCY
)
from src.services.graph_node_manager import (
    DEFAULT_NODE_STATES,
    DEFAULT_NODE_FREQUENCY,
    DEFAULT_NODE_IMPORTANCE,
    DEFAULT_NODE_DECAY_SCORE
)


# Confidence mapping by edge type
EDGE_TYPE_CONFIDENCE = {
    'explicit_link': 0.9,
    'frontmatter': 0.85,
    'mentions': 0.7,
    'references': 0.7,
    'co_occurrence': 0.7,
    'similar_to': 0.6,
    'related_to': 0.5,
    'inferred': 0.4,
    'implements': 0.8,
    'includes': 0.8,
    'fixed_by': 0.85,
    'resolves': 0.9,
    'uses_pattern': 0.75,
    'has_tier': 0.95,
    'requires': 0.85,
    'enables': 0.8,
}


def get_edge_confidence_by_type(edge_type: str) -> float:
    """Get initial confidence based on edge type."""
    return EDGE_TYPE_CONFIDENCE.get(edge_type, DEFAULT_EDGE_CONFIDENCE)


def audit_edges(graph_service: GraphService) -> List[Tuple[str, str, Dict]]:
    """
    Audit all edges and identify those missing Bayesian attributes.

    Returns list of (source, target, missing_attrs) tuples.
    """
    edges_to_migrate = []
    required_attrs = {'weight', 'confidence', 'evidence', 'frequency', 'evidence_chunks', 'last_accessed'}

    for source, target, data in graph_service.graph.edges(data=True):
        existing = set(data.keys())
        missing = required_attrs - existing

        if missing:
            edges_to_migrate.append((source, target, {'missing': list(missing), 'data': data}))

    return edges_to_migrate


def backfill_edge(
    graph_service: GraphService,
    source: str,
    target: str,
    edge_data: Dict[str, Any],
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Backfill a single edge with default Bayesian attributes.

    Returns dict with changes made.
    """
    changes = {}
    edge_type = edge_data.get('type', 'unknown')
    initial_confidence = get_edge_confidence_by_type(edge_type)

    # Define defaults
    defaults = {
        'weight': DEFAULT_EDGE_WEIGHT,
        'confidence': initial_confidence,
        'evidence': DEFAULT_EDGE_EVIDENCE,
        'frequency': DEFAULT_EDGE_FREQUENCY,
        'evidence_chunks': [],
        'last_accessed': datetime.utcnow().isoformat()
    }

    # Identify what needs to be added
    for attr, default_val in defaults.items():
        if attr not in edge_data:
            changes[attr] = default_val
            if not dry_run:
                edge_data[attr] = default_val

    return changes


def migrate_edges(
    data_dir: str,
    dry_run: bool = True,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Migrate all edges to include Bayesian attributes.

    Args:
        data_dir: Path to Memory MCP data directory
        dry_run: If True, only report changes without applying
        verbose: If True, print detailed output

    Returns:
        Migration report dict
    """
    logger.info(f"Starting edge migration (dry_run={dry_run})")

    # Initialize graph service
    graph_service = GraphService(data_dir=data_dir)
    graph_service.load_graph()

    # Audit current state
    edges_to_migrate = audit_edges(graph_service)

    report = {
        'total_edges': graph_service.get_edge_count(),
        'edges_needing_migration': len(edges_to_migrate),
        'dry_run': dry_run,
        'changes': []
    }

    if verbose:
        print(f"\n{'='*60}")
        print(f"EDGE MIGRATION {'(DRY RUN)' if dry_run else '(LIVE)'}")
        print(f"{'='*60}")
        print(f"Total edges: {report['total_edges']}")
        print(f"Edges needing migration: {report['edges_needing_migration']}")
        print()

    # Process each edge
    for source, target, info in edges_to_migrate:
        edge_data = graph_service.graph.get_edge_data(source, target)
        changes = backfill_edge(graph_service, source, target, edge_data, dry_run)

        if changes:
            change_record = {
                'edge': f"{source} -> {target}",
                'type': edge_data.get('type', 'unknown'),
                'added_attrs': list(changes.keys()),
                'values': changes
            }
            report['changes'].append(change_record)

            if verbose:
                print(f"  {source} -> {target}")
                print(f"    Type: {edge_data.get('type', 'unknown')}")
                print(f"    Adding: {list(changes.keys())}")
                print(f"    Confidence: {changes.get('confidence', 'N/A')}")
                print()

    # Save if not dry run
    if not dry_run and report['changes']:
        graph_service.save_graph()
        logger.info(f"Saved graph with {len(report['changes'])} migrated edges")
        if verbose:
            print(f"\n[OK] Saved {len(report['changes'])} migrated edges")
    elif dry_run:
        if verbose:
            print(f"\n[DRY RUN] Would migrate {len(report['changes'])} edges")

    return report


# ============================================================
# NODE MIGRATION (Phase 3: NOD-005)
# ============================================================

def audit_nodes(graph_service: GraphService) -> List[Tuple[str, Dict]]:
    """
    Audit all nodes and identify those missing Bayesian attributes.

    Returns list of (node_id, missing_attrs) tuples.
    """
    nodes_to_migrate = []
    required_attrs = {'states', 'frequency', 'importance', 'decay_score', 'created_at', 'last_accessed'}

    for node_id, data in graph_service.graph.nodes(data=True):
        existing = set(data.keys())
        missing = required_attrs - existing

        if missing:
            nodes_to_migrate.append((node_id, {'missing': list(missing), 'data': data}))

    return nodes_to_migrate


def backfill_node(
    graph_service: GraphService,
    node_id: str,
    node_data: Dict[str, Any],
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Backfill a single node with default Bayesian attributes.

    Returns dict with changes made.
    """
    changes = {}
    now = datetime.utcnow().isoformat()

    # Define defaults
    defaults = {
        'states': DEFAULT_NODE_STATES.copy(),
        'frequency': DEFAULT_NODE_FREQUENCY,
        'importance': DEFAULT_NODE_IMPORTANCE,
        'decay_score': DEFAULT_NODE_DECAY_SCORE,
        'created_at': now,
        'last_accessed': now
    }

    # Identify what needs to be added
    for attr, default_val in defaults.items():
        if attr not in node_data:
            changes[attr] = default_val
            if not dry_run:
                node_data[attr] = default_val

    return changes


def migrate_nodes(
    graph_service: GraphService,
    dry_run: bool = True,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Migrate all nodes to include Bayesian attributes.

    Args:
        graph_service: GraphService instance (already loaded)
        dry_run: If True, only report changes without applying
        verbose: If True, print detailed output

    Returns:
        Migration report dict
    """
    logger.info(f"Starting node migration (dry_run={dry_run})")

    # Audit current state
    nodes_to_migrate = audit_nodes(graph_service)

    report = {
        'total_nodes': graph_service.get_node_count(),
        'nodes_needing_migration': len(nodes_to_migrate),
        'dry_run': dry_run,
        'changes': []
    }

    if verbose:
        print(f"\n{'='*60}")
        print(f"NODE MIGRATION {'(DRY RUN)' if dry_run else '(LIVE)'}")
        print(f"{'='*60}")
        print(f"Total nodes: {report['total_nodes']}")
        print(f"Nodes needing migration: {report['nodes_needing_migration']}")
        print()

    # Process each node
    for node_id, info in nodes_to_migrate:
        node_data = graph_service.graph.nodes[node_id]
        changes = backfill_node(graph_service, node_id, node_data, dry_run)

        if changes:
            change_record = {
                'node': node_id,
                'type': node_data.get('type', 'unknown'),
                'added_attrs': list(changes.keys()),
                'values': {k: v for k, v in changes.items() if k not in ['states']}
            }
            report['changes'].append(change_record)

            if verbose:
                print(f"  {node_id}")
                print(f"    Type: {node_data.get('type', 'unknown')}")
                print(f"    Adding: {list(changes.keys())}")
                print()

    if dry_run:
        if verbose:
            print(f"\n[DRY RUN] Would migrate {len(report['changes'])} nodes")

    return report


def migrate_all(
    data_dir: str,
    dry_run: bool = True,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Migrate both edges and nodes to include Bayesian attributes.

    Args:
        data_dir: Path to Memory MCP data directory
        dry_run: If True, only report changes without applying
        verbose: If True, print detailed output

    Returns:
        Combined migration report dict
    """
    logger.info(f"Starting full graph migration (dry_run={dry_run})")

    # Initialize graph service
    graph_service = GraphService(data_dir=data_dir)
    graph_service.load_graph()

    # Migrate edges
    edges_to_migrate = audit_edges(graph_service)
    edge_changes = []

    if verbose:
        print(f"\n{'='*60}")
        print(f"EDGE MIGRATION {'(DRY RUN)' if dry_run else '(LIVE)'}")
        print(f"{'='*60}")
        print(f"Total edges: {graph_service.get_edge_count()}")
        print(f"Edges needing migration: {len(edges_to_migrate)}")
        print()

    for source, target, info in edges_to_migrate:
        edge_data = graph_service.graph.get_edge_data(source, target)
        changes = backfill_edge(graph_service, source, target, edge_data, dry_run)
        if changes:
            edge_changes.append({
                'edge': f"{source} -> {target}",
                'type': edge_data.get('type', 'unknown'),
                'added_attrs': list(changes.keys())
            })
            if verbose:
                print(f"  {source} -> {target}: {list(changes.keys())}")

    # Migrate nodes
    node_report = migrate_nodes(graph_service, dry_run, verbose)

    # Save if not dry run
    if not dry_run and (edge_changes or node_report['changes']):
        graph_service.save_graph()
        logger.info(f"Saved graph with {len(edge_changes)} edges and {len(node_report['changes'])} nodes migrated")
        if verbose:
            print(f"\n[OK] Saved {len(edge_changes)} edges and {len(node_report['changes'])} nodes")

    return {
        'edges': {
            'total': graph_service.get_edge_count(),
            'migrated': len(edge_changes),
            'changes': edge_changes
        },
        'nodes': {
            'total': node_report['total_nodes'],
            'migrated': len(node_report['changes']),
            'changes': node_report['changes']
        },
        'dry_run': dry_run
    }


def main():
    """Main entry point for migration script."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Migrate graph edges and nodes to include Bayesian attributes'
    )
    parser.add_argument(
        '--data-dir',
        default=r'C:\Users\17175\.claude\memory-mcp-data',
        help='Path to Memory MCP data directory'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Only report changes without applying (default: True)'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Actually apply the migration (overrides --dry-run)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress verbose output'
    )
    parser.add_argument(
        '--edges-only',
        action='store_true',
        help='Only migrate edges (Phase 2)'
    )
    parser.add_argument(
        '--nodes-only',
        action='store_true',
        help='Only migrate nodes (Phase 3)'
    )

    args = parser.parse_args()

    dry_run = not args.apply
    verbose = not args.quiet

    # Determine migration scope
    if args.edges_only:
        report = migrate_edges(
            data_dir=args.data_dir,
            dry_run=dry_run,
            verbose=verbose
        )
        # Print summary
        print(f"\n{'='*60}")
        print("MIGRATION SUMMARY (EDGES ONLY)")
        print(f"{'='*60}")
        print(f"Total edges: {report['total_edges']}")
        print(f"Edges migrated: {len(report['changes'])}")
        print(f"Mode: {'DRY RUN' if report['dry_run'] else 'APPLIED'}")
        return 0 if not report['changes'] or not dry_run else 1

    elif args.nodes_only:
        graph_service = GraphService(data_dir=args.data_dir)
        graph_service.load_graph()
        report = migrate_nodes(graph_service, dry_run, verbose)
        if not dry_run and report['changes']:
            graph_service.save_graph()
            print(f"\n[OK] Saved {len(report['changes'])} nodes")
        # Print summary
        print(f"\n{'='*60}")
        print("MIGRATION SUMMARY (NODES ONLY)")
        print(f"{'='*60}")
        print(f"Total nodes: {report['total_nodes']}")
        print(f"Nodes migrated: {len(report['changes'])}")
        print(f"Mode: {'DRY RUN' if report['dry_run'] else 'APPLIED'}")
        return 0 if not report['changes'] or not dry_run else 1

    else:
        # Default: migrate both edges and nodes
        report = migrate_all(
            data_dir=args.data_dir,
            dry_run=dry_run,
            verbose=verbose
        )
        # Print summary
        print(f"\n{'='*60}")
        print("MIGRATION SUMMARY (FULL)")
        print(f"{'='*60}")
        print(f"Total edges: {report['edges']['total']}")
        print(f"Edges migrated: {report['edges']['migrated']}")
        print(f"Total nodes: {report['nodes']['total']}")
        print(f"Nodes migrated: {report['nodes']['migrated']}")
        print(f"Mode: {'DRY RUN' if report['dry_run'] else 'APPLIED'}")
        total_changes = report['edges']['migrated'] + report['nodes']['migrated']
        return 0 if not total_changes or not dry_run else 1


if __name__ == '__main__':
    sys.exit(main())
