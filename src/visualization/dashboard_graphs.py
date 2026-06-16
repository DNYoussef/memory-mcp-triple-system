"""
Dashboard Graph Visualization - Unified visualization for Life OS Dashboard.

Two distinct views per user requirement:
1. Beads View: Tree/DAG for tasks (GitHub-like with completions/mergers)
2. BayesGraph View: Idea web for knowledge relationships

Future: Nodes may link across these systems.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
from enum import Enum
from loguru import logger


class GraphFormat(Enum):
    """Output format for graph export."""
    JSON = "json"
    DOT = "dot"
    MERMAID = "mermaid"
    CYTOSCAPE = "cytoscape"


class ViewType(Enum):
    """Type of graph view."""
    BEADS_DAG = "beads_dag"  # Tree/DAG task view
    IDEA_WEB = "idea_web"    # Knowledge graph view


@dataclass
class GraphNode:
    """Universal node representation."""
    id: str
    title: str
    node_type: str = "default"  # task, idea, chunk, entity
    status: str = "open"        # For tasks: open, in_progress, blocked, closed
    priority: int = 3           # 1-5
    labels: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Scoring for visualization
    pagerank: float = 0.0       # For beads
    ppr_score: float = 0.5      # For idea web
    decay_score: float = 1.0    # Memory layer indicator


@dataclass
class GraphEdge:
    """Universal edge representation."""
    source: str
    target: str
    edge_type: str = "related"  # blocks, related, references, mentions
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphData:
    """Complete graph data."""
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)
    view_type: ViewType = ViewType.IDEA_WEB


@dataclass
class ExportResult:
    """Result of graph export."""
    format: str
    view_type: str
    graph: str = ""
    nodes_count: int = 0
    edges_count: int = 0
    adjacency: Optional[Dict] = None
    explanation: Dict[str, str] = field(default_factory=dict)


# Status colors for DOT/visualization
STATUS_COLORS = {
    "open": "#50FA7B",       # Green
    "in_progress": "#8BE9FD", # Cyan
    "blocked": "#FF5555",     # Red
    "closed": "#6272A4",      # Gray-blue
}

# Memory layer colors
LAYER_COLORS = {
    "short": "#4CAF50",   # Green - recent (24h)
    "medium": "#FF9800",  # Orange - mid-term (7d)
    "long": "#9E9E9E",    # Gray - long-term (30d+)
}


class DashboardGraphVisualizer:
    """
    Unified graph visualization for Life OS Dashboard.

    Supports both Beads DAG view (tasks) and Idea Web view (knowledge).

    Usage:
        visualizer = DashboardGraphVisualizer()

        # Create beads task graph
        beads_data = visualizer.create_beads_view(tasks)
        mermaid = visualizer.export(beads_data, GraphFormat.MERMAID)

        # Create idea web graph
        web_data = visualizer.create_idea_web(chunks, edges)
        cytoscape = visualizer.export(web_data, GraphFormat.CYTOSCAPE)
    """

    def __init__(self):
        """Initialize dashboard graph visualizer."""
        logger.debug("DashboardGraphVisualizer initialized")

    def create_beads_view(
        self,
        tasks: List[Dict[str, Any]],
        include_closed: bool = True
    ) -> GraphData:
        """
        Create Beads DAG view from tasks.

        Args:
            tasks: List of task dicts with id, title, status, dependencies
            include_closed: Whether to include closed tasks

        Returns:
            GraphData configured for Beads DAG view
        """
        graph = GraphData(view_type=ViewType.BEADS_DAG)

        for task in tasks:
            if not include_closed and task.get("status") == "closed":
                continue

            node = GraphNode(
                id=task.get("id", ""),
                title=task.get("title", "Untitled"),
                node_type="task",
                status=task.get("status", "open"),
                priority=task.get("priority", 3),
                labels=task.get("labels", []),
                pagerank=task.get("pagerank", 0.0),
            )
            graph.nodes.append(node)

            # Create edges from dependencies
            for dep in task.get("dependencies", []):
                edge = GraphEdge(
                    source=task["id"],
                    target=dep.get("depends_on_id", dep) if isinstance(dep, dict) else dep,
                    edge_type=dep.get("type", "related") if isinstance(dep, dict) else "related",
                )
                graph.edges.append(edge)

        logger.debug(f"Created Beads view: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        return graph

    def create_idea_web(
        self,
        chunks: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ) -> GraphData:
        """
        Create Idea Web view from memory chunks.

        Args:
            chunks: List of memory chunk dicts with id, text, metadata
            relationships: List of edge dicts with source, target, type

        Returns:
            GraphData configured for Idea Web view
        """
        graph = GraphData(view_type=ViewType.IDEA_WEB)

        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            node = GraphNode(
                id=chunk.get("id", ""),
                title=self._extract_title(chunk),
                node_type=chunk.get("type", "chunk"),
                labels=metadata.get("tags", []),
                ppr_score=metadata.get("ppr_score", 0.5),
                decay_score=metadata.get("decay_score", 1.0),
                metadata=metadata,
            )
            graph.nodes.append(node)

        for rel in relationships:
            edge = GraphEdge(
                source=rel.get("source", ""),
                target=rel.get("target", ""),
                edge_type=rel.get("type", "related"),
                weight=rel.get("weight", 1.0),
            )
            graph.edges.append(edge)

        logger.debug(f"Created Idea Web: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        return graph

    def export(
        self,
        graph: GraphData,
        format: GraphFormat,
        root_id: Optional[str] = None,
        max_depth: int = 0
    ) -> ExportResult:
        """
        Export graph to specified format.

        Args:
            graph: GraphData to export
            format: Output format
            root_id: Optional root for subgraph extraction
            max_depth: Max depth for subgraph (0 = unlimited)

        Returns:
            ExportResult with graph in specified format
        """
        # Filter to subgraph if root specified
        if root_id:
            graph = self._extract_subgraph(graph, root_id, max_depth)

        result = ExportResult(
            format=format.value,
            view_type=graph.view_type.value,
            nodes_count=len(graph.nodes),
            edges_count=len(graph.edges),
        )

        if format == GraphFormat.DOT:
            result.graph = self._to_dot(graph)
            result.explanation = {
                "what": "Dependency graph in Graphviz DOT format",
                "how_to_render": "dot -Tpng file.dot -o graph.png",
            }

        elif format == GraphFormat.MERMAID:
            result.graph = self._to_mermaid(graph)
            result.explanation = {
                "what": "Graph in Mermaid diagram format",
                "how_to_render": "Paste into Markdown or mermaid.live",
            }

        elif format == GraphFormat.CYTOSCAPE:
            result.adjacency = self._to_cytoscape(graph)
            result.explanation = {
                "what": "Graph in Cytoscape.js JSON format",
                "how_to_render": "Load into Cytoscape.js visualization",
            }

        else:  # JSON
            result.adjacency = self._to_adjacency(graph)
            result.explanation = {
                "what": "Graph as JSON adjacency list",
            }

        return result

    def _extract_subgraph(
        self,
        graph: GraphData,
        root_id: str,
        max_depth: int
    ) -> GraphData:
        """Extract subgraph starting from root node."""
        # Build adjacency map
        adj: Dict[str, List[str]] = {n.id: [] for n in graph.nodes}
        for edge in graph.edges:
            if edge.source in adj:
                adj[edge.source].append(edge.target)

        # BFS to find reachable nodes
        visited: Set[str] = set()
        queue = [(root_id, 0)]

        while queue:
            node_id, depth = queue.pop(0)
            if node_id in visited:
                continue
            if max_depth > 0 and depth > max_depth:
                continue
            visited.add(node_id)

            for neighbor in adj.get(node_id, []):
                if neighbor not in visited:
                    queue.append((neighbor, depth + 1))

        # Filter to visited nodes
        result = GraphData(view_type=graph.view_type)
        result.nodes = [n for n in graph.nodes if n.id in visited]
        result.edges = [e for e in graph.edges if e.source in visited and e.target in visited]

        return result

    def _to_dot(self, graph: GraphData) -> str:
        """Convert to Graphviz DOT format."""
        lines = [
            "digraph G {",
            '    rankdir=LR;',
            '    node [shape=box, fontname="Helvetica", fontsize=10];',
            "",
        ]

        for node in sorted(graph.nodes, key=lambda n: n.id):
            color = self._get_node_color(node, graph.view_type)
            title = self._escape_dot(node.title[:30] + "..." if len(node.title) > 30 else node.title)
            label = f"{node.id}\\n{title}"

            if graph.view_type == ViewType.BEADS_DAG:
                label += f"\\nP{node.priority} {node.status}"

            penwidth = 1.0 + node.pagerank * 3.0 if node.pagerank else 1.0
            lines.append(f'    "{node.id}" [label="{label}", fillcolor="{color}", style=filled, penwidth={penwidth:.1f}];')

        lines.append("")

        for edge in sorted(graph.edges, key=lambda e: (e.source, e.target)):
            style = "bold" if edge.edge_type == "blocks" else "dashed"
            color = "#E53935" if edge.edge_type == "blocks" else "#999999"
            lines.append(f'    "{edge.source}" -> "{edge.target}" [style={style}, color="{color}"];')

        lines.append("}")
        return "\n".join(lines)

    def _to_mermaid(self, graph: GraphData) -> str:
        """Convert to Mermaid diagram format."""
        lines = [
            "graph TD",
            "    classDef open fill:#50FA7B,stroke:#333,color:#000",
            "    classDef inprogress fill:#8BE9FD,stroke:#333,color:#000",
            "    classDef blocked fill:#FF5555,stroke:#333,color:#000",
            "    classDef closed fill:#6272A4,stroke:#333,color:#fff",
            "    classDef short fill:#4CAF50,stroke:#333",
            "    classDef medium fill:#FF9800,stroke:#333",
            "    classDef long fill:#9E9E9E,stroke:#333",
            "",
        ]

        for node in sorted(graph.nodes, key=lambda n: n.id):
            safe_id = self._safe_mermaid_id(node.id)
            safe_title = self._escape_mermaid(node.title)
            lines.append(f'    {safe_id}["{node.id}<br/>{safe_title}"]')

            # Assign class based on view type
            if graph.view_type == ViewType.BEADS_DAG:
                cls = node.status.replace("_", "")
            else:
                cls = self._get_memory_layer(node.decay_score)
            lines.append(f"    class {safe_id} {cls}")

        lines.append("")

        for edge in sorted(graph.edges, key=lambda e: (e.source, e.target)):
            from_id = self._safe_mermaid_id(edge.source)
            to_id = self._safe_mermaid_id(edge.target)
            link = "==>" if edge.edge_type == "blocks" else "-.->"
            lines.append(f"    {from_id} {link} {to_id}")

        return "\n".join(lines)

    def _to_cytoscape(self, graph: GraphData) -> Dict[str, Any]:
        """Convert to Cytoscape.js JSON format."""
        nodes = []
        for node in graph.nodes:
            color = self._get_node_color(node, graph.view_type)
            size = 30 + int(50 * (node.ppr_score ** 0.5)) if node.ppr_score else 40

            nodes.append({
                "data": {
                    "id": node.id,
                    "label": node.title[:50],
                    "type": node.node_type,
                    "nodeColor": color,
                    "width": size,
                    "height": size,
                    "pprScore": node.ppr_score,
                    "decayScore": node.decay_score,
                }
            })

        edges = []
        for edge in graph.edges:
            edges.append({
                "data": {
                    "source": edge.source,
                    "target": edge.target,
                    "type": edge.edge_type,
                    "weight": edge.weight,
                }
            })

        return {"nodes": nodes, "edges": edges}

    def _to_adjacency(self, graph: GraphData) -> Dict[str, Any]:
        """Convert to JSON adjacency list."""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "title": n.title,
                    "type": n.node_type,
                    "status": n.status,
                    "priority": n.priority,
                    "labels": n.labels,
                }
                for n in graph.nodes
            ],
            "edges": [
                {
                    "from": e.source,
                    "to": e.target,
                    "type": e.edge_type,
                }
                for e in graph.edges
            ],
        }

    def _extract_title(self, chunk: Dict) -> str:
        """Extract title from chunk."""
        metadata = chunk.get("metadata", {})
        return (
            metadata.get("title") or
            metadata.get("name") or
            chunk.get("text", "")[:50] or
            chunk.get("id", "Untitled")
        )

    def _get_node_color(self, node: GraphNode, view_type: ViewType) -> str:
        """Get node color based on view type."""
        if view_type == ViewType.BEADS_DAG:
            return STATUS_COLORS.get(node.status, "#FFFFFF")
        else:
            layer = self._get_memory_layer(node.decay_score)
            return LAYER_COLORS.get(layer, "#2196F3")

    def _get_memory_layer(self, decay_score: float) -> str:
        """Determine memory layer from decay score."""
        if decay_score > 0.8:
            return "short"
        elif decay_score > 0.5:
            return "medium"
        return "long"

    def _escape_dot(self, text: str) -> str:
        """Escape text for DOT format."""
        return text.replace("\\", "\\\\").replace('"', '\\"')

    def _escape_mermaid(self, text: str) -> str:
        """Escape text for Mermaid format."""
        return text.replace('"', "'").replace("<", "&lt;").replace(">", "&gt;")

    def _safe_mermaid_id(self, id: str) -> str:
        """Create safe Mermaid node ID."""
        return "".join(c if c.isalnum() else "_" for c in id)
