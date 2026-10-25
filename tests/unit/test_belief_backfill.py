"""
Backfill scripts (PLAN-B section 7, 4.4, 6.2 B-PR5 tests 13-16 and 15b, 6.4).

Every database here is a real file-backed SQLite in tmp_path. Nothing reads
real memory data and nothing calls a model: extraction runs against a stub.
Expected values are hand values from the reference calculator's rules
(belief_calc_r8.py): reported 0.7, witnessed 0.95, R1 0.949130, EW 0.539915.
"""

import hashlib
import json
import re
import sqlite3
from pathlib import Path

import pytest

from scripts import belief_backfill as bf
from src.belief_web.belief_store import BeliefStore
from src.belief_web.solver import logit, sigmoid
from src.services import memory_ingestion_service as mis
from src.stores.kv_store import KVStore

T12, T15 = "2026-10-14T12:00:00Z", "2026-10-14T15:00:00Z"
STORED = "2026-10-14T12:00:00"  # ingestion stamps naive utcnow (UTC)
BELIEF_TABLES = ("belief_seq", "beliefs", "assertions", "edges", "aliases")
OTHER_TABLES = ("kv_store", "observations", "sessions")
ROW_TABLES = ("beliefs", "assertions", "edges", "aliases")
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
R1_LIVE = sigmoid(logit(0.95) * 2 ** (-(3 / 24) / 14))  # 0.949130


def snapshot(db, tables, where=""):
    c = sqlite3.connect(str(db))
    try:
        return {
            t: sorted(c.execute(f"SELECT * FROM {t} {where}").fetchall(), key=repr)
            for t in tables
        }
    finally:
        c.close()


def digest(db, tables, where=""):
    return hashlib.sha256(repr(snapshot(db, tables, where)).encode()).hexdigest()


def origin_rows(db, origin):
    c = sqlite3.connect(str(db))
    try:
        return {
            t: c.execute(
                f"SELECT count(*) FROM {t} WHERE origin=?", (origin,)
            ).fetchone()[0]
            for t in ROW_TABLES
        }
    finally:
        c.close()


def obs(oid):
    return {"observation_id": oid, "session_id": "s1", "obs_type": "tool_use",
            "concept": "implementation", "tool_name": "Edit", "content": oid}  # fmt: skip


def write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n"
    )
    return path


def memory(mid, text, who="alice", stored_at=STORED, project="gs"):
    return {"id": mid, "text": text, "stored_at": stored_at, "who": who,
            "project": project}  # fmt: skip


def extracted(mid, *beliefs, because=()):
    return {"id": mid, "beliefs": list(beliefs), "because": list(because)}


def entry(key, value=True, source_type="reported", claim=None, **kw):
    out = {"key": key, "value": value, "source_type": source_type, **kw}
    if claim is not False:
        out["claim"] = claim or f"{key} holds"
    return out


# The fixture import of test 13: a copy of one note (same reporter), a direct
# check quoted in its memory, and a claim that names no check.
EXPORT = [
    memory("m1", "Nick said the price sheet is still unsent."),
    memory("m2", "Copy of the note: price sheet still unsent."),
    memory(
        "m3", "Checked the deploy myself: ran railway status, all green.", who="bob"
    ),
    memory("m4", "Carol is sure the pricing is final now.", who="carol"),
]
EXTRACTED = [
    extracted("m1", entry("nick.price_sheet.sent", False)),
    extracted("m2", entry("nick.price_sheet.sent", False, claim=False)),
    extracted(
        "m3",
        entry("guardspine.deploy.green", source_type="witnessed",
              quote="ran railway status"),  # fmt: skip
    ),
    extracted(
        "m4",
        entry("guardspine.pricing.final", source_type="witnessed"),  # no quote: capped
        because=["guardspine.deploy.green"],
    ),
]
EXPECTED_CONTENT = {
    ("nick.price_sheet.sent", "testimony:alice:-1", -1),
    ("guardspine.deploy.green", "testimony:bob:1", 1),
    ("guardspine.pricing.final", "testimony:carol:1", 1),
}
EXPECTED_P = {  # at T12 = stored_at, so no decay
    "nick.price_sheet.sent": 0.3,  # the copy counts once
    "guardspine.deploy.green": 0.95,  # witnessed, the quote is in the memory
    "guardspine.pricing.final": 0.7,  # witnessed claimed, no quote: reported
}


@pytest.fixture
def files(tmp_path):
    return (
        write_jsonl(tmp_path / "export.jsonl", EXPORT),
        write_jsonl(tmp_path / "extracted.jsonl", EXTRACTED),
    )


def check_content(db, origin="import:X"):
    c = sqlite3.connect(str(db))
    try:
        got = set(
            c.execute(
                "SELECT belief_key, source_id, polarity FROM assertions WHERE origin=?",
                (origin,),
            ).fetchall()
        )
    finally:
        c.close()
    assert got == EXPECTED_CONTENT
    s = BeliefStore(str(db))
    try:
        for key, p in EXPECTED_P.items():
            assert abs(s.probability(key, T12) - p) < 1e-6, key
    finally:
        s.close()


# ================================================================ test 13


def test_backfill_content_and_idempotent(tmp_path, files):
    db = tmp_path / "agent_kv.db"
    records = bf.read_records(*files)
    first = bf.load(str(db), records, "X")
    check_content(db)
    once = digest(db, ROW_TABLES, "WHERE origin='import:X'")
    second = bf.load(str(db), bf.read_records(*files), "X")
    check_content(db)
    assert first["rows"] == second["rows"] == origin_rows(db, "import:X")
    assert origin_rows(db, "import:X")["assertions"] == 4  # both copies are mentions
    # replay changes no row (seq included): exact replay is idempotent
    assert digest(db, ROW_TABLES, "WHERE origin='import:X'") == once
    assert first["witnessed_capped"] == 1


def test_backfill_content_check_fails_on_a_loader_that_inserts_nothing(tmp_path):
    db = tmp_path / "agent_kv.db"
    BeliefStore(str(db)).close()  # schema, no rows
    with pytest.raises(AssertionError):
        check_content(db)


def test_backfill_rows_are_import_origin_with_historical_timestamps(tmp_path, files):
    db = tmp_path / "agent_kv.db"
    bf.load(str(db), bf.read_records(*files), "X")
    c = sqlite3.connect(str(db))
    origins = {
        r[0]
        for t in ROW_TABLES
        for r in c.execute(f"SELECT DISTINCT origin FROM {t}").fetchall()
    }
    stamps = set(c.execute("SELECT observed_at, recorded_at FROM assertions"))
    chunks = {r[0] for r in c.execute("SELECT chunk_id FROM assertions")}
    edges = c.execute("SELECT origin, src, dst, type FROM edges").fetchall()
    c.close()
    assert origins == {"import:X"}
    assert stamps == {("2026-10-14T12:00:00.000000Z", "2026-10-14T12:00:00.000000Z")}
    assert chunks == {"m1", "m2", "m3", "m4"}  # the memory's chunk is the provenance
    assert edges == [
        (
            "import:X",
            "guardspine.pricing.final",
            "guardspine.deploy.green",
            "depends_on",
        )
    ]


# ================================================================ test 14


