"""
Quick setup verification for MEM-QWEN-001 POC.
Run this first to verify all dependencies are available.
"""

import sys
from pathlib import Path


def check_gpu():
    """Check GPU availability."""
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"[OK] GPU: {name} ({vram:.1f}GB VRAM)")
            return True
        else:
            print("[WARN] No GPU detected - will run on CPU")
            return True
    except ImportError:
        print("[FAIL] torch not installed")
        return False


def check_cross_encoder():
    """Check cross-encoder availability."""
    try:
        from sentence_transformers import CrossEncoder
        print("[OK] sentence-transformers.CrossEncoder available")
        return True
    except ImportError:
        print("[FAIL] sentence-transformers not installed")
        return False


def check_memory_mcp():
    """Check Memory MCP imports."""
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    try:
        from src.indexing.vector_indexer import VectorIndexer
        from src.indexing.embedding_pipeline import EmbeddingPipeline
        print("[OK] Memory MCP imports available")
        return True
    except ImportError as e:
        print(f"[FAIL] Memory MCP import error: {e}")
        return False


def check_chromadb_data():
    """Check ChromaDB has data."""
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    data_dir = Path.home() / ".claude" / "memory-mcp-data" / "chroma"

    if not data_dir.exists():
        print(f"[FAIL] ChromaDB directory not found: {data_dir}")
        return False

    try:
        from src.indexing.vector_indexer import VectorIndexer
        indexer = VectorIndexer.get_instance(
            persist_directory=str(data_dir),
            collection_name="memory_chunks"
        )
        count = indexer.collection.count()
        if count > 0:
            print(f"[OK] ChromaDB has {count} documents")
            return True
        else:
            print("[WARN] ChromaDB is empty - run some memory_store operations first")
            return False
    except Exception as e:
        print(f"[FAIL] ChromaDB error: {e}")
        return False


def main():
    """Run all checks."""
    print("MEM-QWEN-001 Setup Verification")
    print("=" * 50)

    results = [
        check_gpu(),
        check_cross_encoder(),
        check_memory_mcp(),
        check_chromadb_data(),
    ]

    print("=" * 50)
    if all(results):
        print("All checks passed! Run poc_reranker.py to start benchmark.")
        return 0
    else:
        print("Some checks failed. Fix issues before running POC.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
