"""
Ingest System Documentation into Memory MCP

This script ingests all documentation about the Memory MCP Triple System
into the system itself, enabling AI models to retrieve information about
how the system works, how to use it, and how it's architected.

This creates a "self-aware" memory system that can answer questions about itself.
"""
import sys
import io
from pathlib import Path
from typing import List, Dict, Any

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.chunking.semantic_chunker import SemanticChunker
from src.indexing.embedding_pipeline import EmbeddingPipeline
from src.indexing.vector_indexer import VectorIndexer


def print_header(title: str):
    """Print section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def collect_documentation_files() -> List[Path]:
    """
    Collect all documentation files to ingest.

    Returns:
        List of Path objects for markdown documentation files
    """
    base_dir = Path(__file__).parent.parent

    # Documentation sources
    doc_sources = [
        base_dir / "docs" / "INGESTION-AND-RETRIEVAL-EXPLAINED.md",
        base_dir / "docs" / "MCP-DEPLOYMENT-GUIDE.md",
        base_dir / "docs" / "weeks" / "WEEK-13-COMPLETE-SUMMARY.md",
        base_dir / "docs" / "weeks" / "WEEK-13-IMPLEMENTATION-PLAN.md",
        base_dir / "README.md" if (base_dir / "README.md").exists() else None,
        base_dir / "CLAUDE.md" if (base_dir / "CLAUDE.md").exists() else None,
    ]

    # Filter out None and non-existent files
    existing_files = [f for f in doc_sources if f and f.exists()]

    print(f"Found {len(existing_files)} documentation files:")
    for file in existing_files:
        print(f"  • {file.relative_to(base_dir)}")

    return existing_files


def ingest_file(
    file_path: Path,
    chunker: SemanticChunker,
    embedder: EmbeddingPipeline,
    indexer: VectorIndexer
) -> int:
    """
    Ingest a single documentation file.

    Args:
        file_path: Path to markdown file
        chunker: SemanticChunker instance
        embedder: EmbeddingPipeline instance
        indexer: VectorIndexer instance

    Returns:
        Number of chunks created
    """
    print(f"\n  Processing: {file_path.name}")

    # Read file content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract title from first # header or filename
    title = file_path.stem.replace('-', ' ').title()
    if content.startswith('# '):
        first_line = content.split('\n')[0]
        title = first_line.replace('# ', '').strip()

    # Chunk the document
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

    chunks = []
    for idx, para in enumerate(paragraphs):
        # Skip very short paragraphs and code blocks
        if len(para) < 50:
            continue

        # Skip lines that are just headers (single line starting with #)
        if para.startswith('#') and '\n' not in para:
            continue

        chunks.append({
            'text': para,
            'file_path': str(file_path),
            'chunk_index': idx,
            'metadata': {
                'title': title,
                'filename': file_path.name,
                'category': 'system_documentation',
                'source': 'memory_mcp_docs',
                'ingestion_type': 'self_reference'
            }
        })

    if not chunks:
        print(f"    WARNING: No chunks created from {file_path.name}")
        return 0

    print(f"    Chunks: {len(chunks)}")

    # Generate embeddings
    chunk_texts = [c['text'] for c in chunks]
    embeddings = embedder.encode(chunk_texts)
    print(f"    Embeddings: {len(embeddings)} generated")

    # Index in ChromaDB
    indexer.index_chunks(chunks, embeddings.tolist())
    print(f"    ✓ Indexed {len(chunks)} chunks")

    return len(chunks)


def test_self_retrieval(
    embedder: EmbeddingPipeline,
    indexer: VectorIndexer
):
    """
    Test that the system can retrieve information about itself.

    Args:
        embedder: EmbeddingPipeline instance
        indexer: VectorIndexer instance
    """
    print_header("Testing Self-Referential Retrieval")

    test_queries = [
        "How does the ingestion pipeline work?",
        "What is mode-aware context?",
        "How do I deploy the MCP server?",
        "What are the three retrieval strategies?",
        "How does chunking work in this system?",
    ]

    for query in test_queries:
        print(f"\nQuery: \"{query}\"")

        # Generate query embedding
        query_embedding = embedder.encode_single(query)

        # Search
        results = indexer.search_similar(
            query_embedding=query_embedding.tolist(),
            top_k=3
        )

        if results:
            print(f"  Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                similarity = 1.0 - result['distance']
                print(f"\n  [{i}] Similarity: {similarity:.3f}")
                print(f"      Source: {result['metadata'].get('title', 'Unknown')}")
                print(f"      File: {result['metadata'].get('filename', 'Unknown')}")
                print(f"      Preview: {result['document'][:120]}...")
        else:
            print("  ⚠ No results found")

    print("\n✓ Self-retrieval test complete")


def main():
    """Main ingestion workflow."""

    print_header("Memory MCP Documentation Ingestion")
    print("\nIngesting system documentation into the memory system...")
    print("This enables AI models to retrieve information about the system itself.")

    # Step 1: Initialize components
    print_header("Step 1: Initialize Components")

    print("Initializing chunker...")
    chunker = SemanticChunker(
        min_chunk_size=128,
        max_chunk_size=512,
        overlap=50
    )
    print("✓ SemanticChunker ready")

    print("\nInitializing embedder...")
    print("  NOTE: This requires downloading the model if not cached.")
    print("  Model: sentence-transformers/all-MiniLM-L6-v2 (~90MB)")
    print("  This may take a minute on first run...")

    try:
        embedder = EmbeddingPipeline(model_name='all-MiniLM-L6-v2')
        print(f"✓ EmbeddingPipeline ready (dim={embedder.embedding_dim})")
    except Exception as e:
        print(f"\n❌ ERROR: Could not load embedding model")
        print(f"   {e}")
        print("\n   Make sure you have internet connection for first-time model download.")
        print("   Or download the model manually and update the path in config.")
        sys.exit(1)

    print("\nInitializing vector indexer...")
    indexer = VectorIndexer(
        persist_directory='./chroma_data',
        collection_name='memory_embeddings'
    )
    indexer.create_collection(vector_size=384)
    print("✓ VectorIndexer ready")

    # Step 2: Collect documentation files
    print_header("Step 2: Collect Documentation Files")

    doc_files = collect_documentation_files()

    if not doc_files:
        print("\n⚠ WARNING: No documentation files found!")
        print("   Make sure you run this script from the project root directory.")
        sys.exit(1)

    # Step 3: Ingest each file
    print_header("Step 3: Ingest Documentation")

    total_chunks = 0
    successful_files = 0

    for file_path in doc_files:
        try:
            chunks_created = ingest_file(file_path, chunker, embedder, indexer)
            total_chunks += chunks_created
            if chunks_created > 0:
                successful_files += 1
        except Exception as e:
            print(f"    ❌ ERROR ingesting {file_path.name}: {e}")
            import traceback
            traceback.print_exc()

    # Step 4: Summary
    print_header("Ingestion Summary")

    print(f"\nFiles processed: {successful_files}/{len(doc_files)}")
    print(f"Total chunks created: {total_chunks}")
    print(f"Storage location: ./chroma_data/")
    print(f"Collection: memory_embeddings")

    if total_chunks == 0:
        print("\n⚠ WARNING: No chunks were created!")
        print("   Check that documentation files contain substantial content.")
        sys.exit(1)

    print("\n✅ Documentation ingestion complete!")

    # Step 5: Test retrieval
    if total_chunks > 0:
        print("\n" + "─" * 70)
        response = input("\nTest self-referential retrieval? (y/n): ")
        if response.lower() == 'y':
            test_self_retrieval(embedder, indexer)

    # Final instructions
    print_header("Next Steps")
    print("\nThe system documentation is now ingested and searchable!")
    print("\nAI models can now retrieve information about:")
    print("  • How the ingestion pipeline works")
    print("  • How to use the MCP server")
    print("  • What mode-aware context is")
    print("  • How to deploy the system")
    print("  • System architecture and components")
    print("\nExample query:")
    print('  POST /tools/vector_search')
    print('  {"query": "How does mode-aware context work?", "limit": 5}')
    print("\nOr in Claude Desktop:")
    print('  "Search my memory for information about mode detection"')


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Ingestion cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
