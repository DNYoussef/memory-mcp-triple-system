#!/usr/bin/env python
"""Doc-accuracy gate: current-facing docs must match code reality (the independent
method for the doc-sync goal). Runnable by either model: `python scripts/check_docs.py`.

Facts are harvested from code (tool names, entrypoints), NOT hardcoded, so the
gate tracks the registry. Current docs are gated hard; everything else is treated
as history and only listed (point-in-time records are not rewritten).
"""
import argparse
import os
import re
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Authoritative, user/model-facing docs. These must match reality.
CURRENT_DOCS = [
    "README.md",
    "docs/CURRENT.md",
    "docs/QUICK-START.md",
    "docs/MCP-INTEGRATION.md",
    "docs/ARCHITECTURE.md",
    "docs/api/MCP-DEPLOYMENT-GUIDE.md",
    "docs/api/INGESTION-AND-RETRIEVAL-EXPLAINED.md",
    "docs/architecture/SELF-REFERENTIAL-MEMORY.md",
    "docs/integration/BEADS-MEMORY-MCP-INTEGRATION-MANIFEST.md",
    "docs/README.md",
]

# Stale claims that contradict current reality (regex, reason).
BANNED = [
    (r"src\.mcp\.server\b", "dead entrypoint; real HTTP entry is src.mcp.http_server"),
    (r"\b11 MCP tools\b", "tool count drift; 18 tools (use the names, see CURRENT.md)"),
    (r"\b6 tools\b", "tool count drift; 18 tools"),
    (r"\b14 tools\b", "tool count drift; 18 tools"),
    (r"100:1", "false compression claim; SUMMARY_MAX_LEN budget, not 100:1"),
    (r"vector-only", "false; retrieval is vector+graph (+bayesian) fused"),
    (r"ready for implementation", "beads is implemented, not a plan"),
    (r"GET /tools", "wrong route; tool routes are JSON-body POST"),
    (r"27/27", "stale test count; link the live board instead"),
    (r"100% (test )?coverage", "stale coverage claim; link the live board"),
]


def harvest_tool_names(code_root):
    sys.path.insert(0, str(code_root))
    from src.mcp.tool_registry import get_tool_definitions

    return {t["name"] for t in get_tool_definitions()}


def read(root, rel):
    with open(root / rel, encoding="utf-8") as f:
        return f.read()


def all_markdown(root):
    out = []
    for base, _, files in os.walk(root / "docs"):
        if "project-history" in base:
            continue
        for fn in files:
            if fn.endswith(".md"):
                out.append(
                    os.path.relpath(os.path.join(base, fn), root).replace("\\", "/")
                )
    if (root / "README.md").exists():
        out.append("README.md")
    return sorted(out)


def without_external_blocks(text):
    kept = []
    external = False
    fenced = False
    for line in text.splitlines():
        if not external and re.match(
            r"^\*{0,2}Location\*{0,2}:\s*`?(?:[A-Za-z]:[\\/]|/)", line
        ):
            external = True
            continue
        if external:
            if line.startswith("```"):
                if fenced:
                    external = False
                    fenced = False
                else:
                    fenced = True
            continue
        kept.append(line)
    return "\n".join(kept)


def reference_violations(text, code_root):
    text = without_external_blocks(text)
    found = []

    def missing(form, value, relative):
        path = code_root / relative
        if not path.exists():
            found.append((form, value))

    for match in re.finditer(r"(?<![\w])src/([A-Za-z0-9_./-]+\.py)", text):
        missing("slash", match.group(0), Path("src") / match.group(1))
    for match in re.finditer(r"(?<![\w])src\\([A-Za-z0-9_.\\-]+\.py)", text):
        missing(
            "backslash",
            match.group(0),
            Path("src") / Path(match.group(1).replace("\\", "/")),
        )
    for match in re.finditer(
        r"\bfrom\s+src\.([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s+import\b", text
    ):
        module = Path("src") / Path(match.group(1).replace(".", "/"))
        if (
            not (code_root / module.with_suffix(".py")).exists()
            and not (code_root / module / "__init__.py").exists()
        ):
            found.append(("src-import", match.group(0)))
    for match in re.finditer(
        r"\bfrom\s+([A-Za-z_]\w*)\.([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s+import\b", text
    ):
        package, rest = match.groups()
        if package == "src" or not (code_root / "src" / package).exists():
            continue
        module = Path("src") / package / Path(rest.replace(".", "/"))
        if (
            not (code_root / module.with_suffix(".py")).exists()
            and not (code_root / module / "__init__.py").exists()
        ):
            found.append(("bare-import", match.group(0)))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-root", type=Path, default=Path(ROOT))
    parser.add_argument("--code-root", type=Path, default=Path(ROOT))
    args = parser.parse_args(argv)
    docs_root = args.docs_root.resolve()
    code_root = args.code_root.resolve()
    tools = harvest_tool_names(code_root)
    new_tools = {"kv_get", "kv_set", "kv_delete", "context_retrieve"}
    violations = []

    for rel in CURRENT_DOCS:
        if not (docs_root / rel).exists():
            violations.append((rel, "MISSING current doc"))
            continue
        text = read(docs_root, rel)
        for rx, reason in BANNED:
            m = re.search(rx, text, re.IGNORECASE)
            if m:
                violations.append((rel, f"banned '{m.group(0)}' -> {reason}"))
        # A doc that enumerates tools (lists vector_search + memory_store) must
        # include the new tools, or its tool list is stale.
        if "vector_search" in text and "memory_store" in text:
            missing = [t for t in sorted(new_tools) if t not in text]
            if missing:
                violations.append((rel, f"tool list missing: {', '.join(missing)}"))
        # Ingestion store field is 'text', not 'content'.
        if "ingestion" in rel.lower() and re.search(r'"content"\s*:', text):
            violations.append((rel, 'store field is "text", not "content"'))
        for form, value in reference_violations(text, code_root):
            violations.append(
                (rel, f"missing code reference form={form} value={value}")
            )

    classified = set(CURRENT_DOCS)
    history = [m for m in all_markdown(docs_root) if m not in classified]

    print(f"tools in registry ({len(tools)}): {', '.join(sorted(tools))}\n")
    print(
        f"current docs gated: {len(CURRENT_DOCS)} | history (records, not gated): {len(history)}\n"
    )
    if violations:
        print("DOC DRIFT:")
        for rel, v in violations:
            print(f"  {rel}: {v}")
        print(f"\n{len(violations)} violation(s)")
        return 1
    print("OK: all current docs match code reality.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