@pytest.mark.parametrize("exc", [RuntimeError, KeyboardInterrupt])
def test_backfill_interrupted_leaves_nothing(tmp_path, files, monkeypatch, exc):
    db = tmp_path / "agent_kv.db"
    live = BeliefStore(str(db))
    live.add_assertion("live", "k.live", polarity=1, source_type="witnessed",
                       observed_at=T12, recorded_at=T12, chunk_id="c1",
                       claim="live claim")  # fmt: skip
    live.close()
    before = digest(db, BELIEF_TABLES)
    real = bf._write_entry
    calls = []

    def flaky(store, origin, record, item):
        if Path(store.db_path) == db:  # validation runs on a scratch store first
            calls.append(item["key"])
            if len(calls) == 3:
                raise exc("interrupted mid-load")
        return real(store, origin, record, item)

    monkeypatch.setattr(bf, "_write_entry", flaky)
    with pytest.raises(exc):
        bf.load(str(db), bf.read_records(*files), "X")
    assert len(calls) == 3  # two entries were written before the interrupt
    assert origin_rows(db, "import:X") == dict.fromkeys(ROW_TABLES, 0)
    assert digest(db, BELIEF_TABLES) == before
    monkeypatch.setattr(bf, "_write_entry", real)
    bf.load(str(db), bf.read_records(*files), "X")  # a clean retry succeeds
    check_content(db)


def test_load_refuses_any_invalid_record_before_writing(tmp_path, files):
    db = tmp_path / "agent_kv.db"
    bad = [
        extracted("m1", entry("nick.price_sheet.sent", False), entry("Bad Key")),
        extracted("m2", entry("k.when", observed_at="not a time")),
        *EXTRACTED[2:],
    ]
    write_jsonl(files[1], bad)
    with pytest.raises(bf.BackfillError) as err:
        bf.load(str(db), bf.read_records(*files), "X")
    report = err.value.report
    assert report["error_count"] == 2
    assert any("Bad Key" in e for e in report["errors"])
    assert not db.exists()  # nothing opened, nothing written


def test_validate_reports_counts_without_touching_any_database(tmp_path, files):
    report = bf.validate(bf.read_records(*files))
    assert report["error_count"] == 0
    assert report["records"] == 4 and report["entries"] == 4
    assert report["rows"] == {"beliefs": 3, "assertions": 4, "edges": 1, "aliases": 0}
    assert set(tmp_path.iterdir()) == set(files)  # the scratch store is gone


def test_witnessed_kept_only_when_the_memory_quotes_the_check(tmp_path):
    exp = write_jsonl(
        tmp_path / "e.jsonl",
        [memory("m1", "I ran gh pr view 361: merged.", who="bob")],
    )
    cases = [
        ({"quote": "ran gh pr view 361"}, 0.95),  # the quote is in the text
        ({"quote": "checked the dashboard"}, 0.7),  # quote not in the text
        ({}, 0.7),  # no quote
        (
            {"quote": "ran gh pr view 361", "reliability": 0.99},
            0.95,
        ),  # no model numbers
    ]
    for i, (extra, want) in enumerate(cases):
        db = tmp_path / f"db{i}.db"
        ext = write_jsonl(
            tmp_path / f"x{i}.jsonl",
            [
                extracted(
                    "m1", entry("gh.pr361.merged", source_type="witnessed", **extra)
                )
            ],
        )
        bf.load(str(db), bf.read_records(exp, ext), "X")
        s = BeliefStore(str(db))
        assert abs(s.probability("gh.pr361.merged", T12) - want) < 1e-6, extra
        s.close()


def test_observed_after_stored_at_is_rejected(tmp_path):
    exp = write_jsonl(tmp_path / "e.jsonl", [memory("m1", "note")])
    ext = write_jsonl(
        tmp_path / "x.jsonl",
        [extracted("m1", entry("k.future", observed_at="2026-10-14T12:01:00Z"))],
    )
    report = bf.validate(bf.read_records(exp, ext))
    assert report["error_count"] == 1
    assert "later than the memory's stored_at" in report["errors"][0]
    ok = write_jsonl(
        tmp_path / "y.jsonl",
        [extracted("m1", entry("k.past", observed_at="2026-10-14T11:00:00Z"))],
    )
    assert bf.validate(bf.read_records(exp, ok))["error_count"] == 0


def test_validation_errors_are_sanitized(tmp_path, files):
    write_jsonl(
        files[1], [extracted("m1", entry("k.a", source_type="API_KEY=hunter2xyz"))]
    )
    report = bf.validate(bf.read_records(*files))
    assert report["error_count"] == 1
    # since review r2 the entry is refused before validation even sees it
    assert "hunter2xyz" not in json.dumps(report)
    assert "refused, unsafe text (sha256:" in report["errors"][0]


def test_extracted_id_missing_from_export_is_an_error(tmp_path, files):
    write_jsonl(files[1], EXTRACTED + [extracted("m9", entry("k.orphan"))])
    with pytest.raises(bf.BackfillError, match="m9"):
        bf.read_records(*files)


# ================================================================ bulk limits


def test_import_size_and_count_limits_refuse_before_any_work(
    tmp_path, files, monkeypatch
):
    db = tmp_path / "agent_kv.db"
    monkeypatch.setattr(bf, "MAX_IMPORT_BYTES", 64)
    with pytest.raises(bf.BackfillError, match="bytes"):
        bf.read_records(*files)
    monkeypatch.setattr(bf, "MAX_IMPORT_BYTES", 10**6)
    monkeypatch.setattr(bf, "MAX_IMPORT_RECORDS", 3)
    with pytest.raises(bf.BackfillError, match="records"):
        bf.read_records(*files)
    monkeypatch.setattr(bf, "MAX_IMPORT_RECORDS", 4)
    assert len(bf.read_records(*files)) == 4  # at the limit is fine
    assert not db.exists()


def test_import_record_over_belief_limits_is_an_error(tmp_path, files):
    write_jsonl(
        files[1],
        [extracted("m1", *[entry(f"k.n{i}") for i in range(51)])],
    )
    report = bf.validate(bf.read_records(*files))
    assert report["error_count"] == 1
    assert "51 entries exceed the limit of 50" in report["errors"][0]
    assert report["rows"] == {"beliefs": 0, "assertions": 0, "edges": 0, "aliases": 0}


def test_import_error_report_is_bounded(tmp_path, files):
    write_jsonl(
        files[1],
        [
            extracted(
                "m1", *[entry(f"k.n{i}", source_type="x" * 400) for i in range(50)]
            )
        ],
    )
    report = bf.validate(bf.read_records(*files))
    assert report["error_count"] == 50
    assert len("".join(report["errors"])) <= bf.ERROR_BUDGET  # notice included
    assert report["errors"][-1].endswith("more errors not shown")


# ================================================================ test 15


