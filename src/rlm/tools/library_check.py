"""
RLM-Powered Library Check Tool.

RLM-013: Enhances pre-coding library check with recursive codebase exploration.
Replaces the 3-tier search strategy with RLM pattern matching.

Key Features:
- Uses RLMCodebaseEnvironment for cross-project search
- Finds similar implementations automatically
- Suggests reuse vs build-new decisions
- Logs results to Memory MCP

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from loguru import logger

# Add project path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.rlm.rlm_codebase_env import (  # noqa: E402
    RLMCodebaseEnvironment,
    PatternType,
    PATTERN_SIGNATURES,
)


@dataclass
class LibraryCheckResult:
    """Result of a library check query.

    RLM-013: Contains matched patterns, similar files, and recommendations.

    Attributes:
        query: Original search query
        pattern_matches: Patterns found matching query
        similar_files: Files with similar implementations
        recommendation: REUSE, ADAPT, FOLLOW, EXTRACT, or BUILD_NEW
        confidence: Recommendation confidence (0.0-1.0)
        time_saved_hours: Estimated hours saved by reuse
        search_stats: Statistics about the search
    """

    query: str
    pattern_matches: List[Dict[str, Any]] = field(default_factory=list)
    similar_files: List[Dict[str, Any]] = field(default_factory=list)
    recommendation: str = "BUILD_NEW"
    confidence: float = 0.0
    time_saved_hours: float = 0.0
    search_stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "pattern_matches": self.pattern_matches,
            "similar_files": self.similar_files,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "time_saved_hours": self.time_saved_hours,
            "search_stats": self.search_stats,
            "timestamp": datetime.utcnow().isoformat(),
        }


class RLMLibraryCheck:
    """
    RLM-013: RLM-powered library check for pre-coding decisions.

    Uses RLMCodebaseEnvironment to search across all projects for
    existing implementations, patterns, and reusable code.

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    # Decision thresholds
    REUSE_THRESHOLD = 0.90
    ADAPT_THRESHOLD = 0.70
    FOLLOW_THRESHOLD = 0.50
    EXTRACT_THRESHOLD = 0.30

    # Time saved estimates (hours)
    TIME_SAVED = {
        "REUSE": 8.0,
        "ADAPT": 5.0,
        "FOLLOW": 3.0,
        "EXTRACT": 1.5,
        "BUILD_NEW": 0.0,
    }

    def __init__(self, env: Optional[RLMCodebaseEnvironment] = None):
        """
        Initialize library check tool.

        Args:
            env: RLMCodebaseEnvironment instance (creates new if None)

        NASA Rule 10: 10 LOC (<=60)
        """
        self._env = env
        self._env_initialized = False
        self._check_count = 0

        logger.info("RLMLibraryCheck initialized")

    def _ensure_env(self) -> RLMCodebaseEnvironment:
        """Lazy load and initialize environment."""
        if self._env is None:
            self._env = RLMCodebaseEnvironment()

        if not self._env_initialized:
            self._env.load_data("all")
            self._env_initialized = True

        return self._env

    def check(
        self,
        query: str,
        context: Optional[str] = None,
        languages: Optional[List[str]] = None,
    ) -> LibraryCheckResult:
        """
        RLM-013: Perform library check for a coding task.

        Searches the codebase for existing implementations and patterns
        that match the query, then recommends whether to reuse or build new.

        Args:
            query: Description of what needs to be built
            context: Additional context about the task
            languages: Limit search to specific languages

        Returns:
            LibraryCheckResult with matches and recommendation

        NASA Rule 10: 55 LOC (<=60)
        """
        env = self._ensure_env()
        self._check_count += 1

        result = LibraryCheckResult(query=query)

        # Step 1: Search for patterns in query
        query_lower = query.lower()
        detected_patterns: List[PatternType] = []

        for pattern_type, sig in PATTERN_SIGNATURES.items():
            keywords = sig.get("keywords", [])
            if any(kw in query_lower for kw in keywords):
                detected_patterns.append(pattern_type)

        # Step 2: Search for pattern implementations
        for pattern_type in detected_patterns[:5]:  # Limit to 5 patterns
            matches = env.search_patterns(
                pattern_type=pattern_type, languages=languages, limit=5
            )
            result.pattern_matches.extend(matches)

        # Step 3: Content search for query terms
        content_matches = env.search_content(
            pattern=query, language=languages[0] if languages else None, limit=10
        )

        for match in content_matches:
            result.similar_files.append(
                {
                    "file_path": match.get("path", match.get("file_path")),
                    "project": match.get("project"),
                    "match_line": match.get("match_line"),
                    "match_preview": match.get("match_preview", "")[:100],
                }
            )

        # Step 4: Calculate recommendation
        result = self._calculate_recommendation(result)

        # Step 5: Record stats
        result.search_stats = {
            "patterns_checked": len(detected_patterns),
            "pattern_matches_found": len(result.pattern_matches),
            "similar_files_found": len(result.similar_files),
            "languages_searched": languages or ["all"],
        }

        logger.info(
            f"Library check: query='{query[:50]}' recommendation={result.recommendation} "
            f"confidence={result.confidence:.2f}"
        )

        return result

    def _calculate_recommendation(
        self, result: LibraryCheckResult
    ) -> LibraryCheckResult:
        """
        Calculate recommendation based on matches.

        Args:
            result: LibraryCheckResult to update

        Returns:
            Updated result with recommendation

        NASA Rule 10: 35 LOC (<=60)
        """
        # Score based on match quality
        pattern_score = 0.0
        if result.pattern_matches:
            # Average confidence of pattern matches
            pattern_score = sum(
                m.get("confidence", 0.5) for m in result.pattern_matches
            ) / len(result.pattern_matches)

        file_score = 0.0
        if result.similar_files:
            # More similar files = higher score
            file_score = min(len(result.similar_files) / 10, 1.0)

        # Combined score
        combined_score = pattern_score * 0.6 + file_score * 0.4

        # Determine recommendation
        if combined_score >= self.REUSE_THRESHOLD:
            result.recommendation = "REUSE"
        elif combined_score >= self.ADAPT_THRESHOLD:
            result.recommendation = "ADAPT"
        elif combined_score >= self.FOLLOW_THRESHOLD:
            result.recommendation = "FOLLOW"
        elif combined_score >= self.EXTRACT_THRESHOLD:
            result.recommendation = "EXTRACT"
        else:
            result.recommendation = "BUILD_NEW"

        result.confidence = combined_score
        result.time_saved_hours = self.TIME_SAVED.get(result.recommendation, 0.0)

        return result

    def check_file(
        self, file_path: str, languages: Optional[List[str]] = None
    ) -> LibraryCheckResult:
        """
        RLM-013: Check for similar implementations to a file.

        Args:
            file_path: Path to reference file
            languages: Limit search to specific languages

        Returns:
            LibraryCheckResult with similar files

        NASA Rule 10: 25 LOC (<=60)
        """
        env = self._ensure_env()
        self._check_count += 1

        result = LibraryCheckResult(query=f"similar to {Path(file_path).name}")

        # Find similar implementations
        similar = env.find_similar_implementations(file_path)

        for sim in similar:
            result.similar_files.append(
                {
                    "file_path": sim["file_path"],
                    "project": sim["project"],
                    "shared_patterns": sim["shared_patterns"],
                    "same_project": sim.get("same_project", False),
                }
            )

        result = self._calculate_recommendation(result)

        result.search_stats = {
            "reference_file": file_path,
            "similar_files_found": len(result.similar_files),
        }

        return result

    def quick_search(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        RLM-013: Quick keyword search across codebase.

        Fast search for files containing a keyword.

        Args:
            keyword: Keyword to search
            limit: Maximum results

        Returns:
            List of matching files

        NASA Rule 10: 15 LOC (<=60)
        """
        env = self._ensure_env()

        matches = env.search_content(pattern=keyword, limit=limit)

        return [
            {
                "file_path": m.get("path", m.get("file_path")),
                "project": m.get("project"),
                "line": m.get("match_line"),
                "preview": m.get("match_preview", "")[:100],
            }
            for m in matches
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get tool statistics."""
        env_stats = self._env.get_stats() if self._env else {}
        return {
            "check_count": self._check_count,
            "env_initialized": self._env_initialized,
            "env_stats": env_stats,
        }


def format_advisory(result: LibraryCheckResult) -> str:
    """
    Format library check result as advisory message.

    Args:
        result: LibraryCheckResult to format

    Returns:
        Formatted advisory string

    NASA Rule 10: 45 LOC (<=60)
    """
    lines = [
        "=" * 60,
        "!! RLM LIBRARY CHECK: PRE-CODING ADVISORY !!",
        "=" * 60,
        f"Query: {result.query}",
        "",
        f"RECOMMENDATION: {result.recommendation}",
        f"Confidence: {result.confidence:.0%}",
        f"Estimated Time Saved: {result.time_saved_hours:.1f} hours",
        "",
    ]

    if result.pattern_matches:
        lines.append("PATTERN MATCHES:")
        for match in result.pattern_matches[:5]:
            lines.append(f"  - [{match['pattern_type']}] {match['file_path']}")
            lines.append(
                f"    Line {match['line_number']}: {match['match_preview'][:60]}..."
            )
        lines.append("")

    if result.similar_files:
        lines.append("SIMILAR FILES:")
        for sim in result.similar_files[:5]:
            lines.append(f"  - {sim['file_path']}")
            if sim.get("match_preview"):
                lines.append(f"    Preview: {sim['match_preview'][:60]}...")
        lines.append("")

    lines.extend(
        [
            "-" * 60,
            "DECISION MATRIX:",
            "| REUSE (>90%)    | Copy existing code       | 8+ hours saved |",
            "| ADAPT (70-90%)  | Modify existing          | 5 hours saved  |",
            "| FOLLOW (50-70%) | Use as reference         | 3 hours saved  |",
            "| EXTRACT (30-50%)| Extract reusable parts   | 1.5 hours saved|",
            "| BUILD_NEW (<30%)| Implement from scratch   | Proceed        |",
            "-" * 60,
            "",
            f"Search Stats: {result.search_stats}",
            "=" * 60,
        ]
    )

    return "\n".join(lines)


# CLI interface for hook integration
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RLM Library Check")
    parser.add_argument("query", help="What you want to build")
    parser.add_argument("--lang", "-l", help="Language filter")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    args = parser.parse_args()

    checker = RLMLibraryCheck()
    result = checker.check(
        query=args.query, languages=[args.lang] if args.lang else None
    )

    if args.json:
        import json

        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_advisory(result))
