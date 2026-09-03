#!/usr/bin/env python
"""Measure coverage and require a non-regressive configured floor."""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE_ID = "P5"


def probe(fixture) -> bool:
    return fixture.get("configured", 0) > 0 and fixture.get("configured") == int(fixture.get("measured", -1))


def _planted_bad_fixture():
    return [{"configured": 0, "measured": 20.0}, {"configured": 21, "measured": 20.0}]


def _real_fixture():
    config = (REPO / "pytest.ini").read_text(encoding="utf-8")
    configured = re.search(r"--cov-fail-under=(\d+)", config)
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--cov=src", "--cov-fail-under=0", "-q"],
        cwd=REPO,
        text=True,
        capture_output=True,
    )
    total = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%", run.stdout, re.MULTILINE)
    return {
        "configured": int(configured.group(1)) if configured else 0,
        "measured": float(total.group(1)) if run.returncode == 0 and total else -1,
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
    result = _real_fixture()
    ok = probe(result)
    if not ok:
        return 1
    print(f"COVERAGE_RATCHET_OK configured={result['configured']} measured={result['measured']:.1f} ok=1")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
