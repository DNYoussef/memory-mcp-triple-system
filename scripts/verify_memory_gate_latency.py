"""Measure hook logic and process latency against their documented budgets."""

import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.stores.kv_store import KVStore  # noqa: E402
from src.hooks.post_tool_handler import _redact_structured  # noqa: E402


HOOKS = ROOT / "src" / "hooks"
SAMPLES = 12
LOGIC_BUDGET_MS = 100.0
PROCESS_BUDGET_MS = 350.0


def _run(script: str, payload: dict, env: dict) -> float:
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(HOOKS / script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=env,
        timeout=5,
    )
    elapsed = (time.perf_counter() - start) * 1000
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout or f"{script} failed")
    return elapsed


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="memory-gate-latency-") as temp:
        temp_path = Path(temp)
        db_path = temp_path / "agent_kv.db"
        KVStore(str(db_path)).close()
        env = os.environ.copy()
        env["MEMORY_MCP_DB"] = str(db_path)
        env["PYTHONPATH"] = str(ROOT)
        env["HOME"] = temp
        env["USERPROFILE"] = temp
        env["HOMEDRIVE"] = temp_path.drive
        env["HOMEPATH"] = str(temp_path)[len(temp_path.drive) :]

        durations = {
            "prompt": [],
            "pretool": [],
            "posttool": [],
            "user_prompt": [],
            "session_start": [],
            "stop": [],
        }
        for sample in range(SAMPLES):
            session_id = f"latency-session-{sample}"
            marker = f"marker-{sample}"
            store = KVStore(str(db_path))
            store.set(f"prompt_marker:{session_id}", marker, ttl=86400)
            store.close()
            payload = {"session_id": session_id}
            durations["prompt"].append(_run("prompt_marker_handler.py", payload, env))
            durations["pretool"].append(
                _run(
                    "pre_tool_memory_gate.py",
                    {"session_id": session_id, "tool_name": "Edit"},
                    env,
                )
            )
            large_result = {
                "session_id": session_id,
                "tool_name": "Grep",
                "tool_input": {"pattern": "latency"},
                "tool_response": [
                    {"type": "text", "text": f"match {index}"}
                    for index in range(16_000)
                ],
            }
            durations["posttool"].append(
                _run("post_tool_handler.py", large_result, env)
            )
            durations["user_prompt"].append(
                _run(
                    "user_prompt_memory_handler.py",
                    {"session_id": session_id, "prompt": "latency", "cwd": temp},
                    env,
                )
            )
            durations["session_start"].append(
                _run(
                    "session_start_handler.py",
                    {"session_id": session_id, "cwd": temp},
                    env,
                )
            )
            durations["stop"].append(_run("stop_handler.py", payload, env))

    p95 = {
        name: statistics.quantiles(values, n=20, method="inclusive")[18]
        for name, values in durations.items()
    }
    logic_durations = []
    deep_list = [{"type": "text", "text": f"match {index}"} for index in range(1_000)]
    wide_list = ["x"] * 100_000
    for _ in range(SAMPLES):
        start = time.perf_counter()
        fully_redacted = _redact_structured(deep_list, budget=1_000_000)
        _redact_structured(wide_list)
        logic_durations.append((time.perf_counter() - start) * 1000)
    if fully_redacted[-1]["text"] != "match 999":
        raise SystemExit("large-budget redaction control was truncated")
    logic_p95 = statistics.quantiles(logic_durations, n=20, method="inclusive")[18]

    slow = {name: value for name, value in p95.items() if value > PROCESS_BUDGET_MS}
    if slow:
        detail = ", ".join(f"{name}={value:.1f}" for name, value in slow.items())
        raise SystemExit(
            f"hook p95 exceeds {PROCESS_BUDGET_MS:.0f} ms process budget: {detail}"
        )
    if logic_p95 > LOGIC_BUDGET_MS:
        raise SystemExit(
            f"redaction p95 {logic_p95:.1f} ms exceeds "
            f"{LOGIC_BUDGET_MS:.0f} ms logic budget"
        )
    detail = ", ".join(f"{name}={value:.1f}" for name, value in p95.items())
    print(f"MEMORY HOOK LATENCY PASS logic={logic_p95:.1f}, {detail}")


if __name__ == "__main__":
    main()
