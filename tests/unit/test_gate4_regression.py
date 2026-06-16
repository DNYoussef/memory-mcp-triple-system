"""
Gate 4 regression tests: lifecycle, legacy metadata, and storage durability.

Tests:
  - cleanup_expired method exists and is callable
  - stage_transitions uses numeric _ts fields, not ISO strings
  - vector_indexer backfill method exists
  - http_server defaults to /data/chroma, not /app/chroma_data
  - http_server has volume verification function
  - auth hardening uses secrets.compare_digest
"""

import os
import unittest


class TestLifecycleRegression(unittest.TestCase):
    """Verify lifecycle code fixes from Gate 4."""

    def test_cleanup_expired_exists(self):
        """lifecycle_manager must have cleanup_expired method."""
        src = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "memory", "lifecycle_manager.py"
        )
        with open(src, "r") as f:
            content = f.read()
        self.assertIn(
            "def cleanup_expired",
            content,
            "lifecycle_manager.py is missing cleanup_expired method"
        )

    def test_stage_transitions_uses_numeric_ts(self):
        """stage_transitions must query last_accessed_ts (float), not last_accessed (string)."""
        src = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "memory", "stage_transitions.py"
        )
        with open(src, "r") as f:
            content = f.read()
        # Must use last_accessed_ts with $lt
        self.assertIn("last_accessed_ts", content)
        # Must NOT use last_accessed (without _ts) in $lt queries
        # Find the demote query block
        demote_idx = content.find("demote_stale_chunks")
        query_block = content[demote_idx:demote_idx + 500]
        self.assertNotRegex(
            query_block,
            r'"last_accessed":\s*\{"\$lt"',
            "stage_transitions still uses last_accessed (string) in $lt query"
        )

    def test_stage_transitions_uses_demoted_at_ts(self):
        """Demoted chunk queries must use demoted_at_ts (float)."""
        src = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "memory", "stage_transitions.py"
        )
        with open(src, "r") as f:
            content = f.read()
        self.assertIn("demoted_at_ts", content)


class TestStorageDurability(unittest.TestCase):
    """Verify ChromaDB storage is durable, not container-local."""

    def test_default_persist_dir_is_volume(self):
        """http_server must default to /data/chroma, not /app/chroma_data."""
        src = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "mcp", "http_server.py"
        )
        with open(src, "r") as f:
            content = f.read()
        # The default must be /data/chroma
        self.assertIn(
            '"/data/chroma"',
            content,
            "http_server.py does not default to /data/chroma"
        )
        # /app/chroma_data must NOT appear as a default
        self.assertNotIn(
            'CHROMA_PERSIST_DIR", "/app/chroma_data"',
            content,
            "http_server.py still defaults to container-local /app/chroma_data"
        )

    def test_volume_verification_exists(self):
        """http_server must have a volume writability check."""
        src = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "mcp", "http_server.py"
        )
        with open(src, "r") as f:
            content = f.read()
        self.assertIn(
            "_verify_volume_writable",
            content,
            "http_server.py is missing _verify_volume_writable function"
        )

    def test_backfill_method_exists(self):
        """vector_indexer must have legacy metadata backfill."""
        src = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "indexing", "vector_indexer.py"
        )
        with open(src, "r") as f:
            content = f.read()
        self.assertIn(
            "_backfill_legacy_metadata",
            content,
            "vector_indexer.py is missing _backfill_legacy_metadata method"
        )

    def test_backfill_handles_missing_ts(self):
        """Backfill must check for and add last_accessed_ts and created_at_ts."""
        src = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "indexing", "vector_indexer.py"
        )
        with open(src, "r") as f:
            content = f.read()
        backfill_idx = content.find("_backfill_legacy_metadata")
        backfill_block = content[backfill_idx:backfill_idx + 2000]
        self.assertIn("last_accessed_ts", backfill_block)
        self.assertIn("created_at_ts", backfill_block)


class TestAuthHardening(unittest.TestCase):
    """Verify auth hardening from Gate 4."""

    def test_uses_compare_digest(self):
        """Auth must use secrets.compare_digest, not == for token comparison."""
        src = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "mcp", "http_server.py"
        )
        with open(src, "r") as f:
            content = f.read()
        self.assertIn("secrets.compare_digest", content)

    def test_config_matches_code_default(self):
        """config/memory-mcp.yaml persist_directory must match code default."""
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "config", "memory-mcp.yaml"
        )
        with open(config_path, "r") as f:
            config = f.read()
        self.assertIn(
            "/data/chroma",
            config,
            "config/memory-mcp.yaml does not use /data/chroma"
        )


if __name__ == "__main__":
    unittest.main()
