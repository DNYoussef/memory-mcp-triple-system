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
    assert len("".join(report["errors"])) <= bf.ERROR_BUDGET + 100
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
    report = bf.export_records(records, str(out))
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
                             "stored_at": STORED, "project": "gs", "who": "alice"}  # fmt: skip
    dump = out.read_text(encoding="utf-8")
    assert not re.search(r"(?i)<\s*/?\s*private", dump)
    assert "hidden" not in dump
    assert report["exported"] == 5
    assert report["excluded"] == {"private_residue": 3, "missing_stored_at": 1}
    assert report["excluded_ids"] == ["spaced", "stray", "who_tag", "no_time"]


def test_export_refuses_to_overwrite(tmp_path):
    out = tmp_path / "export.jsonl"
    out.write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        bf.export_records([chroma_like("a", "t")], str(out))
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
    with pytest.raises(SystemExit):
        bf.main(["load"])  # no default database path
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
