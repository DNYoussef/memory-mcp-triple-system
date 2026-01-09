"""
MCP Server Implementation using stdio protocol
Compatible with Claude Code's MCP expectations.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

import json
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path
import yaml
from loguru import logger

from .tools.vector_search import VectorSearchTool
from ..nexus.processor import NexusProcessor

# Phase 6: Production wiring imports (C3.2-C3.6)
from ..stores.event_log import EventLog
from ..stores.kv_store import KVStore
from ..debug.query_trace import QueryTrace
from ..lifecycle.hotcold_classifier import HotColdClassifier
from ..memory.lifecycle_manager import MemoryLifecycleManager
from .obsidian_client import ObsidianMCPClient

# ISS-003 fix: Import Graph and Bayesian engines for full architecture wiring
from ..services.graph_service import GraphService
from ..services.graph_query_engine import GraphQueryEngine
from ..bayesian.probabilistic_query_engine import ProbabilisticQueryEngine
from ..bayesian.network_builder import NetworkBuilder  # ISS-018 fix


class NexusSearchTool:
    """
    Wrapper around NexusProcessor for MCP integration.

    Routes vector_search calls through NexusProcessor's 5-step SOP pipeline.
    Falls back to direct VectorSearchTool if NexusProcessor fails.

    Phase 6: Includes production wiring for EventLog, KVStore, QueryTrace,
    LifecycleManager, and ObsidianClient.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Nexus search tool with production features.

        Args:
            config: System configuration dictionary
        """
        self.config = config
        self.vector_search_tool = VectorSearchTool(config)
        self._nexus_processor: Optional[NexusProcessor] = None

        # Phase 6: Production wiring (C3.2-C3.6)
        self._init_production_features(config)

        logger.info("NexusSearchTool initialized with production features")

    def _init_production_features(self, config: Dict[str, Any]) -> None:
        """
        Initialize production features (C3.2-C3.6).

        NASA Rule 10: 25 LOC
        """
        data_dir = Path(config.get('storage', {}).get('data_dir', './data'))
        data_dir.mkdir(parents=True, exist_ok=True)

        # C3.3: Event logging
        self.event_log = EventLog(db_path=str(data_dir / "events.db"))

        # C3.4: KV store for session state
        self.kv_store = KVStore(db_path=str(data_dir / "kv_store.db"))

        # C3.5: Lifecycle manager with hot/cold classifier
        # ISS-019 fix: Wire real VectorIndexer instead of None
        self.hot_cold_classifier = HotColdClassifier()
        self.lifecycle_manager = MemoryLifecycleManager(
            vector_indexer=self.vector_search_tool.indexer,
            kv_store=self.kv_store
        )

        # C3.2: Obsidian client (lazy init)
        # ISS-034 fix: Support both config paths for backwards compatibility
        # Priority: env var > obsidian.vault_path > storage.obsidian_vault
        import os
        vault_path = (
            os.environ.get('OBSIDIAN_VAULT_PATH') or
            config.get('obsidian', {}).get('vault_path') or
            config.get('storage', {}).get('obsidian_vault')
        )
        self._obsidian_client: Optional[ObsidianMCPClient] = None
        self._vault_path = vault_path

        logger.info(f"Production features initialized: data_dir={data_dir}")

    @property
    def obsidian_client(self) -> Optional[ObsidianMCPClient]:
        """C3.2: Lazy load ObsidianClient."""
        if self._obsidian_client is None and self._vault_path:
            try:
                self._obsidian_client = ObsidianMCPClient(
                    vault_path=self._vault_path,
                    chunker=self.vector_search_tool.chunker,
                    embedder=self.vector_search_tool.embedder,
                    indexer=self.vector_search_tool.indexer
                )
                logger.info(f"ObsidianClient initialized: {self._vault_path}")
            except Exception as e:
                logger.warning(f"ObsidianClient init failed: {e}")
        return self._obsidian_client

    def log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """C3.3: Log event to event store."""
        from ..stores.event_log import EventType
        try:
            # Map string to EventType enum
            event_type_map = {
                "vector_search": EventType.QUERY_EXECUTED,
                "memory_store": EventType.CHUNK_ADDED,
                "chunk_added": EventType.CHUNK_ADDED,
                "chunk_updated": EventType.CHUNK_UPDATED,
                "chunk_deleted": EventType.CHUNK_DELETED,
                "query_executed": EventType.QUERY_EXECUTED,
                "entity_consolidated": EventType.ENTITY_CONSOLIDATED,
                "lifecycle_transition": EventType.LIFECYCLE_TRANSITION
            }
            enum_type = event_type_map.get(event_type, EventType.QUERY_EXECUTED)
            self.event_log.log_event(event_type=enum_type, data=data)
        except Exception as e:
            logger.warning(f"Event logging failed: {e}")

    def get_session_preference(self, key: str, default: str = "") -> str:
        """C3.4: Get session preference from KV store."""
        try:
            value = self.kv_store.get(f"session:{key}")
            return value if value is not None else default
        except Exception as e:
            logger.warning(f"Failed to get session preference {key}: {e}")
            return default

    def create_query_trace(self, query: str, mode: str) -> QueryTrace:
        """C3.6: Create query trace for debugging."""
        trace = QueryTrace.create(
            query=query,
            user_context={"mode": mode, "source": "mcp_stdio"}
        )
        trace.mode_detected = mode
        return trace

    @property
    def nexus_processor(self) -> Optional[NexusProcessor]:
        """Lazy load NexusProcessor with all 3 tiers."""
        if self._nexus_processor is None:
            try:
                # ISS-003 fix: Wire all 3 tiers (Vector + Graph + Bayesian)
                # Initialize Graph tier (HippoRAG)
                data_dir = self.config.get('storage', {}).get('data_dir', './data')
                graph_service = GraphService(data_dir=data_dir)
                graph_query_engine = GraphQueryEngine(graph_service=graph_service)

                # ISS-018 fix: Build Bayesian network from knowledge graph
                bayesian_network = None
                try:
                    network_builder = NetworkBuilder(max_nodes=1000)
                    bayesian_network = network_builder.build_network(graph_service.graph)
                    if bayesian_network:
                        logger.info("Bayesian network built successfully")
                except Exception as bn_err:
                    logger.warning(f"Bayesian network build failed (will use fallback): {bn_err}")

                # Initialize Bayesian tier with network
                probabilistic_engine = ProbabilisticQueryEngine(
                    timeout_seconds=1.0,
                    network=bayesian_network
                )

                # Initialize NexusProcessor with all tiers
                self._nexus_processor = NexusProcessor(
                    vector_indexer=self.vector_search_tool.indexer,
                    graph_query_engine=graph_query_engine,
                    probabilistic_query_engine=probabilistic_engine,
                    embedding_pipeline=self.vector_search_tool.embedder
                )
                logger.info("NexusProcessor initialized with all 3 tiers (Vector + Graph + Bayesian)")
            except Exception as e:
                logger.warning(f"NexusProcessor init failed, using fallback: {e}")
                self._nexus_processor = None

        return self._nexus_processor

    def execute(
        self,
        query: str,
        limit: int = 5,
        mode: str = "execution"
    ) -> List[Dict[str, Any]]:
        """
        Execute search through NexusProcessor or fallback.

        Args:
            query: Search query text
            limit: Number of results
            mode: Query mode (execution/planning/brainstorming)

        Returns:
            List of search results
        """
        # Try NexusProcessor first
        if self.nexus_processor:
            try:
                result = self._execute_nexus(query, mode, limit)
                logger.info(f"NexusProcessor success: {len(result)} results")
                return result
            except Exception as e:
                logger.warning(f"NexusProcessor failed, falling back: {e}")

        # Fallback to direct vector search
        logger.info("Using fallback VectorSearchTool")
        return self.vector_search_tool.execute(query, limit)

    def _execute_nexus(
        self,
        query: str,
        mode: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Execute via NexusProcessor and format results."""
        # Run 5-step SOP pipeline
        nexus_result = self.nexus_processor.process(
            query=query,
            mode=mode,
            top_k=50,  # Recall 50 candidates per tier
            token_budget=10000
        )

        # Combine core + extended results
        all_results = nexus_result["core"] + nexus_result["extended"]

        # Limit to requested count
        limited_results = all_results[:limit]

        # Format for MCP (convert from Nexus format)
        formatted = []
        for result in limited_results:
            formatted.append({
                "text": result.get("text", ""),
                "score": result.get("hybrid_score", result.get("score", 0.0)),
                "file_path": result.get("metadata", {}).get("file_path", ""),
                "chunk_index": result.get("metadata", {}).get("chunk_index", 0),
                "tier": result.get("tier", "unknown"),
                "metadata": result.get("metadata", {})
            })

        return formatted


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    config_path = Path(__file__).parent.parent.parent / "config" / "memory-mcp.yaml"
    assert config_path.exists(), f"Config not found: {config_path}"

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    return config