def test_rollback_preserves_everything_else(tmp_path):
    db = tmp_path / "agent_kv.db"
    kv = KVStore(str(db))
    kv.set("pref", "before")
    kv.store_observation(obs("o1"))
    kv.create_session({"session_id": "s1", "started_at": T12, "project": "gs"})
    s = BeliefStore(str(db))
    # live, before the import: EW base edge
    s.add_assertion("live", "a.k", polarity=1, source_type="witnessed", reliability=0.9,
                    observed_at=T15, recorded_at=T15, chunk_id="ca", claim="A")  # fmt: skip
    s.add_edge("live", "a.k", "b.k", "supports", 0.1)
    p_ew = s.probability("b.k", T15)
    assert round(p_ew, 6) == 0.539915
    # import X: the shared Gmail event (R1), two keys to merge (MR), the EW edge
    exp = write_jsonl(
        tmp_path / "e.jsonl",
        [
            memory("x1", "Sent Nick the price sheet: gmail sent abc.", who="david"),
            memory("x2", "pricing is final", who="carol"),
            memory("x3", "a note on a.x", who="erin"),
            memory("x4", "a note on b.x", who="frank"),
        ],
    )
    ext = write_jsonl(
        tmp_path / "x.jsonl",
        [
            extracted(
                "x1",
                entry(
                    "nick.price_sheet.sent",
                    source_type="witnessed",
                    source_ref="gmail:sent:abc",
                    quote="gmail sent abc",
                ),
            ),  # fmt: skip
            extracted("x2", entry("guardspine.pricing.final")),
            extracted("x3", entry("a.x")),
            extracted("x4", entry("b.x")),
        ],
    )
    bf.load(str(db), bf.read_records(exp, ext), "X")
    s.add_edge("import:X", "a.k", "b.k", "supports", 0.9)
    assert round(s.probability("b.k", T15), 6) == 0.808455
    # import Y, untouched by X's rollback
    ey = write_jsonl(tmp_path / "ey.jsonl", [memory("y1", "y note", who="gail")])
    xy = write_jsonl(tmp_path / "xy.jsonl", [extracted("y1", entry("c.y"))])
    bf.load(str(db), bf.read_records(ey, xy), "Y")
    # live AFTER the import: the same Gmail event as its own row, a new belief
    s.add_assertion("live", "nick.price_sheet.sent", polarity=1, source_type="witnessed",
                    observed_at=T12, recorded_at=T12, chunk_id="live1",
                    source_ref="gmail:sent:abc", claim="Nick price sheet was sent")  # fmt: skip
    s.add_assertion("live", "k.after", polarity=1, source_type="reported",
                    observed_at=T15, recorded_at=T15, chunk_id="c9", claim="after")  # fmt: skip
    kv.set("pref2", "after-import")
    kv.store_observation(obs("o2"))
    # merge X's beliefs, archive first (the merge undo)
    bf.merge_pairs(str(db), [("a.x", "b.x")], "merge:review1", str(tmp_path / "pre.db"))
    live_p = s.probability("nick.price_sheet.sent", T15)
    assert abs(live_p - R1_LIVE) < 1e-6
    assert all(snapshot(db, OTHER_TABLES).values())  # the hashes cover real rows
    others = digest(db, OTHER_TABLES)
    live_rows = digest(db, ROW_TABLES, "WHERE origin='live'")
    y_rows = digest(db, ROW_TABLES, "WHERE origin='import:Y'")
    merge_rows = digest(db, ROW_TABLES, "WHERE origin LIKE 'merge:%'")

    report = bf.rollback(str(db), "X")  # no FK error

    assert sum(report["deleted"].values()) > 0
    assert origin_rows(db, "import:X") == dict.fromkeys(ROW_TABLES, 0)
    assert digest(db, OTHER_TABLES) == others
    assert digest(db, ROW_TABLES, "WHERE origin='live'") == live_rows
    assert digest(db, ROW_TABLES, "WHERE origin='import:Y'") == y_rows
    assert digest(db, ROW_TABLES, "WHERE origin LIKE 'merge:%'") == merge_rows
    assert round(s.probability("b.k", T15), 6) == 0.539915  # EW
    assert s.resolve("a.x") == "b.x" and abs(s.probability("a.x", T15) - 0.5) < 1e-9
    assert s.mentions("a.x") == []  # MR
    assert abs(s.probability("nick.price_sheet.sent", T15) - live_p) < 1e-12  # R1
    assert s.mentions("nick.price_sheet.sent") == [("live1", 1, 1)]
    assert not s.exists("guardspine.pricing.final")
    assert round(s.probability("c.y", T15), 6) == 0.698901  # Y, stored 3 h earlier
    assert s.exists("k.after")
    s.close()
    kv.close()


def test_rollback_of_an_unknown_import_is_an_error(tmp_path):
    db = tmp_path / "agent_kv.db"
    BeliefStore(str(db)).close()
    with pytest.raises(bf.BackfillError, match="no rows"):
        bf.rollback(str(db), "nope")


# ================================================================ merges (4.4)


def test_merge_batch_archives_first_and_is_all_or_nothing(tmp_path):
    db = tmp_path / "agent_kv.db"
    s = BeliefStore(str(db))
    s.add_assertion("live", "nick.pricesheet.sent", polarity=1, source_type="reported",
                    observed_at=T15, recorded_at=T15, chunk_id="m1", claim="N")  # fmt: skip
    s.add_assertion("live", "nick.price_sheet.sent", polarity=1, source_type="reported",
                    observed_at=T15, recorded_at=T15, chunk_id="m2", claim="N")  # fmt: skip
    s.add_edge("live", "a.k", "c.k", "supports", 0.5)
    s.add_edge("live", "b.k", "c.k", "excludes", 0.5)
    before = snapshot(db, BELIEF_TABLES)
    pairs = [("nick.pricesheet.sent", "nick.price_sheet.sent"), ("a.k", "b.k")]
    arc = tmp_path / "pre-merge.db"
    with pytest.raises(Exception, match="supports and excludes"):
        bf.merge_pairs(str(db), pairs, "merge:r1", str(arc))  # MX in the batch
    assert snapshot(db, BELIEF_TABLES) == before  # the first merge rolled back too
    assert snapshot(arc, BELIEF_TABLES) == before  # archive taken before any merge
    arc2 = tmp_path / "pre-merge-2.db"
    out = bf.merge_pairs(str(db), pairs[:1], "merge:r2", str(arc2))
    assert out["merged"] == 1 and snapshot(arc2, BELIEF_TABLES) == before
    assert abs(s.probability("nick.pricesheet.sent", T15) - 0.7) < 1e-6  # M1
    with pytest.raises(FileExistsError):
        bf.merge_pairs(str(db), pairs[:1], "merge:r3", str(arc2))
    s.close()


def test_review_pairs_file_feeds_merge(tmp_path):
    path = tmp_path / "review.json"
    path.write_text(
        json.dumps(
            [
                {"old": "a.k", "new": "b.k", "score": 1.0, "approve": True},
                {"old": "c.k", "new": "d.k", "score": 0.95, "approve": False},
            ]
        ),
        encoding="utf-8",
    )
    assert bf.approved_pairs(str(path)) == [("a.k", "b.k")]


# ================================================================ test 15b (7.2)


