"""
Belief web solver: per-belief local log-odds plus bounded propagation.

PLAN-B sections 3.1-3.3. Pure functions, no I/O. The store (belief_store.py)
supplies reduced evidence and edge rows; this module turns them into log-odds.

Honest label: this is a confidence propagation, not an exact posterior.
"""

import math
from datetime import datetime
from typing import Dict, Hashable, Iterable, List, NamedTuple, Optional, Tuple

K = 2.0  # message gain
CAP = 0.9  # total incoming weight per belief is scaled down to this
CLAMP_L = 7.0  # log-odds used for hypothetical true/false evidence
HALF_LIFE_DEFAULT = {"state": 14.0, "plan": 30.0, "fact": 365.0}
EDGE_TYPES = ("supports", "excludes", "depends_on")
TOLERANCE = 1e-12
MAX_ROUNDS = 1000

Rule = Tuple[Hashable, Hashable, str]  # (u, v, edge type): a message u -> v


class Evidence(NamedTuple):
    polarity: int
    reliability: float
    source_type: str
    observed_at: datetime
    recorded_at: datetime
    source_id: str = ""
    chunk_id: str = ""


class Local(NamedTuple):
    L: float
    active: List[Evidence]
    superseded: List[Evidence]
    llrs: List[float]  # one per active evidence, same order


class Solution(NamedTuple):
    L: Dict[Hashable, float]
    messages: Dict[Rule, float]
    weights: Dict[Rule, float]  # after normalization
    iterations: int
    converged: bool
    deltas: List[float]  # per round: max |dm_e| / (K * w_e), the contraction norm


class EdgeConflict(ValueError):
    """Self-edge, or supports plus excludes on one unordered pair."""


def logit(r: float) -> float:
    return math.log(r / (1 - r))


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def local_logodds(
    evidence: Iterable[Evidence],
    kind: str,
    now: datetime,
    half_life_days: Optional[float] = None,
    prior: float = 0.0,
) -> Local:
    """L0(b) = prior + sum of decayed llr over active evidence (section 3.1).

    Evidence observed or recorded after `now` never counts, so age >= 0 and
    decay cannot amplify. For state and plan, evidence observed before the
    latest witnessed observation is superseded: kept as history, adds 0.
    """
    h = half_life_days if half_life_days is not None else HALF_LIFE_DEFAULT[kind]
    eligible = [e for e in evidence if e.observed_at <= now and e.recorded_at <= now]
    active, superseded = eligible, []
    if kind in ("state", "plan"):
        witnessed = [e.observed_at for e in eligible if e.source_type == "witnessed"]
        if witnessed:
            tw = max(witnessed)
            active = [e for e in eligible if e.observed_at >= tw]
            superseded = [e for e in eligible if e.observed_at < tw]
    llrs = [
        e.polarity
        * logit(e.reliability)
        * 2 ** (-(now - e.observed_at).total_seconds() / 86400.0 / h)
        for e in active
    ]
    return Local(prior + sum(llrs), active, superseded, llrs)


def reduce_edges(
    rows: Iterable[Tuple[str, Hashable, Hashable, float]]
) -> Dict[Rule, float]:
    """Edge rows (type, src, dst, weight) -> message rules {(u, v, type): weight}.

    supports(a, b) is a -> b; excludes(a, b) is a -> b and b -> a; depends_on(a, b)
    is b -> a. Duplicates keep the max weight. Sorted, so input order cannot
    matter (section 2.4).
    """
    rules: Dict[Rule, float] = {}
    pairs: Dict[frozenset, set] = {}
    for t, a, b, w in sorted(rows, key=lambda r: (r[1], r[2], r[0], r[3])):
        if a == b:
            raise EdgeConflict(f"self-edge on {a}")
        if t == "supports":
            items = [(a, b, t)]
        elif t == "excludes":
            items = [(a, b, t), (b, a, t)]
        elif t == "depends_on":
            items = [(b, a, t)]
        else:
            raise EdgeConflict(f"unknown edge type {t!r}")
        for k in items:
            rules[k] = max(w, rules.get(k, 0.0))
            pairs.setdefault(frozenset(k[:2]), set()).add(t)
    for pair, types in pairs.items():
        if "supports" in types and "excludes" in types:
            raise EdgeConflict(
                f"supports and excludes on one pair {sorted(map(str, pair))}"
            )
    return rules


def solve(
    L0: Dict[Hashable, float],
    rows: Iterable[Tuple[str, Hashable, Hashable, float]],
    clamp: Optional[Dict[Hashable, float]] = None,
    tol: float = TOLERANCE,
    max_rounds: int = MAX_ROUNDS,
) -> Solution:
    """Jacobi message passing from m = 0 (section 3.2).

    m(u->v) = w * K * g(tanh((L(u) - M(v->u)) / 2)), where M(v->u) is the sum of
    current messages v -> u (cavity). g is max(0, x) for supports, -max(0, x)
    for excludes and min(0, x) for depends_on. Incoming weights per belief are
    scaled to sum <= CAP, which makes the update a 0.9-contraction in the
    weighted norm (section 3.3).

    Clamped beliefs are fixed at their value and have every incoming rule
    removed, so nothing flows back into them and their cavity is empty.
    """
    clamp = clamp or {}
    rules = {k: w for k, w in reduce_edges(rows).items() if k[1] not in clamp}
    into: Dict[Hashable, float] = {}
    for (_, v, _), w in rules.items():
        into[v] = into.get(v, 0.0) + w
    weights = {
        k: w * (CAP / into[k[1]] if into[k[1]] > CAP else 1.0) for k, w in rules.items()
    }

    keys = list(weights)
    index = {k: i for i, k in enumerate(keys)}
    src = [k[0] for k in keys]
    dst = [k[1] for k in keys]
    gain = [K * weights[k] for k in keys]
    mode = [k[2] for k in keys]
    rev = [
        [index[r] for r in ((v, u, t) for t in EDGE_TYPES) if r in index]
        for (u, v, _) in keys
    ]
    base = dict(L0)
    base.update(clamp)

    m = [0.0] * len(keys)
    deltas: List[float] = []
    converged, it = not keys, 0
    while not converged and it < max_rounds:
        it += 1
        L = dict(base)
        for i, v in enumerate(dst):
            L[v] += m[i]
        new = [0.0] * len(keys)
        d = dw = 0.0
        for i, u in enumerate(src):
            x = math.tanh((L[u] - sum(m[j] for j in rev[i])) / 2)
            g = (
                max(0.0, x)
                if mode[i] == "supports"
                else (-max(0.0, x) if mode[i] == "excludes" else min(0.0, x))
            )
            new[i] = gain[i] * g
            change = abs(new[i] - m[i])
            d = max(d, change)
            dw = max(dw, change / gain[i])
        deltas.append(dw)
        m = new
        converged = d < tol

    L = dict(base)
    for i, v in enumerate(dst):
        L[v] += m[i]
    return Solution(L, dict(zip(keys, m)), weights, it, converged, deltas)
