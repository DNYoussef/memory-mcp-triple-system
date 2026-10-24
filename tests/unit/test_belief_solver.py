"""
Belief web solver fixtures (PLAN-B section 6.1, F-series, W, D).

Every expected value is the one asserted by the plan's reference calculator
(belief_calc_r8.py). Tolerance 1e-6, F25 1e-4.
"""

import math
import random
from datetime import datetime, timezone

import pytest

from src.belief_web.solver import (
    EdgeConflict,
    Evidence,
    local_logodds,
    logit,
    reduce_edges,
    sigmoid,
    solve,
)

T12, T15 = "2026-10-14T12:00:00Z", "2026-10-14T15:00:00Z"
OLD14 = "2026-09-30T15:00:00Z"
REL = {"witnessed": 0.95, "reported": 0.70, "inferred": 0.60, "assumed": 0.55}
a9, a95, a7, a8, a6 = logit(0.9), logit(0.95), logit(0.7), logit(0.8), logit(0.6)


def ts(s):
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def ev(pol, st, obs, rec=None, r=None):
    return Evidence(pol, r if r is not None else REL[st], st, ts(obs), ts(rec or obs))


def P(evs, kind, now, h=None):
    return sigmoid(local_logodds(evs, kind, ts(now), h).L)


def holes(llrs):
    """Calculator holes_local: the product predicates land in B-PR4 (find_holes)."""
    out = set()
    if any(x >= 0.4 for x in llrs) and any(x <= -0.4 for x in llrs):
        out.add("contradicted")
    if sum(abs(x) for x in llrs) < 0.1:
        out.add("unsupported")
    return out


def approx(want, tol=1e-6):
    return pytest.approx(want, abs=tol)


# ---------------------------------------------------------------- local log-odds


def test_llr_table():
    assert a9 == approx(2.197225)
    assert a95 == approx(2.944439)
    assert a7 == approx(0.847298)
    assert a8 == approx(1.386294)
    assert a6 == approx(0.405465)


def test_f1_fresh():
    loc = local_logodds([ev(1, "witnessed", T15, r=0.9)], "state", ts(T15))
    assert loc.L == approx(2.197225)
    assert sigmoid(loc.L) == approx(0.9)


def test_f2_half_life_defaults_and_override():
    e = [ev(1, "witnessed", OLD14, r=0.9)]
    assert P(e, "state", T15) == approx(0.75)  # F2 omitted
    assert P(e, "state", T15, None) == approx(0.75)  # F2n explicit null
    assert P(e, "state", T15, 7.0) == approx(sigmoid(a9 / 4))  # F2o
    assert P(
        [ev(1, "witnessed", "2026-09-14T15:00:00Z", r=0.9)], "plan", T15
    ) == approx(0.75)
    assert P(
        [ev(1, "witnessed", "2025-10-14T15:00:00Z", r=0.9)], "fact", T15
    ) == approx(0.75)


def test_f3_note_after_check_is_contradicted():
    loc = local_logodds(
        [ev(1, "witnessed", T12), ev(-1, "reported", T15)], "state", ts(T15)
    )
    assert sigmoid(loc.L) == approx(0.888843)
    assert sigmoid(loc.L) == approx(sigmoid(a95 * 2 ** (-(3 / 24) / 14) - a7))
    assert "contradicted" in holes(loc.llrs)


def test_f3a_note_before_check_is_superseded():
    loc = local_logodds(
        [ev(-1, "reported", T12), ev(1, "witnessed", T15)], "state", ts(T15)
    )
    assert sigmoid(loc.L) == approx(0.95)
    assert len(loc.superseded) == 1 and loc.superseded[0].polarity == -1


def test_f3b_fact_has_no_supersession():
    e = [ev(1, "witnessed", T15), ev(-1, "reported", "2026-10-04T15:00:00Z")]
    assert P(e, "fact", T15, 14.0) == approx(0.918938)


def test_f9_tie_is_contradicted():
    loc = local_logodds(
        [ev(1, "witnessed", T15, r=0.9), ev(-1, "witnessed", T15, r=0.9)],
        "state",
        ts(T15),
    )
    assert sigmoid(loc.L) == approx(0.5)
    assert "contradicted" in holes(loc.llrs)


def test_f13_empty_is_unsupported():
    loc = local_logodds([], "state", ts(T15))
    assert sigmoid(loc.L) == approx(0.5)
    assert "unsupported" in holes(loc.llrs)


