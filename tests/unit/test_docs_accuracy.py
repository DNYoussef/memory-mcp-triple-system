"""Doc-accuracy gate as a test: current-facing docs must match code reality.

Keeps scripts/check_docs.py honest in CI so doc drift fails the suite, not just
a manual run.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_current_docs_match_code():
    result = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "check_docs.py")],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": ROOT},
    )
    assert result.returncode == 0, f"doc drift:\n{result.stdout}\n{result.stderr}"
