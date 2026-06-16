"""Cap Bayesian node in-degree to keep CPD tables bounded.

A node with K binary parents needs a 2 x 2^K CPD table. On the real knowledge
graph some hub entities accumulate dozens of parents, so 2^K explodes:
  - pgmpy MaximumLikelihoodEstimator tries to allocate 128 GiB+ (numpy refuses,
    the node's CPD is skipped, check_model then fails - the whole net is lost);
  - the lightweight builder enumerates 2^K parent combinations in a Python loop
    and hangs.

Capping each node to at most MAX_PARENTS incoming edges (highest-weight kept)
bounds every CPD at 2^MAX_PARENTS columns. A 4-parent Markov blanket keeps the
dominant conditioning signal; only weak parents are dropped.
"""
from typing import Callable, Iterable, List, Optional, Tuple

MAX_PARENTS = 4


def cap_in_degree(
    edges: Iterable[Tuple],
    max_parents: int = MAX_PARENTS,
    weight: Optional[Callable[[str, str], float]] = None,
) -> List[Tuple[str, str]]:
    """Return edges with no node exceeding max_parents incoming edges.

    edges: iterable of (u, v) or (u, v, data) tuples.
    weight: optional fn(u, v) -> float; higher is kept first. When None, keeps
        edges in iteration order (deterministic for an ordered input).
    """
    by_child: dict = {}
    for e in edges:
        u, v = e[0], e[1]
        by_child.setdefault(v, []).append((u, v))

    kept: List[Tuple[str, str]] = []
    for v, in_edges in by_child.items():
        if len(in_edges) > max_parents:
            # Deterministic: highest weight first, ties broken by parent id so
            # the kept set does not depend on graph load/construction order.
            in_edges.sort(key=lambda uv: uv[0])
            if weight is not None:
                in_edges.sort(key=lambda uv: weight(uv[0], uv[1]), reverse=True)
        kept.extend(in_edges[:max_parents])
    return kept
