"""
Unit tests for VectorSearchTool
Following TDD (London School) with proper test structure.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.mcp.tools.vector_search import VectorSearchTool


class TestVectorSearchTool:
    """Test suite for VectorSearchTool."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return {
            'embeddings': {
                'model': 'all-MiniLM-L6-v2',
                'dimension': 384
            },
            'storage': {
                'vector_db': {
                    'persist_directory': './test_chroma_data',
                    'collection_name': 'test_collection'
                }
            },
            'chunking': {
                'min_chunk_size': 128,
                'max_chunk_size': 512,
                'overlap': 50
            }
        }

    @pytest.fixture
    def tool(self, config):
        """Create VectorSearchTool instance."""
        return VectorSearchTool(config)

    def test_initialization(self, tool):
        """Test tool initialization."""
        assert tool is not None
        assert tool.config is not None

    def test_initialization_missing_embeddings_config(self):
        """Test initialization fails without embeddings config."""
        with pytest.raises(AssertionError):
            VectorSearchTool({'storage': {}})

    def test_initialization_missing_storage_config(self):
        """Test initialization fails without storage config."""
        with pytest.raises(AssertionError):
            VectorSearchTool({'embeddings': {}})

    def test_lazy_loading_chunker(self, tool):
        """Test chunker is lazy loaded."""
        assert tool._chunker is None

        with patch('src.mcp.tools.vector_search.SemanticChunker') as MockChunker:
            _ = tool.chunker
            MockChunker.assert_called_once()

    def test_lazy_loading_embedder(self, tool):
        """Test embedder is lazy loaded."""
        assert tool._embedder is None

        with patch('src.mcp.tools.vector_search.EmbeddingPipeline') as MockEmbedder:
            _ = tool.embedder
            MockEmbedder.assert_called_once()

    def test_lazy_loading_indexer(self, tool):
        """Test indexer is lazy loaded."""
        assert tool._indexer is None

        with patch('src.mcp.tools.vector_search.VectorIndexer') as MockIndexer:
            _ = tool.indexer
            MockIndexer.assert_called_once()

    def test_check_services_structure(self, tool):
        """Test check_services returns correct structure."""
        # Create mock components
        mock_indexer = MagicMock()
        mock_indexer.client.heartbeat.side_effect = Exception("ChromaDB unavailable")

        mock_embedder = MagicMock()
        mock_embedder.encode_single.side_effect = Exception("Embeddings unavailable")

        # Set the internal attributes directly (bypass @property)
        tool._indexer = mock_indexer
        tool._embedder = mock_embedder

        services = tool.check_services()

        assert 'chromadb' in services
        assert 'embeddings' in services
        assert services['chromadb'] == 'unavailable'
        assert services['embeddings'] == 'unavailable'


class TestVectorSearchExecution:
    """Test suite for vector search execution (with mocks)."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return {
            'embeddings': {
                'model': 'all-MiniLM-L6-v2',
                'dimension': 384
            },
            'storage': {
                'vector_db': {
                    'persist_directory': './test_chroma_data',
                    'collection_name': 'test_collection'
                }
            },
            'chunking': {
                'min_chunk_size': 128,
                'max_chunk_size': 512,
                'overlap': 50
            }
        }

    @pytest.fixture
    def tool(self, config):
        """Create VectorSearchTool with mocked components."""
        tool = VectorSearchTool(config)

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.encode_single.return_value = MagicMock()
        mock_embedder.encode_single.return_value.tolist.return_value = [0.1] * 384
        tool._embedder = mock_embedder

        # Mock indexer
        mock_indexer = MagicMock()
        mock_indexer.collection_name = 'test_collection'

        # Mock ChromaDB query result (returns dict with lists)
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            'ids': [['test_id_1']],
            'documents': [['Test chunk text']],
            'metadatas': [[{
                'file_path': '/test/file.md',
                'chunk_index': 0,
                'title': 'Test Document'
            }]],
            'distances': [[0.05]]  # Low distance = high similarity
        }
        mock_indexer.collection = mock_collection
        tool._indexer = mock_indexer

        return tool

    def test_execute_valid_query(self, tool):
        """Test execute with valid query."""
        results = tool.execute("test query", limit=5)

        assert len(results) > 0
        assert results[0]['text'] == 'Test chunk text'
        assert results[0]['file_path'] == '/test/file.md'
        assert results[0]['score'] == 0.95

    def test_execute_empty_query_fails(self, tool):
        """Test execute fails with empty query."""
        with pytest.raises(AssertionError):
            tool.execute("", limit=5)

    def test_execute_zero_limit_fails(self, tool):
        """Test execute fails with zero limit."""
        with pytest.raises(AssertionError):
            tool.execute("test query", limit=0)

    def test_execute_limit_too_large_fails(self, tool):
        """Test execute fails with limit >100."""
        with pytest.raises(AssertionError):
            tool.execute("test query", limit=101)

    def test_execute_calls_embedder(self, tool):
        """Test execute calls embedder with query."""
        tool.execute("test query", limit=5)

        tool._embedder.encode_single.assert_called_once_with("test query")

    def test_execute_calls_indexer_search(self, tool):
        """Test execute calls indexer search."""
        tool.execute("test query", limit=5)

        tool._indexer.collection.query.assert_called_once()

    def test_execute_result_structure(self, tool):
        """Test execute returns correctly structured results."""
        results = tool.execute("test query", limit=5)

        assert isinstance(results, list)
        result = results[0]
        assert 'text' in result
        assert 'file_path' in result
        assert 'chunk_index' in result
        assert 'score' in result
        assert 'metadata' in result

    def test_execute_metadata_extraction(self, tool):
        """Test metadata is correctly extracted."""
        results = tool.execute("test query", limit=5)

        # Metadata should contain 'title' but not 'text', 'file_path', 'chunk_index'
        metadata = results[0]['metadata']
        assert 'title' in metadata
        assert 'text' not in metadata
        assert 'file_path' not in metadata
        assert 'chunk_index' not in metadata
