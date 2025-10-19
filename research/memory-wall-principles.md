# Memory Wall Principles: Analysis & Integration

**Source**: "AI's Memory Wall: Why Compute Grew 60,000x But Memory Only 100x (PLUS My 8 Principles to Fix)"
**Date**: 2025-10-17
**Purpose**: Extract principles for Memory MCP Triple System design

---

## Executive Summary

### The Core Problem
> "Memory is perhaps the biggest unsolved problem in AI and it is one of the only problems in AI that is getting worse, not better."

**The Memory Wall**: Chip compute capabilities grew **60,000x** while memory capabilities only grew **100x**, creating a widening gap between intelligence and memory.

**Fundamental Tension**:
- AI systems are **stateless by design** (start from zero each conversation)
- Useful intelligence **requires state** (remembering context, history, preferences)
- Current solutions (ChatGPT memory, Claude recall) are "not good enough" - very lossy

**Why This Matters**: As AI gets smarter, the memory gap becomes MORE problematic, not less.

---

## Six Root Causes

### 1. The Relevance Problem

**What It Is**:
> "What's relevant actually changes based on the task that you're doing, the phase of your work, the scope you're in."

**Why Semantic Search Fails**:
- Semantic similarity is **only a proxy** for relevance, not a true solution
- Cannot handle: "Find the document where we decided X" (specific)
- Cannot handle: "Ignore client A, focus on B/C/D" (scoped filtering)
- Cannot handle: "Only what we decided since October 12th" (temporal)
- **No general algorithm for relevance** - requires human judgment about task context

**Healthcare Example**:
User afraid to ask health questions in ChatGPT because work (healthcare industry) and personal health data both look like "health data" - scope collision problem.

**Implications for Our Design**:
- ❌ **Don't**: Rely solely on vector similarity (Qdrant)
- ✅ **Do**: Add temporal filtering, scope tagging, multi-hop graph queries (Neo4j + HippoRAG)
- ✅ **Do**: Human-in-loop for relevance curation (UI for tagging/scoping)

### 2. Persistence Precision Trade-off

**What It Is**:
> "If you store everything, retrieval becomes very noisy and expensive. If you store selectively, you're going to lose information."

**The Dilemma**:
- Store everything → Noisy retrieval + expensive context windows
- Store selectively → Lose needed information later
- Let system decide → Optimizes for wrong thing (recency, frequency, saliency vs importance)

**Human Solution: Forgetting as Technology**:
> "Human memory is actually very good at this through the technology of forgetting."

- Lossy compression with emotional/importance weighting
- **Database keys analogy**: You remember the "key" to retrieve memory, not full detail
- Childhood memories accessible (keys retained) vs last Thursday (keys lost)
- Effort to remember = retrieving database keys, then reconstructing

**AI Problem**:
> "AI systems don't have any of that. They either accumulate or they purge, but they do not decay."

**Implications for Our Design**:
- ✅ **Do**: Implement structured "forgetting" - decay session data but keep metadata "keys"
- ✅ **Do**: Importance weighting (user tags "critical" vs "reference")
- ✅ **Do**: Bayesian Network (Week 9) for probabilistic decay/retrieval
- ❌ **Don't**: Accumulate everything hoping RAG solves it

### 3. Single Context Window Assumption

**What It Is**:
> "Vendors often try to solve memory by making context windows bigger. But volume is not the issue. The structure is the problem."

**Critical Quote**:
> "A million token context window is not a usable million token context window if it's full of unsorted context. That is worse than a tightly curated 10,000 [token window]."

**Why It Fails**:
- Model still must find what matters, parse relevance, ignore noise
- Expanding context doesn't solve problem - **makes it more expensive**
- API bills spike from stuffing context windows

**Real Solution**:
> "Requires multiple context streams with different life cycles and retrieval patterns."

**Implications for Our Design**:
- ✅ **Do**: 3 separate layers (Vector/Graph/Bayesian) with different retrieval patterns
- ✅ **Do**: Life cycle separation (permanent/temporary/ephemeral)
- ✅ **Do**: Mode-aware routing (planning vs execution)
- ❌ **Don't**: Jam everything into one giant context window

### 4. The Portability Problem

**What It Is**:
> "Every single vendor builds proprietary memory layers because they think in their pitch deck that memory is a moat."

**Vendor Lock-In Examples**:
- ChatGPT memory
- Claude recall
- Cursor memory banks
- **Not interoperable** - switching costs are real

**The Commons Problem**:
> "This behavior encourages users to leave memory to the tool rather than encouraging them to build a proper context library."

**Business Critical**:
> "From a business perspective, you have to be multimodel. It is a liability to be single model."

**Implications for Our Design**:
- ✅ **Do**: MCP (Model Context Protocol) as standard interface
- ✅ **Do**: Markdown storage (Obsidian) - portable, human-readable
- ✅ **Do**: Multi-model support (ChatGPT, Claude, Gemini)
- ✅ **Do**: Survive vendor/tool/model changes
- ❌ **Don't**: Build on proprietary APIs without abstraction layer

### 5. The Passive Accumulation Fallacy

**What It Is**:
> "Most memory features assume you just use your AI normally and it will figure out what to remember. That is the default mental model of users."

**Why It Fails**:
- System **cannot distinguish preference from fact**
- Cannot tell project-specific from evergreen context
- Doesn't know when old information is stale
- Optimizes for **continuity** (keep conversation going), not correctness

**The Hard Truth**:
> "Useful memory fundamentally requires active curation. You have to decide what to keep, what to update, and what to discard. And that is work."

