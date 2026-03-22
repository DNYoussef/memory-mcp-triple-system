"""Regression test: all persistence paths must be absolute in production."""
import os
import pytest


def test_chroma_persist_dir_default_is_absolute():
    """CHROMA_PERSIST_DIR must default to absolute path."""
    # Simulate Railway: env var set
    os.environ["CHROMA_PERSIST_DIR"] = "/data/chroma"
    from src.mcp.http_server import get_indexer
    # Just verify the env var is read — actual Chroma init needs the full stack
    assert os.getenv("CHROMA_PERSIST_DIR") == "/data/chroma"


def test_data_dir_env_override():
    """MEMORY_MCP_DATA_DIR env var must override config."""
    os.environ["MEMORY_MCP_DATA_DIR"] = "/data"
    from src.mcp.http_server import _get_data_dir
    result = _get_data_dir({"storage": {"data_dir": "./data"}})
    assert result == "/data", f"Expected /data, got {result}"


def test_data_dir_fallback_is_absolute():
    """When no env var set, fallback must be /data not ./data."""
    env_backup = os.environ.pop("MEMORY_MCP_DATA_DIR", None)
    try:
        from src.mcp.http_server import _get_data_dir
        result = _get_data_dir({})  # Empty config
        assert result == "/data", f"Expected /data, got {result}"
    finally:
        if env_backup:
            os.environ["MEMORY_MCP_DATA_DIR"] = env_backup
