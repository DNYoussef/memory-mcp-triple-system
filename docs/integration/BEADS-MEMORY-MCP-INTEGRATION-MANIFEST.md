# BEADS + MEMORY MCP INTEGRATION MANIFEST

**Generated**: 2026-01-12
**Purpose**: Gap reconnaissance for Beads (procedural memory) + Memory MCP (semantic memory) integration
**Status**: Integration architecture complete, ready for implementation
**Location**: `~/reconnaissance/`

---

## EXECUTIVE SUMMARY

This manifest documents the integration strategy for bridging **Beads** (Steve Yegge's git-backed procedural task management) with **Memory MCP** (triple-layer semantic memory system). The integration creates a **unified retrieval router** that provides mode-aware context delivery:

- **Execution Mode**: 80% Beads (task-focused) + 20% Memory (background context)
- **Planning Mode**: 50% Beads + 50% Memory (balanced exploration)
- **Brainstorming Mode**: 20% Beads + 80% Memory (knowledge-heavy)

**Gap Status**: **100% gaps identified**, solution architecture complete, library components mapped.

**Implementation Effort**: **22-28 hours** across 3 components

**Key Deliverables**:
1. `memory-mcp-beads-bridge` (NEW COMPONENT) - 10-12h
2. `unified-retrieval-router` (NEW COMPONENT) - 8-10h
3. `beads-webhook-receiver` (OPTIONAL) - 4-6h

---

## PART I: GAP ANALYSIS

### Gap Matrix (MECE)

| Gap ID | Component | Criticality | Beads Side | Memory MCP Side | Status |
|--------|-----------|-------------|------------|-----------------|--------|
| **GAP-01** | Beads Task Query Bridge | P0 | bd CLI wrapper | Python subprocess | DESIGN COMPLETE |
| **GAP-02** | Memory MCP Query Interface | P0 | N/A | Nexus Processor API | EXISTS (70%) |
| **GAP-03** | Mode-Aware Router | P0 | N/A | Mode detector + routing logic | DESIGN COMPLETE |
| **GAP-04** | WHO/WHEN/PROJECT/WHY Sync | P1 | `.beads/issues.jsonl` metadata | Tagging protocol | DESIGN COMPLETE |
| **GAP-05** | Webhook Receiver (optional) | P2 | POST endpoint | FastAPI router | PATTERN EXISTS |
| **GAP-06** | Context Window Optimization | P1 | bd prime, brief flags | Token budget management | DESIGN COMPLETE |

### Gap Details

#### GAP-01: Beads Task Query Bridge (P0, 10-12h)

**Problem**: Memory MCP (Python) needs to query Beads (Go CLI) for procedural task context.

**Current State**:
- Beads CLI provides `bd ready`, `bd show`, `bd list` with `--json` flags
- No Python wrapper exists for subprocess calls
- No caching layer for repeated queries

**Solution**: Create `memory-mcp-beads-bridge` component

**Location**: `D:\Projects\memory-mcp-triple-system\src\integrations\beads_bridge.py`

**Implementation**:
```python
# Core Architecture
class BeadsBridge:
    def __init__(self, beads_binary="bd", cache_ttl=60):
        self.binary = beads_binary
        self.cache = {}  # Simple TTL cache
        self.cache_ttl = cache_ttl

    async def get_ready_tasks(self, limit=10, brief=True) -> List[BeadTask]:
        """Get unblocked tasks ready for work."""
        cmd = [self.binary, "ready", "--json"]
        if brief:
            cmd.append("--brief")
        if limit:
            cmd.extend(["--limit", str(limit)])

        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            raise BeadsError(f"bd ready failed: {stderr.decode()}")

        tasks = json.loads(stdout.decode())
        return [BeadTask.from_dict(t) for t in tasks]

    async def get_task_detail(self, task_id: str) -> BeadTask:
        """Get full task details with dependencies and comments."""
        # Check cache first
        cache_key = f"task:{task_id}"
        if cache_key in self.cache:
            cached_at, data = self.cache[cache_key]
            if time.time() - cached_at < self.cache_ttl:
                return data

        cmd = [self.binary, "show", task_id, "--json"]
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            raise BeadsError(f"bd show failed: {stderr.decode()}")

        task_data = json.loads(stdout.decode())
        task = BeadTask.from_dict(task_data)

        # Cache result
        self.cache[cache_key] = (time.time(), task)
        return task

    async def query_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        assignee: Optional[str] = None,
        limit: int = 20
    ) -> List[BeadTask]:
        """Flexible task query with filters."""
        cmd = [self.binary, "list", "--json", "--limit", str(limit)]

        if status:
            cmd.extend(["--status", status])
        if priority is not None:
            cmd.extend(["--priority", str(priority)])
        if assignee:
            cmd.extend(["--assignee", assignee])

        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            raise BeadsError(f"bd list failed: {stderr.decode()}")

        tasks = json.loads(stdout.decode())
        return [BeadTask.from_dict(t) for t in tasks]
```

**Data Model**:
```python
@dataclass
class BeadTask:
    id: str  # e.g., "bd-a1b2"
    title: str
    description: Optional[str]
    status: str  # open, in_progress, closed, blocked
    priority: int  # 0-4
    issue_type: str  # bug, feature, task, epic
    assignee: Optional[str]
    created_at: datetime
    updated_at: datetime
    dependencies: List[BeadDependency]
    labels: List[str]
    comments: List[BeadComment]

    @classmethod
    def from_dict(cls, data: dict) -> 'BeadTask':
        """Parse from bd --json output."""
        return cls(
            id=data['id'],
            title=data['title'],
            description=data.get('description'),
            status=data.get('status', 'open'),
            priority=data.get('priority', 2),
            issue_type=data.get('issue_type', 'task'),
            assignee=data.get('assignee'),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            dependencies=[BeadDependency.from_dict(d) for d in data.get('dependencies', [])],
            labels=data.get('labels', []),
            comments=[BeadComment.from_dict(c) for c in data.get('comments', [])]
        )
```

**Testing Strategy**:
```python
# tests/test_beads_bridge.py
import pytest
import asyncio
from integrations.beads_bridge import BeadsBridge, BeadTask

@pytest.mark.asyncio
async def test_get_ready_tasks():
    bridge = BeadsBridge()
    tasks = await bridge.get_ready_tasks(limit=5)
    assert isinstance(tasks, list)
    for task in tasks:
        assert isinstance(task, BeadTask)
        assert task.id.startswith("bd-")

@pytest.mark.asyncio
async def test_get_task_detail():
    bridge = BeadsBridge()
    tasks = await bridge.get_ready_tasks(limit=1)
    if tasks:
        task_detail = await bridge.get_task_detail(tasks[0].id)
        assert task_detail.id == tasks[0].id
        assert task_detail.description is not None

@pytest.mark.asyncio
async def test_query_tasks_with_filters():
    bridge = BeadsBridge()
    open_tasks = await bridge.query_tasks(status="open", priority=0)
    assert all(t.status == "open" for t in open_tasks)
    assert all(t.priority == 0 for t in open_tasks)
```

**Library Component Reuse**:
- **Pattern**: Async subprocess wrapper (similar to existing `multi-model-router`)
- **Resilience**: Circuit breaker pattern for bd CLI failures
- **Caching**: Simple TTL cache (60s default, configurable)

---

#### GAP-02: Memory MCP Query Interface Enhancement (P0, 2-3h)

**Problem**: Nexus Processor needs public API for external retrieval routers.

**Current State**:
- Nexus Processor exists with 5-step pipeline (RECALL → FILTER → DEDUPLICATE → RANK → COMPRESS)
- Currently internal-only, called via MCP stdio server
- No public Python API for direct programmatic access

**Solution**: Extract NexusProcessor as standalone service

**Location**: `D:\Projects\memory-mcp-triple-system\src\nexus\public_api.py`

**Implementation**:
```python
# Public API for unified retrieval router
from nexus.processor import NexusProcessor
from typing import Dict, List, Any

class MemoryMCPQueryService:
    """Public API for Memory MCP semantic retrieval."""

    def __init__(self, data_dir: str = "./data"):
        self.nexus = NexusProcessor(data_dir=data_dir)

    async def semantic_search(
        self,
        query: str,
        mode: str = "execution",  # execution/planning/brainstorming
        top_k: int = 50,
        token_budget: int = 10000
    ) -> Dict[str, Any]:
        """
        Search semantic memory using triple-tier retrieval.

        Returns:
        {
            'core': [top-5 to top-15 results],
            'extended': [next 0-25 results],
            'token_count': int,
            'compression_ratio': float,
            'mode': str,
            'pipeline_stats': {...}
        }
        """
        return await self.nexus.process(
            query=query,
            mode=mode,
            top_k=top_k,
            token_budget=token_budget
        )

    async def get_related_entities(self, entity_name: str) -> List[str]:
        """Get entities related to given entity via HippoRAG graph."""
        # Use HippoRAG graph traversal
        from services.graph_service import GraphService
        graph = GraphService(data_dir=self.nexus.data_dir)
        graph.load_graph()

        # Find related entities via graph edges
        related = graph.get_neighbors(entity_name, max_depth=2)
        return related

    async def store_context(
        self,
        content: str,
        metadata: Dict[str, Any],
        tags: Dict[str, str]  # WHO/WHEN/PROJECT/WHY
    ) -> str:
        """Store new semantic context with tagging protocol."""
        from mcp.stdio_server import _enrich_metadata_with_tagging

        # Enrich metadata with tagging protocol
        enriched = _enrich_metadata_with_tagging(metadata, tags)

        # Store via Memory MCP
        return await self.nexus.store_memory(
            content=content,
            metadata=enriched
        )
```

**Testing Strategy**:
```python
@pytest.mark.asyncio
async def test_semantic_search_execution_mode():
    service = MemoryMCPQueryService()
    result = await service.semantic_search(
        query="How do I implement authentication?",
        mode="execution",
        top_k=10
    )
    assert 'core' in result
    assert len(result['core']) <= 5  # Execution mode: 5 core
    assert result['mode'] == "execution"

@pytest.mark.asyncio
async def test_get_related_entities():
    service = MemoryMCPQueryService()
    related = await service.get_related_entities("FastAPI")
    assert isinstance(related, list)
    # Should find Pydantic, SQLAlchemy, etc.
```

---

#### GAP-03: Unified Retrieval Router (P0, 8-10h)

**Problem**: No system exists to route between Beads (procedural) and Memory MCP (semantic) based on query mode.

**Current State**: N/A - Completely new component

**Solution**: Create `unified-retrieval-router` with mode-aware routing logic

**Location**: `D:\Projects\memory-mcp-triple-system\src\routing\unified_router.py`

**Implementation**:
```python
from typing import Dict, List, Any, Tuple
from integrations.beads_bridge import BeadsBridge, BeadTask
from nexus.public_api import MemoryMCPQueryService
from modes.mode_detector import ModeDetector

class UnifiedRetrievalRouter:
    """
    Mode-aware retrieval router that blends Beads (procedural)
    and Memory MCP (semantic) results.

    Routing Strategy:
    - Execution:     80% Beads + 20% Memory (task-focused)
    - Planning:      50% Beads + 50% Memory (balanced)
    - Brainstorming: 20% Beads + 80% Memory (knowledge-heavy)
    """

    def __init__(self, beads_bridge: BeadsBridge, memory_service: MemoryMCPQueryService):
        self.beads = beads_bridge
        self.memory = memory_service
        self.mode_detector = ModeDetector()

        # Routing weights by mode
        self.weights = {
            "execution": {"beads": 0.8, "memory": 0.2},
            "planning": {"beads": 0.5, "memory": 0.5},
            "brainstorming": {"beads": 0.2, "memory": 0.8}
        }

    async def retrieve(
        self,
        query: str,
        mode: Optional[str] = None,
        token_budget: int = 10000
    ) -> Dict[str, Any]:
        """
        Unified retrieval across Beads and Memory MCP.

        Args:
            query: User query
            mode: Optional mode override (otherwise auto-detected)
            token_budget: Max tokens for combined result

        Returns:
        {
            'beads_tasks': [BeadTask...],
            'memory_results': {'core': [...], 'extended': [...]},
            'mode': str,
            'routing_weights': {'beads': float, 'memory': float},
            'total_token_count': int
        }
        """
        # Detect or use provided mode
        if mode is None:
            mode = self.mode_detector.detect(query)

        weights = self.weights[mode]

        # Allocate token budget
        beads_budget = int(token_budget * weights["beads"])
        memory_budget = int(token_budget * weights["memory"])

        # Parallel retrieval
        beads_tasks, memory_results = await asyncio.gather(
            self._retrieve_beads(query, beads_budget, mode),
            self._retrieve_memory(query, memory_budget, mode),
            return_exceptions=True
        )

        # Handle failures gracefully
        if isinstance(beads_tasks, Exception):
            beads_tasks = []
        if isinstance(memory_results, Exception):
            memory_results = {'core': [], 'extended': []}

        return {
            'beads_tasks': beads_tasks,
            'memory_results': memory_results,
            'mode': mode,
            'routing_weights': weights,
            'total_token_count': self._count_tokens(beads_tasks, memory_results)
        }

    async def _retrieve_beads(
        self,
        query: str,
        token_budget: int,
        mode: str
    ) -> List[BeadTask]:
        """Retrieve tasks from Beads."""
        # Execution mode: focus on ready tasks
        if mode == "execution":
            tasks = await self.beads.get_ready_tasks(limit=10, brief=True)

        # Planning mode: include blocked and future tasks
        elif mode == "planning":
            ready = await self.beads.get_ready_tasks(limit=5, brief=False)
            blocked = await self.beads.query_tasks(status="blocked", limit=5)
            tasks = ready + blocked

        # Brainstorming mode: high-level epics and features
        else:  # brainstorming
            tasks = await self.beads.query_tasks(
                issue_type="epic",
                status="open",
                limit=5
            )

        # Trim to token budget
        return self._trim_to_budget(tasks, token_budget)

    async def _retrieve_memory(
        self,
        query: str,
        token_budget: int,
        mode: str
    ) -> Dict[str, Any]:
        """Retrieve from Memory MCP semantic memory."""
        return await self.memory.semantic_search(
            query=query,
            mode=mode,
            token_budget=token_budget
        )

    def _trim_to_budget(self, tasks: List[BeadTask], budget: int) -> List[BeadTask]:
        """Trim task list to fit token budget."""
        total_tokens = 0
        trimmed = []

        for task in tasks:
            task_tokens = self._estimate_tokens(task)
            if total_tokens + task_tokens > budget:
                break
            trimmed.append(task)
            total_tokens += task_tokens

        return trimmed

    def _estimate_tokens(self, task: BeadTask) -> int:
        """Estimate tokens for a Bead task (rough heuristic)."""
        # Title: ~10 tokens, description: ~50-100 tokens, metadata: ~20 tokens
        base = 30
        if task.description:
            base += len(task.description.split()) * 1.3  # Rough token estimate
        return int(base)

    def _count_tokens(self, tasks: List[BeadTask], memory: Dict) -> int:
        """Count total tokens in combined result."""
        beads_tokens = sum(self._estimate_tokens(t) for t in tasks)
        memory_tokens = memory.get('token_count', 0)
        return beads_tokens + memory_tokens
```

**Integration Testing**:
```python
@pytest.mark.asyncio
async def test_unified_router_execution_mode():
    bridge = BeadsBridge()
    memory = MemoryMCPQueryService()
    router = UnifiedRetrievalRouter(bridge, memory)

    result = await router.retrieve(
        query="What's the next task I should work on?",
        mode="execution"
    )

    assert result['mode'] == "execution"
    assert result['routing_weights']['beads'] == 0.8
    assert result['routing_weights']['memory'] == 0.2
    assert len(result['beads_tasks']) > 0  # Should have ready tasks

@pytest.mark.asyncio
async def test_unified_router_brainstorming_mode():
    bridge = BeadsBridge()
    memory = MemoryMCPQueryService()
    router = UnifiedRetrievalRouter(bridge, memory)

    result = await router.retrieve(
        query="What are all the authentication patterns we could use?",
        mode="brainstorming"
    )

    assert result['mode'] == "brainstorming"
    assert result['routing_weights']['memory'] == 0.8
    assert len(result['memory_results']['core']) > 0  # Should have semantic results
```

---

#### GAP-04: WHO/WHEN/PROJECT/WHY Sync (P1, 4-5h)

**Problem**: Beads JSONL and Memory MCP need unified metadata tagging.

**Current State**:
- Beads stores: `id`, `title`, `created_at`, `updated_at`, `created_by`, `assignee`
- Memory MCP uses: `WHO`, `WHEN`, `PROJECT`, `WHY` tagging protocol
- No bidirectional sync mechanism

**Solution**: Create metadata mapper that syncs both directions

**Location**: `D:\Projects\memory-mcp-triple-system\src\integrations\metadata_sync.py`

**Implementation**:
```python
class MetadataSync:
    """Sync metadata between Beads and Memory MCP tagging protocols."""

    @staticmethod
    def beads_to_memory_mcp(task: BeadTask, project: str) -> Dict[str, Any]:
        """Convert Beads task metadata to Memory MCP tagging protocol."""
        return {
            'WHO': {
                'name': task.assignee or f"beads:{task.id}",
                'category': "agent-specific"
            },
            'WHEN': {
                'iso': task.updated_at.isoformat(),
                'unix': int(task.updated_at.timestamp()),
                'readable': task.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            },
            'PROJECT': project,
            'WHY': task.issue_type,  # bug/feature/task/epic
            'x-beads-id': task.id,
            'x-beads-status': task.status,
            'x-beads-priority': task.priority
        }

    @staticmethod
    async def sync_task_to_memory(
        task: BeadTask,
        memory_service: MemoryMCPQueryService,
        project: str
    ):
        """Store Beads task in Memory MCP as context."""
        metadata = MetadataSync.beads_to_memory_mcp(task, project)

        # Combine title + description as content
        content = f"{task.title}\n\n{task.description or ''}"

        # Add dependency context
        if task.dependencies:
            dep_text = "\n\nDependencies:\n" + "\n".join(
                f"- {d.to_id} ({d.type})" for d in task.dependencies
            )
            content += dep_text

        await memory_service.store_context(
            content=content,
            metadata=metadata,
            tags={
                'WHO': metadata['WHO']['name'],
                'WHEN': metadata['WHEN']['iso'],
                'PROJECT': project,
                'WHY': metadata['WHY']
            }
        )
```

**Sync Workflow**:
```python
# Sync Beads tasks to Memory MCP on completion
@dataclass
class BeadsSyncConfig:
    sync_on_create: bool = False
    sync_on_close: bool = True
    sync_on_update: bool = False
    project_name: str = "default"

class BeadsMemorySyncService:
    def __init__(
        self,
        beads_bridge: BeadsBridge,
        memory_service: MemoryMCPQueryService,
        config: BeadsSyncConfig
    ):
        self.beads = beads_bridge
        self.memory = memory_service
        self.config = config

    async def watch_and_sync(self):
        """Watch Beads JSONL for changes and sync to Memory MCP."""
        # Poll .beads/issues.jsonl for changes
        # (In production, could use file watcher or webhook)
        last_sync = time.time()

        while True:
            await asyncio.sleep(30)  # Check every 30 seconds

            # Get recently updated tasks
            recent = await self.beads.query_tasks(
                status=None,  # All statuses
                limit=100
            )

            for task in recent:
                if task.updated_at.timestamp() > last_sync:
                    # Should sync based on config
                    should_sync = (
                        (self.config.sync_on_create and task.status == "open") or
                        (self.config.sync_on_close and task.status == "closed") or
                        (self.config.sync_on_update)
                    )

                    if should_sync:
                        await MetadataSync.sync_task_to_memory(
                            task,
                            self.memory,
                            self.config.project_name
                        )

            last_sync = time.time()
```

---

#### GAP-05: Webhook Receiver (OPTIONAL, P2, 4-6h)

**Problem**: Want to trigger Memory MCP operations on Beads events (create, close, etc.).

**Current State**: No webhook integration

**Solution**: FastAPI webhook endpoint for Beads events

**Location**: `D:\Projects\life-os-dashboard\src\routers\beads_webhook.py`

**Implementation**:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from integrations.beads_bridge import BeadTask
from nexus.public_api import MemoryMCPQueryService

router = APIRouter(prefix="/api/v1/beads", tags=["beads"])

class BeadsWebhookPayload(BaseModel):
    event: str  # "create", "update", "close", "comment"
    task_id: str
    task: dict  # Full task JSON from bd --json

@router.post("/webhook")
async def beads_webhook(
    payload: BeadsWebhookPayload,
    memory: MemoryMCPQueryService = Depends(get_memory_service)
):
    """Receive Beads events and sync to Memory MCP."""
    task = BeadTask.from_dict(payload.task)

    if payload.event == "close":
        # Store completed task as learning
        await MetadataSync.sync_task_to_memory(
            task,
            memory,
            project="life-os"
        )
        return {"status": "synced", "task_id": task.id}

    elif payload.event == "create":
        # Store as active context
        # (optional - might be too noisy)
        return {"status": "acknowledged", "task_id": task.id}

    return {"status": "ignored", "event": payload.event}
```

**Library Component Reuse**:
- **webhook-idempotency** pattern (prevents duplicate processing)
- **fastapi-router-template** for CRUD structure

---

#### GAP-06: Context Window Optimization (P1, 3-4h)

**Problem**: Combined Beads + Memory results may exceed token budgets.

**Solution**: Use Beads' built-in optimization flags + Memory's compression

**Beads Optimization Flags**:
```bash
# Brief mode (minimal output)
bd ready --json --brief --limit 10

# Field selection (cherry-pick fields)
bd list --json --fields id,title,status,priority

# Max description length
bd show bd-a1b2 --json --max-description-length 100
```

**Memory MCP Optimization**:
- Already has mode-aware token budgets (5K/10K/20K)
- Already has Nexus Processor compression (COMPRESS step)

**Integration**:
```python
class OptimizedRetrievalRouter(UnifiedRetrievalRouter):
    """Extends UnifiedRetrievalRouter with aggressive compression."""

    async def _retrieve_beads(self, query: str, token_budget: int, mode: str):
        # Use brief mode + field selection
        if mode == "execution":
            tasks = await self.beads.get_ready_tasks(
                limit=10,
                brief=True,
                fields=["id", "title", "status", "priority"]
            )

        # Further compression: strip long descriptions
        for task in tasks:
            if task.description and len(task.description) > 200:
                task.description = task.description[:200] + "..."

        return self._trim_to_budget(tasks, token_budget)
```

---

## PART II: SOLUTION ARCHITECTURE

### Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     UNIFIED RETRIEVAL ROUTER                      │
│                                                                    │
│  ┌────────────────────────┐      ┌────────────────────────┐     │
│  │   Mode Detector        │      │   Routing Engine       │     │
│  │  (execution/planning/  │─────▶│  (weight-based blend)  │     │
│  │   brainstorming)       │      │                        │     │
│  └────────────────────────┘      └───────────┬────────────┘     │
│                                               │                   │
└───────────────────────────────────────────────┼───────────────────┘
                                                │
                        ┌───────────────────────┴────────────────────┐
                        │                                            │
                        v                                            v
        ┌───────────────────────────┐              ┌─────────────────────────────┐
        │    BEADS BRIDGE           │              │   MEMORY MCP QUERY SERVICE  │
        │  (Procedural Memory)      │              │   (Semantic Memory)         │
        │                           │              │                             │
        │  - get_ready_tasks()      │              │  - semantic_search()        │
        │  - get_task_detail()      │              │  - get_related_entities()   │
        │  - query_tasks()          │              │  - store_context()          │
        └───────────┬───────────────┘              └──────────────┬──────────────┘
                    │                                             │
                    v                                             v
        ┌───────────────────────────┐              ┌─────────────────────────────┐
        │  Beads CLI (bd)           │              │  Memory MCP Nexus Processor │
        │  - bd ready --json        │              │  - Vector RAG (40%)         │
        │  - bd show --json         │              │  - HippoRAG (40%)           │
        │  - bd list --json         │              │  - Bayesian (20%)           │
        └───────────┬───────────────┘              └──────────────┬──────────────┘
                    │                                             │
                    v                                             v
        ┌───────────────────────────┐              ┌─────────────────────────────┐
        │  .beads/issues.jsonl      │              │  ChromaDB + NetworkX        │
        │  (Git-tracked)            │              │  (Vector + Graph Storage)   │
        └───────────────────────────┘              └─────────────────────────────┘
```

### Data Flow: Query Execution

```
User Query: "What should I work on next?"
         │
         ▼
   ┌─────────────┐
   │ Mode Detect │ → "execution" (80% Beads + 20% Memory)
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │  Allocate   │ → 8000 tokens Beads, 2000 tokens Memory
   │  Budget     │
   └──────┬──────┘
          │
          ├────────────────────────────┬─────────────────────────────┐
          │                            │                             │
          ▼                            ▼                             ▼
   ┌─────────────┐          ┌──────────────────┐         ┌──────────────────┐
   │ Beads Query │          │ Memory Vector    │         │ Memory HippoRAG  │
   │ bd ready    │          │ Search           │         │ Graph Traversal  │
   └──────┬──────┘          └────────┬─────────┘         └────────┬─────────┘
          │                          │                            │
          ▼                          ▼                            ▼
   ┌──────────────────────────────────────────────────────────────┐
   │              MERGE & RANK                                     │
   │  - Deduplicate overlapping results                            │
   │  - Weight by source (80% Beads, 20% Memory)                   │
   │  - Sort by relevance + priority                               │
   └────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ Final Result │
                     │ ~10K tokens  │
                     └──────────────┘
```

---

## PART III: IMPLEMENTATION PLAN

### Week 1: Core Bridge (10-12h)

**Day 1-2: Beads Bridge (6h)**
- [ ] Create `BeadsBridge` class with async subprocess wrappers
- [ ] Implement `get_ready_tasks()`, `get_task_detail()`, `query_tasks()`
- [ ] Add TTL caching layer (60s default)
- [ ] Write unit tests with real `bd` CLI

**Day 3: Memory MCP Public API (2-3h)**
- [ ] Extract `MemoryMCPQueryService` from Nexus Processor
- [ ] Add `semantic_search()`, `get_related_entities()`, `store_context()`
- [ ] Write integration tests

**Day 4: Metadata Sync (3-4h)**
- [ ] Create `MetadataSync` class for bidirectional mapping
- [ ] Implement `beads_to_memory_mcp()` converter
- [ ] Add `sync_task_to_memory()` for closed tasks

### Week 2: Unified Router (8-10h)

**Day 1-2: Router Core (5h)**
- [ ] Create `UnifiedRetrievalRouter` class
- [ ] Implement mode-aware routing logic (80/20, 50/50, 20/80)
- [ ] Add parallel retrieval with `asyncio.gather()`
- [ ] Implement token budget allocation

**Day 3: Optimization (2h)**
- [ ] Add `_trim_to_budget()` for Beads results
- [ ] Integrate Beads `--brief`, `--fields` flags
- [ ] Add description truncation

**Day 4: Testing (3h)**
- [ ] Write integration tests for all 3 modes
- [ ] Test token budget compliance
- [ ] Test graceful degradation (if one source fails)

### Week 3 (Optional): Webhook & Polish (4-6h)

**Day 1: Webhook Receiver (3h)**
- [ ] FastAPI endpoint at `/api/v1/beads/webhook`
- [ ] Idempotency with `webhook-idempotency` pattern
- [ ] Event handling (create/update/close/comment)

**Day 2: Documentation & Polish (2-3h)**
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Integration guide with examples
- [ ] Configuration documentation

---

## PART IV: LIBRARY COMPONENT REUSE

### Existing Components to Adapt

| Library Component | Adaptation | Effort |
|-------------------|------------|--------|
| **multi-model-router** | Pattern for subprocess routing | REUSE 70% |
| **webhook-idempotency** | Webhook deduplication | REUSE 90% |
| **fastapi-router-template** | CRUD endpoint structure | REUSE 80% |
| **telemetry-bridge** | Memory MCP integration pattern | REUSE 60% |
| **circuit-breaker** | Beads CLI failure resilience | REUSE 100% |

### New Components to Build

| Component | Location | LOC Estimate | Test Coverage |
|-----------|----------|--------------|---------------|
| `memory-mcp-beads-bridge` | `src/integrations/beads_bridge.py` | 250-300 | 90%+ |
| `unified-retrieval-router` | `src/routing/unified_router.py` | 300-350 | 85%+ |
| `metadata-sync` | `src/integrations/metadata_sync.py` | 150-200 | 80%+ |
| `beads-webhook-receiver` | Backend router | 100-150 | 75%+ |

---

## PART V: TESTING STRATEGY

### Unit Tests

```python
# tests/test_beads_bridge.py
@pytest.mark.asyncio
async def test_beads_bridge_ready_tasks()
@pytest.mark.asyncio
async def test_beads_bridge_caching()
@pytest.mark.asyncio
async def test_beads_bridge_error_handling()

# tests/test_unified_router.py
@pytest.mark.asyncio
async def test_router_execution_mode()
@pytest.mark.asyncio
async def test_router_planning_mode()
@pytest.mark.asyncio
async def test_router_brainstorming_mode()
@pytest.mark.asyncio
async def test_router_token_budget()

# tests/test_metadata_sync.py
def test_beads_to_memory_mcp_conversion()
@pytest.mark.asyncio
async def test_sync_task_to_memory()
```

### Integration Tests

```python
# tests/integration/test_e2e_retrieval.py
@pytest.mark.asyncio
async def test_e2e_execution_workflow():
    """
    Full workflow test:
    1. Create Beads tasks
    2. Store semantic context in Memory MCP
    3. Query via Unified Router
    4. Verify correct routing weights
    5. Verify token budgets respected
    """
```

---

## PART VI: DEPLOYMENT CHECKLIST

### Prerequisites

- [ ] Beads installed: `npm install -g @beads/bd` or `go install github.com/steveyegge/beads/cmd/bd@latest`
- [ ] Memory MCP running with ChromaDB
- [ ] PostgreSQL for Life OS Dashboard (if using webhooks)
- [ ] Python 3.10+ with asyncio

### Configuration

```yaml
# config/beads-integration.yaml
beads:
  binary_path: "bd"  # or full path
  cache_ttl_seconds: 60
  default_limit: 10
  brief_mode: true

memory_mcp:
  data_dir: "./data"
  chroma_persist_dir: "./chroma_data"

unified_router:
  weights:
    execution:
      beads: 0.8
      memory: 0.2
    planning:
      beads: 0.5
      memory: 0.5
    brainstorming:
      beads: 0.2
      memory: 0.8

  token_budgets:
    execution: 5000
    planning: 10000
    brainstorming: 20000

metadata_sync:
  sync_on_create: false
  sync_on_close: true
  sync_on_update: false
  project_name: "life-os"
```

### Verification

```bash
# 1. Test Beads CLI
bd init --prefix test
bd create "Test integration" -p 1
bd ready --json

# 2. Test Beads Bridge
python -m pytest tests/test_beads_bridge.py -v

# 3. Test Unified Router
python -m pytest tests/test_unified_router.py -v

# 4. Test E2E workflow
python -m pytest tests/integration/test_e2e_retrieval.py -v
```

---

## PART VII: PERFORMANCE CONSIDERATIONS

### Latency Targets

| Operation | Target | Fallback |
|-----------|--------|----------|
| Beads query (bd ready) | <100ms | 200ms with cache |
| Memory semantic search | <300ms | Nexus default |
| Unified router (total) | <500ms | 1000ms acceptable |
| Webhook processing | <50ms | Async background |

### Caching Strategy

1. **Beads Bridge**: 60s TTL cache for `get_ready_tasks()`
2. **Memory MCP**: Native ChromaDB caching
3. **Router**: No caching (always fresh data)

### Scaling Considerations

- **Beads**: SQLite local-only, fast by design
- **Memory MCP**: ChromaDB scales to millions of chunks
- **Router**: Stateless, horizontally scalable

---

## PART VIII: REFERENCES

### Beads Documentation

- [GitHub: steveyegge/beads](https://github.com/steveyegge/beads)
- [Architecture Documentation](https://github.com/steveyegge/beads/blob/main/docs/ARCHITECTURE.md)
- [Claude Integration](https://github.com/steveyegge/beads/blob/main/docs/CLAUDE_INTEGRATION.md)
- [beads-mcp PyPI Package](https://pypi.org/project/beads-mcp/)
- [FastMCP: Beads MCP](https://fastmcp.me/MCP/Details/1540/beads)

### Memory MCP Documentation

- Memory MCP Project: `D:\Projects\memory-mcp-triple-system`
- Nexus Processor: `src/nexus/processor.py`
- Mode Detection: `src/modes/mode_detector.py`
- Tagging Protocol: `src/mcp/stdio_server.py`

### Library Components

- `.claude/library/catalog.json` - Component inventory
- `.claude/docs/inventories/LIBRARY-PATTERNS-GUIDE.md` - Patterns
- Multi-Model Router: `components/ai/model_router/providers.py`
- Webhook Idempotency: `patterns/webhook_idempotency/`

---

## PART IX: SUCCESS METRICS

### Functional Requirements

- [ ] Unified router correctly detects modes (execution/planning/brainstorming)
- [ ] Routing weights applied correctly (80/20, 50/50, 20/80)
- [ ] Beads tasks retrieved successfully via CLI wrapper
- [ ] Memory MCP semantic search integrated
- [ ] Token budgets respected (5K/10K/20K)
- [ ] Metadata synced between Beads and Memory MCP

### Quality Requirements

- [ ] Test coverage >85% across all components
- [ ] Latency <500ms for unified retrieval
- [ ] Graceful degradation if Beads or Memory fails
- [ ] NASA Rule 10 compliant (all functions ≤60 LOC)
- [ ] Full type annotations with mypy compliance

### Integration Requirements

- [ ] Works with existing Context Cascade skills
- [ ] Compatible with Life OS Dashboard
- [ ] Reuses library components (multi-model-router, webhook-idempotency)
- [ ] Follows WHO/WHEN/PROJECT/WHY tagging protocol

---

## PART X: NEXT STEPS

1. **Immediate (Week 1)**:
   - Implement `BeadsBridge` class
   - Extract Memory MCP public API
   - Create metadata sync layer

2. **Short-term (Week 2)**:
   - Build Unified Retrieval Router
   - Add token budget optimization
   - Write comprehensive tests

3. **Optional (Week 3)**:
   - Add webhook receiver for real-time sync
   - Polish documentation
   - Deploy to Life OS Dashboard

4. **Future Enhancements**:
   - Beads → Memory MCP automatic sync service
   - Visual dashboard for routing metrics
   - A/B testing for optimal routing weights

---

<promise>BEADS_MEMORY_MCP_INTEGRATION_MANIFEST_COMPLETE_2026_01_12</promise>