**Vendor Promise vs Reality**:
- Vendors promise passive solutions (doesn't scale as product)
- Reality: Passive accumulation doesn't solve the problem either
- Costs billions at enterprise level, extremely frustrating for users

**Implications for Our Design**:
- ✅ **Do**: Active curation UI (tagging, updating, discarding)
- ✅ **Do**: Human-in-loop for critical facts
- ✅ **Do**: Update workflows (detect stale data, prompt user)
- ❌ **Don't**: Assume LLM can auto-curate correctly

### 6. Memory is Multiple Problems

**What It Is**:
> "When people say AI memory, what they really mean is any number of [different things]."

**Memory Types**:

| Type | Description | Storage Pattern | Update Pattern |
|------|-------------|-----------------|----------------|
| **Preferences** | How I like things done | Key-value | Persistent |
| **Facts** | What's true about entities | Structured (SQL/Graph) | Needs updates |
| **Knowledge (Parametric)** | Domain expertise | Model weights | Embedded in model |
| **Knowledge (Episodic)** | Conversational, temporal | Vector (semantic) | Ephemeral |
| **Knowledge (Procedural)** | How we solved this before | Exemplars (graph/vector) | Successes/failures |

**Critical Insight**:
> "Every single memory type needs different system design to handle storage retrieval and update patterns. Treating this problem as one problem guarantees you are going to solve none of the real problems well."

**Implications for Our Design**:
- ✅ **Do**: Match storage to memory type (key-value, structured, vector, graph)
- ✅ **Do**: Separate retrieval strategies per type
- ✅ **Do**: Different update workflows per type
- ❌ **Don't**: Use RAG for everything (square peg, round hole)

---

## Eight Solution Principles

### Principle 1: Memory is an Architecture (Not a Feature)

**What It Means**:
> "You cannot wait for vendors to solve this. Every tool will have memory capabilities, but if you leave it to tools, they will solve different slices."

**Your Responsibility**:
- Architect memory as **standalone system** that works across all tools
- Principles that work across chat, agentic systems, enterprise platforms (fractal)

**How We Apply It**:
```yaml
# Memory Architecture (not vendor feature)
obsidian_vault:
  location: ~/Documents/Memory-Vault
  format: markdown
  portable: true

mcp_server:
  interface: standardized
  tools: [vector_search, graph_query, probabilistic_query]

storage_layers:
  layer1_vector: qdrant (docker)
  layer2_graph: neo4j (docker)
  layer3_bayesian: custom (python)
```

**Fractal Principle**: Same architecture works for personal chat AND enterprise agentic systems.

### Principle 2: Separate by Life Cycle (Not by Convenience)

**What It Means**:
> "You need to separate personal preferences (permanent) from project facts (temporary) from session state (ephemeral)."

**Critical Warning**:
> "Mixing different life cycle states - mixing permanent with temporary with ephemeral - it just breaks memory."

**Life Cycle Separation**:

| Life Cycle | Example | Storage | Retrieval | Update |
|------------|---------|---------|-----------|--------|
| **Permanent** | Personal preferences (writing style) | Key-value (Redis) | Always loaded | Rare |
| **Temporary** | Project facts (client requirements) | Structured (Neo4j) | Scoped query | Regular |
| **Ephemeral** | Session state (conversation context) | Vector (Qdrant) | Semantic search | Constant |

**Chat Example**:
```markdown
# System Prompt (Permanent Preferences)
- Writing style: Technical, concise, bullet points
- Output format: Markdown with code examples
- NASA Rule 10: ≤60 LOC per function

# Project Context (Temporary Facts)
- Project: Memory MCP Triple System
- Client: Personal use
- Timeline: 12 weeks
- Stack: Python, Qdrant, Neo4j

# Session State (Ephemeral)
- Current task: Loop 1 planning
- Last output: Research document
- Next step: Pre-mortem
```

**How We Apply It**:
```python
# src/utils/lifecycle_manager.py
class LifecycleManager:
    def store(self, data: dict, lifecycle: str):
        if lifecycle == "permanent":
            # Redis key-value
            self.redis.set(f"pref:{key}", value)
        elif lifecycle == "temporary":
            # Neo4j with TTL metadata
            self.neo4j.create_node(data, ttl="project")
        elif lifecycle == "ephemeral":
            # Qdrant vector with session tag
            self.qdrant.upsert(embedding, metadata={"session_id": id})
```

### Principle 3: Match Storage to Query Pattern

**What It Means**:
> "Different questions require different retrieval. You need multiple stores."

**Query Pattern Matrix**:

| Query | Storage Type | Example | Retrieval Method |
|-------|--------------|---------|------------------|
| "What is my style?" | **Key-Value** | Redis | Direct lookup |
| "What is client ID?" | **Structured** | Neo4j/SQL | Relational query |
| "Similar work we've done?" | **Semantic** | Qdrant | Vector similarity |
| "What did we do last time?" | **Event Logs** | TimescaleDB | Temporal query |

**Anti-Pattern**:
> "Trying to do all of these in one storage pattern is going to fail. When people say 'We have our data lake and it's going to be a RAG,' I'm like, why? Have you heard the word RAG repeated a hundred times like a magic spell for memory? It does not work that way."

**How We Apply It**:
```python
# src/routing/storage_router.py
class StorageRouter:
    def route_query(self, query: str, query_type: str):
        if query_type == "preference":
            return self.redis.get(query)  # Key-value
        elif query_type == "fact":
            return self.neo4j.query(query)  # Structured
        elif query_type == "semantic":
            return self.qdrant.search(query)  # Vector
        elif query_type == "temporal":
            return self.timescale.query(query)  # Event logs
```

### Principle 4: Mode-Aware Context Beats Volume

**What It Means**:
> "More context is not better context. Planning conversations need breadth. Execution conversations need precision."

**Mode Requirements**:
- **Planning/Brainstorming**: Breadth, alternatives, comparables, space to range
- **Execution**: Precision, constraints, audited for correctness

**Critical Insight**:
> "Retrieval strategy needs to match your task type."

**Chat Application**:
- Prompting = giving mode-aware context to AI
- "I'm brainstorming, give me wild ideas" vs "Execute this precisely"

**Agentic Application**:
- Architect mode awareness into system
- Eval on precision for execution environments
- Allow breadth for planning environments

**How We Apply It**:
```python
# src/routing/mode_detector.py
class ModeDetector:
    def detect_mode(self, query: str) -> str:
        # Planning keywords
        if any(word in query for word in ["brainstorm", "explore", "alternatives"]):
            return "planning"  # Breadth retrieval

        # Execution keywords
        if any(word in query for word in ["implement", "deploy", "execute"]):
            return "execution"  # Precision retrieval

        return "default"

# src/retrieval/mode_aware_retrieval.py
class ModeAwareRetrieval:
    def retrieve(self, query: str, mode: str):
        if mode == "planning":
            # Breadth: top-k=20, diverse results
            return self.qdrant.search(query, limit=20, diversity=0.7)
        elif mode == "execution":
            # Precision: top-k=5, high similarity threshold
            return self.qdrant.search(query, limit=5, threshold=0.85)
```

### Principle 5: Build Portable as a First-Class Object

**What It Means**:
> "Your memory layer needs to survive vendor changes, tool changes, model changes."

**Survival Criteria**:
- ✅ ChatGPT changes pricing → memory still works
- ✅ Claude adds feature → memory still works
- ✅ Switch from Anthropic to OpenAI → memory still works

**Current State (Bad)**:
> "Almost nobody can say right now [their memory survives these changes]. People who are doing it tend to be designing very large scale agentic AI systems at the enterprise level."

**Best Practice**:
> "It is sort of like keeping a go bag next to the door in case you need to get out."

**How Power Users Do It**:
- Configure Obsidian (note-taking app)
- Markdown storage (portable, human-readable)
- Tie into AI via plugins/APIs
- Platform-independent

**How We Apply It**:
```yaml
# config/portability.yaml
storage:
  format: markdown  # Human-readable, universal
  location: obsidian_vault  # User-controlled, not vendor

interface:
  protocol: MCP  # Model Context Protocol (standard)
  tools:
    - vector_search  # Works with any LLM
    - graph_query
    - probabilistic_query

models:
  - chatgpt  # OpenAI
  - claude   # Anthropic
  - gemini   # Google
  # Add new models easily - MCP abstraction layer
```

**Implementation**:
```python
# src/mcp/portable_server.py
class PortableMCPServer:
    """MCP server that works with any model."""

    def register_tools(self):
        """Tools are model-agnostic."""
        return [
            Tool("vector_search", self.vector_search),
            Tool("graph_query", self.graph_query),
            Tool("probabilistic_query", self.prob_query)
        ]

    def vector_search(self, query: str):
        """Works regardless of which LLM calls it."""
        results = self.qdrant.search(query)
        return self.format_portable(results)
```

### Principle 6: Compression is Curation

**What It Means**:
> "Do not upload 40 pages hoping the AI extracts what matters. You need to do the compression work."

**Your Responsibility**:
- Write the brief
- Identify key facts
- State constraints
- **This is where judgment lives**

**Anti-Pattern**:
User uploads 40-page report, asks for analysis, hopes AI extracts what matters.

**Better Pattern**:
1. Use AI to extract structured data (separate call)
2. YOU verify facts are correct
3. YOU decide what constraints matter
4. YOU compress to brief with judgment applied

**Critical Insight**:
> "Memory is bound up in how we humans touch the work. The judgment in compression is human judgment. It may be human judgment that you amplify with AI, but it remains human judgment."

**How We Apply It**:
```python
# src/curation/compression_workflow.py
class CompressionWorkflow:
    def compress_document(self, doc_path: str):
        # Step 1: AI extracts structured data
        extracted = self.llm.extract_facts(doc_path)

        # Step 2: Human verifies facts (UI prompt)
        verified = self.ui.verify_facts(extracted)

        # Step 3: Human identifies key constraints
        constraints = self.ui.identify_constraints(verified)

        # Step 4: Human writes brief (AI assists)
        brief = self.ui.write_brief(verified, constraints)

        # Step 5: Store compressed version
        self.store(brief, lifecycle="temporary")

        return brief  # Much smaller than 40 pages
```

**UI for Curation** (Week 3):
```markdown
# Curation Interface
[Document: project-requirements.pdf - 40 pages]

## Extracted Facts (AI)
- Client: Acme Corp
- Budget: $500k
- Timeline: 6 months
- Stack: Python, React

[✓] Verified  [Edit] [Discard]

## Constraints (You Decide)
- Must use existing AWS infrastructure
- PCI compliance required
- Team size: 5 developers

[Add Constraint]

## Brief (You Write, AI Assists)
"Acme Corp project: $500k budget, 6-month timeline, 5 devs.
Must integrate with AWS, meet PCI compliance. Stack: Python/React."

[Save as Temporary] [Save as Permanent] [Discard]
```

### Principle 7: Retrieval Needs Verification

**What It Means**:
> "Semantic search will recall well but fail on specifics. You need to pair fuzzy retrieval with exact verification."

**Two-Stage Retrieval**:
1. **Recall candidates** (semantic/graph search)
2. **Verify against ground truth** (structured data)

**Critical Example - $500k Fine**:
> "There was a very prominent fine leveled against a major consultant firm in the last two weeks. Close to half a million dollars because they could not verify facts around court cases in a document. They hallucinated them and didn't catch them. Retrieval failed."

**Why LLMs Hallucinate Here**:
> "The LLM is designed to keep the conversation going, it just inserted something plausible and nobody caught it."

**How We Apply It**:
```python
# src/retrieval/verified_retrieval.py
class VerifiedRetrieval:
    def retrieve_with_verification(self, query: str, require_verification: bool = True):
        # Stage 1: Recall candidates (fuzzy)
        candidates = self.qdrant.search(query, limit=20)

        if not require_verification:
            return candidates  # Fast path for non-critical queries

        # Stage 2: Verify against ground truth (exact)
        verified = []
        for candidate in candidates:
            # Check against structured data
            if self.verify_fact(candidate):
                verified.append(candidate)
            else:
                # Log hallucination attempt
                self.log_hallucination(candidate, query)

        return verified

    def verify_fact(self, candidate: dict) -> bool:
        """Verify against ground truth sources."""
        # Example: Legal case verification
        if candidate["type"] == "legal_case":
            case_id = candidate["case_id"]
            # Query authoritative database
            ground_truth = self.legal_db.get_case(case_id)
            return ground_truth is not None

        # Example: Client fact verification
        if candidate["type"] == "client_fact":
            client_id = candidate["client_id"]
            ground_truth = self.crm.get_client(client_id)
            return ground_truth["name"] == candidate["client_name"]

        return True  # No verification needed
```

**When to Verify**:
- **Always**: Legal facts, financial data, policy statements
- **Optional**: Brainstorming ideas, draft content
- **Never**: Session ephemera (conversation flow)

**Human Verification (Small Scale)**:
```markdown
# Query: "What did we decide about API authentication?"

## Recalled Candidates (Semantic Search):
1. "We decided to use OAuth2 with JWT tokens" (similarity: 0.92)
2. "API authentication should be robust" (similarity: 0.78)
3. "Consider OAuth2 or API keys" (similarity: 0.75)

[⚠️ Verify before using in production]

## Verify:
- Source: meeting-notes-2025-10-15.md
- Attendees: John, Sarah, Mike
- Decision: OAuth2 + JWT
- Status: Approved

[✓ Verified - Safe to Use]
```

### Principle 8: Memory Compounds Through Structure

**What It Means**:
> "Random accumulation does not compound. It just creates noise. Just adding stuff doesn't compound."

**Human Analogy**:
> "If we just added memories randomly the way we experience them in life and we had no lossiness, no forgetting ability, we would not be able to function as people. Forgetting is a technology for us."

**Structured Memory as Technology**:
- Evergreen context → One place
- Version prompts → Another place
- Tagged exemplars → Another place

**Benefits of Structure**:
> "You let each interaction build without degradation if you have structured memory. Otherwise, you just have random accumulation. Otherwise, you have the pile of transcripts you never got to, and you're like, 'Well, this is data. We're logging it. It's probably good.' It just creates noise."

**How We Apply It**:
```
memory-mcp-triple-system/
├── obsidian_vault/
│   ├── permanent/           # Evergreen context
│   │   ├── preferences.md
│   │   ├── writing-style.md
│   │   └── values.md
│   ├── projects/            # Temporary, scoped
│   │   ├── memory-system/
│   │   │   ├── requirements.md
│   │   │   ├── decisions.md
│   │   │   └── archive/
│   │   └── other-project/
│   ├── sessions/            # Ephemeral, auto-expire
│   │   ├── 2025-10-17/
│   │   └── 2025-10-16/
│   └── exemplars/           # Procedural knowledge
│       ├── successful-patterns/
│       └── failed-attempts/
```

**Structured Storage**:
```python
# src/storage/structured_store.py
class StructuredStore:
    def store(self, data: dict, structure: str):
        # Evergreen context
        if structure == "evergreen":
            path = f"permanent/{data['category']}.md"
            self.append_to_file(path, data)

        # Project context
        elif structure == "project":
            path = f"projects/{data['project_id']}/{data['type']}.md"
            self.write_versioned(path, data)

        # Session context
        elif structure == "session":
            path = f"sessions/{data['date']}/{data['session_id']}.md"
            self.write_with_ttl(path, data, ttl_days=30)

        # Exemplars
        elif structure == "exemplar":
            path = f"exemplars/{data['outcome']}/{data['pattern']}.md"
            self.tag_and_store(path, data)
```

**Compounding Effect**:
- **Month 1**: 100 structured facts stored
- **Month 6**: 600 structured facts, easy to query ("What did we decide in March?")
- **Year 1**: 1,200 structured facts, patterns emerge ("We always fail at X step")

**vs Random Accumulation**:
- **Month 1**: 100 random notes
- **Month 6**: 600 random notes, impossible to find anything
- **Year 1**: 1,200 random notes, "pile of transcripts you never got to"

---

## Human Memory as Model

### Forgetting as Technology

**Database Keys Analogy**:
> "Your brain is desperately compressing information to make it useful to you and has dumped out those database keys. And when you go to the effort of remembering, you're literally retrieving the database keys to get the memory back."

**Memory Decay**:
- Childhood memories: Keys retained (high emotional/importance weight) → accessible
- Last Thursday: Keys lost (low importance) → inaccessible unless you reconstruct

**The Reconstruction Process**:
```
User: "Did we go to the movies last Thursday?"
Brain: [searches for key] → Not found
User: "What movies are playing?"
Brain: [trigger] "Oh yeah, we saw that movie!"
Brain: [key retrieved] → Full memory accessible
```

**Lossy Compression**:
- Memory decays into approximation (the "key")
- Effort retrieves full detail from key
- Emotional/importance weighting determines what keys to keep

### Implications for AI Systems

**AI Has No Decay**:
> "AI systems don't have any of that. They either accumulate or they purge, but they do not decay."

**What We Need**:
1. **Decay mechanism**: Session data loses detail over time, keeps "keys" (metadata)
2. **Importance weighting**: User/LLM tags critical vs reference
3. **Reconstruction**: Retrieval effort = re-expanding from keys (query formulation)

**How We Apply It**:
```python
# src/bayesian/memory_decay.py
class MemoryDecay:
    def decay_session_memory(self, session_id: str, days_old: int):
        """Decay session memory while keeping retrieval keys."""
        session = self.get_session(session_id)

        # Calculate decay factor (exponential)
        decay_factor = math.exp(-days_old / 30)  # 30-day half-life

        if decay_factor < 0.1:
            # Compress to keys only (metadata)
            keys = {
                "date": session["date"],
                "topic": session["topic"],
                "participants": session["participants"],
                "outcome": session["outcome"],
                "tags": session["tags"]
            }
            # Discard full transcript
            self.store_keys_only(session_id, keys)

        elif decay_factor < 0.5:
            # Compress to summary + keys
            summary = self.llm.summarize(session["transcript"])
            self.store_summary(session_id, summary, keys)

        else:
            # Keep full detail (recent)
            pass

    def retrieve_from_key(self, key: dict):
        """Attempt reconstruction from key metadata."""
        # If user queries old session
        if "full_transcript" not in key:
            # Attempt reconstruction
            return f"Session on {key['date']} about {key['topic']}. Outcome: {key['outcome']}. [Full transcript not available - decay applied]"
        else:
            return key["full_transcript"]
```

---

## Memory Types Matrix

| Type | Example | Storage | Query Pattern | Lifecycle | Update | Verification |
|------|---------|---------|---------------|-----------|--------|--------------|
| **Preferences** | Writing style, output format | Key-Value (Redis) | Direct lookup | Permanent | Rare | Manual |
| **Facts** | Client ID, project budget | Structured (Neo4j) | Relational/Graph | Temporary | Regular | Always |
| **Knowledge (Episodic)** | "What we discussed last week" | Vector (Qdrant) | Semantic similarity | Session | Constant | Optional |
| **Knowledge (Procedural)** | "How we solved X before" | Graph+Vector | Exemplar search | Project | On completion | Manual |
| **Knowledge (Parametric)** | Domain expertise (Python syntax) | Model weights | N/A | Permanent | N/A (in model) | N/A |

---

## Obsidian Integration Strategy

### Why Obsidian Works

**Transcript Mentions**:
> "Power users configure Obsidian for this. The thing that is a common trait is that they are obsessed with making sure the memory is configured correctly for them and the AI has to come in and be queried correctly or called correctly to engage with a piece of the memory that matters."

**Key Features**:
1. **Markdown-native**: Portable, human-readable, universal format
2. **Graph view**: Visualizes relationships between notes
3. **Backlinks**: Automatic bidirectional links
4. **Platform-independent**: Works on Mac, Windows, Linux, mobile
5. **Plugin ecosystem**: Can tie into AI systems via plugins/APIs

### Power User Pattern

**What They Do**:
1. Structure Obsidian vault by lifecycle (permanent/projects/sessions)
2. Use frontmatter for metadata (tags, dates, importance)
3. Link notes to create knowledge graph
4. Query AI with specific note references
5. AI reads relevant notes, returns structured responses
6. User curates: tags, updates, archives

**Example Obsidian Note**:
```markdown
---
title: Memory MCP Triple System
type: project
lifecycle: temporary
importance: high
tags: [ai, memory, rag, mcp]
created: 2025-10-17
updated: 2025-10-17
---

# Memory MCP Triple System

## Overview
Building a portable, multi-model memory system using:
- Layer 1: Vector RAG (Qdrant)
- Layer 2: GraphRAG (Neo4j + HippoRAG)
- Layer 3: Bayesian Networks

## Decisions
- [[decision-use-qdrant|Use Qdrant for vector store]]
- [[decision-obsidian-storage|Use Obsidian for portable storage]]

## Related
- [[hirag-research|HiRAG Research]]
- [[hipporag-paper|HippoRAG Paper]]
- [[memory-wall-principles|Memory Wall Principles]]
```

**AI Query Example**:
```
User: "What did we decide about vector databases?"

AI Tool Call: obsidian_query("vector database decision")

Obsidian Returns: [[decision-use-qdrant]] note

AI Response: "You decided to use Qdrant for the vector store because:
1. Best performance (1,238 QPS, 99% recall)
2. Self-hosted (privacy)
3. Lowest cost ($0.014/hr)
Source: [[decision-use-qdrant]] from 2025-10-17"
```

### How We Integrate

**Week 1-2: Obsidian Sync**:
```python
# src/obsidian/file_watcher.py
class ObsidianSync:
    def __init__(self, vault_path: str):
        self.vault_path = vault_path
        self.watcher = Observer()

    def start(self):
        """Watch Obsidian vault for changes."""
        handler = ObsidianHandler(self)
        self.watcher.schedule(handler, self.vault_path, recursive=True)
        self.watcher.start()

    def on_file_created(self, file_path: str):
        """Auto-index new Obsidian notes."""
        metadata = self.parse_frontmatter(file_path)
        content = self.read_markdown(file_path)

        # Index in appropriate store based on lifecycle
        if metadata.get("lifecycle") == "permanent":
            self.redis.set(metadata["title"], content)
        elif metadata.get("lifecycle") == "temporary":
            self.neo4j.create_node(content, metadata)
        else:  # ephemeral
            embedding = self.embed(content)
            self.qdrant.upsert(embedding, metadata)

    def parse_frontmatter(self, file_path: str) -> dict:
        """Extract YAML frontmatter from markdown."""
        with open(file_path) as f:
            content = f.read()
        match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
        if match:
            return yaml.safe_load(match.group(1))
        return {}
```

---

## Portability Requirements

### The Vendor Lock-In Problem

**Current State**:
- **ChatGPT memory**: Proprietary, OpenAI-only
- **Claude recall**: Proprietary, Anthropic-only
- **Cursor memory banks**: Proprietary, Cursor-only

**Non-Interoperable by Design**:
> "The model makers like that because it makes the switching cost real and you can't port what ChatGPT knows about me to Claude and your memory is locked in."

**Switching Costs**:
- Lose all accumulated memory when changing vendors
- Cannot use best model for each task
- Vendor pricing changes force difficult migration

### Our Portability Strategy

**MCP as Standard Interface**:
```yaml
# config/mcp_config.json
{
  "name": "memory-mcp-server",
  "version": "1.0.0",
  "tools": [
    {
      "name": "vector_search",
      "description": "Semantic search over memory",
      "parameters": {
        "query": {"type": "string"},
        "limit": {"type": "integer", "default": 10}
      }
    },
    {
      "name": "graph_query",
      "description": "Multi-hop graph queries",
      "parameters": {
        "query": {"type": "string"},
        "hops": {"type": "integer", "default": 3}
      }
    },
    {
      "name": "probabilistic_query",
      "description": "Bayesian probabilistic queries",
      "parameters": {
        "query": {"type": "string"},
        "confidence_threshold": {"type": "number", "default": 0.7}
      }
    }
  ]
}
```

**Markdown Storage (Obsidian)**:
- ✅ Portable: Works with any tool that reads markdown
- ✅ Human-readable: You can read/edit without AI
- ✅ Version control: Git-friendly
- ✅ Future-proof: Markdown won't die

**Multi-Model Support**:
```python
# src/mcp/multi_model_client.py
class MultiModelClient:
    def __init__(self):
        self.models = {
            "chatgpt": OpenAIClient(mcp_server_url),
            "claude": AnthropicClient(mcp_server_url),
            "gemini": GoogleClient(mcp_server_url)
        }

    def query(self, query: str, model: str = "auto"):
        """Query any model with same memory backend."""
        if model == "auto":
            model = self.choose_model(query)

        # All models use same MCP tools
        return self.models[model].query_with_tools(query)

    def choose_model(self, query: str):
        """Choose best model for task."""
        if "code" in query:
            return "claude"  # Best for code
        elif "creative" in query:
            return "chatgpt"  # Best for creative
        else:
            return "gemini"  # Best for search
```

**Survival Criteria**:
- ✅ **Vendor change**: OpenAI → Anthropic → Google (MCP abstraction)
- ✅ **Tool change**: ChatGPT → Claude Desktop → Custom app (markdown storage)
- ✅ **Model change**: GPT-4 → Claude-3.5 → Gemini-2 (MCP tools)
- ✅ **Pricing change**: Switch to cheaper model instantly
- ✅ **Feature change**: Vendor adds/removes features, you're independent

---

## Critical Design Decisions

### What NOT to Do ❌

1. **❌ Single Context Window Solve**
   - Don't jam everything into one giant context
   - Volume ≠ better (creates noise + cost)

2. **❌ Passive Accumulation**
   - Don't assume LLM can auto-curate
   - System can't distinguish preference from fact

3. **❌ Semantic Search as Only Retrieval**
   - Semantic similarity is proxy, not solution
   - Fails on specific queries ("find where we decided X")

4. **❌ Vendor-Locked Memory**
   - Don't build on proprietary APIs without abstraction
   - Creates switching costs, vendor dependence

5. **❌ Volume Over Structure**
   - Don't just log everything hoping it helps
   - Random accumulation = noise, not memory

6. **❌ One Storage Pattern for All**
   - Don't use RAG for everything
   - Different queries need different storage

### What TO Do ✅

1. **✅ Multiple Storage Types Matched to Query Patterns**
   - Key-value (preferences)
   - Structured (facts)
   - Semantic (episodic knowledge)
   - Graph (procedural knowledge)

2. **✅ Active Curation (Human Judgment)**
   - UI for tagging, updating, discarding
   - Compression is curation
   - Human verifies critical facts

3. **✅ Two-Stage Retrieval (Recall + Verify)**
   - Stage 1: Semantic search (recall candidates)
   - Stage 2: Verify against ground truth (structured data)
   - Prevents $500k hallucination fines

4. **✅ Life Cycle Separation (Permanent/Temporary/Ephemeral)**
   - Don't mix different life cycles
   - Clear separation prevents memory pollution

5. **✅ Mode-Aware Context (Planning vs Execution)**
   - Planning: Breadth retrieval, alternatives
   - Execution: Precision retrieval, constraints

6. **✅ Portable First (MCP + Markdown)**
   - Survives vendor/tool/model changes
   - Human-readable, version-controlled

7. **✅ Structured Memory (Tagged, Versioned, Scoped)**
   - Evergreen → One place
   - Projects → Another place
   - Sessions → Another place
   - Compounding effect over time

---

## Integration with Our Hybrid RAG Design

### Layer 1: Vector RAG (Qdrant + Sentence-Transformers)

**Handles**: Episodic knowledge (semantic search)

**Query Pattern**: "Similar work we've done", "What discussions mentioned X?"

**Lifecycle**: Session/Project (temporary/ephemeral)

**Principles Applied**:
- **#3**: Match storage to query pattern (vector for semantic)
- **#8**: Structured memory (tagged sessions in Qdrant)

**How It Works**:
```python
# Episodic memory storage
session = {
    "content": "Discussion about memory systems...",
    "metadata": {
        "date": "2025-10-17",
        "topic": "memory architecture",
        "lifecycle": "ephemeral",
        "importance": "medium",
        "session_id": "abc123"
    }
}

# Index in Qdrant
embedding = sentence_transformer.encode(session["content"])
qdrant.upsert(
    collection="episodic_memory",
    points=[{
        "id": session["session_id"],
        "vector": embedding,
        "payload": session["metadata"]
    }]
)

# Query
query = "What did we discuss about architecture?"
query_embedding = sentence_transformer.encode(query)
results = qdrant.search(
    collection="episodic_memory",
    query_vector=query_embedding,
    limit=10,
    query_filter={
        "must": [
            {"key": "topic", "match": {"value": "architecture"}}
        ]
    }
)
```

### Layer 2: GraphRAG (Neo4j + HippoRAG)

**Handles**: Facts + Procedural knowledge (multi-hop queries)

**Query Pattern**: "What did we decide about X?", "How did we solve Y before?", "What's connected to Z?"

**Lifecycle**: Project/Permanent (temporary/permanent)

**Principles Applied**:
- **#3**: Match storage to query pattern (graph for relationships)
- **#7**: Retrieval needs verification (graph facts verified against structured data)

**How It Works**:
```cypher
// Store decision (fact)
CREATE (d:Decision {
  title: "Use Qdrant for Vector Store",
  date: "2025-10-17",
  rationale: "Best performance, self-hosted, low cost",
  lifecycle: "temporary",
  project: "memory-mcp-system"
})

// Link to related concepts
MATCH (p:Project {name: "memory-mcp-system"})
MATCH (d:Decision {title: "Use Qdrant for Vector Store"})
CREATE (p)-[:HAS_DECISION]->(d)

// Multi-hop query with HippoRAG
MATCH path = (p:Project)-[:HAS_DECISION]->(d:Decision)-[:INFLUENCES]->(i:Implementation)
WHERE p.name = "memory-mcp-system"
RETURN path
```

**HippoRAG Multi-Hop**:
```python
# Query: "What decisions influence our implementation?"
from hipporag import HippoRAG

hippo = HippoRAG(neo4j_url, qdrant_client)
results = hippo.query(
    "What decisions influence our implementation?",
    max_hops=3,
    use_ppr=True  # Personalized PageRank
)

# 10-30x faster than iterative RAG
# 20% better accuracy on multi-hop
```

### Layer 3: Bayesian Network (Probabilistic Reasoning)

**Handles**: Uncertainty quantification, decision support

**Query Pattern**: "How confident are we?", "What's the probability X is correct?", "What if Y changes?"

**Lifecycle**: Ephemeral (decision support sessions)

**Principles Applied**:
- **#4**: Mode-aware context (Bayesian for decision-making mode)
- **#7**: Retrieval needs verification (probabilistic confidence scores)

**How It Works**:
```python
# Bayesian network for decision confidence
from pgmpy.models import BayesianNetwork
from pgmpy.inference import VariableElimination

# Define network
model = BayesianNetwork([
    ('VectorDBPerformance', 'UseQdrant'),
    ('Cost', 'UseQdrant'),
    ('SelfHosted', 'UseQdrant'),
    ('UseQdrant', 'ProjectSuccess')
])

# Query probability
inference = VariableElimination(model)
result = inference.query(
    variables=['ProjectSuccess'],
    evidence={'UseQdrant': 'yes'}
)

# Returns: P(ProjectSuccess | UseQdrant=yes) = 0.87
```

**Uncertainty Scoring**:
```python
# Query: "Should we use Qdrant?"
query_result = {
    "recommendation": "Use Qdrant",
    "confidence": 0.87,
    "reasoning": {
        "performance": 0.95,  # Strong evidence
        "cost": 0.82,         # Good evidence
        "self_hosted": 0.91   # Strong evidence
    },
    "uncertainty": 0.13
}

# If uncertainty > 0.2, flag for human review
if query_result["uncertainty"] > 0.2:
    prompt_human_review()
```

### Obsidian as Universal Layer

**Handles**: All memory types (unified markdown interface)

**Query Pattern**: Human + AI access to all data

**Lifecycle**: Permanent (user-curated, never auto-deleted)

**Principles Applied**:
- **#1**: Memory is architecture (Obsidian is the foundation)
- **#2**: Separate by lifecycle (vault structure)
- **#5**: Build portable (markdown format)
- **#6**: Compression is curation (human writes notes)
- **#8**: Memory compounds through structure (graph of notes)

**Vault Structure**:
```
obsidian_vault/
├── permanent/
│   ├── preferences.md          # Lifecycle: permanent
│   ├── writing-style.md
│   └── core-values.md
├── projects/
│   ├── memory-mcp-system/      # Lifecycle: temporary (project)
│   │   ├── requirements.md
│   │   ├── decisions.md
│   │   ├── research/
│   │   └── archive/
│   └── other-project/
├── sessions/
│   ├── 2025-10-17/             # Lifecycle: ephemeral (30-day TTL)
│   │   ├── loop1-planning.md
│   │   └── research-session.md
│   └── 2025-10-16/
└── exemplars/
    ├── successful-patterns/     # Lifecycle: permanent (procedural)
    │   ├── tdd-workflow.md
    │   └── api-design-pattern.md
    └── failed-attempts/
        └── passive-rag-fails.md
```

**AI Access via MCP**:
```python
# src/mcp/obsidian_tools.py
class ObsidianMCPTools:
    def search_vault(self, query: str, scope: str = "all"):
        """MCP tool: search Obsidian vault."""
        if scope == "permanent":
            search_path = "obsidian_vault/permanent/"
        elif scope == "project":
            search_path = f"obsidian_vault/projects/{current_project}/"
        else:
            search_path = "obsidian_vault/"

        # Search markdown files
        results = self.grep_markdown(search_path, query)
        return self.format_for_llm(results)

    def get_note(self, note_path: str):
        """MCP tool: retrieve specific Obsidian note."""
        full_path = f"obsidian_vault/{note_path}"
        content = self.read_markdown(full_path)
        metadata = self.parse_frontmatter(content)
        return {"content": content, "metadata": metadata}
```

---

## Pre-Mortem Risk Integration

### Risks Identified from Memory Wall Transcript

#### Risk 1: Relevance Failure (P1)

**Description**: Semantic search alone won't handle specific queries like "find where we decided X" or "ignore client A, focus on B/C/D"

**Probability**: High (explicitly stated problem in transcript)

**Impact**: High (retrieval returns wrong information, decisions based on incorrect context)

**Mitigation**:
- ✅ Add temporal filtering (Neo4j graph queries)
- ✅ Add scope tagging (metadata in Qdrant)
- ✅ Multi-hop GraphRAG (HippoRAG for "what did we decide" queries)
- ✅ Human verification UI for critical queries

**Owner**: ML Developer (Week 5-6: GraphRAG implementation)

#### Risk 2: Context Window Bloat (P2)

**Description**: Expanding context window creates noise and cost, doesn't solve structure problem. "A million token context window full of unsorted context is worse than a tightly curated 10,000."

**Probability**: Medium (common anti-pattern)

**Impact**: Medium (high API costs, noisy retrieval)

**Mitigation**:
- ✅ Structured retrieval (only load relevant lifecycle)
- ✅ Mode-aware context (planning=breadth, execution=precision)
- ✅ Compression via curation (human writes briefs)
- ✅ Lifecycle separation (don't load everything)

**Owner**: Performance Engineer (Week 11: optimization)

#### Risk 3: Vendor Lock-In (P0)

**Description**: "Every vendor builds proprietary memory layers. ChatGPT memory, Claude recall, Cursor banks - not interoperable. Users invest time, switching costs are real."

**Probability**: High (default vendor behavior)

**Impact**: Critical (lose all memory when switching models/tools)

**Mitigation**:
- ✅ MCP as standard interface (Week 2)
- ✅ Markdown storage in Obsidian (Week 1)
- ✅ Multi-model support (Week 2: ChatGPT + Claude + Gemini)
- ✅ Abstraction layer (MCP server decouples storage from models)

**Owner**: Backend Dev (Week 1-2: MCP server)

#### Risk 4: Passive Accumulation (P1)

**Description**: "System cannot distinguish preference from fact. Doesn't know when old information is stale. Optimizes for continuity (keep conversation going), not correctness."

**Probability**: High (default LLM behavior)

**Impact**: High (incorrect facts persist, memory pollution)

**Mitigation**:
- ✅ Active curation UI (Week 3: tagging, updating, discarding)
- ✅ Lifecycle tagging (permanent/temporary/ephemeral)
- ✅ Stale data detection (version tracking, temporal queries)
- ✅ Update workflows (prompt user when facts change)

**Owner**: Frontend Dev (Week 3: curation interface)

#### Risk 5: Stale Information (P1)

**Description**: Old facts persist incorrectly. "If you've ever wondered why ChatGPT talks about old AI models as if they are active today, that is the same issue."

**Probability**: High (no automatic staleness detection)

**Impact**: High (decisions based on outdated facts)

**Mitigation**:
- ✅ Version tagging (metadata: created_date, updated_date)
- ✅ Temporal queries (Neo4j: "decisions since October 12th")
- ✅ Update prompts (UI: "This fact is 6 months old, still correct?")
- ✅ Archive old data (move to archive/, keep retrieval keys)

**Owner**: Backend Dev (Week 5: versioning + archival)

#### Risk 6: Hallucination Without Verification (P0)

**Description**: "$500k fine against consultant firm - hallucinated court cases in legal document. Retrieval failed. LLM designed to keep conversation going, inserted something plausible, nobody caught it."

**Probability**: Medium (common in production systems without verification)

**Impact**: Critical (legal liability, financial loss, reputation damage)

**Mitigation**:
- ✅ Two-stage retrieval (Week 7: recall + verify)
- ✅ Ground truth databases (Neo4j structured facts)
- ✅ Verification flags (UI: ⚠️ Unverified, ✅ Verified)
- ✅ Human-in-loop for legal/financial/policy facts

**Owner**: Security Manager + Backend Dev (Week 7: verification layer)

#### Risk 7: Single Storage Pattern (P2)

**Description**: "Trying to do all of [key-value, structured, semantic, event logs] in one storage pattern is going to fail. 'We have our data lake and it's going to be a RAG' - it does not work that way."

**Probability**: Medium (common misconception)

**Impact**: Medium (retrieval failures, performance issues)

**Mitigation**:
- ✅ Match storage to query pattern (principle #3)
- ✅ Key-value: Redis (preferences)
- ✅ Structured: Neo4j (facts)
- ✅ Semantic: Qdrant (episodic)
- ✅ Event logs: TimescaleDB (temporal)

**Owner**: Architect (Week 1: infrastructure design)

#### Risk 8: Memory Doesn't Compound (P2)

**Description**: "Random accumulation does not compound. It just creates noise. Otherwise you have the pile of transcripts you never got to, and you're like 'Well, this is data. We're logging it. It's probably good.' It creates noise."

**Probability**: High (default behavior without structure)

**Impact**: Medium (memory doesn't improve over time, degrades)

**Mitigation**:
- ✅ Structured storage (principle #8)
- ✅ Evergreen context → permanent/
- ✅ Project context → projects/{id}/
- ✅ Session context → sessions/{date}/
- ✅ Compounding effect tracked (metrics: structured facts over time)

**Owner**: Coder (Week 1-12: maintain structure discipline)

---

## Action Items for Our Design

### 1. Add Curation Interface (Week 3)

**What**: UI for human judgment in memory management

**Why**: Principle #6 (compression is curation) - human judgment required

**Features**:
- Tag lifecycle: permanent/temporary/ephemeral
- Mark importance: critical/high/medium/low
- Update facts: edit, version, archive
- Stale data alerts: "This fact is 6 months old, still correct?"
- Verify retrieval: ✅ Verified / ⚠️ Unverified

**Code**:
```python
# src/ui/curation_interface.py
class CurationInterface:
    def tag_lifecycle(self, note_id: str):
        """UI prompt to tag note lifecycle."""
        choice = self.prompt_user([
            "Permanent (never delete)",
            "Temporary (project duration)",
            "Ephemeral (30-day TTL)"
        ])
        self.update_metadata(note_id, lifecycle=choice)

    def detect_stale(self, note_id: str):
        """Alert user to potentially stale facts."""
        note = self.get_note(note_id)
        age_days = (datetime.now() - note["created"]).days

        if age_days > 180 and note["type"] == "fact":
            response = self.prompt_user(
                f"Fact '{note['title']}' is {age_days} days old. Still correct?",
                options=["Yes", "Update", "Archive"]
            )

            if response == "Update":
                self.edit_note(note_id)
            elif response == "Archive":
                self.archive_note(note_id)
```

### 2. Implement Mode-Aware Routing (Week 11)

**What**: Automatic detection of planning vs execution mode

**Why**: Principle #4 (mode-aware context) - breadth vs precision

**Features**:
- Planning mode: Breadth retrieval (top-k=20, diverse results)
- Execution mode: Precision retrieval (top-k=5, high threshold)
- Automatic mode detection from query keywords
- Manual override (user can force mode)

**Code**:
```python
# src/routing/mode_aware_router.py
class ModeAwareRouter:
    def route(self, query: str, mode: str = "auto"):
        if mode == "auto":
            mode = self.detect_mode(query)

        if mode == "planning":
            return self.planning_retrieval(query)
        elif mode == "execution":
            return self.execution_retrieval(query)

    def detect_mode(self, query: str) -> str:
        planning_keywords = ["brainstorm", "explore", "alternatives", "ideas", "research"]
        execution_keywords = ["implement", "deploy", "execute", "build", "create"]

        if any(word in query.lower() for word in planning_keywords):
            return "planning"
        elif any(word in query.lower() for word in execution_keywords):
            return "execution"
        else:
            return "default"

    def planning_retrieval(self, query: str):
        """Breadth: diverse results, lower threshold."""
        return self.qdrant.search(
            query,
            limit=20,
            threshold=0.65,
            diversity_score=0.7
        )

    def execution_retrieval(self, query: str):
        """Precision: focused results, high threshold."""
        return self.qdrant.search(
            query,
            limit=5,
            threshold=0.85,
            diversity_score=0.2
        )
```

### 3. Add Verification Layer (Week 7)

**What**: Two-stage retrieval (recall + verify against ground truth)

**Why**: Principle #7 (retrieval needs verification) - prevent $500k hallucinations

**Features**:
- Stage 1: Recall candidates (semantic/graph)
- Stage 2: Verify against structured data (Neo4j facts)
- Confidence scoring (verified vs unverified)
- Human-in-loop for critical queries (legal, financial, policy)

**Code**:
```python
# src/retrieval/verification_layer.py
class VerificationLayer:
    def retrieve_verified(self, query: str, require_verification: bool = True):
        # Stage 1: Recall
        candidates = self.qdrant.search(query, limit=20)

        if not require_verification:
            return candidates

        # Stage 2: Verify
        verified = []
        for candidate in candidates:
            if self.verify(candidate):
                verified.append({**candidate, "verified": True})
            else:
                self.log_unverified(candidate)

        return verified

    def verify(self, candidate: dict) -> bool:
        """Verify against ground truth in Neo4j."""
        if candidate["type"] == "decision":
            # Query Neo4j for decision node
            cypher = """
            MATCH (d:Decision {title: $title})
            RETURN d
            """
            result = self.neo4j.query(cypher, title=candidate["title"])
            return result is not None

        elif candidate["type"] == "fact":
            # Query structured database
            fact = self.postgres.query(
                "SELECT * FROM facts WHERE id = %s",
                candidate["id"]
            )
            return fact is not None

        return True  # Default: trust semantic search
```

### 4. Design Forgetting Mechanism (Week 9 - Bayesian)

**What**: Structured decay for session data (keep "keys", lose detail)

**Why**: Principle from transcript - "Forgetting is a technology"

**Features**:
- Exponential decay (30-day half-life for sessions)
- Keep metadata "keys" (date, topic, participants, outcome)
- Discard full transcripts after decay threshold
- Reconstruction from keys (summary + metadata)

**Code**:
```python
# src/bayesian/forgetting_mechanism.py
class ForgettingMechanism:
    def apply_decay(self, session_id: str, days_old: int):
        """Apply exponential decay to session memory."""
        decay_factor = math.exp(-days_old / 30)

        if decay_factor < 0.1:
            # Full decay: keys only
            self.compress_to_keys(session_id)
        elif decay_factor < 0.5:
            # Partial decay: summary + keys
            self.compress_to_summary(session_id)
        else:
            # No decay: keep full detail
            pass

    def compress_to_keys(self, session_id: str):
        """Keep only retrieval keys (metadata)."""
        session = self.get_session(session_id)
        keys = {
            "date": session["date"],
            "topic": session["topic"],
            "outcome": session["outcome"],
            "tags": session["tags"],
            "participants": session["participants"]
        }
        # Discard transcript
        self.store_keys_only(session_id, keys)

    def reconstruct_from_keys(self, session_id: str):
        """Attempt reconstruction from metadata keys."""
        keys = self.get_keys(session_id)
        return f"Session on {keys['date']} about {keys['topic']}. Outcome: {keys['outcome']}. [Full transcript archived - retrieve if needed]"
```

### 5. Obsidian Sync (Week 1-2)

**What**: File watcher for auto-indexing Obsidian notes

**Why**: Principle #5 (build portable) - markdown as universal format

**Features**:
- Watch Obsidian vault for file changes
- Parse frontmatter (YAML metadata)
- Auto-index in appropriate store (lifecycle-based)
- Graph visualization sync with Neo4j

**Code**:
```python
# src/obsidian/sync_engine.py
class ObsidianSyncEngine:
    def __init__(self, vault_path: str):
        self.vault_path = vault_path
        self.watcher = Observer()

    def start(self):
        handler = FileSystemEventHandler()
        handler.on_created = self.on_file_created
        handler.on_modified = self.on_file_modified
        handler.on_deleted = self.on_file_deleted

        self.watcher.schedule(handler, self.vault_path, recursive=True)
        self.watcher.start()

    def on_file_created(self, event):
        if event.src_path.endswith(".md"):
            self.index_note(event.src_path)

    def index_note(self, file_path: str):
        """Parse and index Obsidian note."""
        content = self.read_file(file_path)
        metadata = self.parse_frontmatter(content)

        # Route to appropriate store based on lifecycle
        lifecycle = metadata.get("lifecycle", "ephemeral")

        if lifecycle == "permanent":
            self.redis.set(metadata["title"], content)
        elif lifecycle == "temporary":
            self.neo4j.create_node(content, metadata)
        else:  # ephemeral
            embedding = self.embed(content)
            self.qdrant.upsert(embedding, metadata)

        # Sync graph structure to Neo4j
        self.sync_graph_links(file_path, metadata)

    def sync_graph_links(self, file_path: str, metadata: dict):
        """Extract [[wiki-links]] and create Neo4j relationships."""
        content = self.read_file(file_path)
        links = re.findall(r'\[\[([^\]]+)\]\]', content)

        for link in links:
            self.neo4j.create_relationship(
                source=metadata["title"],
                target=link,
                type="LINKS_TO"
            )
```

---

## References

**Source Video**:
- Title: "AI's Memory Wall: Why Compute Grew 60,000x But Memory Only 100x (PLUS My 8 Principles to Fix)"
- URL: https://www.youtube.com/watch?v=JdJE6_OU3YA

**Key Statistics**:
- Compute growth: **60,000x**
- Memory growth: **100x**
- Fine for hallucination: **$500,000** (consultant firm, legal case hallucinations)

**Key Quotes**:
1. "Memory is perhaps the biggest unsolved problem in AI and it is one of the only problems in AI that is getting worse, not better."
2. "A million token context window is not a usable million token context window if it's full of unsorted context. That is worse than a tightly curated 10,000."
3. "Semantic similarity is a proxy for relevance, not a solution."
4. "Forgetting is a technology for us [humans]."
5. "Memory is an architecture, not a feature."
6. "Compression is curation. The judgment in compression is human judgment."
7. "Random accumulation does not compound. It just creates noise."
8. "Your memory layer needs to survive vendor changes, tool changes, model changes."

**Integration with Our Design**:
- All 8 principles integrated into 3-layer hybrid architecture
- All 6 root causes addressed with specific mitigations
- Obsidian power user pattern adopted
- MCP portability strategy implemented
- Active curation UI planned (Week 3)
- Two-stage verification implemented (Week 7)
- Forgetting mechanism designed (Week 9)

---

**Version**: 1.0.0
**Date**: 2025-10-17
**Status**: ✅ Complete - Ready for Pre-Mortem Integration
**Next Step**: Generate pre-mortem risk analysis document
