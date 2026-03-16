"""
RLM Codebase Environment - AI Exoskeleton project indexer.

RLM-009: Create project index across 18 AI Exoskeleton projects.
Enables self-referential code analysis by indexing all project files.

Key Features:
- Index files across 18+ projects
- Language-aware file filtering
- Content search and retrieval
- Cross-project pattern detection

Projects:
- context-cascade, memory-mcp, connascence
- life-os-dashboard, life-os-frontend, claude-dev-cli
- trader-ai, fog-compute, the-agent-maker
- dnyoussef-portfolio, slop-detector, and more

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import os
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, Tuple
from loguru import logger

from .rlm_environment import RLMEnvironment, RLMConfig, RLMResult, ExecutionContext


# GuardSpine Autonomous Business System -- all indexed codebases
GUARDSPINE_PROJECTS = {
    # Core Product
    "guardspine": "D:/Projects/GuardSpine",
    "guardspine-kernel": "D:/Projects/guardspine-kernel",
    "guardspine-kernel-py": "D:/Projects/guardspine-kernel-py",
    "codeguard-action": "D:/Projects/codeguard-action",
    # Execution Layer
    "openclaw-upstream": "D:/Projects/openclaw-upstream",
    "paperclip": "D:/Projects/paperclip",
    # Workflow & Integration
    "n8n-nodes-guardspine": "D:/Projects/n8n-nodes-guardspine",
    "guardspine-ops": "D:/Projects/guardspine-ops",
    # Infrastructure
    "memory-mcp": "D:/Projects/memory-mcp-triple-system",
    "connascence": "D:/Projects/connascence",
    "slop-detector": "D:/Projects/slop-detector",
}
# Legacy alias
AI_EXOSKELETON_PROJECTS = GUARDSPINE_PROJECTS

# File extensions to index by language
LANGUAGE_EXTENSIONS = {
    "python": [".py"],
    "typescript": [".ts", ".tsx"],
    "javascript": [".js", ".jsx"],
    "markdown": [".md"],
    "yaml": [".yaml", ".yml"],
    "json": [".json"],
    "rust": [".rs"],
    "shell": [".sh", ".bash", ".ps1"],
}

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".cache", "coverage", ".pytest_cache",
    "chroma_data", ".beads", "logs",
}


# =============================================================================
# RLM-012: Cross-Project Pattern Search Definitions
# =============================================================================

class PatternType(str, Enum):
    """Common implementation patterns to search across projects."""
    RETRY_LOGIC = "retry_logic"
    CIRCUIT_BREAKER = "circuit_breaker"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    DECAY_PATTERN = "decay_pattern"
    SINGLETON = "singleton"
    FACTORY = "factory"
    OBSERVER = "observer"
    CACHING = "caching"
    RATE_LIMITING = "rate_limiting"
    VALIDATION = "validation"
    ERROR_HANDLING = "error_handling"
    LOGGING = "logging"
    AUTH_PATTERN = "auth_pattern"
    API_CLIENT = "api_client"


# Pattern search signatures - regex patterns and keywords
PATTERN_SIGNATURES: Dict[PatternType, Dict[str, Any]] = {
    PatternType.RETRY_LOGIC: {
        "keywords": ["retry", "max_retries", "attempt", "retry_count", "retries"],
        "regex": [
            r"for\s+\w+\s+in\s+range\s*\(\s*\w*retries?\w*",
            r"while\s+\w*attempt\w*\s*<",
            r"@retry",
            r"tenacity\.",
        ],
        "indicators": ["sleep", "backoff", "delay"],
    },
    PatternType.CIRCUIT_BREAKER: {
        "keywords": ["circuit_breaker", "breaker", "half_open", "open_state"],
        "regex": [
            r"class\s+\w*Circuit\w*Breaker",
            r"CircuitBreaker\s*\(",
            r"state\s*[=:]\s*['\"]?(open|closed|half)",
        ],
        "indicators": ["failure_count", "threshold", "reset_timeout"],
    },
    PatternType.EXPONENTIAL_BACKOFF: {
        "keywords": ["exponential_backoff", "backoff", "exp_backoff"],
        "regex": [
            r"\*\s*2\s*\*\*",
            r"2\s*\*\*\s*attempt",
            r"backoff\s*=\s*base\s*\*",
            r"min\s*\(\s*\w+\s*\*\s*2",
        ],
        "indicators": ["jitter", "max_backoff", "base_delay"],
    },
    PatternType.DECAY_PATTERN: {
        "keywords": ["decay", "ttl", "expiry", "expire", "freshness"],
        "regex": [
            r"e\s*\*\*\s*\(-",
            r"math\.exp\s*\(-",
            r"decay_rate\s*\*",
            r"age\s*/\s*\w+",
        ],
        "indicators": ["timestamp", "created_at", "stale"],
    },
    PatternType.SINGLETON: {
        "keywords": ["singleton", "_instance", "instance"],
        "regex": [
            r"_instance\s*=\s*None",
            r"if\s+\w*_instance\w*\s+is\s+None",
            r"__new__.*_instance",
        ],
        "indicators": ["cls._instance", "self.__class__._instance"],
    },
    PatternType.FACTORY: {
        "keywords": ["factory", "create", "build", "make"],
        "regex": [
            r"class\s+\w*Factory",
            r"def\s+create_\w+",
            r"def\s+build_\w+",
            r"@classmethod.*create",
        ],
        "indicators": ["register", "registry", "builder"],
    },
    PatternType.CACHING: {
        "keywords": ["cache", "cached", "memoize", "lru_cache"],
        "regex": [
            r"@cache",
            r"@lru_cache",
            r"@functools\.cache",
            r"_cache\s*[=:]",
            r"cache\.get\s*\(",
        ],
        "indicators": ["ttl", "invalidate", "expire"],
    },
    PatternType.RATE_LIMITING: {
        "keywords": ["rate_limit", "throttle", "limiter", "bucket"],
        "regex": [
            r"class\s+\w*RateLimiter",
            r"tokens?\s*<=?\s*0",
            r"requests_per_",
            r"@ratelimit",
        ],
        "indicators": ["window", "tokens", "bucket"],
    },
    PatternType.VALIDATION: {
        "keywords": ["validate", "validator", "schema", "pydantic"],
        "regex": [
            r"class\s+\w+\(BaseModel\)",
            r"@validator",
            r"@field_validator",
            r"def\s+validate_\w+",
        ],
        "indicators": ["Field(", "Optional[", "Literal["],
    },
    PatternType.ERROR_HANDLING: {
        "keywords": ["error_handler", "exception", "try", "except"],
        "regex": [
            r"class\s+\w+Error\s*\(",
            r"class\s+\w+Exception\s*\(",
            r"@error_handler",
            r"raise\s+\w+Error",
        ],
        "indicators": ["traceback", "logging.error", "logger.error"],
    },
    PatternType.AUTH_PATTERN: {
        "keywords": ["auth", "authenticate", "authorization", "token", "jwt"],
        "regex": [
            r"def\s+authenticate",
            r"Bearer\s+",
            r"get_current_user",
            r"Depends\s*\(\s*\w*auth",
        ],
        "indicators": ["password", "credentials", "session"],
    },
    PatternType.API_CLIENT: {
        "keywords": ["client", "api_client", "http", "requests"],
        "regex": [
            r"class\s+\w+Client\s*[:\(]",
            r"requests\.(get|post|put|delete)",
            r"httpx\.",
            r"aiohttp\.",
        ],
        "indicators": ["base_url", "headers", "timeout"],
    },
}


@dataclass
class PatternMatch:
    """A pattern match found in the codebase.

    RLM-012: Records where implementation patterns are found.

    Attributes:
        pattern_type: Type of pattern matched
        file_path: File containing the pattern
        project: Project name
        line_number: Line where pattern starts
        match_preview: Code snippet showing the match
        confidence: Match confidence (0.0-1.0)
        indicators_found: Additional indicators present
    """
    pattern_type: PatternType
    file_path: str
    project: str
    line_number: int
    match_preview: str
    confidence: float
    indicators_found: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern_type": self.pattern_type.value,
            "file_path": self.file_path,
            "project": self.project,
            "line_number": self.line_number,
            "match_preview": self.match_preview,
            "confidence": self.confidence,
            "indicators_found": self.indicators_found,
        }


@dataclass
class CodeFile:
    """A code file in the index.

    Attributes:
        path: Absolute file path
        project: Project name
        language: Detected language
        size_bytes: File size
        lines: Line count (lazy loaded)
        modified: Last modification time
    """
    path: str
    project: str
    language: str
    size_bytes: int
    modified: str
    lines: int = 0
    content_preview: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "project": self.project,
            "language": self.language,
            "size_bytes": self.size_bytes,
            "modified": self.modified,
            "lines": self.lines,
            "content_preview": self.content_preview,
        }


# RLM-010: Constants for file content loading
DEFAULT_CHUNK_SIZE = 4000  # Characters per chunk (fits nicely in context)
MAX_FILE_SIZE = 1_000_000  # 1MB max for full content loading
PREVIEW_LINES = 50  # Lines for content preview


@dataclass
class FileChunk:
    """A chunk of file content for lazy loading.

    RLM-010: Supports chunking for large files.

    Attributes:
        file_path: Source file path
        chunk_index: Index of this chunk (0-based)
        total_chunks: Total chunks in file
        start_line: Starting line number (1-based)
        end_line: Ending line number (1-based)
        content: Chunk content
        char_offset: Character offset from file start
    """
    file_path: str
    chunk_index: int
    total_chunks: int
    start_line: int
    end_line: int
    content: str
    char_offset: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
            "char_offset": self.char_offset,
            "content_length": len(self.content),
        }


class RLMCodebaseEnvironment(RLMEnvironment):
    """
    RLM-009: Codebase environment for AI Exoskeleton projects.

    Indexes and provides search across all AI Exoskeleton code,
    enabling self-referential analysis and pattern detection.

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    def __init__(
        self,
        config: Optional[RLMConfig] = None,
        projects: Optional[Dict[str, str]] = None
    ):
        """
        Initialize codebase environment.

        Args:
            config: RLM configuration
            projects: Project name -> path mapping (defaults to AI_EXOSKELETON_PROJECTS)

        NASA Rule 10: 15 LOC (<=60)
        """
        super().__init__(config)

        self.projects = projects or AI_EXOSKELETON_PROJECTS
        self._index: Dict[str, CodeFile] = {}
        self._by_project: Dict[str, List[str]] = {}
        self._by_language: Dict[str, List[str]] = {}
        self._indexed = False

        logger.info(f"RLMCodebaseEnvironment initialized: {len(self.projects)} projects")

    def load_data(self, source: str = "all") -> bool:
        """
        Index project files.

        Args:
            source: Project name or "all"

        Returns:
            True if indexed successfully

        NASA Rule 10: 25 LOC (<=60)
        """
        try:
            if source == "all":
                for project_name, project_path in self.projects.items():
                    self._index_project(project_name, project_path)
            else:
                if source in self.projects:
                    self._index_project(source, self.projects[source])
                else:
                    logger.warning(f"Unknown project: {source}")
                    return False

            self._indexed = True
            logger.info(f"Indexed {len(self._index)} files across {len(self._by_project)} projects")
            return True

        except Exception as e:
            logger.error(f"Failed to index codebase: {e}")
            return False

    def _index_project(self, project_name: str, project_path: str) -> int:
        """
        Index a single project.

        Args:
            project_name: Project name
            project_path: Project root path

        Returns:
            Number of files indexed

        NASA Rule 10: 40 LOC (<=60)
        """
        count = 0
        path = Path(project_path)

        if not path.exists():
            logger.warning(f"Project path not found: {project_path}")
            return 0

        self._by_project[project_name] = []

        for root, dirs, files in os.walk(path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                filepath = Path(root) / filename
                language = self._detect_language(filename)

                if not language:
                    continue

                try:
                    stat = filepath.stat()
                    code_file = CodeFile(
                        path=str(filepath),
                        project=project_name,
                        language=language,
                        size_bytes=stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
                    )

                    file_key = str(filepath)
                    self._index[file_key] = code_file
                    self._by_project[project_name].append(file_key)

                    if language not in self._by_language:
                        self._by_language[language] = []
                    self._by_language[language].append(file_key)

                    count += 1

                except Exception as e:
                    logger.debug(f"Failed to index {filepath}: {e}")

        return count

    def _detect_language(self, filename: str) -> Optional[str]:
        """Detect language from filename extension."""
        ext = Path(filename).suffix.lower()
        for lang, extensions in LANGUAGE_EXTENSIONS.items():
            if ext in extensions:
                return lang
        return None

    def search(
        self,
        query: str,
        limit: int = 10,
        context: Optional[ExecutionContext] = None
    ) -> List[Dict[str, Any]]:
        """
        Search codebase for files matching query.

        Searches file paths, project names, and optionally content.

        Args:
            query: Search query
            limit: Maximum results
            context: Execution context

        Returns:
            List of matching files

        NASA Rule 10: 30 LOC (<=60)
        """
        results: List[CodeFile] = []
        query_lower = query.lower()

        for file_key, code_file in self._index.items():
            score = 0.0

            # Match on path
            if query_lower in file_key.lower():
                score = 0.9

            # Match on project
            elif query_lower in code_file.project.lower():
                score = 0.7

            # Match on language
            elif query_lower == code_file.language:
                score = 0.6

            if score > 0:
                results.append((score, code_file))

        # Sort by score
        results.sort(key=lambda x: x[0], reverse=True)
        self._query_count += 1

        return [f.to_dict() for _, f in results[:limit]]

    def get_chunk(
        self,
        chunk_id: str,
        context: Optional[ExecutionContext] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get file by path.

        Args:
            chunk_id: File path
            context: Execution context

        Returns:
            File info with content preview

        NASA Rule 10: 20 LOC (<=60)
        """
        if chunk_id not in self._index:
            return None

        code_file = self._index[chunk_id]

        # Load content preview
        try:
            with open(chunk_id, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                code_file.lines = len(lines)
                code_file.content_preview = "".join(lines[:50])
        except Exception as e:
            logger.debug(f"Failed to read file content: {e}")

        return code_file.to_dict()

    def search_content(
        self,
        pattern: str,
        language: Optional[str] = None,
        project: Optional[str] = None,
        limit: int = 20,
        use_regex: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search file contents for a pattern.

        Args:
            pattern: Text pattern to search (or regex if use_regex=True)
            language: Filter by language
            project: Filter by project
            limit: Maximum results
            use_regex: Treat pattern as regex

        Returns:
            List of files with matching content

        NASA Rule 10: 55 LOC (<=60)
        """
        import re
        results = []

        # Compile regex or prepare simple pattern
        if use_regex:
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                return []
        else:
            pattern_lower = pattern.lower()
            regex = None

        # Filter candidates
        candidates = list(self._index.keys())
        if language and language in self._by_language:
            candidates = self._by_language[language]
        if project and project in self._by_project:
            candidates = [c for c in candidates if c in self._by_project.get(project, [])]

        for file_key in candidates[:500]:  # Limit scan
            try:
                with open(file_key, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Match logic
                if regex:
                    match = regex.search(content)
                else:
                    match = pattern_lower in content.lower()

                if match:
                    code_file = self._index[file_key]
                    # Find matching line
                    for i, line in enumerate(content.split("\n")):
                        line_match = regex.search(line) if regex else pattern_lower in line.lower()
                        if line_match:
                            results.append({
                                **code_file.to_dict(),
                                "match_line": i + 1,
                                "match_preview": line.strip()[:200]
                            })
                            break

                    if len(results) >= limit:
                        break

            except Exception:
                continue

        return results

    def get_project_stats(self, project: str) -> Dict[str, Any]:
        """
        Get statistics for a project.

        NASA Rule 10: 20 LOC (<=60)
        """
        if project not in self._by_project:
            return {"error": f"Unknown project: {project}"}

        files = self._by_project[project]
        by_lang: Dict[str, int] = {}
        total_size = 0

        for file_key in files:
            code_file = self._index[file_key]
            by_lang[code_file.language] = by_lang.get(code_file.language, 0) + 1
            total_size += code_file.size_bytes

        return {
            "project": project,
            "file_count": len(files),
            "total_size_bytes": total_size,
            "by_language": by_lang,
            "path": self.projects.get(project)
        }

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all indexed projects with stats."""
        return [self.get_project_stats(p) for p in self._by_project.keys()]

    def get_stats(self) -> Dict[str, Any]:
        """Get environment statistics."""
        base_stats = super().get_stats()
        base_stats.update({
            "total_files": len(self._index),
            "total_projects": len(self._by_project),
            "by_language": {lang: len(files) for lang, files in self._by_language.items()},
            "indexed": self._indexed
        })
        return base_stats

    def export_index(self, output_path: str) -> int:
        """
        Export index to JSONL.

        Args:
            output_path: Output file path

        Returns:
            Number of records exported

        NASA Rule 10: 15 LOC (<=60)
        """
        count = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for file_key, code_file in self._index.items():
                f.write(json.dumps(code_file.to_dict()) + "\n")
                count += 1

        logger.info(f"Exported {count} files to {output_path}")
        return count

    # =========================================================================
    # RLM-010: Lazy File Content Loader with Chunking Support
    # =========================================================================

    def load_file_content(
        self,
        file_path: str,
        start_line: int = 1,
        end_line: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        RLM-010: Lazy load file content on demand.

        Loads specific line ranges from a file, enabling efficient
        retrieval of only needed content.

        Args:
            file_path: Path to file
            start_line: Starting line (1-based, default 1)
            end_line: Ending line (inclusive, None for all)

        Returns:
            Dict with content, line range, and metadata

        NASA Rule 10: 35 LOC (<=60)
        """
        if file_path not in self._index:
            logger.warning(f"File not in index: {file_path}")
            return None

        code_file = self._index[file_path]

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()

            total_lines = len(all_lines)

            # Normalize line numbers (1-based)
            start_idx = max(0, start_line - 1)
            end_idx = total_lines if end_line is None else min(end_line, total_lines)

            selected_lines = all_lines[start_idx:end_idx]
            content = "".join(selected_lines)

            return {
                **code_file.to_dict(),
                "content": content,
                "start_line": start_line,
                "end_line": end_idx,
                "total_lines": total_lines,
                "lines_returned": len(selected_lines),
                "content_length": len(content),
            }

        except Exception as e:
            logger.error(f"Failed to load file content: {e}")
            return None

    def get_file_chunks(
        self,
        file_path: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE
    ) -> List[Dict[str, Any]]:
        """
        RLM-010: Split file into chunks for large file processing.

        Splits file content into chunks by character count while
        respecting line boundaries for better context.

        Args:
            file_path: Path to file
            chunk_size: Target characters per chunk (default 4000)

        Returns:
            List of FileChunk dicts

        NASA Rule 10: 45 LOC (<=60)
        """
        if file_path not in self._index:
            logger.warning(f"File not in index: {file_path}")
            return []

        code_file = self._index[file_path]

        # Check file size
        if code_file.size_bytes > MAX_FILE_SIZE:
            logger.warning(f"File too large for chunking: {code_file.size_bytes} bytes")
            return []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()

            chunks: List[FileChunk] = []
            current_chunk_lines: List[str] = []
            current_chunk_chars = 0
            current_start_line = 1
            char_offset = 0

            for i, line in enumerate(all_lines, 1):
                line_len = len(line)

                # If adding this line exceeds chunk size, finalize current chunk
                if current_chunk_chars + line_len > chunk_size and current_chunk_lines:
                    chunk = FileChunk(
                        file_path=file_path,
                        chunk_index=len(chunks),
                        total_chunks=0,  # Set after loop
                        start_line=current_start_line,
                        end_line=i - 1,
                        content="".join(current_chunk_lines),
                        char_offset=char_offset - current_chunk_chars,
                    )
                    chunks.append(chunk)

                    current_chunk_lines = []
                    current_chunk_chars = 0
                    current_start_line = i

                current_chunk_lines.append(line)
                current_chunk_chars += line_len
                char_offset += line_len

            # Final chunk
            if current_chunk_lines:
                chunk = FileChunk(
                    file_path=file_path,
                    chunk_index=len(chunks),
                    total_chunks=0,
                    start_line=current_start_line,
                    end_line=len(all_lines),
                    content="".join(current_chunk_lines),
                    char_offset=char_offset - current_chunk_chars,
                )
                chunks.append(chunk)

            # Update total_chunks
            total = len(chunks)
            for chunk in chunks:
                chunk.total_chunks = total

            logger.debug(f"Split {file_path} into {total} chunks")
            return [c.to_dict() for c in chunks]

        except Exception as e:
            logger.error(f"Failed to chunk file: {e}")
            return []

    def get_chunk_by_index(
        self,
        file_path: str,
        chunk_index: int,
        chunk_size: int = DEFAULT_CHUNK_SIZE
    ) -> Optional[Dict[str, Any]]:
        """
        RLM-010: Get a specific chunk by index.

        Retrieves only the requested chunk without loading entire file,
        efficient for targeted content retrieval.

        Args:
            file_path: Path to file
            chunk_index: Chunk index (0-based)
            chunk_size: Target characters per chunk

        Returns:
            FileChunk dict or None if not found

        NASA Rule 10: 20 LOC (<=60)
        """
        chunks = self.get_file_chunks(file_path, chunk_size)

        if not chunks:
            return None

        if chunk_index < 0 or chunk_index >= len(chunks):
            logger.warning(f"Chunk index {chunk_index} out of range [0, {len(chunks)})")
            return None

        return chunks[chunk_index]

    def load_lines_around(
        self,
        file_path: str,
        target_line: int,
        context_lines: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        RLM-010: Load context around a specific line.

        Useful for examining code around a match or error location.

        Args:
            file_path: Path to file
            target_line: Line number to center on (1-based)
            context_lines: Lines before and after to include

        Returns:
            Dict with content centered on target line

        NASA Rule 10: 15 LOC (<=60)
        """
        start = max(1, target_line - context_lines)
        end = target_line + context_lines

        result = self.load_file_content(file_path, start, end)

        if result:
            result["target_line"] = target_line
            result["context_lines"] = context_lines

        return result

    # =========================================================================
    # RLM-012: Cross-Project Pattern Search
    # =========================================================================

    def search_patterns(
        self,
        pattern_type: PatternType,
        projects: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        RLM-012: Search for implementation patterns across projects.

        Finds reusable implementations of common patterns like retry logic,
        circuit breakers, caching, etc.

        Args:
            pattern_type: Type of pattern to search for
            projects: Limit to specific projects (None = all)
            languages: Limit to specific languages (None = all)
            limit: Maximum results

        Returns:
            List of PatternMatch dicts

        NASA Rule 10: 55 LOC (<=60)
        """
        import re

        if pattern_type not in PATTERN_SIGNATURES:
            logger.warning(f"Unknown pattern type: {pattern_type}")
            return []

        sig = PATTERN_SIGNATURES[pattern_type]
        keywords = sig.get("keywords", [])
        regexes = [re.compile(r, re.IGNORECASE) for r in sig.get("regex", [])]
        indicators = sig.get("indicators", [])

        matches: List[PatternMatch] = []

        # Filter candidates
        candidates = list(self._index.keys())
        if projects:
            candidates = [c for c in candidates if self._index[c].project in projects]
        if languages:
            candidates = [c for c in candidates if self._index[c].language in languages]

        for file_key in candidates[:500]:
            try:
                with open(file_key, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    lines = content.split("\n")

                content_lower = content.lower()

                # Check keywords first (fast)
                keyword_hits = [kw for kw in keywords if kw in content_lower]
                if not keyword_hits:
                    continue

                # Check regex patterns
                for i, line in enumerate(lines, 1):
                    for regex in regexes:
                        if regex.search(line):
                            # Found match - calculate confidence
                            indicator_hits = [ind for ind in indicators if ind in content_lower]
                            conf = min(0.5 + len(keyword_hits) * 0.1 + len(indicator_hits) * 0.1, 1.0)

                            match = PatternMatch(
                                pattern_type=pattern_type,
                                file_path=file_key,
                                project=self._index[file_key].project,
                                line_number=i,
                                match_preview=line.strip()[:200],
                                confidence=conf,
                                indicators_found=indicator_hits,
                            )
                            matches.append(match)
                            break  # One match per file per pattern
                    else:
                        continue
                    break

                if len(matches) >= limit:
                    break

            except Exception:
                continue

        # Sort by confidence
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return [m.to_dict() for m in matches[:limit]]

    def find_all_patterns(
        self,
        projects: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        limit_per_pattern: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        RLM-012: Find all pattern types across projects.

        Scans for all known patterns and returns a summary of
        reusable implementations organized by pattern type.

        Args:
            projects: Limit to specific projects (None = all)
            languages: Limit to specific languages (None = all)
            limit_per_pattern: Max matches per pattern type

        Returns:
            Dict mapping pattern type to list of matches

        NASA Rule 10: 20 LOC (<=60)
        """
        results: Dict[str, List[Dict[str, Any]]] = {}

        for pattern_type in PatternType:
            matches = self.search_patterns(
                pattern_type=pattern_type,
                projects=projects,
                languages=languages,
                limit=limit_per_pattern
            )
            if matches:
                results[pattern_type.value] = matches

        logger.info(f"Found {sum(len(v) for v in results.values())} pattern matches")
        return results

    def find_similar_implementations(
        self,
        file_path: str,
        context_lines: int = 30
    ) -> List[Dict[str, Any]]:
        """
        RLM-012: Find similar implementations to a given file.

        Analyzes patterns in the given file and finds other files
        that implement similar patterns.

        Args:
            file_path: Path to reference file
            context_lines: Lines to analyze from start

        Returns:
            List of similar files with shared patterns

        NASA Rule 10: 50 LOC (<=60)
        """
        if file_path not in self._index:
            return []

        # Load reference file content
        result = self.load_file_content(file_path, 1, context_lines)
        if not result:
            return []

        content = result.get("content", "").lower()

        # Detect patterns in reference file
        detected_patterns: List[PatternType] = []
        for pattern_type, sig in PATTERN_SIGNATURES.items():
            keywords = sig.get("keywords", [])
            if any(kw in content for kw in keywords):
                detected_patterns.append(pattern_type)

        if not detected_patterns:
            return []

        # Find files with same patterns
        similar: Dict[str, Dict[str, Any]] = {}
        ref_project = self._index[file_path].project

        for pattern_type in detected_patterns:
            matches = self.search_patterns(pattern_type, limit=20)
            for match in matches:
                match_path = match["file_path"]
                if match_path == file_path:
                    continue

                if match_path not in similar:
                    similar[match_path] = {
                        "file_path": match_path,
                        "project": match["project"],
                        "shared_patterns": [],
                        "same_project": match["project"] == ref_project,
                    }
                similar[match_path]["shared_patterns"].append(match["pattern_type"])

        # Sort by number of shared patterns
        results = list(similar.values())
        results.sort(key=lambda x: len(x["shared_patterns"]), reverse=True)

        return results[:20]

    def get_pattern_summary(self) -> Dict[str, Any]:
        """
        RLM-012: Get summary of patterns across all projects.

        Returns a high-level view of pattern distribution.

        Returns:
            Summary dict with pattern counts by project

        NASA Rule 10: 25 LOC (<=60)
        """
        summary: Dict[str, Dict[str, int]] = {}

        for project_name in self._by_project.keys():
            summary[project_name] = {}
            for pattern_type in PatternType:
                matches = self.search_patterns(
                    pattern_type=pattern_type,
                    projects=[project_name],
                    limit=100
                )
                if matches:
                    summary[project_name][pattern_type.value] = len(matches)

        return {
            "by_project": summary,
            "total_projects": len(summary),
            "patterns_analyzed": len(PatternType),
        }
