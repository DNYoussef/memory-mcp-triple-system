"""
Unit tests for VisualMemoryIndexer.

MEM-QWEN-006: Tests for ChromaDB visual memory indexer.

Tests:
1. Initialization and configuration
2. Add visual memory
3. Search operations
4. Get by ID
5. Delete operations
6. Metadata handling
7. Error handling
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from src.indexing.visual_indexer import VisualMemoryIndexer


class TestVisualMemoryIndexerInitialization:
    """Test VisualMemoryIndexer initialization."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield temp
        try:
            shutil.rmtree(temp)
        except PermissionError:
            pass  # Windows file lock

    def test_initialization_default_collection(self, temp_dir):
        """Test default collection name."""
        indexer = VisualMemoryIndexer(persist_directory=temp_dir)
        assert indexer.collection_name == "visual_memories"

    def test_initialization_custom_collection(self, temp_dir):
        """Test custom collection name."""
        indexer = VisualMemoryIndexer(
            persist_directory=temp_dir, collection_name="my_visuals"
        )
        assert indexer.collection_name == "my_visuals"

    def test_initialization_creates_directory(self):
        """Test that initialization creates persist directory."""
        temp = tempfile.mkdtemp()
        new_dir = Path(temp) / "new_subdir"

        try:
            indexer = VisualMemoryIndexer(persist_directory=str(new_dir))
            assert new_dir.exists()
        finally:
            try:
                shutil.rmtree(temp)
            except PermissionError:
                pass

    def test_initialization_empty_collection(self, temp_dir):
        """Test newly initialized collection is empty."""
        indexer = VisualMemoryIndexer(persist_directory=temp_dir)
        assert indexer.count() == 0


class TestVisualMemoryIndexerAddVisual:
    """Test adding visual memories."""

    @pytest.fixture
    def indexer(self):
        """Create indexer with temporary directory."""
        temp = tempfile.mkdtemp()
        idx = VisualMemoryIndexer(persist_directory=temp)
        yield idx
        try:
            shutil.rmtree(temp)
        except PermissionError:
            pass

    @pytest.fixture
    def sample_embedding(self):
        """Sample embedding vector."""
        return [0.1] * 384

    def test_add_visual_returns_doc_id(self, indexer, sample_embedding):
        """Test add_visual returns document ID."""
        result = indexer.add_visual(
            doc_id="test-doc-1",
            embedding=sample_embedding,
            metadata={"visual_type": "screenshot"},
            document="Test document",
        )
        assert result == "test-doc-1"

    def test_add_visual_increments_count(self, indexer, sample_embedding):
        """Test add_visual increments collection count."""
        initial_count = indexer.count()

        indexer.add_visual(
            doc_id="test-doc-1",
            embedding=sample_embedding,
            metadata={"visual_type": "screenshot"},
            document="Test document",
        )

        assert indexer.count() == initial_count + 1

    def test_add_multiple_visuals(self, indexer, sample_embedding):
        """Test adding multiple visuals."""
        for i in range(5):
            indexer.add_visual(
                doc_id=f"test-doc-{i}",
                embedding=sample_embedding,
                metadata={"visual_type": "screenshot", "index": i},
                document=f"Document {i}",
            )

        assert indexer.count() == 5

    def test_add_visual_with_nested_metadata(self, indexer, sample_embedding):
        """Test metadata flattening for nested dicts."""
        indexer.add_visual(
            doc_id="test-doc-1",
            embedding=sample_embedding,
            metadata={
                "visual_type": "screenshot",
                "agent": {"name": "test", "version": "1.0"},
            },
            document="Test",
        )

        result = indexer.get_by_id("test-doc-1")
        assert result is not None
        # Nested dict should be flattened
        assert "agent.name" in result["metadata"] or "agent" in str(result["metadata"])


