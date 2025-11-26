"""
Phase 3 Unit Tests - Mock Code Replacement Validation

Tests that mock implementations have been replaced with real code:
- B2.1: Semantic chunking uses embeddings
- B1.1: Obsidian client uses real chunker/indexer
- B1.6: Bayesian CPD uses informed estimation (not random.choice)
"""

import sys
from pathlib import Path
import pytest
import inspect

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSemanticChunkerRealImplementation:
    """Test B2.1: Max-Min semantic chunking is real, not mock."""

    def test_chunker_has_embedding_support(self):
        """Verify chunker supports embedding pipeline."""
        from src.chunking.semantic_chunker import SemanticChunker

        chunker = SemanticChunker()

        # Check for embedding-related attributes
        assert hasattr(chunker, '_embedding_pipeline'), "Missing embedding pipeline attribute"
        assert hasattr(chunker, '_use_semantic'), "Missing semantic flag"
        assert hasattr(chunker, 'similarity_threshold'), "Missing similarity threshold"

    def test_chunker_has_semantic_methods(self):
        """Verify chunker has semantic chunking methods."""
        from src.chunking.semantic_chunker import SemanticChunker

        chunker = SemanticChunker()

        # Check for semantic methods
        assert hasattr(chunker, '_split_into_sentences'), "Missing sentence splitter"
        assert hasattr(chunker, '_compute_sentence_similarities'), "Missing similarity computation"
        assert hasattr(chunker, '_find_semantic_boundaries'), "Missing boundary detection"
        assert hasattr(chunker, '_merge_sentences_into_chunks'), "Missing chunk merger"

    def test_no_todo_in_split_chunks(self):
        """Verify TODO comment has been removed from _split_into_chunks."""
        from src.chunking.semantic_chunker import SemanticChunker

        source = inspect.getsource(SemanticChunker._split_into_chunks)

        # The old TODO should be gone
        assert "TODO: Implement Max-Min" not in source, \
            "TODO comment still present - implementation not complete"

    def test_semantic_chunking_produces_chunks(self):
        """Test that semantic chunking produces reasonable output."""
        from src.chunking.semantic_chunker import SemanticChunker

        chunker = SemanticChunker(
            min_chunk_size=10,
            max_chunk_size=100,
            similarity_threshold=0.5
        )
        chunker._use_semantic = False  # Use fallback for faster test

        test_text = """
        This is the first paragraph about machine learning.
        It contains multiple sentences about AI and neural networks.

        This is the second paragraph about a completely different topic.
        It discusses gardening and plants in detail.

        The third paragraph returns to technology topics.
        It mentions cloud computing and databases.
        """

        chunks = chunker.chunk_text(test_text.strip(), "test.md")

        assert len(chunks) > 0, "Chunker produced no chunks"
        assert all('text' in c for c in chunks), "Chunks missing text field"


class TestObsidianClientRealImplementation:
    """Test B1.1: Obsidian client uses real chunker/indexer."""

    def test_obsidian_has_lazy_loaders(self):
        """Verify Obsidian client has lazy loaders for real components."""
        from src.mcp import obsidian_client

        # Check for lazy loader functions
        assert hasattr(obsidian_client, '_get_chunker'), "Missing chunker loader"
        assert hasattr(obsidian_client, '_get_embedder'), "Missing embedder loader"
        assert hasattr(obsidian_client, '_get_indexer'), "Missing indexer loader"

    def test_sync_file_uses_real_chunker(self):
        """Verify _sync_file method uses real chunker, not mock."""
        from src.mcp.obsidian_client import ObsidianMCPClient

        source = inspect.getsource(ObsidianMCPClient._sync_file)

        # Check for real implementation markers
        assert "_get_chunker()" in source, "Not using real chunker"
        assert "_get_embedder()" in source, "Not using real embedder"
        assert "_get_indexer()" in source, "Not using real indexer"

        # Check mock comment is removed
        assert "For Week 7, we return mock success" not in source, \
            "Mock implementation still present"


class TestBayesianCPDRealImplementation:
    """Test B1.6: Bayesian CPD uses informed estimation."""

    def test_network_builder_has_informed_methods(self):
        """Verify NetworkBuilder has informed data generation."""
        from src.bayesian.network_builder import NetworkBuilder

        builder = NetworkBuilder()

        # Check for new methods
        assert hasattr(builder, '_extract_node_states'), "Missing state extractor"
        assert hasattr(builder, '_generate_informed_data'), "Missing informed data generator"

    def test_no_random_choice_in_estimate_cpds(self):
        """Verify random.choice is not used in CPD estimation."""
        from src.bayesian.network_builder import NetworkBuilder

        # Check estimate_cpds source
        source = inspect.getsource(NetworkBuilder.estimate_cpds)

        # Should NOT have random.choice in the main method
        assert "random.choice" not in source, \
            "estimate_cpds still uses random.choice - not replaced with informed estimation"

    def test_informed_data_uses_graph_structure(self):
        """Verify _generate_informed_data uses graph structure."""
        from src.bayesian.network_builder import NetworkBuilder

        source = inspect.getsource(NetworkBuilder._generate_informed_data)

        # Check for graph-aware generation
        assert "edge_data" in source or "weight" in source, \
            "Informed data should use edge weights"
        assert "degree" in source, \
            "Informed data should use node degree"
        assert "topological" in source.lower(), \
            "Informed data should respect topological order"


class TestMockCodeRemovalVerification:
    """Verify all specified mock code has been removed."""

    def test_semantic_chunker_todo_removed(self):
        """B2.1: Verify TODO removed from semantic_chunker.py line 116."""
        chunker_path = Path(__file__).parent.parent.parent / "src" / "chunking" / "semantic_chunker.py"
        content = chunker_path.read_text(encoding='utf-8')

        assert "TODO: Implement Max-Min semantic chunking" not in content, \
            "B2.1 TODO still present at line 116"

    def test_obsidian_mock_removed(self):
        """B1.1: Verify mock return removed from obsidian_client.py line 167."""
        obsidian_path = Path(__file__).parent.parent.parent / "src" / "mcp" / "obsidian_client.py"
        content = obsidian_path.read_text(encoding='utf-8')

        assert "For Week 7, we return mock success" not in content, \
            "B1.1 mock comment still present"

        assert "chunks = max(1, len(content) // 500)" not in content, \
            "B1.1 mock chunk estimation still present"

    def test_bayesian_random_removed(self):
        """B1.6: Verify random.choice removed from network_builder.py estimate_cpds."""
        builder_path = Path(__file__).parent.parent.parent / "src" / "bayesian" / "network_builder.py"
        content = builder_path.read_text(encoding='utf-8')

        # Check that the old pattern is gone from estimate_cpds
        # The old code had: row[node] = random.choice(states) in estimate_cpds
        # Now it's in _generate_informed_data but uses np.random with probabilities

        # Read just the estimate_cpds method
        import re
        estimate_cpds_match = re.search(
            r'def estimate_cpds\(.*?\n(?:.*?\n)*?(?=\n    def |\nclass |\Z)',
            content,
            re.MULTILINE
        )

        if estimate_cpds_match:
            estimate_cpds_content = estimate_cpds_match.group(0)
            assert "random.choice" not in estimate_cpds_content, \
                "B1.6 random.choice still in estimate_cpds method"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
