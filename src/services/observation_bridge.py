"""Bridge between observation capture and memory retrieval tiers.

When an observation is stored in KVStore, this bridge:
1. Indexes content into vector tier (if ChromaDB available)
2. Extracts entities for graph tier (via NER)
3. Logs to KV for structured queries

This is the connect point that makes captured observations findable.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import json
import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from loguru import logger

# Privacy tag regex -- redacts <private>...</private> content before storage
_PRIVATE_RE = re.compile(r"<private>.*?</private>", re.DOTALL)

from ..stores.kv_store import KVStore
from ..models.observation_types import Observation, classify_tool


class ObservationBridge:
    """Bridges observation capture to memory retrieval tiers."""

    def __init__(
        self,
        kv_store: KVStore,
        vector_indexer: Optional[Any] = None,
        graph_service: Optional[Any] = None,
        entity_extractor: Optional[Any] = None,
    ):
        """Initialize bridge with storage backends.

        Args:
            kv_store: KVStore for structured observation storage
            vector_indexer: VectorIndexer for semantic search (optional)
            graph_service: GraphService for entity graph (optional)
            entity_extractor: NER service for entity extraction (optional)
        """
        self.kv_store = kv_store
        self.vector_indexer = vector_indexer
        self.graph_service = graph_service
        self.entity_extractor = entity_extractor

    def capture_tool_use(
        self,
        session_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_result: str,
        is_error: bool = False,
        project: str = "",
    ) -> Optional[Observation]:
        """Capture a tool invocation as an observation.

        This is the main entry point called by PostToolUse hooks.

        Args:
            session_id: Current session ID
            tool_name: Name of the tool that was invoked
            tool_input: Tool input parameters
            tool_result: Tool output (truncated if needed)
            is_error: Whether the tool call resulted in an error
            project: Current project name

        Returns:
            Created Observation, or None if deduped/skipped
        """
        # Build content summary (truncated for storage)
        content = self._build_content(tool_name, tool_input, tool_result)

        # Dedup: skip if identical content exists in this session
        content_hash = hashlib.md5(content.encode()).hexdigest()
        if self.kv_store.observation_exists(session_id, content):
            return None

        # Classify
        obs_type = classify_tool(tool_name, is_error=is_error)

        # Create observation
        obs = Observation(
            session_id=session_id,
            obs_type=obs_type,
            tool_name=tool_name,
            content=content,
            metadata={
                "tool_input_keys": list(tool_input.keys()) if tool_input else [],
                "is_error": is_error,
                "content_hash": content_hash,
            },
            project=project,
        )

        # Extract entities if NER available
        if self.entity_extractor:
            try:
                obs.entities = self._extract_entities(content)
            except Exception as e:
                logger.debug(f"Entity extraction skipped: {e}")

        # Store in KVStore (structured tier)
        self.kv_store.store_observation(obs.to_dict())

        # Increment session tool count
        self.kv_store.increment_tool_count(session_id)

        # Index into vector tier (background-safe)
        self._index_to_vector(obs)

        # Index into graph tier
        self._index_to_graph(obs)

        return obs

    def _build_content(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_result: str,
    ) -> str:
        """Build a concise content string from tool invocation.

        Truncates to ~500 chars to keep observation storage lean.
        """
        parts = [f"{tool_name}:"]

        # Extract key info from input
        if tool_name in ("Read", "Glob", "Grep"):
            path = tool_input.get("file_path") or tool_input.get("path", "")
            pattern = tool_input.get("pattern", "")
            if path:
                parts.append(path)
            if pattern:
                parts.append(f"pattern={pattern}")
        elif tool_name in ("Write", "Edit"):
            path = tool_input.get("file_path", "")
            parts.append(path)
        elif tool_name == "Bash":
            cmd = tool_input.get("command", "")[:200]
            parts.append(cmd)
        elif tool_name == "Task":
            desc = tool_input.get("description", "")
            parts.append(desc)
        else:
            # Generic: just list the keys
            parts.append(str(list(tool_input.keys()))[:100])

        # Append truncated result
        result_preview = tool_result[:200].replace("\n", " ") if tool_result else ""
        if result_preview:
            parts.append(f"-> {result_preview}")

        raw = " ".join(parts)[:500]
        return _PRIVATE_RE.sub("[REDACTED]", raw)

    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text using NER service."""
        if not self.entity_extractor:
            return []
        try:
            result = self.entity_extractor.extract(text)
            return [e["text"] for e in result if "text" in e][:10]
        except Exception:
            return []

    def _index_to_vector(self, obs: Observation) -> None:
        """Index observation into vector tier for semantic search."""
        if not self.vector_indexer:
            return
        try:
            from ..indexing.vector_indexer import CHROMADB_AVAILABLE
            if not CHROMADB_AVAILABLE:
                return
            # Use add_document with observation ID
            # Embedding will be generated by the pipeline
            # For now, store as a document that can be embedded later
            self.kv_store.set(
                f"obs:pending_embed:{obs.observation_id}",
                obs.content,
                ttl=86400,  # 24h TTL for pending embeddings
            )
        except Exception as e:
            logger.debug(f"Vector indexing skipped: {e}")

    def _index_to_graph(self, obs: Observation) -> None:
        """Index observation entities into knowledge graph."""
        if not self.graph_service or not obs.entities:
            return
        try:
            for entity in obs.entities:
                self.graph_service.add_node(
                    entity,
                    node_type="entity",
                    metadata={
                        "source": "observation",
                        "session_id": obs.session_id,
                        "obs_type": obs.obs_type.value,
                    },
                )
        except Exception as e:
            logger.debug(f"Graph indexing skipped: {e}")

    def get_recent_observations(
        self,
        project: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get recent observations for context injection."""
        return self.kv_store.get_observations(project=project, limit=limit)

    def get_session_observations(
        self, session_id: str
    ) -> List[Dict[str, Any]]:
        """Get all observations for a specific session."""
        return self.kv_store.get_observations(
            session_id=session_id, limit=500
        )
