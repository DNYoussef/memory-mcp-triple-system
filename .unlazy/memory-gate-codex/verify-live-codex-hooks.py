"""Exercise the installed memory gate through real Codex lifecycle events."""

import json
import shutil
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


CODEX = Path(r"C:\Users\17175\AppData\Roaming\npm\codex.cmd")
TMP_ROOT = Path(r"C:\Users\17175\.codex-tmp")
DB = Path(r"C:\Users\17175\.claude\memory-mcp-data\agent_kv.db")
HANDOFF_DIR = DB.parent
SESSIONS_ROOT = Path(r"C:\Users\17175\.codex\sessions")


def _complete(command):
    started = datetime.now(timezone.utc)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    thread = next(event for event in events if event.get("type") == "thread.started")
    session_id = thread["thread_id"]
    if str(uuid.UUID(session_id)) != session_id:
        raise RuntimeError("Codex returned an invalid session id")
    return session_id, started, datetime.now(timezone.utc), result


def _run(workspace, prompt, ephemeral=True):
    command = [
        r"C:\Windows\System32\cmd.exe",
        "/d",
        "/c",
        str(CODEX),
        "exec",
        "--approve-for-me",
        "--skip-git-repo-check",
    ]
    if ephemeral:
        command.append("--ephemeral")
    command.extend(["-C", str(workspace), "--json", prompt])
    return _complete(command)


def _resume(session_id, prompt):
    return _complete(
        [
            r"C:\Windows\System32\cmd.exe",
            "/d",
            "/c",
            str(CODEX),
            "exec",
            "--approve-for-me",
            "resume",
            "--skip-git-repo-check",
            "--json",
            session_id,
            prompt,
        ]
    )


def _value(connection, key):
    row = connection.execute(
        "SELECT value FROM kv_store WHERE key = ?", (key,)
    ).fetchone()
    return None if row is None else row[0]


def _tool_diagnostics(result):
    tools = []
    for line in result.stdout.splitlines():
        event = json.loads(line)
        item = event.get("item", {})
        if item.get("type") == "mcp_tool_call":
            tools.append(
                {
                    "tool": item.get("tool") or item.get("name"),
                    "status": item.get("status"),
                }
            )
    return tools


def _timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _assert_first_run(connection, session_id, workspace):
    marker = _value(connection, f"prompt_marker:{session_id}")
    assert marker, "first run has no prompt marker"
    assert (
        _value(connection, f"recall_nudge:{session_id}:{marker}") == "1"
    ), "first edit did not record a denial nudge"
    assert (
        _value(connection, f"recall:{session_id}:{marker}") is None
    ), "first run unexpectedly received retrieval credit"
    assert (
        _value(connection, f"last_edit_at:{session_id}") is None
    ), "denied edit was recorded as successful"
    assert not (workspace / "denied.txt").exists(), "denied edit reached disk"


def _assert_second_dirty(connection, session_id, started, ended, workspace):
    marker = _value(connection, f"prompt_marker:{session_id}")
    assert marker, "second run has no prompt marker"
    assert (
        _value(connection, f"recall:{session_id}:{marker}") == "1"
    ), "second run has no retrieval receipt"
    assert (
        _value(connection, f"recall_nudge:{session_id}:{marker}") is None
    ), "credited edit was denied"
    edit = _value(connection, f"last_edit_at:{session_id}")
    saved = _value(connection, f"last_save_at:{session_id}")
    assert edit, "second run has no edit timestamp"
    assert saved is None, "second run saved before the Stop proof"
    assert (
        _value(connection, f"stop_nudge:{session_id}") == "1"
    ), "real Codex Stop did not execute the blocking path"
    assert started <= _timestamp(edit) <= ended, "edit timestamp is stale"
    assert (workspace / "allowed.txt").read_text(
        encoding="utf-8"
    ) == "CODEX_GATE_ALLOWED\n", "allowed edit content is wrong"


def _assert_recovery(connection, session_id, started, ended, diagnostics):
    edit = _value(connection, f"last_edit_at:{session_id}")
    saved = _value(connection, f"last_save_at:{session_id}")
    assert saved, "Stop recovery did not record a save timestamp; tools=" + json.dumps(
        diagnostics
    )
    assert _timestamp(saved) >= _timestamp(edit), "save timestamp predates the edit"
    assert started <= _timestamp(saved) <= ended, "save timestamp is stale"
    assert _value(connection, f"skip:{session_id}") is None, "waiver was not consumed"


def _cleanup(connection, session_ids):
    for session_id in session_ids:
        connection.execute(
            "DELETE FROM kv_store WHERE key LIKE ?",
            (f"%:{session_id}:%",),
        )
        connection.execute(
            "DELETE FROM kv_store WHERE key LIKE ?",
            (f"%:{session_id}",),
        )
        handoff = HANDOFF_DIR / f"current_session-{session_id}.json"
        if handoff.exists():
            handoff.unlink()
    connection.commit()
    sessions_root = SESSIONS_ROOT.resolve()
    for session_id in session_ids:
        for transcript in SESSIONS_ROOT.rglob(f"*-{session_id}.jsonl"):
            if transcript.resolve().is_relative_to(sessions_root):
                transcript.unlink()


def main():
    run_root = TMP_ROOT / f"memory-gate-codex-live-{uuid.uuid4().hex}"
    first = run_root / "first"
    second = run_root / "second"
    first.mkdir(parents=True)
    second.mkdir()
    session_ids = []
    connection = sqlite3.connect(DB, timeout=30)
    try:
        first_id, _, _, _ = _run(
            first,
            "Do not call any memory tool. Use apply_patch exactly once to create "
            "denied.txt containing CODEX_GATE_DENIED. If the hook denies it, do not "
            "retry. Reply exactly CODEX_GATE_DENIAL_OBSERVED.",
        )
        session_ids.append(first_id)
        _assert_first_run(connection, first_id, first)

        second_id, started, ended, _ = _run(
            second,
            "Your first action must be a call to the memory_mcp unified_search tool "
            "with query CODEX_GATE_RETRIEVAL. Do not substitute another tool. After "
            "that call succeeds, use apply_patch to create allowed.txt with "
            "exactly CODEX_GATE_ALLOWED and a newline. Do not save or waive before "
            "your Stop attempt. Reply exactly CODEX_GATE_DIRTY_STOP.",
            ephemeral=False,
        )
        session_ids.append(second_id)
        _assert_second_dirty(connection, second_id, started, ended, second)

        resumed_at = datetime.now(timezone.utc)
        resumed_id, _started, recovered_at, result = _resume(
            second_id,
            "Your first and mandatory action is to call the kv_set tool from "
            'memory_mcp with key "skip:'
            + second_id
            + '", value "live Codex gate recovery", and ttl 86400. Wait for '
            "that tool to succeed before replying CODEX_GATE_RECOVERED.",
        )
        assert resumed_id == second_id, "Codex resumed the wrong session"
        _assert_recovery(
            connection,
            second_id,
            resumed_at,
            recovered_at,
            _tool_diagnostics(result),
        )
        print("CODEX MEMORY GATE LIVE PASS")
    finally:
        _cleanup(connection, session_ids)
        connection.close()
        if run_root.parent == TMP_ROOT and run_root.name.startswith(
            "memory-gate-codex-live-"
        ):
            shutil.rmtree(run_root, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except (
        AssertionError,
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        StopIteration,
        subprocess.TimeoutExpired,
        TypeError,
        ValueError,
    ) as exc:
        print(f"CODEX MEMORY GATE LIVE FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