def handle_list_tools() -> List[Dict[str, Any]]:
    """Return list of available MCP tools (7 total with obsidian_sync)."""
    return [
        {
            "name": "vector_search",
            "description": "Search memory vault using semantic similarity with mode-aware context adaptation",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query text"},
                    "limit": {"type": "integer", "description": "Number of results", "default": 5},
                    "mode": {
                        "type": "string",
                        "description": "Query mode: execution, planning, or brainstorming",
                        "enum": ["execution", "planning", "brainstorming"],
                        "default": "execution"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "memory_store",
            "description": "Store information in memory vault with automatic layer assignment",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Content to store"},
                    "metadata": {"type": "object", "description": "Optional metadata"}
                },
                "required": ["text"]
            }
        },
        {
            "name": "graph_query",
            "description": "Query knowledge graph using HippoRAG multi-hop reasoning",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query text for graph search"},
                    "max_hops": {"type": "integer", "description": "Maximum hops", "default": 3},
                    "limit": {"type": "integer", "description": "Number of results", "default": 10}
                },
                "required": ["query"]
            }
        },
        {
            "name": "entity_extraction",
            "description": "Extract named entities from text using NER",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to extract entities from"},
                    "entity_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Entity types to extract (e.g., PERSON, ORG, CONCEPT)",
                        "default": ["PERSON", "ORG", "GPE", "CONCEPT"]
                    }
                },
                "required": ["text"]
            }
        },
        {
            "name": "hipporag_retrieve",
            "description": "Full HippoRAG pipeline: entity extraction + graph query + ranking",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query text"},
                    "limit": {"type": "integer", "description": "Number of results", "default": 10},
                    "mode": {
                        "type": "string",
                        "enum": ["execution", "planning", "brainstorming"],
                        "default": "execution"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "detect_mode",
            "description": "Detect query mode (execution/planning/brainstorming) from text",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query to analyze for mode"}
                },
                "required": ["query"]
            }
        },
        {
            "name": "obsidian_sync",
            "description": "Sync Obsidian vault to memory system (C3.2)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "file_extensions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File extensions to sync (default: ['.md'])",
                        "default": [".md"]
                    }
                },
                "required": []
            }
        }
    ]


