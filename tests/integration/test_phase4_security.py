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


def test_post_tool_hook_redacts_secret_output_and_preserves_normal_text(tmp_path, monkeypatch):
    db_path = tmp_path / "agent_kv.db"
    session_file = tmp_path / "current_session.json"
    KVStore(str(db_path)).close()
    session_file.write_text(
        json.dumps({"session_id": "phase4-session", "project": "memory-mcp"}),
        encoding="utf-8",
    )

    monkeypatch.setenv("MEMORY_MCP_DB", str(db_path))
    monkeypatch.setattr(post_tool_handler, "SESSION_FILE", str(session_file))
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "echo normal"},
                    "tool_output": (
                        "normal output line "
                        "OPENAI_API_KEY=sk-live-secret-value-1234567890 "
                        "Bearer eyJhbGciOiJsecretsecret"
                    ),
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
    assert "OPENAI_API_KEY=[REDACTED]" in content
    assert "sk-live-secret-value" not in content
    assert "eyJhbGciOiJsecretsecret" not in content
