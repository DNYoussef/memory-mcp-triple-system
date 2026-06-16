"""Acceptance gate for the observation auto-capture pipeline wiring.

Guards the two regressions that made `observation_timeline` return empty:

  Bug #2 (read path): the MCP runtime built its KVStore on "kv_store.db" while
      the capture hooks wrote to "agent_kv.db" -- reads and writes hit different
      files. Guarded by test_runtime_uses_canonical_db_name.

  Bug #1 (write path): the PostToolUse/SessionStart/Stop hooks were never wired
      into Claude Code's settings, so nothing was captured at all. Guarded by
      test_claude_settings_wire_capture_hooks.

The existing tests/unit/test_e2e_autocapture.py injects ONE store into both the
writer and reader, so it cannot catch a writer/reader file-path mismatch. This
gate asserts the PRODUCTION wiring instead.

Hermetic: every DB lives under tmp_path. Canary-asserted: a unique marker string
must survive the round trip, not merely "non-empty".
"""

import io
import json
import os
from pathlib import Path


from src.stores.kv_store import KVStore, DEFAULT_DB_NAME
from src.models.observation_types import Session
from src.services.observation_bridge import ObservationBridge

REPO_ROOT = Path(__file__).resolve().parents[2]


# --- Bug #2: runtime and hooks must resolve the SAME database file -----------

def test_canonical_db_name_is_agent_kv():
    """The one source of truth for the store filename."""
    assert DEFAULT_DB_NAME == "agent_kv.db"


def test_hook_default_db_uses_canonical_name():
    """The capture hooks must target the canonical DB filename."""
    from src.hooks import post_tool_handler, session_start_handler, stop_handler

    for mod in (post_tool_handler, session_start_handler, stop_handler):
        assert os.path.basename(mod.DEFAULT_DB) == DEFAULT_DB_NAME, (
            f"{mod.__name__}.DEFAULT_DB={mod.DEFAULT_DB} drifted from "
            f"{DEFAULT_DB_NAME}"
        )


def test_runtime_uses_canonical_db_name():
    """service_wiring and http_server must build KVStore on DEFAULT_DB_NAME.

    Fails before the fix: both hardcode the literal "kv_store.db" for the
    runtime KVStore, so observation_timeline reads an empty file.
    """
    wiring = (REPO_ROOT / "src" / "mcp" / "service_wiring.py").read_text(encoding="utf-8")
    http = (REPO_ROOT / "src" / "mcp" / "http_server.py").read_text(encoding="utf-8")

    # The exact divergent constructions that caused the bug must be gone.
    assert 'data_dir / "kv_store.db"' not in wiring, (
        "service_wiring still builds the runtime KVStore on kv_store.db"
    )
    assert 'data_dir, "kv_store.db"' not in http, (
        "http_server still builds the runtime KVStore on kv_store.db"
    )
    # ...and they must reference the shared constant.
    assert "DEFAULT_DB_NAME" in wiring
    assert "DEFAULT_DB_NAME" in http


def test_runtime_resolver_yields_canonical_db(tmp_path, monkeypatch):
    """Behavioral guard: the REAL runtime resolver must build its KVStore on
    agent_kv.db, not just contain the constant in source (kills grep false-pass).
    """
    import importlib

    monkeypatch.setenv("MEMORY_MCP_DATA_DIR", str(tmp_path))
    http = importlib.import_module("src.mcp.http_server")
    monkeypatch.setattr(http, "_kv_store", None, raising=False)

    store = http.get_kv_store()
    assert Path(store.db_path).name == DEFAULT_DB_NAME
    assert Path(store.db_path).parent == tmp_path  # resolver honored the env dir


def test_observation_written_by_writer_is_seen_by_reader(tmp_path):
    """Canary round trip across two KVStores on the SAME canonical file.

    Models production: the hook writes via one KVStore instance, the MCP
    runtime reads via another. They must point at the same file.
    """
    db = tmp_path / DEFAULT_DB_NAME
    canary = "CANARY-obs-7f3a9c"

    writer = KVStore(str(db))
    session = Session(project="gate-test")
    writer.create_session(session.to_dict())
    bridge = ObservationBridge(kv_store=writer)
    bridge.capture_tool_use(
        session_id=session.session_id,
        tool_name="Bash",
        tool_input={"command": canary},
        tool_result="ok",
        project="gate-test",
    )
    writer.close()

    reader = KVStore(str(db))  # independent instance, same file
    obs = reader.get_observations(project="gate-test")
    reader.close()

    assert any(canary in o["content"] for o in obs), (
        "reader could not see the observation the writer stored"
    )


# --- Bug #1: the capture hooks must actually run end to end ------------------

def test_post_tool_handler_captures_observation(tmp_path, monkeypatch):
    """Drive the real PostToolUse handler and confirm it persists a canary.

    Proves the handler logic is healthy -- so the empty timeline was wiring,
    not a broken handler.
    """
    from src.hooks import post_tool_handler as h

    db = tmp_path / DEFAULT_DB_NAME
    session_file = tmp_path / "current_session.json"
    canary = "CANARY-hook-b2e1d8"

    store = KVStore(str(db))
    session = Session(project="hook-test")
    store.create_session(session.to_dict())
    store.close()

    session_file.write_text(json.dumps(
        {"session_id": session.session_id, "project": "hook-test"}
    ))

    monkeypatch.setattr(h, "SESSION_FILE", str(session_file))
    monkeypatch.setenv("MEMORY_MCP_DB", str(db))
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": canary},
        "tool_result": "done",
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))

    h.main()

    store = KVStore(str(db))
    obs = store.get_observations(session_id=session.session_id)
    store.close()
    assert any(canary in o["content"] for o in obs), (
        "PostToolUse handler did not persist the observation"
    )


def test_claude_settings_wire_capture_hooks():
    """Claude Code settings must wire all three capture hooks.

    Fails before the fix: neither settings.json nor settings.local.json has a
    hooks block, so the PostToolUse handler never runs.
    """
    claude_dir = Path.home() / ".claude"
    # Assert the FULL handler script path, not just the basename -- a hook
    # pointing at the wrong repo would silently run unfixed code.
    hooks_dir = "D:/Projects/memory-mcp-triple-system/src/hooks"
    wanted = {
        "PostToolUse": f"{hooks_dir}/post_tool_handler.py",
        "SessionStart": f"{hooks_dir}/session_start_handler.py",
        "Stop": f"{hooks_dir}/stop_handler.py",
    }

    merged_hooks = {}
    for name in ("settings.json", "settings.local.json"):
        p = claude_dir / name
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        merged_hooks.update(data.get("hooks", {}) or {})

    missing = []
    for event, cmd_path in wanted.items():
        entries = merged_hooks.get(event)
        # Normalize backslashes so the check is path-separator agnostic.
        blob = json.dumps(entries).replace("\\\\", "/").replace("\\", "/") if entries else ""
        if not entries or cmd_path not in blob:
            missing.append(f"{event} -> {cmd_path}")
    assert not missing, f"capture hooks not wired (or wrong path) in settings: {missing}"