def test_f15_independent_sources_count():
    assert P([ev(1, "witnessed", T15), ev(1, "witnessed", T15)], "fact", T15) == approx(
        0.997238
    )
    four = [ev(1, "witnessed", T15)] + [ev(-1, "reported", T15)] * 4
    assert P(four, "state", T15) == approx(0.390609)


def test_f16_state_transition_and_fact_control():
    e = [ev(-1, "witnessed", "2026-10-13T15:00:00Z"), ev(1, "witnessed", T15)]
    assert P(e, "state", T15) == approx(0.95)
    assert P(e, "fact", T15, 14.0) == approx(0.535498)


def test_f27_future_evidence_excluded():
    assert P([ev(1, "witnessed", "2026-10-28T15:00:00Z")], "state", T15) == approx(0.5)
    late = [ev(1, "witnessed", T12, rec="2026-10-15T00:00:00Z")]
    assert P(late, "state", T15) == approx(0.5)  # F27r replay


def test_d1_decay_without_write():
    e = [ev(1, "witnessed", T15, r=0.9)]
    assert P(e, "state", T15) == approx(0.9)
    assert P(e, "state", "2026-10-28T15:00:00Z") == approx(0.75)


# ---------------------------------------------------------------- propagation


def p_of(L0, rows, key, **kw):
    return sigmoid(solve(L0, rows, **kw).L[key])


def test_f4_chain():
    sol = solve({"A": a9, "B": 0.0}, [("supports", "A", "B", 0.5)])
    assert sol.L["B"] == approx(0.8, 1e-4)
    assert sigmoid(sol.L["B"]) == approx(0.689974)
    assert sol.converged


def test_f5_excludes():
    sol = solve({"A": a9, "B": 0.0}, [("excludes", "A", "B", 0.5)])
    assert sigmoid(sol.L["A"]) == approx(0.9)
    assert sigmoid(sol.L["B"]) == approx(0.310026)


def test_f6_two_cycle_cavity():
    rows = [("supports", "A", "B", 0.5), ("supports", "B", "A", 0.5)]
    sol = solve({"A": a9, "B": 0.0}, rows)
    assert sigmoid(sol.L["A"]) == approx(0.9)
    assert sigmoid(sol.L["B"]) == approx(0.689974)


def test_f7_normalization():
    sol = solve(
        {"A": a9, "B": a9, "C": a9, "D": 0.0},
        [("supports", x, "D", 0.5) for x in "ABC"],
    )
    assert sol.L["D"] == approx(1.44)
    assert all(w == approx(0.3) for (u, v, _), w in sol.weights.items() if v == "D")


def test_f10_load_children():
    sol = solve(
        {"X": a6, "Y": 0.0, "Z": 0.0, "W": 0.0},
        [("supports", "X", y, 0.8) for y in "YZW"],
    )
    assert sigmoid(sol.L["X"]) == approx(0.6)
    for y in "YZW":
        assert sigmoid(sol.L[y]) == approx(sigmoid(0.32))
        assert sigmoid(sol.L[y]) == approx(0.5793, 1e-4)


def test_f11_three_cycle_bounded_echo():
    rows = [
        ("supports", "A", "B", 0.5),
        ("supports", "B", "C", 0.5),
        ("supports", "C", "A", 0.5),
    ]
    pa = p_of({"A": a9, "B": 0.0, "C": 0.0}, rows, "A")
    assert pa == approx(0.916183)
    assert pa < 0.92


def test_f12_excludes_both_evidenced():
    sol = solve({"A": a9, "B": a8}, [("excludes", "A", "B", 0.5)])
    assert sol.L["A"] == approx(a9 - 0.6)
    assert sol.L["B"] == approx(a8 - 0.8)
    assert sigmoid(sol.L["A"]) + sigmoid(sol.L["B"]) > 1.1  # contradicted_pair


def test_f17_f18_false_source_says_nothing():
    assert p_of({"A": -a9, "B": 0.0}, [("supports", "A", "B", 0.5)], "B") == approx(0.5)
    assert p_of({"A": -a9, "B": 0.0}, [("excludes", "A", "B", 0.5)], "B") == approx(0.5)


def test_f19_f20_depends_on_one_sided():
    assert solve({"a": 0.0, "b": -a9}, [("depends_on", "a", "b", 0.5)]).L[
        "a"
    ] == approx(-0.8)
    assert p_of({"a": 0.0, "b": a9}, [("depends_on", "a", "b", 0.5)], "a") == approx(
        0.5
    )


def test_f21_supports_plus_depends_on_kept_separately():
    rows = [("supports", "b", "a", 0.5), ("depends_on", "a", "b", 0.5)]
    sol = solve({"a": 0.0, "b": -a9}, rows)
    assert sol.L["a"] == approx(-0.72)
    assert sorted(sol.weights.values()) == [approx(0.45), approx(0.45)]


