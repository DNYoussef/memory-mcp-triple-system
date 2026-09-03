#!/usr/bin/env python
"""Exercise one trace write for every registered tool through both routers."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
GATE_ID = "P2a"


def probe(fixture) -> bool:
    return (
        fixture.get("tools", 0) > 0
        and fixture.get("rows_expected") == fixture.get("rows_actual")
        and fixture.get("error_rows", 0) > 0
        and fixture.get("isolated")
    )


def _planted_bad_fixture():
    good = {"tools": 18, "rows_expected": 36, "rows_actual": 36, "error_rows": 1, "isolated": True}
    return [
        {**good, "tools": 0},
        {**good, "rows_actual": 35},
        {**good, "error_rows": 0},
        {**good, "isolated": False},
    ]


def _real_fixture():
    import src.mcp.request_router as router
    import src.mcp.stdio_server as stdio
    from src.mcp.tool_registry import get_tool_definitions

    names = [item["name"] for item in get_tool_definitions()]
    writes = []
    tool = MagicMock()
    tool.config = {"paths": {"data_dir": "."}}

    class Trace:
        def log(self, db_path=None):
            writes.append((db_path, bool(getattr(self, "error", None))))
            return True

    tool.create_query_trace.side_effect = lambda *args, **kwargs: Trace()
    patches = {}
    for attr in vars(router):
        if attr.startswith("handle_") and attr != "handle_call_tool":
            patches[attr] = MagicMock(return_value={"content": [], "isError": attr.endswith("kv_delete")})
    with patch.multiple(router, **patches):
        for name in names:
            router.handle_call_tool(name, {}, tool)
            stdio.handle_call_tool(name, {}, tool)
        before = len(writes)

        class BrokenTrace(Trace):
            def log(self, db_path=None):
                raise OSError("read only")

        tool.create_query_trace.side_effect = lambda *args, **kwargs: BrokenTrace()
        isolated = router.handle_call_tool(names[0], {}, tool).get("isError") is False and len(writes) == before
    return {
        "tools": len(names),
        "rows_expected": len(names) * 2,
        "rows_actual": len(writes),
        "error_rows": sum(error for _, error in writes),
        "isolated": isolated,
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
    print(
        f"TRACE_EVERY_TOOL_OK tools={result['tools']} rows_expected={result['rows_expected']} "
        f"rows_actual_match=1 error_rows={result['error_rows']} trace_failure_isolated=1"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
