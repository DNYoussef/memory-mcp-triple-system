"""Regression tests for cross-subsystem mutation locking (MECE E7).

E7 ("no cross-scheduler lock"): the lifecycle subsystems (demote/archive/cleanup
run by LifecycleScheduler, and consolidate run by the /tools/consolidate
endpoint) all mutate the SAME Chroma collection through the singleton
MemoryLifecycleManager, and all run via asyncio.to_thread - i.e. in real worker
threads, genuinely concurrent. With no shared lock they can interleave:
delete-after-read, double-delete, phantom archive entries.

The fix gives the manager one threading.RLock (_mutation_lock) acquired by every
mutating entry point, so at most one mutation runs at a time on a given manager.
These tests are black-box: they instrument the collection/KV calls with a
concurrency probe and assert that two mutating operations never occupy their
critical sections at the same time.
"""

import threading
import time
from unittest.mock import MagicMock

from src.memory.lifecycle_manager import MemoryLifecycleManager


class _ConcurrencyProbe:
    """Records the maximum number of threads simultaneously inside a guarded
    critical section. A correct shared mutation lock keeps this at 1."""

    def __init__(self, dwell=0.03):
        self._dwell = dwell
        self._lock = threading.Lock()  # guards the counter only, NOT the SUT
        self.active = 0
        self.max_concurrent = 0

    def _occupy(self):
        with self._lock:
            self.active += 1
            if self.active > self.max_concurrent:
                self.max_concurrent = self.active
        # Widen the window so a genuine race actually overlaps in wall-clock.
        time.sleep(self._dwell)
        with self._lock:
            self.active -= 1

    def collection_get(self, *args, **kwargs):
        self._occupy()
        return {"ids": []}  # falsy -> archive finds nothing and returns 0

    def kv_cleanup(self, *args, **kwargs):
        self._occupy()
        return 0


def _manager_with_probe(probe):
    indexer = MagicMock()
    indexer.collection.get.side_effect = probe.collection_get
    kv = MagicMock()
    kv.cleanup_expired.side_effect = probe.kv_cleanup
    return MemoryLifecycleManager(indexer, kv)


def _run_concurrently(*targets):
    """Start each target on its own thread, released together by a barrier so
    they collide in their critical sections, then join."""
    barrier = threading.Barrier(len(targets))

    def wrap(fn):
        def runner():
            barrier.wait()
            fn()
        return runner

    threads = [threading.Thread(target=wrap(t)) for t in targets]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


class TestCrossSubsystemMutationLock:
    def test_distinct_mutators_do_not_interleave(self):
        """archive_demoted_chunks (Lifecycle) and cleanup_expired must serialize
        on the SHARED lock - proving the lock spans different mutating methods,
        not just re-entrancy within one. Without the lock both worker threads
        enter their critical sections at once (max_concurrent == 2)."""
        probe = _ConcurrencyProbe()
        manager = _manager_with_probe(probe)

        _run_concurrently(
            manager.archive_demoted_chunks,
            manager.cleanup_expired,
        )

        assert probe.max_concurrent == 1, (
            "archive and cleanup ran their Chroma/KV mutations concurrently; "
            "mutating operations on one manager must serialize on _mutation_lock"
        )

    def test_same_mutator_serializes_with_itself(self):
        """Two concurrent archive sweeps (e.g. scheduler + ingestion-service
        maintenance) must not both enter the critical section at once."""
        probe = _ConcurrencyProbe()
        manager = _manager_with_probe(probe)

        _run_concurrently(
            manager.archive_demoted_chunks,
            manager.archive_demoted_chunks,
        )

        assert probe.max_concurrent == 1, (
            "two concurrent archive sweeps interleaved; they must serialize"
        )
