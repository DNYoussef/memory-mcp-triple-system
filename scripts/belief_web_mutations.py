"""
Mutation run for the belief web (PLAN-B section 6.5, B-PR1).

Each mutant is a temporary text edit of src/belief_web/*.py that re-creates a
defect from the reference calculator's mutation list (belief_calc_r8.py), or
a PR1 safeguard (validation, FK, atomicity). For each mutant the script
applies the edit, runs the belief web tests, restores the original bytes and
asserts the file hash matches. Exit 0 only if the baseline passes and every
mutant is killed (some test went red).

Run from the repo root:
    PYTHONPATH=. python scripts/belief_web_mutations.py
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOLVER = ROOT / "src" / "belief_web" / "solver.py"
STORE = ROOT / "src" / "belief_web" / "belief_store.py"
TESTS = ["tests/unit/test_belief_solver.py", "tests/unit/test_belief_store.py"]

# name -> [(file, old, new, expected count)]
MUTANTS = {
    "no_cavity": [
        (
            SOLVER,
            "x = math.tanh((L[u] - sum(m[j] for j in rev[i])) / 2)",
            "x = math.tanh(L[u] / 2)",
            1,
        )
    ],
    "two_sided": [
        (
            SOLVER,
            "max(0.0, x)\n"
            '                if mode[i] == "supports"\n'
            '                else (-max(0.0, x) if mode[i] == "excludes" else min(0.0, x))',
            'x if mode[i] == "supports" else (-x if mode[i] == "excludes" else x)',
            1,
        )
    ],
    "no_norm": [
        (
            SOLVER,
            "(k, w * (CAP / into[k[1]] if into[k[1]] > CAP else 1.0))",
            "(k, w)",
            1,
        )
    ],
    "no_decay": [
        (
            SOLVER,
            "* 2 ** (-(now - e.observed_at).total_seconds() / 86400.0 / h)",
            "* 1.0",
            1,
        )
    ],
    "no_future_clamp": [
        (
            SOLVER,
            "eligible = [e for e in evidence if e.observed_at <= now and e.recorded_at <= now]",
            "eligible = list(evidence)",
            1,
        )
    ],
    "no_supersession": [(SOLVER, 'if kind in ("state", "plan"):', "if False:", 1)],
    "accept_conflict_reduce": [
        (SOLVER, 'if "supports" in types and "excludes" in types:', "if False:", 1)
    ],
    "accept_conflict_write": [
        (STORE, 'if type in ("supports", "excludes"):', "if False:", 1)
    ],
    "clamp_as_L0": [
        (
            SOLVER,
            "rules = {k: w for k, w in reduce_edges(rows).items() if k[1] not in clamp}",
            "rules = dict(reduce_edges(rows))",
            1,
        )
    ],
    "clamp_round1": [
        (
            SOLVER,
            "rules = {k: w for k, w in reduce_edges(rows).items() if k[1] not in clamp}",
            "rules = dict(reduce_edges(rows))",
            1,
        ),
        (SOLVER, "L[v] += m[i]", "L[v] += 0.0 if v in clamp else m[i]", 2),
    ],
    "no_read_dedupe": [
        (STORE, ") WHERE rk = 1 ORDER BY", ") WHERE rk >= 1 ORDER BY", 1)
    ],
    "no_alias_repoint": [
        (
            STORE,
            'c.execute("UPDATE aliases SET key=? WHERE key=?", (new, old))',
            "pass",
            1,
        )
    ],
    "merge_located_overwrite": [(STORE, "(max(loc, hloc), keep)", "(loc, keep)", 1)],
    "edge_shared_row": [
        (
            STORE,
            "            self._belief(c, origin, s)\n",
            "            if c.execute('SELECT 1 FROM edges WHERE src=? AND dst=? AND type=?', (s, d, type))"
            ".fetchone():\n"
            "                c.execute('UPDATE edges SET weight=max(weight, ?) WHERE src=? AND dst=? AND "
            "type=?', (w, s, d, type))\n"
            "                return\n"
            "            self._belief(c, origin, s)\n",
            1,
        )
    ],
    "rollback_by_key": [
        (
            STORE,
            'c.execute(f"DELETE FROM {table} WHERE origin=?", (origin,))',
            'c.execute(f"DELETE FROM {table} WHERE origin=?", (origin,)) if table != "beliefs" else '
            'c.execute("DELETE FROM beliefs WHERE key IN (SELECT key FROM beliefs WHERE origin=?)", '
            "(origin,))",
            1,
        )
    ],
    "dedupe_before_filter": [
        (
            STORE,
            '"WHERE observed_at <= ? AND recorded_at <= ?"\n'
            '            + (f" AND belief_key{flt}" if flt else "")\n'
            '            + ") WHERE rk = 1 ORDER BY',
            '"WHERE 1"\n'
            '            + (f" AND belief_key{flt}" if flt else "")\n'
            '            + ") WHERE rk = 1 AND observed_at <= ? AND recorded_at <= ? ORDER BY',
            1,
        ),
        (STORE, "(now, now, *args)", "(*args, now, now)", 1),
    ],
    "merge_mixed_tuple": [
        (
            STORE,
            "            # 2a.",
            "            for aid, o, sid, p, ch, obs in c.execute('SELECT id, origin, source_id, "
            "polarity, chunk_id, observed_at FROM assertions WHERE belief_key=?', (old,)).fetchall():\n"
            "                hit = c.execute('SELECT id FROM assertions WHERE belief_key=? AND origin=? "
            "AND source_id=? AND polarity=? AND chunk_id=?', (new, o, sid, p, ch)).fetchone()\n"
            "                if hit:\n"
            "                    c.execute('UPDATE assertions SET observed_at=min(observed_at, ?) "
            "WHERE id=?', (obs, hit[0]))\n"
            "                    c.execute('DELETE FROM assertions WHERE id=?', (aid,))\n"
            "            # 2a.",
            1,
        )
    ],
    "merge_new_seq": [
        (
            STORE,
            "c.execute(\n"
            '                "UPDATE assertions SET belief_key=? WHERE belief_key=?", (new, old)\n'
            "            )",
            "for row in c.execute('SELECT id, origin, source_id, polarity, source_type, reliability, "
            "observed_at, recorded_at, chunk_id, located, note FROM assertions WHERE belief_key=? "
            "ORDER BY seq', (old,)).fetchall():\n"
            "                c.execute('DELETE FROM assertions WHERE id=?', (row[0],))\n"
            "                self._insert_assertion(c, (row[1], new, *row[2:]))",
            1,
        )
    ],
    "collision_delete_old": [
        (
            STORE,
            "keep, drop = (aid, hid) if sq < hsq else (hid, aid)",
            "keep, drop = (hid, aid)",
            1,
        )
    ],
    "attr_priority_rowid": [
        (
            STORE,
            '"SELECT key, origin, claim, claim_seq, kind, kind_seq, half_life_days, hl_seq, "',
            '"SELECT key, origin, claim, rowid, kind, rowid, half_life_days, rowid, "',
            1,
        )
    ],
    "same_origin_dest_wins": [
        (
            STORE,
            "take = new is not None and (cur is None or new_seq < cur_seq)",
            "take = new is not None and cur is None",
            1,
        )
    ],
    "row_level_seq": [
        (
            STORE,
            "take = new is not None and (cur is None or new_seq < cur_seq)",
            "take = new is not None and (cur is None or (seq is not None and seq < row[0]))",
            1,
        ),
        (
            STORE,
            "seqs.append(new_seq if take else cur_seq)",
            "seqs.append(None if (new if take else cur) is None else "
            "(min(row[0], seq) if seq is not None else row[0]))",
            1,
        ),
    ],
    "archive_without_counter": [
        (
            STORE,
            't for t in ARCHIVE_TABLES if not (t == "belief_seq" and mode == "same_db")',
            't for t in ARCHIVE_TABLES if t != "belief_seq"',
            1,
        )
    ],
    "same_db_resets_counter": [
        (
            STORE,
            't for t in ARCHIVE_TABLES if not (t == "belief_seq" and mode == "same_db")',
            "t for t in ARCHIVE_TABLES",
            1,
        )
    ],
    "no_seq_guard": [
        (
            STORE,
            '"UPDATE belief_seq SET n = n + 1 WHERE n < ? RETURNING n"',
            '"UPDATE belief_seq SET n = n + 1 WHERE ? > 0 RETURNING n"',
            1,
        )
    ],
    "hl_ignored": [
        (STORE, "now_dt, hl, prior or 0.0", "now_dt, None, prior or 0.0", 1)
    ],
    "hl_order_desc": [
        (
            STORE,
            'rank = (origin != "live", seq)',
            'rank = (origin != "live", -seq if i == 2 else seq)',
            1,
        )
    ],
    "attrs_insert_ignore": [
        (
            STORE,
            "        vals, seqs = [], []\n",
            "        return\n        vals, seqs = [], []\n",
            1,
        )
    ],
    "fallback_all_located": [
        (STORE, "return [0] * len(chunks)", "return [1] * len(chunks)", 1),
        (
            STORE,
            'return [1 if q in " ".join(ch.casefold().split()) else 0 for ch in chunks]',
            'hits = [1 if q in " ".join(ch.casefold().split()) else 0 for ch in chunks]\n'
            "    return hits if any(hits) else [1] * len(chunks)",
            1,
        ),
    ],
    # PR1 safeguards beyond the calculator list
    "fk_off": [
        (
            STORE,
            'c.execute("PRAGMA foreign_keys=ON")',
            'c.execute("PRAGMA foreign_keys=OFF")',
            1,
        ),
        (
            STORE,
            'if c.execute("PRAGMA foreign_keys").fetchone()[0] != 1:',
            'if c.execute("PRAGMA foreign_keys").fetchone()[0] != 0:',
            1,
        ),
    ],
    "no_future_reject": [(STORE, "if obs > rec + CLOCK_SKEW:", "if False:", 1)],
    "bool_as_number": [
        (
            STORE,
            "isinstance(value, bool)\n        or not isinstance",
            "not isinstance",
            1,
        )
    ],
    "no_finite_check": [(STORE, " or not math.isfinite(value)", "", 1)],
    "batch_commits_on_error": [
        (
            STORE,
            'c.execute("ROLLBACK")',
            'c.execute("COMMIT")',
            1,
        )
    ],
    "anonymous_who_kept": [
        (
            STORE,
            'who = "unknown" if not who or who in ANONYMOUS else who',
            'who = who or "unknown"',
            1,
        )
    ],
    "rollback_any_origin": [
        (
            STORE,
            'if not validate_origin(origin).startswith("import:"):',
            "if not validate_origin(origin):",
            1,
        )
    ],
    "component_seeds_only": [
        (
            STORE,
            "scope = self._component(\n"
            "                    {self.resolve(k) for k in keys} | set(clamp), edges\n"
            "                )",
            "scope = {self.resolve(k) for k in keys} | set(clamp)",
            1,
        )
    ],
    "merge_refuse_skipped": [
        (STORE, "reduce_edges(self._effective_edges(c, rename={old: new}))", "pass", 1)
    ],
    # review r1 fixes: each mutant re-creates the reported defect
    "commit_outside_guard": [
        (
            STORE,
            '                c.execute("COMMIT" if depth == 0 else f"RELEASE sp{depth}")\n'
            "            except BaseException:",
            "                pass\n            except BaseException:",
            1,
        ),
        (
            STORE,
            "                raise\n            finally:\n                self._local.depth = depth",
            "                raise\n            else:\n"
            '                c.execute("COMMIT" if depth == 0 else f"RELEASE sp{depth}")\n'
            "            finally:\n                self._local.depth = depth",
            1,
        ),
    ],
    "prior_ignored": [(STORE, "now_dt, hl, prior or 0.0", "now_dt, hl, 0.0", 1)],
    "prior_dropped_by_merge": [
        (
            STORE,
            "self._belief(c, o, new, cl, kd, hl, pr, seq=sq, aseq=(cs, ks, hs, ps))",
            "self._belief(c, o, new, cl, kd, hl, None, seq=sq, aseq=(cs, ks, hs, None))",
            1,
        )
    ],
    "prior_unvalidated": [
        (
            STORE,
            'prior_logit = _number("prior_logit", prior_logit, -5.0, 5.0, False, False)',
            "prior_logit = prior_logit",
            1,
        )
    ],
    "sigmoid_one_branch": [
        (
            SOLVER,
            "    if x >= 0:\n        return 1 / (1 + math.exp(-x))\n"
            "    z = math.exp(x)\n    return z / (1 + z)",
            "    return 1 / (1 + math.exp(-x))",
            1,
        )
    ],
    "zero_weight_kept": [
        (
            SOLVER,
            "weights = {k: w for k, w in scaled if w > 0.0}",
            "weights = dict(scaled)",
            1,
        )
    ],
    # review r2 fix
    "nested_after_auto_rollback": [
        (STORE, "if depth and not c.in_transaction:", "if False:", 1)
    ],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tests():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--no-cov",
            *TESTS,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    failed = sorted(set(re.findall(r"^(?:FAILED|ERROR) (\S+)", proc.stdout, re.M)))
    summary = (
        proc.stdout.strip().splitlines()[-1]
        if proc.stdout.strip()
        else proc.stderr[-200:]
    )
    return proc.returncode, failed, summary


def main():
    originals = {p: (p.read_bytes(), sha(p)) for p in (SOLVER, STORE)}
    rc, failed, summary = run_tests()
    print(f"baseline: rc={rc} {summary}")
    if rc != 0:
        return 1
    # known-inert control: a comment edit must SURVIVE, or the harness cannot tell
    control = {
        "control_inert_comment": [
            (SOLVER, "K = 2.0  # message gain", "K = 2.0  # gain (control)", 1)
        ]
    }
    survived = []
    for name, edits in {**control, **MUTANTS}.items():
        try:
            for path, old, new, count in edits:
                text = path.read_text(encoding="utf-8")
                if text.count(old) != count:
                    raise SystemExit(
                        f"{name}: anchor count {text.count(old)} != {count} in {path.name}"
                    )
                path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
            rc, failed, summary = run_tests()
        finally:
            for path, (data, digest) in originals.items():
                path.write_bytes(data)
                assert sha(path) == digest, f"{path} not restored"
        killed = rc != 0
        shown = ", ".join(f.split("::")[-1] for f in failed[:4]) + (
            f" (+{len(failed) - 4})" if len(failed) > 4 else ""
        )
        print(
            f"mutation {name:26s} -> {'KILLED' if killed else 'SURVIVED'}: {shown or summary}"
        )
        if name in control:
            if killed:
                print("CONTROL KILLED: the harness reports kills for inert edits")
                return 1
        elif not killed:
            survived.append(name)
    print(
        "hashes restored: "
        + ", ".join(f"{p.name} {d[:12]}" for p, (_, d) in originals.items())
    )
    if survived:
        print("SURVIVING MUTATIONS: " + ", ".join(survived))
        return 1
    print(f"ALL {len(MUTANTS)} MUTATIONS KILLED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
