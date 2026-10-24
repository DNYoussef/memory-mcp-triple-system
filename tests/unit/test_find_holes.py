"""
find_holes and lifecycle_status belief counts (PLAN-B sections 5.2, 6.2 B-PR4).

One positive and one negative fixture per hole kind (F3, F3a, F9, F10, F12,
F13, F16 and a stale case), the located/unlocated mention rule of section
4.1, ranking, filters, and the read-only contract: both tools read through
the read-only store and write nothing, also while a writer process holds the
database mid-WAL. Calls go through handle_call_tool, as the MCP server does.
"""

import hashlib
import json
import math
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.belief_web.belief_store import BeliefStore
from src.belief_web.solver import logit, sigmoid
from src.mcp.request_router import handle_call_tool

T12, T15 = "2026-10-14T12:00:00Z", "2026-10-14T15:00:00Z"
a9, a95, a7, a8, a6 = logit(0.9), logit(0.95), logit(0.7), logit(0.8), logit(0.6)
TABLES = ("belief_seq", "beliefs", "assertions", "edges", "aliases")
KINDS = (
    "contradicted",
    "outdated_memory",
    "contradicted_pair",
    "stale",
    "unsupported",
    "weak_load_bearing",
)
STATS = {"active": 3, "demoted": 1, "archived": 0, "rehydratable": 0, "total": 4}


@pytest.fixture
def db(tmp_path):
    return tmp_path / "agent_kv.db"


@pytest.fixture
def store(db):
    s = BeliefStore(str(db))
    yield s
    s.close()


@pytest.fixture
def tool(db):
    manager = MagicMock()
    manager.get_stage_stats.return_value = dict(STATS)
    yield SimpleNamespace(
        config={}, kv_store=SimpleNamespace(db_path=db), lifecycle_manager=manager
    )


def write(s, key, pol, st, obs, chunk, rec=None, located=1, **kw):
    s.add_assertion(
        "live",
        key,
        polarity=pol,
        source_type=st,
        observed_at=obs,
        recorded_at=rec or obs,
        chunk_id=chunk,
        located=located,
        claim=kw.pop("claim", f"{key} holds"),
        **kw,
    )


def call(tool, name, **arguments):
    out = handle_call_tool(
        name, {"now": T15, **arguments} if name == "find_holes" else arguments, tool
    )
    text = out["content"][0]["text"]
    try:
        return json.loads(text), out["isError"]
    except ValueError:
        return {"text": text}, out["isError"]


def holes(tool, **arguments):
    payload, is_error = call(tool, "find_holes", **arguments)
    assert is_error is False, payload
    return payload


def of(payload, hole, key):
    found = [h for h in payload["holes"] if h["hole"] == hole and h.get("key") == key]
    return found[0] if found else None


# ================================================================ contradicted (F3, F9)


def test_contradicted_lists_the_disputed_side_only(store, tool):
    write(
        store,
        "nick.price_sheet.sent",
        1,
        "witnessed",
        T12,
        "check",
        source_ref="gmail:sent:a",
    )
    write(store, "nick.price_sheet.sent", -1, "reported", T15, "note")
    payload = holes(tool)
    h = of(payload, "contradicted", "nick.price_sheet.sent")
    assert math.isclose(h["p"], 0.888843, abs_tol=1e-6)
    (src,) = h["disputed_sources"]
    assert (src["source_id"], src["polarity"], src["chunks"]) == (
        "testimony:unknown:-1",
        -1,
        ["note"],
    )
    assert of(payload, "outdated_memory", "nick.price_sheet.sent") is None


def test_tie_is_contradicted_with_both_sides(store, tool):
    write(
        store, "k.tie", 1, "witnessed", T15, "c1", source_ref="ref:a", reliability=0.9
    )
    write(
        store, "k.tie", -1, "witnessed", T15, "c2", source_ref="ref:b", reliability=0.9
    )
    h = of(holes(tool), "contradicted", "k.tie")
    assert math.isclose(h["p"], 0.5, abs_tol=1e-12)
    assert sorted(s["chunks"][0] for s in h["disputed_sources"]) == ["c1", "c2"]


