"""
Belief store fixtures (PLAN-B sections 2, 4.4, 6.1, 7).

Ports every store fixture of the reference calculator belief_calc_r8.py
(F14, R1, MR, MB, MC, EW, M1, M2, MX, RD, MD, MT, AE, AM, AI, P1-P4, MI,
AX, AS, AP, UA, SX, HL, RS) plus the validation, FK and atomicity rules the
calculator does not execute. Expected values match the calculator's.
"""

import hashlib
import sqlite3

import pytest

from src.belief_web.belief_store import (
    SEQ_MAX,
    BeliefStore,
    BeliefValidationError,
    SeqExhausted,
    format_ts,
    locate_chunks,
    source_id_for,
)
from src.belief_web.solver import EdgeConflict, logit, sigmoid
from src.stores.kv_store import KVStore

T12, T15 = "2026-10-14T12:00:00Z", "2026-10-14T15:00:00Z"
OLD14 = "2026-09-30T15:00:00Z"
a9, a95, a7 = logit(0.9), logit(0.95), logit(0.7)
A7_3H = sigmoid(a7 * 2 ** (-(3 / 24) / 14))
FACT14 = sigmoid(a9 * 2 ** (-14 / 365))  # 0.894691
HL7 = sigmoid(a9 * 2 ** (-14 / 7))  # 0.633975
HL30 = sigmoid(a9 * 2 ** (-14 / 30))
BELIEF_TABLES = ("belief_seq", "beliefs", "assertions", "edges", "aliases")


@pytest.fixture
def db(tmp_path):
    return tmp_path / "agent_kv.db"


@pytest.fixture
def store(db):
    s = BeliefStore(str(db))
    yield s
    s.close()


def write(
    s,
    origin,
    name,
    pol,
    st,
    obs,
    chunk,
    source_ref=None,
    who=None,
    located=1,
    kind=None,
    r=None,
    rec=None,
    claim=None,
    half_life_days=None,
    **extra,
):
    """The calculator's write(): one assertion, recorded_at defaults to observed_at."""
    s.add_assertion(
        origin,
        name,
        polarity=pol,
        source_type=st,
        observed_at=obs,
        recorded_at=rec or obs,
        chunk_id=chunk,
        source_ref=source_ref,
        who=who,
        located=located,
        kind=kind,
        reliability=r,
        claim=claim,
        half_life_days=half_life_days,
        **extra,
    )


def snapshot(db, tables=BELIEF_TABLES):
    c = sqlite3.connect(str(db))
    try:
        return {
            t: sorted(c.execute(f"SELECT * FROM {t}").fetchall(), key=repr)
            for t in tables
        }
    finally:
        c.close()


def table_hash(db, tables):
    return hashlib.sha256(repr(snapshot(db, tables)).encode()).hexdigest()


def close(got, want, tol=1e-9):
    return abs(got - want) < tol


# ================================================================ schema and connection


