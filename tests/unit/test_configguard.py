"""Regression tests for ConfigGuard fail-closed behavior (MECE A3).

A3: ConfigGuard previously wrote the scanned diff to a hardcoded /tmp/ path; on
the resulting failure on Windows the bare except returned ALLOW - waving
unscanned, secret-bearing config diffs through (fail OPEN). The fix (commit
5adb4df) uses a portable NamedTemporaryFile and fails CLOSED (BLOCK) on any scan
error. These tests pin both behaviors so the gate cannot silently regress to
fail-open, and were absent when A3 sat in the untested backlog.
"""

from unittest.mock import patch

from src.guardspine.configguard.configguard import ConfigGuard


def test_gate_change_fails_closed_when_scan_raises():
    """If scanning raises, the gate must BLOCK (fail closed), never ALLOW."""
    guard = ConfigGuard()

    with patch.object(guard, "scan_file", side_effect=RuntimeError("scan boom")):
        decision = guard.gate_change("app.env", "", "password = hunter2")

    assert decision["action"] == "BLOCK"
    assert decision["risk_score"] == 1.0


def test_gate_change_blocks_secret_on_this_host():
    """End-to-end on the current host: a secret-bearing config is scanned via a
    portable temp file and BLOCKed. On the old hardcoded /tmp path this would
    have failed on Windows (and, per A3, failed open)."""
    guard = ConfigGuard()

    decision = guard.gate_change("app.env", "", "password = supersecret123")

    assert decision["action"] == "BLOCK"
    assert decision["l4_critical"] >= 1


def test_gate_change_clean_config_not_blocked_as_secret():
    """A config with no secrets is not flagged as a critical secret leak."""
    guard = ConfigGuard()

    decision = guard.gate_change("app.env", "", "log_level = info\nworkers = 4\n")

    assert decision["l4_critical"] == 0
    assert decision["action"] != "BLOCK"
