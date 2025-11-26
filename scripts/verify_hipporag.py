#!/usr/bin/env python3
"""
HippoRAG Pipeline Verification Script

Quick smoke test to verify HippoRAG is working correctly.
Run this after any changes to graph/PPR/entity services.

Usage:
    python scripts/verify_hipporag.py

Expected: All checks pass in <5 seconds
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.graph_service import GraphService
from services.graph_query_engine import GraphQueryEngine
from services.entity_service import EntityService
from services.hipporag_service import HippoRagService
import tempfile
import shutil


def print_check(name: str, passed: bool, details: str = ""):
    """Print check result."""
    status = "PASS" if passed else "FAIL"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"
    print(f"{color}[{status}]{reset} {name}")
    if details:
        print(f"      {details}")


def verify_networkx_ppr():
    """Verify NetworkX PPR is available."""
    try:
        import networkx as nx
        has_pagerank = hasattr(nx, 'pagerank')
        version_ok = tuple(map(int, nx.__version__.split('.')[:2])) >= (3, 0)

        print_check(
            "NetworkX PPR available",
            has_pagerank and version_ok,
            f"NetworkX {nx.__version__}, pagerank: {has_pagerank}"
        )
        return has_pagerank and version_ok
    except Exception as e:
        print_check("NetworkX PPR available", False, str(e))
        return False


def verify_entity_service():
    """Verify entity extraction."""
    try:
        entity_svc = EntityService()
        entities = entity_svc.extract_entities("Python is great for NLP")

        has_entities = len(entities) > 0
        print_check(
            "Entity extraction",
            has_entities,
            f"Extracted {len(entities)} entities"
        )
        return has_entities
    except Exception as e:
        print_check("Entity extraction", False, str(e))
        return False


def verify_graph_operations():
    """Verify graph node/edge operations."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = GraphService(data_dir=tmpdir)

            # Add nodes
            graph.add_entity_node("test_entity", "CONCEPT")
            graph.add_chunk_node("test_chunk", {"text": "test"})

            # Add edge
            graph.add_relationship("test_chunk", "mentions", "test_entity")

            # Verify
            has_entity = graph.get_node("test_entity") is not None
            has_chunk = graph.get_node("test_chunk") is not None
            has_edge = graph.graph.has_edge("test_chunk", "test_entity")

            success = has_entity and has_chunk and has_edge
            print_check(
                "Graph operations",
                success,
                f"Nodes: {graph.get_node_count()}, Edges: {graph.get_edge_count()}"
            )
            return success
    except Exception as e:
        print_check("Graph operations", False, str(e))
        return False


def verify_ppr_computation():
    """Verify PPR computation."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = GraphService(data_dir=tmpdir)

            # Create test graph
            graph.add_entity_node("python", "CONCEPT")
            graph.add_entity_node("ml", "CONCEPT")
            graph.add_chunk_node("chunk1", {"text": "Python ML"})
            graph.add_relationship("chunk1", "mentions", "python")
            graph.add_relationship("chunk1", "mentions", "ml")

            # Run PPR
            query_engine = GraphQueryEngine(graph)
            ppr_scores = query_engine.personalized_pagerank(["python"], alpha=0.85)

            has_scores = len(ppr_scores) > 0
            has_query_node = "python" in ppr_scores

            print_check(
                "PPR computation",
                has_scores and has_query_node,
                f"{len(ppr_scores)} scores computed"
            )
            return has_scores and has_query_node
    except Exception as e:
        print_check("PPR computation", False, str(e))
        return False


def verify_chunk_ranking():
    """Verify chunk ranking by PPR."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = GraphService(data_dir=tmpdir)

            # Create test graph
            graph.add_entity_node("python", "CONCEPT")
            graph.add_chunk_node("chunk1", {"text": "Python"})
            graph.add_chunk_node("chunk2", {"text": "Other"})
            graph.add_relationship("chunk1", "mentions", "python")

            # Run PPR and rank
            query_engine = GraphQueryEngine(graph)
            ppr_scores = query_engine.personalized_pagerank(["python"])
            ranked = query_engine.rank_chunks_by_ppr(ppr_scores, top_k=5)

            has_results = len(ranked) > 0
            correct_top = ranked[0][0] == "chunk1" if ranked else False

            print_check(
                "Chunk ranking",
                has_results and correct_top,
                f"{len(ranked)} chunks ranked"
            )
            return has_results and correct_top
    except Exception as e:
        print_check("Chunk ranking", False, str(e))
        return False


def verify_hipporag_pipeline():
    """Verify full HippoRAG pipeline."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = GraphService(data_dir=tmpdir)
            entity_svc = EntityService()
            hipporag = HippoRagService(graph, entity_svc)

            # Create test data
            graph.add_entity_node("python", "CONCEPT")
            graph.add_entity_node("nlp", "CONCEPT")
            graph.add_chunk_node("chunk1", {"text": "Python NLP tutorial"})
            graph.add_relationship("chunk1", "mentions", "python")
            graph.add_relationship("chunk1", "mentions", "nlp")

            # Run pipeline
            results = hipporag.retrieve("Python NLP", top_k=5)

            has_results = len(results) > 0
            print_check(
                "HippoRAG pipeline",
                has_results,
                f"{len(results)} results returned"
            )
            return has_results
    except Exception as e:
        print_check("HippoRAG pipeline", False, str(e))
        return False


def verify_multi_hop():
    """Verify multi-hop retrieval."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = GraphService(data_dir=tmpdir)
            entity_svc = EntityService()
            hipporag = HippoRagService(graph, entity_svc)

            # Create multi-hop graph
            graph.add_entity_node("ai", "CONCEPT")
            graph.add_entity_node("ml", "CONCEPT")
            graph.add_chunk_node("chunk1", {"text": "AI"})
            graph.add_relationship("chunk1", "mentions", "ai")
            graph.add_relationship("ai", "related_to", "ml")

            # Run multi-hop
            results = hipporag.retrieve_multi_hop("AI", max_hops=2, top_k=5)

            has_results = len(results) > 0
            print_check(
                "Multi-hop retrieval",
                has_results,
                f"{len(results)} results with BFS expansion"
            )
            return has_results
    except Exception as e:
        print_check("Multi-hop retrieval", False, str(e))
        return False


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("HippoRAG Pipeline Verification")
    print("=" * 60)
    print()

    checks = [
        ("NetworkX PPR", verify_networkx_ppr),
        ("Entity Service", verify_entity_service),
        ("Graph Operations", verify_graph_operations),
        ("PPR Computation", verify_ppr_computation),
        ("Chunk Ranking", verify_chunk_ranking),
        ("HippoRAG Pipeline", verify_hipporag_pipeline),
        ("Multi-hop Retrieval", verify_multi_hop)
    ]

    results = []
    for name, check_func in checks:
        try:
            passed = check_func()
            results.append((name, passed))
        except Exception as e:
            print_check(name, False, f"Unexpected error: {e}")
            results.append((name, False))
        print()

    # Summary
    print("=" * 60)
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    if passed_count == total_count:
        print(f"\033[92mALL CHECKS PASSED ({passed_count}/{total_count})\033[0m")
        print("\nHippoRAG pipeline is ready for production use.")
        return 0
    else:
        print(f"\033[91mSOME CHECKS FAILED ({passed_count}/{total_count})\033[0m")
        print("\nFailed checks:")
        for name, passed in results:
            if not passed:
                print(f"  - {name}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
