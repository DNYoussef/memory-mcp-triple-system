# Visual Memory Sidecar - Architecture Design

**MEM-QWEN-004: Visual Memory Sidecar Design**
**Version**: 1.0.0
**Status**: DESIGN
**Last Updated**: 2026-01-18

---

## Executive Summary

Visual Memory Sidecar extends Memory MCP Triple System with multimodal capabilities for screenshots, diagrams, and visual content. It operates as a **separate collection** alongside the existing text-based memory system, enabling cross-modal search (text queries retrieving images).

**Key Design Principles**:
- **Non-invasive**: No modifications to existing text-based architecture
- **Separate collection**: Visual memories in dedicated ChromaDB collection
- **Unified search**: Single API to query both text and visual memories
- **Hardware-aware**: ~8GB VRAM requirement for Qwen3-VL-Embedding-2B

---

## Architecture Overview

```
+------------------------------------------------------------------+
|                     MEMORY MCP TRIPLE SYSTEM                      |
+------------------------------------------------------------------+
|                                                                   |
|  +--------------------+                                           |
|  |   MCP INTERFACE    |  <-- Claude Desktop / Claude Code         |
|  |   (stdio_server)   |                                           |
|  +--------+-----------+                                           |
|           |                                                       |
|           v                                                       |
|  +--------------------+     +------------------------+            |
|  |  NEXUS PROCESSOR   |     | VISUAL MEMORY SIDECAR  |            |
|  |  (text memories)   |<--->|   (visual memories)    |            |
|  +--------+-----------+     +----------+-------------+            |
|           |                            |                          |
|     +-----+-----+-----+               |                          |
|     |     |     |     |               |                          |
|     v     v     v     v               v                          |
|  +------+---+---+---+---+     +----------------+                 |
|  |VECTOR|HIP|BAY|RERANK|     | VISUAL INDEXER |                 |
|  | TIER |RAG|ESI|     |     | (ChromaDB)     |                 |
|  +------+---+---+-----+     +----------------+                 |
|  Chroma  NX  pgm  CE         visual_memories                    |
|                                                                   |
+------------------------------------------------------------------+
```

---

## Component Design

### 1. Qwen3VLEmbedder

**Purpose**: Generate multimodal embeddings for images and text using Qwen3-VL-Embedding-2B.

**File**: `src/services/qwen3vl_embedder.py`

```python
class Qwen3VLEmbedder:
    """
    Multimodal embedding using Qwen3-VL-Embedding-2B.

    Model: Qwen/Qwen3-VL-Embedding-2B
    Dimensions: 2048 (native), 384 (MRL truncated)
    VRAM: ~8GB
    """

    MODEL_NAME = "Qwen/Qwen3-VL-Embedding-2B"
    NATIVE_DIM = 2048
    MRL_DIM = 384  # Matryoshka truncation for compatibility

    def __init__(
        self,
        model_name: str = None,
        device: str = None,
        use_mrl: bool = True,
        target_dim: int = 384
    ):
        """
        Initialize Qwen3-VL embedder.

        Args:
            model_name: HuggingFace model name (default: Qwen3-VL-Embedding-2B)
            device: 'cuda' or 'cpu' (auto-detect if None)
            use_mrl: Use Matryoshka truncation for dimension reduction
            target_dim: Target dimension when using MRL (default: 384)
        """
        self.model_name = model_name or self.MODEL_NAME
        self._model = None
        self._processor = None
        self._device = device
        self.use_mrl = use_mrl
        self.target_dim = target_dim if use_mrl else self.NATIVE_DIM

    @property
    def device(self) -> str:
        """Lazy device detection."""
        if self._device is None:
            import torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        return self._device

    @property
    def model(self):
        """Lazy model loading."""
        if self._model is None:
            self._load_model()
        return self._model

    def _load_model(self) -> None:
        """Load Qwen3-VL model and processor."""
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

        self._processor = AutoProcessor.from_pretrained(self.model_name)
        self._model = Qwen2VLForConditionalGeneration.from_pretrained(
            self.model_name,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            device_map="auto"
        )

    def embed_image(self, image_path: str) -> List[float]:
        """
        Generate embedding for an image.

        Args:
            image_path: Path to image file

        Returns:
            Embedding vector (target_dim dimensions)
        """
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self._processor(images=image, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.get_image_features(**inputs)
            embedding = outputs[0].cpu().numpy().tolist()

        if self.use_mrl:
            embedding = embedding[:self.target_dim]

        return embedding

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for text query.

        Args:
            text: Query text

        Returns:
            Embedding vector (target_dim dimensions)
        """
        inputs = self._processor(text=text, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.get_text_features(**inputs)
            embedding = outputs[0].cpu().numpy().tolist()

        if self.use_mrl:
            embedding = embedding[:self.target_dim]

        return embedding

    def embed_multimodal(self, image_path: str, caption: str) -> List[float]:
        """
        Generate joint embedding for image+text.

        Args:
            image_path: Path to image file
            caption: Associated text/caption

        Returns:
            Joint embedding vector
        """
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self._processor(
            images=image,
            text=caption,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            # Pool image and text features
            embedding = outputs.last_hidden_state.mean(dim=1)[0].cpu().numpy().tolist()

        if self.use_mrl:
            embedding = embedding[:self.target_dim]

        return embedding

    def get_info(self) -> Dict[str, Any]:
        """Get embedder configuration info."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "native_dim": self.NATIVE_DIM,
            "target_dim": self.target_dim,
            "use_mrl": self.use_mrl,
            "loaded": self._model is not None
        }
```

