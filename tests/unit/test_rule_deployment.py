"""Regression tests for RuleDeploymentService remove changes (MECE H4).

H4 ("remove unguarded"): the remove branch of _apply_change did
content.replace(change.current_value, "") with no guards. Two failure modes:
  - no-op: if current_value was absent, replace did nothing but the method
    still returned (True, "") - a false success (modify guards this, remove
    did not), and the dry-run path only checked file existence for remove.
  - strip file-wide: replace removes EVERY occurrence, so a current_value that
    appears more than once is stripped throughout the file.

The fix guards remove like modify (non-empty + present, in both dry-run and
deployment) and removes a single occurrence (count=1) instead of all.
"""

from src.services.improvement.rule_deployment import RuleDeploymentService
from src.services.improvement.outcome_schema import RuleChange


def _svc(tmp_path):
    return RuleDeploymentService(base_path=str(tmp_path))


def _remove(rule_path, current_value):
    return RuleChange(
        rule_path=rule_path,
        change_type="remove",
        current_value=current_value,
    )


class TestRemoveChange:
    def test_absent_value_fails_instead_of_silent_noop(self, tmp_path):
        f = tmp_path / "rules.md"
        f.write_text("alpha\nbeta\n", encoding="utf-8")
        change = _remove("rules.md", "gamma")  # not present

        success, err = _svc(tmp_path)._apply_change(change, dry_run=False)

        assert success is False
        assert err  # a real error message
        assert f.read_text(encoding="utf-8") == "alpha\nbeta\n"  # untouched

    def test_removes_single_occurrence_not_file_wide(self, tmp_path):
        f = tmp_path / "rules.md"
        f.write_text("RULE-X\nkeep me\nRULE-X\n", encoding="utf-8")
        change = _remove("rules.md", "RULE-X")

        success, err = _svc(tmp_path)._apply_change(change, dry_run=False)

        assert success is True
        remaining = f.read_text(encoding="utf-8")
        assert remaining.count("RULE-X") == 1, "remove stripped the value file-wide"
        assert "keep me" in remaining

    def test_empty_current_value_fails(self, tmp_path):
        f = tmp_path / "rules.md"
        f.write_text("alpha\n", encoding="utf-8")
        change = _remove("rules.md", "")

        success, err = _svc(tmp_path)._apply_change(change, dry_run=False)

        assert success is False
        assert f.read_text(encoding="utf-8") == "alpha\n"

    def test_dry_run_validates_value_present(self, tmp_path):
        f = tmp_path / "rules.md"
        f.write_text("alpha\n", encoding="utf-8")
        change = _remove("rules.md", "missing")

        # Dry run must predict the real failure, not just check file existence.
        success, err = _svc(tmp_path)._apply_change(change, dry_run=True)

        assert success is False

    def test_verify_agrees_with_single_occurrence_remove(self, tmp_path):
        # A repeated value leaves one occurrence after remove; verify must not
        # call that a failure (it used to require complete absence).
        f = tmp_path / "rules.md"
        f.write_text("RULE-X\nkeep\nRULE-X\n", encoding="utf-8")
        svc = _svc(tmp_path)
        change = _remove("rules.md", "RULE-X")

        ok, _ = svc._apply_change(change, dry_run=False)
        assert ok is True
        assert svc._verify_change(change)["verified"] is True

    def test_verify_without_apply_is_not_proven(self, tmp_path):
        # No _apply_change ran, so a still-present value must NOT verify as a
        # successful remove (guards against unapplied/reverted removes).
        f = tmp_path / "rules.md"
        f.write_text("RULE-X\nRULE-X\n", encoding="utf-8")
        svc = _svc(tmp_path)
        result = svc._verify_change(_remove("rules.md", "RULE-X"))
        assert result["verified"] is False

    def test_remove_unique_value_succeeds(self, tmp_path):
        f = tmp_path / "rules.md"
        f.write_text("alpha\nREMOVE ME\nbeta\n", encoding="utf-8")
        change = _remove("rules.md", "REMOVE ME\n")

        success, err = _svc(tmp_path)._apply_change(change, dry_run=False)

        assert success is True
        remaining = f.read_text(encoding="utf-8")
        assert "REMOVE ME" not in remaining
        assert "alpha" in remaining and "beta" in remaining
