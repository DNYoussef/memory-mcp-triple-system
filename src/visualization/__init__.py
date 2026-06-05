"""
Visualization modules for Life OS Dashboard.

Two distinct views per architectural decision:
1. Beads View: Tree/DAG for tasks (GitHub-like)
2. BayesGraph View: Idea web for knowledge relationships
"""

from .dashboard_graphs import (
    DashboardGraphVisualizer,
    GraphData,
    GraphNode,
    GraphEdge,
    GraphFormat,
    ViewType,
    ExportResult,
)

__all__ = [
    "DashboardGraphVisualizer",
    "GraphData",
    "GraphNode",
    "GraphEdge",
    "GraphFormat",
    "ViewType",
    "ExportResult",
]