def test_one_sided_or_weak_evidence_is_not_contradicted(store, tool):
    write(store, "k.one", 1, "witnessed", T15, "c1")  # F1-like, one side
    write(store, "k.weak", 1, "witnessed", T15, "c2", source_ref="ref:w")
    write(
        store, "k.weak", -1, "assumed", T15, "c3", reliability=0.55
    )  # |llr| 0.2 < 0.4
    payload = holes(tool)
    assert of(payload, "contradicted", "k.one") is None
    assert of(payload, "contradicted", "k.weak") is None


# ================================================================ outdated_memory (F3a, F16)


def test_superseded_note_is_outdated_not_contradicted(store, tool):
    write(store, "k.note", -1, "reported", T12, "note")
    write(store, "k.note", 1, "witnessed", T15, "check", source_ref="gmail:sent:b")
    payload = holes(tool)
    h = of(payload, "outdated_memory", "k.note")
    assert math.isclose(h["p"], 0.95, abs_tol=1e-9)
    (src,) = h["outdated_sources"]
    assert src["chunks"] == ["note"] and src["memory_refs"] == []
    assert src["note"] == (
        "superseded by a newer check on 2026-10-14; may have been true when written"
    )
    assert of(payload, "contradicted", "k.note") is None


def test_state_transition_marks_yesterday_outdated(store, tool):  # F16
    write(
        store,
        "k.live",
        -1,
        "witnessed",
        "2026-10-13T15:00:00Z",
        "yesterday",
        source_ref="chk:1",
    )
    write(store, "k.live", 1, "witnessed", T15, "today", source_ref="chk:2")
    payload = holes(tool)
    h = of(payload, "outdated_memory", "k.live")
    assert math.isclose(h["p"], 0.95, abs_tol=1e-9)
    assert [s["chunks"] for s in h["outdated_sources"]] == [["yesterday"]]
    assert of(payload, "contradicted", "k.live") is None


def test_unlocated_mention_is_a_memory_ref_not_a_chunk(store, tool):
    write(store, "k.note", -1, "reported", T12, "chunk-a", located=0)
    write(store, "k.note", -1, "reported", T12, "chunk-b", located=0)
    write(store, "k.note", 1, "witnessed", T15, "check", source_ref="gmail:sent:b")
    (src,) = of(holes(tool), "outdated_memory", "k.note")["outdated_sources"]
    assert src["chunks"] == [] and src["memory_refs"] == ["chunk-a", "chunk-b"]


def test_fact_has_no_supersession_so_nothing_is_outdated(store, tool):
    write(store, "k.fact", -1, "reported", T12, "note", kind="fact", half_life_days=14)
    write(store, "k.fact", 1, "witnessed", T15, "check", source_ref="gmail:sent:c")
    payload = holes(tool)
    assert of(payload, "outdated_memory", "k.fact") is None
    assert of(payload, "contradicted", "k.fact") is not None  # both sides stay active


def test_superseded_evidence_of_the_same_sign_is_not_outdated(store, tool):
    write(store, "k.agree", 1, "reported", T12, "note")
    write(store, "k.agree", 1, "witnessed", T15, "check", source_ref="gmail:sent:d")
    assert of(holes(tool), "outdated_memory", "k.agree") is None


# ================================================================ contradicted_pair (F12)


def test_excludes_pair_both_evidenced_is_contradicted_pair(store, tool):
    write(store, "k.a", 1, "witnessed", T15, "ca", reliability=0.9)
    write(store, "k.b", 1, "witnessed", T15, "cb", reliability=0.8)
    store.add_edge("live", "k.a", "k.b", "excludes", 0.5)
    (h,) = [x for x in holes(tool)["holes"] if x["hole"] == "contradicted_pair"]
    assert h["keys"] == ["k.a", "k.b"]
    assert math.isclose(h["p"][0], sigmoid(a9 - 0.6), abs_tol=1e-6)  # 0.8316
    assert math.isclose(h["p"][1], sigmoid(a8 - 0.8), abs_tol=1e-6)  # 0.6425


def test_strong_belief_excluding_an_unevidenced_one_is_not_a_pair(store, tool):
    """F5: A 0.9 excludes B with no evidence on B gives 0.90 + 0.31 = 1.21 > 1.1,
    yet B only leans false. Both sides must lean true (plan predicate fix)."""
    write(store, "k.a", 1, "witnessed", T15, "ca", reliability=0.9)
    store.add_edge("live", "k.a", "k.b", "excludes", 0.5)
    payload = holes(tool)
    assert not [x for x in payload["holes"] if x["hole"] == "contradicted_pair"]
    assert payload["counts"]["contradicted_pair"] == 0