@pytest.mark.parametrize(
    "rows",
    [
        [("supports", "A", "B", 0.5), ("excludes", "A", "B", 0.5)],  # F22
        [("supports", "A", "B", 0.5), ("excludes", "B", "A", 0.5)],  # F22 reversed
        [("supports", "A", "A", 0.5)],  # F23
    ],
)
def test_f22_f23_rejected(rows):
    with pytest.raises(EdgeConflict):
        reduce_edges(rows)
    with pytest.raises(EdgeConflict):
        solve({"A": 0.0, "B": 0.0}, rows)


def test_reduce_keeps_max_weight_and_positive_control():
    rules = reduce_edges([("supports", "A", "B", 0.2), ("supports", "A", "B", 0.7)])
    assert rules == {("A", "B", "supports"): 0.7}


def test_f24_clamp():
    rows = [("supports", "A", "B", 0.9), ("supports", "B", "A", 0.9)]
    sol = solve({"A": a9, "B": a8}, rows, clamp={"A": 7.0})
    assert sol.L["A"] == pytest.approx(7.0, abs=1e-12)
    assert not any(v == "A" for (_, v, _) in sol.weights)
    assert sol.messages[("A", "B", "supports")] == approx(1.796720)
    assert sol.messages[("A", "B", "supports")] == approx(1.8 * math.tanh(3.5))
    assert sol.L["B"] == approx(a8 + 1.8 * math.tanh(3.5))
    assert sigmoid(sol.L["B"]) == approx(0.9602, 1e-4)


def test_f25_order_independent():
    rows = [
        ("supports", "A", "B", 0.5),
        ("depends_on", "C", "B", 0.4),
        ("excludes", "A", "D", 0.6),
        ("supports", "D", "C", 0.3),
        ("supports", "C", "A", 0.2),
    ]
    L0 = {"A": a9, "B": 0.0, "C": -a7, "D": a6}
    base = solve(L0, rows).L
    rng = random.Random(7)
    for _ in range(50):
        got = solve(L0, rng.sample(rows, len(rows))).L
        assert max(abs(got[k] - base[k]) for k in base) < 1e-12
    for k, want in (("A", 0.8762), ("B", 0.6797), ("C", 0.3000), ("D", 0.3648)):
        assert sigmoid(base[k]) == approx(want, 1e-4)


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
        rows.append(
            (
                rng.choice(["supports", "excludes", "depends_on"]),
                a,
                b,
                rng.uniform(0.05, 1),
            )
        )
    return L0, rows


def test_f26_random_web_contracts():
    L0, rows = f26_web()
    sol = solve(L0, rows)
    assert sol.converged
    assert sol.iterations < 1000
    ratios = [b / a for a, b in zip(sol.deltas, sol.deltas[1:]) if a > 1e-10]
    assert ratios
    assert max(ratios) <= 0.9 + 1e-9
    assert max(ratios) == approx(0.638728)


def test_w1_w2_weight_change_moves_answer():
    assert p_of({"A": a9, "B": 0.0}, [("supports", "A", "B", 0.1)], "B") == approx(
        0.539915
    )
    assert p_of({"A": a9, "B": 0.0}, [("supports", "A", "B", 0.9)], "B") == approx(
        0.808455
    )


def test_round_cap_reports_not_converged():
    sol = solve({"A": a9, "B": 0.0}, [("supports", "A", "B", 0.5)], max_rounds=1)
    assert sol.converged is False
    assert sol.iterations == 1


def test_sigmoid_is_stable_at_extremes():
    assert sigmoid(-1000.0) == 0.0
    assert sigmoid(1000.0) == 1.0
    assert 0.0 < sigmoid(-736.1097447916098) < 1e-300
    assert sigmoid(-2.0) == approx(1 / (1 + math.exp(2.0)), 1e-15)
    assert sigmoid(2.0) == approx(1 / (1 + math.exp(-2.0)), 1e-15)


def test_underflowed_weight_is_dropped_not_divided_by():
    three = [
        ("supports", x, "D", w) for x, w in (("A", 5e-324), ("B", 1.0), ("C", 1.0))
    ]
    two = three[1:]
    L0 = {"A": a9, "B": a9, "C": a9, "D": 0.0}
    got = solve(L0, three)
    want = solve(L0, two)
    assert got.converged
    assert got.L["D"] == want.L["D"]
    assert ("A", "D", "supports") not in got.weights
