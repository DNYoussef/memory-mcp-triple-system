"""
Vector Search Tool Implementation
Implements vector similarity search using semantic chunking and embeddings.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from typing import List, Dict, Any
from loguru import logger

from ...chunking.semantic_chunker import SemanticChunker
from ...indexing.embedding_pipeline import EmbeddingPipeline
from ...indexing.vector_indexer import VectorIndexer, resolve_persist_dir


def _require_config_section(config: Dict[str, Any], section: str) -> None:
    """Validate required config without relying on assert statements."""
    if not isinstance(config, dict) or section not in config:
        raise ValueError(f"Missing {section} config")


def _validate_search_request(query: str, limit: int) -> None:
    """Validate vector-search request under normal and optimized Python."""
    if not isinstance(query, str) or len(query) == 0:
        raise ValueError("Query cannot be empty")
    if not isinstance(limit, int):
        raise ValueError("Limit must be an integer")
    if limit <= 0:
        raise ValueError("Limit must be positive")
    if limit > 100:
        raise ValueError("Limit too large (max 100)")


class VectorSearchTool:
    """Vector search tool for MCP server."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize vector search tool.

        Args:
            config: System configuration dictionary
        """
        _require_config_section(config, 'embeddings')
        _require_config_section(config, 'storage')

        self.config = config

        # Initialize components (lazy loading for offline mode)
        self._chunker = None
        self._embedder = None
        self._indexer = None

        logger.info("VectorSearchTool initialized")

    @property
    def chunker(self) -> SemanticChunker:
        """Lazy load semantic chunker."""
        if self._chunker is None:
            chunking_config = self.config.get('chunking', {})
            self._chunker = SemanticChunker(
                min_chunk_size=chunking_config.get('min_chunk_size', 128),
                max_chunk_size=chunking_config.get('max_chunk_size', 512),
                overlap=chunking_config.get('overlap', 50)
            )
        return self._chunker

    @property
    def embedder(self) -> EmbeddingPipeline:
        """Lazy load embedding pipeline."""
        if self._embedder is None:
            embedding_config = self.config.get('embeddings', {})
            model = embedding_config.get('model', 'all-MiniLM-L6-v2')
            # Extract model name if full path provided
            if '/' in model:
                model = model.split('/')[-1]
            self._embedder = EmbeddingPipeline(model_name=model)
        return self._embedder

    @property
    def indexer(self) -> VectorIndexer:
        """Lazy load vector indexer."""
        if self._indexer is None:
            vector_config = self.config['storage']['vector_db']
            # Single resolver so stdio and HTTP open the same store. Env
            # (CHROMA_PERSIST_DIR / MEMORY_MCP_DATA_DIR) wins over the config
            # default, matching service_wiring._get_data_dir precedence.
            persist_directory = resolve_persist_dir(
                default=vector_config.get('persist_directory') or '/data/chroma'
            )
            self._indexer = VectorIndexer.get_instance(
                persist_directory=persist_directory,
                collection_name=vector_config.get('collection_name', 'memory_chunks')
            )
        return self._indexer

    def check_services(self) -> Dict[str, str]:
        """
        Check availability of dependent services.

        Returns:
            Dictionary of service statuses
        """
        services = {
            'chromadb': 'unknown',
            'embeddings': 'unknown'
        }

        # Check ChromaDB
        try:
            self.indexer.client.heartbeat()
            services['chromadb'] = 'available'
        except Exception as e:
            logger.warning(f"ChromaDB unavailable: {e}")
            services['chromadb'] = 'unavailable'

        # Check embeddings
        try:
            # Test with probe text
            _ = self.embedder.encode_single("test")
            services['embeddings'] = 'available'
        except Exception as e:
            logger.warning(f"Embeddings unavailable: {e}")
            services['embeddings'] = 'unavailable'

        return services

    def execute(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Execute vector search.

        Args:
            query: Search query text
            limit: Number of results

        Returns:
            List of search results with scores
        """
        _validate_search_request(query, limit)

        logger.info(f"Vector search: '{query}' (limit={limit})")

        # Generate query embedding
        query_embedding = self.embedder.encode_single(query)

        # Search ChromaDB
        search_results = self.indexer.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=limit
        )

        # Format results (ChromaDB returns dict with lists)
        results = []
        if search_results['ids'] and len(search_results['ids'][0]) > 0:
            for i in range(len(search_results['ids'][0])):
                metadata = search_results['metadatas'][0][i]
                # Chroma collection uses cosine distance: distance = 1 - cosine.
                distance = search_results['distances'][0][i]
                similarity = max(0.0, min(1.0, 1.0 - distance))

                results.append({
                    'text': search_results['documents'][0][i],
                    'file_path': metadata.get('file_path', ''),
                    'chunk_index': metadata.get('chunk_index', 0),
                    'score': similarity,
                    'metadata': {
                        k: v for k, v in metadata.items()
                        if k not in ['file_path', 'chunk_index']
                    }
                })

        logger.info(f"Found {len(results)} results")
        return results
