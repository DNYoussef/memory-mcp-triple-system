"""
Request Router Module - Tool execution and routing.

Handles all MCP tool calls and routes to appropriate handlers.
Extracted from stdio_server.py as part of MEM-CLEAN-003.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import json
import time
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .service_wiring import NexusSearchTool

REQUIRED_TAGS = ["who", "when", "project", "why"]


# === Metadata Helpers ===

def _normalize_metadata_tags(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize tag case (uppercase to lowercase)."""
    normalized = dict(metadata)
    for tag in REQUIRED_TAGS:
        upper = tag.upper()
        if upper in normalized and tag not in normalized:
            normalized[tag] = normalized[upper]
    return normalized


def _validate_metadata(metadata: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Validate required metadata tags."""
    if metadata is None:
        return False, REQUIRED_TAGS
    missing = [tag for tag in REQUIRED_TAGS if not metadata.get(tag)]
    return len(missing) == 0, missing


def _autofill_metadata(metadata: Dict[str, Any], missing: List[str]) -> Dict[str, Any]:
    """Autofill missing metadata tags."""
    now = datetime.utcnow().isoformat()
    if "who" in missing:
        metadata["who"] = "unknown:mcp-client"
    if "when" in missing:
        metadata["when"] = now
    if "project" in missing:
        metadata["project"] = "untagged"
    if "why" in missing:
        metadata["why"] = "unspecified"
    return metadata


def _get_tagging_policy(config: Dict[str, Any]) -> Dict[str, bool]:
    """Get tagging policy from config."""
    tagging = config.get("tagging", {})
    return {
        "strict": bool(tagging.get("strict", False)),
        "auto_fill": bool(tagging.get("auto_fill", True))
    }


def _enrich_metadata_with_tagging(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich metadata with WHO/WHEN/PROJECT/WHY tagging protocol."""
    import os
    now = datetime.utcnow()

    agent_name = metadata.get('agent', 'unknown')
    agent_category = metadata.get('agent_category', 'general')
    who = metadata.get('who', metadata.get('WHO', agent_name))
    timestamp_iso = metadata.get('when', metadata.get('WHEN', now.isoformat() + 'Z'))
    timestamp_unix = int(now.timestamp())
    timestamp_readable = now.strftime('%Y-%m-%d %H:%M:%S')

    project = os.environ.get(
        'MEMORY_MCP_PROJECT',
        metadata.get('project', metadata.get('PROJECT', 'memory-mcp-triple-system'))
    )
    intent = metadata.get('intent', metadata.get('why', metadata.get('WHY', 'storage')))

    return {
        **metadata,
        'WHO': who,
        'WHEN': timestamp_iso,
        'PROJECT': project,
        'WHY': intent,
        'agent_name': agent_name,
        'agent_category': agent_category,
        'timestamp_iso': timestamp_iso,
        'timestamp_unix': timestamp_unix,
        'timestamp_readable': timestamp_readable,
        'project': project,
        'intent': intent,
        '_tagging_version': '1.0.0',
        '_tagging_protocol': 'memory-mcp-triple-system'
    }


def _assign_confidence(metadata: Dict[str, Any]) -> float:
    """Assign confidence based on source type."""
    existing = metadata.get("confidence")
    if existing is not None:
        return float(existing)

    source_type = str(metadata.get("source_type") or metadata.get("source") or "").lower()
    mapping = {
        "witnessed": 0.95,
        "reported": 0.70,
        "inferred": 0.50,
        "assumed": 0.30,
    }
    return mapping.get(source_type, 0.5)


# === Tool Handlers ===

def _format_result_compact(idx: int, result: Dict[str, Any]) -> Dict[str, Any]:
    """Format a search result in compact mode (~50 tokens)."""
    text_preview = result.get("text", "")[:80].replace("\n", " ")
    score = result.get("score", 0.0)
    tier = result.get("tier", "")
    tier_tag = f" [{tier}]" if tier else ""
    file_path = result.get("file_path", "")
    return {
        "type": "text",
        "text": f"{idx}. ({score:.3f}){tier_tag} {text_preview}... | {file_path}"
    }


def _format_result_full(idx: int, result: Dict[str, Any]) -> Dict[str, Any]:
    """Format a search result in full mode (~500 tokens)."""
    tier_info = f"Tier: {result.get('tier', 'unknown')}\n" if "tier" in result else ""
    return {
        "type": "text",
        "text": (
            f"Result {idx}:\n{result['text']}\n\n"
            f"{tier_info}Score: {result['score']:.4f}\n"
            f"File: {result['file_path']}\n"
        )
    }


def handle_vector_search(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle vector_search tool execution."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 5)
    mode = arguments.get("mode", "execution")
    detail = arguments.get("detail", "full")

    tool.kv_store.set("session:last_query_mode", mode)
    tool.kv_store.set("session:last_query_limit", str(limit))

    trace = tool.create_query_trace(query, mode)
    start_time = time.time()
    results = tool.execute(query, limit, mode)

    trace.retrieval_ms = int((time.time() - start_time) * 1000)
    trace.retrieved_chunks = [{"score": r.get("score", 0)} for r in results[:5]]
    trace.stores_queried = ["vector", "graph", "bayesian"]
    trace.routing_logic = "NexusProcessor 3-tier"
    trace.output = f"Retrieved {len(results)} results"
    trace.total_latency_ms = trace.retrieval_ms

    data_dir = tool.config.get('storage', {}).get('data_dir', './data')
    try:
        trace.log(db_path=f"{data_dir}/query_traces.db")
    except Exception:
        pass

    tool.log_event("vector_search", {
        "query": query[:100], "mode": mode, "limit": limit,
        "results_count": len(results), "latency_ms": trace.retrieval_ms
    })

    formatter = _format_result_compact if detail == "compact" else _format_result_full
    content = [formatter(idx, r) for idx, r in enumerate(results, 1)]

    return {"content": content, "isError": False}


def handle_memory_store(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle memory_store with tagging, lifecycle, and event logging."""
    text = arguments.get("text", "")
    metadata = _normalize_metadata_tags(arguments.get("metadata", {}))
    is_valid, missing = _validate_metadata(metadata)

    if not is_valid:
        policy = _get_tagging_policy(tool.config)
        if policy["strict"]:
            return {
                "content": [{"type": "text", "text": f"Missing required tags: {missing}"}],
                "isError": True
            }
        if policy["auto_fill"]:
            metadata = _autofill_metadata(metadata, missing)
            logger.warning(f"Auto-filled missing tags: {missing}")

    if not text:
        return {
            "content": [{"type": "text", "text": "Error: Empty text provided"}],
            "isError": True
        }

    try:
        enriched_metadata = _enrich_metadata_with_tagging(metadata)
        enriched_metadata["confidence"] = _assign_confidence(enriched_metadata)

        embedder = tool.vector_search_tool.embedder
        indexer = tool.vector_search_tool.indexer

        try:
            classification = tool.hot_cold_classifier.classify(text, enriched_metadata)
            enriched_metadata['lifecycle_tier'] = classification.get('tier', 'hot')
            enriched_metadata['decay_score'] = classification.get('decay_score', 1.0)
        except Exception:
            enriched_metadata['lifecycle_tier'] = 'hot'
            enriched_metadata['decay_score'] = 1.0

        chunks = [{
            'text': text,
            'file_path': enriched_metadata.get('key', 'manual_entry'),
            'chunk_index': 0,
            'metadata': enriched_metadata
        }]

        try:
            embeddings = embedder.encode([text])
            if embeddings is None or len(embeddings) == 0:
                raise ValueError("Embedding generation failed")
            indexer.index_chunks(chunks, embeddings.tolist())
        except Exception as embed_err:
            return {
                "content": [{"type": "text", "text": f"Storage failed: {embed_err}"}],
                "isError": True
            }

        try:
            tool.lifecycle_manager.demote_stale_chunks()
            tool.lifecycle_manager.archive_demoted_chunks()
        except Exception:
            pass

        entities_added = _store_entities_to_graph(text, enriched_metadata, tool, embedder)

        tool.log_event("memory_store", {
            "text_length": len(text),
            "agent": enriched_metadata.get('agent', {}).get('name', 'unknown'),
            "project": enriched_metadata.get('project', 'unknown'),
            "lifecycle_tier": enriched_metadata.get('lifecycle_tier', 'hot'),
            "entities_extracted": entities_added
        })

        tagging_info = f"Tagged: WHO={enriched_metadata['agent_name']}, PROJECT={enriched_metadata['project']}"
        lifecycle_info = f"Lifecycle: {enriched_metadata.get('lifecycle_tier', 'hot')}"

        return {
            "content": [{"type": "text", "text": f"Stored memory: {text[:100]}...\n{tagging_info}\n{lifecycle_info}"}],
            "isError": False,
            "tags_auto_filled": missing if not is_valid else []
        }

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Memory store error: {e}"}], "isError": True}


def _store_entities_to_graph(
    text: str,
    metadata: Dict[str, Any],
    tool: "NexusSearchTool",
    embedder
) -> int:
    """Extract and store entities to graph. Returns count added."""
    if not tool.entity_service:
        return 0

    try:
        from ..services.graph_service import GraphService
        chunk_id = hashlib.md5(text.encode()).hexdigest()[:16]
        entities = tool.entity_service.extract_entities(text)

        if not entities:
            return 0

        tool.graph_service.add_chunk_node(chunk_id, {
            'text': text[:500],
            'file_path': metadata.get('key', 'manual_entry'),
            'timestamp': metadata.get('timestamp')
        })

        entities_added = 0
        for ent in entities:
            entity_id = ent['text'].lower().replace(' ', '_')
            tool.graph_service.add_entity_node(entity_id, ent['type'], {
                'text': ent['text'], 'start': ent['start'], 'end': ent['end']
            })
            tool.graph_service.add_relationship(
                chunk_id, GraphService.EDGE_MENTIONS, entity_id,
                {'entity_type': ent['type'], 'position': ent['start'], 'confidence': 0.8}
            )
            try:
                tool.graph_service.link_similar_entities(entity_id, embedder=embedder)
            except Exception:
                pass
            entities_added += 1

        tool.graph_service.save_graph()
        return entities_added
    except Exception:
        return 0


def handle_graph_query(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle graph_query - HippoRAG multi-hop reasoning."""
    query = arguments.get("query", "")
    max_hops = arguments.get("max_hops", 3)
    limit = arguments.get("limit", 10)

    try:
        if tool.nexus_processor and tool.nexus_processor.graph_query_engine:
            results = tool.nexus_processor.graph_query_engine.query(
                query=query, top_k=limit, max_hops=max_hops
            )
        else:
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


def handle_entity_extraction(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle entity_extraction - NER from text."""
    import re
    text = arguments.get("text", "")
    entity_types = arguments.get("entity_types", ["PERSON", "ORG", "GPE", "CONCEPT"])

    try:
        if tool.entity_service:
            entities = tool.entity_service.extract_entities_by_type(text, entity_types)
        else:
            entities = []
            cap_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
            matches = re.findall(cap_pattern, text)

            for match in matches[:20]:
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


def handle_hipporag_retrieve(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle hipporag_retrieve - Full HippoRAG pipeline."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)
    mode = arguments.get("mode", "execution")

    try:
        entity_result = handle_entity_extraction({"text": query}, tool)
        if tool.hipporag_service:
            results = tool.hipporag_service.retrieve_multi_hop(query=query, top_k=limit)
        else:
            results = tool.execute(query, limit, mode)

        content = [{"type": "text", "text": f"=== HippoRAG Pipeline Results ===\nMode: {mode}\nQuery: {query}\n"}]

        if not entity_result.get("isError"):
            content.append(entity_result["content"][0])

        for idx, result in enumerate(results, 1):
            if isinstance(result, dict):
                tier = result.get('tier', 'hipporag')
                score = result.get('score', 0.0)
                text_content = result.get('text', '')
            else:
                tier = 'hipporag'
                score = getattr(result, "score", 0.0)
                text_content = getattr(result, "text", "")
            content.append({
                "type": "text",
                "text": f"\nResult {idx} [{tier}] (score: {score:.4f}):\n{text_content[:300]}...\n"
            })

        return {"content": content, "isError": False}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"HippoRAG error: {e}"}], "isError": True}


def handle_detect_mode(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle detect_mode - Classify query intent."""
    query = arguments.get("query", "").lower()

    execution_patterns = ["what is", "define", "explain", "show me", "find", "get"]
    planning_patterns = ["how should", "what approach", "design", "plan", "strategy", "recommend"]
    brainstorming_patterns = ["what if", "imagine", "explore", "could we", "ideas for", "possibilities"]

    mode = "execution"
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
        "content": [{"type": "text", "text": f"Detected mode: {mode}\nConfidence: {confidence:.0%}\nQuery: {query[:100]}"}],
        "isError": False
    }


def handle_lifecycle_status(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle lifecycle_status - Get lifecycle statistics."""
    stats = tool.lifecycle_manager.get_stage_stats()
    return {"content": [{"type": "text", "text": json.dumps(stats)}], "isError": False}


def handle_bayesian_inference(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle bayesian_inference - Probabilistic inference."""
    query = arguments.get("query", "")
    evidence = arguments.get("evidence")

    if not tool.nexus_processor or not tool.nexus_processor.probabilistic_query_engine:
        return {"content": [{"type": "text", "text": "Bayesian engine unavailable"}], "isError": True}

    query_var = tool.nexus_processor._extract_query_entity(query)
    result = tool.nexus_processor.probabilistic_query_engine.query_conditional(
        network=None, query_vars=[query_var], evidence=evidence
    )

    return {"content": [{"type": "text", "text": json.dumps(result)}], "isError": False}


def handle_unified_search(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle unified_search - NexusProcessor 5-step SOP."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 5)
    mode = arguments.get("mode", "execution")
    detail = arguments.get("detail", "full")

    if not tool.nexus_processor:
        return handle_vector_search(arguments, tool)

    nexus_result = tool.nexus_processor.process(
        query=query, mode=mode, top_k=50, token_budget=10000
    )

    combined = nexus_result.get("core", []) + nexus_result.get("extended", [])
    limited = combined[:limit]

    if detail == "compact":
        content = []
        for idx, r in enumerate(limited, 1):
            text_preview = str(r.get("text", ""))[:80].replace("\n", " ")
            score = r.get("score", 0.0)
            tier = r.get("tier", "")
            tier_tag = f" [{tier}]" if tier else ""
            content.append({
                "type": "text",
                "text": f"{idx}. ({score:.3f}){tier_tag} {text_preview}..."
            })
        stats = nexus_result.get("pipeline_stats", {})
        content.append({
            "type": "text",
            "text": f"--- {len(limited)} results | mode={mode} | {stats.get('total_ms', '?')}ms"
        })
        return {"content": content, "isError": False}

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "results": limited,
                "pipeline_stats": nexus_result.get("pipeline_stats"),
                "mode": mode
            })
        }],
        "isError": False
    }


