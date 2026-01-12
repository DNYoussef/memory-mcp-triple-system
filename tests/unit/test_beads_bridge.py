import asyncio
import json
from typing import Any, List

import pytest

from src.integrations.beads_bridge import BeadsBridge, BeadTask


class FakeProcess:
    def __init__(self, payload: Any, returncode: int = 0) -> None:
        self._payload = payload
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        stdout = json.dumps(self._payload).encode()
        return stdout, b""


@pytest.mark.asyncio
async def test_get_ready_tasks_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [{"id": "bd-1", "title": "Test", "status": "open"}]

    async def fake_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        return FakeProcess(payload)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    bridge = BeadsBridge()
    tasks = await bridge.get_ready_tasks(limit=1)

    assert isinstance(tasks, list)
    assert isinstance(tasks[0], BeadTask)
    assert tasks[0].id == "bd-1"


@pytest.mark.asyncio
async def test_get_task_detail_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"id": "bd-1", "title": "Test", "status": "open"}
    calls: List[List[str]] = []

    async def fake_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        calls.append(list(args))
        return FakeProcess(payload)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    bridge = BeadsBridge(cache_ttl=60)

    first = await bridge.get_task_detail("bd-1")
    second = await bridge.get_task_detail("bd-1")

    assert first.id == second.id
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_query_tasks_handles_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class ErrorProcess(FakeProcess):
        async def communicate(self) -> tuple[bytes, bytes]:
            return b"[]", b"error"

    async def fake_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        return ErrorProcess([], returncode=1)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    bridge = BeadsBridge()

    tasks = await bridge.query_tasks(status="open")
    assert tasks == []