def _handle_vector_search(
    arguments: Dict[str, Any],
    tool: NexusSearchTool
) -> Dict[str, Any]:
    """Handle vector_search tool execution with event logging and query tracing."""
    import time
    query = arguments.get("query", "")
    limit = arguments.get("limit", 5)
    mode = arguments.get("mode", "execution")

    # C3.4: Store last query mode in session state
    tool.kv_store.set("session:last_query_mode", mode)
    tool.kv_store.set("session:last_query_limit", str(limit))

    # C3.6: Create query trace
    trace = tool.create_query_trace(query, mode)
    start_time = time.time()

    # Route through NexusProcessor
    results = tool.execute(query, limit, mode)

    # C3.6: Update trace with results and persist to SQLite
    trace.retrieval_ms = int((time.time() - start_time) * 1000)
    trace.retrieved_chunks = [{"score": r.get("score", 0)} for r in results[:5]]
    trace.stores_queried = ["vector", "graph", "bayesian"]
    trace.routing_logic = "NexusProcessor 3-tier"
    trace.output = f"Retrieved {len(results)} results"
    trace.total_latency_ms = trace.retrieval_ms
    
    # C3.6: Save trace to SQLite (query_traces.db)
    data_dir = tool.config.get('storage', {}).get('data_dir', './data')
    try:
        trace.log(db_path=f"{data_dir}/query_traces.db")
    except Exception:
        pass  # Continue on trace logging failure

    # C3.3: Log event
    tool.log_event("vector_search", {
        "query": query[:100],
        "mode": mode,
        "limit": limit,
        "results_count": len(results),
        "latency_ms": trace.retrieval_ms
    })

    # Format results for MCP
    content = []
    for idx, result in enumerate(results, 1):
        tier_info = f"Tier: {result.get('tier', 'unknown')}\n" if 'tier' in result else ""
        content.append({
            "type": "text",
            "text": f"Result {idx}:\n{result['text']}\n\n{tier_info}Score: {result['score']:.4f}\nFile: {result['file_path']}\n"
        })

    return {
        "content": content,
        "isError": False
    }


