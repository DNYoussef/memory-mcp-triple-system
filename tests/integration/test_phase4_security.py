"""Phase 4 security regressions."""

import io
import json
import subprocess
import sys
from pathlib import Path

from src.hooks import post_tool_handler
from src.stores.kv_store import KVStore


def test_vector_search_validation_survives_python_optimized_mode():
    repo_root = Path(__file__).resolve().parents[2]
    script = """
from src.mcp.tools.vector_search import VectorSearchTool

try:
    VectorSearchTool({})
except ValueError as exc:
    assert "Missing embeddings config" in str(exc)
else:
    raise SystemExit("constructor validation did not run")

tool = VectorSearchTool({"embeddings": {}, "storage": {"vector_db": {}}})
for query, limit, expected in [
    ("", 5, "Query cannot be empty"),
    ("hello", 0, "Limit must be positive"),
    ("hello", 101, "Limit too large"),
]:
    try:
        tool.execute(query, limit)
    except ValueError as exc:
        assert expected in str(exc), str(exc)
    else:
        raise SystemExit(f"execute validation did not run for {expected}")
"""
    result = subprocess.run(
        [sys.executable, "-O", "-c", script],
        cwd=repo_root,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr + result.stdout


def test_load_config_missing_path_survives_python_optimized_mode(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    missing = tmp_path / "missing.yaml"
    script = f"""
from pathlib import Path
from src.mcp.service_wiring import load_config

try:
    load_config(Path(r"{missing}"))
except FileNotFoundError as exc:
    assert "Config not found" in str(exc)
else:
    raise SystemExit("load_config validation did not run")
"""
    result = subprocess.run(
        [sys.executable, "-O", "-c", script],
        cwd=repo_root,
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr + result.stdout


def test_post_tool_hook_redacts_secret_output_and_preserves_normal_text(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "agent_kv.db"
    session_file = tmp_path / "current_session.json"
    KVStore(str(db_path)).close()
    session_file.write_text(
        json.dumps({"session_id": "phase4-session", "project": "memory-mcp"}),
        encoding="utf-8",
    )

    monkeypatch.setenv("MEMORY_MCP_DB", str(db_path))
    monkeypatch.setattr(post_tool_handler, "_session_file", lambda _: str(session_file))
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "session_id": "phase4-hook-session",
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": (
                            'echo normal PASSWORD="alpha \\"beta\\" gamma" '
                            "Authorization: Basic dXNlcjpwYXNzd29yZA=="
                        )
                    },
                    "tool_response": {
                        "PASSWORD": "hunter2",
                        "OPENAI_API_KEY": "sk-live-secret-value-1234567890",
                        "Authorization": "Digest username=admin secret=topsecret",
                        "normal": "normal output line",
                    },
                }
            )
        ),
    )

    post_tool_handler.main()

    store = KVStore(str(db_path))
    try:
        observations = store.get_observations(session_id="phase4-session")
    finally:
        store.close()

    assert len(observations) == 1
    content = observations[0]["content"]
    assert "normal output line" in content
    assert "'PASSWORD': '[REDACTED]'" in content
    assert "'OPENAI_API_KEY': '[REDACTED]'" in content
    assert "hunter2" not in content
    assert "alpha" not in content
    assert "beta" not in content
    assert "gamma" not in content
    assert "dXNlcjpwYXNzd29yZA" not in content
    assert "sk-live-secret-value" not in content


def test_structured_redaction_handles_multiple_keys_and_stable_placeholders():
    value = {
        "PASSWORD": "hunter2",
        "OPENAI_API_KEY": "sk-live-secret-value-1234567890",
        "Authorization": "Basic dXNlcjpwYXNzd29yZA==",
        "sk-secret-key-material-123456": "first secret used as a key",
        "sk-other-key-material-654321": "second secret used as a key",
        "normal": "keep me",
    }
    first = post_tool_handler._redact_structured(value)
    second = post_tool_handler._redact_structured(value)

    assert first == second
    assert first["normal"] == "keep me"
    assert first["PASSWORD"] == "[REDACTED]"
    assert first["OPENAI_API_KEY"] == "[REDACTED]"
    assert first["Authorization"] == "[REDACTED]"
    redacted_keys = [key for key in first if key.startswith("[REDACTED_KEY_")]
    assert len(redacted_keys) == 2
    assert "[REDACTED_KEY_ce342576]" in first
    assert "sk-secret-key-material-123456" not in json.dumps(first)
    assert "sk-other-key-material-654321" not in json.dumps(first)


