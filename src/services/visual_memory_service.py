"""
Visual Memory Service for Screenshot and Diagram Management.

MEM-QWEN-005: High-level service for ingesting and searching visual memories.
Combines Qwen3-VL embedder with ChromaDB indexer for cross-modal search.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import uuid
import time
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path
from loguru import logger

if TYPE_CHECKING:
    from .qwen3vl_embedder import Qwen3VLEmbedder
    from ..indexing.visual_indexer import VisualMemoryIndexer


class VisualMemoryService:
    """
    High-level service for visual memory operations.

    Combines Qwen3-VL embedder with ChromaDB indexer for
    screenshot/diagram ingestion and cross-modal search.
    """

    # Supported visual memory types
    VISUAL_TYPES = ["screenshot", "diagram", "photo", "chart", "ui_element", "other"]

    def __init__(
        self,
        embedder: "Qwen3VLEmbedder",
        indexer: "VisualMemoryIndexer",
        enabled: bool = True
    ):
        """
        Initialize visual memory service.

        Args:
            embedder: Qwen3-VL embedder instance
            indexer: Visual memory indexer instance
            enabled: Enable/disable service
        """
        self.embedder = embedder
        self.indexer = indexer
        self.enabled = enabled

        logger.info(f"VisualMemoryService initialized: enabled={enabled}")

    def ingest_screenshot(
        self,
        image_path: str,
        title: str = "",
        context: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest a screenshot into visual memory.

        Args:
            image_path: Path to screenshot image
            title: Screenshot title/label
            context: Contextual description
            metadata: Additional metadata

        Returns:
            Ingestion result with doc_id
        """
        return self._ingest_visual(
            image_path=image_path,
            visual_type="screenshot",
            title=title,
            context=context,
            metadata=metadata
        )

    def ingest_diagram(
        self,
        image_path: str,
        title: str = "",
        context: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest a diagram into visual memory.

        Args:
            image_path: Path to diagram image
            title: Diagram title/label
            context: Contextual description
            metadata: Additional metadata

        Returns:
            Ingestion result with doc_id
        """
        return self._ingest_visual(
            image_path=image_path,
            visual_type="diagram",
            title=title,
            context=context,
            metadata=metadata
        )

    def ingest_visual(
        self,
        image_path: str,
        visual_type: str = "other",
        title: str = "",
        context: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest any visual type into memory.

        Args:
            image_path: Path to image file
            visual_type: Type of visual (screenshot, diagram, photo, etc.)
            title: Title/label
            context: Contextual description
            metadata: Additional metadata

        Returns:
            Ingestion result with doc_id
        """
        if visual_type not in self.VISUAL_TYPES:
            visual_type = "other"

        return self._ingest_visual(
            image_path=image_path,
            visual_type=visual_type,
            title=title,
            context=context,
            metadata=metadata
        )

    def _ingest_visual(
        self,
        image_path: str,
        visual_type: str,
        title: str,
        context: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Internal method to ingest any visual type.

        Args:
            image_path: Path to image file
            visual_type: Type of visual (screenshot, diagram, etc.)
            title: Title/label
            context: Contextual description
            metadata: Additional metadata

        Returns:
            Ingestion result
        """
        if not self.enabled:
            return {"success": False, "error": "Visual memory service disabled"}

        # Validate image exists
        path = Path(image_path)
        if not path.exists():
            return {"success": False, "error": f"Image not found: {image_path}"}

        # Generate embedding
        start_time = time.time()
        embedding = self._generate_embedding(image_path, context)
        embed_time = time.time() - start_time

        if not embedding or all(v == 0.0 for v in embedding):
            return {"success": False, "error": "Embedding generation failed"}

        # Prepare metadata with WHO/WHEN/PROJECT/WHY
        doc_id = str(uuid.uuid4())
        full_metadata = self._build_metadata(
            visual_type=visual_type,
            image_path=str(path.absolute()),
            title=title,
            context=context,
            embedding_dim=len(embedding),
            extra_metadata=metadata
        )

        # Store in index
        document_text = f"[{visual_type.upper()}] {title}: {context}".strip()
        self.indexer.add_visual(
            doc_id=doc_id,
            embedding=embedding,
            metadata=full_metadata,
            document=document_text
        )

        logger.info(f"Ingested {visual_type}: {doc_id} ({embed_time*1000:.0f}ms)")

        return {
            "success": True,
            "doc_id": doc_id,
            "visual_type": visual_type,
            "embedding_dim": len(embedding),
            "embed_time_ms": int(embed_time * 1000)
        }

    def _generate_embedding(
        self,
        image_path: str,
        context: str
    ) -> List[float]:
        """Generate embedding using appropriate method."""
        if context:
            return self.embedder.embed_multimodal(image_path, context)
        return self.embedder.embed_image(image_path)

    def _build_metadata(
        self,
        visual_type: str,
        image_path: str,
        title: str,
        context: str,
        embedding_dim: int,
        extra_metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build full metadata with WHO/WHEN/PROJECT/WHY tagging."""
        metadata = {
            "visual_type": visual_type,
            "image_path": image_path,
            "title": title,
            "context": context,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "embedding_dim": embedding_dim,
        }

        # Merge extra metadata
        if extra_metadata:
            metadata.update(extra_metadata)

        # WHO/WHEN/PROJECT/WHY defaults
        if "agent.name" not in metadata and "agent" not in metadata:
            metadata["agent.name"] = "visual_memory_service"
            metadata["agent.version"] = "1.0.0"
        if "project" not in metadata:
            metadata["project"] = "memory-mcp"
        if "intent" not in metadata:
            metadata["intent"] = "visual_ingestion"

        return metadata

    def search_visual(
        self,
        query: str,
        top_k: int = 10,
        visual_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search visual memories with text query.

        Cross-modal search: text query retrieves relevant images.

        Args:
            query: Text search query
            top_k: Number of results
            visual_type: Optional filter by visual type

        Returns:
            List of matching visual memories
        """
        if not self.enabled:
            return []

        # Generate text embedding for query
        query_embedding = self.embedder.embed_text(query)

        if not query_embedding or all(v == 0.0 for v in query_embedding):
            logger.warning("Query embedding generation failed")
            return []

        # Build filter
        where = None
        if visual_type and visual_type in self.VISUAL_TYPES:
            where = {"visual_type": visual_type}

        # Search
        results = self.indexer.search(
            query_embedding=query_embedding,
            top_k=top_k,
            where=where
        )

        logger.debug(f"Visual search '{query}': {len(results)} results")
        return results

    def get_visual(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a visual memory by ID."""
        return self.indexer.get_by_id(doc_id)

    def delete_visual(self, doc_id: str) -> bool:
        """Delete a visual memory by ID."""
        return self.indexer.delete(doc_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get visual memory statistics."""
        return {
            "enabled": self.enabled,
            "total_visuals": self.indexer.count(),
            "embedder": self.embedder.get_info(),
            "indexer": self.indexer.get_info(),
            "visual_types": self.VISUAL_TYPES
        }
