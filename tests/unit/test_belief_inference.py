"""
bayesian_inference on the belief web (PLAN-B sections 4.5, 5.1, 6.2 tests 7-12, 6.4).

Beliefs are written through the real memory_store ingestion path with the real
embedder (all-MiniLM-L6-v2, as in production), so the stored claim vectors and
the matcher are the ones that ship. The labeled dataset test asserts the rates
recorded when the threshold was chosen.
"""

import hashlib
import json
import math
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.belief_web.belief_store import BeliefStore
from src.belief_web.solver import CLAMP_L, logit, sigmoid
from src.mcp.request_router import handle_bayesian_inference
from src.services import memory_ingestion_service as mis
from src.services.memory_ingestion_service import MemoryIngestionService

T15 = "2026-10-14T15:00:00Z"
PILOT, RAILWAY = "guardspine.paid_pilot.exists", "guardspine.railway.incident"
PILOT_QUERY = "Do we have any paid pilots for GuardSpine yet?"
TABLES = ("belief_seq", "beliefs", "assertions", "edges", "aliases")


@pytest.fixture(scope="module")
def embedder():
    from src.indexing.embedding_pipeline import EmbeddingPipeline

    return EmbeddingPipeline()


@pytest.fixture
def web(tmp_path, embedder, monkeypatch):
    """A tool on the belief_web backend whose store is filled via memory_store.
    The ingestion clock is pinned at T15, so recorded_at is never after `now`."""
    fixed = datetime(2026, 10, 14, 15, 0, 0)

    class Frozen(datetime):
        @classmethod
        def utcnow(cls):
            return fixed

    monkeypatch.setattr(mis, "datetime", Frozen)
    svc = MemoryIngestionService(
        embedder=embedder,
        indexer=MagicMock(),
        graph_service=None,
        entity_service=None,
        classifier=None,
        lifecycle_manager=None,
        event_log=None,
    )
    svc._belief_store = BeliefStore(str(tmp_path / "agent_kv.db"))
    tool = SimpleNamespace(
        config={"belief_web": {"backend": "belief_web"}},
        nexus_processor=None,  # the legacy engine is never reached
        vector_search_tool=SimpleNamespace(embedder=embedder),
        kv_store=SimpleNamespace(db_path=tmp_path / "agent_kv.db"),
        _ingestion_service=svc,
    )
    yield tool
    svc._belief_store.close()


def record(tool, key, claim, value=True, source_type="witnessed", **kw):
    entry = {"key": key, "claim": claim, "value": value, "source_type": source_type}
    out = tool._ingestion_service.ingest(
        f"note about {key}", {"beliefs": [{**entry, "observed_at": T15, **kw}]}
    )
    assert out["beliefs"] == {"recorded": 1, "errors": []}, out["beliefs"]


def pilot_web(tool):
    record(tool, PILOT, "GuardSpine has at least one paying pilot customer", False)
    record(tool, RAILWAY, "The Railway platform security incident affected GuardSpine")


def threshold():
    from src.belief_web.inference import MATCH_THRESHOLD

    return MATCH_THRESHOLD


def ask(tool, **arguments):
    out = handle_bayesian_inference({"now": T15, **arguments}, tool)
    text = out["content"][0]["text"]
    try:
        return json.loads(text), out["isError"]
    except ValueError:  # a plain-text answer (the legacy engine's errors)
        return {"text": text}, out["isError"]


def store_of(tool):
    return tool._ingestion_service._belief_store


def table_hash(db):
    c = sqlite3.connect(str(db))
    try:
        rows = {
            t: sorted(c.execute(f"SELECT * FROM {t}").fetchall(), key=repr)
            for t in TABLES
        }
    finally:
        c.close()
    return hashlib.sha256(repr(rows).encode()).hexdigest()


# ================================================================ 7, 8: evidence refusal


def test_unknown_evidence_is_refused_not_ignored(web):
    pilot_web(web)
    bad = {"production_blocked": True, "railway_incident": True, "pr361_merged": True}
    payload, is_error = ask(web, query=PILOT_QUERY, evidence=bad)
    assert is_error is True
    assert "results" not in payload
    assert set(payload["unmatched_evidence"]) == set(bad)
    for candidates in payload["unmatched_evidence"].values():
        assert len(candidates) == 2  # every belief in this two-belief web
        assert {c["key"] for c in candidates} == {PILOT, RAILWAY}
    assert "memory_store" in payload["hint"]

    # positive control: a real key with a boolean is applied
    payload, is_error = ask(web, query=PILOT_QUERY, evidence={RAILWAY: True})
    assert is_error is False and payload["evidence"] == {RAILWAY: True}

    # explicit escape hatch: dropped keys are reported, never silent
    payload, is_error = ask(
        web, query=PILOT_QUERY, evidence=bad, unknown_evidence="drop"
    )
    assert is_error is False
    assert payload["ignored_evidence"] == sorted(bad)
    assert payload["evidence"] == {}


