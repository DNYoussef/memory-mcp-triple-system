#!/usr/bin/env python
"""Prove Beads failures are errors while empty success remains valid."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
GATE_ID = "P1b"
TOKEN = "BEADS_ERRORS_OK handlers=3 modes=3 cases=9 positive=1 http_response_beads_error=1 request_local=1"


def probe(fixture) -> bool:
    return fixture == {"cases": 9, "positive": True, "http": True, "request_local": True}


def _planted_bad_fixture():
    good = {"cases": 9, "positive": True, "http": True, "request_local": True}
    return [{**good, key: 0 if key == "cases" else False} for key in good]


async def _raise(message):
    raise RuntimeError(message)


async def _command_failures():
    from src.integrations.beads_bridge import BeadsBridge, BeadsCLIError

    bridge = BeadsBridge()

    class Process:
        def __init__(self, returncode=1):
            self.returncode = returncode

        async def communicate(self):
            return b"[]", b"failure"

        def kill(self):
            return None

        async def wait(self):
            return 0

    errors = []
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=Process())):
        try:
            await bridge._run_command(["bd"])
        except BeadsCLIError as exc:
            errors.append(exc)
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=Process(0))), patch(
        "asyncio.wait_for", new=AsyncMock(side_effect=asyncio.TimeoutError)
    ):
        try:
            await bridge._run_command(["bd"])
        except BeadsCLIError as exc:
            errors.append(exc)
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=OSError("spawn"))):
        try:
            await bridge._run_command(["bd"])
        except BeadsCLIError as exc:
            errors.append(exc)
    return errors


def _real_fixture():
    from src.mcp.request_router import (
        handle_beads_query_tasks,
        handle_beads_ready_tasks,
        handle_beads_task_detail,
    )
    from src.routing.unified_router import UnifiedRetrievalRouter
    from src.mcp import http_server

    errors = asyncio.run(_command_failures())
    tool = MagicMock()
    handlers = (
        (handle_beads_ready_tasks, "get_ready_tasks", {}),
        (handle_beads_task_detail, "get_task_detail", {"task_id": "x"}),
        (handle_beads_query_tasks, "query_tasks", {}),
    )
    cases = 0
    for handler, method, args in handlers:
        for error in errors:
            async def fail(current=error):
                raise current

            setattr(tool.beads_bridge, method, MagicMock(side_effect=lambda *a, _fail=fail, **k: _fail()))
            cases += bool(handler(args, tool).get("isError"))
    tool.beads_bridge.get_ready_tasks = MagicMock(return_value=asyncio.sleep(0, result=[]))
    positive = not bool(handle_beads_ready_tasks({}, tool).get("isError"))

    bridge = MagicMock()
    bridge.get_ready_tasks = MagicMock(side_effect=lambda **kwargs: _raise("request-a"))
    bridge.query_tasks = MagicMock(side_effect=lambda **kwargs: _raise("request-b"))
    memory = MagicMock()
    memory.process.return_value = []
    unified_router = UnifiedRetrievalRouter(bridge, memory)

    async def retrieve_both():
        return await asyncio.gather(
            unified_router.retrieve("x", mode="execution"),
            unified_router.retrieve("x", mode="planning"),
        )

    result, second = asyncio.run(retrieve_both())
    http_router = MagicMock()
    http_router.retrieve = AsyncMock(return_value=result)
    with patch.object(http_server, "get_unified_router", return_value=http_router), patch.object(
        http_server, "get_event_log", return_value=MagicMock()
    ):
        response = asyncio.run(
            http_server.unified_retrieve(
                http_server.UnifiedRetrievalRequest(query="x", mode="execution", token_budget=1000)
            )
        )
    http = response.get("beads_error") == "request-a"
    request_local = result.get("beads_error") == "request-a" and second.get("beads_error") == "request-b"
    return {"cases": cases, "positive": positive, "http": http, "request_local": request_local}


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
    print(TOKEN)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
