"""Quick RLM verification test."""
import sys
sys.path.insert(0, "src")

from rlm.rlm_codebase_env import RLMCodebaseEnvironment

print("=== RLM Quick Verification ===\n")

# Initialize
env = RLMCodebaseEnvironment()
print(f"Projects configured: {len(env.projects)}")

# Index just ai-exoskeleton for speed
print("\nIndexing ai-exoskeleton project...")
env.load_data("ai-exoskeleton")
print(f"Files indexed: {len(env._index)}")
print(f"By project: {list(env._by_project.keys())}")

# Search test
print("\n=== Search Test: 'circuit' ===")
results = env.search_content("circuit", limit=5)
print(f"Found {len(results)} results")
for r in results[:3]:
    path = r.get("path", r.get("file", "unknown"))
    print(f"  - {path[-60:]}")

# Search for CAPTURE layer references
print("\n=== Search Test: 'CAPTURE' ===")
results = env.search_content("CAPTURE", limit=5)
print(f"Found {len(results)} results")
for r in results[:3]:
    path = r.get("path", r.get("file", "unknown"))
    print(f"  - {path[-60:]}")

# Load file content test
print("\n=== Load File Content Test ===")
content = env.load_file_content(
    "D:/2026-AI-EXOSKELETON/2026-AI-EXOSKELETON-TODO.md",
    start_line=1,
    end_line=15
)
print(f"Loaded {len(content)} chars from TODO.md")
print("First 200 chars:")
print(content[:200])

print("\n=== RLM VERIFICATION: PASSED ===")