---

### 2. VisualMemoryIndexer

**Purpose**: ChromaDB collection specifically for visual memories.

**File**: `src/indexing/visual_indexer.py`

```python
class VisualMemoryIndexer:
    """
    ChromaDB indexer for visual memories.

    Separate from text memory collection to allow different
    embedding dimensions and metadata schemas.
    """

    COLLECTION_NAME = "visual_memories"

    def __init__(
        self,
        persist_directory: str = "./chroma_visual",
        collection_name: str = None
    ):
        """
        Initialize visual memory indexer.

        Args:
            persist_directory: ChromaDB persistence path
            collection_name: Collection name (default: visual_memories)
        """
        import chromadb

        self.persist_directory = persist_directory
        self.collection_name = collection_name or self.COLLECTION_NAME

        self._client = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_visual(
        self,
        doc_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        document: str = ""
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
        self._collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[document]
        )
        return doc_id

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        where: Dict = None,
        include: List[str] = None
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

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=include
        )

        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i] if "documents" in results else "",
                "metadata": results["metadatas"][0][i] if "metadatas" in results else {},
                "score": 1.0 - results["distances"][0][i] if "distances" in results else 0.0
            })

        return formatted

    def delete(self, doc_id: str) -> bool:
        """Delete a visual memory by ID."""
        try:
            self._collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def count(self) -> int:
        """Get total count of visual memories."""
        return self._collection.count()

    def get_info(self) -> Dict[str, Any]:
        """Get indexer info."""
        return {
            "collection_name": self.collection_name,
            "persist_directory": self.persist_directory,
            "count": self.count()
        }
```

---

### 3. VisualMemoryService

**Purpose**: High-level service for ingesting and searching visual memories.

**File**: `src/services/visual_memory_service.py`

