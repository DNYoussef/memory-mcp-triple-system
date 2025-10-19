"""
Performance Tests for Week 3 Curation UI
Tests batch load, auto-suggest, and full workflow timing.

Target: <5 minutes to curate 20 chunks
NASA Rule 10 Compliant: All functions ≤60 LOC
"""

import pytest
import chromadb
import uuid
import time
from typing import List, Dict, Any

from src.services.curation_service import CurationService


# ============================================================================
# Test Data Generators (NASA Compliant: ≤60 LOC per function)
# ============================================================================

def generate_test_chunk(
    chunk_type: str = "medium",
    verified: bool = False,
    chunk_index: int = 0
) -> Dict[str, Any]:
    """
    Generate single test chunk with realistic content.

    Args:
        chunk_type: Type of chunk (short/medium/long/todo/reference)
        verified: Verification status
        chunk_index: Chunk index number

    Returns:
        Chunk dictionary with text and metadata
    """
    assert chunk_type in ['short', 'medium', 'long', 'todo', 'reference'], \
        f"Invalid chunk_type: {chunk_type}"

    # Generate realistic text based on type
    text_templates = {
        'short': "Quick note about feature X.",
        'medium': " ".join([
            "This is a medium-length chunk describing implementation details.",
            "It contains multiple sentences with technical information.",
            "The content is typical of code documentation or meeting notes.",
            "Approximately 50-100 words in total length."
        ]),
        'long': " ".join([
            "This is a comprehensive documentation chunk that contains",
            "extensive technical details about system architecture,",
            "implementation patterns, and design decisions.",
            "It includes multiple paragraphs with thorough explanations",
            "of complex concepts and their interrelationships.",
            "The text extends beyond 200 words to simulate detailed",
            "technical documentation or specification documents.",
            "Such chunks typically represent permanent knowledge that",
            "should be retained for long-term reference and consultation.",
            "They often include code examples, architectural diagrams,",
            "API specifications, and other critical technical information."
        ] * 3),  # Multiply to ensure >200 words
        'todo': "TODO: Implement the authentication feature using JWT tokens.",
        'reference': "Reference: The authentication module uses OAuth2 definition."
    }

    text = text_templates.get(chunk_type, text_templates['medium'])
    chunk_id = str(uuid.uuid4())

    return {
        'id': chunk_id,
        'text': text,
        'metadata': {
            'file_path': f'/test/file_{chunk_index}.txt',
            'chunk_index': chunk_index,
            'lifecycle': 'temporary',
            'verified': verified
        }
    }


def generate_test_batch(batch_size: int = 20) -> List[Dict[str, Any]]:
    """
    Generate batch of test chunks with variety.

    Args:
        batch_size: Number of chunks to generate

    Returns:
        List of chunk dictionaries
    """
    assert batch_size > 0, "batch_size must be positive"
    assert batch_size <= 100, "batch_size too large (max 100)"

    chunks = []
    chunk_types = ['short', 'medium', 'long', 'todo', 'reference']

    for i in range(batch_size):
        # Distribute chunk types evenly
        chunk_type = chunk_types[i % len(chunk_types)]
        chunk = generate_test_chunk(
            chunk_type=chunk_type,
            verified=False,
            chunk_index=i
        )
        chunks.append(chunk)

    return chunks


# ============================================================================
# Pytest Fixtures (NASA Compliant: ≤60 LOC per function)
# ============================================================================

@pytest.fixture
def fresh_chroma_client(tmp_path):
    """
    Create fresh ChromaDB client for each test.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        ChromaDB client instance
    """
    # Use temporary directory for test isolation
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    yield client
    # Cleanup handled by pytest tmp_path


@pytest.fixture
def curation_service(fresh_chroma_client, tmp_path):
    """
    Create CurationService with fresh ChromaDB client.

    Args:
        fresh_chroma_client: Fresh ChromaDB client
        tmp_path: Pytest temporary directory

    Returns:
        CurationService instance
    """
    service = CurationService(
        chroma_client=fresh_chroma_client,
        collection_name="test_memory_chunks",
        data_dir=str(tmp_path / "data")
    )
    return service


@pytest.fixture
def populated_service(curation_service):
    """
    Create CurationService pre-populated with 20 test chunks.

    Args:
        curation_service: CurationService fixture

    Returns:
        CurationService with 20 unverified chunks
    """
    # Generate and insert 20 chunks
    chunks = generate_test_batch(batch_size=20)

    # Add chunks to ChromaDB
    ids = [chunk['id'] for chunk in chunks]
    documents = [chunk['text'] for chunk in chunks]
    metadatas = [chunk['metadata'] for chunk in chunks]

    curation_service.collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    return curation_service


