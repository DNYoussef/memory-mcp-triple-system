from datetime import datetime

from src.integrations.beads_bridge import BeadTask
from src.integrations.metadata_sync import MetadataSync


def test_beads_to_memory_mcp_mapping() -> None:
    task = BeadTask(
        id="bd-1",
        title="Task",
        description=None,
        status="open",
        priority=1,
        issue_type="bug",
        assignee="alice",
        created_at=datetime(2025, 1, 1),
        updated_at=datetime(2025, 1, 2),
    )
    sync = MetadataSync()
    metadata = sync.beads_to_memory_mcp(task, project="memory")

    assert metadata["WHO"] == "alice"
    assert metadata["PROJECT"] == "memory"
    assert metadata["WHY"] == "bug"
    assert metadata["beads"]["id"] == "bd-1"