def test_uninstall_archives_live_rows(tmp_path, files):
    db = tmp_path / "agent_kv.db"
    kv = KVStore(str(db))
    kv.store_observation(obs("o1"))
    s = BeliefStore(str(db))
    s.add_assertion("live", "k.before", polarity=1, source_type="witnessed",
                    observed_at=T12, recorded_at=T12, chunk_id="c1", claim="b")  # fmt: skip
    s.close()
    bf.load(str(db), bf.read_records(*files), "X")
    s = BeliefStore(str(db))
    s.add_assertion("live", "k.after", polarity=-1, source_type="reported",
                    observed_at=T15, recorded_at=T15, chunk_id="c2", claim="a")  # fmt: skip
    s.add_edge("live", "k.after", "k.before", "depends_on", 0.5)
    s.close()
    before = snapshot(db, BELIEF_TABLES)
    assert any(r[0] == "live" and r[1] == "k.after" for r in before["beliefs"])
    kept = digest(db, OTHER_TABLES)
    arc = tmp_path / "belief-archive.db"

    counts = bf.uninstall(str(db), str(arc))

    assert counts == {t: len(rows) for t, rows in before.items()}
    assert snapshot(arc, BELIEF_TABLES) == before  # every row, live ones included
    c = sqlite3.connect(str(db))
    left = {
        r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    mig = c.execute("SELECT count(*) FROM migrations WHERE version='008'").fetchone()[0]
    c.close()
    assert not left & set(BELIEF_TABLES) and mig == 0
    assert digest(db, OTHER_TABLES) == kept
    # restore into a fresh schema brings every row and the counter back
    bf.restore(str(db), str(arc), "fresh")
    assert snapshot(db, BELIEF_TABLES) == before
    kv.close()


def test_uninstall_stops_when_a_row_lands_after_the_archive(tmp_path, monkeypatch):
    db = tmp_path / "agent_kv.db"
    s = BeliefStore(str(db))
    s.add_assertion("live", "k.a", polarity=1, source_type="witnessed",
                    observed_at=T12, recorded_at=T12, chunk_id="c1", claim="a")  # fmt: skip
    s.close()
    real = BeliefStore.archive

    def archive_then_write(self, path):
        counts = real(self, path)
        late = BeliefStore(str(db))  # a writer that was not quiesced
        late.add_assertion("live", "k.late", polarity=1, source_type="reported",
                           observed_at=T15, recorded_at=T15, chunk_id="c2",
                           claim="late")  # fmt: skip
        late.close()
        return counts

    monkeypatch.setattr(BeliefStore, "archive", archive_then_write)
    with pytest.raises(bf.BackfillError, match="changed after the archive"):
        bf.uninstall(str(db), str(tmp_path / "arc.db"))
    s = BeliefStore(str(db))
    assert s.exists("k.late") and s.exists("k.a")  # nothing dropped
    s.close()


def test_uninstall_refuses_an_existing_archive_and_drops_nothing(tmp_path):
    db = tmp_path / "agent_kv.db"
    s = BeliefStore(str(db))
    s.add_assertion("live", "k.a", polarity=1, source_type="witnessed",
                    observed_at=T12, recorded_at=T12, chunk_id="c1", claim="a")  # fmt: skip
    s.close()
    before = snapshot(db, BELIEF_TABLES)
    arc = tmp_path / "taken.db"
    arc.write_bytes(b"")
    with pytest.raises(FileExistsError):
        bf.uninstall(str(db), str(arc))
    assert snapshot(db, BELIEF_TABLES) == before


# ================================================================ test 16


def sha_id(mid):
    return "sha256:" + hashlib.sha256(mid.encode("utf-8")).hexdigest()[:16]


def chroma_like(mid, text, **md):
    return {"id": mid, "text": text,
            "metadata": {"stored_at": STORED, "project": "gs", "who": "alice", **md}}  # fmt: skip


def test_export_sanitizer(tmp_path):
    key = "sk-" + "A1b2C3d4E5f6G7h8J9k0"
    bearer = "Bearer " + "abcdefghijklmnop0123"
    records = [
        chroma_like("closed", "keep <private>hidden one</private> tail"),
        chroma_like("unclosed", "keep <private>hidden two to the end"),
        chroma_like("upper", "keep <PRIVATE>hidden three</PRIVATE> tail"),
        chroma_like("secrets", f"API_KEY=hunter2xyz and {key} and auth {bearer} ok"),
        chroma_like("plain", "Nick's price sheet is still unsent."),
        # planted positive controls: strip_private leaves these, the check must not
        chroma_like("spaced", "keep < private >hidden four</ private > tail"),
        chroma_like("stray", "a stray </private> close tag"),
        chroma_like("who_tag", "fine text", who="<  Private>agent"),
        chroma_like("no_time", "fine text", stored_at=None),
    ]
    out = tmp_path / "export.jsonl"
    report = bf.export_records({"memory_chunks": records}, str(out))
    rows = {
        r["id"]: r
        for r in map(json.loads, out.read_text(encoding="utf-8").splitlines())
    }
    assert set(rows) == {"closed", "unclosed", "upper", "secrets", "plain"}
    assert rows["closed"]["text"] == "keep [REDACTED] tail"
    assert rows["unclosed"]["text"] == "keep [REDACTED]"
    assert rows["upper"]["text"] == "keep [REDACTED] tail"
    secret = rows["secrets"]["text"]
    assert "hunter2xyz" not in secret and key not in secret and bearer not in secret
    assert rows["plain"]["text"] == "Nick's price sheet is still unsent."
    assert rows["plain"] == {"id": "plain", "text": "Nick's price sheet is still unsent.",
                             "stored_at": STORED, "project": "gs", "who": "alice",
                             "collection": "memory_chunks"}  # fmt: skip
    dump = out.read_text(encoding="utf-8")
    assert not re.search(r"(?i)<\s*/?\s*private", dump)
    assert "hidden" not in dump
    assert report["exported"] == 5
    assert report["excluded"] == {
        "unsafe_id": 0,
        "private_residue": 3,
        "missing_stored_at": 1,
    }
    assert [(r["digest"], r["reason"]) for r in report["excluded_records"]] == [
        (sha_id("spaced"), "private_residue"),
        (sha_id("stray"), "private_residue"),
        (sha_id("who_tag"), "private_residue"),
        (sha_id("no_time"), "missing_stored_at"),
    ]


def test_export_refuses_to_overwrite(tmp_path):
    out = tmp_path / "export.jsonl"
    out.write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        bf.export_records({"memory_chunks": [chroma_like("a", "t")]}, str(out))
    assert out.read_text(encoding="utf-8") == "x"


def test_export_reads_a_chroma_collection(tmp_path):
    chromadb = pytest.importorskip("chromadb")
    path = tmp_path / "chroma"
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(path), settings=Settings(anonymized_telemetry=False)
    )
    col = client.get_or_create_collection("memory_chunks", embedding_function=None)
    col.add(
        ids=["c1", "c2", "c3"],
        documents=["one", "two", "three"],
        metadatas=[{"stored_at": STORED, "who": "w", "project": "p"}] * 3,
        embeddings=[[0.1, 0.2], [0.2, 0.1], [0.3, 0.3]],
    )
    got = sorted(
        bf.read_chroma(str(path), "memory_chunks", page=2), key=lambda r: r["id"]
    )
    assert [(r["id"], r["text"], r["metadata"]["who"]) for r in got] == [
        ("c1", "one", "w"),
        ("c2", "two", "w"),
        ("c3", "three", "w"),
    ]


