"""
Unit tests for VectorIndexer
Following TDD (London School) with proper test structure.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from src.indexing.vector_indexer import VectorIndexer


class TestVectorIndexer:
    """Test suite for VectorIndexer."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for ChromaDB."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        # Cleanup: delete temp directory
        try:
            shutil.rmtree(temp_path)
        except Exception:
            pass

    @pytest.fixture
    def indexer(self, temp_dir):
        """Create indexer instance with temporary ChromaDB directory."""
        indexer = VectorIndexer(
            persist_directory=temp_dir,
            collection_name="test_collection"
        )
        yield indexer
        # Cleanup: delete test collection
        try:
            indexer.client.delete_collection("test_collection")
        except Exception:
            pass

    def test_initialization(self, indexer):
        """Test indexer initialization."""
        assert indexer.collection_name == "test_collection"
        assert Path(indexer.persist_directory).exists()

    def test_create_collection(self, indexer):
        """Test collection creation."""
        indexer.create_collection(vector_size=384)

        # Verify collection exists using ChromaDB API
        collections = indexer.client.list_collections()
        collection_names = [c.name for c in collections]

        assert "test_collection" in collection_names

    def test_index_chunks(self, indexer):
        """Test indexing chunks."""
        indexer.create_collection(vector_size=384)

        chunks = [
            {
                'text': 'Test chunk 1',
                'file_path': '/test/file.md',
                'chunk_index': 0,
                'metadata': {'title': 'Test'}
            },
            {
                'text': 'Test chunk 2',
                'file_path': '/test/file.md',
                'chunk_index': 1,
                'metadata': {'title': 'Test'}
            }
        ]

        embeddings = [
            [0.1] * 384,  # Dummy embedding
            [0.2] * 384   # Dummy embedding
        ]

        indexer.index_chunks(chunks, embeddings)

        # Verify indexed using ChromaDB API
        result = indexer.collection.get()

        assert len(result['ids']) == 2
        assert len(result['documents']) == 2

    def test_index_chunks_mismatched_lengths_raises(self, indexer):
        """Test that mismatched lengths raise error."""
        indexer.create_collection(vector_size=384)

        chunks = [{'text': 'Test', 'file_path': '/test', 'chunk_index': 0}]
        embeddings = [[0.1] * 384, [0.2] * 384]  # 2 embeddings, 1 chunk

        with pytest.raises(AssertionError):
            indexer.index_chunks(chunks, embeddings)

    def test_index_empty_chunks_raises(self, indexer):
        """Test that empty chunks list raises error."""
        indexer.create_collection(vector_size=384)

        with pytest.raises(AssertionError):
            indexer.index_chunks([], [])

    def test_delete_chunks_success(self, indexer):
        """Test successful chunk deletion."""
        indexer.create_collection(vector_size=384)

        # First, index some chunks
        chunks = [
            {
                'text': 'Test chunk 1',
                'file_path': '/test/file.md',
                'chunk_index': 0
            },
            {
                'text': 'Test chunk 2',
                'file_path': '/test/file.md',
                'chunk_index': 1
            }
        ]
        embeddings = [[0.1] * 384, [0.2] * 384]
        indexer.index_chunks(chunks, embeddings)

        # Get IDs of indexed chunks
        result = indexer.collection.get()
        ids_to_delete = result['ids'][:1]  # Delete first chunk

        # Delete chunks
        success = indexer.delete_chunks(ids_to_delete)

        assert success is True

        # Verify deletion
        result_after = indexer.collection.get()
        assert len(result_after['ids']) == 1

    def test_delete_chunks_empty_list(self, indexer):
        """Test deletion with empty ID list (edge case)."""
        indexer.create_collection(vector_size=384)

        # Delete with empty list should succeed (no-op)
        success = indexer.delete_chunks([])

        assert success is True

    def test_delete_chunks_nonexistent_ids(self, indexer):
        """Test deletion of nonexistent IDs (graceful failure)."""
        indexer.create_collection(vector_size=384)

        # Try to delete IDs that don't exist
        nonexistent_ids = ['fake-id-1', 'fake-id-2']
        success = indexer.delete_chunks(nonexistent_ids)

        # ChromaDB may handle this gracefully or fail
        # We expect True (graceful) or False (error logged)
        assert isinstance(success, bool)

    def test_update_chunks_metadata(self, indexer):
        """Test updating metadata only."""
        indexer.create_collection(vector_size=384)

        # Index a chunk
        chunks = [{
            'text': 'Test chunk',
            'file_path': '/test/file.md',
            'chunk_index': 0
        }]
        embeddings = [[0.1] * 384]
        indexer.index_chunks(chunks, embeddings)

        # Get chunk ID
        result = indexer.collection.get()
        chunk_id = result['ids'][0]

        # Update metadata
        new_metadata = {'title': 'Updated Title', 'author': 'Test Author'}
        success = indexer.update_chunks(
            ids=[chunk_id],
            metadatas=[new_metadata]
        )

        assert success is True

        # Verify update
        updated_result = indexer.collection.get(ids=[chunk_id])
        assert updated_result['metadatas'][0]['title'] == 'Updated Title'

    def test_update_chunks_embeddings(self, indexer):
        """Test updating embeddings only."""
        indexer.create_collection(vector_size=384)

        # Index a chunk
        chunks = [{
            'text': 'Test chunk',
            'file_path': '/test/file.md',
            'chunk_index': 0
        }]
        embeddings = [[0.1] * 384]
        indexer.index_chunks(chunks, embeddings)

        # Get chunk ID
        result = indexer.collection.get()
        chunk_id = result['ids'][0]

        # Update embedding
        new_embedding = [[0.5] * 384]
        success = indexer.update_chunks(
            ids=[chunk_id],
            embeddings=new_embedding
        )

        assert success is True

    def test_update_chunks_documents(self, indexer):
        """Test updating documents only."""
        indexer.create_collection(vector_size=384)

        # Index a chunk
        chunks = [{
            'text': 'Test chunk',
            'file_path': '/test/file.md',
            'chunk_index': 0
        }]
        embeddings = [[0.1] * 384]
        indexer.index_chunks(chunks, embeddings)

        # Get chunk ID
        result = indexer.collection.get()
        chunk_id = result['ids'][0]

        # Update document
        new_document = ['Updated document text']
        success = indexer.update_chunks(
            ids=[chunk_id],
            documents=new_document
        )

        assert success is True

        # Verify update
        updated_result = indexer.collection.get(ids=[chunk_id])
        assert updated_result['documents'][0] == 'Updated document text'

    def test_update_chunks_all_fields(self, indexer):
        """Test updating all fields (embeddings, metadata, documents)."""
        indexer.create_collection(vector_size=384)

        # Index a chunk
        chunks = [{
            'text': 'Test chunk',
            'file_path': '/test/file.md',
            'chunk_index': 0
        }]
        embeddings = [[0.1] * 384]
        indexer.index_chunks(chunks, embeddings)

        # Get chunk ID
        result = indexer.collection.get()
        chunk_id = result['ids'][0]

        # Update all fields
        success = indexer.update_chunks(
            ids=[chunk_id],
            embeddings=[[0.9] * 384],
            metadatas=[{'title': 'All Updated'}],
            documents=['Completely new text']
        )

        assert success is True

        # Verify all updates
        updated_result = indexer.collection.get(ids=[chunk_id])
        assert updated_result['documents'][0] == 'Completely new text'
        assert updated_result['metadatas'][0]['title'] == 'All Updated'

    def test_update_chunks_empty_list(self, indexer):
        """Test update with empty ID list (edge case)."""
        indexer.create_collection(vector_size=384)

        # Update with empty list should succeed (no-op)
        success = indexer.update_chunks([], metadatas=[])

        assert success is True

    def test_update_chunks_nonexistent_ids(self, indexer):
        """Test update of nonexistent IDs (graceful failure)."""
        indexer.create_collection(vector_size=384)

        # Try to update IDs that don't exist
        nonexistent_ids = ['fake-id-1']
        success = indexer.update_chunks(
            ids=nonexistent_ids,
            metadatas=[{'title': 'New'}]
        )

        # ChromaDB may handle this gracefully or fail
        # We expect True (graceful) or False (error logged)
        assert isinstance(success, bool)
