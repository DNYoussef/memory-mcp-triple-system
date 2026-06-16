"""F6: the embedder must not be force-loaded at NexusSearchTool construction.

Wiring it into the lifecycle manager used to access .embedder eagerly, loading
the ~8s SentenceTransformer at boot. It is now passed via a _LazyEmbedder proxy
that resolves on first use, so the MCP server boots fast.
"""
import os
import tempfile

from src.mcp.service_wiring import _LazyEmbedder


class TestLazyEmbedderProxy:
    def test_does_not_resolve_until_first_access(self):
        calls = {"n": 0}

        class Real:
            embedding_dim = 384

            def encode_single(self, text):
                return [0.0] * 384

        def provider():
            calls["n"] += 1
            return Real()

        proxy = _LazyEmbedder(provider)
        assert calls["n"] == 0  # nothing loaded yet
        assert proxy.embedding_dim == 384  # first access resolves
        assert calls["n"] == 1
        proxy.encode_single("x")  # reuses the resolved instance
        assert calls["n"] == 1

    def test_deepcopy_does_not_recurse(self):
        import copy
        proxy = _LazyEmbedder(lambda: object())
        # copying must not re-enter __getattr__ into RecursionError
        copy.deepcopy(proxy)
        copy.copy(proxy)


class TestConstructionIsLazy:
    def test_construction_does_not_load_embedder(self):
        saved = os.environ.get("MEMORY_MCP_DATA_DIR")
        os.environ["MEMORY_MCP_DATA_DIR"] = tempfile.mkdtemp(prefix="f6-")
        try:
            from src.mcp.service_wiring import NexusSearchTool, load_config

            tool = NexusSearchTool(load_config())
            # the SentenceTransformer is NOT loaded at boot...
            assert tool.vector_search_tool._embedder is None
            # ...and the lifecycle manager holds the lazy proxy, not the real model
            assert isinstance(tool.lifecycle_manager.embedding_pipeline, _LazyEmbedder)
        finally:
            if saved is None:
                os.environ.pop("MEMORY_MCP_DATA_DIR", None)
            else:
                os.environ["MEMORY_MCP_DATA_DIR"] = saved


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
