import shutil

import pytest

from src.integrations.beads_bridge import BeadsBridge, BeadTask


@pytest.mark.asyncio
async def test_beads_bridge_real_binary() -> None:
    if shutil.which("bd") is None:
        pytest.skip("bd binary not available")
    bridge = BeadsBridge()
    tasks = await bridge.get_ready_tasks(limit=1)
    assert isinstance(tasks, list)
    if tasks:
        assert isinstance(tasks[0], BeadTask)
