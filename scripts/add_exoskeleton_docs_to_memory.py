"""
Add the 12 core AI Exoskeleton documents to Memory MCP.
This script indexes all 12 core documents plus supporting files into the memory system.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Set up paths
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ['MEMORY_MCP_DATA_DIR'] = str(Path.home() / '.claude' / 'memory-mcp-data')

import yaml

# The 12 core documents as defined in README.md
CORE_DOCS = [
    ("ORGAN-MAP", "2026-EXOSKELETON-ORGAN-MAP.md", "Biological metaphor - 18 projects as organs"),
    ("COMPONENT-MAPPING", "2026-COMPONENT-MAPPING-ADDENDUM.md", "Library inventory - 84 components"),
    ("WIRING-BLUEPRINT", "2026-EXOSKELETON-WIRING-BLUEPRINT.md", "Technical connections - nerves, muscles, immune"),
    ("TODO", "2026-AI-EXOSKELETON-TODO.md", "Master action plan - roadmap, 5-loop system"),
    ("MECE-GAP-ANALYSIS", "MECE-GAP-ANALYSIS.md", "Migration audit - gap tracking"),
    ("IMPLEMENTATION-PLAN", "2026-IMPLEMENTATION-PLAN.md", "Execution roadmap - 275h, 9 weeks, 4 phases"),
    ("SKILL-TASK-MAPPING", "SKILL-TASK-MAPPING.md", "Skill assignments - 252 skills to tasks"),
    ("GAP-RECONNAISSANCE", "GAP-RECONNAISSANCE-SimpleLLM-Buzz.md", "External project analysis - 4 new components"),
    ("METABOLIC-MAP", "2026-METABOLIC-MAP.md", "Living system flow - nutrient flow, 4 missing organs"),
    ("MCP-TOOL-SEARCH", "MCP-TOOL-SEARCH-OPTIMIZATION.md", "Context optimization - 85% token reduction"),
    ("GENOME-ECOSYSTEM", "2026-GENOME-ECOSYSTEM-SCALING.md", "Hierarchical scaling - 12-level biological stack"),
    ("DUAL-MOO-CONTROL-SPEC", "2026-DUAL-MOO-CONTROL-SPEC.md", "Optimization control - 8 objectives, 5D/14D vars"),
]

# Additional supporting files
SUPPORTING_FILES = [
    ("README", "README.md", "Master index - document suite overview"),
    ("STATUS-JSON", "2026-EXOSKELETON-STATUS.json", "Canonical status - source of truth for project status"),
    ("STATUS-MD", "2026-EXOSKELETON-STATUS.md", "Human-readable status report"),
    ("SYSTEM-MAP", "2026-EXOSKELETON-SYSTEM-MAP.md", "Bird's-eye system diagram"),
]

EXOSKELETON_DIR = Path(r"D:\2026-AI-EXOSKELETON")


def load_config():
    """Load configuration from memory-mcp.yaml"""
    config_path = Path(__file__).parent.parent / 'config' / 'memory-mcp.yaml'
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {
        'storage': {
            'data_dir': os.environ.get('MEMORY_MCP_DATA_DIR', './data'),
            'vector_db': {'type': 'chromadb', 'persist_directory': './chroma_data'}
        },
        'embeddings': {
            'model': 'sentence-transformers/all-MiniLM-L6-v2'
        }
    }


def chunk_document(text: str, max_chunk_size: int = 1000, overlap: int = 100) -> list:
    """Split document into overlapping chunks for better retrieval."""
    chunks = []
    lines = text.split('\n')
    current_chunk = []
    current_size = 0

    for line in lines:
        line_size = len(line)
        if current_size + line_size > max_chunk_size and current_chunk:
            chunks.append('\n'.join(current_chunk))
            # Keep last few lines for overlap
            overlap_lines = []
            overlap_size = 0
            for prev_line in reversed(current_chunk):
                if overlap_size + len(prev_line) < overlap:
                    overlap_lines.insert(0, prev_line)
                    overlap_size += len(prev_line)
                else:
                    break
            current_chunk = overlap_lines
            current_size = overlap_size

        current_chunk.append(line)
        current_size += line_size

    if current_chunk:
        chunks.append('\n'.join(current_chunk))

    return chunks


def main():
    print("=" * 60)
    print("Adding AI Exoskeleton 12 Core Docs to Memory MCP")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Source: {EXOSKELETON_DIR}")
    print("=" * 60)

    # Load config and initialize tools
    print("\n[INIT] Loading configuration...")
    config = load_config()

    print("[INIT] Initializing NexusSearchTool...")
    from src.mcp.stdio_server import NexusSearchTool
    tool = NexusSearchTool(config)
    print("[INIT] Initialization complete\n")

    # Track statistics
    total_chunks = 0
    total_docs = 0

    # Process core documents
    print("-" * 40)
    print("Processing 12 Core Documents...")
    print("-" * 40)

    for doc_name, filename, description in CORE_DOCS:
        filepath = EXOSKELETON_DIR / filename
        if not filepath.exists():
            print(f"[SKIP] {doc_name}: File not found at {filepath}")
            continue

        print(f"[PROC] {doc_name}: {filename}")
        text = filepath.read_text(encoding='utf-8', errors='ignore')

        # Chunk the document
        chunks_text = chunk_document(text)
        chunks = []

        for i, chunk_text in enumerate(chunks_text):
            chunks.append({
                'text': chunk_text,
                'file_path': str(filepath),
                'chunk_index': i,
                'metadata': {
                    'who': 'exoskeleton-indexer:1.0.0',
                    'when': datetime.now().isoformat(),
                    'project': 'ai-exoskeleton',
                    'why': 'documentation-indexing',
                    'doc_name': doc_name,
                    'doc_type': 'core_doc',
                    'description': description,
                    'source': '2026-AI-EXOSKELETON',
                    'total_chunks': len(chunks_text)
                }
            })

        if chunks:
            # Generate embeddings and index
            texts = [c['text'] for c in chunks]
            embeddings = tool.vector_search_tool.embedder.encode(texts)
            tool.vector_search_tool.indexer.index_chunks(chunks, embeddings.tolist())
            total_chunks += len(chunks)
            total_docs += 1
            print(f"       Indexed {len(chunks)} chunks")

    # Process supporting files
    print("\n" + "-" * 40)
    print("Processing Supporting Files...")
    print("-" * 40)

    for doc_name, filename, description in SUPPORTING_FILES:
        filepath = EXOSKELETON_DIR / filename
        if not filepath.exists():
            print(f"[SKIP] {doc_name}: File not found at {filepath}")
            continue

        print(f"[PROC] {doc_name}: {filename}")

        # Handle JSON files differently
        if filename.endswith('.json'):
            text = filepath.read_text(encoding='utf-8', errors='ignore')
            chunks_text = [text[:2000]]  # Just first 2000 chars for JSON
        else:
            text = filepath.read_text(encoding='utf-8', errors='ignore')
            chunks_text = chunk_document(text)

        chunks = []
        for i, chunk_text in enumerate(chunks_text):
            chunks.append({
                'text': chunk_text,
                'file_path': str(filepath),
                'chunk_index': i,
                'metadata': {
                    'who': 'exoskeleton-indexer:1.0.0',
                    'when': datetime.now().isoformat(),
                    'project': 'ai-exoskeleton',
                    'why': 'documentation-indexing',
                    'doc_name': doc_name,
                    'doc_type': 'supporting',
                    'description': description,
                    'source': '2026-AI-EXOSKELETON',
                    'total_chunks': len(chunks_text)
                }
            })

        if chunks:
            texts = [c['text'] for c in chunks]
            embeddings = tool.vector_search_tool.embedder.encode(texts)
            tool.vector_search_tool.indexer.index_chunks(chunks, embeddings.tolist())
            total_chunks += len(chunks)
            total_docs += 1
            print(f"       Indexed {len(chunks)} chunks")

    # Summary
    print("\n" + "=" * 60)
    print("INDEXING COMPLETE")
    print("=" * 60)
    print(f"Documents indexed: {total_docs}")
    print(f"Total chunks: {total_chunks}")
    print(f"Memory MCP data dir: {os.environ.get('MEMORY_MCP_DATA_DIR')}")
    print("=" * 60)

    # Verify by searching
    print("\n[VERIFY] Testing retrieval...")
    results = tool.vector_search_tool.execute("AI exoskeleton organ map 18 projects", limit=3)
    print(f"[VERIFY] Search returned {len(results)} results")
    for r in results[:3]:
        print(f"         - {r.get('metadata', {}).get('doc_name', 'unknown')}: score={r.get('score', 0):.3f}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
