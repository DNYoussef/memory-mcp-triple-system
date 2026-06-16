"""
Property Inheritance Chain - Compute inherited values through parent chains.

Ported from Nexus-Properties with enhancements:
- Path-based exclusion rules (exclude different props for different paths)
- Inheritance chain tracking (know which parent a value came from)
- Circular inheritance detection (prevent infinite loops)
- Priority resolution (handle conflicts from multiple parents)

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Callable, Tuple
from loguru import logger


@dataclass
class InheritedValue:
    """A value and its inheritance source."""

    value: Any
    source_path: str  # File path where value originates
    inheritance_chain: List[str] = field(
        default_factory=list
    )  # Path from source to current
    is_overridden: bool = False  # True if local value exists


@dataclass
class PathExclusion:
    """Exclude certain properties for files matching a path pattern."""

    path_pattern: str  # e.g., "Projects/*" or "Archive/**"
    excluded_props: Set[str]
    enabled: bool = True


@dataclass
class InheritanceConfig:
    """Configuration for property inheritance system."""

    # Properties that should never inherit
    globally_excluded: Set[str] = field(
        default_factory=lambda: {
            "parents",
            "children",
            "related",
            "aliases",
            "tags",
            "id",
        }
    )

    # Path-based exclusions
    path_exclusions: List[PathExclusion] = field(default_factory=list)

    # Property used to specify which parent takes priority
    prioritize_parent_prop: str = "prioritize_parent"

    # Maximum inheritance depth (prevent deep chains)
    max_depth: int = 50


class PropertyInheritanceChain:
    """
    Compute inherited values through parent-child relationships.

    Tracks inheritance chains and resolves effective values considering:
    - Local overrides (child values take precedence)
    - Multiple parents (uses prioritize_parent or first parent)
    - Path-based exclusions (different rules for different folders)
    - Circular reference detection

    Usage:
        from src.integrations.frontmatter_mapper import FrontmatterMapper

        chain = PropertyInheritanceChain()

        # Compute effective frontmatter for a file
        effective = chain.compute_effective_frontmatter(
            file_path="Projects/TaskA.md",
            local_frontmatter={"title": "Task A"},
            get_frontmatter=lambda path: vault.read_frontmatter(path)
        )

        # Get inheritance info for a specific property
        inherited = chain.get_inherited_value(
            file_path="Projects/TaskA.md",
            prop_name="project",
            get_frontmatter=lambda path: vault.read_frontmatter(path)
        )
    """

    def __init__(self, config: Optional[InheritanceConfig] = None):
        """Initialize property inheritance chain."""
        self.config = config or InheritanceConfig()
        logger.debug("PropertyInheritanceChain initialized")

    def compute_effective_frontmatter(
        self,
        file_path: str,
        local_frontmatter: Dict[str, Any],
        get_frontmatter: Callable[[str], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compute effective frontmatter including inherited values.

        Args:
            file_path: Path to the file
            local_frontmatter: File's own frontmatter
            get_frontmatter: Function to get frontmatter for a path

        Returns:
            Effective frontmatter with inherited values filled in
        """
        effective = dict(local_frontmatter)
        visited = {file_path}

        # Get parent chain
        parents = self._get_parent_chain(
            file_path, local_frontmatter, get_frontmatter, visited
        )

        # Process parents from furthest ancestor to nearest
        for parent_path, parent_fm in reversed(parents):
            self._apply_inherited_props(effective, parent_fm, file_path, parent_path)

        return effective

    def get_inherited_value(
        self,
        file_path: str,
        prop_name: str,
        get_frontmatter: Callable[[str], Dict[str, Any]],
    ) -> Optional[InheritedValue]:
        """
        Get inheritance info for a specific property.

        Args:
            file_path: Path to the file
            prop_name: Property to trace
            get_frontmatter: Function to get frontmatter for a path

        Returns:
            InheritedValue with source and chain, or None if not inherited
        """
        local_fm = get_frontmatter(file_path)

        # Check if local value exists
        if prop_name in local_fm:
            return InheritedValue(
                value=local_fm[prop_name],
                source_path=file_path,
                inheritance_chain=[file_path],
                is_overridden=False,
            )

        # Check if excluded for this path
        if self._is_excluded(file_path, prop_name):
            return None

        # Trace through parents
        visited = {file_path}
        chain = [file_path]

        return self._trace_inherited_value(
            file_path, prop_name, get_frontmatter, visited, chain
        )

    def get_inheritance_tree(
        self, file_path: str, get_frontmatter: Callable[[str], Dict[str, Any]]
    ) -> Dict[str, InheritedValue]:
        """
        Get inheritance info for all properties.

        Returns:
            Dict mapping property name to InheritedValue
        """
        result = {}
        local_fm = get_frontmatter(file_path)
        effective = self.compute_effective_frontmatter(
            file_path, local_fm, get_frontmatter
        )

        for prop_name, value in effective.items():
            inherited = self.get_inherited_value(file_path, prop_name, get_frontmatter)
            if inherited:
                result[prop_name] = inherited

        return result

    def detect_circular_inheritance(
        self, file_path: str, get_frontmatter: Callable[[str], Dict[str, Any]]
    ) -> Optional[List[str]]:
        """
        Detect circular parent references.

        Returns:
            List of paths in the cycle, or None if no cycle
        """
        visited = []
        current = file_path

        while current:
            if current in visited:
                cycle_start = visited.index(current)
                return visited[cycle_start:] + [current]

            visited.append(current)
            fm = get_frontmatter(current)
            parents = self._extract_parents(fm)

            if not parents:
                return None

            # Follow prioritized parent or first parent
            current = self._get_priority_parent(fm, parents)
            if current and current in visited:
                cycle_start = visited.index(current)
                return visited[cycle_start:] + [current]

        return None

    def add_path_exclusion(self, path_pattern: str, props: Set[str]) -> None:
        """Add path-based exclusion rule."""
        self.config.path_exclusions.append(PathExclusion(path_pattern, props, True))
        logger.debug(f"Added path exclusion: {path_pattern} -> {props}")

    def _get_parent_chain(
        self,
        file_path: str,
        frontmatter: Dict[str, Any],
        get_frontmatter: Callable[[str], Dict[str, Any]],
        visited: Set[str],
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Get ordered list of (parent_path, parent_frontmatter) pairs."""
        parents = self._extract_parents(frontmatter)
        if not parents:
            return []

        # Get priority parent
        priority = self._get_priority_parent(frontmatter, parents)
        if priority and priority in parents:
            parents.remove(priority)
            parents.insert(0, priority)

        chain = []
        for parent_path in parents:
            if parent_path in visited:
                continue  # Skip circular references
            if len(chain) >= self.config.max_depth:
                logger.warning(f"Max inheritance depth reached for {file_path}")
                break

            visited.add(parent_path)
            parent_fm = get_frontmatter(parent_path)
            chain.append((parent_path, parent_fm))

            # Recursively get parent's parents
            parent_chain = self._get_parent_chain(
                parent_path, parent_fm, get_frontmatter, visited
            )
            chain.extend(parent_chain)

        return chain

    def _apply_inherited_props(
        self,
        target: Dict[str, Any],
        source: Dict[str, Any],
        target_path: str,
        source_path: str,
    ) -> None:
        """Apply inherited properties from source to target (if not present)."""
        for prop_name, value in source.items():
            # Skip if already set (local override)
            if prop_name in target:
                continue

            # Skip excluded properties
            if self._is_excluded(target_path, prop_name):
                continue

            target[prop_name] = value

    def _trace_inherited_value(
        self,
        file_path: str,
        prop_name: str,
        get_frontmatter: Callable[[str], Dict[str, Any]],
        visited: Set[str],
        chain: List[str],
    ) -> Optional[InheritedValue]:
        """Trace inheritance chain to find property source."""
        frontmatter = get_frontmatter(file_path)
        parents = self._extract_parents(frontmatter)

        if not parents:
            return None

        # Get priority parent
        priority = self._get_priority_parent(frontmatter, parents)
        if priority and priority in parents:
            parents.remove(priority)
            parents.insert(0, priority)

        for parent_path in parents:
            if parent_path in visited:
                continue
            if len(chain) >= self.config.max_depth:
                return None

            visited.add(parent_path)
            parent_fm = get_frontmatter(parent_path)

            if prop_name in parent_fm:
                return InheritedValue(
                    value=parent_fm[prop_name],
                    source_path=parent_path,
                    inheritance_chain=chain + [parent_path],
                    is_overridden=False,
                )

            # Recurse
            result = self._trace_inherited_value(
                parent_path, prop_name, get_frontmatter, visited, chain + [parent_path]
            )
            if result:
                return result

        return None

    def _extract_parents(self, frontmatter: Dict[str, Any]) -> List[str]:
        """Extract parent paths from frontmatter."""
        parents = frontmatter.get("parents", [])
        if isinstance(parents, str):
            parents = [parents] if parents else []

        # Extract link names
        result = []
        for p in parents:
            if isinstance(p, str):
                # Handle [[Link]] format
                if p.startswith("[[") and p.endswith("]]"):
                    p = p[2:-2].split("|")[0]
                result.append(p)

        return result

    def _get_priority_parent(
        self, frontmatter: Dict[str, Any], parents: List[str]
    ) -> Optional[str]:
        """Get the prioritized parent from frontmatter."""
        priority = frontmatter.get(self.config.prioritize_parent_prop)
        if not priority:
            return parents[0] if parents else None

        # Handle [[Link]] format
        if isinstance(priority, str):
            if priority.startswith("[[") and priority.endswith("]]"):
                priority = priority[2:-2].split("|")[0]
            if priority in parents:
                return priority

        return parents[0] if parents else None

    def _is_excluded(self, file_path: str, prop_name: str) -> bool:
        """Check if property is excluded for this path."""
        # Global exclusions
        if prop_name in self.config.globally_excluded:
            return True

        # Path-based exclusions
        for exclusion in self.config.path_exclusions:
            if not exclusion.enabled:
                continue
            if self._path_matches(file_path, exclusion.path_pattern):
                if prop_name in exclusion.excluded_props:
                    return True

        return False

    def _path_matches(self, file_path: str, pattern: str) -> bool:
        """Check if file path matches pattern (glob-like)."""
        path = Path(file_path)
        pattern_path = Path(pattern)

        # Simple prefix matching for now
        # e.g., "Projects/*" matches "Projects/TaskA.md"
        pattern_str = str(pattern_path).replace("*", "").replace("**", "")
        return str(path).startswith(pattern_str)
