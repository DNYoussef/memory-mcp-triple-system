import asyncio
import json
from typing import Any, List

import pytest

from src.integrations.beads_bridge import BeadsBridge, BeadsCLIError, BeadTask


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
async def test_get_task_detail_accepts_list_from_bd_show(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # bd show <id> --json returns a one-element list, not a bare object.
    payload = [{"id": "mem-0rn", "title": "Probe", "status": "open", "priority": 3}]

    async def fake_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        return FakeProcess(payload)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    task = await BeadsBridge().get_task_detail("mem-0rn")

    assert task.id == "mem-0rn"
    assert task.title == "Probe"


@pytest.mark.asyncio
async def test_get_task_detail_reads_comment_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # bd 0.47.1 emits comment content as "text"; older payloads used "body".
    payload = [
        {
            "id": "mem-0rn",
            "title": "Probe",
            "status": "open",
            "comments": [
                {
                    "id": 1,
                    "author": "DNYoussef",
                    "text": "Important note",
                    "created_at": "2026-10-23T00:38:53Z",
                },
                {"author": "legacy", "body": "Old body"},
            ],
        }
    ]

    async def fake_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        return FakeProcess(payload)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    task = await BeadsBridge().get_task_detail("mem-0rn")

    assert [c.body for c in task.comments] == ["Important note", "Old body"]


@pytest.mark.asyncio
async def test_get_task_detail_list_without_match_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [{"id": "other-1", "title": "Other", "status": "open"}]

    async def fake_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        return FakeProcess(payload)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    task = await BeadsBridge().get_task_detail("mem-0rn")

    assert task.title == BeadTask.empty("mem-0rn").title


@pytest.mark.asyncio
async def test_query_tasks_handles_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class ErrorProcess(FakeProcess):
        async def communicate(self) -> tuple[bytes, bytes]:
            return b"[]", b"error"

    async def fake_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        return ErrorProcess([], returncode=1)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    bridge = BeadsBridge()

    with pytest.raises(BeadsCLIError, match="error"):
        await bridge.query_tasks(status="open")