class TestVisualMemoryIndexerSearch:
    """Test search operations."""

    @pytest.fixture
    def populated_indexer(self):
        """Create indexer with sample data."""
        temp = tempfile.mkdtemp()
        idx = VisualMemoryIndexer(persist_directory=temp)

        # Add sample documents with different embeddings
        embeddings = [
            [1.0] + [0.0] * 383,  # doc-1: high on dim 0
            [0.0, 1.0] + [0.0] * 382,  # doc-2: high on dim 1
            [0.5, 0.5] + [0.0] * 382,  # doc-3: mixed
        ]

        for i, emb in enumerate(embeddings):
            idx.add_visual(
                doc_id=f"doc-{i+1}",
                embedding=emb,
                metadata={"visual_type": "screenshot" if i < 2 else "diagram"},
                document=f"Document {i+1}",
            )

        yield idx

        try:
            shutil.rmtree(temp)
        except PermissionError:
            pass

    def test_search_returns_results(self, populated_indexer):
        """Test search returns results."""
        query_embedding = [1.0] + [0.0] * 383
        results = populated_indexer.search(query_embedding, top_k=3)

        assert len(results) > 0

    def test_search_respects_top_k(self, populated_indexer):
        """Test search respects top_k limit."""
        query_embedding = [0.5] * 384
        results = populated_indexer.search(query_embedding, top_k=2)

        assert len(results) <= 2

    def test_search_returns_scores(self, populated_indexer):
        """Test search results include scores."""
        query_embedding = [1.0] + [0.0] * 383
        results = populated_indexer.search(query_embedding, top_k=3)

        for result in results:
            assert "score" in result
            assert 0.0 <= result["score"] <= 1.0

    def test_search_with_filter(self, populated_indexer):
        """Test search with metadata filter."""
        query_embedding = [0.5] * 384
        results = populated_indexer.search(
            query_embedding, top_k=10, where={"visual_type": "diagram"}
        )

        for result in results:
            assert result["metadata"]["visual_type"] == "diagram"

    def test_search_empty_collection(self):
        """Test search on empty collection."""
        temp = tempfile.mkdtemp()
        try:
            idx = VisualMemoryIndexer(persist_directory=temp)
            results = idx.search([0.5] * 384, top_k=5)
            assert len(results) == 0
        finally:
            try:
                shutil.rmtree(temp)
            except PermissionError:
                pass

    def test_search_includes_text(self, populated_indexer):
        """Test search results include document text."""
        query_embedding = [1.0] + [0.0] * 383
        results = populated_indexer.search(query_embedding, top_k=1)

        assert len(results) > 0
        assert "text" in results[0]


class TestVisualMemoryIndexerGetById:
    """Test get by ID operations."""

    @pytest.fixture
    def indexer_with_doc(self):
        """Create indexer with one document."""
        temp = tempfile.mkdtemp()
        idx = VisualMemoryIndexer(persist_directory=temp)

        idx.add_visual(
            doc_id="test-doc-1",
            embedding=[0.5] * 384,
            metadata={"visual_type": "screenshot", "title": "Test"},
            document="Test document content",
        )

        yield idx

        try:
            shutil.rmtree(temp)
        except PermissionError:
            pass

    def test_get_by_id_existing(self, indexer_with_doc):
        """Test get_by_id for existing document."""
        result = indexer_with_doc.get_by_id("test-doc-1")

        assert result is not None
        assert result["id"] == "test-doc-1"
        assert "metadata" in result
        assert "text" in result

    def test_get_by_id_nonexistent(self, indexer_with_doc):
        """Test get_by_id for nonexistent document."""
        result = indexer_with_doc.get_by_id("nonexistent-doc")

        assert result is None

    def test_get_by_id_includes_metadata(self, indexer_with_doc):
        """Test get_by_id includes metadata."""
        result = indexer_with_doc.get_by_id("test-doc-1")

        assert result["metadata"]["visual_type"] == "screenshot"
        assert result["metadata"]["title"] == "Test"


