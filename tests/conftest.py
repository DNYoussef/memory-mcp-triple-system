"""
Pytest configuration and fixtures
Shared test utilities for all test modules.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def test_data_dir():
    """Get test data directory."""
    return Path(__file__).parent / "test_data"


@pytest.fixture
def sample_texts():
    """Sample texts for testing."""
    return [
        "This is the first test sentence.",
        "Here is another sentence for testing.",
        "A third sentence to complete the set."
    ]
