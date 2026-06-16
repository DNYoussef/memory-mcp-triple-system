"""Gate: graph_query must return chunk TEXT, not blank results.

Repro for the graph_query empty-results bug. Ingestion stores the chunk body
under node metadata['text'] (167/197 live chunks), but
GraphQueryEngine._get_chunk_text read only the top-level 'text'/'content'
keys, so every graph_query result came back blank ("...").

Hermetic (fresh temp data dir) + canary-asserted (a unique string must
round-trip through query()).
"""

import shutil
import tempfile

from src.services.graph_query_engine import GraphQueryEngine
from src.services.graph_service import GraphService

CANARY = "ZZ_GRAPHQUERY_CANARY_unique_momentum_signal_42"


def test_graph_query_returns_metadata_text():
    data_dir = tempfile.mkdtemp(prefix="gqtest_")
    try:
        gs = GraphService(data_dir=data_dir)
        gs.add_entity_node("momentum", "CONCEPT", {"text": "momentum"})
        gs.add_chunk_node("c1", {"text": CANARY, "file_path": "x.md"})
        gs.add_relationship("c1", "mentions", "momentum")

        engine = GraphQueryEngine(gs)
        results = engine.query(query="momentum", max_hops=2, top_k=5)

        texts = " ".join(r.get("text", "") for r in results)
        assert CANARY in texts, f"chunk text not resolved; got {results!r}"
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    test_graph_query_returns_metadata_text()
    print("PASS")
