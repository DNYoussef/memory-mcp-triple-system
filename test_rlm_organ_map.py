"""RLM verification of 2026-EXOSKELETON-ORGAN-MAP.md claims."""
import sys
sys.path.insert(0, "src")

from rlm.rlm_codebase_env import RLMCodebaseEnvironment

print("=== RLM ORGAN MAP VERIFICATION ===\n")

# Initialize and index
env = RLMCodebaseEnvironment()
print("Loading all projects...")
env.load_data("all")
print(f"Indexed {len(env._index)} files across {len(env._by_project)} projects\n")

# CLAIM 1: Project count - Document says 18/19 projects
print("=== CLAIM 1: Project Count ===")
print(f"Projects in RLM: {len(env.projects)}")
print(f"Project names: {list(env.projects.keys())}")
print()

# CLAIM 2: Skills count - 264 skills
print("=== CLAIM 2: Skills Count (264 claimed) ===")
skill_results = env.search_content("SKILL.md", limit=500)
print(f"SKILL.md files found: {len(skill_results)}")
print()

# CLAIM 3: Agents count - 260 agents
print("=== CLAIM 3: Agents Count (260 claimed) ===")
agent_results = env.search_content("agents/", limit=500)
# Count unique agent directories
agent_paths = set()
for r in agent_results:
    path = r.get("path", "")
    if "agents/" in path and path.endswith(".md"):
        agent_paths.add(path)
print(f"Agent MD files found: {len(agent_paths)}")
print()

# CLAIM 4: Components - 80 in library
print("=== CLAIM 4: Library Components (80 claimed) ===")
catalog_results = env.search_content("catalog.json", limit=10)
print(f"Catalog files found: {len(catalog_results)}")
for r in catalog_results[:3]:
    print(f"  - {r.get('path', 'unknown')[-70:]}")
print()

# CLAIM 5: API endpoints - 496 claimed
print("=== CLAIM 5: API Endpoints (496 claimed) ===")
router_results = env.search_content("router", project="life-os-dashboard", limit=50)
print(f"Router references in life-os-dashboard: {len(router_results)}")
print()

# CLAIM 6: Agentwise specialists - 11 claimed
print("=== CLAIM 6: Agentwise Specialists (11 claimed) ===")
specialist_results = env.search_content("specialist", project="agentwise", limit=50)
print(f"Specialist references in agentwise: {len(specialist_results)}")
print()

# CLAIM 7: Slop detector patterns - 69 claimed
print("=== CLAIM 7: Slop Detector Patterns (69 claimed) ===")
slop_results = env.search_content("pattern", project="slop-detector", limit=100)
print(f"Pattern references in slop-detector: {len(slop_results)}")
print()

# CLAIM 8: Meta-calculus simulations - 67 claimed
print("=== CLAIM 8: Meta-calculus Simulations (67 claimed) ===")
sim_results = env.search_content("simulation", project="meta-calculus", limit=100)
print(f"Simulation references in meta-calculus: {len(sim_results)}")
print()

# CLAIM 9: Document suite count - 14 claimed
print("=== CLAIM 9: Document Suite (14 claimed) ===")
doc_results = env.search_content("2026-", project="ai-exoskeleton", limit=50)
print(f"2026-* docs in exoskeleton: {len(doc_results)}")
for r in doc_results[:5]:
    print(f"  - {r.get('path', 'unknown')[-50:]}")

print("\n=== RLM VERIFICATION COMPLETE ===")
