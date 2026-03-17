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
# Graceful degradation: Bayesian layer returns empty results if pgmpy unavailable.
try:
    from src.bayesian.network_builder import NetworkBuilder
    from src.bayesian.probabilistic_query_engine import ProbabilisticQueryEngine
    from src.bayesian.bayesian_graph_sync import BayesianGraphSync
    BAYESIAN_AVAILABLE = True
except ImportError:
    NetworkBuilder = None  # type: ignore[assignment,misc]
    ProbabilisticQueryEngine = None  # type: ignore[assignment,misc]
    BayesianGraphSync = None  # type: ignore[assignment,misc]
    BAYESIAN_AVAILABLE = False

__all__ = ["NetworkBuilder", "ProbabilisticQueryEngine", "BayesianGraphSync", "BAYESIAN_AVAILABLE"]
