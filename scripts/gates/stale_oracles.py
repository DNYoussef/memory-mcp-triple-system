#!/usr/bin/env python
"""Reject stale, superseded root-level verification scripts."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

GATE_ID = "P0-3"
TARGETS = (
    "gate0_verify.py",
    "gate1_verify.py",
    "gate2_verify.py",
    "gate4_verify.py",
    "test_rlm_quick.py",
    "test_all_14_tools.py",
    "test_rlm_organ_map.py",
    "tests/test_all_14_tools.py",
)


def probe(fixture) -> bool:
    return fixture.get("deleted") == 8 and fixture.get("references") == 0 and fixture.get("excluded", 0) > 0


def _planted_bad_fixture():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / TARGETS[0]).write_text("stale", encoding="ascii")
        (root / "consumer.py").write_text("gate0_verify.py", encoding="ascii")
        (root / "audits").mkdir()
        (root / "audits/report.md").write_text("gate1_verify.py", encoding="ascii")
        scanned = _real_fixture(root)
        return [
            scanned,
            {"deleted": 8, "references": 1, "excluded": 1},
            {"deleted": 8, "references": 0, "excluded": 0},
        ]


def _real_fixture(root=None):
    root = Path(root or Path(__file__).resolve().parents[2])
    present = sum((root / name).exists() for name in TARGETS)
    references = 0
    excluded = {".git", "audits", "archive"}
    needles = {Path(name).name for name in TARGETS}
    excluded_count = 0
    git_files = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    paths = [root / line for line in git_files.stdout.splitlines()] if git_files.returncode == 0 else root.rglob("*")
    for path in paths:
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith("docs/connascence/") or rel == "scripts/gates/stale_oracles.py":
            excluded_count += 1
            continue
        if any(part in excluded for part in path.relative_to(root).parts):
            excluded_count += 1
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        references += sum(name in text for name in needles)
    return {"deleted": len(TARGETS) - present, "references": references, "excluded": excluded_count}


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
    parser.add_argument("--root")
    args = parser.parse_args(argv)
    result = _real_fixture(args.root)
    ok = probe(result)
    if not ok:
        return 1
    print(
        f"STALE_ORACLES_GONE absent={result['deleted']} refs={result['references']} "
        f"excluded_scan_artifacts={result['excluded']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
