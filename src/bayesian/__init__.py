"""
Bayesian Graph RAG module.

v0.8.0 component - Probabilistic inference over knowledge graphs.

Components:
- NetworkBuilder: Convert knowledge graph to Bayesian belief network
- ProbabilisticQueryEngine: Execute probabilistic queries (P(X|Y), MAP)
"""

from src.bayesian.network_builder import NetworkBuilder
from src.bayesian.probabilistic_query_engine import ProbabilisticQueryEngine

__all__ = ["NetworkBuilder", "ProbabilisticQueryEngine"]
