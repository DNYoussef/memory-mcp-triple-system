#!/usr/bin/env python3
"""
Memory MCP Audit Script

Audits all three retrieval tiers:
- Vector RAG (ChromaDB): Content quality, embedding presence
- HippoRAG (Graph): Connectivity, orphan nodes, dead links
- Bayesian: Confidence distribution

Outputs cleanup recommendations.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, Any, List, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import chromadb
from chromadb.config import Settings
import networkx as nx


def load_config():
    """Load configuration."""
    import yaml
    config_path = Path(__file__).parent.parent / "config" / "memory-mcp.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def audit_vector_rag(config: dict) -> Dict[str, Any]:
    """Audit ChromaDB vector store."""
    print("\n[1/3] Auditing Vector RAG (ChromaDB)...")

    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])
    collection_name = config['storage']['vector_db']['collection_name']

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )

    try:
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        return {"error": str(e), "total": 0}

    # Get all documents with metadata
    total = collection.count()
    print(f"  Total memories: {total}")

    # Sample analysis (can't load all 21k at once)
    sample_size = min(1000, total)
    results = collection.get(
        limit=sample_size,
        include=["documents", "metadatas"]
    )

    # Analyze content quality
    content_lengths = []
    empty_content = []
    short_content = []  # < 50 chars
    metadata_issues = []
    project_distribution = Counter()
    who_distribution = Counter()
    why_distribution = Counter()

    for i, doc in enumerate(results.get("documents", [])):
        doc_id = results["ids"][i] if results.get("ids") else f"doc_{i}"
        metadata = results["metadatas"][i] if results.get("metadatas") else {}

        # Content length analysis
        length = len(doc) if doc else 0
        content_lengths.append(length)

        if length == 0:
            empty_content.append(doc_id)
        elif length < 50:
            short_content.append(doc_id)

        # Metadata completeness
        missing_fields = []
        for field in ["WHO", "WHEN", "PROJECT", "WHY"]:
            if field not in metadata:
                missing_fields.append(field)
        if missing_fields:
            metadata_issues.append({
                "id": doc_id,
                "missing": missing_fields
            })

        # Distribution analysis
        project_distribution[metadata.get("PROJECT", "unknown")] += 1
        who_distribution[metadata.get("WHO", "unknown")] += 1
        why_distribution[metadata.get("WHY", "unknown")] += 1

    avg_length = sum(content_lengths) / len(content_lengths) if content_lengths else 0

    return {
        "total": total,
        "sample_size": sample_size,
        "content_analysis": {
            "avg_length": round(avg_length, 2),
            "min_length": min(content_lengths) if content_lengths else 0,
            "max_length": max(content_lengths) if content_lengths else 0,
            "empty_count": len(empty_content),
            "short_count": len(short_content),
            "empty_ids": empty_content[:10],  # First 10
            "short_ids": short_content[:10]
        },
        "metadata_analysis": {
            "incomplete_count": len(metadata_issues),
            "issues": metadata_issues[:10]
        },
        "distributions": {
            "top_projects": dict(project_distribution.most_common(10)),
            "top_sources": dict(who_distribution.most_common(10)),
            "top_intents": dict(why_distribution.most_common(10))
        }
    }


def audit_hipporag(config: dict) -> Dict[str, Any]:
    """Audit NetworkX graph for HippoRAG."""
    print("\n[2/3] Auditing HippoRAG (Graph)...")

    graph_file = Path(config['storage']['data_dir']) / "graph.json"

    if not graph_file.exists():
        return {"error": "graph.json not found", "nodes": 0, "edges": 0}

    # Load graph
    with open(graph_file) as f:
        graph_data = json.load(f)

    G = nx.node_link_graph(graph_data)

    total_nodes = G.number_of_nodes()
    total_edges = G.number_of_edges()
    print(f"  Nodes: {total_nodes}, Edges: {total_edges}")

    # Node type distribution
    node_types = Counter()
    for node, data in G.nodes(data=True):
        node_types[data.get("type", "unknown")] += 1

    # Find orphan nodes (no edges)
    orphan_nodes = [n for n in G.nodes() if G.degree(n) == 0]

    # Find weakly connected nodes (degree 1)
    weak_nodes = [n for n in G.nodes() if G.degree(n) == 1]

    # Connectivity analysis
    if G.is_directed():
        # For directed graphs, check weak connectivity
        components = list(nx.weakly_connected_components(G))
    else:
        components = list(nx.connected_components(G))

    component_sizes = [len(c) for c in components]
    largest_component = max(component_sizes) if component_sizes else 0

    # Degree distribution
    degrees = [d for n, d in G.degree()]
    avg_degree = sum(degrees) / len(degrees) if degrees else 0

    # Find hub nodes (high degree)
    hub_threshold = avg_degree * 3
    hub_nodes = [(n, d) for n, d in G.degree() if d > hub_threshold]
    hub_nodes.sort(key=lambda x: x[1], reverse=True)

    # Dead link analysis (edges to non-existent nodes)
    # In a properly built graph this should be 0
    dead_links = []
    for source, target in G.edges():
        if source not in G.nodes() or target not in G.nodes():
            dead_links.append((source, target))

    return {
        "nodes": total_nodes,
        "edges": total_edges,
        "node_types": dict(node_types),
        "connectivity": {
            "components": len(components),
            "largest_component": largest_component,
            "largest_component_pct": round(largest_component / total_nodes * 100, 2) if total_nodes else 0,
            "avg_degree": round(avg_degree, 2)
        },
        "issues": {
            "orphan_nodes": len(orphan_nodes),
            "orphan_sample": orphan_nodes[:10],
            "weak_nodes": len(weak_nodes),
            "dead_links": len(dead_links)
        },
        "hubs": {
            "count": len(hub_nodes),
            "top_10": [(str(n)[:50], d) for n, d in hub_nodes[:10]]
        }
    }


def audit_bayesian(config: dict) -> Dict[str, Any]:
    """Audit Bayesian tier (confidence/probability analysis)."""
    print("\n[3/3] Auditing Bayesian Tier (Confidence)...")

    chroma_dir = Path(config['storage']['vector_db']['persist_directory'])
    collection_name = config['storage']['vector_db']['collection_name']

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False)
    )

    try:
        collection = client.get_collection(name=collection_name)
    except Exception:
        return {"error": "Collection not found"}

    # Sample for confidence analysis
    sample_size = min(1000, collection.count())
    results = collection.get(
        limit=sample_size,
        include=["metadatas"]
    )

    # Analyze confidence scores
    confidence_scores = []
    no_confidence = 0
    low_confidence = []  # < 0.3

    for i, metadata in enumerate(results.get("metadatas", [])):
        doc_id = results["ids"][i] if results.get("ids") else f"doc_{i}"
        confidence = metadata.get("confidence")

        if confidence is None:
            no_confidence += 1
        else:
            try:
                conf_val = float(confidence)
                confidence_scores.append(conf_val)
                if conf_val < 0.3:
                    low_confidence.append({
                        "id": doc_id,
                        "confidence": conf_val
                    })
            except (ValueError, TypeError):
                no_confidence += 1

    if confidence_scores:
        avg_conf = sum(confidence_scores) / len(confidence_scores)
        min_conf = min(confidence_scores)
        max_conf = max(confidence_scores)
    else:
        avg_conf = min_conf = max_conf = 0

    # Confidence distribution buckets
    buckets = {
        "0.0-0.3 (low)": 0,
        "0.3-0.5 (medium-low)": 0,
        "0.5-0.7 (medium)": 0,
        "0.7-0.9 (high)": 0,
        "0.9-1.0 (very high)": 0
    }

    for score in confidence_scores:
        if score < 0.3:
            buckets["0.0-0.3 (low)"] += 1
        elif score < 0.5:
            buckets["0.3-0.5 (medium-low)"] += 1
        elif score < 0.7:
            buckets["0.5-0.7 (medium)"] += 1
        elif score < 0.9:
            buckets["0.7-0.9 (high)"] += 1
        else:
            buckets["0.9-1.0 (very high)"] += 1

    return {
        "sample_size": sample_size,
        "confidence_analysis": {
            "has_confidence": len(confidence_scores),
            "no_confidence": no_confidence,
            "avg_confidence": round(avg_conf, 3),
            "min_confidence": round(min_conf, 3),
            "max_confidence": round(max_conf, 3)
        },
        "distribution": buckets,
        "low_confidence_items": low_confidence[:10]
    }


def generate_cleanup_recommendations(
    vector_audit: dict,
    graph_audit: dict,
    bayesian_audit: dict
) -> Dict[str, Any]:
    """Generate cleanup recommendations based on audit results."""
    print("\n[4/4] Generating Cleanup Recommendations...")

    recommendations = {
        "delete": [],
        "reinforce": [],
        "repair": [],
        "warnings": []
    }

    # Vector RAG recommendations
    if vector_audit.get("content_analysis", {}).get("empty_count", 0) > 0:
        recommendations["delete"].append({
            "category": "empty_content",
            "count": vector_audit["content_analysis"]["empty_count"],
            "reason": "Memories with no content provide no value",
            "sample_ids": vector_audit["content_analysis"].get("empty_ids", [])
        })

    if vector_audit.get("content_analysis", {}).get("short_count", 0) > 0:
        short_count = vector_audit["content_analysis"]["short_count"]
        if short_count > 100:
            recommendations["warnings"].append({
                "category": "short_content",
                "count": short_count,
                "reason": "Many memories under 50 chars may have poor embeddings",
                "action": "Review and consider deletion"
            })

    # Graph recommendations
    if graph_audit.get("issues", {}).get("orphan_nodes", 0) > 0:
        orphan_count = graph_audit["issues"]["orphan_nodes"]
        recommendations["repair"].append({
            "category": "orphan_nodes",
            "count": orphan_count,
            "reason": "Nodes with no edges won't be found by HippoRAG multi-hop",
            "action": "Re-run entity extraction or delete if content is empty"
        })

    if graph_audit.get("connectivity", {}).get("components", 0) > 1:
        comp_count = graph_audit["connectivity"]["components"]
        if comp_count > 10:
            recommendations["warnings"].append({
                "category": "fragmented_graph",
                "count": comp_count,
                "reason": "Graph has many disconnected components",
                "action": "Add cross-references to improve connectivity"
            })

    # Bayesian recommendations
    if bayesian_audit.get("confidence_analysis", {}).get("no_confidence", 0) > 0:
        no_conf = bayesian_audit["confidence_analysis"]["no_confidence"]
        recommendations["repair"].append({
            "category": "missing_confidence",
            "count": no_conf,
            "reason": "Memories without confidence scores won't work in Bayesian tier",
            "action": "Assign default confidence (0.5) or compute from source"
        })

    low_conf = len(bayesian_audit.get("low_confidence_items", []))
    if low_conf > 0:
        recommendations["warnings"].append({
            "category": "low_confidence",
            "count": low_conf,
            "reason": "Low confidence items may be filtered out in queries",
            "action": "Review and verify or delete"
        })

    # Calculate totals
    total_delete = sum(r.get("count", 0) for r in recommendations["delete"])
    total_repair = sum(r.get("count", 0) for r in recommendations["repair"])
    total_warnings = len(recommendations["warnings"])

    recommendations["summary"] = {
        "items_to_delete": total_delete,
        "items_to_repair": total_repair,
        "warnings": total_warnings,
        "health_score": calculate_health_score(vector_audit, graph_audit, bayesian_audit)
    }

    return recommendations


def calculate_health_score(
    vector_audit: dict,
    graph_audit: dict,
    bayesian_audit: dict
) -> float:
    """Calculate overall health score (0-100)."""
    score = 100.0

    # Deduct for content issues
    total = vector_audit.get("total", 1)
    empty_pct = vector_audit.get("content_analysis", {}).get("empty_count", 0) / total * 100
    score -= empty_pct * 2  # Heavy penalty for empty content

    short_pct = vector_audit.get("content_analysis", {}).get("short_count", 0) / total * 100
    score -= short_pct * 0.5  # Light penalty for short content

    # Deduct for graph issues
    nodes = graph_audit.get("nodes", 1)
    orphan_pct = graph_audit.get("issues", {}).get("orphan_nodes", 0) / nodes * 100
    score -= orphan_pct * 1.5

    # Bonus for good connectivity
    largest_pct = graph_audit.get("connectivity", {}).get("largest_component_pct", 0)
    if largest_pct > 90:
        score += 5  # Bonus for well-connected graph

    # Deduct for missing confidence
    sample = bayesian_audit.get("sample_size", 1)
    no_conf_pct = bayesian_audit.get("confidence_analysis", {}).get("no_confidence", 0) / sample * 100
    score -= no_conf_pct * 0.5

    return max(0, min(100, round(score, 1)))


def main():
    """Run full audit."""
    print("=" * 60)
    print("Memory MCP Triple-Tier Audit")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    config = load_config()

    # Run audits
    vector_audit = audit_vector_rag(config)
    graph_audit = audit_hipporag(config)
    bayesian_audit = audit_bayesian(config)

    # Generate recommendations
    recommendations = generate_cleanup_recommendations(
        vector_audit,
        graph_audit,
        bayesian_audit
    )

    # Compile full report
    report = {
        "timestamp": datetime.now().isoformat(),
        "vector_rag": vector_audit,
        "hipporag": graph_audit,
        "bayesian": bayesian_audit,
        "recommendations": recommendations
    }

    # Save report
    report_dir = Path(__file__).parent.parent / "reports"
    report_dir.mkdir(exist_ok=True)
    report_file = report_dir / f"audit-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    report_file.write_text(json.dumps(report, indent=2, default=str))

    # Print summary
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    print(f"\nHealth Score: {recommendations['summary']['health_score']}/100")
    print(f"\nVector RAG:")
    print(f"  - Total memories: {vector_audit.get('total', 0)}")
    print(f"  - Avg content length: {vector_audit.get('content_analysis', {}).get('avg_length', 0)} chars")
    print(f"  - Empty content: {vector_audit.get('content_analysis', {}).get('empty_count', 0)}")

    print(f"\nHippoRAG (Graph):")
    print(f"  - Nodes: {graph_audit.get('nodes', 0)}")
    print(f"  - Edges: {graph_audit.get('edges', 0)}")
    print(f"  - Orphan nodes: {graph_audit.get('issues', {}).get('orphan_nodes', 0)}")
    print(f"  - Components: {graph_audit.get('connectivity', {}).get('components', 0)}")
    print(f"  - Largest component: {graph_audit.get('connectivity', {}).get('largest_component_pct', 0)}%")

    print(f"\nBayesian:")
    print(f"  - Has confidence: {bayesian_audit.get('confidence_analysis', {}).get('has_confidence', 0)}")
    print(f"  - No confidence: {bayesian_audit.get('confidence_analysis', {}).get('no_confidence', 0)}")
    print(f"  - Avg confidence: {bayesian_audit.get('confidence_analysis', {}).get('avg_confidence', 0)}")

    print(f"\nRecommendations:")
    print(f"  - Items to delete: {recommendations['summary']['items_to_delete']}")
    print(f"  - Items to repair: {recommendations['summary']['items_to_repair']}")
    print(f"  - Warnings: {recommendations['summary']['warnings']}")

    print(f"\nFull report saved to: {report_file}")

    return report


if __name__ == "__main__":
    report = main()
    print(json.dumps(report, indent=2, default=str))
