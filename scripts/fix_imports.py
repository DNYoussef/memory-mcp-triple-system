"""
Fix import errors for memory-mcp-triple-system.
Tests all critical imports and provides diagnostics.
"""

import os
import sys
import warnings

# Set environment variables before any imports
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['HF_HOME'] = r'C:\Users\17175\.cache\huggingface'

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Suppress the specific FutureWarning about TRANSFORMERS_CACHE
warnings.filterwarnings('ignore', message='.*TRANSFORMERS_CACHE.*', category=FutureWarning)

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_imports():
    """Test all critical imports."""
    print("Testing imports for memory-mcp-triple-system...\n")

    results = []

    # Test 1: Basic dependencies
    try:
        import numpy as np
        results.append(("✓", "numpy", np.__version__))
    except Exception as e:
        results.append(("✗", "numpy", str(e)))

    # Test 2: Transformers
    try:
        import transformers
        results.append(("✓", "transformers", transformers.__version__))
    except Exception as e:
        results.append(("✗", "transformers", str(e)))

    # Test 3: Sentence Transformers
    try:
        import sentence_transformers
        results.append(("✓", "sentence_transformers", sentence_transformers.__version__))
    except Exception as e:
        results.append(("✗", "sentence_transformers", str(e)))

    # Test 4: Embedding Pipeline
    try:
        from src.indexing.embedding_pipeline import EmbeddingPipeline
        results.append(("✓", "EmbeddingPipeline", "OK"))
    except Exception as e:
        results.append(("✗", "EmbeddingPipeline", str(e)))

    # Test 5: Stdio Server
    try:
        from src.mcp.stdio_server import main
        results.append(("✓", "stdio_server", "OK"))
    except Exception as e:
        results.append(("✗", "stdio_server", str(e)))

    # Test 6: ChromaDB
    try:
        import chromadb
        results.append(("✓", "chromadb", chromadb.__version__))
    except Exception as e:
        results.append(("✗", "chromadb", str(e)))

    # Test 7: Environment encoding
    try:
        encoding = sys.getdefaultencoding()
        results.append(("✓", "Python encoding", encoding))
    except Exception as e:
        results.append(("✗", "Python encoding", str(e)))

    # Print results
    print("=" * 60)
    print("IMPORT TEST RESULTS")
    print("=" * 60)
    for status, name, version in results:
        print(f"{status} {name:30s} {version}")
    print("=" * 60)

    # Check for failures
    failures = [r for r in results if r[0] == "✗"]
    if failures:
        print(f"\n❌ {len(failures)} test(s) failed!")
        return False
    else:
        print("\n✅ All imports successful!")
        return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
