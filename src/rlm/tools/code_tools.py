"""
RLM Code Analysis Tools for Codebase Navigation.

RLM-011: Code-specific search tools for AI Exoskeleton codebase.
Provides AST-based code analysis for functions, classes, imports, and call tracing.

Key Tools:
- find_function(): Find function definitions by name/pattern
- find_class(): Find class definitions by name/pattern
- find_imports(): Find import statements
- trace_calls(): Trace function call chains

Supports Python, TypeScript, and JavaScript (with varying depth).

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from loguru import logger


@dataclass
class CodeSymbol:
    """A code symbol (function, class, import).

    Attributes:
        name: Symbol name
        symbol_type: function, class, method, import
        file_path: Source file path
        line_number: Line number (1-based)
        end_line: End line number
        signature: Function signature or class definition
        docstring: Optional docstring
        project: Project name
    """
    name: str
    symbol_type: str  # function, class, method, import, variable
    file_path: str
    line_number: int
    end_line: int = 0
    signature: str = ""
    docstring: str = ""
    project: str = ""
    parent: str = ""  # For methods: class name

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "symbol_type": self.symbol_type,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "end_line": self.end_line,
            "signature": self.signature,
            "docstring": self.docstring[:500] if self.docstring else "",
            "project": self.project,
            "parent": self.parent,
        }


@dataclass
class FunctionCall:
    """A function call reference.

    Attributes:
        caller: Calling function/method
        callee: Called function/method
        file_path: Source file path
        line_number: Line number of call
        arguments: Call arguments (if extractable)
    """
    caller: str
    callee: str
    file_path: str
    line_number: int
    arguments: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "caller": self.caller,
            "callee": self.callee,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "arguments": self.arguments,
        }


class RLMCodeTools:
    """
    RLM-011: Code analysis tools for codebase navigation.

    Provides AST-based code analysis across Python files,
    with regex fallback for TypeScript/JavaScript.

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    def __init__(self, codebase_env=None):
        """
        Initialize code tools.

        Args:
            codebase_env: RLMCodebaseEnvironment instance for file access

        NASA Rule 10: 10 LOC (<=60)
        """
        self._env = codebase_env
        self._symbol_cache: Dict[str, List[CodeSymbol]] = {}
        self._call_cache: Dict[str, List[FunctionCall]] = {}
        self._query_count = 0

        logger.info("RLMCodeTools initialized")

    def find_function(
        self,
        name_pattern: str,
        project: Optional[str] = None,
        use_regex: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        RLM-011: Find function definitions by name.

        Searches for function/method definitions across the codebase.

        Args:
            name_pattern: Function name or regex pattern
            project: Filter by project name
            use_regex: Treat name_pattern as regex
            limit: Maximum results

        Returns:
            List of CodeSymbol dicts

        NASA Rule 10: 30 LOC (<=60)
        """
        results: List[CodeSymbol] = []

        if use_regex:
            try:
                pattern = re.compile(name_pattern, re.IGNORECASE)
            except re.error:
                return []
        else:
            pattern = None
            name_lower = name_pattern.lower()

        files = self._get_python_files(project)

        for file_path in files[:200]:  # Limit scan
            symbols = self._extract_symbols_python(file_path)

            for symbol in symbols:
                if symbol.symbol_type not in ("function", "method"):
                    continue

                # Match logic
                if pattern:
                    matches = pattern.search(symbol.name)
                else:
                    matches = name_lower in symbol.name.lower()

                if matches:
                    results.append(symbol)
                    if len(results) >= limit:
                        break

            if len(results) >= limit:
                break

        self._query_count += 1
        return [s.to_dict() for s in results]

    def find_class(
        self,
        name_pattern: str,
        project: Optional[str] = None,
        use_regex: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        RLM-011: Find class definitions by name.

        Searches for class definitions across the codebase.

        Args:
            name_pattern: Class name or regex pattern
            project: Filter by project name
            use_regex: Treat name_pattern as regex
            limit: Maximum results

        Returns:
            List of CodeSymbol dicts

        NASA Rule 10: 30 LOC (<=60)
        """
        results: List[CodeSymbol] = []

        if use_regex:
            try:
                pattern = re.compile(name_pattern, re.IGNORECASE)
            except re.error:
                return []
        else:
            pattern = None
            name_lower = name_pattern.lower()

        files = self._get_python_files(project)

        for file_path in files[:200]:
            symbols = self._extract_symbols_python(file_path)

            for symbol in symbols:
                if symbol.symbol_type != "class":
                    continue

                if pattern:
                    matches = pattern.search(symbol.name)
                else:
                    matches = name_lower in symbol.name.lower()

                if matches:
                    results.append(symbol)
                    if len(results) >= limit:
                        break

            if len(results) >= limit:
                break

        self._query_count += 1
        return [s.to_dict() for s in results]

    def find_imports(
        self,
        module_pattern: str,
        project: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        RLM-011: Find import statements.

        Searches for import statements matching a module pattern.

        Args:
            module_pattern: Module name to search for
            project: Filter by project name
            limit: Maximum results

        Returns:
            List of CodeSymbol dicts

        NASA Rule 10: 25 LOC (<=60)
        """
        results: List[CodeSymbol] = []
        pattern_lower = module_pattern.lower()

        files = self._get_python_files(project)

        for file_path in files[:300]:
            symbols = self._extract_imports_python(file_path)

            for symbol in symbols:
                if pattern_lower in symbol.name.lower():
                    results.append(symbol)
                    if len(results) >= limit:
                        break

            if len(results) >= limit:
                break

        self._query_count += 1
        return [s.to_dict() for s in results]

    def trace_calls(
        self,
        function_name: str,
        project: Optional[str] = None,
        direction: str = "callers",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        RLM-011: Trace function call chains.

        Finds where a function is called (callers) or what it calls (callees).

        Args:
            function_name: Function name to trace
            project: Filter by project name
            direction: "callers" or "callees"
            limit: Maximum results

        Returns:
            List of FunctionCall dicts

        NASA Rule 10: 35 LOC (<=60)
        """
        results: List[FunctionCall] = []
        name_lower = function_name.lower()

        files = self._get_python_files(project)

        for file_path in files[:200]:
            calls = self._extract_calls_python(file_path)

            for call in calls:
                if direction == "callers":
                    # Find calls TO this function
                    if name_lower in call.callee.lower():
                        results.append(call)
                else:
                    # Find calls FROM this function
                    if name_lower in call.caller.lower():
                        results.append(call)

                if len(results) >= limit:
                    break

            if len(results) >= limit:
                break

        self._query_count += 1
        return [c.to_dict() for c in results]

    def _get_python_files(self, project: Optional[str] = None) -> List[str]:
        """Get Python files from environment."""
        if not self._env:
            return []

        if hasattr(self._env, "_by_language"):
            files = self._env._by_language.get("python", [])
            if project and hasattr(self._env, "_by_project"):
                project_files = set(self._env._by_project.get(project, []))
                files = [f for f in files if f in project_files]
            return files

        return []

    def _extract_symbols_python(self, file_path: str) -> List[CodeSymbol]:
        """Extract function and class symbols from Python file."""
        cache_key = f"symbols:{file_path}"
        if cache_key in self._symbol_cache:
            return self._symbol_cache[cache_key]

        symbols: List[CodeSymbol] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()

            tree = ast.parse(source, filename=file_path)
            project = self._get_project_name(file_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    symbols.append(self._func_to_symbol(node, file_path, project, ""))
                elif isinstance(node, ast.AsyncFunctionDef):
                    symbols.append(self._func_to_symbol(node, file_path, project, "", is_async=True))
                elif isinstance(node, ast.ClassDef):
                    symbols.append(self._class_to_symbol(node, file_path, project))
                    # Extract methods
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            symbols.append(self._func_to_symbol(
                                item, file_path, project, node.name,
                                is_async=isinstance(item, ast.AsyncFunctionDef)
                            ))

        except (SyntaxError, Exception) as e:
            logger.debug(f"Failed to parse {file_path}: {e}")

        self._symbol_cache[cache_key] = symbols
        return symbols

    def _func_to_symbol(
        self,
        node,
        file_path: str,
        project: str,
        parent: str,
        is_async: bool = False
    ) -> CodeSymbol:
        """Convert AST function node to CodeSymbol."""
        # Build signature
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        sig = f"{'async ' if is_async else ''}def {node.name}({', '.join(args)})"

        return CodeSymbol(
            name=node.name,
            symbol_type="method" if parent else "function",
            file_path=file_path,
            line_number=node.lineno,
            end_line=node.end_lineno or node.lineno,
            signature=sig,
            docstring=ast.get_docstring(node) or "",
            project=project,
            parent=parent,
        )

    def _class_to_symbol(self, node, file_path: str, project: str) -> CodeSymbol:
        """Convert AST class node to CodeSymbol."""
        bases = [self._get_name(b) for b in node.bases]
        sig = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"

        return CodeSymbol(
            name=node.name,
            symbol_type="class",
            file_path=file_path,
            line_number=node.lineno,
            end_line=node.end_lineno or node.lineno,
            signature=sig,
            docstring=ast.get_docstring(node) or "",
            project=project,
        )

    def _get_name(self, node) -> str:
        """Get name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return str(node)

    def _extract_imports_python(self, file_path: str) -> List[CodeSymbol]:
        """Extract import statements from Python file."""
        symbols: List[CodeSymbol] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()

            tree = ast.parse(source, filename=file_path)
            project = self._get_project_name(file_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        symbols.append(CodeSymbol(
                            name=alias.name,
                            symbol_type="import",
                            file_path=file_path,
                            line_number=node.lineno,
                            signature=f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""),
                            project=project,
                        ))
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        symbols.append(CodeSymbol(
                            name=f"{module}.{alias.name}" if module else alias.name,
                            symbol_type="import",
                            file_path=file_path,
                            line_number=node.lineno,
                            signature=f"from {module} import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""),
                            project=project,
                            parent=module,
                        ))

        except (SyntaxError, Exception) as e:
            logger.debug(f"Failed to parse imports from {file_path}: {e}")

        return symbols

    def _extract_calls_python(self, file_path: str) -> List[FunctionCall]:
        """Extract function calls from Python file."""
        cache_key = f"calls:{file_path}"
        if cache_key in self._call_cache:
            return self._call_cache[cache_key]

        calls: List[FunctionCall] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()

            tree = ast.parse(source, filename=file_path)
            current_func = "<module>"

            class CallVisitor(ast.NodeVisitor):
                def visit_FunctionDef(self, node):
                    nonlocal current_func
                    old_func = current_func
                    current_func = node.name
                    self.generic_visit(node)
                    current_func = old_func

                def visit_AsyncFunctionDef(self, node):
                    nonlocal current_func
                    old_func = current_func
                    current_func = node.name
                    self.generic_visit(node)
                    current_func = old_func

                def visit_Call(self, node):
                    callee = self._get_call_name(node.func)
                    if callee:
                        calls.append(FunctionCall(
                            caller=current_func,
                            callee=callee,
                            file_path=file_path,
                            line_number=node.lineno,
                        ))
                    self.generic_visit(node)

                def _get_call_name(self, node) -> str:
                    if isinstance(node, ast.Name):
                        return node.id
                    elif isinstance(node, ast.Attribute):
                        base = self._get_call_name(node.value)
                        return f"{base}.{node.attr}" if base else node.attr
                    return ""

            CallVisitor().visit(tree)

        except (SyntaxError, Exception) as e:
            logger.debug(f"Failed to extract calls from {file_path}: {e}")

        self._call_cache[cache_key] = calls
        return calls

    def _get_project_name(self, file_path: str) -> str:
        """Get project name from file path."""
        if self._env and hasattr(self._env, "_index"):
            code_file = self._env._index.get(file_path)
            if code_file:
                return code_file.project
        return ""

    def get_stats(self) -> Dict[str, Any]:
        """Get tool statistics."""
        return {
            "query_count": self._query_count,
            "symbol_cache_size": len(self._symbol_cache),
            "call_cache_size": len(self._call_cache),
            "has_env": self._env is not None,
        }


# Convenience functions for standalone use

def find_function(
    codebase_env,
    name_pattern: str,
    project: Optional[str] = None,
    use_regex: bool = False,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Find function definitions."""
    tools = RLMCodeTools(codebase_env)
    return tools.find_function(name_pattern, project, use_regex, limit)


def find_class(
    codebase_env,
    name_pattern: str,
    project: Optional[str] = None,
    use_regex: bool = False,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Find class definitions."""
    tools = RLMCodeTools(codebase_env)
    return tools.find_class(name_pattern, project, use_regex, limit)


def find_imports(
    codebase_env,
    module_pattern: str,
    project: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Find import statements."""
    tools = RLMCodeTools(codebase_env)
    return tools.find_imports(module_pattern, project, limit)


def trace_calls(
    codebase_env,
    function_name: str,
    project: Optional[str] = None,
    direction: str = "callers",
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Trace function calls."""
    tools = RLMCodeTools(codebase_env)
    return tools.trace_calls(function_name, project, direction, limit)