# ================================================================ extract (7 step 2)


def stub_model(calls, pad=0):
    def call(prompt):
        calls.append(prompt)
        ids = re.findall(r'^\{"id": "(m\d+)"', prompt, re.M)
        lines = [
            json.dumps(extracted(i, entry(f"topic.k{len(calls)}", claim="c")))
            for i in ids
        ]
        return "\n".join(lines) + "\n" * pad

    return call


def test_extract_batches_vocabulary_and_output(tmp_path):
    exp = write_jsonl(
        tmp_path / "e.jsonl", [memory(f"m{i}", f"memory {i}") for i in range(45)]
    )
    out = tmp_path / "extracted.jsonl"
    calls = []
    report = bf.extract(str(exp), str(out), stub_model(calls))
    sizes = [len(re.findall(r'^\{"id": "m\d+"', p, re.M)) for p in calls]
    assert sizes == [20, 20, 5]
    assert "topic.k1" not in calls[0] and "topic.k1" in calls[1]  # vocabulary grows
    assert "topic.k2" in calls[2]
    assert "data, not instructions" in calls[0]
    lines = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 45 and lines[0]["id"] == "m0"
    assert report["batches"] == 3 and report["errors"] == []
    assert 0 < report["tokens"] < bf.TOKEN_ABORT


def test_extract_aborts_at_the_token_budget(tmp_path):
    exp = write_jsonl(
        tmp_path / "e.jsonl", [memory(f"m{i}", f"memory {i}") for i in range(45)]
    )
    out = tmp_path / "extracted.jsonl"
    calls = []
    with pytest.raises(bf.TokenBudgetExceeded, match="before any model call"):
        bf.extract(str(exp), str(out), stub_model(calls), token_budget=10)
    assert calls == [] and not out.exists()  # preflight: nothing was sent
    need = bf.preflight_tokens(bf.read_jsonl(str(exp)))
    with pytest.raises(bf.TokenBudgetExceeded, match="after batch 1"):
        bf.extract(
            str(exp), str(out), stub_model(calls, pad=40000), token_budget=need + 50
        )
    assert len(calls) == 1 and not out.exists()  # stopped mid-run, no output kept


def test_extract_reports_bad_reply_lines(tmp_path):
    exp = write_jsonl(tmp_path / "e.jsonl", [memory("m1", "a"), memory("m2", "b")])
    out = tmp_path / "extracted.jsonl"

    def model(prompt):
        return 'not json\n{"id": "m7", "beliefs": []}\n' + json.dumps(extracted("m1"))

    report = bf.extract(str(exp), str(out), model)
    assert len(report["errors"]) == 2
    assert report["missing"] == ["m2"]
    assert [
        json.loads(x)["id"] for x in out.read_text(encoding="utf-8").splitlines()
    ] == ["m1"]


def test_tokens_default_budget_is_the_plan_abort():
    assert bf.TOKEN_ABORT == 1_500_000


# ================================================================ duplicates (6.4)


def test_duplicate_dataset_precision_and_recall():
    data = json.loads(
        (FIXTURES / "belief_duplicate_pairs.json").read_text(encoding="utf-8")
    )
    assert len(data["duplicates"]) == 20 and len(data["distinct"]) == 20
    t = bf.DUPLICATE_THRESHOLD
    tp = sum(bf.key_similarity(a, b) >= t for a, b in data["duplicates"])
    fp = sum(bf.key_similarity(a, b) >= t for a, b in data["distinct"])
    # committed rates at the committed threshold (recorded in the PR ledger)
    assert t == 0.90
    assert (tp, fp) == (19, 0)  # precision 1.00, recall 0.95


def test_review_list_names_near_duplicate_keys(tmp_path):
    exp = write_jsonl(
        tmp_path / "e.jsonl", [memory("m1", "a"), memory("m2", "b"), memory("m3", "c")]
    )
    ext = write_jsonl(
        tmp_path / "x.jsonl",
        [
            extracted("m1", entry("nick.pricesheet.sent")),
            extracted("m2", entry("nick.price_sheet.sent")),
            extracted(
                "m3", entry("guardspine.pr361.merged"), entry("guardspine.pr362.merged")
            ),
        ],
    )
    report = bf.validate(
        bf.read_records(exp, ext), existing_keys=["nick.price_sheet.read"]
    )
    assert [(d["old"], d["new"]) for d in report["duplicates"]] == [
        ("nick.pricesheet.sent", "nick.price_sheet.sent")
    ]
    assert (
        report["duplicates"][0]["approve"] is False
    )  # review decides, never the script


# ================================================================ CLI


def test_cli_requires_explicit_paths_and_exits_nonzero_on_errors(
    tmp_path, files, capsys
):
    # no default database path: a usage error, through the safe error path
    assert bf.main(["load"]) == 1
    assert "the following arguments are required" in capsys.readouterr().out
    assert (
        bf.main(["validate", "--export", str(files[0]), "--extracted", str(files[1])])
        == 0
    )
    db = tmp_path / "agent_kv.db"
    args = ["--db", str(db), "--export", str(files[0]), "--extracted", str(files[1])]
    assert bf.main(["load", *args, "--import-id", "X", "--dry-run"]) == 0
    assert not db.exists()  # a dry run opens nothing
    assert bf.main(["load", *args, "--import-id", "X"]) == 0
    check_content(db)
    assert bf.main(["rollback", "--db", str(db), "--import-id", "X"]) == 0
    assert origin_rows(db, "import:X") == dict.fromkeys(ROW_TABLES, 0)
    write_jsonl(files[1], [extracted("m1", entry("Bad Key"))])
    assert (
        bf.main(["validate", "--export", str(files[0]), "--extracted", str(files[1])])
        == 1
    )
    printed = capsys.readouterr().out
    assert "Bad Key" in printed


# ================================================================ review r1 (Sol)

ID_CANARY = "API_KEY=ID_CANARY"
PRIV_ID = "<private>PRIV_ID_CANARY</private>"
SK_ID = "sk-" + "IDCANARY0123456789ab"
WITHHELD = "1 diagnostic withheld (unresolved private tag)"


def test_r1_unsafe_ids_are_excluded_and_reported_by_digest(tmp_path):
    records = [chroma_like(i, "fine text") for i in (ID_CANARY, PRIV_ID, SK_ID)]
    records.append(chroma_like("c1-safe:id.0", "fine text"))
    out = tmp_path / "export.jsonl"
    report = bf.export_records({"memory_chunks": records}, str(out))
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in rows] == ["c1-safe:id.0"]  # a safe id is kept as is
    assert report["excluded"]["unsafe_id"] == 3
    assert [r["digest"] for r in report["excluded_records"]] == [
        sha_id(ID_CANARY),
        sha_id(PRIV_ID),
        sha_id(SK_ID),
    ]
    dump = json.dumps(report) + out.read_text(encoding="utf-8")
    assert "CANARY" not in dump and "<" not in dump


