"""
memory_store `beliefs`/`because` ingestion (PLAN-B section 4.1, 4.2, 6.2 B-PR2).

Tests 1-6 and 6b of section 6.2 plus the backward-compatibility guard: a store
without beliefs answers exactly as before and never creates the belief tables.
Values match the reference calculator belief_calc_r8.py (F2*, F14, F15, P1-P4).
"""

import asyncio
import math
import sqlite3
from array import array
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.belief_web.belief_store import BeliefStore
from src.belief_web.solver import logit, sigmoid
from src.services import memory_ingestion_service as mis
from src.services.memory_ingestion_service import MemoryIngestionService
from src.stores.kv_store import KVStore

T12, T15 = "2026-10-14T12:00:00Z", "2026-10-14T15:00:00Z"
a9, a95, a7 = logit(0.9), logit(0.95), logit(0.7)
BUDGET = "Budget decision: we keep the Q4 travel budget at the current level. " * 2
PRICE = "Nick's price sheet still unsent; waiting on the final pricing numbers. " * 2
TRAVEL = "Travel: the Philadelphia trip moves to November after the cruise week. " * 2
THREE = "\n\n".join([BUDGET, PRICE, TRAVEL])  # >= 300 chars, so it is chunked
MAIN_RESULT_KEYS = {
    "success",
    "chunk_id",
    "chunk_ids",
    "chunks_stored",
    "stored_at",
    "text_length",
    "metadata",
    "entities",
    "lifecycle_tier",
    "elapsed_ms",
    "graph_persisted",
    "warnings",
}


class ParagraphChunker:
    def chunk_text(self, text, file_path):
        return [{"text": p} for p in text.split("\n\n")]


def freeze(monkeypatch, iso):
    """Pin the ingestion clock, so recorded_at is a known instant."""
    fixed = datetime.fromisoformat(iso.replace("Z", ""))

    class Frozen(datetime):
        @classmethod
        def utcnow(cls):
            return fixed

    monkeypatch.setattr(mis, "datetime", Frozen)


def service(tmp_path, own_store=True, **kw):
    """Ingestion with fakes for the vector and graph stores and a real BeliefStore.
    own_store=False leaves the store to be opened lazily next to a KVStore."""
    embedder = MagicMock()
    embedder.encode.return_value = [[0.0] * 8]
    embedder.model_name = "test-embedder"
    entities = MagicMock()
    entities.extract_entities.return_value = [{"text": "Nick"}]
    entities.add_entities_to_graph.return_value = {
        "entities_added": 0,
        "relationships_created": 0,
        "entity_types": [],
    }
    graph = MagicMock()
    graph.save_graph.return_value = True
    svc = MemoryIngestionService(
        embedder=embedder,
        indexer=MagicMock(),
        graph_service=graph,
        entity_service=entities,
        classifier=None,
        lifecycle_manager=None,
        event_log=None,
        chunker=ParagraphChunker(),
        **kw,
    )
    if own_store:
        svc._belief_store = BeliefStore(str(tmp_path / "agent_kv.db"))
    return svc


def belief(key, value=True, source_type="witnessed", **kw):
    return {"key": key, "claim": f"{key} holds", "value": value,
            "source_type": source_type, **kw}  # fmt: skip


def rows(svc, sql="SELECT belief_key, chunk_id, located, source_id FROM assertions"):
    return sorted(svc._belief_store._conn().execute(sql).fetchall())


def store_count(svc):
    c = svc._belief_store._conn()
    return {
        t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in ("beliefs", "assertions", "edges", "aliases")
    }


def stdio(svc, text, metadata):
    from src.mcp.request_router import handle_memory_store

    tool = SimpleNamespace(config={}, _ingestion_service=svc)
    return handle_memory_store({"text": text, "metadata": metadata}, tool)


def http(svc, monkeypatch, text, metadata):
    from src.mcp import http_server

    monkeypatch.setattr(http_server, "get_ingestion_service", lambda: svc)
    return asyncio.run(
        http_server.memory_store(
            http_server.MemoryStoreRequest(text=text, metadata=metadata)
        )
    )