```python
class VisualMemoryService:
    """
    High-level service for visual memory operations.

    Combines Qwen3-VL embedder with ChromaDB indexer for
    screenshot/diagram ingestion and cross-modal search.
    """

    # Visual memory types
    VISUAL_TYPES = ["screenshot", "diagram", "photo", "chart", "ui_element"]

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

    def ingest_screenshot(
        self,
        image_path: str,
        title: str = "",
        context: str = "",
        metadata: Dict[str, Any] = None
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
        metadata: Dict[str, Any] = None
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

    def _ingest_visual(
        self,
        image_path: str,
        visual_type: str,
        title: str,
        context: str,
        metadata: Dict[str, Any]
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
        import uuid
        import time
        from pathlib import Path

        if not self.enabled:
            return {"success": False, "error": "Visual memory service disabled"}

        # Validate image exists
        if not Path(image_path).exists():
            return {"success": False, "error": f"Image not found: {image_path}"}

        # Generate embedding
        start_time = time.time()

        if context:
            # Joint image+text embedding
            embedding = self.embedder.embed_multimodal(image_path, context)
        else:
            # Image-only embedding
            embedding = self.embedder.embed_image(image_path)

        embed_time = time.time() - start_time

        # Prepare metadata
        doc_id = str(uuid.uuid4())
        full_metadata = {
            "visual_type": visual_type,
            "image_path": str(Path(image_path).absolute()),
            "title": title,
            "context": context,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "embedding_dim": len(embedding),
            **(metadata or {})
        }

        # WHO/WHEN/PROJECT/WHY tagging
        if "agent" not in full_metadata:
            full_metadata["agent"] = {"name": "visual_memory_service", "version": "1.0.0"}
        if "project" not in full_metadata:
            full_metadata["project"] = "memory-mcp"
        if "intent" not in full_metadata:
            full_metadata["intent"] = "visual_ingestion"

        # Store in index
        document_text = f"[{visual_type.upper()}] {title}: {context}"
        self.indexer.add_visual(
            doc_id=doc_id,
            embedding=embedding,
            metadata=full_metadata,
            document=document_text
        )

        return {
            "success": True,
            "doc_id": doc_id,
            "visual_type": visual_type,
            "embedding_dim": len(embedding),
            "embed_time_ms": int(embed_time * 1000)
        }

    def search_visual(
        self,
        query: str,
        top_k: int = 10,
        visual_type: str = None
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

        # Build filter
        where = None
        if visual_type:
            where = {"visual_type": visual_type}

        # Search
        results = self.indexer.search(
            query_embedding=query_embedding,
            top_k=top_k,
            where=where
        )

        return results

    def delete_visual(self, doc_id: str) -> bool:
        """Delete a visual memory by ID."""
        return self.indexer.delete(doc_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get visual memory statistics."""
        return {
            "enabled": self.enabled,
            "total_visuals": self.indexer.count(),
            "embedder": self.embedder.get_info(),
            "indexer": self.indexer.get_info()
        }
```

---

### 4. UnifiedSearchRouter

**Purpose**: Single API to search both text and visual memories.

**File**: `src/services/unified_search_router.py`

