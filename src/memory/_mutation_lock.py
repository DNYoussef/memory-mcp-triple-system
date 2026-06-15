"""Shared mutation-serialization primitive for the lifecycle subsystems.

The lifecycle subsystems (stage transitions, consolidation, cleanup) all mutate
the same Chroma collection through one MemoryLifecycleManager instance, and the
server runs them via asyncio.to_thread - in real worker threads, concurrently.
Without serialization they race (delete-after-read, double-delete, phantom
archive entries).

`guarded_mutation` decorates a manager method so it acquires the instance's
shared `_mutation_lock` (a threading.RLock created in
MemoryLifecycleManager.__init__) for the duration of the call. RLock is used so
that if one guarded method ever calls another on the same thread it re-enters
rather than self-deadlocking. This module imports nothing from the memory
package, so it is safe to import from any of the mixins without a cycle.
"""

import functools


def guarded_mutation(method):
    """Serialize a mutating manager method on the instance's _mutation_lock."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._mutation_lock:
            return method(self, *args, **kwargs)

    return wrapper
