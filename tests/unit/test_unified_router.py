import pytest

from src.integrations.beads_bridge import BeadTask
from src.routing.unified_router import UnifiedRetrievalRouter


class FakeBeadsBridge:
    async def get_ready_tasks(self, limit: int = 10, brief: bool = True):
        return [
            BeadTask(
                id="bd-1",
                title="Task one",
                description="short desc",
                status="open",
                priority=1,
                issue_type="task",
                assignee=None,
                created_at=None,
                updated_at=None,
            )
        ]

    async def query_tasks(self, *args, **kwargs):
        return await self.get_ready_tasks()


class FakeMemoryService:
    async def semantic_search(self, query: str, mode: str, top_k: int, token_budget: int):
        return {"core": [{"text": "memory"}], "extended": []}


@pytest.mark.asyncio
async def test_retrieve_combines_sources() -> None:
    router = UnifiedRetrievalRouter(FakeBeadsBridge(), FakeMemoryService())
    result = await router.retrieve("test", mode="execution", token_budget=200)

    assert result["mode"] == "execution"
    assert result["beads"]
    assert result["memory"]["core"]