def test_project_filter_keeps_the_pair_load_and_rank(store, tool):
    write(store, "k.a", 1, "witnessed", T15, "ca", reliability=0.9)
    write(store, "k.b", 1, "witnessed", T15, "cb", reliability=0.8)
    store.link("live", "k.b", "k.b holds", project="alpha")
    store.add_edge("live", "k.a", "k.b", "excludes", 0.5)
    for child in ("k.c1", "k.c2", "k.c3"):
        store.add_edge("live", "k.a", child, "supports", 0.5)

    def pair(**kw):
        (h,) = [
            x for x in holes(tool, **kw)["holes"] if x["hole"] == "contradicted_pair"
        ]
        return h["load"], h["rank"]

    assert pair()[0] == 3
    assert pair(project="alpha") == pair()  # k.a is outside the filter


def test_weak_excludes_pair_is_not(store, tool):
    write(store, "k.a", 1, "inferred", T15, "ca")  # 0.6, no evidence on k.b
    store.add_edge("live", "k.a", "k.b", "excludes", 0.5)
    payload = holes(tool)
    assert not [x for x in payload["holes"] if x["hole"] == "contradicted_pair"]
    assert payload["counts"]["contradicted_pair"] == 0


# ================================================================ stale


def test_stale_when_newest_active_evidence_is_past_the_half_life(store, tool):
    write(
        store, "k.old", 1, "witnessed", "2026-09-24T15:00:00Z", "c1"
    )  # 20 days, state 14
    write(store, "k.recent", 1, "witnessed", "2026-10-04T15:00:00Z", "c2")  # 10 days
    write(store, "k.fact", 1, "witnessed", "2026-09-24T15:00:00Z", "c3", kind="fact")
    payload = holes(tool)
    h = of(payload, "stale", "k.old")
    assert (h["age_days"], h["half_life_days"]) == (20.0, 14.0)
    assert of(payload, "stale", "k.recent") is None
    assert of(payload, "stale", "k.fact") is None  # 365-day half-life


def test_stale_reads_the_newest_evidence_and_the_effective_half_life(store, tool):
    write(store, "k.mixed", 1, "reported", "2026-09-24T15:00:00Z", "c1", who="alice")
    write(store, "k.mixed", 1, "reported", "2026-10-12T15:00:00Z", "c2", who="bob")
    write(
        store, "k.long", 1, "witnessed", "2026-09-24T15:00:00Z", "c3", half_life_days=30
    )
    payload = holes(tool)
    assert of(payload, "stale", "k.mixed") is None  # newest is 2 days old
    assert of(payload, "stale", "k.long") is None  # 20 days < 30


# ================================================================ unsupported (F13)


def test_placeholder_without_evidence_is_unsupported(store, tool):
    write(store, "k.a", 1, "witnessed", T15, "c1")
    store.add_edge("live", "k.a", "k.empty", "depends_on", 0.5)
    payload = holes(tool)
    h = of(payload, "unsupported", "k.empty")
    assert h["claim"] == "k.empty" and math.isclose(h["p"], 0.5, abs_tol=1e-12)
    assert of(payload, "unsupported", "k.a") is None


def test_weak_but_real_evidence_is_not_unsupported(store, tool):
    write(store, "k.assumed", 1, "assumed", T15, "c1")  # |llr| 0.2
    assert of(holes(tool), "unsupported", "k.assumed") is None


# ================================================================ weak_load_bearing (F10)


def test_single_inferred_source_carrying_load_is_weak(store, tool):
    write(store, "k.x", 1, "inferred", T15, "cx")
    for child in ("k.y", "k.z", "k.w"):
        store.add_edge("live", "k.x", child, "supports", 0.8)
    payload = holes(tool)
    h = of(payload, "weak_load_bearing", "k.x")
    assert h["load"] == 3 and h["single_source"] is True
    assert math.isclose(h["p"], 0.6, abs_tol=1e-9)
    assert math.isclose(h["rank"], 4 * (1 - abs(2 * 0.6 - 1)), abs_tol=1e-9)
    assert of(payload, "weak_load_bearing", "k.y") is None  # load 0
    assert of(holes(tool, min_load=4), "weak_load_bearing", "k.x") is None


