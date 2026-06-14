"""Regression tests for LifecycleScheduler cadence (MECE E6).

E6 ("hour-0-only cleanup"): the scheduler gated archival on
`current_hour % 6 == 0` and expired-entry cleanup on `current_hour == 0`
(wall-clock midnight). The loop sleeps ~3600s, so if the process is not alive
at that exact hour - or the loop drifts past the boundary - the sweep is
skipped entirely and stage stats carry unswept expired rows.

The fix gates on ELAPSED TIME since the last run (archival every 6h, cleanup
every 24h) anchored to process start, so the cadence no longer depends on which
wall-clock hour the loop happens to fire. These tests pin two invariants:
cleanup/archival run at a non-midnight hour, and they respect their minimum
interval (no over-sweeping every cycle).
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.memory.lifecycle_scheduler import LifecycleScheduler


def _manager():
    manager = MagicMock()
    manager.demote_stale_chunks.return_value = 0
    manager.archive_demoted_chunks.return_value = 0
    manager.cleanup_expired.return_value = 0
    return manager


class TestSchedulerCadence:
    @pytest.mark.asyncio
    async def test_cleanup_and_archival_run_at_nonzero_hour(self):
        """Starting at 03:00 - NOT midnight and NOT a multiple of 6 - cleanup and
        archival must still run within the first cycle. Under the old wall-clock
        gate they would be skipped here (and every cycle until the process
        happened to be alive at hour 0 / a multiple of 6)."""
        manager = _manager()
        scheduler = LifecycleScheduler(manager)
        scheduler._running = True

        async def stop_after_first(_seconds):
            scheduler._running = False

        fake_now = datetime(2024, 1, 1, 3, 0, 0)
        with patch("src.memory.lifecycle_scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            with patch("asyncio.sleep", side_effect=stop_after_first):
                await scheduler._run_loop()

        manager.demote_stale_chunks.assert_called_once()
        manager.archive_demoted_chunks.assert_called_once()
        manager.cleanup_expired.assert_called_once()

    @pytest.mark.asyncio
    async def test_intervals_are_respected_across_cycles(self):
        """Two cycles one hour apart: demotion runs every cycle, but archival
        (6h) and cleanup (24h) run only once - the minimum interval has not
        elapsed for the second cycle, so they must not re-sweep."""
        manager = _manager()
        scheduler = LifecycleScheduler(manager)
        scheduler._running = True

        sleeps = {"n": 0}

        async def advance(_seconds):
            sleeps["n"] += 1
            if sleeps["n"] >= 2:
                scheduler._running = False

        # First cycle establishes the baseline (last_* is None -> run); second
        # cycle is only 1h later, below both the 6h and 24h thresholds.
        times = [datetime(2024, 1, 1, 3, 0, 0), datetime(2024, 1, 1, 4, 0, 0)]
        with patch("src.memory.lifecycle_scheduler.datetime") as mock_dt:
            mock_dt.now.side_effect = times
            with patch("asyncio.sleep", side_effect=advance):
                await scheduler._run_loop()

        assert manager.demote_stale_chunks.call_count == 2
        manager.archive_demoted_chunks.assert_called_once()
        manager.cleanup_expired.assert_called_once()
