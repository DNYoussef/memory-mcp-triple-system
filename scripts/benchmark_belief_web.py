"""
Belief web solver benchmark (PLAN-B section 3.4, B-PR1 gate).

Targets:
- whole-web solve (what find_holes does) on 3k-8k beliefs: < 3 s;
- bayesian_inference, which solves only the connected component of the
  matched and clamped beliefs: p95 < 300 ms.
No cache: every call solves from the current rows at `now`.

Webs measured:
- F26: 1,000 beliefs / 3,000 typed edges (seed 1), solver only and through the store;
- 8k connected: 8,000 beliefs, 2-5 assertions each, 24,000 random edges
  (one giant component, the worst case for component scoping);
- 8k clustered: the same counts split into 160 projects of 50 beliefs, edges
  inside a project only.

Run from the repo root:
    PYTHONPATH=. python scripts/benchmark_belief_web.py [workdir]
"""

import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

from src.belief_web.belief_store import BeliefStore
from src.belief_web.solver import solve

NOW = "2026-10-14T15:00:00Z"
TYPES = ("supports", "excludes", "depends_on")
SOURCE_TYPES = ("witnessed", "reported", "inferred", "assumed")


def f26_web():
    rng = random.Random(1)
    n = 1000
    L0 = {i: rng.uniform(-3, 3) for i in range(n)}
    rows, seen = [], set()
    while len(rows) < 3000:
        a, b = rng.sample(range(n), 2)
        if frozenset((a, b)) in seen:
            continue
        seen.add(frozenset((a, b)))
        rows.append((rng.choice(TYPES), a, b, rng.uniform(0.05, 1)))
    return L0, rows


def timed(fn, repeat):
    out = []
    for _ in range(repeat):
        t = time.perf_counter()
        result = fn()
        out.append(time.perf_counter() - t)
    return out, result


def build_store(path, n, n_edges, cluster, seed):
    """n beliefs with 2-5 assertions each; edges between random pairs, inside
    clusters of `cluster` beliefs (cluster = n gives one random web)."""
    rng = random.Random(seed)
    s = BeliefStore(str(path))
    keys = [f"bench.c{i // cluster}.k{i}" for i in range(n)]
    t = time.perf_counter()
    with s.batch():
        for i, k in enumerate(keys):
            for j in range(rng.randint(2, 5)):
                day = rng.randint(1, 13)
                s.add_assertion(
                    "live",
                    k,
                    polarity=rng.choice((1, -1)),
                    source_type=rng.choice(SOURCE_TYPES),
                    observed_at=f"2026-10-{day:02d}T12:00:00Z",
                    recorded_at=f"2026-10-{day:02d}T12:00:00Z",
                    chunk_id=f"chunk{i}_{j}",
                    who=f"who{rng.randint(0, 3)}",
                    kind=rng.choice(("state", "plan", "fact")),
                )
        seen = set()
        while len(seen) < n_edges:
            c = rng.randrange(n // cluster)
            a, b = rng.sample(range(c * cluster, (c + 1) * cluster), 2)
            if frozenset((a, b)) in seen:
                continue
            seen.add(frozenset((a, b)))
            s.add_edge(
                "live", keys[a], keys[b], rng.choice(TYPES), rng.uniform(0.05, 1)
            )
    return s, keys, time.perf_counter() - t


def bench_store(label, path, n, n_edges, cluster, queries=60):
    s, keys, load = build_store(path, n, n_edges, cluster, seed=n + cluster)
    whole, sol = timed(lambda: s.solve(NOW), 3)
    rng = random.Random(5)
    picks = [rng.choice(keys) for _ in range(queries)]
    comp = []
    for k in picks:
        t = time.perf_counter()
        part = s.solve(
            NOW, keys=[k], clamp={rng.choice(keys): 7.0} if cluster == n else None
        )
        comp.append(time.perf_counter() - t)
    comp.sort()
    p95 = comp[int(0.95 * (len(comp) - 1))]
    print(
        f"{label}: beliefs {len(sol.L)}, rules {len(sol.weights)}, load {load:.1f} s; "
        f"whole-web solve median {statistics.median(whole):.3f} s (max {max(whole):.3f}), "
        f"{sol.iterations} rounds, converged {sol.converged}; "
        f"component solve p50 {statistics.median(comp) * 1000:.0f} ms p95 {p95 * 1000:.0f} ms "
        f"(last component {len(part.L)} beliefs)"
    )
    s.close()
    return statistics.median(whole), p95


def main():
    work = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(tempfile.mkdtemp(prefix="belief-bench-"))
    )
    work.mkdir(parents=True, exist_ok=True)
    L0, rows = f26_web()
    t, sol = timed(lambda: solve(L0, rows), 5)
    print(
        f"F26 solver only: median {statistics.median(t):.3f} s, {sol.iterations} rounds, converged {sol.converged}"
    )
    results = {
        "F26 store": bench_store(
            "F26 store (1k/3k)", work / "f26.db", 1000, 3000, 1000
        ),
        "8k connected": bench_store(
            "8k connected (8k/24k)", work / "8k.db", 8000, 24000, 8000
        ),
        "8k clustered": bench_store(
            "8k clustered (160 x 50)", work / "8k_clustered.db", 8000, 24000, 50
        ),
    }
    print("targets: whole-web < 3 s, component p95 < 300 ms")
    for name, (whole, p95) in results.items():
        print(
            f"  {name:13s} whole-web {'PASS' if whole < 3 else 'MISS'} ({whole:.3f} s), "
            f"component p95 {'PASS' if p95 < 0.3 else 'MISS'} ({p95 * 1000:.0f} ms)"
        )


if __name__ == "__main__":
    main()