def test_load_follows_supports_and_depends_on_to_depth_five(store, tool):
    write(store, "k.base", 1, "inferred", T15, "cb")
    chain = ["k.base", "k.n1", "k.n2", "k.n3", "k.n4", "k.n5", "k.n6"]
    for a, b in zip(chain, chain[1:]):
        store.add_edge("live", b, a, "depends_on", 0.5)  # b rests on a
    assert of(holes(tool), "weak_load_bearing", "k.base")["load"] == 5  # n6 is depth 6


def test_well_evidenced_load_is_not_weak(store, tool):
    write(store, "k.x", 1, "witnessed", T15, "c1", source_ref="ref:1")
    write(store, "k.x", 1, "witnessed", T15, "c2", source_ref="ref:2")
    for child in ("k.y", "k.z", "k.w"):
        store.add_edge("live", "k.x", child, "supports", 0.8)
    assert of(holes(tool), "weak_load_bearing", "k.x") is None


def test_uncertain_load_is_weak_even_with_several_sources(store, tool):
    write(store, "k.x", 1, "inferred", T15, "c1", who="alice")
    write(store, "k.x", 1, "inferred", T15, "c2", who="bob")  # p 0.69, two sources
    for child in ("k.y", "k.z"):
        store.add_edge("live", "k.x", child, "supports", 0.5)
    h = of(holes(tool), "weak_load_bearing", "k.x")
    assert h["single_source"] is False and 0.3 <= h["p"] <= 0.7


def test_single_witnessed_source_carrying_load_is_not_weak(store, tool):
    write(store, "k.x", 1, "witnessed", T15, "c1")  # p 0.95, one witnessed source
    for child in ("k.y", "k.z"):
        store.add_edge("live", "k.x", child, "supports", 0.5)
    assert of(holes(tool), "weak_load_bearing", "k.x") is None


# ================================================================ ranking and filters


def test_rank_orders_holes_and_ties_put_contradicted_first(store, tool):
    write(
        store, "z.tie", 1, "witnessed", T15, "c1", source_ref="ref:a", reliability=0.9
    )
    write(
        store, "z.tie", -1, "witnessed", T15, "c2", source_ref="ref:b", reliability=0.9
    )
    store.add_edge(
        "live", "z.tie", "a.empty", "excludes", 0.5
    )  # a.empty: unsupported, p 0.5
    write(store, "k.x", 1, "inferred", T15, "cx")
    for child in ("k.y", "k.z", "k.w"):
        store.add_edge("live", "k.x", child, "supports", 0.8)
    order = [(h["hole"], h.get("key")) for h in holes(tool)["holes"]]
    assert order[0] == ("weak_load_bearing", "k.x")  # rank 3.2
    assert order.index(("contradicted", "z.tie")) < order.index(
        ("unsupported", "a.empty")
    )


def test_filters_and_counts(store, tool):
    write(store, "k.old", 1, "witnessed", "2026-09-24T15:00:00Z", "c1")
    write(store, "k.p1", 1, "witnessed", "2026-09-24T15:00:00Z", "c2")
    store.link("live", "k.p1", "k.p1 holds", project="alpha")
    store.add_edge("live", "k.old", "k.empty", "depends_on", 0.5)
    everything = holes(tool)
    assert (
        everything["counts"]["stale"] == 2 and everything["counts"]["unsupported"] == 1
    )
    only = holes(tool, kinds=["stale"], limit=1)
    assert [h["hole"] for h in only["holes"]] == ["stale"]
    assert only["counts"] == everything["counts"]  # counts ignore kinds and limit
    alpha = holes(tool, project="alpha")
    assert {h["key"] for h in alpha["holes"]} == {"k.p1"} and alpha["beliefs"] == 1


def test_provenance_lists_are_capped_with_omitted_counts(store, tool):
    with store.batch():
        for i in range(2000):  # one memory note copied into 2000 unlocated chunks
            write(store, "k.note", -1, "reported", T12, f"chunk-{i:04d}", located=0)
        write(store, "k.note", 1, "witnessed", T15, "check", source_ref="gmail:sent:e")
    out = handle_call_tool("find_holes", {"now": T15, "limit": 1}, tool)
    assert len(out["content"][0]["text"]) < 10_000  # was about 36 KB per 2k refs
    (h,) = json.loads(out["content"][0]["text"])["holes"]
    (src,) = h["outdated_sources"]
    assert len(src["memory_refs"]) == 20 and src["memory_refs_omitted"] == 1980
    assert src["chunks"] == [] and src["chunks_omitted"] == 0
    assert h["sources_omitted"] == 0