def test_r1_unsafe_id_in_an_input_file_never_reaches_a_prompt(tmp_path):
    exp = write_jsonl(
        tmp_path / "e.jsonl", [memory(ID_CANARY, "text"), memory("m2", "b")]
    )
    calls = []
    with pytest.raises(bf.BackfillError) as err:
        bf.extract(str(exp), str(tmp_path / "x.jsonl"), stub_model(calls))
    assert calls == [] and "CANARY" not in str(err.value)
    assert sha_id(ID_CANARY) in str(err.value)


def test_r1_extract_diagnostics_are_sanitized_and_tags_withheld(
    tmp_path, monkeypatch, capsys
):
    exp = write_jsonl(tmp_path / "e.jsonl", [memory("m1", "a"), memory("m2", "b")])

    def model(prompt):
        return "\n".join(
            [
                "API_KEY=REPLY_CANARY not json",
                json.dumps({"id": "API_KEY=REPLY_CANARY2", "beliefs": []}),
                "< private >PRIV_REPLY_CANARY",
                "x" * 70 + " " + "sk-" + "REPLYCANARY0123456789",
                json.dumps(extracted("m1")),
            ]
        )

    report = bf.extract(str(exp), str(tmp_path / "x.jsonl"), model)
    dump = json.dumps(report)
    assert "CANARY" not in dump and "<" not in dump
    assert len(report["errors"]) == 4  # three shown, then the withheld notice
    assert report["errors"][-1] == WITHHELD
    # the CLI prints through the same helper
    monkeypatch.setattr(bf, "model_command", lambda cmd: model)
    out = tmp_path / "y.jsonl"
    args = ["extract", "--export", str(exp), "--out", str(out), "--model-cmd", "stub"]
    code = bf.main(args)
    printed = capsys.readouterr().out
    assert code == 0 and "CANARY" not in printed and "<" not in printed


def test_r1_validate_errors_with_private_tags_are_withheld(tmp_path, files):
    write_jsonl(
        files[1],
        [extracted("m1", entry("k.a", source_type="< private >PRIV_VALIDATE_CANARY"))],
    )
    report = bf.validate(bf.read_records(*files))
    assert report["error_count"] == 1
    assert "CANARY" not in json.dumps(report)
    # since review r2 the entry is refused by digest before any validator echo
    assert len(report["errors"]) == 1
    assert "refused, unsafe text (sha256:" in report["errors"][0]


def test_r1_cli_error_messages_go_through_the_helper(tmp_path, capsys):
    exp = write_jsonl(tmp_path / "e.jsonl", [memory("m1", "a")])
    bad = tmp_path / "x.jsonl"
    line = json.dumps({"id": "API_KEY=CLI_CANARY < private >"})
    bad.write_text(line + "\n", encoding="utf-8")
    code = bf.main(["validate", "--export", str(exp), "--extracted", str(bad)])
    printed = capsys.readouterr().out
    assert code == 1 and "CANARY" not in printed and "<" not in printed


def test_r1_safe_diagnostic_sanitizes_before_truncating():
    secret = "sk-" + "TRUNCCANARY0123456789"
    text = "e" * 70 + " " + secret  # a cut at 80 first would leave 'sk-TRUNCCAN'
    got = bf.safe_diagnostic(text, cap=80)
    assert got is not None and "TRUNC" not in got and len(got) <= 80
    assert bf.safe_diagnostic("a < private >b") is None
    assert bf.safe_diagnostic("plain") == "plain"


def test_r1_safe_diagnostic_gives_the_sanitizer_the_whole_text(monkeypatch):
    # strip_private's trailing patterns hide the order today; a sanitizer that
    # only knows whole tokens shows it: a cut first leaves 'sk-TRUNCC' behind
    whole_tokens = re.compile(r"sk-[A-Za-z0-9]{16,}")
    monkeypatch.setattr(bf, "strip_private", lambda t: whole_tokens.sub("[X]", t))
    got = bf.safe_diagnostic("e" * 70 + " sk-" + "TRUNCCANARY0123456789", cap=80)
    assert got == "e" * 70 + " [X]"


def chroma_with(path, collections):
    chromadb = pytest.importorskip("chromadb")
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(path), settings=Settings(anonymized_telemetry=False)
    )
    for name, recs in collections.items():
        col = client.get_or_create_collection(name, embedding_function=None)
        col.add(
            ids=[r[0] for r in recs],
            documents=[r[1] for r in recs],
            metadatas=[r[2] for r in recs],
            embeddings=[[0.1, 0.2]] * len(recs),
        )


def test_r1_export_covers_both_collections_and_loads_once(tmp_path, capsys):
    md = {"stored_at": STORED, "who": "w", "project": "p"}
    chroma = tmp_path / "chroma"
    chroma_with(
        chroma,
        {
            "memory_chunks": [("c1", "one", md), ("c2", "two", md)],
            "agent_memories": [
                ("a1", "agent one", md),
                ("a2", "no time", {"who": "w"}),
            ],
            "test_other": [("t1", "never exported", md)],
        },
    )
    out = tmp_path / "export.jsonl"
    assert bf.main(["export", "--chroma", str(chroma), "--out", str(out)]) == 0
    report = json.loads(capsys.readouterr().out)
    per = report["collections"]
    assert set(per) == {"memory_chunks", "agent_memories"}
    assert per["memory_chunks"]["read"] == 2 and per["memory_chunks"]["exported"] == 2
    assert per["agent_memories"]["read"] == 2
    assert per["agent_memories"]["exported"] == 1
    assert per["agent_memories"]["excluded"]["missing_stored_at"] == 1
    assert report["exported"] == 3
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert {(r["id"], r["collection"]) for r in rows} == {
        ("c1", "memory_chunks"),
        ("c2", "memory_chunks"),
        ("a1", "agent_memories"),
    }
    ext = write_jsonl(
        tmp_path / "x.jsonl",
        [extracted("c1", entry("k.one")), extracted("a1", entry("k.agent"))],
    )
    db = tmp_path / "agent_kv.db"
    bf.load(str(db), bf.read_records(str(out), str(ext)), "X")  # one import
    c = sqlite3.connect(str(db))
    got = set(c.execute("SELECT origin, chunk_id FROM assertions"))
    c.close()
    assert got == {("import:X", "c1"), ("import:X", "a1")}


def test_r1_an_id_in_two_collections_is_refused(tmp_path):
    a = [chroma_like("same", "one")]
    b = [chroma_like("same", "two")]
    out = tmp_path / "export.jsonl"
    with pytest.raises(bf.BackfillError, match="more than one collection"):
        bf.export_records({"memory_chunks": a, "agent_memories": b}, str(out))
    assert not out.exists()


def test_r1_budget_above_the_ceiling_is_refused(tmp_path, monkeypatch):
    exp = write_jsonl(tmp_path / "e.jsonl", [memory("m1", "a")])
    calls = []
    with pytest.raises(bf.BackfillError, match="exceeds the 1500000 token ceiling"):
        bf.extract(
            str(exp),
            str(tmp_path / "x.jsonl"),
            stub_model(calls),
            token_budget=bf.TOKEN_ABORT + 1,
        )
    assert calls == [] and not (tmp_path / "x.jsonl").exists()
    monkeypatch.setattr(bf, "model_command", lambda cmd: stub_model(calls))
    args = ["extract", "--export", str(exp), "--out", str(tmp_path / "y.jsonl")]
    assert bf.main([*args, "--model-cmd", "stub", "--budget", "2000000"]) == 1
    assert calls == []
    assert bf.main([*args, "--model-cmd", "stub", "--budget", "100000"]) == 0
    assert len(calls) == 1  # a lower budget still runs


