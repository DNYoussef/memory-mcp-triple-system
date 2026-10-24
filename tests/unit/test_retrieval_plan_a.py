"""A1 retrieval: seeds, phrase matching, seed weights and reported scores.

Real GraphService / GraphQueryEngine / HippoRagService on small in-memory graphs.
Only NER is stubbed. The ingest-then-query guards (T1i, T1j) need real spaCy and
live in tests/integration/test_retrieval_ingest_query.py.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.nexus.processor import NexusProcessor
from src.services.graph_query_engine import GraphQueryEngine
from src.services.graph_service import GraphService
from src.services.hipporag_service import HippoRagService


class StubNER:
    """Reports each listed name that appears in the text, nothing else."""

    nlp = None

    def __init__(self, *names):
        self.names = names

    def extract_entities(self, text):
        return [
            {"text": n, "type": "ORG", "start": 0, "end": len(n)}
            for n in self.names
            if n in text
        ]


def _graph(tmp_path, chunks, names=None):
    """chunks: [(chunk_id, [entity_id, ...])] in insertion order (oldest first)."""
    names = names or {}
    gs = GraphService(data_dir=str(tmp_path))
    for cid, ents in chunks:
        gs.add_chunk_node(cid, {"text": cid})
        for e in ents:
            if gs.get_node(e) is None:
                gs.add_entity_node(
                    e, "ORG", {"text": names.get(e, e.replace("_", " "))}
                )
            gs.add_relationship(cid, "mentions", e)
    return gs


def _ids(results):
    return [r.chunk_id if hasattr(r, "chunk_id") else r["chunk_id"] for r in results]


# ---- T1a / T1l / T1g: order of the primary score and of exact ties ----


def test_t1a_exact_ties_keep_insertion_order(tmp_path):
    gs = _graph(tmp_path, [("old", ["seed", "a1"]), ("new", ["seed", "b1"])])
    h = HippoRagService(gs, StubNER("Seed"))
    assert _ids(h.retrieve_multi_hop("Seed", top_k=5)) == ["old", "new"]


@pytest.mark.parametrize(
    "detailed, pings, ner, query",
    [
        (  # astra: migration runbook vs three newer status pings
            ["london", "paris", "migration", "cutover", "rollback", "dns"],
            ["london", "paris", "status"],
            ("London", "Paris"),
            "London Paris migration status",
        ),
        (  # sol: detailed failure note vs three newer near-duplicates
            ["deploy", "outage", "root_cause", "remediation", "rollback"],
            ["deploy", "outage", "update"],
            ("Deploy", "Outage"),
            "Deploy Outage",
        ),
    ],
)
def test_t1l_newer_repetitive_notes_do_not_crowd_out_detailed_note(
    tmp_path, detailed, pings, ner, query
):
    chunks = [("detailed", detailed)] + [(f"ping{i}", pings) for i in range(3)]
    h = HippoRagService(_graph(tmp_path, chunks), StubNER(*ner))
    assert _ids(h.retrieve_multi_hop(query, top_k=5))[0] == "detailed"


def test_t1g_higher_primary_outranks_older_chunk(tmp_path):
    gs = _graph(tmp_path, [("one_seed", ["alpha"]), ("two_seeds", ["alpha", "bravo"])])
    h = HippoRagService(gs, StubNER("Alpha", "Bravo"))
    assert _ids(h.retrieve_multi_hop("Alpha Bravo", top_k=5))[0] == "two_seeds"


# ---- T1h: reported scores ----


def _strictly_decreasing(xs):
    return all(a > b for a, b in zip(xs, xs[1:]))


@pytest.mark.parametrize(
    "hi, lo", [(0.432709765, 0.432669419), (0.484936586, 0.484934356)]
)
def test_t1h_scores_strictly_decrease_through_tier_and_hybrid_rank(tmp_path, hi, lo):
    gs = _graph(
        tmp_path,
        [("c_hi", ["alpha"]), ("c_lo", ["bravo"]), ("c_tie", ["bravo"])],
    )
    engine = GraphQueryEngine(gs)
    engine.personalized_pagerank = lambda **_kw: {"alpha": hi, "bravo": lo}
    raw = engine.retrieve_multi_hop("alpha bravo", top_k=10)
    assert _ids(raw) == ["c_hi", "c_lo", "c_tie"]
    scores = [r["score"] for r in raw]
    assert all(s > 0 for s in scores) and _strictly_decreasing(scores)

    proc = NexusProcessor(
        vector_indexer=MagicMock(),
        graph_query_engine=engine,
        probabilistic_query_engine=MagicMock(),
        embedding_pipeline=MagicMock(),
    )
    tier = proc._query_hipporag_tier("alpha bravo", 10)
    assert _strictly_decreasing([r["score"] for r in tier])
    assert [r["id"] for r in proc.rank(tier)] == ["c_hi", "c_lo", "c_tie"]


def test_t1h_thousand_results_stay_positive_and_decreasing(tmp_path):
    chunks = [(f"c{i:04d}", ["one"]) for i in range(1002)] + [("last", ["half"])]
    engine = GraphQueryEngine(_graph(tmp_path, chunks))
    ranked = engine.rank_chunks_by_ppr({"one": 1.0, "half": 0.499750623}, top_k=1003)
    scores = [s for _, s in ranked]
    assert len(scores) == 1003 and ranked[-1][0] == "last"
    assert all(s > 0 for s in scores) and _strictly_decreasing(scores)


# ---- T1b: word-boundary phrase matcher ----


def test_t1b_phrase_matcher(tmp_path):
    gs = _graph(
        tmp_path,
        [
            ("c1", ["proprioceptive_ai", "united_states", "guardspine", "auditor"]),
            ("c2", ["a", "in", "the", "2", "planning"]),
        ],
        names={"proprioceptive_ai": "Proprioceptive AI", "guardspine": "GuardSpine"},
    )
    gs.graph.add_node("python", type="entity", text="Python", metadata={})
    gs.graph.add_node("us_alias", type="entity", metadata={"name": "United States"})
    m = GraphQueryEngine(gs)._extract_query_entities
    assert m("What is Proprioceptive AI?") == ["proprioceptive_ai"]
    assert m("what happened in United States") == ["united_states"]
    assert m("united-states policy") == ["united_states"]
    assert sorted(m("GuardSpine's auditor, validation")) == ["auditor", "guardspine"]
    assert m("I write Python") == ["python"]
    assert m("what are the holes in the plan") == []


def test_t1b_name_only_in_metadata_name_matches(tmp_path):
    gs = GraphService(data_dir=str(tmp_path))
    gs.graph.add_node("usa_node", type="entity", metadata={"name": "United States"})
    assert GraphQueryEngine(gs)._extract_query_entities("visit United States") == [
        "usa_node"
    ]


# ---- T1c / T1k: bounded, name-deduplicated fallback ----


def test_t1c_fallback_fills_second_seed_and_skips_same_name_junk(tmp_path):
    gs = _graph(
        tmp_path,
        [
            ("c1", ["guardspine", "holes"]),
            ("c2", ["guardspine", "holes"]),
            ("c3", ["guardspine", "##_guardspine"]),
        ],
        names={"guardspine": "GuardSpine", "##_guardspine": "## GuardSpine"},
    )
    h = HippoRagService(gs, StubNER("GuardSpine"))
    assert h._get_query_nodes("what are the holes in GuardSpine") == [
        "guardspine",
        "holes",
    ]


def test_t1c_fallback_skips_other_node_with_the_ner_seeds_name(tmp_path):
    # The NER seed 'guardspine,_inc' is not the canonical node for its name
    # "guardspine inc"; the rarer canonical node 'guardspine_inc' must not take
    # the second slot from 'holes'.
    gs = _graph(
        tmp_path,
        [
            ("c1", ["guardspine,_inc", "holes"]),
            ("c2", ["guardspine,_inc", "holes"]),
            ("c3", ["guardspine_inc"]),
        ],
        names={
            "guardspine,_inc": "GuardSpine, Inc.",
            "guardspine_inc": "GuardSpine Inc",
        },
    )
    h = HippoRagService(gs, StubNER("GuardSpine, Inc."))
    assert h._get_query_nodes("what are the holes in GuardSpine, Inc.") == [
        "guardspine,_inc",
        "holes",
    ]


PHRASES = ["amber", "birch", "cedar", "delta", "ember"]
PHRASES += ["fjord", "grove", "harbor", "iris", "jade"]


def test_t1k_fallback_cannot_multiply_one_seed(tmp_path):
    chunks = [("target", ["xenon", "own1"])]
    chunks += [("other_x1", ["xenon", "misc1"]), ("other_x2", ["xenon", "misc2"])]
    chunks += [(f"distract_{p}", [p, f"miscd{i}"]) for i, p in enumerate(PHRASES)]
    h = HippoRagService(_graph(tmp_path, chunks), StubNER("Xenon"))
    query = "Xenon " + " ".join(PHRASES)
    assert len(h._get_query_nodes(query)) == 2
    assert _ids(h.retrieve_multi_hop(query, top_k=20)).index("target") < 2


# ---- T1d: the handler prints the seeds retrieval used ----


def test_t1d_handler_lists_real_seeds(tmp_path):
    from src.mcp.request_router import handle_hipporag_retrieve

    gs = _graph(tmp_path, [("chunk_one", ["auditor"])])
    tool = SimpleNamespace(hipporag_service=HippoRagService(gs, StubNER("ANALYSIS")))
    out = handle_hipporag_retrieve({"query": "ANALYSIS of the auditor"}, tool)
    text = "".join(c["text"] for c in out["content"])
    assert "Seeds: auditor" in text


# ---- T1e: seeds go straight to PPR ----


def test_t1e_multi_hop_matches_single_hop(tmp_path):
    gs = _graph(tmp_path, [("old", ["seed", "a1"]), ("new", ["seed", "b1"])])
    gs.add_relationship("a1", "related_to", "far")
    h = HippoRagService(gs, StubNER("Seed"))
    assert _ids(h.retrieve_multi_hop("Seed", max_hops=3)) == _ids(h.retrieve("Seed"))


# ---- T1f: 1/degree seed weights ----


def test_t1f_rare_seed_outweighs_hub(tmp_path):
    chunks = [(f"h{i}", ["hub"]) for i in range(19)] + [("both", ["hub", "rare"])]
    engine = GraphQueryEngine(_graph(tmp_path, chunks))
    w = engine._create_personalization_vector(["hub", "rare"])
    assert w["rare"] == pytest.approx(20 * w["hub"])
    assert sum(w.values()) == pytest.approx(1.0)