def test_dict_failure_records_error_observation(tmp_path, monkeypatch):
    db_path = tmp_path / "agent_kv.db"
    session_file = tmp_path / "current_session.json"
    KVStore(str(db_path)).close()
    session_file.write_text(
        json.dumps({"session_id": "error-session", "project": "memory-mcp"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MEMORY_MCP_DB", str(db_path))
    monkeypatch.setattr(post_tool_handler, "_session_file", lambda _: str(session_file))
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "session_id": "error-hook-session",
                    "tool_name": "mcp__memory-mcp__memory_store",
                    "tool_input": {"text": "normal"},
                    "tool_response": {"content": [], "isError": True},
                }
            )
        ),
    )

    post_tool_handler.main()
    store = KVStore(str(db_path))
    try:
        observations = store.get_observations(session_id="error-session")
    finally:
        store.close()
    assert len(observations) == 1
    assert observations[0]["metadata"]["is_error"] is True


def test_builtin_failure_records_error_observation(tmp_path, monkeypatch):
    db_path = tmp_path / "agent_kv.db"
    session_file = tmp_path / "current_session.json"
    KVStore(str(db_path)).close()
    session_file.write_text(
        json.dumps({"session_id": "builtin-error-session", "project": "memory-mcp"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MEMORY_MCP_DB", str(db_path))
    monkeypatch.setattr(post_tool_handler, "_session_file", lambda _: str(session_file))
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "session_id": "builtin-error-hook-session",
                    "tool_name": "Bash",
                    "tool_input": {"command": "exit 1"},
                    "tool_response": {"success": False, "stderr": "fatal"},
                }
            )
        ),
    )

    post_tool_handler.main()
    store = KVStore(str(db_path))
    try:
        observations = store.get_observations(session_id="builtin-error-session")
    finally:
        store.close()
    assert len(observations) == 1
    assert observations[0]["metadata"]["is_error"] is True


def test_post_tool_hook_redacts_legacy_string_output(tmp_path, monkeypatch):
    db_path = tmp_path / "agent_kv.db"
    session_file = tmp_path / "current_session.json"
    KVStore(str(db_path)).close()
    session_file.write_text(
        json.dumps({"session_id": "legacy-session", "project": "memory-mcp"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MEMORY_MCP_DB", str(db_path))
    monkeypatch.setattr(post_tool_handler, "_session_file", lambda _: str(session_file))
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "session_id": "legacy-hook-session",
                    "tool_name": "Bash",
                    "tool_input": {"command": "echo normal"},
                    "tool_output": (
                        "normal output PASSWORD=legacy-secret "
                        "<private>private-secret</private>"
                    ),
                }
            )
        ),
    )

    post_tool_handler.main()
    store = KVStore(str(db_path))
    try:
        content = store.get_observations(session_id="legacy-session")[0]["content"]
    finally:
        store.close()
    assert "normal output" in content
    assert "legacy-secret" not in content
    assert "private-secret" not in content


def test_bounded_redaction_hides_secrets_split_at_preview_boundary():
    value = {
        "pad": "y" * 400,
        "command": "z" * 75 + "<private>TOPSECRET</private>",
        "PASSWORD": "hunter2",
        "notes": "kept",
    }
    redacted = post_tool_handler._redact_structured(value)
    serialized = json.dumps(redacted)
    assert set(redacted) == set(value)
    assert "TOPSECRET" not in serialized
    assert "hunter2" not in serialized
