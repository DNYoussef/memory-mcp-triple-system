"""
Choose belief_web.match_threshold on the labeled dataset (PLAN-B section 6.4).

Loads tests/fixtures/belief_match_labeled.json into a scratch BeliefStore,
ranks every query with the product Matcher (real embedder), and picks the
threshold that maximizes recall subject to a no-match false accept rate
<= 5%. Ties go to the higher threshold. Prints the confusion counts that the
gate ledger records; tests/unit/test_belief_inference.py asserts them.

Run from the repo root:
    PYTHONPATH=. python scripts/choose_match_threshold.py
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "tests" / "fixtures" / "belief_match_labeled.json"
MAX_FALSE_ACCEPT = 0.05


def load(path=DATASET):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert len(data["claims"]) == 40, len(data["claims"])
    assert len(data["queries"]) == 60, len(data["queries"])
    assert len(data["no_match"]) == 20, len(data["no_match"])
    keys = {c["key"] for c in data["claims"]}
    assert len(keys) == 40 and all(q["key"] in keys for q in data["queries"])
    return data


def build_matcher(data, embedder, db_path):
    """A store holding exactly the dataset claims, then the product Matcher."""
    from src.belief_web.belief_store import BeliefStore
    from src.belief_web.inference import Matcher

    store = BeliefStore(str(db_path))
    for c in data["claims"]:
        store.add_assertion(
            "live",
            c["key"],
            polarity=1,
            source_type="reported",
            observed_at="2026-10-14T12:00:00Z",
            recorded_at="2026-10-14T12:00:00Z",
            chunk_id="dataset",
            claim=c["claim"],
        )
    try:
        return Matcher(store, embedder)  # holds the catalog, not the store
    finally:
        store.close()


def ranked(matcher, data):
    """Top (key, score) per labeled query and the top score per no-match query."""
    labeled = [(q["key"], matcher.rank(q["query"])[0]) for q in data["queries"]]
    none = [matcher.rank(q)[0][1] for q in data["no_match"]]
    return labeled, none


def confusion(labeled, none, threshold):
    correct = sum(1 for want, (k, s) in labeled if s >= threshold and k == want)
    wrong = sum(1 for want, (k, s) in labeled if s >= threshold and k != want)
    false_accept = sum(1 for s in none if s >= threshold)
    return {
        "threshold": round(threshold, 4),
        "recall": correct / len(labeled),
        "correct": correct,
        "wrong_key": wrong,
        "missed": len(labeled) - correct - wrong,
        "no_match_false_accept": false_accept,
        "false_accept_rate": false_accept / len(none),
    }


def choose(labeled, none):
    """Every threshold between two adjacent observed scores gives the same
    counts, so the answer is an interval. Take the best feasible candidate,
    then the midpoint down to the next lower observed score, for margin on
    both sides."""
    candidates = sorted({s for _, (_, s) in labeled} | set(none))
    best = None
    for i, t in enumerate(candidates):
        c = confusion(labeled, none, t)
        if c["false_accept_rate"] <= MAX_FALSE_ACCEPT and (
            best is None or c["recall"] >= best[1]["recall"]
        ):
            best = (i, c)  # ascending, so a tie keeps the higher candidate
    if best is None:
        return None
    i, c = best
    lower = candidates[i - 1] if i else 0.0
    mid = confusion(labeled, none, (lower + candidates[i]) / 2)
    assert {k: v for k, v in mid.items() if k != "threshold"} == {
        k: v for k, v in c.items() if k != "threshold"
    }
    return {**mid, "interval": [round(lower, 4), round(candidates[i], 4)]}


def main():
    from src.indexing.embedding_pipeline import EmbeddingPipeline

    data = load()
    with tempfile.TemporaryDirectory() as tmp:
        matcher = build_matcher(data, EmbeddingPipeline(), Path(tmp) / "agent_kv.db")
        labeled, none = ranked(matcher, data)
        best = choose(labeled, none)
    print(json.dumps(best, indent=1))
    return 0 if best else 1


if __name__ == "__main__":
    sys.exit(main())