def test_disputed_sources_are_capped(store, tool):
    for ref in ("gmail:sent:f", "gmail:sent:g"):  # winning side: 2 x 2.944
        write(store, "k.x", 1, "witnessed", T15, ref, source_ref=ref)
    write(store, "k.x", -1, "inferred", T15, "n0", who="who0")  # 0.405 >= 0.4
    for i in range(1, 26):  # 25 more distinct reporters, 0.2 each
        write(store, "k.x", -1, "assumed", T15, f"n{i}", who=f"who{i}")
    h = of(holes(tool), "contradicted", "k.x")
    assert h["p"] > 0.5  # so the 26 negative sources are the disputed side
    assert len(h["disputed_sources"]) == 20 and h["sources_omitted"] == 6


def test_response_size_is_capped(store, tool):
    from src.belief_web.holes import MAX_BYTES

    with store.batch():
        for i in range(100):
            write(store, f"k.s{i:03d}", 1, "witnessed", "2026-09-24T15:00:00Z", f"c{i}",
                  claim=f"claim {i} " + "x" * 2000)  # fmt: skip
    payload = holes(tool, limit=200)
    assert len(json.dumps(payload["holes"])) <= MAX_BYTES
    assert payload["omitted"]["by_size"] > 0 and payload["omitted"]["by_limit"] == 0
    assert len(payload["holes"]) + payload["omitted"]["by_size"] == 100
    assert payload["counts"]["stale"] == 100


@pytest.mark.parametrize(
    "arguments, message",
    [
        ({"kinds": ["nope"]}, "kinds must be"),
        ({"kinds": []}, "kinds must be"),
        ({"limit": 0}, "limit must be"),
        ({"min_load": True}, "min_load must be"),
        ({"project": 3}, "project must be text"),
        ({"now": "soon"}, "unparseable timestamp"),
    ],
)
def test_bad_arguments(tool, arguments, message):
    payload, is_error = call(tool, "find_holes", **arguments)
    assert is_error is True and message in payload["error"]


def test_find_holes_is_registered():
    from src.mcp.tool_registry import _find_holes_tool, get_tool_definitions

    assert "find_holes" in {t["name"] for t in get_tool_definitions()}
    enum = _find_holes_tool()["inputSchema"]["properties"]["kinds"]["items"]["enum"]
    assert tuple(enum) == KINDS


# ================================================================ lifecycle_status counts


def test_lifecycle_status_adds_belief_counts(store, tool):
    write(store, "k.note", -1, "reported", T12, "n1", located=0)
    write(store, "k.note", -1, "reported", T12, "n2", located=0)
    write(store, "k.note", 1, "witnessed", T15, "check", source_ref="gmail:sent:b")
    store.add_edge("live", "k.note", "k.empty", "depends_on", 0.5)
    payload, is_error = call(tool, "lifecycle_status")
    assert is_error is False
    assert {k: payload[k] for k in STATS} == STATS  # the old stats, unchanged
    beliefs = payload["beliefs"]
    assert (
        beliefs["beliefs"],
        beliefs["evidence"],
        beliefs["mentions"],
        beliefs["edges"],
    ) == (
        2,
        2,
        3,
        1,
    )
    assert set(beliefs["holes"]) == set(KINDS)
    assert (
        beliefs["holes"]["outdated_memory"] == 1
        and beliefs["holes"]["unsupported"] == 1
    )


def test_lifecycle_counts_and_holes_come_from_one_snapshot(store, tool, monkeypatch):
    """A commit between two snapshots gave beliefs 0 with unsupported 1."""
    real, calls = BeliefStore.web, []

    def web(self, now, *a, **kw):
        snap = real(self, now, *a, **kw)
        calls.append(1)
        if len(calls) == 1:  # another writer commits right after the first read
            store.add_edge("live", "k.a", "k.b", "supports", 0.5)
        return snap

    monkeypatch.setattr(BeliefStore, "web", web)
    payload, is_error = call(tool, "lifecycle_status")
    assert is_error is False and len(calls) == 1
    assert payload["beliefs"]["beliefs"] == 0
    assert payload["beliefs"]["holes"] == {k: 0 for k in KINDS}


