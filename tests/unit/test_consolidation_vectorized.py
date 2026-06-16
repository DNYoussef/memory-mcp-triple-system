"""F9: vectorized pairwise cosine must match the per-pair calculation exactly."""
import numpy as np

from src.memory.consolidation import ConsolidationMixin


def test_pairwise_matches_per_pair():
    rng = np.random.default_rng(0)
    embs = rng.normal(size=(6, 8)).tolist()
    c = ConsolidationMixin.__new__(ConsolidationMixin)
    m = ConsolidationMixin._pairwise_cosine(embs)
    for i in range(len(embs)):
        for j in range(len(embs)):
            expected = c._calculate_similarity(embs[i], embs[j])
            assert abs(float(m[i, j]) - expected) < 1e-9


def test_zero_norm_row_is_zero_similarity():
    embs = [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]]
    m = ConsolidationMixin._pairwise_cosine(embs)
    assert float(m[0, 1]) == 0.0
    assert float(m[1, 0]) == 0.0