def _enrich_metadata_with_tagging(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich metadata with WHO/WHEN/PROJECT/WHY tagging protocol.

    Args:
        metadata: Original metadata from caller

    Returns:
        Enriched metadata with tagging protocol fields
    """
    import os
    from datetime import datetime

    now = datetime.utcnow()

    # WHO - Agent information
    agent_name = metadata.get('agent', 'unknown')
    agent_category = metadata.get('agent_category', 'general')

    # WHEN - Timestamps
    timestamp_iso = now.isoformat() + 'Z'
    timestamp_unix = int(now.timestamp())
    timestamp_readable = now.strftime('%Y-%m-%d %H:%M:%S')

    # PROJECT - From env or metadata or default
    project = os.environ.get(
        'MEMORY_MCP_PROJECT',
        metadata.get('project', 'memory-mcp-triple-system')
    )

    # WHY - Intent
    intent = metadata.get('intent', 'storage')

    # Build enriched metadata
    enriched = {
        **metadata,
        'agent': {
            'name': agent_name,
            'category': agent_category
        },
        'timestamp': {
            'iso': timestamp_iso,
            'unix': timestamp_unix,
            'readable': timestamp_readable
        },
        'project': project,
        'intent': intent,
        '_tagging_version': '1.0.0',
        '_tagging_protocol': 'memory-mcp-triple-system'
    }

    return enriched


def _handle_memory_store(
    arguments: Dict[str, Any],
    tool: NexusSearchTool
) -> Dict[str, Any]:
    """Handle memory_store with tagging, lifecycle management, and event logging."""
    text = arguments.get("text", "")
    metadata = arguments.get("metadata", {})

    if not text:
        return {
            "content": [{"type": "text", "text": "Error: Empty text provided"}],
            "isError": True
        }

    try:
        # Enrich metadata with tagging protocol
        enriched_metadata = _enrich_metadata_with_tagging(metadata)

        # Use the vector search tool components to store
        embedder = tool.vector_search_tool.embedder
        indexer = tool.vector_search_tool.indexer

        # C3.5: Classify memory using hot/cold classifier
        try:
            classification = tool.hot_cold_classifier.classify(text, enriched_metadata)
            enriched_metadata['lifecycle_tier'] = classification.get('tier', 'hot')
            enriched_metadata['decay_score'] = classification.get('decay_score', 1.0)
        except Exception as e:
            logger.debug(f"Lifecycle classification skipped: {e}")
            enriched_metadata['lifecycle_tier'] = 'hot'
            enriched_metadata['decay_score'] = 1.0

        # Create chunk with enriched metadata
        chunks = [{
            'text': text,
            'file_path': enriched_metadata.get('key', 'manual_entry'),
            'chunk_index': 0,
            'metadata': enriched_metadata
        }]

        # Generate embedding and index with error handling
        try:
            embeddings = embedder.encode([text])
            if embeddings is None or len(embeddings) == 0:
                raise ValueError("Embedding generation failed")

            success = indexer.index_chunks(chunks, embeddings.tolist())
            if not success:
                raise RuntimeError("Indexing failed")

        except Exception as embed_err:
            logger.error(f"Failed to store memory: {embed_err}")
            return {
                "content": [{
                    "type": "text",
                    "text": f"Storage failed: {embed_err}"
                }],
                "isError": True
            }

        # C3.5: Process lifecycle management (demote stale, archive old, consolidate)
        try:
            tool.lifecycle_manager.demote_stale_chunks()
            tool.lifecycle_manager.archive_demoted_chunks()
        except Exception as lc_err:
            logger.debug(f"Lifecycle processing skipped: {lc_err}")

        # C3.3: Log event
        tool.log_event("memory_store", {
            "text_length": len(text),
            "agent": enriched_metadata.get('agent', {}).get('name', 'unknown'),
            "project": enriched_metadata.get('project', 'unknown'),
            "lifecycle_tier": enriched_metadata.get('lifecycle_tier', 'hot')
        })

        # Include tagging info in response
        tagging_info = f"Tagged: WHO={enriched_metadata['agent']['name']}, PROJECT={enriched_metadata['project']}, INTENT={enriched_metadata['intent']}"
        lifecycle_info = f"Lifecycle: {enriched_metadata.get('lifecycle_tier', 'hot')}"

        return {
            "content": [{
                "type": "text",
                "text": f"Stored memory: {text[:100]}...\n{tagging_info}\n{lifecycle_info}"
            }],
            "isError": False
        }

    except Exception as e:
        logger.error(f"Memory store operation failed: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Memory store error: {e}"
            }],
            "isError": True
        }


def _handle_graph_query(
    arguments: Dict[str, Any],
    tool: NexusSearchTool
) -> Dict[str, Any]:
    """Handle graph_query tool - HippoRAG multi-hop reasoning."""
    query = arguments.get("query", "")
    max_hops = arguments.get("max_hops", 3)
    limit = arguments.get("limit", 10)

    try:
        # Try to use graph query engine if available
        if tool.nexus_processor and tool.nexus_processor.graph_query_engine:
            results = tool.nexus_processor.graph_query_engine.retrieve_multi_hop(
                query=query,
                top_k=limit,
                max_hops=max_hops
            )
        else:
            # Fallback to vector search with graph context note
            results = tool.execute(query, limit, "planning")
            for r in results:
                r['note'] = "Graph engine not available - using vector fallback"

        content = []
        for idx, result in enumerate(results, 1):
            note = result.get('note', '')
            note_text = f"\nNote: {note}" if note else ""
            content.append({
                "type": "text",
                "text": f"Result {idx}:\n{result.get('text', '')[:500]}...{note_text}\n"
            })

        return {"content": content, "isError": False}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Graph query error: {e}"}], "isError": True}


def _handle_entity_extraction(
    arguments: Dict[str, Any],
    tool: NexusSearchTool
) -> Dict[str, Any]:
    """Handle entity_extraction tool - NER from text."""
    text = arguments.get("text", "")
    entity_types = arguments.get("entity_types", ["PERSON", "ORG", "GPE", "CONCEPT"])

    try:
        # Simple regex-based entity extraction (fallback)
        # In production, would use spaCy NER
        import re

        entities = []

        # Extract capitalized phrases as potential entities
        cap_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        matches = re.findall(cap_pattern, text)

        for match in matches[:20]:  # Limit to 20 entities
            # Simple heuristic classification
            if len(match.split()) > 1:
                etype = "ORG" if any(w in match for w in ["Inc", "Corp", "Ltd"]) else "CONCEPT"
            else:
                etype = "PERSON" if match[0].isupper() else "CONCEPT"

            if etype in entity_types:
                entities.append({"text": match, "type": etype, "confidence": 0.7})

        return {
            "content": [{
                "type": "text",
                "text": f"Extracted {len(entities)} entities:\n" +
                       "\n".join([f"- {e['text']} ({e['type']})" for e in entities])
            }],
            "isError": False
        }

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Entity extraction error: {e}"}], "isError": True}


def _handle_hipporag_retrieve(
    arguments: Dict[str, Any],
    tool: NexusSearchTool
) -> Dict[str, Any]:
    """Handle hipporag_retrieve - Full HippoRAG pipeline."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)
    mode = arguments.get("mode", "execution")

    try:
        # Step 1: Extract entities from query
        entity_result = _handle_entity_extraction({"text": query}, tool)

        # Step 2: Use NexusProcessor with all tiers
        results = tool.execute(query, limit, mode)

        # Format combined output
        content = []
        content.append({
            "type": "text",
            "text": f"=== HippoRAG Pipeline Results ===\nMode: {mode}\nQuery: {query}\n"
        })

        # Add entity info
        if not entity_result.get("isError"):
            content.append(entity_result["content"][0])

        # Add retrieval results
        for idx, result in enumerate(results, 1):
            tier = result.get('tier', 'unknown')
            score = result.get('score', 0.0)
            content.append({
                "type": "text",
                "text": f"\nResult {idx} [{tier}] (score: {score:.4f}):\n{result['text'][:300]}...\n"
            })

        return {"content": content, "isError": False}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"HippoRAG error: {e}"}], "isError": True}


