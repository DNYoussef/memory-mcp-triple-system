"""Auth regression tests for Memory MCP HTTP tool routes."""

import importlib
import sys
from types import SimpleNamespace

import pytest


def _reload_http_server(
    monkeypatch: pytest.MonkeyPatch,
    *,
    key: str | None,
    alias: bool = False,
    allow_unauthenticated: bool = False,
):
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_MCP_API_KEY", raising=False)
    monkeypatch.delenv("MEMORY_MCP_ALLOW_UNAUTHENTICATED_TOOLS", raising=False)
    monkeypatch.delenv("MEMORY_MCP_HTTP_HOST", raising=False)
    if allow_unauthenticated:
        monkeypatch.setenv("MEMORY_MCP_ALLOW_UNAUTHENTICATED_TOOLS", "true")
    if key is not None:
        env_name = "MEMORY_MCP_API_KEY" if alias else "MCP_API_KEY"
        monkeypatch.setenv(env_name, key)

    sys.modules.pop("src.mcp.http_server", None)
    module = importlib.import_module("src.mcp.http_server")
    return importlib.reload(module)


def test_tool_auth_fails_closed_without_api_key(monkeypatch: pytest.MonkeyPatch):
    module = _reload_http_server(monkeypatch, key=None)

    assert not module._is_authorized_tool_request("")
    assert not module._is_authorized_tool_request("anything")


def test_tool_auth_can_be_explicitly_disabled(monkeypatch: pytest.MonkeyPatch):
    module = _reload_http_server(monkeypatch, key=None, allow_unauthenticated=True)

    assert module._is_authorized_tool_request("")


def test_http_bind_host_defaults_to_loopback(monkeypatch: pytest.MonkeyPatch):
    module = _reload_http_server(monkeypatch, key=None)

    assert module._get_http_bind_host() == "127.0.0.1"


def test_http_bind_host_can_be_explicitly_overridden(monkeypatch: pytest.MonkeyPatch):
    module = _reload_http_server(monkeypatch, key=None)
    monkeypatch.setenv("MEMORY_MCP_HTTP_HOST", "0.0.0.0")

    assert module._get_http_bind_host() == "0.0.0.0"


def test_http_metadata_normalization_drops_uppercase_aliases(monkeypatch: pytest.MonkeyPatch):
    module = _reload_http_server(monkeypatch, key="test-key")

    metadata = module._normalize_metadata({
        "WHO": "codex",
        "WHEN": "2026-06-15T12:00:00Z",
        "PROJECT": "memory-mcp-triple-system",
        "WHY": "smoke-test",
        "file_path": "/smoke/test.md",
    })

    assert metadata["who"] == "codex"
    assert metadata["when"] == "2026-06-15T12:00:00Z"
    assert metadata["project"] == "memory-mcp-triple-system"
    assert metadata["why"] == "smoke-test"
    assert not (set(metadata) & {"WHO", "WHEN", "PROJECT", "WHY"})


def test_tool_auth_uses_primary_or_alias_env(monkeypatch: pytest.MonkeyPatch):
    module = _reload_http_server(monkeypatch, key="primary-key")
    assert module.MCP_API_KEY == "primary-key"

    module = _reload_http_server(monkeypatch, key="alias-key", alias=True)
    assert module.MCP_API_KEY == "alias-key"


def test_extract_tool_api_key_prefers_explicit_header(monkeypatch: pytest.MonkeyPatch):
    module = _reload_http_server(monkeypatch, key="test-key")
    bearer = SimpleNamespace(credentials="bearer-key")

    assert module._extract_tool_api_key(bearer, "header-key") == "header-key"
    assert module._extract_tool_api_key(bearer, None) == "bearer-key"
    assert module._extract_tool_api_key(None, None) == ""


@pytest.mark.asyncio
async def test_require_tool_api_key_rejects_missing_or_wrong_token(monkeypatch: pytest.MonkeyPatch):
    module = _reload_http_server(monkeypatch, key="test-key")

    with pytest.raises(module.HTTPException) as missing_exc:
        await module.require_tool_api_key(None, None)
    assert missing_exc.value.status_code == 401

    wrong = SimpleNamespace(credentials="wrong-key")
    with pytest.raises(module.HTTPException) as wrong_exc:
        await module.require_tool_api_key(wrong, None)
    assert wrong_exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_tool_api_key_accepts_matching_token(monkeypatch: pytest.MonkeyPatch):
    module = _reload_http_server(monkeypatch, key="test-key")

    bearer = SimpleNamespace(credentials="test-key")
    await module.require_tool_api_key(bearer, None)
    await module.require_tool_api_key(None, "test-key")