```python
class UnifiedSearchRouter:
    """
    Unified search across text and visual memories.

    Routes queries to appropriate backends and merges results.
    """

    def __init__(
        self,
        nexus_processor: "NexusProcessor",
        visual_memory_service: "VisualMemoryService" = None,
        visual_weight: float = 0.3
    ):
        """
        Initialize unified search router.

        Args:
            nexus_processor: Text memory NexusProcessor
            visual_memory_service: Visual memory service (optional)
            visual_weight: Weight for visual results in unified search
        """
        self.nexus_processor = nexus_processor
        self.visual_service = visual_memory_service
        self.visual_weight = visual_weight
        self.text_weight = 1.0 - visual_weight

    def search(
        self,
        query: str,
        mode: str = "execution",
        top_k: int = 10,
        include_visual: bool = True,
        include_text: bool = True
    ) -> Dict[str, Any]:
        """
        Unified search across all memory types.

        Args:
            query: Search query
            mode: Query mode (execution, planning, brainstorming)
            top_k: Total number of results
            include_visual: Include visual memories
            include_text: Include text memories

        Returns:
            Unified search results with text and visual sections
        """
        results = {
            "query": query,
            "mode": mode,
            "text_results": [],
            "visual_results": [],
            "unified_results": []
        }

        # Calculate per-source limits
        text_k = int(top_k * 0.7) if include_visual else top_k
        visual_k = top_k - text_k if include_visual else 0

        # Text search via NexusProcessor
        if include_text:
            text_results = self.nexus_processor.process(
                query=query,
                mode=mode,
                top_k=text_k
            )
            results["text_results"] = text_results.get("core", []) + text_results.get("extended", [])

        # Visual search
        if include_visual and self.visual_service and self.visual_service.enabled:
            visual_results = self.visual_service.search_visual(
                query=query,
                top_k=visual_k
            )
            results["visual_results"] = visual_results

        # Merge and rank unified results
        results["unified_results"] = self._merge_results(
            text_results=results["text_results"],
            visual_results=results["visual_results"],
            top_k=top_k
        )

        return results

    def _merge_results(
        self,
        text_results: List[Dict],
        visual_results: List[Dict],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Merge and rank text and visual results.

        Args:
            text_results: Results from NexusProcessor
            visual_results: Results from VisualMemoryService
            top_k: Number of results to return

        Returns:
            Merged and ranked results
        """
        merged = []

        # Add text results with source tag
        for result in text_results:
            merged.append({
                "source": "text",
                "score": result.get("score", 0) * self.text_weight,
                "original_score": result.get("score", 0),
                **result
            })

        # Add visual results with source tag
        for result in visual_results:
            merged.append({
                "source": "visual",
                "score": result.get("score", 0) * self.visual_weight,
                "original_score": result.get("score", 0),
                **result
            })

        # Sort by weighted score
        merged.sort(key=lambda x: x["score"], reverse=True)

        return merged[:top_k]

    def search_visual_only(
        self,
        query: str,
        top_k: int = 10,
        visual_type: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search only visual memories.

        Args:
            query: Text query
            top_k: Number of results
            visual_type: Optional filter (screenshot, diagram, etc.)

        Returns:
            Visual memory results
        """
        if not self.visual_service or not self.visual_service.enabled:
            return []

        return self.visual_service.search_visual(
            query=query,
            top_k=top_k,
            visual_type=visual_type
        )

    def get_info(self) -> Dict[str, Any]:
        """Get router configuration info."""
        return {
            "text_weight": self.text_weight,
            "visual_weight": self.visual_weight,
            "visual_enabled": bool(self.visual_service and self.visual_service.enabled),
            "visual_stats": self.visual_service.get_stats() if self.visual_service else None
        }
```

---

## MCP Tool Extensions

### New MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `ingest_screenshot` | Ingest screenshot to visual memory | image_path, title, context, metadata |
| `ingest_diagram` | Ingest diagram to visual memory | image_path, title, context, metadata |
| `search_visual` | Search visual memories | query, top_k, visual_type |
| `unified_search` | Search text + visual memories | query, mode, top_k, include_visual |

### Tool Definitions

```python
# src/mcp/tools/visual_memory_tools.py

VISUAL_MEMORY_TOOLS = [
    {
        "name": "ingest_screenshot",
        "description": "Ingest a screenshot into visual memory for later retrieval",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Path to screenshot image file"
                },
                "title": {
                    "type": "string",
                    "description": "Title/label for the screenshot"
                },
                "context": {
                    "type": "string",
                    "description": "Contextual description of the screenshot"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata (project, intent, etc.)"
                }
            },
            "required": ["image_path"]
        }
    },
    {
        "name": "ingest_diagram",
        "description": "Ingest a diagram into visual memory for later retrieval",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Path to diagram image file"
                },
                "title": {
                    "type": "string",
                    "description": "Title/label for the diagram"
                },
                "context": {
                    "type": "string",
                    "description": "Contextual description of the diagram"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                }
            },
            "required": ["image_path"]
        }
    },
    {
        "name": "search_visual",
        "description": "Search visual memories with a text query (cross-modal)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text search query"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results (default: 10)",
                    "default": 10
                },
                "visual_type": {
                    "type": "string",
                    "enum": ["screenshot", "diagram", "photo", "chart", "ui_element"],
                    "description": "Filter by visual type"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "unified_search",
        "description": "Search both text and visual memories",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "mode": {
                    "type": "string",
                    "enum": ["execution", "planning", "brainstorming"],
                    "default": "execution"
                },
                "top_k": {
                    "type": "integer",
                    "default": 10
                },
                "include_visual": {
                    "type": "boolean",
                    "default": true
                },
                "include_text": {
                    "type": "boolean",
                    "default": true
                }
            },
            "required": ["query"]
        }
    }
]
```