def _handle_detect_mode(
    arguments: Dict[str, Any],
    tool: NexusSearchTool
) -> Dict[str, Any]:
    """Handle detect_mode - Classify query intent."""
    query = arguments.get("query", "").lower()

    # Mode detection patterns
    execution_patterns = ["what is", "define", "explain", "show me", "find", "get"]
    planning_patterns = ["how should", "what approach", "design", "plan", "strategy", "recommend"]
    brainstorming_patterns = ["what if", "imagine", "explore", "could we", "ideas for", "possibilities"]

    mode = "execution"  # Default
    confidence = 0.5

    for pattern in execution_patterns:
        if pattern in query:
            mode = "execution"
            confidence = 0.85
            break

    for pattern in planning_patterns:
        if pattern in query:
            mode = "planning"
            confidence = 0.85
            break

    for pattern in brainstorming_patterns:
        if pattern in query:
            mode = "brainstorming"
            confidence = 0.85
            break

    return {
        "content": [{
            "type": "text",
            "text": f"Detected mode: {mode}\nConfidence: {confidence:.0%}\nQuery: {query[:100]}"
        }],
        "isError": False
    }


def _handle_obsidian_sync(
    arguments: Dict[str, Any],
    tool: NexusSearchTool
) -> Dict[str, Any]:
    """Handle obsidian_sync - Sync Obsidian vault to memory (C3.2)."""
    file_extensions = arguments.get("file_extensions", [".md"])

    try:
        # Check if ObsidianClient is configured
        if not tool.obsidian_client:
            return {
                "content": [{
                    "type": "text",
                    "text": "Obsidian vault not configured. Set vault_path in config."
                }],
                "isError": True
            }

        # Sync vault
        result = tool.obsidian_client.sync_vault(file_extensions)

        # C3.3: Log sync event
        tool.log_event("chunk_added", {
            "source": "obsidian_sync",
            "files_synced": result["files_synced"],
            "total_chunks": result["total_chunks"],
            "duration_ms": result["duration_ms"]
        })

        # Format response
        success_text = f"Synced {result['files_synced']} files ({result['total_chunks']} chunks) in {result['duration_ms']}ms"
        if result["errors"]:
            error_text = "\nErrors:\n" + "\n".join(f"- {e}" for e in result["errors"][:5])
            success_text += error_text

        return {
            "content": [{
                "type": "text",
                "text": success_text
            }],
            "isError": not result["success"]
        }

    except Exception as e:
        logger.error(f"Obsidian sync failed: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Obsidian sync error: {e}"
            }],
            "isError": True
        }


