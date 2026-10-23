"""A1 ingest-then-query guards (T1i, T1j): ingestion and query share one NER pipeline,
so a new memory naming the query's entities ranks first. Needs the real spaCy model.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from src.services.entity_service import EntityService
from src.services.graph_service import GraphService
from src.services.hipporag_service import HippoRagService
from src.services.memory_ingestion_service import MemoryIngestionService


# ---- T1i / T1j: real ingestion, then query with the same NER ----


def _ingest_all(tmp_path, texts):
    ner = EntityService()
    if ner.nlp is None:
        pytest.skip("spaCy model not available")
    gs = GraphService(data_dir=str(tmp_path))
    embedder = MagicMock()
    embedder.encode.return_value = [np.zeros(4)]
    svc = MemoryIngestionService(
        embedder=embedder,
        indexer=MagicMock(),
        graph_service=gs,
        entity_service=ner,
        classifier=None,
        lifecycle_manager=None,
        event_log=None,
    )
    ids = [svc.ingest(t, {})["chunk_id"] for t in texts]
    return HippoRagService(gs, ner), ids


def test_t1i_new_memory_ranks_first_over_legacy_chunks(tmp_path):
    texts = [f"GuardSpine, Inc. filed report {i}." for i in range(3)]
    texts += [f"Google shipped release {i} of the app." for i in range(20)]
    new = "GuardSpine, Inc. met Google about n8n."
    h, ids = _ingest_all(tmp_path, texts + [new])
    assert h.retrieve_multi_hop(new, top_k=10)[0].chunk_id == ids[-1]


def test_t1j_new_memory_ranks_first_over_shared_city_chunks(tmp_path):
    texts = [f"London and Paris office note {i}." for i in range(5)]
    new = "London and Paris tested WeRAI Research."
    h, ids = _ingest_all(tmp_path, texts + [new])
    assert h.retrieve_multi_hop(new, top_k=10)[0].chunk_id == ids[-1]
