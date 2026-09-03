#!/usr/bin/env python
"""Verify computed deletion closure, tests, imports, and lint."""

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/gates"))
from reachability import analyze

GATE_ID = "P3"


def _write_checkpoint(path):
    if _run(["git", "status", "--porcelain"]).stdout.strip():
        print("CHECKPOINT_DIRTY_WORKTREE")
        return 3
    target = Path(path)
    data = {
        "sha": _run(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "tree": _run(["git", "rev-parse", "HEAD^{tree}"]).stdout.strip(),
        "checkpoint_clean": True,
        "writer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    try:
        with target.open("x", encoding="ascii") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
    except FileExistsError:
        print(f"CHECKPOINT_EXISTS {target}")
        return 2
    print(f"CHECKPOINT_WRITTEN {target}")
    return 0


def probe(fixture) -> bool:
    return (
        fixture.get("dead_remaining") == 0
        and fixture.get("allowed_dead") == 0
        and fixture.get("call_named")
        and fixture.get("checkpoint_clean")
        and fixture.get("artifact_gone")
        and fixture.get("deleted", 0) > 0
        and fixture.get("tools", 0) > 0
        and fixture.get("nodeid_exact")
        and fixture.get("derivation")
        and fixture.get("lint")
        and fixture.get("passed", 0) > 0
        and fixture.get("failed") == 0
        and fixture.get("errors") == 0
    )


def _planted_bad_fixture():
    good = {
        "dead_remaining": 0,
        "allowed_dead": 0,
        "call_named": True,
        "checkpoint_clean": True,
        "artifact_gone": True,
        "deleted": 1,
        "tools": 18,
        "nodeid_exact": True,
        "derivation": True,
        "lint": True,
        "passed": 1,
        "failed": 0,
        "errors": 0,
    }
    bad = []
    for key, value in good.items():
        if key in ("dead_remaining", "allowed_dead", "failed", "errors"):
            replacement = 1
        elif isinstance(value, bool):
            replacement = False
        else:
            replacement = 0
        bad.append({**good, key: replacement})
    return bad


def _run(args, cwd=REPO):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)


def _collect(cwd):
    run = _run([sys.executable, "-m", "pytest", "tests", "--collect-only", "-q", "-o", "addopts="], cwd)
    return run, {line for line in run.stdout.splitlines() if "::" in line and not line.startswith("<")}


def _dead_modules(sha):
    run = _run(["git", "diff", "--name-status", sha, "--", "src"])
    paths = [line.split("\t", 1)[1] for line in run.stdout.splitlines() if line.startswith("D\t") and line.endswith(".py")]
    return {path[:-3].replace("/", ".") for path in paths}


def _function(tree, parts):
    wanted = [part.split("[", 1)[0] for part in parts]
    nodes = tree.body
    found = None
    for name in wanted:
        found = next((node for node in nodes if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name), None)
        if found is None:
            return None
        nodes = getattr(found, "body", [])
    return found


def _uses_dead(node, tree, dead):
    aliases = {}
    for item in tree.body:
        if isinstance(item, ast.Import):
            for alias in item.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(item, ast.ImportFrom) and item.module:
            for alias in item.names:
                target = f"{item.module}.{alias.name}"
                aliases[alias.asname or alias.name] = target if target in dead else item.module
    for item in ast.walk(node):
        if isinstance(item, ast.Import):
            for alias in item.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(item, ast.ImportFrom) and item.module:
            for alias in item.names:
                target = f"{item.module}.{alias.name}"
                aliases[alias.asname or alias.name] = target if target in dead else item.module
    used = {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}
    return any(name in used and any(module == dead_name or module.startswith(dead_name + ".") for dead_name in dead) for name, module in aliases.items())


def _derive_expected(worktree, baseline, dead):
    expected = set()
    by_file = {}
    for nodeid in baseline:
        by_file.setdefault(nodeid.split("::", 1)[0], []).append(nodeid)
    valid = True
    for rel, nodeids in by_file.items():
        path = worktree / rel
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        file_expected = []
        for nodeid in nodeids:
            node = _function(tree, nodeid.split("::")[1:])
            if node is not None and _uses_dead(node, tree, dead):
                expected.add(nodeid)
                file_expected.append(nodeid)
        if not (REPO / rel).exists() and len(file_expected) != len(nodeids):
            valid = False
    return expected, valid


def _real_fixture(baseline_path, sha_path):
    baseline = json.loads(Path(baseline_path).read_text(encoding="ascii"))
    checkpoint = json.loads(Path(sha_path).read_text(encoding="ascii"))
    sha = checkpoint["sha"]
    commit = _run(["git", "cat-file", "-e", f"{sha}^{{commit}}"])
    tree = _run(["git", "rev-parse", f"{sha}^{{tree}}"])
    writer = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = analyze(REPO)
    current_run, current = _collect(REPO)
    test_run = _run([sys.executable, "-m", "pytest", "tests", "--no-cov", "-q"])
    temp = Path(tempfile.mkdtemp(prefix="mmts-pre-delete-"))
    added = False
    try:
        add = _run(["git", "worktree", "add", "--detach", str(temp), sha])
        if add.returncode:
            raise RuntimeError(add.stderr)
        added = True
        old_run, old = _collect(temp)
        expected, derivation = _derive_expected(temp, old, _dead_modules(sha))
    finally:
        if added:
            _run(["git", "worktree", "remove", "--force", str(temp)])
        shutil.rmtree(temp, ignore_errors=True)
    lint_runs = (
        _run([sys.executable, "-m", "ruff", "check", "src", "tests"]),
        _run([sys.executable, "-m", "black", "--check", "src", "tests"]),
    )
    import_run = _run([sys.executable, "-c", "import src.mcp.stdio_server, src.mcp.http_server"])
    sys.path.insert(0, str(REPO))
    from src.mcp.tool_registry import get_tool_definitions

    removed = old - current
    passed_text = test_run.stdout
    import re

    passed = re.search(r"(\d+) passed", passed_text)
    failed = re.search(r"(\d+) failed", passed_text)
    errors = re.search(r"(\d+) errors?", passed_text)
    return {
        "dead_remaining": len(report["dead_src"]) + len(report["dead_scripts"]),
        "allowed_dead": 0 if report.get("exemptions_valid") else 1,
        "call_named": bool(report.get("allowed_call_unreachable", {}).get("src/universal_components.py")),
        "checkpoint_clean": (
            checkpoint.get("checkpoint_clean") is True
            and commit.returncode == 0
            and tree.stdout.strip() == checkpoint.get("tree")
            and checkpoint.get("writer_sha256") == writer
        ),
        "artifact_gone": not (REPO / "src/stores/event_log.py.init").exists(),
        "deleted": len(_dead_modules(sha)),
        "tools": len(get_tool_definitions()) if import_run.returncode == 0 and len(get_tool_definitions()) == baseline["tools"] else 0,
        "nodeid_exact": removed == expected,
        "derivation": derivation and old_run.returncode == 0,
        "lint": all(run.returncode == 0 for run in lint_runs),
        "passed": int(passed.group(1)) if test_run.returncode == 0 and current_run.returncode == 0 and passed else 0,
        "failed": int(failed.group(1)) if failed else 0,
        "errors": int(errors.group(1)) if errors else 0,
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline")
    parser.add_argument("--sha")
    parser.add_argument("--write-checkpoint")
    args = parser.parse_args(argv)
    if args.write_checkpoint:
        return _write_checkpoint(args.write_checkpoint)
    if not args.baseline or not args.sha:
        parser.error("--baseline and --sha are required")
    result = _real_fixture(args.baseline, args.sha)
    ok = probe(result)
    if not ok:
        return 1
    print(
        "DELETION_CLOSURE_OK dead_remaining=0 allowed_dead=0 call_unreachable_named=1 "
        f"checkpoint_clean=1 artifact_gone=1 deleted={result['deleted']} tools={result['tools']} "
        f"nodeid_diff_exact=1 test_derivation=1 lint=1 passed={result['passed']} failed=0 errors=0"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
