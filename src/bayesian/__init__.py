"""
Bayesian Graph RAG module.

v0.8.0 component - Probabilistic inference over knowledge graphs.

Components:
- NetworkBuilder: Convert knowledge graph to Bayesian belief network
- ProbabilisticQueryEngine: Execute probabilistic queries (P(X|Y), MAP)
- BayesianGraphSync: Bidirectional sync between graph and Bayesian network (BAY-004)
"""

# Lazy imports -- pgmpy requires torch at import time (pgmpy.global_vars line 4).
# On Railway API mode, torch is not installed (~2GB saving).
# Strategy: try pgmpy first (full precision), fall back to lightweight (pure Python).
import logging as _logging

try:
    from .network_builder import NetworkBuilder
    from .probabilistic_query_engine import ProbabilisticQueryEngine
    from .bayesian_graph_sync import BayesianGraphSync
    BAYESIAN_AVAILABLE = True
    BAYESIAN_BACKEND = "pgmpy"
except ImportError:
    try:
        # Lightweight pure-Python Bayesian — no torch dependency
        from .lightweight_network_builder import LightweightNetworkBuilder as NetworkBuilder  # type: ignore[assignment]
        from .lightweight_query_engine import LightweightQueryEngine as ProbabilisticQueryEngine  # type: ignore[assignment]
        BayesianGraphSync = None  # type: ignore[assignment,misc]
        BAYESIAN_AVAILABLE = True
        BAYESIAN_BACKEND = "lightweight"
    except Exception as _e:
        _logging.getLogger(__name__).warning(f"Bayesian layer unavailable: {_e}")
        NetworkBuilder = None  # type: ignore[assignment,misc]
        ProbabilisticQueryEngine = None  # type: ignore[assignment,misc]
        BayesianGraphSync = None  # type: ignore[assignment,misc]
        BAYESIAN_AVAILABLE = False
        BAYESIAN_BACKEND = "none"

__all__ = ["NetworkBuilder", "ProbabilisticQueryEngine", "BayesianGraphSync", "BAYESIAN_AVAILABLE", "BAYESIAN_BACKEND"]
