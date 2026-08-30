"""Verify that the effective user memory hooks are unique, enabled, and trusted."""

import json
import subprocess
import sys
import tomllib
from pathlib import Path


CODEX = Path(r"C:\Users\17175\AppData\Roaming\npm\codex.cmd")
HOOKS_PATH = Path(r"C:\Users\17175\.codex\hooks.json")
CONFIG_PATH = Path(r"C:\Users\17175\.codex\config.toml")
TEMPLATE_PATH = Path(__file__).with_name("hooks.codex.json")
REPO = Path(r"D:\Projects\memory-mcp-triple-system")
PYTHON = REPO / "venv-memory" / "Scripts" / "python.exe"
DATA_DIR = Path(r"C:\Users\17175\.claude\memory-mcp-data")
EXPECTED = {
    ("sessionStart", "session_start_handler.py"): "startup|resume|clear|compact",
    ("userPromptSubmit", "prompt_marker_handler.py"): None,
    ("userPromptSubmit", "user_prompt_memory_handler.py"): None,
    ("preToolUse", "pre_tool_memory_gate.py"): "^apply_patch$",
    ("postToolUse", "post_tool_handler.py"): None,
    ("stop", "stop_handler.py"): None,
}


def _effective_hooks():
    process = subprocess.Popen(
        [
            r"C:\Windows\System32\cmd.exe",
            "/d",
            "/c",
            str(CODEX),
            "app-server",
            "--stdio",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    def send(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "memory-gate-verifier", "version": "1"},
                    "capabilities": {"experimentalApi": True},
                },
            }
        )
        json.loads(process.stdout.readline())
        send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        send(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "hooks/list",
                "params": {"cwds": [str(REPO)]},
            }
        )
        while True:
            line = process.stdout.readline()
            if not line:
                raise RuntimeError(process.stderr.read() or "Codex app-server closed")
            response = json.loads(line)
            if response.get("id") == 2:
                return response["result"]["data"][0]
    finally:
        process.terminate()


def main():
    with CONFIG_PATH.open("rb") as stream:
        config = tomllib.load(stream)
    installed_hooks = json.loads(HOOKS_PATH.read_text(encoding="utf-8"))
    template_hooks = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    assert installed_hooks == template_hooks, "installed hooks differ from template"
    memory_env = config["mcp_servers"]["memory-mcp"]["env"]
    assert Path(memory_env["MEMORY_MCP_ROOT"]) == REPO
    assert Path(memory_env["MEMORY_MCP_DATA_DIR"]) == DATA_DIR

    result = _effective_hooks()
    assert result["warnings"] == [], result["warnings"]
    assert result["errors"] == [], result["errors"]
    expected_scripts = {script for _, script in EXPECTED}
    hooks = [
        hook
        for hook in result["hooks"]
        if Path(hook["command"].split()[-1]).name in expected_scripts
    ]
    assert len(hooks) == len(EXPECTED), f"expected 6 user hooks, found {len(hooks)}"

    seen = set()
    hook_state = config["hooks"]["state"]
    for hook in hooks:
        script = Path(hook["command"].split()[-1]).name
        identity = (hook["eventName"], script)
        assert identity in EXPECTED, f"unexpected user hook: {identity}"
        assert identity not in seen, f"duplicate user hook: {identity}"
        seen.add(identity)
        assert hook["matcher"] == EXPECTED[identity], hook
        assert hook["enabled"] is True, hook
        assert hook["trustStatus"] == "trusted", hook
        state = hook_state[hook["key"]]
        assert state["trusted_hash"] == hook["currentHash"], hook
        assert state.get("enabled", True) is True, hook
        assert hook["sourcePath"].lower() == str(HOOKS_PATH).lower(), hook
        command = hook["command"].replace("/", "\\").lower()
        assert str(PYTHON).lower() in command, hook["command"]
        assert str(REPO / "src" / "hooks").lower() in command, hook["command"]

    assert seen == set(EXPECTED)
    print("CODEX MEMORY HOOK CONFIG PASS")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, RuntimeError) as exc:
        print(f"CODEX MEMORY HOOK CONFIG FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
