"""F3: ChromaDB persist-directory resolution must honor MEMORY_MCP_DATA_DIR.

Regression for the silent wrong-store footgun: a direct VectorIndexer (or any
caller) that does not pass an explicit dir must resolve to the configured store,
not a hardcoded /data/chroma. Precedence:

    explicit arg > CHROMA_PERSIST_DIR > MEMORY_MCP_DATA_DIR/chroma > /data/chroma

The /data/chroma fallback (Railway volume default) is preserved when nothing is
set - that behavior is intentional and asserted by test_gate4_regression.
"""

import os
import unittest

from src.indexing.vector_indexer import resolve_persist_dir


class TestResolvePersistDir(unittest.TestCase):
    def setUp(self):
        self._saved = {
            k: os.environ.get(k) for k in ("CHROMA_PERSIST_DIR", "MEMORY_MCP_DATA_DIR")
        }
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_explicit_arg_wins(self):
        os.environ["CHROMA_PERSIST_DIR"] = "/from/env"
        os.environ["MEMORY_MCP_DATA_DIR"] = "/from/data"
        self.assertEqual(resolve_persist_dir("/explicit"), "/explicit")

    def test_chroma_env_beats_data_dir(self):
        os.environ["CHROMA_PERSIST_DIR"] = "/from/env"
        os.environ["MEMORY_MCP_DATA_DIR"] = "/from/data"
        self.assertEqual(resolve_persist_dir(), "/from/env")

    def test_memory_data_dir_used_when_no_chroma_env(self):
        # This is the bug: MEMORY_MCP_DATA_DIR was ignored on the direct path.
        os.environ["MEMORY_MCP_DATA_DIR"] = os.path.join("tmpdata", "store")
        self.assertEqual(
            resolve_persist_dir(),
            os.path.join("tmpdata", "store", "chroma"),
        )

    def test_default_fallback_preserved(self):
        # Nothing set -> the durable Railway volume default, unchanged.
        self.assertEqual(resolve_persist_dir(), "/data/chroma")


if __name__ == "__main__":
    unittest.main()
