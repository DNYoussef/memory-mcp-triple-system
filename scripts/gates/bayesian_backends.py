#!/usr/bin/env python
"""Run the acceptance harness under both Bayesian backends."""

import os
import ast
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE_ID = "P1d"
TOKEN = "BAYESIAN_BACKENDS_OK pgmpy=12 lightweight=12 adapter_removed=1"


def probe(fixture) -> bool:
    return fixture == {"pgmpy": 12, "lightweight": 12, "adapter_removed": True}


def _planted_bad_fixture():
    good = {"pgmpy": 12, "lightweight": 12, "adapter_removed": True}
    return [{**good, key: 0 if key != "adapter_removed" else False} for key in good]


def _run(backend):
    env = os.environ.copy()
    env["MEMORY_MCP_BAYESIAN_BACKEND"] = backend
    run = subprocess.run(
        [sys.executable, "scripts/acceptance_all_parts.py"],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
    )
    match = re.search(r"(\d+) PASS \| 0 XFAIL \| 0 FAIL", run.stdout)
    identity = subprocess.run(
        [sys.executable, "-c", "import src.bayesian as b; print(b.BAYESIAN_BACKEND)"],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
    )
    observed = identity.stdout.strip().splitlines()[-1] if identity.returncode == 0 and identity.stdout.strip() else ""
    return int(match.group(1)) if run.returncode == 0 and match else 0, observed


def _real_fixture():
    source = (REPO / "src/nexus/tier_queries.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_query_bayesian_conditional")
    handlers = [node for node in ast.walk(method) if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name) and node.type.id == "TypeError"]
    bare_return = any(isinstance(node, ast.Return) for node in method.body)
    pgmpy, pgmpy_backend = _run("pgmpy")
    lightweight, lightweight_backend = _run("lightweight")
    return {
        "pgmpy": pgmpy if pgmpy_backend == "pgmpy" else 0,
        "lightweight": lightweight if lightweight_backend == "lightweight" else 0,
        "adapter_removed": not handlers and bare_return,
    }


def self_test() -> bool:
    for bad in _planted_bad_fixture():
        assert not probe(bad)
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        self_test_ok = self_test()
        if not self_test_ok:
            return 1
        print(f"SELF_TEST_REJECTED {GATE_ID}")
        return 0
    result = _real_fixture()
    ok = probe(result)
    if not ok:
        return 1
    print(TOKEN)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
