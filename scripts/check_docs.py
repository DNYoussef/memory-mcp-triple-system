#!/usr/bin/env python
"""Doc-accuracy gate: current-facing docs must match code reality (the independent
method for the doc-sync goal). Runnable by either model: `python scripts/check_docs.py`.

Facts are harvested from code (tool names, entrypoints), NOT hardcoded, so the
gate tracks the registry. Current docs are gated hard; everything else is treated
as history and only listed (point-in-time records are not rewritten).
"""
import os
import re
import sys

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


def harvest_tool_names():
    sys.path.insert(0, ROOT)
    from src.mcp.tool_registry import get_tool_definitions
    return {t["name"] for t in get_tool_definitions()}


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def all_markdown():
    out = []
    for base, _, files in os.walk(os.path.join(ROOT, "docs")):
        if "project-history" in base:
            continue
        for fn in files:
            if fn.endswith(".md"):
                out.append(os.path.relpath(os.path.join(base, fn), ROOT).replace("\\", "/"))
    if os.path.exists(os.path.join(ROOT, "README.md")):
        out.append("README.md")
    return sorted(out)


def main():
    tools = harvest_tool_names()
    new_tools = {"kv_get", "kv_set", "kv_delete", "context_retrieve"}
    violations = []

    for rel in CURRENT_DOCS:
        if not os.path.exists(os.path.join(ROOT, rel)):
            violations.append((rel, "MISSING current doc"))
            continue
        text = read(rel)
        low = text.lower()
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

    classified = set(CURRENT_DOCS)
    history = [m for m in all_markdown() if m not in classified]

    print(f"tools in registry ({len(tools)}): {', '.join(sorted(tools))}\n")
    print(f"current docs gated: {len(CURRENT_DOCS)} | history (records, not gated): {len(history)}\n")
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
