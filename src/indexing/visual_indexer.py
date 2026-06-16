"""
Visual Memory Indexer for ChromaDB.

MEM-QWEN-005: ChromaDB collection specifically for visual memories.
Separate from text memory collection to allow different schemas.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger


class VisualMemoryIndexer:
    """
    ChromaDB indexer for visual memories.

    Maintains a separate collection from text memories to support
    different embedding dimensions and metadata schemas.
    """

    DEFAULT_COLLECTION = "visual_memories"

    def __init__(
        self,
        persist_directory: str = "./chroma_visual",
        collection_name: Optional[str] = None,
    ):
        """
        Initialize visual memory indexer.

        Args:
            persist_directory: ChromaDB persistence path
            collection_name: Collection name (default: visual_memories)
        """
        import chromadb

        self.persist_directory = persist_directory
        self.collection_name = collection_name or self.DEFAULT_COLLECTION

        # Ensure directory exists
        Path(persist_directory).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name, metadata={"hnsw:space": "cosine"}
        )

        logger.info(
            f"VisualMemoryIndexer initialized: collection={self.collection_name}, "
            f"persist={persist_directory}, count={self.count()}"
        )

    def add_visual(
        self,
        doc_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        document: str = "",
    ) -> str:
        """
        Add a visual memory to the index.

        Args:
            doc_id: Unique document ID
            embedding: Multimodal embedding vector
            metadata: Metadata dict (must include visual_type, image_path)
            document: Optional text description

        Returns:
            Document ID
        """
        # Ensure metadata values are ChromaDB-compatible (str, int, float, bool)
        clean_metadata = self._clean_metadata(metadata)

        self._collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[clean_metadata],
            documents=[document],
        )

        logger.debug(f"Added visual memory: {doc_id}")
        return doc_id

    def _clean_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Convert metadata values to ChromaDB-compatible types."""
        clean = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                clean[key] = value
            elif isinstance(value, dict):
                # Flatten nested dicts with dot notation
                for k, v in value.items():
                    if isinstance(v, (str, int, float, bool)):
                        clean[f"{key}.{k}"] = v
            elif value is None:
                clean[key] = ""
            else:
                clean[key] = str(value)
        return clean

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        where: Optional[Dict] = None,
        include: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search visual memories by embedding similarity.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results
            where: Optional metadata filter
            include: Fields to include in results

        Returns:
            List of matching visual memories
        """
        include = include or ["documents", "metadatas", "distances"]

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=include,
            )
        except Exception as e:
            logger.error(f"Visual search failed: {e}")
            return []

        return self._format_results(results, include)

    def _format_results(
        self, results: Dict, include: List[str]
    ) -> List[Dict[str, Any]]:
        """Format ChromaDB results into standard dict format."""
        formatted = []

        if not results.get("ids") or not results["ids"][0]:
            return formatted

        for i in range(len(results["ids"][0])):
            item = {
                "id": results["ids"][0][i],
                "score": 1.0 - results["distances"][0][i]
                if "distances" in include
                else 0.0,
            }

            if "documents" in include and results.get("documents"):
                item["text"] = results["documents"][0][i]

            if "metadatas" in include and results.get("metadatas"):
                item["metadata"] = results["metadatas"][0][i]

            formatted.append(item)

        return formatted

    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a visual memory by ID."""
        try:
            result = self._collection.get(
                ids=[doc_id], include=["documents", "metadatas", "embeddings"]
            )
            # Check if we got results (handle both list and numpy array)
            ids = result.get("ids", [])
            if ids is not None and len(ids) > 0:
                # Extract values first to avoid numpy array boolean evaluation
                docs = result.get("documents")
                metas = result.get("metadatas")
                embs = result.get("embeddings")
                return {
                    "id": ids[0],
                    "text": docs[0] if docs is not None and len(docs) > 0 else "",
                    "metadata": metas[0]
                    if metas is not None and len(metas) > 0
                    else {},
                    "embedding": list(embs[0])
                    if embs is not None and len(embs) > 0
                    else [],
                }
        except Exception as e:
            logger.error(f"Get by ID failed: {e}")
        return None

    def delete(self, doc_id: str) -> bool:
        """Delete a visual memory by ID."""
        try:
            self._collection.delete(ids=[doc_id])
            logger.debug(f"Deleted visual memory: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    def update_metadata(self, doc_id: str, metadata: Dict[str, Any]) -> bool:
        """Update metadata for a visual memory."""
        try:
            clean_metadata = self._clean_metadata(metadata)
            self._collection.update(ids=[doc_id], metadatas=[clean_metadata])
            return True
        except Exception as e:
            logger.error(f"Metadata update failed: {e}")
            return False

    def count(self) -> int:
        """Get total count of visual memories."""
        return self._collection.count()

    def get_info(self) -> Dict[str, Any]:
        """Get indexer info."""
        return {
            "collection_name": self.collection_name,
            "persist_directory": self.persist_directory,
            "count": self.count(),
        }
