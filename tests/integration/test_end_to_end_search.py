"""
Integration tests for end-to-end vector search workflow.

A2.2 FIX: Updated to use ChromaDB (in-memory) instead of Docker/Qdrant.
Now runs without external dependencies.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestEndToEndVectorSearch:
    """Integration tests for complete vector search workflow with ChromaDB."""

    @pytest.fixture
    def test_markdown_file(self, tmp_path):
        """Create test markdown file."""
        content = """---
title: Integration Test Document
tags: [test, integration]
---

# Test Content

This is a test document for integration testing.
It contains multiple paragraphs that will be chunked.

## Section 1

First section content with meaningful text about vector search.

## Section 2

Second section with different semantic content about embeddings.
"""
        file_path = tmp_path / "test_integration.md"
        file_path.write_text(content, encoding='utf-8')
        return file_path

    @pytest.fixture
    def chroma_persist_dir(self, tmp_path):
        """Create temporary ChromaDB persist directory."""
        persist_dir = tmp_path / "chroma_test"
        persist_dir.mkdir()
        return str(persist_dir)

    def test_full_workflow_chunking_embedding_indexing(
        self, test_markdown_file, chroma_persist_dir
    ):
        """
        Test complete workflow with ChromaDB:
        1. Chunk markdown file
        2. Generate embeddings
        3. Index in ChromaDB
        4. Search and retrieve

        NASA Rule 10: 35 LOC
        """
        from src.chunking.semantic_chunker import SemanticChunker
        from src.indexing.embedding_pipeline import EmbeddingPipeline
        from src.indexing.vector_indexer import VectorIndexer

        # 1. Chunk the markdown file
        chunker = SemanticChunker(min_chunk_size=50, max_chunk_size=200)
        with open(test_markdown_file, 'r', encoding='utf-8') as f:
            content = f.read()
        chunks = chunker.chunk(content)
        assert len(chunks) >= 1, "Should produce at least 1 chunk"

        # 2. Generate embeddings
        embedder = EmbeddingPipeline(model_name='all-MiniLM-L6-v2')
        embeddings = embedder.encode_batch([c['text'] for c in chunks])
        assert len(embeddings) == len(chunks), "Should have embedding per chunk"

        # 3. Index in ChromaDB
        indexer = VectorIndexer(
            persist_directory=chroma_persist_dir,
            collection_name='test_e2e'
        )

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            indexer.add_document(
                doc_id=f"chunk_{i}",
                text=chunk['text'],
                embedding=embedding.tolist(),
                metadata={'file': str(test_markdown_file), 'index': i}
            )

        # 4. Search and retrieve
        query = "vector search embeddings"
        query_embedding = embedder.encode_single(query)
        results = indexer.search(query_embedding.tolist(), top_k=3)

        assert len(results) >= 1, "Should find at least 1 result"
        assert 'text' in results[0], "Result should have text"
        assert 'score' in results[0], "Result should have score"

    def test_mcp_server_vector_search_tool(self, chroma_persist_dir):
        """
        Test MCP server vector search tool with in-memory ChromaDB.

        NASA Rule 10: 30 LOC
        """
        from src.mcp.tools.vector_search import VectorSearchTool

        config = {
            'embeddings': {
                'model': 'all-MiniLM-L6-v2'
            },
            'storage': {
                'vector_db': {
                    'persist_directory': chroma_persist_dir,
                    'collection_name': 'test_mcp'
                }
            },
            'chunking': {
                'min_chunk_size': 50,
                'max_chunk_size': 200
            }
        }

        tool = VectorSearchTool(config)

        # Check services are available
        services = tool.check_services()
        assert services['chromadb'] == 'available', "ChromaDB should be available"
        assert services['embeddings'] == 'available', "Embeddings should be available"

        # Index a test document
        test_text = "Machine learning is a subset of artificial intelligence."
        embedding = tool.embedder.encode_single(test_text)
        tool.indexer.add_document(
            doc_id="test_doc",
            text=test_text,
            embedding=embedding.tolist(),
            metadata={'source': 'test'}
        )

        # Search
        results = tool.execute(query="artificial intelligence", limit=3)
        assert len(results) >= 1, "Should find indexed document"

    def test_performance_target_200ms(self, chroma_persist_dir):
        """
        Test vector search completes within 200ms target.

        NASA Rule 10: 25 LOC
        """
        import time
        from src.mcp.tools.vector_search import VectorSearchTool

        config = {
            'embeddings': {'model': 'all-MiniLM-L6-v2'},
            'storage': {
                'vector_db': {
                    'persist_directory': chroma_persist_dir,
                    'collection_name': 'test_perf'
                }
            },
            'chunking': {'min_chunk_size': 50, 'max_chunk_size': 200}
        }

        tool = VectorSearchTool(config)

        # Index 10 documents
        for i in range(10):
            text = f"Document {i} about topic {i % 3}"
            emb = tool.embedder.encode_single(text)
            tool.indexer.add_document(
                doc_id=f"doc_{i}", text=text,
                embedding=emb.tolist(), metadata={'idx': i}
            )

        # Time the search
        start = time.time()
        results = tool.execute("topic about documents", limit=5)
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 200, f"Search took {elapsed_ms:.0f}ms, target is 200ms"
        assert len(results) >= 1, "Should find results"

    def test_similarity_scores_in_valid_range(self, chroma_persist_dir):
        """
        B3.1 VALIDATION: Test similarity scores are in [0, 1] range.

        NASA Rule 10: 25 LOC
        """
        from src.mcp.tools.vector_search import VectorSearchTool

        config = {
            'embeddings': {'model': 'all-MiniLM-L6-v2'},
            'storage': {
                'vector_db': {
                    'persist_directory': chroma_persist_dir,
                    'collection_name': 'test_scores'
                }
            },
            'chunking': {'min_chunk_size': 50, 'max_chunk_size': 200}
        }

        tool = VectorSearchTool(config)

        # Index diverse documents
        docs = [
            "Python programming language basics",
            "JavaScript web development tutorial",
            "Database design patterns SQL",
            "Machine learning neural networks"
        ]

        for i, text in enumerate(docs):
            emb = tool.embedder.encode_single(text)
            tool.indexer.add_document(
                doc_id=f"doc_{i}", text=text,
                embedding=emb.tolist(), metadata={'idx': i}
            )

        # Search and verify scores
        results = tool.execute("programming tutorial", limit=4)

        for result in results:
            score = result['score']
            assert 0.0 <= score <= 1.0, f"Score {score} not in [0, 1] range"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
