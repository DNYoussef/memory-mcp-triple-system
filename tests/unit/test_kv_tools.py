"""KV MCP tools round-trip (B4): kv_set/kv_get/kv_delete exposed via dispatch."""
import json
from unittest.mock import Mock

from src.mcp.request_router import handle_call_tool


def _tool():
    t = Mock()
    store = {}
    t.kv_store.set.side_effect = lambda k, v, ttl=None: (
        store.__setitem__(k, v) or True
    )
    t.kv_store.get.side_effect = lambda k: store.get(k)
    t.kv_store.delete.side_effect = lambda k: (store.pop(k, None) is not None)
    return t


def test_kv_round_trip_through_dispatch():
    t = _tool()
    assert (
        handle_call_tool("kv_set", {"key": "k", "value": "V1"}, t)["isError"] is False
    )
    got = handle_call_tool("kv_get", {"key": "k"}, t)
    assert "V1" in json.dumps(got)
    handle_call_tool("kv_delete", {"key": "k"}, t)
    after = handle_call_tool("kv_get", {"key": "k"}, t)
    assert "V1" not in json.dumps(after)


def test_kv_set_requires_key():
    assert handle_call_tool("kv_set", {"value": "x"}, _tool())["isError"] is True
