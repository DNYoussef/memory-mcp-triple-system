"""
Semantic Chunker using Max-Min algorithm
Creates semantically coherent chunks from markdown.

Implements sentence-level semantic similarity detection to find
natural topic boundaries. Merges sentences between boundaries
into coherent chunks while respecting size constraints.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import re
import numpy as np
from loguru import logger


class SemanticChunker:
    """Chunks markdown files semantically."""

    def __init__(
        self,
        min_chunk_size: int = 128,
        max_chunk_size: int = 512,
        overlap: int = 50,
        similarity_threshold: float = 0.5,
        embedding_pipeline: Optional[Any] = None
    ):
        """
        Initialize semantic chunker with Max-Min algorithm.

        Args:
            min_chunk_size: Minimum chunk size in tokens
            max_chunk_size: Maximum chunk size in tokens
            overlap: Overlap between chunks in tokens
            similarity_threshold: Cosine similarity threshold for boundaries
            embedding_pipeline: Optional pre-initialized embedding pipeline
        """
        assert min_chunk_size > 0, "Min chunk size must be positive"
        assert max_chunk_size > min_chunk_size, "Max must be > min"
        assert 0 <= overlap < min_chunk_size, "Invalid overlap"
        assert 0.0 <= similarity_threshold <= 1.0, "Threshold must be 0-1"

        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.similarity_threshold = similarity_threshold
        self._embedding_pipeline = embedding_pipeline
        self._use_semantic = True  # Enable semantic chunking by default

        logger.info(
            f"SemanticChunker initialized: {min_chunk_size}-{max_chunk_size} "
            f"tokens, overlap={overlap}, similarity_threshold={similarity_threshold}"
        )

    @property
    def embedding_pipeline(self) -> Optional[Any]:
        """Lazy load embedding pipeline for semantic similarity."""
        if self._embedding_pipeline is None and self._use_semantic:
            try:
                from ..indexing.embedding_pipeline import EmbeddingPipeline
                self._embedding_pipeline = EmbeddingPipeline()
                logger.info("EmbeddingPipeline loaded for semantic chunking")
            except Exception as e:
                logger.warning(f"Could not load EmbeddingPipeline: {e}")
                self._use_semantic = False
        return self._embedding_pipeline

    def chunk_text(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Chunk text content directly.

        Args:
            content: Text content to chunk
            file_path: File path for metadata

        Returns:
            List of chunk dictionaries with metadata
        """
        assert len(content) > 0, "Content cannot be empty"

        metadata = self._extract_frontmatter(content)
        text = self._remove_frontmatter(content)

        chunks = self._split_into_chunks(text)

        result = []
        for idx, chunk_text in enumerate(chunks):
            result.append({
                'text': chunk_text,
                'file_path': file_path,
                'chunk_index': idx,
                'metadata': metadata
            })

        logger.info(f"Created {len(result)} chunks from {file_path}")
        return result

    def chunk_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Chunk markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            List of chunk dictionaries with metadata
        """
        assert file_path.exists(), f"File not found: {file_path}"

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return self.chunk_text(content, str(file_path))

    def _extract_frontmatter(self, content: str) -> Dict[str, Any]:
        """Extract YAML frontmatter from markdown."""
        frontmatter_pattern = r'^---\n(.*?)\n---\n'
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            return {}

        # Simple key:value parsing (not full YAML)
        metadata = {}
        for line in match.group(1).split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()

        return metadata

    def _remove_frontmatter(self, content: str) -> str:
        """Remove frontmatter from content."""
        frontmatter_pattern = r'^---\n.*?\n---\n'
        return re.sub(frontmatter_pattern, '', content, flags=re.DOTALL)

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences for semantic analysis."""
        # Split on sentence boundaries
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        raw_sentences = re.split(sentence_pattern, text)

        # Filter and clean sentences
        sentences = []
        for sent in raw_sentences:
            cleaned = sent.strip()
            if len(cleaned) > 10:  # Minimum sentence length
                sentences.append(cleaned)

        return sentences

    def _compute_sentence_similarities(
        self,
        sentences: List[str]
    ) -> List[float]:
        """Compute cosine similarity between adjacent sentences."""
        if len(sentences) < 2 or not self.embedding_pipeline:
            return [1.0] * (len(sentences) - 1)

        try:
            # Get embeddings for all sentences
            embeddings = self.embedding_pipeline.encode(sentences)

            # Compute cosine similarity between adjacent sentences
            similarities = []
            for i in range(len(embeddings) - 1):
                vec1 = embeddings[i]
                vec2 = embeddings[i + 1]
                # Cosine similarity
                dot = np.dot(vec1, vec2)
                norm = np.linalg.norm(vec1) * np.linalg.norm(vec2)
                sim = dot / norm if norm > 0 else 0.0
                similarities.append(float(sim))

            return similarities

        except Exception as e:
            logger.warning(f"Similarity computation failed: {e}")
            return [1.0] * (len(sentences) - 1)

    def _find_semantic_boundaries(
        self,
        similarities: List[float]
    ) -> List[int]:
        """Find boundary positions where similarity drops below threshold."""
        boundaries = []
        for i, sim in enumerate(similarities):
            if sim < self.similarity_threshold:
                boundaries.append(i + 1)  # Boundary after sentence i
        return boundaries

    def _merge_sentences_into_chunks(
        self,
        sentences: List[str],
        boundaries: List[int]
    ) -> List[str]:
        """Merge sentences between boundaries into chunks."""
        if not sentences:
            return []

        # Add start and end boundaries
        all_boundaries = [0] + boundaries + [len(sentences)]
        all_boundaries = sorted(set(all_boundaries))

        chunks = []
        for i in range(len(all_boundaries) - 1):
            start = all_boundaries[i]
            end = all_boundaries[i + 1]
            chunk_sentences = sentences[start:end]
            chunk_text = ' '.join(chunk_sentences)

            # Respect size constraints
            chunk_tokens = len(chunk_text.split())
            if chunk_tokens > self.max_chunk_size:
                # Split large chunk further
                sub_chunks = self._split_large_chunk(chunk_text)
                chunks.extend(sub_chunks)
            elif chunk_tokens >= self.min_chunk_size:
                chunks.append(chunk_text)
            else:
                # Small chunk - merge with previous if possible
                if chunks:
                    prev_tokens = len(chunks[-1].split())
                    if prev_tokens + chunk_tokens <= self.max_chunk_size:
                        chunks[-1] = chunks[-1] + ' ' + chunk_text
                        continue
                chunks.append(chunk_text)

        return chunks

    def _split_large_chunk(self, text: str) -> List[str]:
        """Split a chunk that exceeds max_chunk_size."""
        words = text.split()
        chunks = []
        current = []
        current_size = 0

        for word in words:
            if current_size + 1 > self.max_chunk_size:
                chunks.append(' '.join(current))
                current = [word]
                current_size = 1
            else:
                current.append(word)
                current_size += 1

        if current:
            chunks.append(' '.join(current))

        return chunks

    def _split_into_chunks(self, text: str) -> List[str]:
        """
        Split text into semantic chunks using Max-Min algorithm.

        Algorithm:
        1. Split text into sentences
        2. Compute embedding similarity between adjacent sentences
        3. Find boundaries where similarity drops below threshold
        4. Merge sentences between boundaries into chunks
        5. Enforce min/max size constraints
        """
        # Step 1: Split into sentences
        sentences = self._split_into_sentences(text)

        if len(sentences) <= 1:
            return [text] if text.strip() else []

        # Step 2: Compute similarities (if semantic enabled)
        if self._use_semantic and self.embedding_pipeline:
            similarities = self._compute_sentence_similarities(sentences)
            # Step 3: Find semantic boundaries
            boundaries = self._find_semantic_boundaries(similarities)
            logger.debug(f"Found {len(boundaries)} semantic boundaries")
        else:
            # Fallback: use paragraph boundaries
            boundaries = self._find_paragraph_boundaries(sentences, text)

        # Step 4 & 5: Merge with size constraints
        chunks = self._merge_sentences_into_chunks(sentences, boundaries)

        logger.info(
            f"Semantic chunking: {len(sentences)} sentences -> {len(chunks)} chunks"
        )

        return chunks

    def _find_paragraph_boundaries(
        self,
        sentences: List[str],
        original_text: str
    ) -> List[int]:
        """Fallback: find boundaries at paragraph breaks."""
        boundaries = []
        cumulative = 0

        for i, sent in enumerate(sentences):
            cumulative += len(sent)
            # Check if there's a paragraph break after this sentence
            pos = original_text.find(sent)
            if pos != -1:
                end_pos = pos + len(sent)
                if end_pos < len(original_text) - 2:
                    next_chars = original_text[end_pos:end_pos + 3]
                    if '\n\n' in next_chars:
                        boundaries.append(i + 1)

        return boundaries
