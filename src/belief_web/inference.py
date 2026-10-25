"""
bayesian_inference on the belief web (PLAN-B sections 4.5, 5.1).

Read-only: the query is matched to beliefs (a key or alias named in the
query, else cosine over claim vectors at a threshold), evidence is applied
as hypothetical clamps that are never written, and only the connected
component of the matched and clamped beliefs is solved, at `now`.

Nothing is ignored silently. An evidence key that does not resolve, or a
value that is not a boolean, refuses the whole call with candidate keys,
unless the caller asks for unknown_evidence "drop", which reports what was
dropped. A query that matches nothing returns the nearest claims, never an
arbitrary belief.
"""

import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .belief_store import BeliefStore, BeliefValidationError, format_ts, parse_ts
from .holes import MAX_BYTES, analyze, bounded, holes_of
from .solver import CLAMP_L

METHOD = "belief_web_v1 log-odds propagation"
# Chosen on tests/fixtures/belief_match_labeled.json (section 6.4) by
# scripts/choose_match_threshold.py: max recall with no-match false accept <= 5%
# (58/60 correct, 2 wrong key, 0/20 false accept; any value in (0.2886, 0.3027]
# gives the same counts, this is the midpoint). Re-checked on real claims
# before activation (section 5.4).
MATCH_THRESHOLD = 0.2956
NEAREST = 3
KEY_TOKEN = re.compile(r"[a-z0-9_]+(?:\.[a-z0-9_]+){1,5}")
HINT = (
    "Use one of the candidate keys with a true/false value, or record the fact "
    "first with memory_store metadata.beliefs. unknown_evidence: 'drop' skips "
    "unresolved keys and reports them."
)


def slug(name: Any) -> str:
    """'Production Blocked' -> 'production_blocked'; dots separate key parts."""
    return re.sub(r"[^a-z0-9_.]+", "_", str(name).strip().lower()).strip("_.")