---

## Configuration Extensions

### memory-mcp.yaml additions

```yaml
# Visual Memory Sidecar Configuration
visual_memory:
  enabled: true

  # Qwen3-VL Embedder
  embedder:
    model_name: Qwen/Qwen3-VL-Embedding-2B
    device: auto  # cuda or cpu (auto-detect)
    use_mrl: true  # Matryoshka dimension reduction
    target_dim: 384  # Match text embedding dimension

  # Visual ChromaDB Collection
  indexer:
    persist_directory: ./chroma_visual
    collection_name: visual_memories

  # Unified Search
  router:
    visual_weight: 0.3  # Weight for visual results
    text_weight: 0.7    # Weight for text results
    default_include_visual: true
```

---

## Data Flow

### Screenshot Ingestion Flow

```
1. User calls ingest_screenshot(image_path, title, context)
   |
2. VisualMemoryService validates image exists
   |
3. Qwen3VLEmbedder generates multimodal embedding
   |-- If context: embed_multimodal(image, context)
   |-- Else: embed_image(image)
   |
4. MRL truncation: 2048d -> 384d
   |
5. VisualMemoryIndexer stores in ChromaDB
   |-- Collection: visual_memories
   |-- Metadata: visual_type, image_path, title, context, WHO/WHEN/PROJECT/WHY
   |
6. Return doc_id and stats
```

### Cross-Modal Search Flow

```
1. User calls search_visual(query="architecture diagram")
   |
2. Qwen3VLEmbedder generates text embedding
   |-- embed_text(query) -> 384d vector
   |
3. VisualMemoryIndexer searches ChromaDB
   |-- Cosine similarity against visual embeddings
   |
4. Return top-K images with scores and metadata
```

### Unified Search Flow

```
1. User calls unified_search(query, mode, include_visual=True)
   |
2. UnifiedSearchRouter splits query
   |
   +-- NexusProcessor (text) --> text_results
   |
   +-- VisualMemoryService (visual) --> visual_results
   |
3. Merge results with weights
   |-- text_score * 0.7 + visual_score * 0.3
   |
4. Sort by unified score, return top-K
```

---

## Hardware Requirements

| Component | VRAM | Notes |
|-----------|------|-------|
| Qwen3-VL-Embedding-2B | ~8GB | FP16 inference |
| ChromaDB (visual) | ~500MB | Depends on collection size |
| **Total** | ~8.5GB | Minimum for visual memory |

**Fallback**: If VRAM insufficient, service disables gracefully and logs warning.

---

## File Structure

```
src/
|-- services/
|   |-- qwen3vl_embedder.py      # NEW: Multimodal embedder
|   |-- visual_memory_service.py  # NEW: Visual memory service
|   |-- unified_search_router.py  # NEW: Unified search API
|   |-- reranker_service.py       # Existing (MEM-QWEN-002)
|-- indexing/
|   |-- visual_indexer.py         # NEW: ChromaDB for visuals
|   |-- vector_indexer.py         # Existing (text)
|-- mcp/
|   |-- tools/
|   |   |-- visual_memory_tools.py # NEW: MCP tool definitions
|   |-- service_wiring.py          # UPDATE: Wire visual services
|   |-- stdio_server.py            # UPDATE: Register new tools
```

---

## Integration Points

### 1. Service Wiring Update