def test_schema_tables_migration_and_fk(store, db):
    names = {
        r[0]
        for r in sqlite3.connect(str(db)).execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert set(BELIEF_TABLES) <= names
    rows = (
        sqlite3.connect(str(db))
        .execute("SELECT version FROM migrations WHERE version='008'")
        .fetchall()
    )
    assert rows == [("008",)]
    assert store._conn().execute("PRAGMA foreign_keys").fetchone()[0] == 1
    BeliefStore(str(db)).close()  # idempotent re-open keeps the single counter row
    assert (
        sqlite3.connect(str(db))
        .execute("SELECT count(*) FROM belief_seq")
        .fetchone()[0]
        == 1
    )


def test_fk_enforced_on_store_connection(store):
    c = store._conn()
    with pytest.raises(sqlite3.IntegrityError):
        c.execute(
            "INSERT INTO assertions(origin, belief_key, source_id, polarity, source_type,"
            " reliability, observed_at, recorded_at, chunk_id, located, seq)"
            " VALUES('live','no.such','s',1,'reported',0.7,'t','t','c',1,999)"
        )
    write(store, "live", "k.ok", 1, "reported", T15, "c1")  # positive control
    assert store.exists("k.ok")


def test_coexists_with_kvstore_tables(db):
    kv = KVStore(str(db))
    kv.set("pref", "x")
    s = BeliefStore(str(db))
    write(s, "live", "k.a", 1, "reported", T15, "c1")
    assert kv.get("pref") == "x"
    s.close()
    kv.close()


# ================================================================ validation (section 2.5)


@pytest.mark.parametrize(
    "key", ["Bad.Key", "single", "a..b", "a.b.c.d.e.f.g", "a.b-c", "", "a.b "]
)
def test_bad_key_rejected(store, db, key):
    with pytest.raises(BeliefValidationError):
        write(store, "live", key, 1, "reported", T15, "c1")
    assert snapshot(db)["beliefs"] == []


@pytest.mark.parametrize("r", [float("nan"), float("inf"), True, 0.5, 1.0, 0.3, "0.7"])
def test_bad_reliability_rejected(store, db, r):
    with pytest.raises(BeliefValidationError):
        write(store, "live", "k.a", 1, "reported", T15, "c1", r=r)
    assert snapshot(db)["assertions"] == []


@pytest.mark.parametrize("hl", [0, -1, 3651, float("nan"), True])
def test_bad_half_life_rejected(store, hl):
    with pytest.raises(BeliefValidationError):
        write(store, "live", "k.a", 1, "reported", T15, "c1", half_life_days=hl)


@pytest.mark.parametrize(
    "field,value",
    [
        ("pol", 0),
        ("pol", 2),
        ("pol", True),
        ("st", "rumor"),
        ("kind", "opinion"),
        ("chunk", ""),
        ("origin", "Live"),
        ("origin", "import:"),
        ("origin", "foo"),
    ],
)
def test_bad_fields_rejected(store, field, value):
    args = {"origin": "live", "pol": 1, "st": "reported", "kind": None, "chunk": "c1"}
    args[field] = value
    with pytest.raises(BeliefValidationError):
        write(
            store,
            args["origin"],
            "k.a",
            args["pol"],
            args["st"],
            T15,
            args["chunk"],
            kind=args["kind"],
        )


def test_valid_boundaries_accepted(store):
    write(
        store,
        "live",
        "a.b.c.d.e.f",
        1,
        "reported",
        T15,
        "c1",
        r=0.51,
        half_life_days=3650,
    )
    write(store, "import:x-1.2", "k.a", -1, "assumed", T15, "c1", r=0.99, kind="plan")
    store.add_edge("live", "k.a", "k.b", "supports", 1.0)
    assert store.exists("a.b.c.d.e.f") and store.exists("k.b")


@pytest.mark.parametrize("w", [0, 1.5, -0.1, float("nan"), True])
def test_bad_weight_rejected(store, w):
    with pytest.raises(BeliefValidationError):
        store.add_edge("live", "k.a", "k.b", "supports", w)


def test_bad_edge_type_rejected(store):
    with pytest.raises(BeliefValidationError):
        store.add_edge("live", "k.a", "k.b", "contradicts", 0.5)


def test_timestamps_normalized_to_utc(store, db):
    write(
        store, "live", "k.a", 1, "reported", "2026-10-14T12:00:00", "c1"
    )  # naive = UTC
    write(store, "live", "k.b", 1, "reported", "2026-10-14T14:00:00+02:00", "c1")
    got = sorted(
        r[0]
        for r in sqlite3.connect(str(db)).execute("SELECT observed_at FROM assertions")
    )
    assert got == ["2026-10-14T12:00:00.000000Z", "2026-10-14T12:00:00.000000Z"]
    assert format_ts("2026-10-14T12:00:00Z") == "2026-10-14T12:00:00.000000Z"


@pytest.mark.parametrize("obs", ["yesterday", "2026-13-01T00:00:00Z", "", None, 5])
def test_unparseable_timestamp_rejected(store, obs):
    with pytest.raises(BeliefValidationError):
        store.add_assertion(
            "live",
            "k.a",
            polarity=1,
            source_type="reported",
            observed_at=obs,
            recorded_at=T15,
            chunk_id="c1",
        )


def test_future_observation_rejected_with_skew(store):
    with pytest.raises(BeliefValidationError):
        write(
            store, "live", "k.a", 1, "reported", "2026-10-14T15:05:01Z", "c1", rec=T15
        )
    write(store, "live", "k.a", 1, "reported", "2026-10-14T15:04:59Z", "c1", rec=T15)
    assert store.exists("k.a")


def test_source_id_rules():
    assert source_id_for("gmail:sent:abc", "alice", 1) == "gmail:sent:abc"
    assert source_id_for(None, "alice", -1) == "testimony:alice:-1"
    for who in (None, "", "unknown", "unknown:mcp-client", "unknown:http-client"):
        assert source_id_for(None, who, 1) == "testimony:unknown:1"


def test_exact_replay_is_idempotent_and_raises_located(store, db):
    write(store, "live", "k.a", 1, "reported", T15, "c1", located=0)
    write(store, "live", "k.a", 1, "reported", T15, "c1", located=1)
    write(store, "live", "k.a", 1, "reported", T15, "c1", located=0)
    assert store.mentions("k.a") == [("c1", 1, 1)]


# ================================================================ atomicity (section 2.6)


def test_batch_is_one_transaction(store, db):
    before = snapshot(db)
    with pytest.raises(BeliefValidationError):
        with store.batch():
            write(store, "live", "k.a", 1, "reported", T15, "c1")
            store.add_edge("live", "k.a", "k.b", "supports", 0.5)
            write(store, "live", "Bad Key", 1, "reported", T15, "c1")
    assert snapshot(db) == before
    with store.batch():  # positive control
        write(store, "live", "k.a", 1, "reported", T15, "c1")
        store.add_edge("live", "k.a", "k.b", "supports", 0.5)
    assert store.exists("k.a") and store.exists("k.b")


def test_failed_insert_mid_batch_leaves_nothing(store, db, monkeypatch):
    before = snapshot(db)
    real = store._insert_assertion
    calls = []

    def boom(*a, **kw):
        calls.append(1)
        if len(calls) == 2:
            raise sqlite3.OperationalError("disk I/O error (injected)")
        return real(*a, **kw)

    monkeypatch.setattr(store, "_insert_assertion", boom)
    with pytest.raises(sqlite3.OperationalError):
        with store.batch():
            write(store, "live", "k.a", 1, "reported", T15, "c1")
            write(store, "live", "k.b", 1, "reported", T15, "c1")
    assert snapshot(db) == before


def test_rollback_refuses_non_import_origins(store):
    write(store, "live", "k.a", 1, "reported", T15, "c1")
    for origin in ("live", "merge:1", "import:"):
        with pytest.raises(BeliefValidationError):
            store.rollback(origin)
    assert store.exists("k.a")


# ================================================================ edges (section 2.4)


def test_f22_supports_plus_excludes_rejected_across_origins(store, db):
    store.add_edge("live", "k.a", "k.b", "supports", 0.5)
    before = snapshot(db)
    with pytest.raises(EdgeConflict):
        store.add_edge("import:X", "k.b", "k.a", "excludes", 0.5)
    assert snapshot(db) == before
    store.add_edge(
        "import:X", "k.b", "k.a", "depends_on", 0.5
    )  # other combinations are kept


def test_f23_self_edge_rejected_including_through_alias(store):
    with pytest.raises(EdgeConflict):
        store.add_edge("live", "k.a", "k.a", "supports", 0.5)
    write(store, "live", "k.a", 1, "witnessed", T15, "c1")
    write(store, "live", "k.b", 1, "witnessed", T15, "c2")
    store.merge("k.a", "k.b", "merge:1")
    with pytest.raises(EdgeConflict):
        store.add_edge("live", "k.a", "k.b", "supports", 0.5)


def test_w1_w2_weight_update_in_place(store, db):
    write(store, "live", "a.k", 1, "witnessed", T15, "ca", r=0.9)
    store.add_edge("live", "a.k", "b.k", "supports", 0.1)
    assert close(store.probability("b.k", T15), 0.539915, 1e-6)
    store.add_edge("live", "a.k", "b.k", "supports", 0.9)
    assert (
        len(snapshot(db)["edges"]) == 1
    )  # no new row: a row-count cache would miss this
    assert close(store.probability("b.k", T15), 0.808455, 1e-6)


def test_d1_decay_with_no_write(store):
    write(store, "live", "k.a", 1, "witnessed", T15, "c1", r=0.9)
    assert close(store.probability("k.a", T15), 0.9, 1e-6)
    assert close(store.probability("k.a", "2026-10-28T15:00:00Z"), 0.75, 1e-6)


def test_component_solve_matches_whole_web(store):
    import random

    rng = random.Random(3)
    keys = [f"n.k{i}" for i in range(60)]
    for i, k in enumerate(keys):
        if i % 3:
            write(
                store,
                "live",
                k,
                rng.choice((1, -1)),
                "reported",
                T12,
                f"c{i}",
                who=f"w{i}",
            )
    for _ in range(80):
        a, b = rng.sample(keys[:30], 2)  # keys 30..59 form other components
        try:
            store.add_edge(
                "live",
                a,
                b,
                rng.choice(("supports", "depends_on")),
                rng.uniform(0.1, 1),
            )
        except EdgeConflict:
            pass
    store.add_edge("live", keys[40], keys[41], "supports", 0.7)
    whole = store.solve(T15).L
    for k in (keys[1], keys[40], keys[41], keys[55]):
        part = store.solve(T15, keys=[k])
        assert k in part.L
        assert abs(part.L[k] - whole[k]) < 1e-9
    assert len(store.solve(T15, keys=[keys[40]]).L) == 2


def test_clamp_is_hypothetical_and_not_persisted(store, db):
    write(store, "live", "k.a", 1, "witnessed", T15, "c1", r=0.9)
    write(store, "live", "k.b", 1, "witnessed", T15, "c2", r=0.8)
    store.add_edge("live", "k.a", "k.b", "supports", 0.9)
    store.add_edge("live", "k.b", "k.a", "supports", 0.9)
    before = table_hash(db, BELIEF_TABLES)
    sol = store.solve(T15, keys=["k.b"], clamp={"k.a": 7.0})
    assert sol.L["k.a"] == 7.0
    assert close(sol.messages[("k.a", "k.b", "supports")], 1.796720, 1e-6)
    assert table_hash(db, BELIEF_TABLES) == before


# ================================================================ calculator store fixtures


def test_f14_copies_count_once(db, tmp_path):
    now = "2026-10-14T15:30:00Z"
    want = sigmoid(a95 * 2 ** (-(3.5 / 24) / 14) - a7 * 2 ** (-(0.5 / 24) / 14))
    assert close(want, 0.888631, 1e-6)
    for n in (1, 4):
        s = BeliefStore(str(tmp_path / f"f14_{n}.db"))
        write(
            s,
            "live",
            "nick.price_sheet.sent",
            1,
            "witnessed",
            T12,
            "c0",
            source_ref="gmail:sent:abc",
        )
        for i in range(n):
            write(
                s,
                "live",
                "nick.price_sheet.sent",
                -1,
                "reported",
                f"2026-10-14T15:{i * 10:02d}:00Z",
                f"c{i + 1}",
                who="unknown:mcp-client" if i % 2 else None,
            )
        assert close(s.probability("nick.price_sheet.sent", now), want)
        assert len([m for m in s.mentions("nick.price_sheet.sent") if m[1] == -1]) == n
        s.close()


def test_f15_distinct_reporters_count(store):
    write(store, "live", "k.f", 1, "witnessed", T15, "c0", source_ref="gmail:sent:1")
    for who in ("alice", "bob", "carol", "dan"):
        write(store, "live", "k.f", -1, "reported", T15, "c_" + who, who=who)
    assert close(store.probability("k.f", T15), 0.390609, 1e-6)
    write(
        store, "live", "k.g", 1, "witnessed", T15, "c1", source_ref="git:1", kind="fact"
    )
    write(store, "live", "k.g", 1, "witnessed", T15, "c2", source_ref="git:2")
    assert close(store.probability("k.g", T15), 0.997238, 1e-6)


def test_r1_shared_event_rollback(db):
    kv = KVStore(str(db))
    kv.set("pref", "before")
    s = BeliefStore(str(db))
    write(
        s,
        "import:X",
        "nick.price_sheet.sent",
        1,
        "witnessed",
        T12,
        "imp1",
        source_ref="gmail:sent:abc",
    )
    write(s, "import:X", "guardspine.pricing.final", 1, "reported", T12, "imp2")
    kv.set("pref2", "after-import")
    write(
        s,
        "live",
        "nick.price_sheet.sent",
        1,
        "witnessed",
        T12,
        "live1",
        source_ref="gmail:sent:abc",
    )
    others = ("kv_store", "observations", "sessions")
    before = table_hash(db, others)
    want = sigmoid(a95 * 2 ** (-(3 / 24) / 14))
    assert close(want, 0.949130, 1e-6)
    s.rollback("import:X")
    assert table_hash(db, others) == before
    assert s.mentions("nick.price_sheet.sent") == [("live1", 1, 1)]
    assert not s.exists("guardspine.pricing.final")
    assert close(s.probability("nick.price_sheet.sent", T15), want)
    s.close()
    kv.close()


def test_mr_merge_then_rollback(store):
    write(store, "import:X", "a.x", 1, "reported", T15, "i1")
    write(store, "import:X", "b.x", 1, "reported", T15, "i2", who="carol")
    store.merge("a.x", "b.x", "merge:1")
    store.rollback("import:X")
    assert close(store.probability("a.x", T15), 0.5)
    assert store.mentions("a.x") == []
    assert store.resolve("a.x") == "b.x"


def test_mb_multi_reporter_merge_keeps_every_mention(store):
    write(store, "live", "old.k", 1, "reported", T15, "alice_chunk", who="alice")
    write(store, "live", "old.k", -1, "reported", T15, "bob_chunk", who="bob")
    write(store, "live", "new.k", 1, "reported", T15, "carol_chunk", who="carol")
    store.merge("old.k", "new.k", "merge:1")
    assert store.mentions("new.k") == [
        ("alice_chunk", 1, 1),
        ("bob_chunk", -1, 1),
        ("carol_chunk", 1, 1),
    ]
    assert close(store.probability("old.k", T15), 0.7)


@pytest.mark.parametrize("old_loc,new_loc", [(1, 0), (0, 1)])
def test_mc_mention_collision_keeps_located_max(store, old_loc, new_loc):
    write(store, "live", "old.k", 1, "reported", T15, "same_chunk", located=old_loc)
    write(store, "live", "new.k", 1, "reported", T15, "same_chunk", located=new_loc)
    store.merge("old.k", "new.k", "merge:1")
    assert store.mentions("new.k") == [("same_chunk", 1, 1)]


def test_ew_shared_edge_weight_rollback(store):
    write(store, "live", "a.k", 1, "witnessed", T15, "ca", r=0.9)
    store.add_edge("live", "a.k", "b.k", "supports", 0.1)
    p1 = store.probability("b.k", T15)
    store.add_edge("import:X", "a.k", "b.k", "supports", 0.9)
    p2 = store.probability("b.k", T15)
    store.rollback("import:X")
    p3 = store.probability("b.k", T15)
    assert (round(p1, 6), round(p2, 6), round(p3, 6)) == (0.539915, 0.808455, 0.539915)


def test_m1_merged_testimony_counts_once(store):
    write(store, "live", "nick.pricesheet.sent", 1, "reported", T15, "m1")
    write(store, "live", "nick.price_sheet.sent", 1, "reported", T15, "m2")
    store.merge("nick.pricesheet.sent", "nick.price_sheet.sent", "merge:1")
    write(store, "live", "nick.pricesheet.sent", 1, "reported", T15, "m3")
    write(store, "live", "nick.price_sheet.sent", 1, "reported", T15, "m4")
    assert close(store.probability("nick.pricesheet.sent", T15), 0.7)
    assert close(store.probability("nick.price_sheet.sent", T15), 0.7)
    assert len(store.mentions("nick.price_sheet.sent")) == 4


def test_m2_consecutive_merges(store, db):
    for k in ("a.x", "b.x", "c.x"):
        write(store, "live", k, 1, "witnessed", T15, "ch_" + k, source_ref="git:" + k)
    store.merge("a.x", "b.x", "merge:1")
    store.merge("b.x", "c.x", "merge:2")
    assert store.resolve("a.x") == "c.x" and store.resolve("b.x") == "c.x"
    assert close(store.probability("a.x", T15), sigmoid(3 * a95))
    keys = {r[1] for r in snapshot(db)["beliefs"]}
    assert keys == {"c.x"}  # an alias is never a key


def test_mx_refused_merge_leaves_tables_identical(store, db):
    for k in ("a.k", "b.k", "c.k"):
        write(store, "live", k, 1, "witnessed", T15, "ch_" + k)
    store.add_edge("live", "a.k", "c.k", "supports", 0.5)
    store.add_edge("live", "b.k", "c.k", "excludes", 0.5)
    before = snapshot(db)
    with pytest.raises(EdgeConflict):
        store.merge("a.k", "b.k", "merge:1")
    assert snapshot(db) == before


def test_merge_refuses_unknown_or_same(store):
    write(store, "live", "k.a", 1, "reported", T15, "c1")
    with pytest.raises(BeliefValidationError):
        store.merge("k.none", "k.a", "merge:1")
    with pytest.raises(BeliefValidationError):
        store.merge("k.a", "k.a", "merge:1")
    with pytest.raises(BeliefValidationError):
        store.merge("k.a", "k.b", "import:1")


def test_rd_ineligible_copy_does_not_hide_eligible_one(store):
    write(store, "live", "k.rd", 1, "reported", T12, "l1")
    write(
        store,
        "import:X",
        "k.rd",
        1,
        "reported",
        "2026-10-14T11:00:00Z",
        "x1",
        rec="2026-10-14T16:00:00Z",
    )
    p = store.probability("k.rd", T15)
    assert close(p, A7_3H) and close(p, 0.698901, 1e-6)


@pytest.mark.parametrize("old,new", [("k.one", "k.two"), ("k.two", "k.one")])
def test_md_merge_keeps_whole_tuples_and_replay(store, old, new):
    write(store, "live", "k.one", 1, "reported", T12, "c1", source_ref="gmail:sent:abc")
    write(
        store, "live", "k.two", 1, "witnessed", T15, "c1", source_ref="gmail:sent:abc"
    )
    store.merge(old, new, "merge:1")
    assert close(store.probability("k.one", T15), A7_3H)
    assert close(
        store.probability("k.one", "2026-10-14T13:00:00Z"),
        sigmoid(a7 * 2 ** (-(1 / 24) / 14)),
    )
    assert len(store.mentions("k.one")) == 2


def test_mt_tie_broken_by_original_seq(store):
    write(
        store, "import:X", "k.old", 1, "witnessed", T15, "cx", source_ref="gmail:sent:t"
    )
    write(
        store, "import:Y", "k.new", 1, "reported", T15, "cy", source_ref="gmail:sent:t"
    )
    store.merge("k.old", "k.new", "merge:1")
    assert close(store.probability("k.new", T15), 0.95)


@pytest.mark.parametrize("order", ["edge_first", "fact_first"])
def test_ae_attributes_edge_then_fact(store, order):
    if order == "edge_first":
        store.add_edge("live", "k.a", "k.b", "supports", 0.5)
    write(
        store,
        "live",
        "k.b",
        1,
        "witnessed",
        OLD14,
        "cb",
        kind="fact",
        r=0.9,
        claim="B is true",
    )
    if order == "fact_first":
        store.add_edge("live", "k.a", "k.b", "supports", 0.5)
    assert close(store.probability("k.b", T15), FACT14)
    assert store.attrs("k.b")["claim"] == "B is true"
    assert store.attrs("k.a")["claim"] == "k.a"  # placeholder displays its key
    assert store.attrs("k.a")["kind"] == "state"


def test_am_merge_into_placeholder_keeps_kind(store):
    store.add_edge("live", "k.a", "k.new", "supports", 0.5)
    write(store, "live", "k.old", 1, "witnessed", OLD14, "co", kind="fact", r=0.9)
    store.merge("k.old", "k.new", "merge:1")
    assert close(store.probability("k.new", T15), FACT14)


def test_ai_import_removal_keeps_live_attributes(store):
    store.add_edge("live", "k.a", "k.b", "supports", 0.5)
    write(store, "import:X", "k.b", 1, "witnessed", T12, "xb", kind="fact")
    write(store, "live", "k.b", 1, "reported", OLD14, "lb", kind="fact")
    store.rollback("import:X")
    assert close(store.probability("k.b", T15), sigmoid(a7 * 2 ** (-14 / 365)))
    assert close(store.probability("k.b", T15), 0.695311, 1e-6)


def test_p1_p4_quote_location(store):
    chunks = [
        "Budget decision: hold spend at 2k.",
        "Nick price sheet still unsent as of today.",
        "Travel: Philly trip moved.",
    ]
    cases = [
        ("k.p1", chunks, "price sheet still  UNSENT"),
        ("k.p2", chunks, None),
        ("k.p3", chunks, "pricing deck"),
        ("k.p4", chunks[1:2], None),
    ]
    got = []
    for key, chs, quote in cases:
        flags = locate_chunks(chs, quote)
        with store.batch():
            for i, fl in enumerate(flags):
                write(
                    store,
                    "live",
                    key,
                    -1,
                    "reported",
                    T15,
                    f"{key}:chunk{i + 1}",
                    located=fl,
                )
        got.append([m[2] for m in store.mentions(key)])
    assert got == [[0, 1, 0], [0, 0, 0], [0, 0, 0], [1]]
    assert close(
        store.probability("k.p1", T15), 0.3
    )  # three rows from one memory count once


@pytest.mark.parametrize("old,new", [("k.old", "k.new"), ("k.new", "k.old")])
def test_mi_identical_tuple_collision_keeps_lowest_seq(store, old, new):
    write(
        store, "import:X", "k.old", 1, "witnessed", T15, "cz", source_ref="gmail:sent:i"
    )
    write(
        store, "import:Y", "k.new", 1, "reported", T15, "cz", source_ref="gmail:sent:i"
    )
    write(
        store, "import:X", "k.new", 1, "witnessed", T15, "cz", source_ref="gmail:sent:i"
    )
    store.merge(old, new, "merge:1")
    assert close(store.probability("k.old", T15), 0.95)


@pytest.mark.parametrize("old,new", [("k.old", "k.new"), ("k.new", "k.old")])
def test_ax_cross_origin_attribute_priority(store, old, new):
    write(
        store,
        "import:X",
        "k.old",
        1,
        "witnessed",
        OLD14,
        "cx",
        source_ref="gmail:sent:e",
        r=0.9,
        kind="fact",
        claim="X claim",
    )
    write(
        store,
        "import:Y",
        "k.new",
        1,
        "witnessed",
        OLD14,
        "cy",
        source_ref="gmail:sent:e",
        r=0.9,
        kind="state",
        claim="Y claim",
    )
    store.merge(old, new, "merge:1")
    assert close(store.probability("k.old", T15), FACT14)
    assert store.attrs("k.old")["claim"] == "X claim"


@pytest.mark.parametrize("old,new", [("k.old", "k.new"), ("k.new", "k.old")])
def test_as_same_origin_attribute_merge(store, old, new):
    write(
        store,
        "live",
        "k.old",
        1,
        "witnessed",
        OLD14,
        "c1",
        source_ref="gmail:sent:s",
        r=0.9,
        kind="fact",
    )
    write(
        store,
        "live",
        "k.new",
        1,
        "witnessed",
        OLD14,
        "c2",
        source_ref="gmail:sent:s",
        r=0.9,
        kind="state",
    )
    store.merge(old, new, "merge:1")
    assert close(store.probability("k.old", T15), FACT14)


GROUPINGS = [
    (("k.a", "k.c"), ("k.b", "k.c")),
    (("k.a", "k.b"), ("k.b", "k.c")),
    (("k.c", "k.a"), ("k.b", "k.a")),
    (("k.b", "k.a"), ("k.c", "k.a")),
]


@pytest.mark.parametrize("steps", GROUPINGS)
def test_ap_per_attribute_priority_every_grouping(store, steps):
    store.add_edge(
        "live", "k.z", "k.a", "supports", 0.5
    )  # k.a placeholder, earliest seq
    write(
        store,
        "live",
        "k.b",
        1,
        "witnessed",
        OLD14,
        "cb",
        source_ref="gmail:sent:p",
        r=0.9,
        kind="fact",
    )
    write(
        store,
        "live",
        "k.c",
        1,
        "witnessed",
        OLD14,
        "cc",
        source_ref="gmail:sent:p",
        r=0.9,
        kind="state",
        claim="C claim",
    )
    for i, (o, n) in enumerate(steps):
        store.merge(o, n, f"merge:{i}")
    a = store.attrs("k.a")
    assert (a["kind"], a["claim"]) == ("fact", "C claim")
    assert close(store.probability("k.a", T15), FACT14)


def test_ua_archive_restore_includes_counter(store, tmp_path):
    write(store, "live", "k.u", 1, "witnessed", T12, "c1", source_ref="gmail:sent:u")
    store.add_edge("live", "k.u", "k.v", "supports", 0.5)
    arc = tmp_path / "belief-archive.db"
    store.archive(str(arc))
    t2 = BeliefStore(str(tmp_path / "fresh.db"))
    t2.restore(str(arc), mode="fresh")
    top = (
        t2._conn()
        .execute(
            "SELECT max(m) FROM (SELECT max(seq) m FROM beliefs UNION ALL "
            "SELECT max(seq) FROM assertions)"
        )
        .fetchone()[0]
    )
    write(t2, "live", "k.u", 1, "reported", T15, "c2")
    new_seq = (
        t2._conn()
        .execute("SELECT seq FROM assertions WHERE chunk_id='c2'")
        .fetchone()[0]
    )
    assert len(t2.mentions("k.u")) == 2
    assert new_seq > top
    assert snapshot(tmp_path / "fresh.db", ("edges",))["edges"][0][1:4] == (
        "k.u",
        "k.v",
        "supports",
    )
    t2.close()


def test_rs_same_db_restore_keeps_live_counter(store, tmp_path):
    write(store, "live", "k.r", 1, "witnessed", T12, "c1", source_ref="gmail:sent:r")
    arc = tmp_path / "belief-archive.db"
    store.archive(str(arc))
    archived = (
        sqlite3.connect(str(arc)).execute("SELECT n FROM belief_seq").fetchone()[0]
    )
    write(store, "live", "k.r", 1, "reported", T15, "c2")
    live_before = store._conn().execute("SELECT n FROM belief_seq").fetchone()[0]
    store.restore(str(arc), mode="same_db")
    after = store._conn().execute("SELECT n FROM belief_seq").fetchone()[0]
    assert store.mentions("k.r") == [("c1", 1, 1)]
    assert live_before > archived
    assert after == live_before


def test_restore_rejects_unknown_mode(store, tmp_path):
    arc = tmp_path / "a.db"
    store.archive(str(arc))
    with pytest.raises(ValueError):
        store.restore(str(arc), mode="merge")


def test_sx_seq_counter_refuses_integer_limit(store, db):
    write(store, "live", "k.x", 1, "witnessed", T15, "c1", source_ref="gmail:sent:x")
    store._conn().execute("UPDATE belief_seq SET n=?", (SEQ_MAX - 1,))
    write(store, "live", "k.x", 1, "reported", T15, "c2")  # takes SEQ_MAX
    before = snapshot(db)
    with pytest.raises(SeqExhausted):
        write(store, "live", "k.x", -1, "reported", T15, "c3")
    assert snapshot(db) == before
    n = store._conn().execute("SELECT n FROM belief_seq").fetchone()[0]
    assert n == SEQ_MAX and isinstance(n, int)


def test_hl_half_life_override_priority_rollback(store, tmp_path):
    # HL1: live fact without half-life; import X supplies 7 days through the same event
    write(
        store,
        "live",
        "k.h",
        1,
        "witnessed",
        OLD14,
        "c1",
        source_ref="gmail:sent:h",
        r=0.9,
        kind="fact",
    )
    write(
        store,
        "import:X",
        "k.h",
        1,
        "witnessed",
        OLD14,
        "x1",
        source_ref="gmail:sent:h",
        r=0.9,
        half_life_days=7.0,
    )
    assert close(store.probability("k.h", T15), HL7)
    assert close(HL7, 0.633975, 1e-6)
    # HL3: rolling back the supplier falls back to the fact default
    store.rollback("import:X")
    assert close(store.probability("k.h", T15), FACT14)
    # HL2a: live half-life beats an import's
    s = BeliefStore(str(tmp_path / "hl2a.db"))
    write(
        s,
        "import:X",
        "k.h",
        1,
        "witnessed",
        OLD14,
        "x1",
        source_ref="gmail:sent:h",
        r=0.9,
        kind="fact",
        half_life_days=7.0,
    )
    write(
        s,
        "live",
        "k.h",
        1,
        "witnessed",
        OLD14,
        "c1",
        source_ref="gmail:sent:h",
        r=0.9,
        half_life_days=30.0,
    )
    assert close(s.probability("k.h", T15), HL30)
    s.close()
    # HL2b: two imports, no live value: the earlier hl_seq wins
    s = BeliefStore(str(tmp_path / "hl2b.db"))
    write(
        s,
        "import:X",
        "k.h",
        1,
        "witnessed",
        OLD14,
        "x1",
        source_ref="gmail:sent:h",
        r=0.9,
        kind="fact",
        half_life_days=7.0,
    )
    write(
        s,
        "import:Y",
        "k.h",
        1,
        "witnessed",
        OLD14,
        "y1",
        source_ref="gmail:sent:h",
        r=0.9,
        half_life_days=3.5,
    )
    assert close(s.probability("k.h", T15), HL7)
    s.close()


@pytest.mark.parametrize("steps", GROUPINGS)
def test_hl4_half_life_merge_groupings(store, steps):
    store.add_edge("live", "k.z", "k.a", "supports", 0.5)
    write(
        store,
        "live",
        "k.b",
        1,
        "witnessed",
        OLD14,
        "cb",
        source_ref="gmail:sent:q",
        r=0.9,
        kind="fact",
        half_life_days=7.0,
    )
    write(
        store,
        "live",
        "k.c",
        1,
        "witnessed",
        OLD14,
        "cc",
        source_ref="gmail:sent:q",
        r=0.9,
        kind="fact",
        half_life_days=28.0,
    )
    for i, (o, n) in enumerate(steps):
        store.merge(o, n, f"merge:{i}")
    assert close(store.probability("k.a", T15), HL7)


def test_merge_writes_alias_and_placeholder_for_merge_origin(store, db):
    write(store, "live", "k.old", 1, "reported", T15, "c1")
    write(store, "live", "k.new", 1, "reported", T15, "c2", who="bob")
    store.merge("k.old", "k.new", "merge:7")
    snap = snapshot(db)
    assert [r[:3] for r in snap["aliases"]] == [("k.old", "merge:7", "k.new")]
    assert ("merge:7", "k.new") in {r[:2] for r in snap["beliefs"]}
    write(
        store, "live", "k.old", -1, "reported", T15, "c3", who="carol"
    )  # writes resolve to the target
    assert {r[1] for r in snapshot(db)["beliefs"]} == {"k.new"}


def test_locate_chunks_rule():
    assert locate_chunks(["only chunk"], None) == [1]
    assert locate_chunks(["a b", "c  D e"], "d E") == [0, 1]
    assert locate_chunks(["a", "b"], "") == [0, 0]


# ================================================================ review r1 regressions


def test_failed_commit_rolls_back_and_store_stays_usable(store, db):
    before = snapshot(db)
    with pytest.raises(sqlite3.IntegrityError):
        with store.batch() as c:
            # a deferred FK violation is only detected by COMMIT itself
            c.execute("PRAGMA defer_foreign_keys=ON")
            c.execute(
                "INSERT INTO assertions(origin, belief_key, source_id, polarity, source_type,"
                " reliability, observed_at, recorded_at, chunk_id, located, seq)"
                " VALUES('live','no.such','s',1,'reported',0.7,'t','t','c',1,999)"
            )
    assert not store._conn().in_transaction
    assert snapshot(db) == before
    write(store, "live", "k.after", 1, "reported", T15, "c1")
    assert store.exists("k.after")


PRIOR1 = sigmoid(1.0 + a7)  # 0.8638095286: prior_logit 1 plus one reported 0.7
assert abs(PRIOR1 - 0.8638095286) < 1e-9


def test_prior_logit_counts_and_survives_merge(store):
    write(store, "live", "k.old", 1, "reported", T15, "c1", prior_logit=1.0)
    assert close(store.probability("k.old", T15), PRIOR1)
    write(store, "live", "k.new", 1, "reported", T15, "c2", who="bob")
    store.merge("k.old", "k.new", "merge:1")
    assert close(store.probability("k.new", T15), sigmoid(1.0 + 2 * a7))
    assert store.attrs("k.new")["prior_logit"] == 1.0


def test_prior_logit_priority_and_rollback(store):
    write(store, "import:X", "k.p", 1, "reported", T15, "x1", prior_logit=-2.0)
    write(store, "import:Y", "k.p", 1, "reported", T15, "y1", prior_logit=3.0)
    assert close(
        store.probability("k.p", T15), sigmoid(-2.0 + a7)
    )  # earlier import wins
    write(store, "live", "k.p", 1, "reported", T15, "l1", prior_logit=1.0)
    assert close(store.probability("k.p", T15), PRIOR1)  # live first
    store.rollback("import:X")
    assert close(store.probability("k.p", T15), PRIOR1)


@pytest.mark.parametrize("prior", [5.1, -5.1, float("nan"), True, "1"])
def test_bad_prior_logit_rejected(store, prior):
    with pytest.raises(BeliefValidationError):
        write(store, "live", "k.a", 1, "reported", T15, "c1", prior_logit=prior)