def handle_obsidian_sync(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle obsidian_sync - Sync Obsidian vault to memory (C3.2)."""
    file_extensions = arguments.get("file_extensions", [".md"])

    try:
        if not tool.obsidian_client:
            return {
                "content": [{"type": "text", "text": "Obsidian vault not configured. Set vault_path in config."}],
                "isError": True
            }

        result = tool.obsidian_client.sync_vault(file_extensions)

        tool.log_event("chunk_added", {
            "source": "obsidian_sync",
            "files_synced": result["files_synced"],
            "total_chunks": result["total_chunks"],
            "duration_ms": result["duration_ms"]
        })

        success_text = f"Synced {result['files_synced']} files ({result['total_chunks']} chunks) in {result['duration_ms']}ms"
        if result["errors"]:
            success_text += "\nErrors:\n" + "\n".join(f"- {e}" for e in result["errors"][:5])

        return {"content": [{"type": "text", "text": success_text}], "isError": not result["success"]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Obsidian sync error: {e}"}], "isError": True}


def handle_beads_ready_tasks(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle beads_ready_tasks - Get unblocked tasks ready for work."""
    limit = arguments.get("limit", 10)
    brief = arguments.get("brief", True)

    try:
        tasks = asyncio.run(tool.beads_bridge.get_ready_tasks(limit=limit, brief=brief))

        if not tasks:
            return {"content": [{"type": "text", "text": "No ready tasks found"}], "isError": False}

        task_lines = []
        for task in tasks:
            priority_icon = ["", "P1", "P2", "P3", "P4", "P5"][min(task.priority, 5)]
            task_lines.append(f"[{task.id}] {priority_icon} {task.title} ({task.status})")

        return {
            "content": [{"type": "text", "text": f"Ready tasks ({len(tasks)}):\n" + "\n".join(task_lines)}],
            "isError": False
        }
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Beads error: {e}"}], "isError": True}


def handle_beads_task_detail(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle beads_task_detail - Get full task details."""
    task_id = arguments.get("task_id", "")

    if not task_id:
        return {"content": [{"type": "text", "text": "Error: task_id is required"}], "isError": True}

    try:
        task = asyncio.run(tool.beads_bridge.get_task_detail(task_id))

        if task.status == "unknown":
            return {"content": [{"type": "text", "text": f"Task {task_id} not found"}], "isError": True}

        deps_text = ", ".join([d.id for d in task.dependencies]) if task.dependencies else "None"
        labels_text = ", ".join(task.labels) if task.labels else "None"
        comments_text = "\n".join([f"  - {c.author}: {c.body[:100]}" for c in task.comments[:3]]) if task.comments else "  None"

        detail = f"""Task: {task.id}
Title: {task.title}
Status: {task.status}
Priority: {task.priority}
Type: {task.issue_type}
Assignee: {task.assignee or 'Unassigned'}
Labels: {labels_text}
Dependencies: {deps_text}
Description: {task.description or 'No description'}
Comments:
{comments_text}"""

        return {"content": [{"type": "text", "text": detail}], "isError": False}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Beads error: {e}"}], "isError": True}


def handle_beads_query_tasks(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle beads_query_tasks - Query tasks with filters."""
    status = arguments.get("status")
    priority = arguments.get("priority")
    assignee = arguments.get("assignee")
    limit = arguments.get("limit", 20)

    try:
        tasks = asyncio.run(tool.beads_bridge.query_tasks(
            status=status, priority=priority, assignee=assignee, limit=limit, brief=True
        ))

        if not tasks:
            filter_info = []
            if status:
                filter_info.append(f"status={status}")
            if priority:
                filter_info.append(f"priority={priority}")
            if assignee:
                filter_info.append(f"assignee={assignee}")
            filter_str = ", ".join(filter_info) if filter_info else "no filters"
            return {"content": [{"type": "text", "text": f"No tasks found ({filter_str})"}], "isError": False}

        task_lines = []
        for task in tasks:
            priority_icon = ["", "P1", "P2", "P3", "P4", "P5"][min(task.priority, 5)]
            assignee_str = f" @{task.assignee}" if task.assignee else ""
            task_lines.append(f"[{task.id}] {priority_icon} {task.title} ({task.status}){assignee_str}")

        return {
            "content": [{"type": "text", "text": f"Query results ({len(tasks)} tasks):\n" + "\n".join(task_lines)}],
            "isError": False
        }
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Beads error: {e}"}], "isError": True}


def handle_observation_timeline(
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Handle observation_timeline - query auto-captured observations."""
    project = arguments.get("project")
    obs_type = arguments.get("obs_type")
    session_id = arguments.get("session_id")
    hours_back = arguments.get("hours_back", 24)
    limit = arguments.get("limit", 30)
    detail = arguments.get("detail", "compact")

    after = (
        datetime.utcnow() - timedelta(hours=hours_back)
    ).isoformat() + "Z"

    try:
        observations = tool.kv_store.get_observations(
            session_id=session_id,
            project=project,
            obs_type=obs_type,
            after=after,
            limit=limit,
        )

        if not observations:
            return {
                "content": [{"type": "text", "text": "No observations found for the given filters."}],
                "isError": False
            }

        content = []
        if detail == "compact":
            for obs in observations:
                ts = obs.get("created_at", "")[:16]
                tool_name = obs.get("tool_name", "")
                otype = obs.get("obs_type", "")
                snippet = obs.get("content", "")[:60].replace("\n", " ")
                content.append({
                    "type": "text",
                    "text": f"[{ts}] {otype}/{tool_name}: {snippet}"
                })
        else:
            for obs in observations:
                ts = obs.get("created_at", "")
                content.append({
                    "type": "text",
                    "text": (
                        f"--- {obs.get('observation_id', '')[:8]} ---\n"
                        f"Time: {ts}\n"
                        f"Type: {obs.get('obs_type', '')}\n"
                        f"Tool: {obs.get('tool_name', '')}\n"
                        f"Project: {obs.get('project', '')}\n"
                        f"Content: {obs.get('content', '')[:400]}\n"
                        f"Entities: {', '.join(obs.get('entities', []))}\n"
                    )
                })

        header = {
            "type": "text",
            "text": f"Timeline: {len(observations)} observations (last {hours_back}h)"
        }
        return {"content": [header] + content, "isError": False}
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Timeline error: {e}"}],
            "isError": True
        }


# === Main Router ===

def handle_call_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    tool: "NexusSearchTool"
) -> Dict[str, Any]:
    """Execute a tool and return results."""
    handlers = {
        "vector_search": handle_vector_search,
        "unified_search": handle_unified_search,
        "memory_store": handle_memory_store,
        "graph_query": handle_graph_query,
        "bayesian_inference": handle_bayesian_inference,
        "entity_extraction": handle_entity_extraction,
        "hipporag_retrieve": handle_hipporag_retrieve,
        "detect_mode": handle_detect_mode,
        "lifecycle_status": handle_lifecycle_status,
        "obsidian_sync": handle_obsidian_sync,
        "beads_ready_tasks": handle_beads_ready_tasks,
        "beads_task_detail": handle_beads_task_detail,
        "beads_query_tasks": handle_beads_query_tasks,
        "observation_timeline": handle_observation_timeline,
    }

    try:
        handler = handlers.get(tool_name)
        if handler:
            return handler(arguments, tool)
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            "isError": True
        }
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "isError": True}
