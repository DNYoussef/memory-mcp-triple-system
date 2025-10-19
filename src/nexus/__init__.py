"""
Nexus Processor module for unified multi-tier RAG retrieval.

This module provides the final integration layer that combines:
- Vector RAG (Chromabd)
- HippoRAG (Multi-hop graph reasoning)
- Bayesian Graph RAG (Probabilistic inference)

Key Components:
- NexusProcessor: 5-step SOP pipeline (Recall → Filter → Deduplicate → Rank → Compress)
"""

from .processor import NexusProcessor

__all__ = ["NexusProcessor"]