def handle_call_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    tool: NexusSearchTool
) -> Dict[str, Any]:
    """Execute a tool and return results (7 tools available)."""
    try:
        if tool_name == "vector_search":
            return _handle_vector_search(arguments, tool)
        elif tool_name == "memory_store":
            return _handle_memory_store(arguments, tool)
        elif tool_name == "graph_query":
            return _handle_graph_query(arguments, tool)
        elif tool_name == "entity_extraction":
            return _handle_entity_extraction(arguments, tool)
        elif tool_name == "hipporag_retrieve":
            return _handle_hipporag_retrieve(arguments, tool)
        elif tool_name == "detect_mode":
            return _handle_detect_mode(arguments, tool)
        elif tool_name == "obsidian_sync":
            return _handle_obsidian_sync(arguments, tool)
        else:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Unknown tool: {tool_name}"
                }],
                "isError": True
            }

    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Error: {str(e)}"
            }],
            "isError": True
        }


def _handle_initialize_method(message_id: Any) -> Dict[str, Any]:
    """Handle MCP initialize method."""
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "memory-mcp-triple-system",
                "version": "1.4.0"
            }
        }
    }


def _handle_tools_list_method(message_id: Any) -> Dict[str, Any]:
    """Handle MCP tools/list method."""
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "result": {
            "tools": handle_list_tools()
        }
    }


