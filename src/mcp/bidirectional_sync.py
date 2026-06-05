"""
Bidirectional Sync Engine - Memory MCP <-> Obsidian Vault.

Ported from Nexus-Properties properties-manager.ts with Memory MCP adaptations:
- Watches for changes in both Memory MCP and Obsidian vault
- Propagates relationship changes bidirectionally
- Syncs WHO/WHEN/PROJECT/WHY metadata to Obsidian frontmatter
- Supports property inheritance cascade

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Callable
from datetime import datetime
import yaml
import re
from loguru import logger

from .vault_file_manager import VaultFileManager


@dataclass
class FrontmatterChange:
    """Represents a change to frontmatter property."""
    key: str
    old_value: Any = None
    new_value: Any = None
    change_type: str = "modified"  # added, modified, deleted


@dataclass
class FrontmatterDiff:
    """Collection of frontmatter changes."""
    added: List[FrontmatterChange] = field(default_factory=list)
    modified: List[FrontmatterChange] = field(default_factory=list)
    deleted: List[FrontmatterChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return len(self.added) + len(self.modified) + len(self.deleted) > 0

    @property
    def all_changes(self) -> List[FrontmatterChange]:
        return self.added + self.modified + self.deleted


@dataclass
class RelationshipConfig:
    """Configuration for a relationship type."""
    prop_name: str  # e.g., "parents"
    reverse_prop_name: str  # e.g., "children"
    edge_type: str  # Memory MCP edge type


# Default relationship configurations (matching Nexus-Properties)
RELATIONSHIP_CONFIGS = [
    RelationshipConfig("parents", "children", "REFERENCES"),
    RelationshipConfig("children", "parents", "RELATED_TO"),
    RelationshipConfig("related", "related", "MENTIONS"),
]

# Properties to exclude from propagation
EXCLUDED_PROPS = {"parents", "children", "related", "aliases", "tags"}


class BidirectionalSyncEngine:
    """
    Bidirectional sync between Memory MCP and Obsidian vault.

    Ported from Nexus-Properties properties-manager.ts with adaptations
    for Memory MCP's triple-layer storage and graph system.

    Features:
    - Watch for Memory MCP changes and update Obsidian frontmatter
    - Watch for Obsidian changes and update Memory MCP
    - Propagate property changes to related notes
    - Sync WHO/WHEN/PROJECT/WHY metadata

    Usage:
        from src.services.graph_service import GraphService
        from src.mcp.vault_file_manager import VaultFileManager

        graph = GraphService()
        file_manager = VaultFileManager("/path/to/vault")
        engine = BidirectionalSyncEngine(graph, file_manager)

        await engine.start()
    """

    def __init__(
        self,
        graph_service: Any,
        file_manager: VaultFileManager,
        propagate_to_children: bool = True,
        debounce_ms: int = 1000,
        excluded_props: Optional[Set[str]] = None
    ):
        """
        Initialize bidirectional sync engine.

        Args:
            graph_service: GraphService instance for Memory MCP
            file_manager: VaultFileManager for Obsidian vault
            propagate_to_children: Whether to cascade changes to children
            debounce_ms: Debounce delay for propagation
            excluded_props: Properties to exclude from propagation
        """
        self.graph = graph_service
        self.file_manager = file_manager
        self.propagate_to_children = propagate_to_children
        self.debounce_ms = debounce_ms
        self.excluded_props = excluded_props or EXCLUDED_PROPS

        # State tracking
        self._running = False
        self._files_being_propagated: Set[str] = set()
        self._debounce_timers: Dict[str, asyncio.Task] = {}
        self._accumulated_diffs: Dict[str, List[FrontmatterDiff]] = {}

        # Callbacks for external notification
        self._change_callbacks: List[Callable] = []

        logger.info("BidirectionalSyncEngine initialized")

    async def start(self) -> None:
        """Start bidirectional sync watching."""
        self._running = True
        logger.info("BidirectionalSyncEngine started")

    async def stop(self) -> None:
        """Stop bidirectional sync and cleanup."""
        self._running = False

        # Cancel pending debounce timers
        for task in self._debounce_timers.values():
            task.cancel()
        self._debounce_timers.clear()
        self._accumulated_diffs.clear()
        self._files_being_propagated.clear()

        logger.info("BidirectionalSyncEngine stopped")

    def add_change_callback(self, callback: Callable) -> None:
        """Add callback for change notifications."""
        self._change_callbacks.append(callback)

    async def handle_memory_change(
        self,
        chunk_id: str,
        old_metadata: Dict[str, Any],
        new_metadata: Dict[str, Any]
    ) -> None:
        """
        Handle Memory MCP chunk metadata change -> sync to Obsidian.

        Args:
            chunk_id: Memory MCP chunk ID
            old_metadata: Previous metadata
            new_metadata: New metadata
        """
        if not self._running:
            return

        diff = self._compute_frontmatter_diff(old_metadata, new_metadata)
        if not diff.has_changes:
            return

        # Find corresponding Obsidian file
        file_path = self._resolve_obsidian_file(chunk_id, new_metadata)
        if not file_path:
            logger.debug(f"No Obsidian file found for chunk {chunk_id}")
            return

        await self._sync_to_obsidian(file_path, diff, new_metadata)

    async def handle_obsidian_change(
        self,
        file_path: str,
        old_frontmatter: Dict[str, Any],
        new_frontmatter: Dict[str, Any]
    ) -> None:
        """
        Handle Obsidian file change -> sync to Memory MCP.

        Args:
            file_path: Obsidian file path
            old_frontmatter: Previous frontmatter
            new_frontmatter: New frontmatter
        """
        if not self._running:
            return

        if file_path in self._files_being_propagated:
            return  # Skip files we're currently propagating to

        diff = self._compute_frontmatter_diff(old_frontmatter, new_frontmatter)
        if not diff.has_changes:
            return

        # Handle relationship changes
        await self._handle_relationship_changes(file_path, old_frontmatter, new_frontmatter)

        # Schedule propagation with debounce
        if self.propagate_to_children:
            await self._schedule_propagation(file_path, new_frontmatter, diff)

        # Notify callbacks
        for callback in self._change_callbacks:
            try:
                await callback(file_path, diff) if asyncio.iscoroutinefunction(callback) else callback(file_path, diff)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def _handle_relationship_changes(
        self,
        file_path: str,
        old_fm: Dict[str, Any],
        new_fm: Dict[str, Any]
    ) -> None:
        """
        Update reverse relationships when relationships change.

        Ported from properties-manager.ts handleFileModification().
        """
        base_name = Path(file_path).stem

        for config in RELATIONSHIP_CONFIGS:
            old_links = self._parse_links(old_fm.get(config.prop_name, []))
            new_links = self._parse_links(new_fm.get(config.prop_name, []))

            added = set(new_links) - set(old_links)
            removed = set(old_links) - set(new_links)

            # Add reverse links to newly added relationships
            for target_name in added:
                target_path = self._resolve_file_from_name(target_name)
                if target_path:
                    await self._add_to_property(target_path, config.reverse_prop_name, base_name)
                    logger.debug(f"Added reverse link: {target_path} -> {base_name}")

            # Remove reverse links from removed relationships
            for target_name in removed:
                target_path = self._resolve_file_from_name(target_name)
                if target_path:
                    await self._remove_from_property(target_path, config.reverse_prop_name, base_name)
                    logger.debug(f"Removed reverse link: {target_path} -> {base_name}")

    async def _schedule_propagation(
        self,
        file_path: str,
        frontmatter: Dict[str, Any],
        diff: FrontmatterDiff
    ) -> None:
        """Schedule frontmatter propagation with debounce."""
        # Cancel existing timer
        if file_path in self._debounce_timers:
            self._debounce_timers[file_path].cancel()

        # Accumulate diffs
        if file_path not in self._accumulated_diffs:
            self._accumulated_diffs[file_path] = []
        self._accumulated_diffs[file_path].append(diff)

        # Create debounced task
        async def propagate_after_delay():
            await asyncio.sleep(self.debounce_ms / 1000)
            del self._debounce_timers[file_path]
            diffs = self._accumulated_diffs.pop(file_path, [])
            merged_diff = self._merge_diffs(diffs)
            await self._propagate_to_children(file_path, frontmatter, merged_diff)

        task = asyncio.create_task(propagate_after_delay())
        self._debounce_timers[file_path] = task

    async def _propagate_to_children(
        self,
        parent_path: str,
        parent_frontmatter: Dict[str, Any],
        diff: FrontmatterDiff
    ) -> None:
        """
        Propagate frontmatter changes to children.

        Ported from properties-manager.ts propagateFrontmatterToChildren().
        """
        children = self._get_children_recursive(parent_path, parent_frontmatter)
        if not children:
            return

        # Filter to non-excluded properties
        filtered = self._filter_excluded_changes(diff)
        if not filtered.has_changes:
            return

        # Mark files as being propagated
        for child in children:
            self._files_being_propagated.add(child)

        try:
            for child_path in children:
                await self._apply_frontmatter_changes(child_path, filtered)
                logger.debug(f"Propagated changes to {child_path}")

        finally:
            for child in children:
                self._files_being_propagated.discard(child)

    async def _sync_to_obsidian(
        self,
        file_path: str,
        diff: FrontmatterDiff,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Sync Memory MCP metadata changes to Obsidian frontmatter.
        """
        try:
            full_path = self.file_manager.vault_path / file_path
            if not full_path.exists():
                logger.warning(f"Cannot sync to non-existent file: {file_path}")
                return

            content = self.file_manager.read_file(full_path)
            if not content:
                return

            # Parse existing frontmatter
            existing_fm = self._parse_frontmatter(content)

            # Apply changes
            for change in diff.added + diff.modified:
                existing_fm[change.key] = change.new_value

            for change in diff.deleted:
                existing_fm.pop(change.key, None)

            # Add WHO/WHEN/PROJECT/WHY if present
            self._sync_tagging_protocol(existing_fm, metadata)

            # Write back
            new_content = self._update_frontmatter(content, existing_fm)
            self.file_manager.write_file(full_path, new_content)

            logger.info(f"Synced {len(diff.all_changes)} changes to {file_path}")

        except Exception as e:
            logger.error(f"Failed to sync to Obsidian: {e}")

    def _sync_tagging_protocol(self, frontmatter: Dict, metadata: Dict) -> None:
        """Sync WHO/WHEN/PROJECT/WHY from Memory MCP to frontmatter."""
        if "WHO" in metadata:
            who = metadata["WHO"]
            if isinstance(who, dict):
                frontmatter["who"] = who.get("name", str(who))
            else:
                frontmatter["who"] = str(who)

        if "WHEN" in metadata:
            when = metadata["WHEN"]
            if isinstance(when, dict):
                frontmatter["updated"] = when.get("iso", when.get("readable", str(when)))
            else:
                frontmatter["updated"] = str(when)

        if "PROJECT" in metadata:
            frontmatter["project"] = metadata["PROJECT"]

        if "WHY" in metadata:
            frontmatter["why"] = metadata["WHY"]

    async def _add_to_property(
        self,
        file_path: str,
        prop_name: str,
        value_to_add: str
    ) -> None:
        """Add a link to a frontmatter property list."""
        try:
            full_path = self.file_manager.vault_path / file_path
            if not full_path.exists():
                return

            content = self.file_manager.read_file(full_path)
            if not content:
                return

            frontmatter = self._parse_frontmatter(content)
            current = frontmatter.get(prop_name, [])
            if isinstance(current, str):
                current = [current] if current else []

            link = f"[[{value_to_add}]]"
            if link not in current and value_to_add not in current:
                current.append(link)
                frontmatter[prop_name] = current
                new_content = self._update_frontmatter(content, frontmatter)
                self.file_manager.write_file(full_path, new_content)

        except Exception as e:
            logger.error(f"Failed to add to property: {e}")

    async def _remove_from_property(
        self,
        file_path: str,
        prop_name: str,
        value_to_remove: str
    ) -> None:
        """Remove a link from a frontmatter property list."""
        try:
            full_path = self.file_manager.vault_path / file_path
            if not full_path.exists():
                return

            content = self.file_manager.read_file(full_path)
            if not content:
                return

            frontmatter = self._parse_frontmatter(content)
            current = frontmatter.get(prop_name, [])
            if isinstance(current, str):
                current = [current] if current else []

            # Remove matching links
            filtered = [
                v for v in current
                if self._extract_link_name(v) != value_to_remove
            ]

            if len(filtered) != len(current):
                frontmatter[prop_name] = filtered
                new_content = self._update_frontmatter(content, frontmatter)
                self.file_manager.write_file(full_path, new_content)

        except Exception as e:
            logger.error(f"Failed to remove from property: {e}")

    async def _apply_frontmatter_changes(
        self,
        file_path: str,
        diff: FrontmatterDiff
    ) -> None:
        """Apply frontmatter diff to a file."""
        try:
            full_path = self.file_manager.vault_path / file_path
            if not full_path.exists():
                return

            content = self.file_manager.read_file(full_path)
            if not content:
                return

            frontmatter = self._parse_frontmatter(content)

            for change in diff.added + diff.modified:
                frontmatter[change.key] = change.new_value

            for change in diff.deleted:
                frontmatter.pop(change.key, None)

            new_content = self._update_frontmatter(content, frontmatter)
            self.file_manager.write_file(full_path, new_content)

        except Exception as e:
            logger.error(f"Failed to apply changes to {file_path}: {e}")

    def _compute_frontmatter_diff(
        self,
        old_fm: Dict[str, Any],
        new_fm: Dict[str, Any]
    ) -> FrontmatterDiff:
        """Compute diff between two frontmatter dicts."""
        diff = FrontmatterDiff()

        all_keys = set(old_fm.keys()) | set(new_fm.keys())
        for key in all_keys:
            old_val = old_fm.get(key)
            new_val = new_fm.get(key)

            if old_val is None and new_val is not None:
                diff.added.append(FrontmatterChange(key, None, new_val, "added"))
            elif old_val is not None and new_val is None:
                diff.deleted.append(FrontmatterChange(key, old_val, None, "deleted"))
            elif old_val != new_val:
                diff.modified.append(FrontmatterChange(key, old_val, new_val, "modified"))

        return diff

    def _merge_diffs(self, diffs: List[FrontmatterDiff]) -> FrontmatterDiff:
        """Merge multiple diffs into one."""
        result = FrontmatterDiff()
        seen_keys: Dict[str, FrontmatterChange] = {}

        for diff in diffs:
            for change in diff.all_changes:
                # Keep latest change for each key
                seen_keys[change.key] = change

        for change in seen_keys.values():
            if change.change_type == "added":
                result.added.append(change)
            elif change.change_type == "modified":
                result.modified.append(change)
            elif change.change_type == "deleted":
                result.deleted.append(change)

        return result

    def _filter_excluded_changes(self, diff: FrontmatterDiff) -> FrontmatterDiff:
        """Filter out excluded properties from diff."""
        return FrontmatterDiff(
            added=[c for c in diff.added if c.key not in self.excluded_props],
            modified=[c for c in diff.modified if c.key not in self.excluded_props],
            deleted=[c for c in diff.deleted if c.key not in self.excluded_props]
        )

    def _get_children_recursive(
        self,
        parent_path: str,
        frontmatter: Dict[str, Any],
        visited: Optional[Set[str]] = None
    ) -> List[str]:
        """Get all children recursively."""
        if visited is None:
            visited = set()

        if parent_path in visited:
            return []
        visited.add(parent_path)

        children_links = frontmatter.get("children", [])
        if isinstance(children_links, str):
            children_links = [children_links]

        all_children = []
        for link in children_links:
            child_name = self._extract_link_name(link)
            child_path = self._resolve_file_from_name(child_name)
            if child_path and child_path not in visited:
                all_children.append(child_path)

                # Get child's frontmatter for recursive search
                try:
                    full_path = self.file_manager.vault_path / child_path
                    content = self.file_manager.read_file(full_path)
                    child_fm = self._parse_frontmatter(content) if content else {}
                    all_children.extend(self._get_children_recursive(child_path, child_fm, visited))
                except Exception:
                    pass

        return all_children

    def _parse_links(self, value: Any) -> List[str]:
        """Parse wiki links from property value."""
        if not value:
            return []
        if isinstance(value, str):
            return [self._extract_link_name(value)]
        if isinstance(value, list):
            return [self._extract_link_name(v) for v in value if v]
        return []

    def _extract_link_name(self, link: str) -> str:
        """Extract name from wiki link [[Name]] or return as-is."""
        if not isinstance(link, str):
            return str(link)
        match = re.match(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', link)
        return match.group(1) if match else link

    def _resolve_obsidian_file(self, chunk_id: str, metadata: Dict) -> Optional[str]:
        """Resolve Memory MCP chunk to Obsidian file path."""
        # Check for explicit file path in metadata
        if "file_path" in metadata:
            return metadata["file_path"]
        if "source" in metadata:
            return metadata["source"]
        return None

    def _resolve_file_from_name(self, name: str) -> Optional[str]:
        """Resolve file name to full path in vault."""
        # Try direct match
        for ext in [".md", ""]:
            check_path = self.file_manager.vault_path / f"{name}{ext}"
            if check_path.exists():
                return f"{name}{ext}"

        # Search vault
        for file in self.file_manager.discover_files([".md"]):
            if file.stem == name:
                return str(file.relative_to(self.file_manager.vault_path))

        return None

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from markdown content."""
        if not content or not content.startswith("---"):
            return {}

        try:
            end = content.find("---", 3)
            if end == -1:
                return {}
            yaml_content = content[3:end].strip()
            return yaml.safe_load(yaml_content) or {}
        except Exception:
            return {}

    def _update_frontmatter(self, content: str, frontmatter: Dict) -> str:
        """Update frontmatter in markdown content."""
        # Remove existing frontmatter if present
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:].lstrip()

        # Generate new frontmatter
        if frontmatter:
            yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
            return f"---\n{yaml_str}---\n\n{content}"

        return content
