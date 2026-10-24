"""
Belief store: origin-scoped SQLite tables for the belief web (PLAN-B section 2).

One ownership rule: every row carries exactly one origin (`live`,
`import:<id>` or `merge:<id>`), only references rows of its own origin, and is
never shared or upserted by another origin. The same logical fact from two
origins is two rows, reduced at read time:
- evidence: drop rows not eligible at `now`, then one contribution per
  (key, source_id, polarity), the earliest row winning by
  (observed_at, recorded_at, live first, seq); supersession is in the solver;
- edge weight: max over origins;
- attributes (claim, kind, half-life): each decided on its own, live first,
  then the smallest attribute seq.

Every tie-break reads `seq`, assigned once from the belief_seq counter and
carried unchanged through merges. No rule reads a row id. Rolling back an
import is therefore a plain DELETE by origin.

Lives in agent_kv.db next to KVStore, on its own connections with foreign
keys ON (KVStore's connections leave them off).
"""

import hashlib
import json
import math
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .solver import (
    EDGE_TYPES,
    EdgeConflict,
    Evidence,
    Solution,
    local_logodds,
    reduce_edges,
    sigmoid,
    solve,
)

KEY_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+){1,5}$")
ORIGIN_RE = re.compile(r"^(live|import:[A-Za-z0-9_.-]+|merge:[A-Za-z0-9_.-]+)$")
KINDS = ("state", "plan", "fact")
RELIABILITY_DEFAULT = {
    "witnessed": 0.95,
    "reported": 0.70,
    "inferred": 0.60,
    "assumed": 0.55,
}
ANONYMOUS = ("", "unknown", "unknown:mcp-client", "unknown:http-client")
CLOCK_SKEW = timedelta(minutes=5)
SEQ_MAX = 9223372036854775807  # SQLite signed 64-bit integer limit
ARCHIVE_TABLES = (
    "belief_seq",
    "beliefs",
    "assertions",
    "edges",
    "aliases",
)  # FK insert order
TUPLE_COLS = (
    "origin",
    "source_id",
    "polarity",
    "source_type",
    "reliability",
    "observed_at",
    "recorded_at",
    "chunk_id",
)  # the full evidence tuple, with belief_key

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS migrations (
        version TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS beliefs (
        origin TEXT NOT NULL,
        key TEXT NOT NULL,
        claim TEXT,
        kind TEXT CHECK(kind IS NULL OR kind IN ('state','plan','fact')),
        half_life_days REAL CHECK(half_life_days IS NULL OR (half_life_days > 0 AND half_life_days <= 3650)),
        prior_logit REAL CHECK(prior_logit IS NULL OR prior_logit BETWEEN -5 AND 5),
        project TEXT, entities TEXT, claim_vec BLOB, vec_model TEXT,
        seq INTEGER NOT NULL,
        claim_seq INTEGER,
        kind_seq INTEGER,
        hl_seq INTEGER,
        prior_seq INTEGER,         -- same for prior_logit (the plan gives none; same rule)
        created_at TEXT NOT NULL,
        PRIMARY KEY(origin, key))""",
    "CREATE INDEX IF NOT EXISTS idx_beliefs_key ON beliefs(key)",
    """CREATE TABLE IF NOT EXISTS assertions (
        id INTEGER PRIMARY KEY,
        origin TEXT NOT NULL,
        belief_key TEXT NOT NULL,
        source_id TEXT NOT NULL,
        polarity INTEGER NOT NULL CHECK(polarity IN (-1, 1)),
        source_type TEXT NOT NULL CHECK(source_type IN ('witnessed','reported','inferred','assumed')),
        reliability REAL NOT NULL CHECK(reliability > 0.5 AND reliability < 1.0),
        observed_at TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        chunk_id TEXT NOT NULL,
        located INTEGER NOT NULL CHECK(located IN (0, 1)),
        seq INTEGER NOT NULL UNIQUE,
        note TEXT NOT NULL DEFAULT '',
        UNIQUE(origin, belief_key, source_id, polarity, chunk_id, source_type, reliability,
               observed_at, recorded_at),
        FOREIGN KEY(origin, belief_key) REFERENCES beliefs(origin, key))""",
    "CREATE INDEX IF NOT EXISTS idx_assertions_key ON assertions(belief_key)",
    "CREATE INDEX IF NOT EXISTS idx_assertions_chunk ON assertions(chunk_id)",
    "CREATE INDEX IF NOT EXISTS idx_assertions_origin ON assertions(origin)",
    """CREATE TABLE IF NOT EXISTS edges (
        origin TEXT NOT NULL, src TEXT NOT NULL, dst TEXT NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('supports','excludes','depends_on')),
        weight REAL NOT NULL CHECK(weight > 0 AND weight <= 1),
        created_at TEXT NOT NULL,
        CHECK(src <> dst),
        PRIMARY KEY(origin, src, dst, type),
        FOREIGN KEY(origin, src) REFERENCES beliefs(origin, key),
        FOREIGN KEY(origin, dst) REFERENCES beliefs(origin, key))""",
    "CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst)",
    "CREATE TABLE IF NOT EXISTS belief_seq (n INTEGER NOT NULL)",
    "INSERT INTO belief_seq(n) SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM belief_seq)",
    """CREATE TABLE IF NOT EXISTS aliases (
        alias TEXT PRIMARY KEY,
        origin TEXT NOT NULL,
        key TEXT NOT NULL,
        FOREIGN KEY(origin, key) REFERENCES beliefs(origin, key))""",
    "INSERT OR IGNORE INTO migrations (version, description, applied_at) "
    "VALUES ('008', 'Belief web tables (beliefs, assertions, edges, belief_seq, aliases)', datetime('now'))",
)


class BeliefValidationError(ValueError):
    """An entry that must produce no rows (bad key, number, time, origin...)."""


class SeqExhausted(RuntimeError):
    """belief_seq reached the SQLite integer limit; the write rolls back."""


# ---------------------------------------------------------------- validation


def parse_ts(value: Any) -> datetime:
    """ISO 8601 (trailing Z accepted) -> aware UTC. A naive value is UTC."""
    if isinstance(value, datetime):
        d = value
    elif isinstance(value, str) and value:
        try:
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise BeliefValidationError(f"unparseable timestamp {value!r}") from exc
    else:
        raise BeliefValidationError(f"timestamp must be an ISO string, got {value!r}")
    return (
        d.replace(tzinfo=timezone.utc)
        if d.tzinfo is None
        else d.astimezone(timezone.utc)
    )


def format_ts(value: Any) -> str:
    """Stored form YYYY-MM-DDTHH:MM:SS.ffffffZ: fixed width, so text order is time order."""
    return parse_ts(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _number(
    name: str, value: Any, lo: float, hi: float, lo_open: bool, hi_open: bool
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise BeliefValidationError(f"{name} must be a finite number, got {value!r}")
    if (
        value < lo
        or value > hi
        or (lo_open and value == lo)
        or (hi_open and value == hi)
    ):
        raise BeliefValidationError(f"{name} {value!r} out of range")
    return float(value)


def validate_key(name: Any) -> str:
    if not isinstance(name, str) or not KEY_RE.match(name):
        raise BeliefValidationError(f"bad belief key {name!r}")
    return name


def validate_origin(origin: Any) -> str:
    if not isinstance(origin, str) or not ORIGIN_RE.match(origin):
        raise BeliefValidationError(f"bad origin {origin!r}")
    return origin


def source_id_for(source_ref: Optional[str], who: Optional[str], polarity: int) -> str:
    """External event ref, else testimony by reporter (section 2.3). The key is
    not part of it, so a merge cannot turn one reporter into two sources."""
    if source_ref:
        return source_ref
    who = "unknown" if not who or who in ANONYMOUS else who
    return f"testimony:{who}:{polarity}"


def locate_chunks(chunks: List[str], quote: Optional[str]) -> List[int]:
    """Section 4.1 quote rule: a single chunk is located; otherwise a chunk is
    located only if it contains the whitespace-normalized, case-folded quote.
    No quote, or a quote that matches nothing, locates no chunk."""
    if len(chunks) == 1:
        return [1]
    q = " ".join((quote or "").casefold().split())
    if not q:
        return [0] * len(chunks)
    return [1 if q in " ".join(ch.casefold().split()) else 0 for ch in chunks]


def _now_stamp() -> str:
    return format_ts(datetime.now(timezone.utc))


# ---------------------------------------------------------------- store


class BeliefStore:
    """Origin-scoped belief tables in one SQLite file. Thread-local connections."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._local = threading.local()
        with self.batch() as c:
            for stmt in SCHEMA:
                c.execute(stmt)

    def _conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
                isolation_level=None,
            )
            try:
                c.execute("PRAGMA journal_mode=WAL")
            except sqlite3.Error:
                pass  # WAL unavailable (e.g. :memory:) -- rollback journal is fine
            # Must be set outside a transaction: SQLite ignores it inside one.
            c.execute("PRAGMA foreign_keys=ON")
            if c.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                c.close()
                raise RuntimeError("SQLite build does not enforce foreign keys")
            self._local.conn = c
            self._local.depth = 0
        return c

    def close(self) -> None:
        c = getattr(self._local, "conn", None)
        if c is not None:
            c.close()
            self._local.conn = None

    @contextmanager
    def batch(self):
        """One write transaction for everything inside; nesting uses savepoints,
        so each nested call is atomic on its own and the outer block is all or
        nothing."""
        with self._lock:
            c = self._conn()
            depth = self._local.depth
            c.execute("BEGIN IMMEDIATE" if depth == 0 else f"SAVEPOINT sp{depth}")
            self._local.depth = depth + 1
            try:
                yield c
                # inside the guard: a failed COMMIT (for example a deferred FK)
                # leaves the transaction open and must be rolled back too
                c.execute("COMMIT" if depth == 0 else f"RELEASE sp{depth}")
            except BaseException:
                if c.in_transaction:  # SQLite may already have rolled back
                    if depth == 0:
                        c.execute("ROLLBACK")
                    else:
                        c.execute(f"ROLLBACK TO sp{depth}")
                        c.execute(f"RELEASE sp{depth}")
                raise
            finally:
                self._local.depth = depth

    @contextmanager
    def _read(self):
        """One consistent snapshot for a multi-query read."""
        with self._lock:
            c = self._conn()
            if self._local.depth:
                yield c
                return
            c.execute("BEGIN")
            try:
                yield c
            finally:
                c.execute("COMMIT")

    def _next_seq(self, c: sqlite3.Connection) -> int:
        """One monotonic counter for beliefs and assertions. Refused at the
        integer limit before any write, so the transaction rolls back clean."""
        row = c.execute(
            "UPDATE belief_seq SET n = n + 1 WHERE n < ? RETURNING n", (SEQ_MAX,)
        ).fetchone()
        if row is None:
            raise SeqExhausted("belief_seq exhausted at the SQLite integer limit")
        return row[0]

    def _belief(
        self,
        c,
        origin,
        key,
        claim=None,
        kind=None,
        half_life_days=None,
        prior_logit=None,
        seq=None,
        aseq=None,
    ):
        """Ensure (origin, key) and merge attributes into it (section 2.2).

        Each non-null attribute carries the seq of the statement that first
        supplied it. Each attribute independently keeps the non-null value with
        the smaller attribute seq; a NULL never wins. A fresh write's values
        get a new (later) seq, so ordinary writes fill NULLs and never
        overwrite. A merge passes the moved row's seqs. The row seq is the min
        of both: existence order only, it never decides an attribute.
        """
        inc = (claim, kind, half_life_days, prior_logit)
        row = c.execute(
            "SELECT seq, claim, kind, half_life_days, prior_logit, claim_seq, kind_seq, hl_seq, "
            "prior_seq FROM beliefs WHERE origin=? AND key=?",
            (origin, key),
        ).fetchone()
        if seq is None and (row is None or any(v is not None for v in inc)):
            seq = self._next_seq(c)
        if aseq is None:
            aseq = tuple(seq if v is not None else None for v in inc)
        if row is None:
            c.execute(
                "INSERT INTO beliefs(origin, key, claim, kind, half_life_days, prior_logit, seq, "
                "claim_seq, kind_seq, hl_seq, prior_seq, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (origin, key, *inc, seq, *aseq, _now_stamp()),
            )
            return
        vals, seqs = [], []
        for cur, cur_seq, new, new_seq in zip(row[1:5], row[5:9], inc, aseq):
            take = new is not None and (cur is None or new_seq < cur_seq)
            vals.append(new if take else cur)
            seqs.append(new_seq if take else cur_seq)
        row_seq = min(row[0], seq) if seq is not None else row[0]
        c.execute(
            "UPDATE beliefs SET claim=?, kind=?, half_life_days=?, prior_logit=?, seq=?, claim_seq=?, "
            "kind_seq=?, hl_seq=?, prior_seq=? WHERE origin=? AND key=?",
            (*vals, row_seq, *seqs, origin, key),
        )

    def resolve(self, name: str) -> str:
        """alias -> key. Aliases and keys are disjoint, so one hop is enough."""
        row = (
            self._conn()
            .execute("SELECT key FROM aliases WHERE alias=?", (name,))
            .fetchone()
        )
        return row[0] if row else name

    # ------------------------------------------------------------ writes

    def add_assertion(
        self,
        origin: str,
        key: str,
        *,
        polarity: int,
        source_type: str,
        observed_at: Any,
        recorded_at: Any,
        chunk_id: str,
        source_ref: Optional[str] = None,
        who: Optional[str] = None,
        reliability: Optional[float] = None,
        located: int = 1,
        kind: Optional[str] = None,
        claim: Optional[str] = None,
        half_life_days: Optional[float] = None,
        prior_logit: Optional[float] = None,
        note: str = "",
    ) -> None:
        """Record one assertion (evidence plus mention) and its belief row.
        Everything is validated before the first write."""
        validate_origin(origin)
        validate_key(key)
        if isinstance(polarity, bool) or polarity not in (-1, 1):
            raise BeliefValidationError(f"polarity must be -1 or 1, got {polarity!r}")
        if source_type not in RELIABILITY_DEFAULT:
            raise BeliefValidationError(f"bad source_type {source_type!r}")
        r = RELIABILITY_DEFAULT[source_type] if reliability is None else reliability
        r = _number("reliability", r, 0.5, 1.0, True, True)
        obs, rec = parse_ts(observed_at), parse_ts(recorded_at)
        if obs > rec + CLOCK_SKEW:
            raise BeliefValidationError(
                "observed_at is later than recorded_at (future observation)"
            )
        if not isinstance(chunk_id, str) or not chunk_id:
            raise BeliefValidationError("chunk_id is required")
        if isinstance(located, bool) or located not in (0, 1):
            raise BeliefValidationError(f"located must be 0 or 1, got {located!r}")
        if kind is not None and kind not in KINDS:
            raise BeliefValidationError(f"bad kind {kind!r}")
        if claim is not None and (not isinstance(claim, str) or not claim.strip()):
            raise BeliefValidationError("claim must be non-empty text")
        if half_life_days is not None:
            half_life_days = _number(
                "half_life_days", half_life_days, 0.0, 3650.0, True, False
            )
        if prior_logit is not None:
            prior_logit = _number("prior_logit", prior_logit, -5.0, 5.0, False, False)
        if source_ref is not None and (
            not isinstance(source_ref, str) or not source_ref
        ):
            raise BeliefValidationError("source_ref must be non-empty text")
        if (who is not None and not isinstance(who, str)) or not isinstance(note, str):
            raise BeliefValidationError("who and note must be text")
        sid = source_id_for(source_ref, who, polarity)
        with self.batch() as c:
            k = self.resolve(key)
            self._belief(c, origin, k, claim, kind, half_life_days, prior_logit)
            self._insert_assertion(
                c,
                (
                    origin,
                    k,
                    sid,
                    polarity,
                    source_type,
                    r,
                    format_ts(obs),
                    format_ts(rec),
                    chunk_id,
                    located,
                    note,
                ),
            )

    def _insert_assertion(self, c, row: Tuple) -> None:
        """An exact replay of the full evidence tuple is idempotent and only
        raises located."""
        c.execute(
            "INSERT INTO assertions(origin, belief_key, source_id, polarity, source_type, reliability, "
            "observed_at, recorded_at, chunk_id, located, note, seq) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(origin, belief_key, source_id, polarity, chunk_id, source_type, reliability, "
            "observed_at, recorded_at) DO UPDATE SET located = max(located, excluded.located)",
            (*row, self._next_seq(c)),
        )

    def add_edge(
        self, origin: str, src: str, dst: str, type: str, weight: float
    ) -> None:
        """Typed edge; endpoints without a row of this origin get NULL placeholders.
        Self-edges and supports plus excludes on one pair (across every origin)
        are rejected."""
        validate_origin(origin)
        validate_key(src)
        validate_key(dst)
        if type not in EDGE_TYPES:
            raise BeliefValidationError(f"bad edge type {type!r}")
        w = _number("weight", weight, 0.0, 1.0, True, False)
        with self.batch() as c:
            s, d = self.resolve(src), self.resolve(dst)
            if s == d:
                raise EdgeConflict(f"self-edge on {s}")
            if type in ("supports", "excludes"):
                other = "excludes" if type == "supports" else "supports"
                if c.execute(
                    "SELECT 1 FROM edges WHERE type=? AND ((src=? AND dst=?) OR (src=? AND dst=?)) "
                    "LIMIT 1",
                    (other, s, d, d, s),
                ).fetchone():
                    raise EdgeConflict(f"supports and excludes on one pair ({s}, {d})")
            self._belief(c, origin, s)
            self._belief(c, origin, d)
            c.execute(
                "INSERT INTO edges(origin, src, dst, type, weight, created_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(origin, src, dst, type) DO UPDATE SET weight = max(weight, excluded.weight)",
                (origin, s, d, type, w, _now_stamp()),
            )

    def merge(self, old: str, new: str, merge_id: str) -> None:
        """Merge belief `old` into `new` in one transaction (section 4.4).
        Every moved row keeps its origin, seq and full evidence tuple."""
        validate_key(old)
        validate_key(new)
        if not validate_origin(merge_id).startswith("merge:"):
            raise BeliefValidationError(
                f"merge origin must be merge:<id>, got {merge_id!r}"
            )
        with self.batch() as c:
            old, new = self.resolve(old), self.resolve(new)
            if old == new:
                raise BeliefValidationError(f"{old} and {new} are already one belief")
            if (
                c.execute(
                    "SELECT 1 FROM beliefs WHERE key=? LIMIT 1", (old,)
                ).fetchone()
                is None
            ):
                raise BeliefValidationError(f"unknown belief {old}")
            # 0. refuse before any write
            reduce_edges(self._effective_edges(c, rename={old: new}))
            # 1. beliefs, per origin, with the moved row's attribute seqs
            for o, cl, kd, hl, pr, sq, cs, ks, hs, ps in c.execute(
                "SELECT origin, claim, kind, half_life_days, prior_logit, seq, claim_seq, kind_seq, "
                "hl_seq, prior_seq FROM beliefs WHERE key=?",
                (old,),
            ).fetchall():
                self._belief(c, o, new, cl, kd, hl, pr, seq=sq, aseq=(cs, ks, hs, ps))
            # 2a. identical full tuples: the lower seq survives, located = max
            where = " AND ".join(f"{col}=?" for col in TUPLE_COLS)
            for aid, loc, sq, *tup in c.execute(
                f"SELECT id, located, seq, {', '.join(TUPLE_COLS)} "
                "FROM assertions WHERE belief_key=?",
                (old,),
            ).fetchall():
                hit = c.execute(
                    f"SELECT id, located, seq FROM assertions WHERE belief_key=? AND {where}",
                    (new, *tup),
                ).fetchone()
                if hit:
                    hid, hloc, hsq = hit
                    keep, drop = (aid, hid) if sq < hsq else (hid, aid)
                    c.execute("DELETE FROM assertions WHERE id=?", (drop,))
                    c.execute(
                        "UPDATE assertions SET located=? WHERE id=?",
                        (max(loc, hloc), keep),
                    )
            # 2b. move every remaining row; seq and tuple unchanged
            c.execute(
                "UPDATE assertions SET belief_key=? WHERE belief_key=?", (new, old)
            )
            # 3. edges, per origin; drop self-edges, collisions keep the max weight
            for o, s, d, t, w, at in c.execute(
                "SELECT origin, src, dst, type, weight, created_at FROM edges "
                "WHERE src=? OR dst=?",
                (old, old),
            ).fetchall():
                s, d = (new if s == old else s), (new if d == old else d)
                if s != d:
                    c.execute(
                        "INSERT INTO edges(origin, src, dst, type, weight, created_at) VALUES(?,?,?,?,?,?) "
                        "ON CONFLICT(origin, src, dst, type) DO UPDATE SET weight = max(weight, "
                        "excluded.weight)",
                        (o, s, d, t, w, at),
                    )
            c.execute("DELETE FROM edges WHERE src=? OR dst=?", (old, old))
            # 4. aliases targeting old: ensure (O', new), then re-point
            for (o,) in c.execute(
                "SELECT DISTINCT origin FROM aliases WHERE key=?", (old,)
            ).fetchall():
                self._belief(c, o, new)
            c.execute("UPDATE aliases SET key=? WHERE key=?", (new, old))
            # 5. nothing references old any more
            c.execute("DELETE FROM beliefs WHERE key=?", (old,))
            # 6. the merge's own placeholder and alias
            self._belief(c, merge_id, new)
            c.execute(
                "INSERT INTO aliases(alias, origin, key) VALUES(?,?,?)",
                (old, merge_id, new),
            )

    def rollback(self, origin: str) -> None:
        """Remove one import: no other origin references its rows (section 7.1)."""
        if not validate_origin(origin).startswith("import:"):
            raise BeliefValidationError(
                f"only an import can be rolled back, got {origin!r}"
            )
        with self.batch() as c:
            for table in ("aliases", "assertions", "edges", "beliefs"):
                c.execute(f"DELETE FROM {table} WHERE origin=?", (origin,))

    # ------------------------------------------------------------ reads

    def _effective_edges(
        self, c, rename: Optional[Dict[str, str]] = None
    ) -> List[Tuple[str, str, str, float]]:
        """One logical edge per (type, src, dst), weight = max over origins."""
        rename = rename or {}
        out: Dict[Tuple[str, str, str], float] = {}
        for s, d, t, w in c.execute("SELECT src, dst, type, weight FROM edges"):
            s, d = rename.get(s, s), rename.get(d, d)
            if s != d:
                out[(t, s, d)] = max(w, out.get((t, s, d), 0.0))
        return [(t, s, d, w) for (t, s, d), w in out.items()]

    @staticmethod
    def _filter(keys: Optional[Iterable[str]]) -> Tuple[str, Tuple]:
        if keys is None:
            return "", ()
        return " IN (SELECT value FROM json_each(?))", (json.dumps(sorted(keys)),)

    def _load_attrs(self, c, keys: Optional[Iterable[str]]) -> Dict[str, Tuple]:
        """Effective (claim, kind, half_life_days, prior_logit) per key: each attribute on its
        own, live first, then the smallest attribute seq. NULL means no opinion."""
        flt, args = self._filter(keys)
        best: Dict[str, List[Any]] = {}
        for key, origin, *pairs in c.execute(
            "SELECT key, origin, claim, claim_seq, kind, kind_seq, half_life_days, hl_seq, "
            "prior_logit, prior_seq FROM beliefs" + (f" WHERE key{flt}" if flt else ""),
            args,
        ):
            slot = best.setdefault(key, [None, None, None, None])
            for i in range(4):
                value, seq = pairs[2 * i], pairs[2 * i + 1]
                rank = (origin != "live", seq)
                if value is not None and (slot[i] is None or rank < slot[i][0]):
                    slot[i] = (rank, value)
        return {k: tuple(s[1] if s else None for s in slot) for k, slot in best.items()}

    def _load_evidence(
        self, c, now: str, keys: Optional[Iterable[str]]
    ) -> Dict[str, List[Evidence]]:
        """Filter on time first, then one row per (key, source, polarity), the
        earliest winning. The order matters: grouping first lets an ineligible
        copy hide an eligible one (fixture RD)."""
        flt, args = self._filter(keys)
        out: Dict[str, List[Evidence]] = {}
        for key, sid, pol, st, r, obs, rec, chunk in c.execute(
            "SELECT belief_key, source_id, polarity, source_type, reliability, observed_at, recorded_at, "
            "chunk_id FROM (SELECT *, row_number() OVER (PARTITION BY belief_key, source_id, polarity "
            "ORDER BY observed_at, recorded_at, origin <> 'live', seq) AS rk FROM assertions "
            "WHERE observed_at <= ? AND recorded_at <= ?"
            + (f" AND belief_key{flt}" if flt else "")
            + ") WHERE rk = 1 ORDER BY belief_key, observed_at, recorded_at, seq",
            (now, now, *args),
        ):
            out.setdefault(key, []).append(
                Evidence(pol, r, st, parse_ts(obs), parse_ts(rec), sid, chunk)
            )
        return out

    @staticmethod
    def _component(seeds: Iterable[str], edges) -> set:
        adj: Dict[str, List[str]] = {}
        for _, s, d, _ in edges:
            adj.setdefault(s, []).append(d)
            adj.setdefault(d, []).append(s)
        seen, todo = set(seeds), list(seeds)
        while todo:
            for nxt in adj.get(todo.pop(), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        return seen

    def solve(
        self,
        now: Any,
        keys: Optional[Iterable[str]] = None,
        clamp: Optional[Dict[str, float]] = None,
    ) -> Solution:
        """Solve from the current rows at `now`; no cache (section 3.4). With
        `keys`, only their connected component (plus clamped beliefs) is solved;
        components are independent, so the answer is the same. Clamps are
        hypothetical and never written."""
        now_s = format_ts(now)
        now_dt = parse_ts(now_s)
        with self._read() as c:
            clamp = {self.resolve(k): v for k, v in (clamp or {}).items()}
            edges = self._effective_edges(c)
            scope = None
            if keys is not None:
                scope = self._component(
                    {self.resolve(k) for k in keys} | set(clamp), edges
                )
                edges = [e for e in edges if e[1] in scope]
            attrs = self._load_attrs(c, scope)
            evidence = self._load_evidence(c, now_s, scope)
        L0 = {}
        for k in set(attrs) | (scope or set()):
            _, kind, hl, prior = attrs.get(k, (None, None, None, None))
            L0[k] = local_logodds(
                evidence.get(k, []), kind or "state", now_dt, hl, prior or 0.0
            ).L
        return solve(L0, edges, clamp)

    def probability(self, name: str, now: Any) -> float:
        key = self.resolve(name)
        return sigmoid(self.solve(now, keys=[key]).L[key])

    def attrs(self, name: str) -> Dict[str, Any]:
        """Effective attributes; display falls back to the key, kind to state."""
        key = self.resolve(name)
        with self._read() as c:
            claim, kind, hl, prior = self._load_attrs(c, [key]).get(
                key, (None, None, None, None)
            )
        return {
            "claim": claim if claim is not None else key,
            "kind": kind or "state",
            "half_life_days": hl,
            "prior_logit": prior,
        }

    def evidence(self, name: str, now: Any) -> List[Evidence]:
        """Representative evidence (eligible, one per source and polarity), before supersession."""
        key = self.resolve(name)
        with self._read() as c:
            return self._load_evidence(c, format_ts(now), [key]).get(key, [])

    def exists(self, name: str) -> bool:
        return (
            self._conn()
            .execute("SELECT 1 FROM beliefs WHERE key=? LIMIT 1", (self.resolve(name),))
            .fetchone()
            is not None
        )

    def mentions(self, name: str) -> List[Tuple[str, int, int]]:
        return sorted(
            self._conn()
            .execute(
                "SELECT chunk_id, polarity, located FROM assertions WHERE belief_key=?",
                (self.resolve(name),),
            )
            .fetchall()
        )

    # ------------------------------------------------------------ archive (section 7.2)

    def _table_digest(self, c, schema: str, table: str) -> Tuple[int, str]:
        rows = sorted(c.execute(f"SELECT * FROM {schema}.{table}").fetchall(), key=repr)
        return len(rows), hashlib.sha256(repr(rows).encode()).hexdigest()

    def archive(self, path: str) -> Dict[str, int]:
        """Copy the four belief tables AND the seq counter to a new file, then
        verify row counts and hashes. Refuses to overwrite an existing file."""
        if Path(path).exists():
            raise FileExistsError(path)
        with self._lock:
            c = self._conn()
            c.execute("ATTACH DATABASE ? AS belief_archive", (str(path),))
            try:
                with self.batch():
                    for t in ARCHIVE_TABLES:
                        c.execute(
                            f"CREATE TABLE belief_archive.{t} AS SELECT * FROM main.{t}"
                        )
                with self._read():
                    for t in ARCHIVE_TABLES:
                        if self._table_digest(c, "main", t) != self._table_digest(
                            c, "belief_archive", t
                        ):
                            raise RuntimeError(f"archive verification failed for {t}")
                    return {
                        t: self._table_digest(c, "main", t)[0] for t in ARCHIVE_TABLES
                    }
            finally:
                c.execute("DETACH DATABASE belief_archive")

    def restore(self, path: str, mode: str) -> None:
        """Replace the belief rows with an archive in one transaction.
        mode "fresh": into a new schema, counter from the archive.
        mode "same_db": merge-batch undo; the live counter is kept, because it is
        already above every archived seq."""
        if mode not in ("fresh", "same_db"):
            raise ValueError(f"restore mode must be fresh or same_db, got {mode!r}")
        tables = [
            t for t in ARCHIVE_TABLES if not (t == "belief_seq" and mode == "same_db")
        ]
        with self._lock:
            c = self._conn()
            c.execute("ATTACH DATABASE ? AS belief_archive", (str(path),))
            try:
                with self.batch():
                    for t in reversed(tables):
                        c.execute(f"DELETE FROM main.{t}")
                    for t in tables:
                        c.execute(
                            f"INSERT INTO main.{t} SELECT * FROM belief_archive.{t}"
                        )
            finally:
                c.execute("DETACH DATABASE belief_archive")
