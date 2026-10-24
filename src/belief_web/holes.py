"""
find_holes: where the belief web is weakest (PLAN-B section 5.2). Read-only.

The whole web is solved at `now` from the current rows, then each belief is
checked against six predicates. None of them ever calls a source wrong: a
contradicted belief lists the sources on the side the posterior disagrees
with, an outdated one lists evidence a newer check superseded ("may have been
true when written"). Only located chunks are named as mentions; a memory
that said it without a located chunk is listed under memory_refs.
"""

from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .belief_store import BeliefStore, BeliefValidationError, format_ts, parse_ts
from .solver import HALF_LIFE_DEFAULT, local_logodds, sigmoid, solve

HOLE_KINDS = (
    "contradicted",
    "outdated_memory",
    "contradicted_pair",
    "stale",
    "unsupported",
    "weak_load_bearing",
)
CONTRADICTION_LLR = 0.4  # both sides at least this strong
PAIR_SUM = 1.1  # excludes pair with pA + pB above this, each side above 0.5
UNSUPPORTED_SUM = 0.1  # total |active decayed llr| below this
WEAK_BAND = (0.3, 0.7)
LOAD_DEPTH = 5
METHOD = "belief_web_v1 log-odds propagation"


def _loads(edges, keys) -> Dict[str, int]:
    """Dependents of each key: what rests on it through supports(key, x) or
    depends_on(x, key), breadth first to LOAD_DEPTH."""
    out: Dict[str, List[str]] = {}
    for t, s, d, _ in edges:
        if t == "supports":
            out.setdefault(s, []).append(d)
        elif t == "depends_on":
            out.setdefault(d, []).append(s)
    loads = {}
    for k in keys:
        seen, todo = {k}, deque([(k, 0)])
        while todo:
            node, depth = todo.popleft()
            if depth == LOAD_DEPTH:
                continue
            for nxt in out.get(node, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append((nxt, depth + 1))
        loads[k] = len(seen) - 1
    return loads


def _sources(web, key: str, evidence) -> List[Dict[str, Any]]:
    """Each evidence group with its located chunks; unlocated ones are memory_refs."""
    out = []
    for e in evidence:
        rows = web.mentions.get((key, e.source_id, e.polarity), [])
        out.append(
            {
                "source_id": e.source_id,
                "polarity": e.polarity,
                "source_type": e.source_type,
                "observed_at": format_ts(e.observed_at),
                "chunks": [c for c, loc in rows if loc],
                "memory_refs": [c for c, loc in rows if not loc],
            }
        )
    return out


def parse_args(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """find_holes input {project?, kinds?, min_load: 2, limit: 20, now?}."""
    project = arguments.get("project")
    kinds = arguments.get("kinds")
    min_load = arguments.get("min_load", 2)
    limit = arguments.get("limit", 20)
    if project is not None and not isinstance(project, str):
        raise BeliefValidationError("project must be text")
    if kinds is not None and (
        not isinstance(kinds, list) or not set(kinds) <= set(HOLE_KINDS) or not kinds
    ):
        raise BeliefValidationError(
            f"kinds must be a non-empty list of {list(HOLE_KINDS)}"
        )
    for name, value, lo, hi in (
        ("min_load", min_load, 0, 1000),
        ("limit", limit, 1, 200),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not lo <= value <= hi
        ):
            raise BeliefValidationError(f"{name} must be an integer from {lo} to {hi}")
    now = arguments.get("now")
    now = parse_ts(now) if now is not None else datetime.now(timezone.utc)
    return {
        "project": project,
        "kinds": kinds,
        "min_load": min_load,
        "limit": limit,
        "now": now,
    }


def _rank(p: float, load: int) -> float:
    return (1 + load) * (1 - abs(2 * p - 1))


def find_holes(
    store: Optional[BeliefStore],
    now: datetime,
    project: Optional[str] = None,
    kinds: Optional[List[str]] = None,
    min_load: int = 2,
    limit: int = 20,
) -> Dict[str, Any]:
    """Holes ranked by (1 + load) * (1 - |2p - 1|), contradicted first on ties.
    counts are by kind before `kinds` and `limit` are applied."""
    if store is None:  # no belief tables yet
        return _result([], {k: 0 for k in HOLE_KINDS}, 0, now, True, 0)
    web = store.web(now)
    local, L0 = {}, {}
    for k, (_, kind, hl, prior) in web.attrs.items():
        kind = kind or "state"
        local[k] = local_logodds(web.evidence.get(k, []), kind, now, hl, prior or 0.0)
        L0[k] = local[k].L
    sol = solve(L0, web.edges)
    p = {k: sigmoid(v) for k, v in sol.L.items()}
    scope = sorted(
        k for k in web.attrs if project is None or project in web.projects.get(k, ())
    )
    loads = _loads(web.edges, scope)
    found: List[Dict[str, Any]] = []
    for k in scope:
        found.extend(_belief_holes(web, k, local[k], p[k], loads[k], min_load, now))
    in_scope = set(scope)
    pairs = sorted(
        {tuple(sorted((s, d))) for t, s, d, _ in web.edges if t == "excludes"}
    )
    for a, b in pairs:
        # both sides must lean true: one strong belief pushing an unevidenced
        # alternative down (F5: 0.90 + 0.31) is the edge working, not a conflict
        both = p[a] > 0.5 and p[b] > 0.5
        if (a in in_scope or b in in_scope) and both and p[a] + p[b] > PAIR_SUM:
            la, lb = loads.get(a, 0), loads.get(b, 0)
            found.append(
                {
                    "hole": "contradicted_pair",
                    "keys": [a, b],
                    "claims": [_claim(web, a), _claim(web, b)],
                    "p": [p[a], p[b]],
                    "load": max(la, lb),
                    "rank": max(_rank(p[a], la), _rank(p[b], lb)),
                }
            )
    counts = {kind: sum(1 for h in found if h["hole"] == kind) for kind in HOLE_KINDS}
    shown = [h for h in found if kinds is None or h["hole"] in kinds]
    shown.sort(
        key=lambda h: (
            -h["rank"],
            h["hole"] != "contradicted",
            h.get("key", ""),
            h.get("keys", []),
        )
    )
    return _result(
        shown[:limit], counts, len(scope), now, sol.converged, sol.iterations
    )


def _claim(web, key: str) -> str:
    claim = web.attrs[key][0]
    return claim if claim is not None else key


def _belief_holes(web, key, local, p, load, min_load, now) -> List[Dict[str, Any]]:
    claim, kind, hl, _ = web.attrs[key]
    kind = kind or "state"
    base = {
        "key": key,
        "claim": _claim(web, key),
        "kind": kind,
        "p": p,
        "load": load,
        "rank": _rank(p, load),
    }
    holes = []
    llrs = local.llrs
    if any(x >= CONTRADICTION_LLR for x in llrs) and any(
        x <= -CONTRADICTION_LLR for x in llrs
    ):
        # the side the posterior disagrees with; both at an exact tie
        side = {-1} if p > 0.5 else ({1} if p < 0.5 else {1, -1})
        disputed = [e for e in local.active if e.polarity in side]
        holes.append(
            {
                **base,
                "hole": "contradicted",
                "disputed_sources": _sources(web, key, disputed),
            }
        )
    sign = (sum(llrs) > 0) - (sum(llrs) < 0)
    if kind in ("state", "plan") and sign and local.superseded:
        older = [e for e in local.superseded if e.polarity != sign]
        if older:
            newest = max(
                e.observed_at for e in local.active if e.source_type == "witnessed"
            )
            note = (
                f"superseded by a newer check on {newest.date().isoformat()}; "
                "may have been true when written"
            )
            sources = [{**s, "note": note} for s in _sources(web, key, older)]
            holes.append(
                {**base, "hole": "outdated_memory", "outdated_sources": sources}
            )
    if local.active:
        newest = max(e.observed_at for e in local.active)
        age_days = (now - newest).total_seconds() / 86400.0
        half_life = hl if hl is not None else HALF_LIFE_DEFAULT[kind]
        if age_days > half_life:
            holes.append(
                {
                    **base,
                    "hole": "stale",
                    "age_days": round(age_days, 6),
                    "half_life_days": half_life,
                }
            )
    if sum(abs(x) for x in llrs) < UNSUPPORTED_SUM:
        holes.append({**base, "hole": "unsupported"})
    sources = {e.source_id for e in local.active}
    single = len(sources) == 1 and all(
        e.source_type != "witnessed" for e in local.active
    )
    if load >= min_load and (WEAK_BAND[0] <= p <= WEAK_BAND[1] or single):
        holes.append({**base, "hole": "weak_load_bearing", "single_source": single})
    return holes


def _result(holes, counts, beliefs, now, converged, iterations) -> Dict[str, Any]:
    return {
        "holes": holes,
        "counts": counts,
        "beliefs": beliefs,
        "now": format_ts(now),
        "converged": converged,
        "iterations": iterations,
        "method": METHOD,
    }


def belief_counts(store: Optional[BeliefStore], now: datetime) -> Dict[str, Any]:
    """lifecycle_status belief counts: beliefs, evidence groups, mention rows,
    logical edges and holes by kind (section 5.2), all zero before any belief."""
    if store is None:
        return {"beliefs": 0, "evidence": 0, "mentions": 0, "edges": 0,
                "holes": {k: 0 for k in HOLE_KINDS}}  # fmt: skip
    web = store.web(now)
    return {
        "beliefs": len(web.attrs),
        "evidence": sum(len(v) for v in web.evidence.values()),
        "mentions": web.mention_rows,
        "edges": len(web.edges),
        "holes": find_holes(store, now)["counts"],
    }
