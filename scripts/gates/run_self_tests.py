#!/usr/bin/env python
"""Validate the fail-first contract and canonical shape of every gate."""

import ast
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = (
    "baseline.py",
    "bayesian_backends.py",
    "bayesian_honesty.py",
    "beads_errors.py",
    "cleanup_under_stdio.py",
    "coverage_ratchet.py",
    "deletion_closure.py",
    "docs_truth.py",
    "railway_smoke.py",
    "stale_oracles.py",
    "tier_degradation.py",
    "trace_every_tool.py",
)


def _function(tree, name):
    return next((node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name), None)


def _calls(node, name):
    return any(isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id == name for item in ast.walk(node))


def _is_call(node, name):
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name


def _returns(node, value):
    return any(isinstance(item, ast.Return) and isinstance(item.value, ast.Constant) and item.value.value == value for item in ast.walk(node))


def _self_test_branch(main):
    branch = next(
        (
            node
            for node in main.body
            if isinstance(node, ast.If)
            and any(isinstance(item, ast.Constant) and item.value == "--self-test" for item in ast.walk(node.test))
        ),
        None,
    )
    if branch is None:
        return False
    assignment = next(
        (node for node in branch.body if isinstance(node, ast.Assign) and _is_call(node.value, "self_test")),
        None,
    )
    if assignment is None or not isinstance(assignment.targets[0], ast.Name):
        return False
    name = assignment.targets[0].id
    guarded = any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.UnaryOp)
        and isinstance(node.test.op, ast.Not)
        and isinstance(node.test.operand, ast.Name)
        and node.test.operand.id == name
        and _returns(node, 1)
        for node in branch.body
    )
    token = any(
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "print"
        and "SELF_TEST_REJECTED" in ast.unparse(node)
        and "GATE_ID" in ast.unparse(node)
        for node in branch.body
    )
    return guarded and token and _returns(branch, 0)


def _real_probe_flow(main):
    assignment_index = None
    name = None
    for index, node in enumerate(main.body):
        if isinstance(node, ast.Assign) and _is_call(node.value, "probe") and isinstance(node.targets[0], ast.Name):
            assignment_index, name = index, node.targets[0].id
            break
        if isinstance(node, (ast.With, ast.Try)):
            for child in node.body:
                if isinstance(child, ast.Assign) and _is_call(child.value, "probe") and isinstance(child.targets[0], ast.Name):
                    assignment_index, name = index, child.targets[0].id
                    break
            if assignment_index is not None:
                break
    if assignment_index is None:
        return False
    tail = main.body[assignment_index + 1 :]
    guard_index = next(
        (
            index
            for index, node in enumerate(tail)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.UnaryOp)
            and isinstance(node.test.op, ast.Not)
            and isinstance(node.test.operand, ast.Name)
            and node.test.operand.id == name
            and _returns(node, 1)
        ),
        None,
    )
    return guard_index is not None and any(_calls(node, "print") for node in tail[guard_index + 1 :])


def _shape(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    probe = _function(tree, "probe")
    planted = _function(tree, "_planted_bad_fixture")
    real = _function(tree, "_real_fixture")
    self_test = _function(tree, "self_test")
    main = _function(tree, "main")
    entry = any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and "__name__" in ast.unparse(node.test)
        and "__main__" in ast.unparse(node.test)
        and _calls(node, "main")
        for node in tree.body
    )
    rejected = any(
        isinstance(node, ast.Assert)
        and isinstance(node.test, ast.UnaryOp)
        and isinstance(node.test.op, ast.Not)
        and _calls(node.test, "probe")
        for node in ast.walk(self_test)
    ) if self_test else False
    return all((probe, planted, real, self_test, main, entry, rejected, _self_test_branch(main), _real_probe_flow(main)))


def _gate_id(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "GATE_ID" for target in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    return ""


def main():
    discovered = tuple(sorted(path.name for path in HERE.glob("*.py") if not path.name.startswith("_") and path.name not in ("reachability.py", "run_self_tests.py")))
    manifest_matches = discovered == tuple(sorted(MANIFEST))
    accepted = 0
    violations = 0
    gate_ids = []
    for name in MANIFEST:
        path = HERE / name
        shape = path.exists() and _shape(path)
        run = subprocess.run(
            [sys.executable, str(path), "--self-test"],
            cwd=HERE.parents[1],
            capture_output=True,
            text=True,
        )
        gate_id = _gate_id(path)
        gate_ids.append(gate_id)
        expected = f"SELF_TEST_REJECTED {gate_id}"
        if shape and run.returncode == 0 and run.stdout.strip() == expected:
            accepted += 1
        else:
            violations += 1
    distinct_ids = len(set(gate_ids)) == len(MANIFEST) and all(gate_ids)
    if accepted != len(MANIFEST) or violations or not manifest_matches or not distinct_ids:
        print(f"SELF_TESTS_FAIL accepted={accepted} shape_violations={violations} manifest_matches_disk={int(manifest_matches)}")
        return 1
    print(f"SELF_TESTS_OK {accepted}/{len(MANIFEST)} modules_accepted={accepted} shape_violations=0 manifest_matches_disk=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