class TestVisualMemoryIndexerDelete:
    """Test delete operations."""

    @pytest.fixture
    def indexer_with_docs(self):
        """Create indexer with multiple documents."""
        temp = tempfile.mkdtemp()
        idx = VisualMemoryIndexer(persist_directory=temp)

        for i in range(3):
            idx.add_visual(
                doc_id=f"doc-{i}",
                embedding=[0.5] * 384,
                metadata={"visual_type": "screenshot"},
                document=f"Document {i}",
            )

        yield idx

        try:
            shutil.rmtree(temp)
        except PermissionError:
            pass

    def test_delete_existing(self, indexer_with_docs):
        """Test deleting existing document."""
        initial_count = indexer_with_docs.count()

        result = indexer_with_docs.delete("doc-0")

        assert result == True
        assert indexer_with_docs.count() == initial_count - 1

    def test_delete_nonexistent(self, indexer_with_docs):
        """Test deleting nonexistent document."""
        initial_count = indexer_with_docs.count()

        result = indexer_with_docs.delete("nonexistent")

        # ChromaDB doesn't error on deleting nonexistent
        assert indexer_with_docs.count() == initial_count

    def test_delete_makes_unfindable(self, indexer_with_docs):
        """Test deleted document is no longer findable."""
        indexer_with_docs.delete("doc-0")

        result = indexer_with_docs.get_by_id("doc-0")

        assert result is None


class TestVisualMemoryIndexerUpdateMetadata:
    """Test metadata update operations."""

    @pytest.fixture
    def indexer_with_doc(self):
        """Create indexer with one document."""
        temp = tempfile.mkdtemp()
        idx = VisualMemoryIndexer(persist_directory=temp)

        idx.add_visual(
            doc_id="test-doc-1",
            embedding=[0.5] * 384,
            metadata={"visual_type": "screenshot", "title": "Original"},
            document="Test document",
        )

        yield idx

        try:
            shutil.rmtree(temp)
        except PermissionError:
            pass

    def test_update_metadata(self, indexer_with_doc):
        """Test updating metadata."""
        result = indexer_with_doc.update_metadata(
            "test-doc-1", {"visual_type": "diagram", "title": "Updated"}
        )

        assert result == True

        doc = indexer_with_doc.get_by_id("test-doc-1")
        assert doc["metadata"]["title"] == "Updated"


class TestVisualMemoryIndexerGetInfo:
    """Test get_info method."""

    def test_get_info_contains_required_fields(self):
        """Test get_info returns required fields."""
        temp = tempfile.mkdtemp()
        try:
            idx = VisualMemoryIndexer(persist_directory=temp)
            info = idx.get_info()

            assert "collection_name" in info
            assert "persist_directory" in info
            assert "count" in info
        finally:
            try:
                shutil.rmtree(temp)
            except PermissionError:
                pass


class TestVisualMemoryIndexerMetadataCleaning:
    """Test metadata cleaning for ChromaDB compatibility."""

    @pytest.fixture
    def indexer(self):
        """Create indexer."""
        temp = tempfile.mkdtemp()
        idx = VisualMemoryIndexer(persist_directory=temp)
        yield idx
        try:
            shutil.rmtree(temp)
        except PermissionError:
            pass

    def test_clean_metadata_preserves_primitives(self, indexer):
        """Test that primitive types are preserved."""
        metadata = {
            "str_val": "hello",
            "int_val": 42,
            "float_val": 3.14,
            "bool_val": True,
        }

        cleaned = indexer._clean_metadata(metadata)

        assert cleaned["str_val"] == "hello"
        assert cleaned["int_val"] == 42
        assert cleaned["float_val"] == 3.14
        assert cleaned["bool_val"] == True

    def test_clean_metadata_flattens_nested_dict(self, indexer):
        """Test that nested dicts are flattened."""
        metadata = {"agent": {"name": "test", "version": "1.0"}}

        cleaned = indexer._clean_metadata(metadata)

        assert "agent.name" in cleaned
        assert cleaned["agent.name"] == "test"
        assert cleaned["agent.version"] == "1.0"

    def test_clean_metadata_handles_none(self, indexer):
        """Test that None values become empty strings."""
        metadata = {"value": None}

        cleaned = indexer._clean_metadata(metadata)

        assert cleaned["value"] == ""

    def test_clean_metadata_converts_other_types(self, indexer):
        """Test that other types are converted to strings."""
        metadata = {"list_val": [1, 2, 3]}

        cleaned = indexer._clean_metadata(metadata)

        assert cleaned["list_val"] == "[1, 2, 3]"