def test_r1_error_budget_is_exact_with_the_notice():
    for n, size in [(50, 100), (21, 100), (20, 100), (3, 990), (1, 3000)]:
        errors = ["x" * size] * n
        got = mis.cap_errors(errors, 2000)
        assert len("".join(got)) <= 2000, (n, size)
        if n * size <= 2000:
            assert got == errors  # everything fits: no notice
        else:
            shown = len(got) - 1
            assert got[-1] == f"... {n - shown} more errors not shown"


def test_r1_cli_errors_with_unsafe_paths_are_sanitized(tmp_path, monkeypatch, capsys):
    exp = write_jsonl(tmp_path / "API_KEY=PATHCANARY_E.jsonl", [memory("m1", "a")])
    taken = tmp_path / "API_KEY=PATHCANARY_O.jsonl"
    taken.write_text("x", encoding="utf-8")
    monkeypatch.setattr(bf, "model_command", lambda cmd: stub_model([]))
    args = ["extract", "--export", str(exp), "--model-cmd", "stub", "--out"]
    assert bf.main([*args, str(taken)]) == 1  # FileExistsError branch
    monkeypatch.setattr(bf, "MAX_IMPORT_BYTES", 1)
    assert bf.main([*args, str(tmp_path / "new.jsonl")]) == 1  # BackfillError branch
    printed = capsys.readouterr().out
    assert "PATHCANARY" not in printed and printed.count("[REDACTED]") == 2


def test_r1_chroma_read_is_reconciled_with_the_collection_count(monkeypatch):
    class Col:
        def count(self):
            return 3

        def get(self, limit, offset, include):
            ids = ["c1", "c2"][offset : offset + limit]
            return {
                "ids": ids,
                "documents": ["d"] * len(ids),
                "metadatas": [{}] * len(ids),
            }

    class Client:
        def __init__(self, path, settings):
            pass

        def get_collection(self, name, embedding_function):
            return Col()

    import chromadb

    monkeypatch.setattr(chromadb, "PersistentClient", Client)
    with pytest.raises(bf.BackfillError, match="read 2 of 3 records"):
        list(bf.read_chroma("unused", "memory_chunks", page=5))


# ================================================================ review r2 (Sol)

KEY_CANARY = "API_KEY=R2CANARY_CLAIM"
TAG_CANARY = "keep < private >R2CANARY_TAG"
SK_CANARY = "sk-" + "R2CANARY0123456789abcd"


def r2_entry(**kw):
    return {**entry("k.r2", claim="a clean claim"), **kw}


@pytest.mark.parametrize(
    "bad",
    [
        {"claim": KEY_CANARY},
        {"quote": TAG_CANARY},
        {"source_ref": SK_CANARY},
        {"kind": KEY_CANARY},
        {"supports": ["k.ok", KEY_CANARY]},
        {"API_KEY=R2CANARY_FIELD": True},  # a field name is text too
    ],
)
def test_r2_validate_refuses_unsafe_text_in_any_entry_field(tmp_path, files, bad):
    write_jsonl(
        files[1],
        [extracted("m1", r2_entry(**bad)), extracted("m3", entry("k.clean"))],
    )
    report = bf.validate(bf.read_records(*files))
    assert report["refused_unsafe"] == 1 and report["error_count"] == 1
    assert "R2CANARY" not in json.dumps(report)
    assert "sha256:" in report["errors"][0]
    assert report["rows"]["assertions"] == 1  # the clean entry still validates


def test_r2_validate_refuses_unsafe_text_in_a_supplied_export(tmp_path):
    exp = write_jsonl(
        tmp_path / "e.jsonl",
        [memory("m1", f"note {KEY_CANARY}"), memory("m2", "fine", who=SK_CANARY)],
    )
    ext = write_jsonl(
        tmp_path / "x.jsonl",
        [extracted("m1", entry("k.a")), extracted("m2", entry("k.b"))],
    )
    report = bf.validate(bf.read_records(exp, ext))
    assert report["refused_unsafe"] == 2 and report["error_count"] == 2
    assert "R2CANARY" not in json.dumps(report)


def test_r2_load_refuses_unsafe_text_even_when_validate_is_bypassed(
    tmp_path, files, monkeypatch
):
    write_jsonl(files[1], [extracted("m1", r2_entry(claim=KEY_CANARY))])
    records = bf.read_records(*files)
    monkeypatch.setattr(bf, "validate", lambda recs: {"error_count": 0})
    db = tmp_path / "agent_kv.db"
    with pytest.raises(bf.BackfillError) as err:
        bf.load(str(db), records, "X")
    assert "R2CANARY" not in str(err.value) and "sha256:" in str(err.value)
    assert not db.exists()  # the last gate runs before the database is opened


def test_r2_import_and_merge_names_must_be_safe(tmp_path, files):
    db = tmp_path / "agent_kv.db"
    with pytest.raises(bf.BackfillError) as err:
        bf.load(str(db), bf.read_records(*files), SK_CANARY)
    assert "R2CANARY" not in str(err.value) and not db.exists()
    bf.load(str(db), bf.read_records(*files), "X")
    with pytest.raises(bf.BackfillError) as err:
        bf.merge_pairs(
            str(db),
            [("guardspine.pricing.final", "guardspine.deploy.green")],
            "merge:" + SK_CANARY,
            str(tmp_path / "arc.db"),
        )
    assert "R2CANARY" not in str(err.value) and not (tmp_path / "arc.db").exists()
    with pytest.raises(bf.BackfillError):
        bf.rollback(str(db), SK_CANARY)


def test_r2_extract_refuses_unsafe_reply_entries(tmp_path):
    exp = write_jsonl(
        tmp_path / "e.jsonl", [memory("m1", "a"), memory("m2", "b"), memory("m3", "c")]
    )
    out = tmp_path / "x.jsonl"

    def model(prompt):
        return "\n".join(
            [
                json.dumps(extracted("m1", r2_entry(claim=KEY_CANARY))),
                json.dumps(extracted("m2", r2_entry(quote=TAG_CANARY))),
                json.dumps(extracted("m3", entry("k.clean"))),
            ]
        )

    report = bf.extract(str(exp), str(out), model)
    written = out.read_text(encoding="utf-8")
    assert "R2CANARY" not in written + json.dumps(report)
    assert [json.loads(x)["id"] for x in written.splitlines()] == ["m3"]
    assert report["refused_unsafe"] == 2 and report["missing"] == ["m1", "m2"]
    assert all("sha256:" in e for e in report["errors"])


def test_r2_cli_catches_every_exception_without_a_traceback(
    tmp_path, monkeypatch, capfd
):
    missing = tmp_path / "API_KEY=R2CANARY_PATH.jsonl"
    assert bf.main(["validate", "--export", str(missing), "--extracted", "b"]) == 1
    assert bf.main(["extract", "--export", "x", "--out", "y", "--model-cmd", "s",
                    "--budget", "API_KEY=R2CANARY_ARG"]) == 1  # fmt: skip

    def boom(*a):
        raise RuntimeError(KEY_CANARY)

    monkeypatch.setattr(bf, "read_records", boom)
    assert bf.main(["validate", "--export", "a", "--extracted", "b"]) == 1
    out, err = capfd.readouterr()
    assert "R2CANARY" not in out + err and "Traceback" not in out + err
    assert out.count('"error"') == 3


