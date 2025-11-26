"""
Memory MCP Triple System

A portable, multi-model memory system using:
- Vector RAG (ChromaDB + Sentence-Transformers)
- Graph RAG (NetworkX + HippoRAG)
- Bayesian Networks (pgmpy)

Architecture: Unified (V/G/B core + time-decay + P/E/S metadata)
See: docs/ARCHITECTURE.md for canonical reference

Version: 1.4.0 (Phase 6 Complete - Production Hardening)
"""

__version__ = "1.4.0"
__author__ = "Memory MCP Team"
