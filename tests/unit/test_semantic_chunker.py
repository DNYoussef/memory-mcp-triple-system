"""
Unit tests for SemanticChunker
Following TDD (London School) with proper test structure.
"""

import pytest
from pathlib import Path
from src.chunking.semantic_chunker import SemanticChunker


class TestSemanticChunker:
    """Test suite for SemanticChunker."""

    @pytest.fixture
    def chunker(self):
        """Create chunker instance."""
        return SemanticChunker(
            min_chunk_size=128,
            max_chunk_size=512,
            overlap=50
        )

    @pytest.fixture
    def sample_markdown(self, tmp_path):
        """Create sample markdown file."""
        content = """---
title: Test Document
tags: [test, sample]
date: 2025-01-01
---

# Introduction

This is a test document with multiple paragraphs.

## Section 1

This is the first section. It contains some text that will be chunked.

The chunker should split this into semantic units.

## Section 2

This is another section with different content.

It should be processed correctly."""

        file_path = tmp_path / "test.md"
        file_path.write_text(content, encoding='utf-8')
        return file_path

    def test_initialization(self, chunker):
        """Test chunker initialization."""
        assert chunker.min_chunk_size == 128
        assert chunker.max_chunk_size == 512
        assert chunker.overlap == 50

    def test_initialization_invalid_params(self):
        """Test initialization with invalid parameters."""
        with pytest.raises(AssertionError):
            SemanticChunker(min_chunk_size=0)

        with pytest.raises(AssertionError):
            SemanticChunker(min_chunk_size=200, max_chunk_size=100)

    def test_chunk_file(self, chunker, sample_markdown):
        """Test chunking a markdown file."""
        chunks = chunker.chunk_file(sample_markdown)

        assert len(chunks) > 0
        assert all('text' in chunk for chunk in chunks)
        assert all('file_path' in chunk for chunk in chunks)
        assert all('chunk_index' in chunk for chunk in chunks)

    def test_extract_frontmatter(self, chunker, sample_markdown):
        """Test frontmatter extraction."""
        chunks = chunker.chunk_file(sample_markdown)

        # Verify metadata extracted
        metadata = chunks[0]['metadata']
        assert 'title' in metadata
        assert metadata['title'] == 'Test Document'

    def test_remove_frontmatter(self, chunker, sample_markdown):
        """Test frontmatter removal."""
        chunks = chunker.chunk_file(sample_markdown)

        # Verify frontmatter not in text
        for chunk in chunks:
            assert '---' not in chunk['text']
            assert 'title:' not in chunk['text']

    def test_file_not_found(self, chunker):
        """Test handling of non-existent file."""
        with pytest.raises(AssertionError):
            chunker.chunk_file(Path("/nonexistent/file.md"))
