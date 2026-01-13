"""
Vector Indexer for ChromaDB
Indexes text chunks with embeddings into ChromaDB embedded vector database.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import List, Dict, Any, Optional, Tuple
import uuid
import time
import sqlite3
import threading
import chromadb
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)


# Retry decorator for database operations that may encounter locks
def db_retry(func):
    """Decorator to retry database operations on lock errors."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, max=2),
        retry=retry_if_exception_type((sqlite3.OperationalError, Exception)),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True
    )(func)


class VectorIndexer:
    """Manages vector indexing in ChromaDB (embedded)."""

    _instances: Dict[Tuple[str, str], "VectorIndexer"] = {}
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(
        cls,
        persist_directory: str = "./chroma_data",
        collection_name: str = "memory_chunks"
    ) -> "VectorIndexer":
        """Return a shared VectorIndexer instance for given configuration."""
        key = (persist_directory, collection_name)
        if key not in cls._instances:
            with cls._instance_lock:
                if key not in cls._instances:
                    cls._instances[key] = cls(
                        persist_directory=persist_directory,
                        collection_name=collection_name
                    )
        return cls._instances[key]

    def __init__(
        self,
        persist_directory: str = "./chroma_data",
        collection_name: str = "memory_chunks"
    ):
        """
        Initialize vector indexer with ChromaDB.

        Args:
            persist_directory: Directory to persist ChromaDB data
            collection_name: Collection name
        """
        assert isinstance(persist_directory, str), "persist_directory must be string"
        assert isinstance(collection_name, str), "collection_name must be string"

        self.persist_directory = persist_directory
        self.collection_name = collection_name

        # Initialize ChromaDB client with persistence (new API)
        self.client = chromadb.PersistentClient(path=persist_directory)

        # Initialize collection immediately (fixes VectorIndexer bug)
        self.create_collection()

        logger.info(f"Initialized ChromaDB at {persist_directory}")

    def create_collection(self, vector_size: int = 384) -> None:
        """
        Create collection if it doesn't exist.

        Args:
            vector_size: Embedding dimension (used for validation)
        """
        assert vector_size > 0, "vector_size must be positive"

        try:
            self.collection = self.client.get_collection(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' already exists")
        except Exception:
            # Collection doesn't exist, create it with optimized HNSW parameters
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={
                    "hnsw:space": "cosine",           # Cosine similarity
                    "hnsw:construction_ef": 100,      # Build-time accuracy
                    "hnsw:search_ef": 100,            # Query-time accuracy
                    "hnsw:M": 16                      # Max connections per node
                }
            )
            logger.info(f"Created collection '{self.collection_name}'")

    @db_retry
    def index_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> None:
        """
        Index chunks with embeddings. Retries on database lock.

        Args:
            chunks: List of chunk dictionaries
            embeddings: List of embedding vectors
        """
        assert len(chunks) == len(embeddings), "Mismatched lengths"
        assert len(chunks) > 0, "Empty chunks list"

        # Prepare data for ChromaDB batch add
        ids = [str(uuid.uuid4()) for _ in chunks]
        documents = [chunk['text'] for chunk in chunks]
        metadatas = [
            {
                'file_path': chunk['file_path'],
                'chunk_index': chunk['chunk_index'],
                **chunk.get('metadata', {})
            }
            for chunk in chunks
        ]

        # Add to ChromaDB collection with performance tracking
        start = time.perf_counter()
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(f"Indexed {len(chunks)} chunks in {elapsed_ms:.2f}ms")      

    @db_retry
    def add_document(
        self,
        doc_id: str,
        text: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a single document with a known ID.

        Args:
            doc_id: Document identifier
            text: Document text
            embedding: Embedding vector
            metadata: Optional metadata

        Returns:
            True if added, False otherwise
        """
        if not doc_id or not text:
            raise ValueError("doc_id and text are required")
        if not embedding:
            raise ValueError("embedding cannot be empty")

        try:
            self.collection.add(
                ids=[doc_id],
                documents=[text],
                embeddings=[embedding],
                metadatas=[metadata or {}]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add document {doc_id}: {e}")
            return False

    @db_retry
    def add_documents(
        self,
        docs: List[Dict[str, Any]]
    ) -> bool:
        """
        Add multiple documents with explicit IDs.

        Args:
            docs: List of dicts with id, text, embedding, metadata

        Returns:
            True if added, False otherwise
        """
        if not docs:
            return True

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        for doc in docs:
            doc_id = doc.get("id")
            text = doc.get("text")
            embedding = doc.get("embedding")
            if not doc_id or not text or not embedding:
                raise ValueError("Each doc requires id, text, and embedding")
            ids.append(str(doc_id))
            documents.append(text)
            embeddings.append(embedding)
            metadatas.append(doc.get("metadata", {}))

        try:
            self.collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return False

    @db_retry
    def delete_chunks(self, ids: List[str]) -> bool:
        """
        Delete chunks by IDs from the collection. Retries on database lock.

        Args:
            ids: List of chunk IDs to delete

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            if not ids:
                logger.warning("Empty IDs list provided for deletion")
                return True  # No-op is successful

            self.collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} chunks from ChromaDB")
            return True

        except Exception as e:
            logger.error(f"Failed to delete chunks: {e}")
            return False

    @db_retry
    def update_chunks(
        self,
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None
    ) -> bool:
        """
        Update existing chunks. Retries on database lock.

        Args:
            ids: List of chunk IDs to update
            embeddings: Optional new embeddings
            metadatas: Optional new metadata
            documents: Optional new document texts

        Returns:
            True if update successful, False otherwise
        """
        try:
            if not ids:
                logger.warning("Empty IDs list provided for update")
                return True  # No-op is successful

            # Build update parameters
            update_params = {'ids': ids}
            if embeddings is not None:
                update_params['embeddings'] = embeddings
            if metadatas is not None:
                update_params['metadatas'] = metadatas
            if documents is not None:
                update_params['documents'] = documents

            self.collection.update(**update_params)
            logger.info(f"Updated {len(ids)} chunks in ChromaDB")
            return True

        except Exception as e:
            logger.error(f"Failed to update chunks: {e}")
            return False

    @db_retry
    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks. Retries on database lock.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            where: Optional metadata filter (ChromaDB where clause)

        Returns:
            List of result dictionaries with 'id', 'document', 'metadata', 'distance'
        """
        assert top_k > 0, "top_k must be positive"
        assert len(query_embedding) > 0, "query_embedding cannot be empty"

        # Query ChromaDB with optional metadata filtering
        query_params = {
            'query_embeddings': [query_embedding],
            'n_results': top_k
        }
        if where is not None:
            query_params['where'] = where

        results = self.collection.query(**query_params)

        # Format results
        formatted_results = []
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                'id': results['ids'][0][i],
                'document': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i]
            })

        return formatted_results

    @db_retry
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents and return normalized scores.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results
            where: Optional metadata filter

        Returns:
            List of result dicts with id, text, metadata, score
        """
        results = self.search_similar(query_embedding, top_k=top_k, where=where)
        formatted = []
        for result in results:
            distance = result.get("distance", 0.0) or 0.0
            similarity = max(0.0, min(1.0, 1.0 - (distance / 2.0)))
            formatted.append({
                "id": result.get("id"),
                "text": result.get("document", ""),
                "metadata": result.get("metadata", {}),
                "score": similarity
            })
        return formatted
