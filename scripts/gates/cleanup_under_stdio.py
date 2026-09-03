#!/usr/bin/env python
"""Exercise the rolling, atomic ingestion cleanup claim."""

import sqlite3
import sys
import tempfile
import threading
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
GATE_ID = "P2b"
TOKEN = "CLEANUP_UNDER_STDIO_OK expired_row_removed=1 spy_first=1 spy_second=0 reacquired_after_ttl=1 contenders=2 concurrent_runs=1 contention_safe=1"


def probe(fixture) -> bool:
    return fixture == {
        "removed": True,
        "first": 1,
        "second": 0,
        "reacquired": True,
        "contenders": 2,
        "runs": 1,
        "safe": True,
    }


def _planted_bad_fixture():
    good = {
        "removed": True,
        "first": 1,
        "second": 0,
        "reacquired": True,
        "contenders": 2,
        "runs": 1,
        "safe": True,
    }
    bad = []
    for key, value in good.items():
        bad.append({**good, key: (not value if isinstance(value, bool) else value + 1)})
    return bad


def _service(kv, lifecycle):
    from src.services.memory_ingestion_service import MemoryIngestionService

    return MemoryIngestionService(
        *(MagicMock() for _ in range(5)), lifecycle, MagicMock(), kv_store=kv
    )


def _real_fixture():
    from src.stores.kv_store import KVStore

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "gate.db"
        kv = KVStore(str(db))

        class Lifecycle:
            def __init__(self):
                self.cleanup_calls = 0

            def cleanup_expired(self):
                self.cleanup_calls += 1
                return kv.cleanup_expired()

            def demote_stale_chunks(self):
                return 0

            def archive_demoted_chunks(self):
                return 0

        lifecycle = Lifecycle()
        service = _service(kv, lifecycle)
        with closing(sqlite3.connect(db)) as con, con:
            con.execute(
                "INSERT INTO kv_store (key,value,created_at,updated_at,expires_at) VALUES (?,?,?,?,?)",
                ("expired", "x", "2000-01-01", "2000-01-01", "2000-01-01"),
            )
        service._run_lifecycle_maintenance()
        with closing(sqlite3.connect(db)) as con, con:
            removed = (
                con.execute(
                    "SELECT count(*) FROM kv_store WHERE key='expired'"
                ).fetchone()[0]
                == 0
            )
        first = lifecycle.cleanup_calls
        service._run_lifecycle_maintenance()
        second = lifecycle.cleanup_calls - first
        with closing(sqlite3.connect(db)) as con, con:
            con.execute(
                "UPDATE kv_store SET expires_at='2000-01-01' WHERE key='lifecycle:cleanup:claim'"
            )
        service._run_lifecycle_maintenance()
        reacquired = lifecycle.cleanup_calls == first + 1

        with closing(sqlite3.connect(db)) as con, con:
            con.execute(
                "UPDATE kv_store SET expires_at='2000-01-01' WHERE key='lifecycle:cleanup:claim'"
            )
        lifecycle.cleanup_calls = 0
        services = [_service(kv, lifecycle), _service(kv, lifecycle)]

        def run(item):
            item._run_lifecycle_maintenance()
            kv.close()

        threads = [threading.Thread(target=run, args=(item,)) for item in services]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        runs = lifecycle.cleanup_calls
        with patch.object(
            kv, "_transaction", side_effect=sqlite3.OperationalError("busy")
        ):
            safe = kv.set_if_absent("contended", "x", ttl=1) is False
        safe = safe and all(not thread.is_alive() for thread in threads)
        kv.close()
    return {
        "removed": removed,
        "first": first,
        "second": second,
        "reacquired": reacquired,
        "contenders": 2,
        "runs": runs,
        "safe": safe,
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
    try:
        result = _real_fixture()
    except Exception:
        result = {}
    ok = probe(result)
    if not ok:
        return 1
    print(TOKEN)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