TAGS = {"who": "alice", "when": T15, "project": "p", "why": "test"}


# ================================================================ 1. both transports


def test_schema_documents_beliefs_and_because():
    from src.mcp.tool_registry import _memory_store_tool

    props = _memory_store_tool()["inputSchema"]["properties"]["metadata"]["properties"]
    item = props["beliefs"]["items"]
    assert set(item["properties"]) == mis.BELIEF_FIELDS  # schema and ingestion agree
    assert item["required"] == ["key", "value", "source_type"]
    assert props["because"]["items"] == {"type": "string"}


def test_memory_store_records_belief_stdio_and_http(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    out = stdio(
        svc, "Nick price sheet was sent", {**TAGS, "beliefs": [belief("k.one")]}
    )
    text = out["content"][0]["text"]
    assert text.startswith("Stored memory: ")
    assert text.endswith("\nBeliefs: recorded 1")
    assert "Belief errors" not in text
    assert out["isError"] is False
    assert out["beliefs_recorded"] == 1 and out["belief_errors"] == []

    body = http(svc, monkeypatch, "second note", {**TAGS, "beliefs": [belief("k.two")]})
    assert body["success"] is True
    assert body["beliefs"] == {"recorded": 1, "errors": []}
    assert [k for k, *_ in rows(svc)] == ["k.one", "k.two"]
    # positive control for the sum: both rows count, p is the witnessed value
    assert math.isclose(svc._belief_store.probability("k.one", T15), 0.95)


def test_belief_linking_fills_claim_columns(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    stdio(svc, "note", {**TAGS, "beliefs": [belief("k.one")]})
    project, entities, vec, model = (
        svc._belief_store._conn()
        .execute("SELECT project, entities, claim_vec, vec_model FROM beliefs")
        .fetchone()
    )
    assert (project, entities, model) == ("p", '["Nick"]', "test-embedder")
    assert len(vec) == 8 * 4  # float32 per dimension


# ================================================================ 2. bad entries


def test_bad_belief_still_stores_memory(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    entries = [
        belief("k.good", observed_at="2026-10-14T12:00:00"),  # naive: UTC
        belief("Bad Key"),
        belief("k.nan", reliability=float("nan")),
        belief("k.future", observed_at="2026-10-14T16:00:00Z"),
        {"key": "k.noclaim", "value": True, "source_type": "reported"},
        {"key": "k.legacy", "claim": "x causes y", "confidence": 0.7},
    ]
    out = stdio(svc, "one memory", {**TAGS, "beliefs": entries})
    text = out["content"][0]["text"]
    assert text.startswith("Stored memory: ")
    svc._indexer.index_chunks.assert_called_once()  # the memory is stored
    assert "\nBeliefs: recorded 1\nBelief errors: " in text
    errors = out["belief_errors"]
    assert [e.split(":")[0] for e in errors] == [
        "Bad Key",
        "k.nan",
        "k.future",
        "k.noclaim",
        "k.legacy",
    ]
    assert "future observation" in errors[2] and "needs a claim" in errors[3]
    assert "unknown fields ['confidence']" in errors[4]
    got = rows(svc, "SELECT belief_key, observed_at FROM assertions")
    assert got == [("k.good", "2026-10-14T12:00:00.000000Z")]
    assert [k for (k,) in rows(svc, "SELECT key FROM beliefs")] == ["k.good"]

    # positive control: an existing key needs no claim
    again = {"key": "k.good", "value": True, "source_type": "reported"}
    out = stdio(svc, "two", {**TAGS, "beliefs": [again]})
    assert out["beliefs_recorded"] == 1 and out["belief_errors"] == []


def test_belief_errors_are_sanitized_and_capped(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    bad = [belief(f"k.<private>secret{i}</private>") for i in range(40)]
    out = stdio(svc, "note", {**TAGS, "beliefs": bad})
    text = out["content"][0]["text"]
    assert "secret" not in text and "secret" not in repr(out["belief_errors"])
    assert "[REDACTED]" in out["belief_errors"][0]
    line = text.split("\nBelief errors: ", 1)[1]
    assert len(line) == 500


# ================================================================ 3. atomic write


def test_belief_write_failure_leaves_no_partial_rows(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    real = BeliefStore._insert_assertion
    calls = []

    def flaky(self, c, row):
        calls.append(row)
        if len(calls) == 2:
            raise sqlite3.OperationalError("disk I/O error")
        return real(self, c, row)

    monkeypatch.setattr(BeliefStore, "_insert_assertion", flaky)
    entries = [belief("k.a"), belief("k.b", depends_on=["k.c"])]
    out = stdio(svc, "note", {**TAGS, "beliefs": entries})
    assert len(calls) == 2
    svc._indexer.index_chunks.assert_called_once()
    assert out["isError"] is False and out["beliefs_recorded"] == 0
    assert out["belief_errors"] == [
        "beliefs: not recorded (disk I/O error); no belief rows kept"
    ]
    assert store_count(svc) == {"beliefs": 0, "assertions": 0, "edges": 0, "aliases": 0}

    monkeypatch.setattr(BeliefStore, "_insert_assertion", real)  # control
    out = stdio(svc, "note", {**TAGS, "beliefs": entries})
    assert out["beliefs_recorded"] == 2
    assert store_count(svc) == {"beliefs": 3, "assertions": 2, "edges": 1, "aliases": 0}


# ================================================================ 4. foreign keys


def test_fk_enforced_through_memory_store(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    real = BeliefStore._belief

    def skip_orphan(self, c, origin, key, *a, **kw):
        if key != "k.orphan":
            return real(self, c, origin, key, *a, **kw)

    monkeypatch.setattr(BeliefStore, "_belief", skip_orphan)
    entries = [belief("k.ok"), belief("k.orphan")]
    out = stdio(svc, "note", {**TAGS, "beliefs": entries})
    assert out["beliefs_recorded"] == 0
    assert "FOREIGN KEY constraint failed" in out["belief_errors"][0]
    assert store_count(svc)["assertions"] == 0

    monkeypatch.setattr(BeliefStore, "_belief", real)  # control: the sibling succeeds
    out = stdio(svc, "note", {**TAGS, "beliefs": entries})
    assert out["beliefs_recorded"] == 2 and store_count(svc)["assertions"] == 2


# ================================================================ 5. dedupe (F14, F15)


def nick_check(svc, monkeypatch):
    freeze(monkeypatch, T12)
    check = belief(
        "nick.price_sheet.sent", observed_at=T12, source_ref="gmail:sent:abc"
    )
    svc.ingest("checked the sent folder", {"beliefs": [check]})


def nick_note(svc, monkeypatch, minute):
    obs = f"2026-10-14T15:{minute:02d}:00Z"
    freeze(monkeypatch, obs)
    note = belief(
        "nick.price_sheet.sent", value=False, source_type="reported", observed_at=obs
    )
    out = svc.ingest(f"price sheet still unsent ({minute})", {"beliefs": [note]})
    assert out["beliefs"] == {"recorded": 1, "errors": []}


def test_duplicate_source_counted_once(tmp_path, monkeypatch):
    want = sigmoid(
        a95 * 2 ** (-(3.5 / 24) / 14) - a7 * 2 ** (-(0.5 / 24) / 14)
    )  # 0.888631
    now = "2026-10-14T15:30:00Z"
    one, four = service(tmp_path / "one"), service(tmp_path / "four")
    nick_check(one, monkeypatch)
    nick_note(one, monkeypatch, 0)
    nick_check(four, monkeypatch)
    for minute in (0, 10, 20, 30):
        nick_note(four, monkeypatch, minute)
    p_one = one._belief_store.probability("nick.price_sheet.sent", now)
    p_four = four._belief_store.probability("nick.price_sheet.sent", now)
    assert math.isclose(want, 0.888631, abs_tol=1e-6)
    assert math.isclose(p_one, want, abs_tol=1e-9)
    assert math.isclose(p_four, want, abs_tol=1e-9)
    assert len(four._belief_store.mentions("nick.price_sheet.sent")) == 5


def test_independent_sources_still_count(tmp_path, monkeypatch):
    """Control F15: distinct refs and distinct reporters are distinct sources."""
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    for ref in ("gmail:sent:a", "gmail:sent:b"):
        svc.ingest("check", {"beliefs": [belief("k.two", kind="fact", source_ref=ref)]})
    assert math.isclose(
        svc._belief_store.probability("k.two", T15), 0.997238, abs_tol=1e-6
    )

    svc.ingest("check", {"beliefs": [belief("k.four", source_ref="gmail:sent:c")]})
    for who in ("alice", "bob", "carol", "dave"):
        note = belief("k.four", value=False, source_type="reported")
        svc.ingest("said so", {"who": who, "beliefs": [note]})
    assert math.isclose(
        svc._belief_store.probability("k.four", T15), 0.390609, abs_tol=1e-6
    )


# ================================================================ 6. mentions (P1-P4)


def located(svc, key):
    return [loc for _, _, loc in svc._belief_store.mentions(key)]


def by_chunk(svc, out, key):
    """located flags in chunk order of this memory."""
    flags = dict(
        svc._belief_store._conn()
        .execute("SELECT chunk_id, located FROM assertions WHERE belief_key=?", (key,))
        .fetchall()
    )
    return [flags[c] for c in out["chunk_ids"]]


def note_entry(key, **kw):
    return belief(key, value=False, source_type="reported", observed_at=T12, **kw)


def test_mentions_multi_chunk_and_external_ref(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    p1 = svc.ingest(
        THREE, {"beliefs": [note_entry("k.p1", quote="price sheet still  UNSENT")]}
    )
    p2 = svc.ingest(THREE, {"beliefs": [note_entry("k.p2")]})
    p3 = svc.ingest(THREE, {"beliefs": [note_entry("k.p3", quote="pricing deck")]})
    p4 = svc.ingest("price sheet still unsent", {"beliefs": [note_entry("k.p4")]})
    assert p1["chunks_stored"] == 3
    assert by_chunk(svc, p1, "k.p1") == [0, 1, 0]
    assert by_chunk(svc, p2, "k.p2") == [0, 0, 0]
    assert by_chunk(svc, p3, "k.p3") == [0, 0, 0]
    assert by_chunk(svc, p4, "k.p4") == [1]
    assert p1["beliefs"]["errors"] == [] and p2["beliefs"]["errors"] == []
    assert p3["beliefs"] == {"recorded": 1, "errors": ["k.p3: quote not found"]}
    # the three P1 rows are one source (three would give three times the llr)
    one = sigmoid(-a7 * 2 ** (-(3 / 24) / 14))
    assert math.isclose(svc._belief_store.probability("k.p1", T15), one, abs_tol=1e-9)

    # A later witnessed check supersedes the note: the chunks it would flag as
    # outdated are the located ones only (find_holes itself is B-PR4).
    for key in ("k.p1", "k.p2"):
        svc.ingest(
            "checked", {"beliefs": [belief(key, source_ref=f"gmail:sent:{key}")]}
        )
        assert math.isclose(svc._belief_store.probability(key, T15), 0.95, abs_tol=1e-9)
    superseded = "SELECT chunk_id FROM assertions WHERE belief_key=? AND polarity=-1 AND located=1"
    conn = svc._belief_store._conn()
    assert [c for (c,) in conn.execute(superseded, ("k.p1",))] == [p1["chunk_ids"][1]]
    assert conn.execute(superseded, ("k.p2",)).fetchall() == []

    ref = svc.ingest(
        THREE,
        {
            "beliefs": [
                note_entry("k.ref", quote="price sheet", source_ref="gmail:sent:x")
            ]
        },
    )
    got = conn.execute(
        "SELECT chunk_id, source_id FROM assertions WHERE belief_key='k.ref' AND located=1"
    ).fetchall()
    assert got == [(ref["chunk_ids"][1], "gmail:sent:x")]


# ================================================================ 6b. half-life defaults


@pytest.mark.parametrize(
    "key, kind, observed, extra, want",
    [
        ("f2.omitted", "state", "2026-09-30T15:00:00Z", {}, 0.75),
        ("f2n.null", "state", "2026-09-30T15:00:00Z", {"half_life_days": None}, 0.75),
        (
            "f2o.override",
            "state",
            "2026-09-30T15:00:00Z",
            {"half_life_days": 7},
            sigmoid(a9 / 4),
        ),
        ("f2p.plan", "plan", "2026-09-14T15:00:00Z", {}, 0.75),
        ("f2f.fact", "fact", "2025-10-14T15:00:00Z", {}, 0.75),
    ],
)
def test_half_life_defaults(tmp_path, monkeypatch, key, kind, observed, extra, want):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    entry = belief(key, kind=kind, observed_at=observed, reliability=0.9, **extra)
    assert svc.ingest("old check", {"beliefs": [entry]})["beliefs"]["recorded"] == 1
    assert math.isclose(svc._belief_store.probability(key, T15), want, abs_tol=1e-6)


# ================================================================ because and edges


def test_because_adds_depends_on_from_every_belief(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    entries = [
        belief("k.a", supports=["k.s"], excludes=["k.x"]),
        belief("k.b", depends_on=["k.d"]),
    ]
    out = svc.ingest("note", {"beliefs": entries, "because": ["k.base"]})
    assert out["beliefs"] == {"recorded": 2, "errors": []}
    assert rows(svc, "SELECT src, dst, type, weight FROM edges") == [
        ("k.a", "k.base", "depends_on", 0.5),
        ("k.a", "k.s", "supports", 0.5),
        ("k.a", "k.x", "excludes", 0.5),
        ("k.b", "k.base", "depends_on", 0.5),
        ("k.b", "k.d", "depends_on", 0.5),
    ]
    assert svc._belief_store.attrs("k.base")["claim"] == "k.base"  # placeholder


def test_conflicting_edge_rejects_only_that_entry(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    entries = [
        belief("k.a", supports=["k.b"]),
        belief("k.c"),
        belief("k.b", excludes=["k.a"]),
    ]
    out = svc.ingest("note", {"beliefs": entries})
    assert out["beliefs"]["recorded"] == 2
    assert out["beliefs"]["errors"] == [
        "k.b: supports and excludes on one pair (k.b, k.a)"
    ]
    assert (
        not svc._belief_store._conn()
        .execute("SELECT 1 FROM assertions WHERE belief_key='k.b'")
        .fetchone()
    )


def test_because_without_beliefs_is_reported(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    out = svc.ingest("note", {"because": ["k.base"]})
    assert out["beliefs"] == {
        "recorded": 0,
        "errors": ["beliefs: because needs at least one belief"],
    }


def test_ingest_switch_off_records_nothing(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    svc._beliefs_enabled = False
    out = svc.ingest("note", {"beliefs": [belief("k.a")]})
    assert out["success"] is True
    assert out["beliefs"]["recorded"] == 0
    assert "disabled" in out["beliefs"]["errors"][0]
    assert store_count(svc)["assertions"] == 0


# ================================================================ backward compatibility


def test_no_beliefs_response_unchanged_and_no_tables(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    monkeypatch.delenv("MEMORY_MCP_PROJECT", raising=False)
    kv = KVStore(str(tmp_path / "agent_kv.db"))
    svc = service(tmp_path, own_store=False, kv_store=kv)
    result = svc.ingest("plain memory", dict(TAGS))
    assert set(result) == MAIN_RESULT_KEYS

    out = stdio(svc, "plain memory", dict(TAGS))
    assert set(out) == {"content", "isError", "tags_auto_filled"}
    assert out["content"][0]["text"] == (
        "Stored memory: plain memory...\nTagged: WHO=unknown, PROJECT=p\n"
        f"Lifecycle: hot\nChunks: {out['content'][0]['text'].rsplit(' ', 1)[1]}"
    )
    body = http(svc, monkeypatch, "plain memory", dict(TAGS))
    assert set(body) == MAIN_RESULT_KEYS | {"tags_auto_filled"}
    tables = sqlite3.connect(str(tmp_path / "agent_kv.db")).execute(
        "SELECT name FROM sqlite_master WHERE name IN ('beliefs', 'assertions', 'belief_seq')"
    )
    assert tables.fetchall() == []
    kv.close()


def test_beliefs_open_store_next_to_kv(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    kv = KVStore(str(tmp_path / "agent_kv.db"))
    svc = service(tmp_path, own_store=False, kv_store=kv)
    out = svc.ingest("note", {"beliefs": [belief("k.a")]})
    assert out["beliefs"] == {"recorded": 1, "errors": []}
    assert svc._belief_store.db_path == kv.db_path
    kv.close()


# ================================================================ review r1


def test_malformed_source_type_rejects_only_that_entry(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    for i, bad in enumerate(([], {}, 7)):
        entries = [belief(f"k.ok{i}"), belief(f"k.bad{i}", source_type=bad)]
        out = stdio(svc, "note", {**TAGS, "beliefs": entries})
        assert out["beliefs_recorded"] == 1
        assert out["belief_errors"] == [f"k.bad{i}: bad source_type {bad!r}"]
    body = http(svc, monkeypatch, "note", {**TAGS, "beliefs": entries[::-1]})
    assert body["beliefs"] == {"recorded": 1, "errors": ["k.bad2: bad source_type 7"]}
    assert [k for (k,) in rows(svc, "SELECT DISTINCT belief_key FROM assertions")] == [
        "k.ok0",
        "k.ok1",
        "k.ok2",
    ]


@pytest.mark.parametrize("bad", [False, 0, "", [], {}, None])
def test_supplied_observed_at_is_validated(tmp_path, monkeypatch, bad):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    entries = [belief("k.bad", observed_at=bad), belief("k.ok")]  # k.ok: omitted
    out = svc.ingest("note", {"beliefs": entries})
    assert out["beliefs"]["recorded"] == 1
    assert out["beliefs"]["errors"][0].startswith("k.bad: ")
    assert "timestamp" in out["beliefs"]["errors"][0]
    got = rows(svc, "SELECT belief_key, observed_at FROM assertions")
    assert got == [("k.ok", "2026-10-14T15:00:00.000000Z")]


def test_merge_keeps_links_with_the_winning_claim(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    vectors = {"old claim": [1.0], "new claim": [2.0]}
    svc._embedder.encode.side_effect = lambda texts: [vectors[texts[0]]]
    svc._entity_service.extract_entities.side_effect = lambda t: [{"text": t}]
    for key, claim in (("k.old", "old claim"), ("k.new", "new claim")):
        entry = {**belief(key), "claim": claim}
        assert svc.ingest(claim, {"beliefs": [entry]})["beliefs"]["recorded"] == 1
    svc._belief_store.merge("k.old", "k.new", "merge:m1")
    got = (
        svc._belief_store._conn()
        .execute(
            "SELECT claim, entities, claim_vec FROM beliefs WHERE origin='live' AND key='k.new'"
        )
        .fetchone()
    )
    assert got == ("old claim", '["old claim"]', array("f", [1.0]).tobytes())


def test_structured_errors_are_capped(tmp_path, monkeypatch):
    freeze(monkeypatch, T15)
    svc = service(tmp_path)
    out = svc.ingest("note", {"beliefs": [belief("K." + "x" * 20000)]})
    errors = out["beliefs"]["errors"]
    assert len(errors) == 1 and len(errors[0]) == 500