```python
# src/mcp/service_wiring.py additions

from ..services.qwen3vl_embedder import Qwen3VLEmbedder
from ..services.visual_memory_service import VisualMemoryService
from ..indexing.visual_indexer import VisualMemoryIndexer
from ..services.unified_search_router import UnifiedSearchRouter

class NexusSearchTool:
    def _init_visual_memory(self, config: Dict[str, Any]) -> None:
        """Initialize visual memory sidecar if enabled."""
        visual_config = config.get('visual_memory', {})

        if not visual_config.get('enabled', False):
            self.visual_service = None
            self.unified_router = None
            return

        try:
            # Initialize embedder
            embedder_config = visual_config.get('embedder', {})
            self.qwen_embedder = Qwen3VLEmbedder(
                model_name=embedder_config.get('model_name'),
                device=embedder_config.get('device'),
                use_mrl=embedder_config.get('use_mrl', True),
                target_dim=embedder_config.get('target_dim', 384)
            )

            # Initialize indexer
            indexer_config = visual_config.get('indexer', {})
            self.visual_indexer = VisualMemoryIndexer(
                persist_directory=indexer_config.get('persist_directory', './chroma_visual'),
                collection_name=indexer_config.get('collection_name', 'visual_memories')
            )

            # Initialize service
            self.visual_service = VisualMemoryService(
                embedder=self.qwen_embedder,
                indexer=self.visual_indexer,
                enabled=True
            )

            # Initialize unified router
            router_config = visual_config.get('router', {})
            self.unified_router = UnifiedSearchRouter(
                nexus_processor=self.nexus_processor,
                visual_memory_service=self.visual_service,
                visual_weight=router_config.get('visual_weight', 0.3)
            )

            logger.info("Visual Memory Sidecar initialized")

        except Exception as e:
            logger.warning(f"Visual memory init failed (disabled): {e}")
            self.visual_service = None
            self.unified_router = None
```

### 2. stdio_server.py Tool Registration

```python
# Add to TOOL_DEFINITIONS list
TOOL_DEFINITIONS.extend(VISUAL_MEMORY_TOOLS)

# Add to tool handlers
async def handle_ingest_screenshot(arguments):
    return search_tool.visual_service.ingest_screenshot(**arguments)

async def handle_search_visual(arguments):
    return search_tool.visual_service.search_visual(**arguments)

async def handle_unified_search(arguments):
    return search_tool.unified_router.search(**arguments)
```

---

## Testing Strategy (MEM-QWEN-006 Preview)

### Unit Tests

1. **Qwen3VLEmbedder Tests**
   - Initialization with different configs
   - Image embedding generation
   - Text embedding generation
   - Multimodal embedding generation
   - MRL truncation
   - Device detection

2. **VisualMemoryIndexer Tests**
   - Add visual memory
   - Search by embedding
   - Filter by visual_type
   - Delete visual memory
   - Count operations

3. **VisualMemoryService Tests**
   - Screenshot ingestion
   - Diagram ingestion
   - Cross-modal search
   - Metadata handling
   - WHO/WHEN/PROJECT/WHY tagging

4. **UnifiedSearchRouter Tests**
   - Merged search results
   - Weight application
   - Visual-only search
   - Text-only search

### Integration Tests

1. **End-to-end screenshot flow**
2. **Cross-modal retrieval accuracy**
3. **MCP tool invocation**
4. **Configuration loading**

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| VRAM insufficient | Medium | High | Graceful disable, CPU fallback |
| Model download failure | Low | Medium | Retry logic, offline mode |
| Embedding dimension mismatch | Low | High | Validate on startup |
| Visual search latency | Medium | Medium | Batch processing, caching |
| Collection corruption | Low | High | Backup, health checks |

---

## Success Criteria

1. **Functional**: Screenshots and diagrams can be ingested and retrieved
2. **Cross-modal**: Text queries return relevant images
3. **Non-invasive**: Existing text memory unchanged
4. **Performance**: Visual search <500ms for top-10
5. **Reliability**: Graceful degradation if visual service unavailable

---

## Next Steps (MEM-QWEN-005)

1. Implement `Qwen3VLEmbedder` class
2. Implement `VisualMemoryIndexer` class
3. Implement `VisualMemoryService` class
4. Implement `UnifiedSearchRouter` class
5. Wire into `service_wiring.py`
6. Register MCP tools in `stdio_server.py`
7. Update `memory-mcp.yaml` with visual config

---

**Design Status**: COMPLETE
**Ready for Implementation**: YES
**Estimated Implementation Time**: 16-20 hours