def test_non_boolean_evidence_refused(web):
    pilot_web(web)
    for evidence in ({"paid_pilots": 0}, {PILOT: 0}, {PILOT: "true"}):
        payload, is_error = ask(web, query=PILOT_QUERY, evidence=evidence)
        assert is_error is True and set(payload["unmatched_evidence"]) == set(evidence)
    payload, is_error = ask(web, query=PILOT_QUERY, evidence={PILOT: False})
    assert is_error is False  # control


def test_evidence_keys_are_slugged_and_alias_resolved(web):
    pilot_web(web)
    record(web, "guardspine.pilot.paid", "GuardSpine pilot is paid")
    store_of(web).merge("guardspine.pilot.paid", PILOT, "merge:m1")
    payload, is_error = ask(
        web, query=PILOT_QUERY, evidence={" GuardSpine.Pilot.Paid ": True}
    )
    assert is_error is False and payload["evidence"] == {PILOT: True}


# ================================================================ 9, 10: query matching


def test_irrelevant_present_node_not_answered(web):
    pilot_web(web)
    payload, is_error = ask(web, query=PILOT_QUERY)
    assert is_error is False
    assert next(iter(payload["results"])) == PILOT
    assert payload["results"][PILOT]["match_score"] >= threshold()


def test_no_match_returns_nearest_claims(web):
    record(web, "admin.passport.renewed", "The passport renewal is done")
    record(web, "infra.docker.working", "Docker works on the local machine")
    record(web, "infra.windows.updated", "Windows updates are installed")
    record(web, "events.devopscon.attending", "We are attending DevOpsCon New York")
    payload, is_error = ask(web, query=PILOT_QUERY)
    assert is_error is True and "results" not in payload
    assert len(payload["nearest"]) == 3
    assert all({"key", "claim", "score"} == set(n) for n in payload["nearest"])
    assert all(n["score"] < threshold() for n in payload["nearest"])
    scores = [n["score"] for n in payload["nearest"]]
    assert scores == sorted(scores, reverse=True)


def test_named_key_in_query_is_used_directly(web):
    pilot_web(web)
    payload, is_error = ask(web, query=f"what is {RAILWAY} now?")
    assert is_error is False
    assert list(payload["results"]) == [RAILWAY]
    assert payload["results"][RAILWAY]["match_score"] == 1.0


def test_empty_web_is_an_error(web):
    payload, is_error = ask(web, query=PILOT_QUERY)
    assert is_error is True and payload["error"] == "no beliefs recorded yet"


# ================================================================ 11: hypothetical evidence


def test_hypothetical_evidence_not_persisted(web, tmp_path):
    pilot_web(web)
    store_of(web).add_edge("live", RAILWAY, PILOT, "excludes", 0.5)
    before = table_hash(tmp_path / "agent_kv.db")
    payload, is_error = ask(web, query=PILOT_QUERY, evidence={RAILWAY: True})
    assert is_error is False
    assert table_hash(tmp_path / "agent_kv.db") == before
    # control: a real write changes the hash
    record(web, "k.other", "another claim")
    assert table_hash(tmp_path / "agent_kv.db") != before


def test_clamped_evidence_propagates_and_matches_solver(web):
    record(web, "k.a", "the alpha release shipped", source_type="reported")
    record(web, "k.b", "customers can use the alpha", source_type="reported")
    store_of(web).add_edge("live", "k.a", "k.b", "supports", 0.9)
    plain, _ = ask(web, query="k.b")
    clamped, is_error = ask(web, query="k.b", evidence={"k.a": True})
    assert is_error is False
    want = sigmoid(
        store_of(web).solve(T15, keys=["k.b"], clamp={"k.a": CLAMP_L}).L["k.b"]
    )
    got = clamped["results"]["k.b"]["probabilities"]["true"]
    assert math.isclose(got, want, abs_tol=1e-12)
    assert got > plain["results"]["k.b"]["probabilities"]["true"]
    (msg,) = clamped["results"]["k.b"]["messages"]
    assert (msg["from"], msg["type"], msg["weight"]) == ("k.a", "supports", 0.9)


