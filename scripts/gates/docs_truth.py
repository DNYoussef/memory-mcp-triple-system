#!/usr/bin/env python
"""Exercise all four local-code documentation reference forms."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE_ID = "P4"
TOKEN = "DOCS_TRUTH_OK forms=4 planted_violations=4 external_control_clean=1 real_ok=1"


def probe(fixture) -> bool:
    return fixture == {"forms": 4, "violations": 4, "external": True, "real": True}


def _planted_bad_fixture():
    good = {"forms": 4, "violations": 4, "external": True, "real": True}
    return [
        {**good, key: 0 if key in ("forms", "violations") else False} for key in good
    ]


def _run(docs, code):
    return subprocess.run(
        [
            sys.executable,
            "scripts/check_docs.py",
            "--docs-root",
            str(docs),
            "--code-root",
            str(code),
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
    )


def _real_fixture():
    with tempfile.TemporaryDirectory() as tmp:
        docs = Path(tmp) / "docs-copy"
        for rel in (
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
        ):
            target = docs / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, target)
        current = docs / "docs/CURRENT.md"
        with current.open("a", encoding="ascii") as handle:
            handle.write("\n`src/missing_one.py`\n`src\\missing_two.py`\n")
            handle.write(
                "`from src.missing_three import Thing`\n`from mcp.missing_four import Thing`\n"
            )
            handle.write(
                "Location: C:\\external\\life-os\n```python\nfrom mcp.missing_external import Thing\n```\n"
            )
        planted = _run(docs, REPO)
        violations = planted.stdout.count("missing code reference")
        external = "missing_external" not in planted.stdout
        forms = sum(
            f"form={name}" in planted.stdout
            for name in ("slash", "backslash", "src-import", "bare-import")
        )
    real = _run(REPO, REPO)
    return {
        "forms": forms,
        "violations": violations,
        "external": external,
        "real": real.returncode == 0
        and "OK: all current docs match code reality." in real.stdout,
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
