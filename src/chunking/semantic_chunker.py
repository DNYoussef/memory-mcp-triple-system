"""
Semantic Chunker using Max-Min algorithm
Creates semantically coherent chunks from markdown.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from typing import List, Dict, Any
from pathlib import Path
import re
from loguru import logger


class SemanticChunker:
    """Chunks markdown files semantically."""

    def __init__(
        self,
        min_chunk_size: int = 128,
        max_chunk_size: int = 512,
        overlap: int = 50
    ):
        """
        Initialize chunker.

        Args:
            min_chunk_size: Minimum chunk size in tokens
            max_chunk_size: Maximum chunk size in tokens
            overlap: Overlap between chunks in tokens
        """
        assert min_chunk_size > 0, "Min chunk size must be positive"
        assert max_chunk_size > min_chunk_size, "Max must be > min"
        assert 0 <= overlap < min_chunk_size, "Invalid overlap"

        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

        logger.info(
            f"Chunker initialized: {min_chunk_size}-{max_chunk_size} "
            f"tokens, overlap={overlap}"
        )

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

    def _split_into_chunks(self, text: str) -> List[str]:
        """Split text into semantic chunks."""
        # Simple paragraph-based chunking
        # TODO: Implement Max-Min semantic chunking algorithm
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_tokens = len(para.split())

            if current_size + para_tokens > self.max_chunk_size:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [para]
                current_size = para_tokens
            else:
                current_chunk.append(para)
                current_size += para_tokens

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks
