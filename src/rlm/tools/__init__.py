"""
RLM Tools Package.

RLM-006: Search tools for Memory MCP integration.
RLM-011: Code-specific search tools for codebase navigation.
RLM-013: Library check tool for pre-coding decisions.
"""

from .search_tools import (
    search_by_namespace,
    search_by_time_range,
    search_by_content,
    search_graph_edges,
    SearchResult,
    TimeRange,
    GraphEdgeFilter,
    RLMSearchTools,
)

from .code_tools import (
    find_function,
    find_class,
    find_imports,
    trace_calls,
    CodeSymbol,
    FunctionCall,
    RLMCodeTools,
)

from .library_check import (
    RLMLibraryCheck,
    LibraryCheckResult,
    format_advisory,
)

from .session_search import (
    RLMSessionSearch,
    SessionLearning,
    SimilarLearning,
    format_search_results,
)

from .learning_aggregator import (
    RLMLearningAggregator,
    AggregatedLearning,
    ExpertiseGap,
    OptimizationRecommendation,
)

__all__ = [
    # Search tools (RLM-006)
    "search_by_namespace",
    "search_by_time_range",
    "search_by_content",
    "search_graph_edges",
    "SearchResult",
    "TimeRange",
    "GraphEdgeFilter",
    "RLMSearchTools",
    # Code tools (RLM-011)
    "find_function",
    "find_class",
    "find_imports",
    "trace_calls",
    "CodeSymbol",
    "FunctionCall",
    "RLMCodeTools",
    # Library check (RLM-013)
    "RLMLibraryCheck",
    "LibraryCheckResult",
    "format_advisory",
    # Session search (RLM-014)
    "RLMSessionSearch",
    "SessionLearning",
    "SimilarLearning",
    "format_search_results",
    # Learning aggregator (RLM-015)
    "RLMLearningAggregator",
    "AggregatedLearning",
    "ExpertiseGap",
    "OptimizationRecommendation",
]