def test_lifecycle_counts_failure_keeps_stats(tool, monkeypatch):
    from src.mcp import request_router

    def boom(_tool):
        raise RuntimeError("disk gone")

    monkeypatch.setattr(request_router, "_belief_reader", boom)
    payload, is_error = call(tool, "lifecycle_status")
    assert is_error is False
    assert {k: payload[k] for k in STATS} == STATS
    assert payload["beliefs"] == {"error": "belief counts failed: disk gone"}


# ================================================================ read-only


def test_first_read_without_tables_writes_nothing(tmp_path):
    from src.stores.kv_store import KVStore

    db = tmp_path / "agent_kv.db"
    KVStore(str(db)).close()
    missing = tmp_path / "absent" / "agent_kv.db"
    for path in (db, missing):
        manager = MagicMock()
        manager.get_stage_stats.return_value = dict(STATS)
        t = SimpleNamespace(
            config={}, kv_store=SimpleNamespace(db_path=path), lifecycle_manager=manager
        )
        payload = holes(t)
        assert payload["holes"] == [] and payload["beliefs"] == 0
        assert payload["counts"] == {k: 0 for k in KINDS}
        counts, _ = call(t, "lifecycle_status")
        assert counts["beliefs"]["beliefs"] == 0
    assert not missing.parent.exists()
    c = sqlite3.connect(str(db))
    names = {n for (n,) in c.execute("SELECT name FROM sqlite_master")}
    c.close()
    assert not names & set(TABLES)


WAL_WRITER = """
import sys
sys.path.insert(0, sys.argv[1])
from src.belief_web.belief_store import BeliefStore

store = BeliefStore(sys.argv[2])
for pol, st, obs, chunk, ref in ((-1, "reported", sys.argv[3], "note", None),
                                 (1, "witnessed", sys.argv[4], "check", "gmail:sent:w")):
    store.add_assertion("live", "k.wal", polarity=pol, source_type=st, observed_at=obs,
                        recorded_at=obs, chunk_id=chunk, source_ref=ref, claim="k.wal holds")
print("READY", flush=True)
sys.stdin.readline()  # hold the connection: no close, so no checkpoint
"""


def test_reads_mid_wal_from_a_writer_process_write_nothing(tmp_path):
    db = tmp_path / "dir with space #1" / "agent_kv.db"
    wal = db.with_name(db.name + "-wal")
    root = str(Path(__file__).resolve().parents[2])
    writer = subprocess.Popen(
        [sys.executable, "-c", WAL_WRITER, root, str(db), T12, T15],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    manager = MagicMock()
    manager.get_stage_stats.return_value = dict(STATS)
    t = SimpleNamespace(
        config={}, kv_store=SimpleNamespace(db_path=db), lifecycle_manager=manager
    )
    try:
        assert writer.stdout.readline().strip() == "READY", writer.stderr.read()
        assert wal.exists() and wal.stat().st_size > 0

        def snapshot():
            c = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                rows = {
                    t_: sorted(c.execute(f"SELECT * FROM {t_}").fetchall(), key=repr)
                    for t_ in TABLES
                }
            finally:
                c.close()
            return (
                hashlib.sha256(db.read_bytes()).hexdigest(),
                wal.stat().st_size,
                hashlib.sha256(repr(rows).encode()).hexdigest(),
            )

        before = snapshot()
        h = of(holes(t), "outdated_memory", "k.wal")
        assert h["outdated_sources"][0]["chunks"] == ["note"]
        counts, _ = call(t, "lifecycle_status")
        assert counts["beliefs"]["beliefs"] == 1 and counts["beliefs"]["mentions"] == 2
        assert snapshot() == before
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            t._belief_reader._conn().execute("UPDATE belief_seq SET n = n")
        assert snapshot() == before and writer.poll() is None
    finally:
        reader = getattr(t, "_belief_reader", None)
        if reader is not None:
            reader.close()
        if writer.poll() is None:
            writer.stdin.close()
            try:
                writer.wait(timeout=30)
            except subprocess.TimeoutExpired:
                writer.kill()
                writer.wait()