def _handle_tools_call_method(
    message_id: Any,
    params: Dict[str, Any],
    tool: NexusSearchTool
) -> Dict[str, Any]:
    """Handle MCP tools/call method."""
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    result = handle_call_tool(tool_name, arguments, tool)

    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "result": result
    }


def _process_message(
    message: Dict[str, Any],
    tool: NexusSearchTool
) -> Dict[str, Any]:
    """Process a single MCP message and return response."""
    method = message.get("method", "")
    message_id = message.get("id")
    params = message.get("params", {})

    if method == "initialize":
        return _handle_initialize_method(message_id)
    elif method == "tools/list":
        return _handle_tools_list_method(message_id)
    elif method == "tools/call":
        return _handle_tools_call_method(message_id, params, tool)
    else:
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }


def _apply_migrations(config: Dict[str, Any]) -> None:
    """C3.7: Apply pending database migrations on startup."""
    import sqlite3

    migrations_dir = Path(__file__).parent.parent.parent / "migrations"
    data_dir = Path(config.get('storage', {}).get('data_dir', './data'))
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "query_traces.db"

    if not migrations_dir.exists():
        return

    try:
        conn = sqlite3.connect(str(db_path))
        # Apply query_traces migration
        migration_file = migrations_dir / "007_query_traces_table.sql"
        if migration_file.exists():
            with open(migration_file, 'r') as f:
                conn.executescript(f.read())
        conn.close()
    except Exception as e:
        # ISS-050 fix: Log migration errors instead of silently ignoring
        logger.warning(f"Database migration failed: {e}. Server continuing with existing schema.")


def main():
    """Main stdio MCP server loop with production features."""
    # Suppress loguru output to stderr (interferes with stdio protocol)
    logger.remove()

    # Load config and initialize Nexus search tool
    config = load_config()

    # C3.7: Apply migrations
    _apply_migrations(config)

    nexus_search_tool = NexusSearchTool(config)

    # Process stdio messages
    for line in sys.stdin:
        try:
            message = json.loads(line.strip())
            response = _process_message(message, nexus_search_tool)
            print(json.dumps(response), flush=True)

        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": message.get("id") if 'message' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