def test_null_claim_vector_is_embedded_in_memory_only(web, tmp_path):
    store_of(web).add_assertion(  # written without linking: claim_vec stays NULL
        "live",
        PILOT,
        polarity=-1,
        source_type="reported",
        observed_at=T15,
        recorded_at=T15,
        chunk_id="c1",
        claim="GuardSpine has at least one paying pilot customer",
    )
    before = table_hash(tmp_path / "agent_kv.db")
    payload, is_error = ask(web, query=PILOT_QUERY)
    assert is_error is False and list(payload["results"]) == [PILOT]
    assert table_hash(tmp_path / "agent_kv.db") == before


# ================================================================ 12: output shape


def test_output_shape_backward_compatible(web):
    """Regression guard (passes on main): the default backend still answers in
    the legacy shape, keys and values untouched (6e3c6b7 included)."""
    web.config = {}
    engine = MagicMock()
    engine.query_conditional.return_value = {
        "results": {
            "guardspine": {
                "probabilities": {"true": 0.6, "false": 0.4},
                "entropy": 0.97,
            }
        },
        "evidence": {"igor": "true"},
        "timeout": False,
    }
    web.nexus_processor = SimpleNamespace(
        probabilistic_query_engine=engine,
        _extract_query_entity=lambda q: "GuardSpine",
    )
    net = MagicMock()
    net.nodes.return_value = ["guardspine", "igor"]
    web.graph_service = object()
    web._build_bayesian_network = lambda graph: net
    out = handle_bayesian_inference(
        {"query": "GuardSpine", "evidence": {"igor": True, "nope": True}}, web
    )
    assert out["isError"] is False
    assert json.loads(out["content"][0]["text"]) == {
        **engine.query_conditional.return_value,
        "ignored_evidence": ["nope"],
    }


def test_belief_web_output_is_a_superset(web):
    pilot_web(web)
    payload, is_error = ask(web, query=PILOT_QUERY)
    assert is_error is False
    assert {"results", "evidence", "timeout"} <= set(payload)  # the legacy keys
    assert set(payload) == {
        "results",
        "evidence",
        "ignored_evidence",
        "unmatched_evidence",
        "timeout",
        "converged",
        "iterations",
        "method",
        "backend",
        "now",
    }
    assert payload["method"] == "belief_web_v1 log-odds propagation"
    assert payload["backend"] == "belief_web" and payload["converged"] is True
    result = payload["results"][PILOT]
    assert set(result) == {
        "probabilities",
        "entropy",
        "claim",
        "match_score",
        "kind",
        "evidence",
        "messages",
        "holes",
    }
    p = result["probabilities"]["true"]
    assert math.isclose(p, 1 - 0.95)  # witnessed false, fresh
    assert math.isclose(result["probabilities"]["false"], 1 - p)
    assert math.isclose(
        result["entropy"], -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
    )
    (ev,) = result["evidence"]
    assert ev["status"] == "active" and ev["polarity"] == -1
    assert math.isclose(ev["llr"], -logit(0.95), abs_tol=1e-6) and ev["age_days"] == 0


def test_default_backend_is_legacy(web):
    """No config, or pgmpy_legacy: the legacy handler answers (here: no engine)."""
    for config in (
        {},
        {"belief_web": {"backend": "pgmpy_legacy"}},
        {"belief_web": None},
    ):
        web.config = config
        out = handle_bayesian_inference({"query": PILOT_QUERY}, web)
        assert out == {
            "content": [{"type": "text", "text": "Bayesian engine unavailable"}],
            "isError": True,
        }
    web.config = {"belief_web": {"backend": "pgmpy"}}
    out = handle_bayesian_inference({"query": PILOT_QUERY}, web)
    assert (
        out["isError"] is True
        and "Unknown belief_web.backend" in out["content"][0]["text"]
    )


@pytest.mark.parametrize(
    "arguments, message",
    [
        ({"query": ""}, "No query provided"),
        ({"query": "x", "evidence": [1]}, "evidence must be an object"),
        ({"query": "x", "unknown_evidence": "ignore"}, "unknown_evidence must be"),
        ({"query": "x", "top_k": 0}, "top_k must be"),
        ({"query": "x", "top_k": True}, "top_k must be"),
        ({"query": "x", "now": "yesterday"}, "unparseable timestamp"),
    ],
)
def test_bad_arguments_are_errors(web, arguments, message):
    out = handle_bayesian_inference(arguments, web)
    assert out["isError"] is True and message in out["content"][0]["text"]


