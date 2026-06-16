"""F11: a chunk whose archived metadata can't be parsed must NOT auto-rehydrate.

The legacy fallback set archived_at_ts=0.0 on a parse failure, and the
rehydration check is `archived_at_ts < cutoff`, so 0.0 is always older than the
cutoff -> corrupted metadata was silently rehydrated every sweep. Parse failures
now map to a far-future timestamp so they stay put until handled explicitly.
"""
import math

from src.memory.stage_transitions import StageTransitionsMixin


def test_unparseable_archived_date_does_not_age_into_rehydration():
    md = StageTransitionsMixin._load_archived_metadata(
        "archived_at: not-a-real-date, other: x"
    )
    ts = md.get("archived_at_ts")
    assert ts == math.inf, f"expected far-future, got {ts!r}"
    # far-future is never < a real cutoff, so it won't be auto-rehydrated
    import time
    cutoff = time.time()
    assert not (float(ts) < cutoff)


def test_valid_archived_date_still_parses():
    md = StageTransitionsMixin._load_archived_metadata(
        "archived_at: 2020-01-01T00:00:00, x: y"
    )
    assert md["archived_at_ts"] > 0 and md["archived_at_ts"] != math.inf


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
