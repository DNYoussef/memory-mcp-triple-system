#!/usr/bin/env python
"""Compute import reachability from the documented Memory MCP roots."""

import argparse
import ast
import fnmatch
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXEMPT = {
    ("src/mcp/service_wiring.py", "src.services.qwen3vl_embedder"),
    ("src/mcp/service_wiring.py", "src.services.visual_memory_service"),
    ("src/mcp/service_wiring.py", "src.indexing.visual_indexer"),
    ("src/mcp/service_wiring.py", "src.services.unified_search_router"),
}


class Imports(ast.NodeVisitor):
    def __init__(self):
        self.nodes = []

    def visit_If(self, node):
        name = ast.unparse(node.test)
        if name == "TYPE_CHECKING" or name.endswith(".TYPE_CHECKING"):
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Import(self, node):
        self.nodes.append(node)

    def visit_ImportFrom(self, node):
        self.nodes.append(node)


def _module(path, root):
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _candidate(name, modules):
    if name in modules:
        return modules[name]
    return None


def _imports(path, root, modules):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    visitor = Imports()
    visitor.visit(tree)
    current = _module(path, root)
    package = current if path.name == "__init__.py" else current.rpartition(".")[0]
    found = set()
    for node in visitor.nodes:
        names = []
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        else:
            base = node.module or ""
            if node.level:
                try:
                    base = importlib.util.resolve_name("." * node.level + base, package)
                except (ImportError, ValueError):
                    continue
            if base:
                names.append(base)
            names.extend(f"{base}.{alias.name}".strip(".") for alias in node.names)
        for name in names:
            target = _candidate(name, modules)
            if target and (path.relative_to(root).as_posix(), name) not in EXEMPT:
                found.add(target)
    return found


def analyze(root=REPO):
    root = Path(root).resolve()
    harness = [
        root / name
        for name in (
            "conftest.py",
            "tests/conftest.py",
            "tests/unit/conftest.py",
            "tests/fixtures/real_services.py",
        )
        if (root / name).exists()
    ]
    files = sorted((root / "src").rglob("*.py")) + sorted((root / "scripts").rglob("*.py")) + harness
    modules = {_module(path, root): path for path in files}
    graph = {path: _imports(path, root, modules) for path in files}
    roots = {
        root / "src/mcp/stdio_server.py",
        root / "src/mcp/http_server.py",
        root / "scripts/gate_tri_tier.py",
        root / "scripts/check_docs.py",
        root / "scripts/acceptance_all_parts.py",
        root / "scripts/bench_tools.py",
        root / "scripts/obsidian_sync.py",
        root / "scripts/fix_imports.py",
        root / "scripts/ingest_documentation.py",
        root / "src/bridges/cytoscape_exporter.py",
    }
    roots.update((root / "src/hooks").glob("*.py"))
    roots.update((root / "scripts/gates").glob("*.py"))
    roots.update(harness)
    live = {path for path in roots if path.exists()}
    pending = list(live)
    while pending:
        source = pending.pop()
        for target in graph.get(source, ()):
            if target not in live:
                live.add(target)
                pending.append(target)
        cursor = source.parent
        while cursor != root:
            init = cursor / "__init__.py"
            if init in graph and init not in live:
                live.add(init)
                pending.append(init)
            cursor = cursor.parent
    src_files = {path for path in files if path.is_relative_to(root / "src")}
    script_files = {path for path in files if path.is_relative_to(root / "scripts")}
    exempt_targets = {module for _, module in EXEMPT}
    imported_elsewhere = []
    for source, targets in graph.items():
        for target in targets:
            if _module(target, root) in exempt_targets:
                imported_elsewhere.append(source.relative_to(root).as_posix())
    universal = root / "src/universal_components.py"
    compatibility_importers = {root / "src/mcp/service_wiring.py", root / "src/mcp/http_server.py"}
    compatibility_ok = universal in live and all(universal in graph.get(path, set()) for path in compatibility_importers)
    allowed_call_unreachable = {}
    if compatibility_ok:
        allowed_call_unreachable["src/universal_components.py"] = (
            "compatibility surface retained through both transport wiring modules"
        )
    return {
        "live": sorted(path.relative_to(root).as_posix() for path in live),
        "dead_src": sorted(path.relative_to(root).as_posix() for path in src_files - live),
        "dead_scripts": sorted(path.relative_to(root).as_posix() for path in script_files - live),
        "exemptions": sorted([list(item) for item in EXEMPT]),
        "exemptions_valid": len(EXEMPT) == 4 and not imported_elsewhere,
        "allowed_call_unreachable": allowed_call_unreachable,
    }


def self_test():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, body in {
            "src/__init__.py": "",
            "src/mcp/__init__.py": "",
            "src/mcp/stdio_server.py": "from src.live import value\n",
            "src/mcp/http_server.py": "",
            "src/live.py": "from .pkg import child\n",
            "src/pkg/__init__.py": "",
            "src/pkg/child.py": "",
            "src/dead.py": "",
            "scripts/gates/reachability.py": "",
        }.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        report = analyze(root)
        assert "src/live.py" in report["live"]
        assert "src/pkg/child.py" in report["live"]
        assert "src/pkg/__init__.py" in report["live"]
        assert report["dead_src"] == ["src/dead.py"]
    print("REACHABILITY_SELF_TEST_OK")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPO)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    report = analyze(args.root)
    if args.report:
        print(json.dumps(report, indent=2))
    else:
        print(f"live={len(report['live'])} dead_src={len(report['dead_src'])} dead_scripts={len(report['dead_scripts'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
