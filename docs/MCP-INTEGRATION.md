# Memory MCP Triple System - MCP Server Integration

**Version**: 1.0.0
**Date**: 2025-11-01
**Status**: PRODUCTION READY

---

## Overview

The Memory MCP Triple System provides persistent, mode-aware memory management for AI assistants through the MCP (Model Context Protocol). It automatically adapts context based on query intent and maintains three-layer retention policies.

## Quick Setup

### Claude Code / Claude Desktop Configuration

Add to your MCP configuration (`C:\Users\<username>\AppData\Roaming\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "memory-mcp": {
      "command": "/path/to/memory-mcp-triple-system/venv/bin/python",
      "args": ["-u", "-m", "src.mcp.stdio_server"],
      "cwd": "/path/to/memory-mcp-triple-system",
      "env": {
        "PYTHONPATH": "/path/to/memory-mcp-triple-system",
        "PYTHONIOENCODING": "utf-8",
        "ENVIRONMENT": "development",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Windows Example**:
```json
"memory-mcp": {
  "command": "C:\\Projects\\memory-mcp-triple-system\\venv\\Scripts\\python.exe",
  "args": ["-u", "-m", "src.mcp.stdio_server"],
  "cwd": "C:\\Projects\\memory-mcp-triple-system"
}
```

## Available MCP Tools

### 1. `vector_search`

Semantic search with mode-aware context adaptation.

**Parameters**:
- `query` (required): Search query text
- `limit` (optional): Number of results to return (default: 5)

**Returns**: Array of search results with text, score, file_path, and metadata

**Mode-Aware Behavior**:
- **Execution Mode**: 5 core results, 0 extended, 5K tokens
- **Planning Mode**: 10 core + 5 extended, 10K tokens
- **Brainstorming Mode**: 15 core + 10 extended, 20K tokens

**Example**:
```json
{
  "content": [
    {
      "type": "text",
      "text": "Result 1:\nImplemented authentication with JWT tokens\n\nScore: 0.8542\nFile: docs/auth-implementation.md"
    }
  ],
  "isError": false
}
```

### 2. `memory_store`

Store information with automatic layer assignment and metadata tagging.

**Parameters**:
- `text` (required): Content to store
- `metadata` (optional): Metadata object with key, namespace, layer, category

**Automatic Features**:
- Layer assignment based on content type (short/mid/long-term)
- Semantic chunking (128-512 tokens)
- Vector embedding (384-dimensional)
- HNSW indexing for fast retrieval

**Example with Tagging Protocol**:
```json
{
  "text": "Fixed authentication bug in JWT validation",
  "metadata": {
    "agent": {
      "name": "coder",
      "category": "code-quality",
      "capabilities": ["memory-mcp", "connascence-analyzer"]
    },
    "timestamp": {
      "iso": "2025-11-01T19:30:00.000Z",
      "unix": 1698871800
    },
    "project": "auth-service",
    "intent": {
      "primary": "bugfix",
      "description": "Fixed JWT token validation logic"
    }
  }
}
```

## Tagging Protocol (REQUIRED)

ALL Memory MCP writes MUST include metadata tags for WHO/WHEN/PROJECT/WHY.

### Implementation

Use the tagging protocol from ruv-sparc-three-loop-system:

**File**: [`memory-mcp-tagging-protocol.js`](https://github.com/DNYoussef/ruv-sparc-three-loop-system/blob/main/hooks/12fa/memory-mcp-tagging-protocol.js)

**Basic Usage**:
```javascript
const { taggedMemoryStore } = require('./hooks/12fa/memory-mcp-tagging-protocol.js');

// Auto-tagged memory write
const tagged = taggedMemoryStore('coder', 'Implemented new feature', {
  task_id: 'FEAT-123',
  project: 'auth-service'
});

// Result includes:
// - agent: { name, category, capabilities }
// - timestamp: { iso, unix, readable }
// - project: 'auth-service'
// - intent: { primary: 'implementation', ... }
```

### Required Metadata Fields

1. **WHO**: Agent information
   - `agent.name`: Agent identifier (e.g., "coder", "planner")
   - `agent.category`: "code-quality" | "planning" | "general"
   - `agent.capabilities`: Array of accessible MCP servers

2. **WHEN**: Timestamp information
   - `timestamp.iso`: ISO 8601 format
   - `timestamp.unix`: Unix timestamp
   - `timestamp.readable`: Human-readable format

3. **PROJECT**: Project identification
   - `project`: Project name (e.g., "auth-service", "connascence-analyzer")
   - Auto-detected from working directory if not provided

4. **WHY**: Intent analysis
   - `intent.primary`: One of 8 categories (implementation, bugfix, refactor, testing, documentation, analysis, planning, research)
   - `intent.description`: Description of intent
   - `intent.task_id`: Optional task/ticket identifier

### Intent Categories

The protocol includes automatic intent detection:

- `implementation`: Creating new features
- `bugfix`: Fixing errors or issues
- `refactor`: Improving code structure
- `testing`: Writing or running tests
- `documentation`: Creating or updating docs
- `analysis`: Analyzing code or patterns
- `planning`: Designing or planning work
- `research`: Investigating or exploring

## Triple-Layer Architecture

### Short-Term Memory (24h retention)
- Recent queries and responses
- Temporary context within session
- High-frequency access

### Mid-Term Memory (7d retention)
- Project-specific context
- Recent decisions and patterns
- Moderate access frequency

### Long-Term Memory (30d+ retention)
- System capabilities and documentation
- Established patterns and learnings
- Low-frequency but high-value access

## Mode Detection

The system automatically detects interaction mode using 29 regex patterns:

### Execution Mode (11 patterns)
- Direct commands: "run", "execute", "test", "build"
- Specific requests with clear outputs
- Token budget: 5K
- Results: 5 core + 0 extended

### Planning Mode (9 patterns)
- Design keywords: "design", "plan", "architect"
- Multi-step workflows
- Token budget: 10K
- Results: 10 core + 5 extended

### Brainstorming Mode (9 patterns)
- Exploratory: "explore", "brainstorm", "possibilities"
- Open-ended research
- Token budget: 20K
- Results: 15 core + 10 extended

**Mode Detection Accuracy**: 85%+

## Integration with Connascence Analyzer

Memory MCP works seamlessly with the [Connascence Safety Analyzer](https://github.com/DNYoussef/connascence-safety-analyzer) for code quality tracking:

**Workflow Example**:
```javascript
[Code Quality Agent]:
  // 1. Analyze code with Connascence
  const violations = Connascence.analyze_file("src/auth.js", "full")

  // 2. Store violations in Memory MCP with tagging
  const tagged = taggedMemoryStore('code-analyzer', JSON.stringify(violations), {
    file: 'src/auth.js',
    intent: 'analysis',
    project: 'auth-service'
  })
  MemoryMCP.memory_store(tagged.text, tagged.metadata)

  // 3. Search prior violations for patterns
  const priorViolations = MemoryMCP.vector_search("parameter bomb violations", 10)

  // 4. Store fix in memory
  const fixTagged = taggedMemoryStore('coder', 'Refactored to config object pattern', {
    file: 'src/auth.js',
    intent: 'refactor',
    project: 'auth-service'
  })
  MemoryMCP.memory_store(fixTagged.text, fixTagged.metadata)
```

## Agent Access

### Global Access (ALL 37 Agents)

ALL agents in the ruv-SPARC system have access to Memory MCP:

- 14 code quality agents: coder, reviewer, tester, etc.
- 23 planning agents: planner, researcher, architect, etc.

**Why Global?** Memory serves all agents for cross-session context persistence.

### Tagging Enforcement

While all agents can access Memory MCP, the tagging protocol ensures proper attribution and intent tracking for every write operation.

## Testing

### Run Test Suite

```bash
cd /path/to/memory-mcp-triple-system
export PYTHONIOENCODING=utf-8

# Mode detector tests
pytest tests/unit/test_mode_detector.py -v

# Mode profile tests
pytest tests/unit/test_mode_profile.py -v
```

Expected results:
- Mode Detector: 14/14 tests passed
- Mode Profiles: 13/13 tests passed
- Total: 27/27 tests (100% pass rate)

### Mode Detection Test

```bash
python scripts/test-mode-detection.py
```

Expected output:
```
Mode: execution, Confidence: 0.80
Mode: planning, Confidence: 0.85
Mode: brainstorming, Confidence: 0.90
```

## Related Systems

- **Connascence Safety Analyzer**: [https://github.com/DNYoussef/connascence-safety-analyzer](https://github.com/DNYoussef/connascence-safety-analyzer)
  - 7+ code quality violation types
  - NASA compliance checking
  - 0.018s analysis performance

- **ruv-SPARC Three-Loop System**: [https://github.com/DNYoussef/ruv-sparc-three-loop-system](https://github.com/DNYoussef/ruv-sparc-three-loop-system)
  - 86+ specialized agents
  - Agent access control matrix
  - Tagging protocol implementation

## Troubleshooting

### Unicode Encoding Errors

Ensure environment variable is set:

```json
"env": {
  "PYTHONIOENCODING": "utf-8"
}
```

Also add to `.env` file:
```
PYTHONIOENCODING=utf-8
```

### spacy/pydantic Version Conflicts

These are non-critical warnings. Core functionality (mode detection, vector search, memory storage) works correctly. If needed:

```bash
pip install --upgrade pydantic spacy
```

### ChromaDB Not Found

Ensure ChromaDB is installed:

```bash
pip install chromadb
```

### No Results from Search

1. Verify data has been indexed
2. Check vector database location (`.chroma/` directory)
3. Try broader search queries
4. Increase limit parameter

## Performance Characteristics

- **Mode Detection**: 85%+ accuracy with 29 patterns
- **Vector Search**: Sub-second retrieval with HNSW indexing
- **Embedding Generation**: 384-dimensional vectors (all-MiniLM-L6-v2)
- **Chunking**: Semantic chunking (128-512 tokens)
- **Test Coverage**: 27/27 tests (100% pass rate)

## Support

- **GitHub Issues**: [https://github.com/DNYoussef/memory-mcp-triple-system/issues](https://github.com/DNYoussef/memory-mcp-triple-system/issues)
- **Documentation**: [https://github.com/DNYoussef/memory-mcp-triple-system/blob/main/README.md](https://github.com/DNYoussef/memory-mcp-triple-system/blob/main/README.md)

---

**Version**: 1.0.0
**Updated**: 2025-11-01
**Status**: PRODUCTION READY