# ================================================================ 6.4 labeled dataset


def test_match_threshold_rates_on_labeled_dataset(tmp_path, embedder):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    try:
        import choose_match_threshold as chooser
    finally:
        sys.path.pop(0)
    data = chooser.load()
    matcher = chooser.build_matcher(data, embedder, tmp_path / "labeled.db")
    labeled, none = chooser.ranked(matcher, data)
    got = chooser.confusion(labeled, none, threshold())
    assert got["false_accept_rate"] <= chooser.MAX_FALSE_ACCEPT
    assert (got["correct"], got["wrong_key"], got["missed"]) == (58, 2, 0)
    assert got["no_match_false_accept"] == 0
    assert chooser.choose(labeled, none)["threshold"] == round(threshold(), 4)


# ================================================================ review r1


def test_first_read_never_creates_tables(tmp_path, embedder):
    from src.stores.kv_store import KVStore

    db = tmp_path / "agent_kv.db"
    KVStore(str(db)).close()  # a live database from before B-PR2
    missing = tmp_path / "absent" / "agent_kv.db"
    for path in (db, missing):
        tool = SimpleNamespace(
            config={"belief_web": {"backend": "belief_web"}},
            # an indexer, so the old path really builds its write store
            vector_search_tool=SimpleNamespace(embedder=embedder, indexer=MagicMock()),
            kv_store=SimpleNamespace(db_path=path),
        )
        payload, is_error = ask(tool, query=PILOT_QUERY)
        assert is_error is True and payload["error"] == "no beliefs recorded yet"
        assert not hasattr(tool, "_belief_reader")  # retried once tables exist
    assert not missing.exists() and not missing.parent.exists()
    c = sqlite3.connect(str(db))
    names = {n for (n,) in c.execute("SELECT name FROM sqlite_master")}
    c.close()
    assert not names & set(TABLES)
    assert (
        "migrations" not in names
        or not sqlite3.connect(str(db))
        .execute("SELECT 1 FROM migrations WHERE version='008'")
        .fetchone()
    )


def test_reader_connection_refuses_writes(web):
    pilot_web(web)
    payload, is_error = ask(web, query=PILOT_QUERY)
    assert is_error is False
    conn = web._belief_reader._conn()
    assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("UPDATE belief_seq SET n = n + 1")
    # control: the writer's connection still writes
    store_of(web)._conn().execute("UPDATE belief_seq SET n = n")


def test_conflicting_evidence_for_one_belief_refused(web):
    pilot_web(web)
    record(web, "guardspine.pilot.paid", "GuardSpine pilot is paid")
    store_of(web).merge("guardspine.pilot.paid", PILOT, "merge:m1")
    for evidence in (
        {PILOT: True, "guardspine.pilot.paid": False},
        {"guardspine.pilot.paid": False, PILOT: True},
        {"GuardSpine.Paid_Pilot.Exists": True, PILOT: False},  # slug collision
    ):
        payload, is_error = ask(web, query=PILOT_QUERY, evidence=evidence)
        assert is_error is True and "results" not in payload
        assert payload["conflicting_evidence"] == {PILOT: evidence}
    # identical duplicates are one fact, not a conflict
    payload, is_error = ask(
        web, query=PILOT_QUERY, evidence={PILOT: True, "guardspine.pilot.paid": True}
    )
    assert is_error is False and payload["evidence"] == {PILOT: True}


@pytest.mark.parametrize("bad", [[], False, 0, "", [1]])
def test_supplied_evidence_must_be_an_object(web, bad):
    pilot_web(web)
    payload, is_error = ask(web, query=PILOT_QUERY, evidence=bad)
    assert is_error is True and "evidence must be an object" in payload["error"]