class Matcher:
    """Cosine over the effective claims. A claim without a stored vector from
    this embedder (NULL after a failed link, another model, a placeholder) is
    embedded in memory for this call and never written: the tool is read-only."""

    def __init__(self, store: BeliefStore, embedder):
        self.catalog = store.catalog()
        self.keys = [k for k, *_ in self.catalog]
        self.claims = dict((k, claim) for k, claim, *_ in self.catalog)
        self._embedder = embedder
        model = getattr(embedder, "model_name", None)
        rows: List[Optional[np.ndarray]] = [
            np.frombuffer(vec, dtype=np.float32)
            if vec is not None and vm == model
            else None
            for _, _, vec, vm in self.catalog
        ]
        missing = [i for i, r in enumerate(rows) if r is None]
        if missing:
            fresh = self._encode([self.catalog[i][1] for i in missing])
            for i, v in zip(missing, fresh):
                rows[i] = v
        self.matrix = self._unit(np.vstack(rows)) if rows else None

    def _encode(self, texts: List[str]) -> np.ndarray:
        return np.asarray(self._embedder.encode(texts), dtype=np.float32).reshape(
            len(texts), -1
        )

    @staticmethod
    def _unit(m: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        return m / np.where(norms == 0, 1.0, norms)

    def rank(self, text: str) -> List[Tuple[str, float]]:
        """Every belief, best first, with its cosine to `text`."""
        if not self.keys:
            return []
        q = self._unit(self._encode([text]))[0]
        if q.shape[0] != self.matrix.shape[1]:
            raise ValueError("claim vectors and query embedding differ in size")
        scores = self.matrix @ q
        order = np.argsort(-scores, kind="stable")
        return [(self.keys[i], float(scores[i])) for i in order]

    def nearest(self, text: str, n: int = NEAREST) -> List[Dict[str, Any]]:
        return [
            {"key": k, "claim": self.claims[k], "score": round(s, 4)}
            for k, s in self.rank(text)[:n]
        ]


def _resolve(store: BeliefStore, name: str) -> Optional[str]:
    key = store.resolve(name)
    return key if store.exists(key) else None


def _args(arguments: Dict[str, Any]) -> Tuple[str, Dict, str, int, datetime]:
    query = arguments.get("query", "")
    evidence = arguments.get("evidence")
    evidence = {} if evidence is None else evidence  # omitted or null only
    mode = arguments.get("unknown_evidence", "refuse")
    top_k = arguments.get("top_k", 3)
    if not isinstance(query, str) or not query.strip():
        raise BeliefValidationError("No query provided")
    if not isinstance(evidence, dict):
        raise BeliefValidationError("evidence must be an object of key: true/false")
    if mode not in ("refuse", "drop"):
        raise BeliefValidationError("unknown_evidence must be 'refuse' or 'drop'")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
        raise BeliefValidationError("top_k must be an integer from 1 to 20")
    now = arguments.get("now")
    now = parse_ts(now) if now is not None else datetime.now(timezone.utc)
    return query, evidence, mode, top_k, now


def infer(
    arguments: Dict[str, Any],
    store: Optional[BeliefStore],
    embedder,
    threshold: float = MATCH_THRESHOLD,
) -> Tuple[Dict[str, Any], bool]:
    """(payload, is_error) for one bayesian_inference call. store None means
    the belief tables do not exist yet: an empty web."""
    try:
        query, raw_evidence, mode, top_k, now = _args(arguments)
    except BeliefValidationError as e:
        return {"error": str(e)}, True
    matcher = Matcher(store, embedder) if store is not None else None
    if matcher is None or not matcher.keys:
        return {
            "error": "no beliefs recorded yet",
            "nearest": [],
            "hint": "record facts with memory_store metadata.beliefs",
        }, True

    # Evidence: slug -> alias -> key. Refused unless every entry resolves to a
    # boolean on a known belief, or the caller chose to drop the rest. Two
    # names for one belief with different values are always refused.
    clamp: Dict[str, float] = {}
    applied: Dict[str, bool] = {}
    names: Dict[str, Dict[str, bool]] = {}
    unmatched: Dict[str, List[Dict[str, Any]]] = {}
    for name, value in raw_evidence.items():
        key = _resolve(store, slug(name))
        if key is None or not isinstance(value, bool):
            unmatched[name] = [
                {"key": c["key"], "score": c["score"]}
                for c in matcher.nearest(str(name).replace("_", " ").replace(".", " "))
            ]
            continue
        names.setdefault(key, {})[name] = value
        applied[key] = value
        clamp[key] = CLAMP_L if value else -CLAMP_L
    conflicts = {k: v for k, v in names.items() if len(set(v.values())) > 1}
    if conflicts:
        return {
            "error": "evidence refused: one belief given both true and false",
            "conflicting_evidence": conflicts,
            "hint": "give each belief one value",
        }, True
    if unmatched and mode == "refuse":
        return {
            "error": "evidence refused: unknown keys or non-boolean values",
            "unmatched_evidence": unmatched,
            "hint": HINT,
        }, True

    # Query: named keys or aliases first, else claims at the threshold.
    named = []
    for token in KEY_TOKEN.findall(query.lower()):
        key = _resolve(store, token)
        if key is not None and key not in named:
            named.append(key)
    if named:
        matches = [(k, 1.0) for k in named[:top_k]]
    else:
        matches = [(k, s) for k, s in matcher.rank(query) if s >= threshold][:top_k]
    if not matches:
        return {
            "error": "no belief matches the query",
            "nearest": matcher.nearest(query),
            "hint": "name a belief key, or rephrase closer to a recorded claim",
        }, True

    # One snapshot of the component of the matched and clamped beliefs, solved
    # once; the hole predicates run on that same solution, no whole-web solve.
    keys = [k for k, _ in matches]
    web = store.web(now, keys=keys + list(clamp))
    local, p, sol = analyze(web, now, clamp)
    holes = holes_of(web, local, p, keys, 2, now)
    budget = MAX_BYTES // len(keys)  # all results together stay under the cap
    results = {
        k: _detail(web, local[k], p[k], sol, k, s, now, holes, budget)
        for k, s in matches
    }
    return {
        "results": results,
        "evidence": applied,
        "ignored_evidence": sorted(unmatched),
        "unmatched_evidence": {},
        "timeout": False,
        "converged": sol.converged,
        "iterations": sol.iterations,
        "method": METHOD,
        "backend": "belief_web",
        "now": format_ts(now),
    }, False


def _detail(web, local, p, sol, key, score, now, holes, budget) -> Dict[str, Any]:
    claim, kind, _, _ = web.attrs[key]
    # the same formatter as find_holes: per-hole caps already applied, then
    # limit and byte cap, with what was left out reported
    shown, omitted = bounded(
        [h for h in holes if key in (h.get("key"), *h.get("keys", ()))],
        max_bytes=budget,
    )
    evidence = [
        _evidence(e, llr, "active", now) for e, llr in zip(local.active, local.llrs)
    ] + [_evidence(e, 0.0, "superseded", now) for e in local.superseded]
    messages = [
        {
            "from": u,
            "type": t,
            "weight": round(sol.weights[(u, v, t)], 6),
            "contribution": round(m, 6),
        }
        for (u, v, t), m in sorted(sol.messages.items())
        if v == key
    ]
    return {
        "probabilities": {"true": p, "false": 1 - p},
        "entropy": _entropy(p),
        "claim": claim if claim is not None else key,
        "match_score": round(score, 4),
        "kind": kind or "state",
        "evidence": evidence,
        "messages": messages,
        "holes": shown,
        "holes_omitted": omitted,
    }


def _evidence(e, llr: float, status: str, now: datetime) -> Dict[str, Any]:
    return {
        "source_id": e.source_id,
        "polarity": e.polarity,
        "source_type": e.source_type,
        "age_days": round((now - e.observed_at).total_seconds() / 86400.0, 6),
        "llr": round(llr, 6),
        "status": status,
    }


def _entropy(p: float) -> float:
    """Shannon entropy in bits, as the legacy engine reports it."""
    return -sum(x * math.log2(x) for x in (p, 1 - p) if x > 0)