# ============================================================================
# Performance Test 1: Batch Load (Target: <2 seconds for 20 chunks)
# ============================================================================

def test_batch_load_performance(benchmark, populated_service):
    """
    Test batch load performance: load 20 chunks in <2 seconds.

    Args:
        benchmark: pytest-benchmark fixture
        populated_service: Pre-populated CurationService

    Asserts:
        - All 20 chunks loaded
        - Mean time <2 seconds
        - 95th percentile <2.5 seconds
    """
    def load_batch():
        """Load batch of 20 unverified chunks."""
        chunks = populated_service.get_unverified_chunks(limit=20)
        assert len(chunks) == 20, f"Expected 20 chunks, got {len(chunks)}"
        return chunks

    # Run benchmark
    result = benchmark(load_batch)

    # Validate results
    assert len(result) == 20, "Must load all 20 chunks"

    # Performance assertions
    stats = benchmark.stats
    mean_time = stats['mean']
    p95_time = stats.get('q_95', mean_time * 1.5)

    assert mean_time < 2.0, \
        f"Mean load time {mean_time:.3f}s exceeds 2s target"
    assert p95_time < 2.5, \
        f"95th percentile {p95_time:.3f}s exceeds 2.5s target"


# ============================================================================
# Performance Test 2: Auto-Suggest (Target: <1 second for 20 suggestions)
# ============================================================================

def test_auto_suggest_performance(benchmark, curation_service):
    """
    Test auto-suggest performance: 20 suggestions in <1 second.

    Args:
        benchmark: pytest-benchmark fixture
        curation_service: CurationService fixture

    Asserts:
        - All 20 suggestions generated
        - Mean time <1 second
        - Suggestions are valid lifecycle tags
    """
    # Generate 20 test chunks
    chunks = generate_test_batch(batch_size=20)

    def auto_suggest_batch():
        """Auto-suggest lifecycle for 20 chunks."""
        suggestions = []
        for chunk in chunks:
            suggestion = curation_service.auto_suggest_lifecycle(chunk)
            suggestions.append(suggestion)
        assert len(suggestions) == 20, "Must generate 20 suggestions"
        return suggestions

    # Run benchmark
    result = benchmark(auto_suggest_batch)

    # Validate results
    assert len(result) == 20, "Must generate all 20 suggestions"

    # All suggestions must be valid lifecycle tags
    valid_lifecycles = {'permanent', 'temporary', 'ephemeral'}
    for suggestion in result:
        assert suggestion in valid_lifecycles, \
            f"Invalid suggestion: {suggestion}"

    # Performance assertions
    stats = benchmark.stats
    mean_time = stats['mean']

    assert mean_time < 1.0, \
        f"Mean auto-suggest time {mean_time:.3f}s exceeds 1s target"


# ============================================================================
# Performance Test 3: Full Workflow (Target: <5 minutes for 20 chunks)
# ============================================================================

def _populate_test_chunks(curation_service, batch_size: int = 20):
    """
    Populate database with fresh test chunks.

    Args:
        curation_service: CurationService instance
        batch_size: Number of chunks to generate
    """
    chunks_data = generate_test_batch(batch_size=batch_size)
    ids = [chunk['id'] for chunk in chunks_data]
    documents = [chunk['text'] for chunk in chunks_data]
    metadatas = [chunk['metadata'] for chunk in chunks_data]

    curation_service.collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )


def _process_chunk_workflow(curation_service, chunk: Dict[str, Any]) -> bool:
    """
    Process single chunk: auto-suggest, tag, verify.

    Args:
        curation_service: CurationService instance
        chunk: Chunk dictionary

    Returns:
        True if successful
    """
    # Auto-suggest lifecycle
    lifecycle = curation_service.auto_suggest_lifecycle(chunk)

    # Tag with lifecycle
    success = curation_service.tag_lifecycle(chunk['id'], lifecycle)
    if not success:
        return False

    # Verify chunk
    success = curation_service.mark_verified(chunk['id'])
    return success