def test_inference_holes_match_find_holes_on_the_component(web, monkeypatch):
    """Sol r1 finding 5: a witnessed tie that find_holes reports as contradicted
    came back from inference with holes []. Inference now runs the same
    predicates on the component it solves; the entries must be identical."""
    from src.mcp.request_router import handle_call_tool

    s = store_of(web)
    for pol, ref in ((1, "ref:a"), (-1, "ref:b")):
        s.add_assertion("live", "k.tie", polarity=pol, source_type="witnessed",
                        observed_at=T15, recorded_at=T15, chunk_id=ref,
                        source_ref=ref, reliability=0.9, claim="the tie holds")  # fmt: skip
    record(web, "k.a", "alpha holds", reliability=0.9)
    record(web, "k.b", "beta holds", source_type="witnessed", reliability=0.8)
    s.add_edge("live", "k.a", "k.b", "excludes", 0.5)
    record(web, "k.far", "an unrelated belief", source_type="reported")
    out = handle_call_tool("find_holes", {"now": T15, "limit": 200}, web)
    whole = json.loads(out["content"][0]["text"])["holes"]

    real, scopes = BeliefStore.web, []

    def spy(self, now, keys=None):
        scopes.append(None if keys is None else sorted(keys))
        return real(self, now, keys=keys)

    monkeypatch.setattr(BeliefStore, "web", spy)
    for key in ("k.tie", "k.a"):
        payload, is_error = ask(web, query=key)
        assert is_error is False
        mine = payload["results"][key]["holes"]
        want = [h for h in whole if key in (h.get("key"), *h.get("keys", ()))]
        assert mine == want and mine
    assert {h["hole"] for h in mine} == {"contradicted_pair"}
    assert scopes == [["k.tie"], ["k.a"]]  # one component snapshot per call


def test_omitted_or_null_evidence_is_none(web):
    pilot_web(web)
    for arguments in ({}, {"evidence": None}):
        payload, is_error = ask(web, query=PILOT_QUERY, **arguments)
        assert is_error is False and payload["evidence"] == {}


# ================================================================ review r2: mid-WAL


WAL_WRITER = """
import sys
sys.path.insert(0, sys.argv[1])
from src.belief_web.belief_store import BeliefStore

store = BeliefStore(sys.argv[2])  # journal_mode=WAL on its connection
store.add_assertion(
    "live", "k.wal", polarity=1, source_type="witnessed",
    observed_at=sys.argv[3], recorded_at=sys.argv[3], chunk_id="c1",
    claim="the WAL writer committed this claim",
)
print("READY", flush=True)
sys.stdin.readline()  # hold the connection: no close, so no checkpoint
"""


def test_reader_sees_rows_mid_wal_from_writer_process(tmp_path, embedder):
    """A writer process commits and stays connected, so the rows live only in
    the -wal file. The inference reader must see them and write nothing."""
    db = tmp_path / "dir with space #1" / "agent_kv.db"
    wal = db.with_name(db.name + "-wal")
    root = str(Path(__file__).resolve().parents[2])
    writer = subprocess.Popen(
        [sys.executable, "-c", WAL_WRITER, root, str(db), T15],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    tool = SimpleNamespace(
        config={"belief_web": {"backend": "belief_web"}},
        vector_search_tool=SimpleNamespace(embedder=embedder),
        kv_store=SimpleNamespace(db_path=db),
    )
    try:
        line = writer.stdout.readline()
        assert line.strip() == "READY", writer.stderr.read()
        assert wal.exists() and wal.stat().st_size > 0

        def snapshot():
            c = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                rows = {
                    t: sorted(c.execute(f"SELECT * FROM {t}").fetchall(), key=repr)
                    for t in TABLES
                }
            finally:
                c.close()
            digest = hashlib.sha256(repr(rows).encode()).hexdigest()
            main = hashlib.sha256(db.read_bytes()).hexdigest()
            return main, wal.stat().st_size, digest, rows["beliefs"]

        before = snapshot()
        assert [r[1] for r in before[3]] == ["k.wal"]  # committed, in the WAL

        payload, is_error = ask(tool, query="what is k.wal")
        assert is_error is False, payload
        assert list(payload["results"]) == ["k.wal"]
        assert math.isclose(payload["results"]["k.wal"]["probabilities"]["true"], 0.95)

        assert snapshot()[:3] == before[:3]  # main bytes, -wal size, tables
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            tool._belief_reader._conn().execute("UPDATE belief_seq SET n = n")
        assert snapshot()[:3] == before[:3]
        assert writer.poll() is None  # the writer held its connection throughout
    finally:
        reader = getattr(tool, "_belief_reader", None)
        if reader is not None:
            reader.close()
        if writer.poll() is None:
            writer.stdin.close()
            try:
                writer.wait(timeout=30)
            except subprocess.TimeoutExpired:
                writer.kill()
                writer.wait()