def test_r2_success_reports_are_scrubbed_too(tmp_path, files, capfd):
    db = tmp_path / "agent_kv.db"
    bf.load(str(db), bf.read_records(*files), "X")
    arc = tmp_path / "API_KEY=R2CANARY_ARC.db"
    assert bf.main(["archive", "--db", str(db), "--out", str(arc)]) == 0
    restore = ["restore", "--db", str(db), "--archive", str(arc), "--mode", "same_db"]
    assert bf.main(restore) == 0
    missing = ["restore", "--db", str(db), "--archive", str(tmp_path / "nope.db")]
    assert bf.main([*missing, "--mode", "same_db"]) == 1  # never created
    assert not (tmp_path / "nope.db").exists()
    out, err = capfd.readouterr()
    assert "R2CANARY" not in out + err


def test_r2_read_chroma_refuses_an_unsafe_name_before_opening_anything():
    name = "sk-" + "COLLECTIONCANARY0123456789"
    with pytest.raises(bf.BackfillError) as err:
        next(bf.read_chroma("never-opened", name))
    assert "CANARY" not in str(err.value) and sha_id(name) in str(err.value)


def test_r2_unsafe_collection_names_are_refused(tmp_path):
    out = tmp_path / "export.jsonl"
    name = "sk-" + "COLLECTIONCANARY0123456789"
    with pytest.raises(bf.BackfillError) as err:
        bf.export_records(
            {"memory_chunks": [chroma_like("c1", "t")], name: [chroma_like("c2", "t")]},
            str(out),
        )
    assert "CANARY" not in str(err.value) and sha_id(name) in str(err.value)
    assert not out.exists()


class FakeChroma:
    """A Chroma stand-in for the sweep: collections of (id, text, metadata)."""

    data = {}

    def __init__(self, path, settings):
        pass

    def get_collection(self, name, embedding_function):
        rows = FakeChroma.data[name]

        class Col:
            def count(self):
                return len(rows)

            def get(self, limit, offset, include):
                part = rows[offset : offset + limit]
                return {
                    "ids": [r[0] for r in part],
                    "documents": [r[1] for r in part],
                    "metadatas": [r[2] for r in part],
                }

        return Col()


def test_r2_canary_sweep_over_every_subcommand(tmp_path, monkeypatch, capfd):
    """Positive control for the whole leak class: canaries in every field of
    every input, then every subcommand; no canary in any output file, report,
    stdout or stderr."""
    chromadb = pytest.importorskip("chromadb")
    key, tag = "API_KEY=SWEEPCANARY_K", "< private >SWEEPCANARY_T"
    sk = "sk-" + "SWEEPCANARY0123456789ab"
    md = {"stored_at": STORED, "who": "w", "project": "p"}
    FakeChroma.data = {
        "memory_chunks": [
            ("c1", "clean memory", md),
            ("c2", f"text {key}", md),
            ("c3", "x", {**md, "who": tag}),
            (sk, "x", md),
            ("c4", "x", {**md, "project": key}),
        ],
        "agent_memories": [("a1", "agent memory", md)],
        sk: [("z1", "x", md)],
    }
    monkeypatch.setattr(chromadb, "PersistentClient", FakeChroma)
    work = tmp_path / "API_KEY=SWEEPCANARY_DIR"
    work.mkdir()
    exp, db = work / "export.jsonl", work / "kv.db"
    codes = []

    def run(*argv):
        codes.append(bf.main([str(a) for a in argv]))

    def model(prompt):
        lines = []
        for mid in re.findall(r'^\{"id": "([^"]+)"', prompt, re.M):
            lines.append(json.dumps(extracted(mid, entry("k.s", claim=key))))
            lines.append(json.dumps({"id": sk, "beliefs": [tag]}))
        return "\n".join(lines + [key, tag])

    monkeypatch.setattr(bf, "model_command", lambda cmd: model)
    seeded = [
        extracted(
            "c1",
            {**entry("k.a"), "claim": key},
            {**entry("k.b"), "quote": tag},
            {**entry("k.c"), "source_ref": sk},
        ),
        extracted("a1", entry("k.ok")),
    ]
    ext = write_jsonl(work / "seeded.jsonl", seeded)
    ok = write_jsonl(work / "ok.jsonl", [extracted("a1", entry("k.ok"))])
    pairs = work / "pairs.json"
    pairs.write_text(json.dumps([{"old": key, "new": "k.ok", "approve": True}]))
    good_pairs = work / "good.json"
    good_pairs.write_text(json.dumps([{"old": "k.ok", "new": "k.s", "approve": True}]))
    inputs = {ext, ok, pairs, good_pairs}
    load = ["load", "--db", db, "--export", exp]

    run("export", "--chroma", work / "c", "--out", exp, "--collection", sk)
    run("export", "--chroma", work / "c", "--out", exp)
    run("extract", "--export", exp, "--out", work / "x1.jsonl", "--model-cmd", "m")
    run("extract", "--export", exp, "--out", work / "x2.jsonl", "--model-cmd", "m",
        "--budget", key)  # fmt: skip
    run(
        "validate", "--export", exp, "--extracted", ext, "--review-out", work / "r.json"
    )
    run("validate", "--export", work / key, "--extracted", ext)
    run(*load, "--extracted", ext, "--import-id", "X", "--dry-run")
    run(*load, "--extracted", ext, "--import-id", "X")
    run(*load, "--extracted", ok, "--import-id", sk)
    run(*load, "--extracted", ok, "--import-id", key)
    run(*load, "--extracted", ok, "--import-id", "X")
    run("rollback", "--db", db, "--import-id", sk)
    run("merge", "--db", db, "--pairs", pairs, "--merge-id", "r1", "--archive",
        work / "m1.db")  # fmt: skip
    run("merge", "--db", db, "--pairs", good_pairs, "--merge-id", sk, "--archive",
        work / "m2.db")  # fmt: skip
    run("archive", "--db", db, "--out", work / "arc.db")
    run("archive", "--db", work / key, "--out", work / "arc2.db")
    run("restore", "--db", db, "--archive", work / sk, "--mode", "same_db")
    run("uninstall", "--db", db, "--archive", work / "arc.db")  # exists: refused
    run("uninstall", "--db", db, "--archive", work / "un.db")
    run("rollback", "--db", db, "--import-id", "X")
    out, err = capfd.readouterr()
    assert codes.count(0) >= 4 and codes.count(1) >= 12  # both kinds of path ran
    assert "SWEEPCANARY" not in out + err and "Traceback" not in err
    produced = [p for p in tmp_path.rglob("*") if p.is_file() and p not in inputs]
    assert {exp, work / "x1.jsonl", db, work / "arc.db", work / "un.db"} <= set(
        produced
    )
    for p in produced:
        assert b"SWEEPCANARY" not in p.read_bytes(), p.name