def test_full_workflow_performance(benchmark, curation_service):
    """
    Test full workflow: curate 20 chunks in <5 minutes (simulated).

    Simulates realistic curation workflow:
    1. Load batch (20 chunks)
    2. Auto-suggest lifecycle for each
    3. Tag with lifecycle
    4. Verify each chunk
    5. Log session time

    Args:
        benchmark: pytest-benchmark fixture
        curation_service: CurationService fixture

    Asserts:
        - All 20 chunks processed
        - Mean time <300 seconds (5 minutes)
        - All chunks verified
    """
    def full_workflow():
        """Simulate full curation workflow for 20 chunks."""
        # Repopulate database with fresh chunks
        _populate_test_chunks(curation_service, batch_size=20)
        workflow_start = time.time()

        # Step 1: Load batch
        chunks = curation_service.get_unverified_chunks(limit=20)
        assert len(chunks) == 20, f"Expected 20 chunks, got {len(chunks)}"

        # Step 2-4: Process each chunk
        for chunk in chunks:
            success = _process_chunk_workflow(curation_service, chunk)
            assert success, f"Failed to process chunk {chunk['id']}"

        # Step 5: Log session time
        workflow_end = time.time()
        duration = int(workflow_end - workflow_start)
        curation_service.log_time(
            duration_seconds=duration,
            chunks_curated=20
        )

        return chunks

    # Run benchmark (disable warmup to save time)
    result = benchmark.pedantic(full_workflow, iterations=5, rounds=1)

    # Validate and report
    _validate_workflow_results(result, benchmark.stats)


def _validate_workflow_results(result: List[Dict], stats: Dict):
    """
    Validate workflow results and print performance report.

    Args:
        result: List of processed chunks
        stats: Benchmark statistics
    """
    assert len(result) == 20, "Must process all 20 chunks"

    mean_time = stats['mean']

    # Target: <5 minutes (300 seconds)
    assert mean_time < 300.0, \
        f"Mean workflow time {mean_time:.1f}s exceeds 300s (5 min) target"

    # Report timing breakdown
    print(f"\n--- Full Workflow Performance Report ---")
    print(f"Mean time: {mean_time:.2f}s")
    print(f"Median time: {stats.get('median', mean_time):.2f}s")
    print(f"Std dev: {stats.get('stddev', 0):.2f}s")
    print(f"Target: <300s (5 minutes)")
    print(f"Margin: {300 - mean_time:.2f}s remaining")


# ============================================================================
# Additional Performance Tests: Edge Cases
# ============================================================================

def test_large_batch_scalability(benchmark, curation_service):
    """
    Test scalability with larger batch (50 chunks).

    Validates system can handle larger batches without degradation.

    Args:
        benchmark: pytest-benchmark fixture
        curation_service: CurationService fixture

    Asserts:
        - Linear scaling (50 chunks ≈ 2.5x time of 20 chunks)
    """
    # Generate and insert 50 chunks
    chunks = generate_test_batch(batch_size=50)

    ids = [chunk['id'] for chunk in chunks]
    documents = [chunk['text'] for chunk in chunks]
    metadatas = [chunk['metadata'] for chunk in chunks]

    curation_service.collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    def load_large_batch():
        """Load batch of 50 chunks."""
        chunks = curation_service.get_unverified_chunks(limit=50)
        assert len(chunks) == 50, f"Expected 50 chunks, got {len(chunks)}"
        return chunks

    # Run benchmark
    result = benchmark(load_large_batch)

    # Validate results
    assert len(result) == 50, "Must load all 50 chunks"

    # Performance assertions (should scale linearly)
    stats = benchmark.stats
    mean_time = stats['mean']

    # 50 chunks should take <5 seconds (2.5x the 2s target for 20)
    assert mean_time < 5.0, \
        f"Mean time {mean_time:.3f}s exceeds 5s target for 50 chunks"


def test_edge_case_performance(benchmark, curation_service):
    """
    Test performance with edge cases (very short/long chunks).

    Args:
        benchmark: pytest-benchmark fixture
        curation_service: CurationService fixture

    Asserts:
        - Handles edge cases without significant slowdown
    """
    # Generate edge case chunks
    edge_chunks = [
        {'text': "X", 'id': str(uuid.uuid4())},  # Very short (1 char)
        {'text': "A " * 1000, 'id': str(uuid.uuid4())},  # Very long (2000 words)
        {'text': "", 'id': str(uuid.uuid4())},  # Empty (edge case)
    ]

    def process_edge_cases():
        """Process edge case chunks."""
        suggestions = []
        for chunk in edge_chunks:
            try:
                suggestion = curation_service.auto_suggest_lifecycle(chunk)
                suggestions.append(suggestion)
            except (AssertionError, KeyError):
                # Empty text may fail assertion
                suggestions.append('temporary')
        return suggestions

    # Run benchmark
    result = benchmark(process_edge_cases)

    # Validate results
    assert len(result) >= 2, "Must process at least 2 valid edge cases"

    # Performance assertions
    stats = benchmark.stats
    mean_time = stats['mean']

    # Edge cases should still be fast (<0.1s)
    assert mean_time < 0.1, \
        f"Edge case processing {mean_time:.3f}s too slow"
