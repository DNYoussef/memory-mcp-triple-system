#!/usr/bin/env python
"""Create or verify the exclusive pre-change baseline artifact."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT = REPO / "audits/baseline-2026-09-03.json"
GATE_ID = "P0-5"


def _digest(data):
    body = {key: value for key, value in data.items() if key != "sha256"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def probe(fixture) -> bool:
    return (
        fixture.get("sha256_match")
        and fixture.get("rewrite_refused")
        and fixture.get("acceptance") == "12 PASS | 0 XFAIL | 0 FAIL"
        and fixture.get("pytest_passed", 0) > 0
        and fixture.get("collected", 0) > 0
        and fixture.get("nodeids", 0) > 0
        and fixture.get("p95_store_ms", -1) >= 0
        and fixture.get("p95_unified_ms", -1) >= 0
        and fixture.get("coverage", -1) >= 0
        and fixture.get("tools", 0) > 0
        and fixture.get("provenance")
    )


def _planted_bad_fixture():
    good = {
        "sha256_match": True,
        "rewrite_refused": True,
        "acceptance": "12 PASS | 0 XFAIL | 0 FAIL",
        "pytest_passed": 1,
        "collected": 1,
        "nodeids": 1,
        "p95_store_ms": 0,
        "p95_unified_ms": 0,
        "coverage": 1.0,
        "tools": 1,
        "provenance": True,
    }
    bad = []
    for key, value in good.items():
        if key == "acceptance":
            replacement = "bad"
        elif key in ("p95_store_ms", "p95_unified_ms", "coverage"):
            replacement = -1
        elif isinstance(value, bool):
            replacement = False
        else:
            replacement = 0
        bad.append({**good, key: replacement})
    return bad


def _run(args, env=None):
    return subprocess.run(args, cwd=REPO, env=env, text=True, capture_output=True)


def _measure():
    collected = _run([sys.executable, "-m", "pytest", "tests", "--collect-only", "-q", "--no-cov"])
    nodeids = sorted(line for line in collected.stdout.splitlines() if "::" in line and not line.startswith("<"))
    tests = _run([sys.executable, "-m", "pytest", "tests", "--no-cov", "-q"])
    passed_match = re.search(r"(\d+) passed", tests.stdout)
    acceptance = _run([sys.executable, "scripts/acceptance_all_parts.py"])
    summary = re.search(r"12 PASS \| 0 XFAIL \| 0 FAIL", acceptance.stdout)
    with tempfile.TemporaryDirectory() as tmp:
        bench_path = Path(tmp) / "bench.json"
        env = os.environ.copy()
        env.update({"BENCH_OUT": str(bench_path), "BENCH_WARM": "3"})
        bench = _run([sys.executable, "scripts/bench_tools.py"], env)
        bench_data = json.loads(bench_path.read_text(encoding="utf-8")) if bench.returncode == 0 else {"rows": []}
    rows = {row["tool"]: row for row in bench_data["rows"]}
    coverage = _run([sys.executable, "-m", "pytest", "tests", "--cov=src", "--cov-fail-under=0", "-q"])
    total = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%", coverage.stdout, re.MULTILINE)
    sys.path.insert(0, str(REPO))
    from src.mcp.tool_registry import get_tool_definitions

    if any(run.returncode for run in (collected, tests, acceptance, bench, coverage)) or not (passed_match and summary and total):
        raise RuntimeError("baseline command failed")
    data = {
        "acceptance": summary.group(0),
        "pytest_passed": int(passed_match.group(1)),
        "collected": len(nodeids),
        "nodeids": nodeids,
        "p95_store_ms": rows["memory_store"]["warm_p95_ms"],
        "p95_unified_ms": rows["unified_search"]["warm_p95_ms"],
        "coverage": float(total.group(1)),
        "tools": len(get_tool_definitions()),
        "git_head": _run(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "git_tree": _run(["git", "rev-parse", "HEAD^{tree}"]).stdout.strip(),
        "checkpoint_clean": True,
    }
    data["sha256"] = _digest(data)
    return data


def _real_fixture(path=DEFAULT):
    path = Path(path)
    data = json.loads(path.read_text(encoding="ascii"))
    rewrite = _run([sys.executable, "scripts/gates/baseline.py", "--write", "--path", str(path)])
    rewrite_refused = rewrite.returncode == 2 and "BASELINE_EXISTS" in rewrite.stdout
    commit = _run(["git", "cat-file", "-e", f"{data.get('git_head')}^{{commit}}"])
    tree = _run(["git", "rev-parse", f"{data.get('git_head')}^{{tree}}"])
    return {
        "sha256_match": data.get("sha256") == _digest(data),
        "rewrite_refused": rewrite_refused,
        "acceptance": data.get("acceptance"),
        "pytest_passed": data.get("pytest_passed", 0),
        "collected": data.get("collected", 0),
        "nodeids": len(data.get("nodeids", [])),
        "p95_store_ms": data.get("p95_store_ms", -1),
        "p95_unified_ms": data.get("p95_unified_ms", -1),
        "coverage": data.get("coverage", -1),
        "tools": data.get("tools", 0),
        "provenance": commit.returncode == 0 and tree.stdout.strip() == data.get("git_tree") and data.get("checkpoint_clean") is True,
    }


def self_test() -> bool:
    for bad in _planted_bad_fixture():
        assert not probe(bad)
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        self_test_ok = self_test()
        if not self_test_ok:
            return 1
        print(f"SELF_TEST_REJECTED {GATE_ID}")
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--path", type=Path, default=DEFAULT)
    args = parser.parse_args(argv)
    if args.verify:
        args.path = args.verify
    if args.write:
        if _run(["git", "status", "--porcelain"]).stdout.strip():
            print("BASELINE_DIRTY_WORKTREE")
            return 3
        try:
            handle = args.path.open("x", encoding="ascii")
        except FileExistsError:
            print(f"BASELINE_EXISTS {args.path}")
            return 2
        try:
            data = _measure()
            json.dump(data, handle, indent=2)
            handle.write("\n")
        except Exception:
            handle.close()
            args.path.unlink(missing_ok=True)
            raise
        finally:
            handle.close()
    result = _real_fixture(args.path)
    ok = probe(result)
    if not ok:
        return 1
    print(
        "BASELINE_OK sha256_match=1 rewrite_refused=1 "
        f"acceptance=\"{result['acceptance']}\" pytest_passed={result['pytest_passed']} "
        f"collected={result['collected']} nodeids={result['nodeids']} p95_store_ms={round(result['p95_store_ms'])} "
        f"p95_unified_ms={round(result['p95_unified_ms'])} cov={result['coverage']:.1f} tools={result['tools']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
