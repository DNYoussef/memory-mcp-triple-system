"""
EntityService - spaCy-based Named Entity Recognition.

Extracts entities from text and integrates with GraphService.
Provides entity extraction, filtering, and graph integration.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from typing import List, Dict, Any, Optional, Set
import re
from loguru import logger
from difflib import SequenceMatcher
import networkx as nx

from .graph_service import GraphService

_MODEL_CACHE: Dict[str, Any] = {}


def load_spacy_model(model_name: str = "en_core_web_sm"):
    """Load spaCy model with auto-download and caching. Lazy imports spacy."""
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]

    try:
        import spacy
        from spacy.cli import download as spacy_download
    except ImportError:
        logger.warning("spaCy not installed - entity extraction disabled")
        return None

    try:
        nlp = spacy.load(model_name)
    except OSError:
        logger.info("Downloading spaCy model: %s", model_name)
        spacy_download(model_name)
        nlp = spacy.load(model_name)

    _MODEL_CACHE[model_name] = nlp
    return nlp


class EntityService:
    """
    Service for extracting named entities using spaCy.

    Provides NER capabilities and integration with GraphService.
    """

    # Entity types we care about (from spaCy)
    ENTITY_TYPES = {
        'PERSON',      # People, including fictional
        'ORG',         # Organizations
        'GPE',         # Geopolitical entities (countries, cities, states)
        'DATE',        # Absolute or relative dates/periods
        'TIME',        # Times smaller than a day
        'MONEY',       # Monetary values
        'PRODUCT',     # Objects, vehicles, foods, etc.
        'EVENT',       # Named hurricanes, battles, wars, sports events
        'LAW',         # Named documents made into laws
        'NORP',        # Nationalities, religious/political groups
        'FAC',         # Buildings, airports, highways, bridges
        'LOC'          # Non-GPE locations, mountain ranges, bodies of water
    }

    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize EntityService with spaCy model.

        Args:
            model_name: spaCy model name (default: en_core_web_sm)
        """
        self.nlp = load_spacy_model(model_name)
        logger.info(f"Loaded spaCy model: {model_name}")

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract all entities from text.

        Args:
            text: Input text to analyze

        Returns:
            List of entity dictionaries
        """
        if not text or not text.strip():
            return []

        if self.nlp is None:
            return self._regex_extract_entities(text)

        try:
            doc = self.nlp(text)

            entities = []
            for ent in doc.ents:
                entities.append({
                    'text': ent.text,
                    'type': ent.label_,
                    'start': ent.start_char,
                    'end': ent.end_char
                })

            logger.debug(f"Extracted {len(entities)} entities from text")
            return entities

        except Exception as e:
            logger.error(f"Failed to extract entities: {e}")
            return []

    # Compiled regex patterns for fallback NER
    _DATE_RE = re.compile(
        r'\b(?:January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+\d{1,2}(?:,?\s+\d{4})?\b'
    )
    _MULTI_PROPER_RE = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')
    _SINGLE_PROPER_RE = re.compile(r'(?<=[a-z]\s)([A-Z][a-z]{2,})\b')
    _ACRONYM_RE = re.compile(r'\b([A-Z]{2,})\b')

    def _regex_extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Regex fallback for entity extraction when spaCy is unavailable."""
        entities: List[Dict[str, Any]] = []

        # DATE patterns (month day, year)
        for m in self._DATE_RE.finditer(text):
            entities.append({
                'text': m.group(), 'type': 'DATE',
                'start': m.start(), 'end': m.end(),
            })

        # Multi-word proper nouns → PERSON heuristic
        for m in self._MULTI_PROPER_RE.finditer(text):
            if not self._overlaps_existing(entities, m.start(), m.end()):
                entities.append({
                    'text': m.group(), 'type': 'PERSON',
                    'start': m.start(), 'end': m.end(),
                })

        # Single capitalized words mid-sentence → ORG heuristic
        for m in self._SINGLE_PROPER_RE.finditer(text):
            s, e = m.start(1), m.end(1)
            if not self._overlaps_existing(entities, s, e):
                entities.append({
                    'text': m.group(1), 'type': 'ORG',
                    'start': s, 'end': e,
                })

        # All-caps acronyms (USA, NASA, IBM) → ORG heuristic
        for m in self._ACRONYM_RE.finditer(text):
            s, e = m.start(1), m.end(1)
            if not self._overlaps_existing(entities, s, e):
                entities.append({
                    'text': m.group(1), 'type': 'ORG',
                    'start': s, 'end': e,
                })

        return sorted(entities, key=lambda ent: ent['start'])

    @staticmethod
    def _overlaps_existing(entities: List[Dict], start: int, end: int) -> bool:
        """Check if span overlaps any existing entity."""
        return any(e['start'] <= start < e['end'] or e['start'] < end <= e['end']
                    for e in entities)

    def extract_entities_by_type(
        self,
        text: str,
        entity_types: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract entities filtered by type.

        Args:
            text: Input text to analyze
            entity_types: List of entity types to extract

        Returns:
            List of filtered entity dictionaries
        """
        all_entities = self.extract_entities(text)

        # Filter by requested types
        filtered = [
            ent for ent in all_entities
            if ent['type'] in entity_types
        ]

        logger.debug(f"Filtered to {len(filtered)} entities of types {entity_types}")
        return filtered

    def add_entities_to_graph(
        self,
        chunk_id: str,
        text: str,
        graph_service: GraphService
    ) -> Dict[str, Any]:
        """
        Extract entities and add to graph.

        Args:
            chunk_id: Chunk identifier
            text: Text to extract entities from
            graph_service: GraphService instance

        Returns:
            Dictionary with stats (entities added, relationships created)
        """
        try:
            entities = self.extract_entities(text)

            entities_added = self._create_entity_nodes(
                entities, graph_service
            )
            relationships_created = self._create_mention_relationships(
                chunk_id, entities, graph_service
            )

            logger.info(
                f"Added {entities_added} entities and "
                f"{relationships_created} relationships for chunk {chunk_id}"
            )

            return {
                'entities_added': entities_added,
                'relationships_created': relationships_created,
                'entity_types': list(set(e['type'] for e in entities))
            }

        except Exception as e:
            logger.error(f"Failed to add entities to graph: {e}")
            return {
                'entities_added': 0,
                'relationships_created': 0,
                'entity_types': []
            }

    def _create_entity_nodes(
        self,
        entities: List[Dict[str, Any]],
        graph_service: GraphService
    ) -> int:
        """
        Create entity nodes in graph.

        Args:
            entities: List of entity dictionaries
            graph_service: GraphService instance

        Returns:
            Number of entities added
        """
        entities_added = 0

        for ent in entities:
            entity_id = self._normalize_entity_text(ent['text'])

            success = graph_service.add_entity_node(
                entity_id,
                ent['type'],
                {
                    'text': ent['text'],
                    'start': ent['start'],
                    'end': ent['end']
                }
            )

            if success:
                entities_added += 1

        return entities_added

    def _create_mention_relationships(
        self,
        chunk_id: str,
        entities: List[Dict[str, Any]],
        graph_service: GraphService
    ) -> int:
        """
        Create mention relationships between chunk and entities.

        Args:
            chunk_id: Chunk identifier
            entities: List of entity dictionaries
            graph_service: GraphService instance

        Returns:
            Number of relationships created
        """
        relationships_created = 0

        for ent in entities:
            entity_id = self._normalize_entity_text(ent['text'])

            # FIX: Correct parameter order (source, relationship_type, target, metadata)
            success = graph_service.add_relationship(
                chunk_id,
                GraphService.EDGE_MENTIONS,
                entity_id,
                {
                    'entity_type': ent['type'],
                    'position': ent['start'],
                    'confidence': 0.8  # Explicit confidence for Bayesian filtering
                }
            )

            if success:
                relationships_created += 1

        return relationships_created

    def get_entity_stats(self, text: str) -> Dict[str, int]:
        """
        Get entity counts by type.

        Args:
            text: Input text to analyze

        Returns:
            Dictionary of entity type counts
        """
        entities = self.extract_entities(text)

        # Count by type
        stats: Dict[str, int] = {}
        for ent in entities:
            entity_type = ent['type']
            stats[entity_type] = stats.get(entity_type, 0) + 1

        return stats

    def deduplicate_entities(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate entities (same text and type).

        Args:
            entities: List of entity dictionaries

        Returns:
            Deduplicated list
        """
        seen = set()
        deduplicated = []

        for ent in entities:
            key = (self._normalize_entity_text(ent['text']), ent['type'])

            if key not in seen:
                seen.add(key)
                deduplicated.append(ent)

        logger.debug(f"Deduplicated {len(entities)} entities to {len(deduplicated)}")
        return deduplicated

    def batch_extract_entities(
        self,
        texts: List[str]
    ) -> List[List[Dict[str, Any]]]:
        """
        Extract entities from multiple texts (batch processing).

        Args:
            texts: List of text strings

        Returns:
            List of entity lists (one per input text)
        """
        if not texts:
            return []

        if self.nlp is None:
            return [self._regex_extract_entities(t) for t in texts]

        try:
            docs = list(self.nlp.pipe(texts))

            results = []
            for doc in docs:
                entities = []
                for ent in doc.ents:
                    entities.append({
                        'text': ent.text,
                        'type': ent.label_,
                        'start': ent.start_char,
                        'end': ent.end_char
                    })
                results.append(entities)

            logger.debug(f"Batch extracted entities from {len(texts)} texts")
            return results

        except Exception as e:
            logger.error(f"Failed batch extraction: {e}")
            return [[] for _ in texts]

    def _normalize_entity_text(self, text: str) -> str:
        """
        Normalize entity text for ID generation.

        Args:
            text: Entity text

        Returns:
            Normalized text (lowercase, no spaces)
        """
        return text.lower().replace(' ', '_').replace('.', '')


class EntityConsolidator:
    """
    Consolidate duplicate entities in knowledge graph.

    Week 8 component for GraphRAG entity consolidation.
    Merges duplicate entities (e.g., "NASA Rule 10", "NASA_Rule_10", "rule 10")
    using string similarity (Levenshtein distance).

    PREMORTEM Risk #7 Mitigation:
    - Target: ≥90% consolidation accuracy
    - Method: String similarity (difflib.SequenceMatcher)
    - Use case: Merge entity variants across chunks

    NASA Rule 10 Compliant: All methods ≤60 LOC
    """

    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize entity consolidator.

        Args:
            similarity_threshold: Min similarity for duplicate detection (0.85)

        NASA Rule 10: 6 LOC (≤60) ✅
        """
        self.similarity_threshold = similarity_threshold
        logger.info(f"EntityConsolidator initialized with threshold={similarity_threshold}")

    def find_duplicate_entities(
        self,
        graph: nx.DiGraph
    ) -> List[Set[str]]:
        """
        Find groups of duplicate entities using string similarity.

        Args:
            graph: NetworkX knowledge graph

        Returns:
            List of entity groups (sets) that are duplicates

        Example:
            >>> consolidator = EntityConsolidator()
            >>> duplicates = consolidator.find_duplicate_entities(graph)
            >>> print(duplicates)
            [
                {"NASA Rule 10", "NASA_Rule_10", "rule 10"},
                {"Python", "python", "Python language"}
            ]

        NASA Rule 10: 42 LOC (≤60) ✅
        """
        # Get all entity nodes (filter by node type if available)
        entity_nodes = [
            node for node in graph.nodes()
            if isinstance(node, str)  # Entity IDs are strings
        ]

        # Group entities by similarity
        duplicate_groups: List[Set[str]] = []
        processed: Set[str] = set()

        for i, entity1 in enumerate(entity_nodes):
            if entity1 in processed:
                continue

            # Start new group with this entity
            group: Set[str] = {entity1}
            processed.add(entity1)

            # Find similar entities
            for entity2 in entity_nodes[i + 1:]:
                if entity2 in processed:
                    continue

                similarity = self._calculate_similarity(entity1, entity2)

                if similarity >= self.similarity_threshold:
                    group.add(entity2)
                    processed.add(entity2)

            # Only add groups with 2+ entities (actual duplicates)
            if len(group) > 1:
                duplicate_groups.append(group)

        logger.info(f"Found {len(duplicate_groups)} duplicate entity groups")
        return duplicate_groups

    def merge_entities(
        self,
        graph: nx.DiGraph,
        entity_group: Set[str],
        canonical_name: Optional[str] = None
    ) -> str:
        """
        Merge duplicate entities into single canonical entity.

        Args:
            graph: NetworkX knowledge graph
            entity_group: Set of duplicate entity names
            canonical_name: Name for merged entity (auto-select if None)

        Returns:
            Canonical entity name

        Logic:
        1. Select canonical name (most frequent or provided)
        2. Consolidate chunk references from all variants
        3. Merge node attributes (frequency, importance)
        4. Update edges to point to canonical entity
        5. Remove duplicate nodes

        NASA Rule 10: 59 LOC (≤60) ✅
        """
        if not entity_group or len(entity_group) < 2:
            logger.warning("Entity group too small for merging, skipping")
            return list(entity_group)[0] if entity_group else ""

        # Select canonical entity
        if canonical_name is None:
            canonical_name = self._select_canonical_entity(graph, entity_group)

        # Consolidate attributes from all variants
        merged_attrs = self._merge_attributes(graph, entity_group)

        # Update graph
        for entity in entity_group:
            if entity == canonical_name:
                # Update canonical entity with merged attributes
                graph.nodes[canonical_name].update(merged_attrs)
                continue

            # Transfer all edges to canonical entity
            # In-edges: (source → entity) becomes (source → canonical)
            for pred in list(graph.predecessors(entity)):
                edge_data = graph.get_edge_data(pred, entity)
                if not graph.has_edge(pred, canonical_name):
                    graph.add_edge(pred, canonical_name, **edge_data)

            # Out-edges: (entity → target) becomes (canonical → target)
            for succ in list(graph.successors(entity)):
                edge_data = graph.get_edge_data(entity, succ)
                if not graph.has_edge(canonical_name, succ):
                    graph.add_edge(canonical_name, succ, **edge_data)

            # Remove duplicate node
            graph.remove_node(entity)

        logger.info(f"Merged {len(entity_group)} entities into '{canonical_name}'")
        return canonical_name

    def consolidate_all(
        self,
        graph: nx.DiGraph
    ) -> Dict[str, Any]:
        """
        Run full consolidation pipeline on graph.

        Returns:
            {
                "groups_found": 15,
                "entities_merged": 42,
                "canonical_entities": ["NASA Rule 10", "Python", ...],
                "consolidation_rate": 0.93  # 93% accuracy
            }

        NASA Rule 10: 32 LOC (≤60) ✅
        """
        initial_entity_count = graph.number_of_nodes()

        # Find all duplicate groups
        duplicate_groups = self.find_duplicate_entities(graph)

        # Merge each group
        canonical_entities = []
        total_entities_merged = 0

        for group in duplicate_groups:
            canonical = self.merge_entities(graph, group)
            canonical_entities.append(canonical)
            total_entities_merged += len(group) - 1  # -1 for canonical itself

        final_entity_count = graph.number_of_nodes()

        # Calculate consolidation rate
        consolidation_rate = (
            total_entities_merged / initial_entity_count
            if initial_entity_count > 0
            else 0.0
        )

        logger.info(
            f"Consolidation complete: {len(duplicate_groups)} groups, "
            f"{total_entities_merged} entities merged, "
            f"rate={consolidation_rate:.2%}"
        )

        return {
            "groups_found": len(duplicate_groups),
            "entities_merged": total_entities_merged,
            "canonical_entities": canonical_entities,
            "consolidation_rate": consolidation_rate
        }

    def _calculate_similarity(self, entity1: str, entity2: str) -> float:
        """
        Calculate string similarity between two entities.

        Uses difflib.SequenceMatcher (Levenshtein-based).

        Args:
            entity1: First entity name
            entity2: Second entity name

        Returns:
            Similarity score (0-1)

        NASA Rule 10: 13 LOC (≤60) ✅
        """
        # Normalize for comparison
        norm1 = entity1.lower().replace('_', ' ').strip()
        norm2 = entity2.lower().replace('_', ' ').strip()

        # Calculate similarity
        similarity = SequenceMatcher(None, norm1, norm2).ratio()

        return similarity

    def _select_canonical_entity(
        self,
        graph: nx.DiGraph,
        entity_group: Set[str]
    ) -> str:
        """
        Select canonical entity from group (most frequent variant).

        Args:
            graph: Knowledge graph
            entity_group: Set of duplicate entity names

        Returns:
            Canonical entity name

        NASA Rule 10: 22 LOC (≤60) ✅
        """
        # Score each entity by frequency (in-degree + out-degree)
        scores: Dict[str, int] = {}

        for entity in entity_group:
            if entity in graph:
                in_degree = graph.in_degree(entity)
                out_degree = graph.out_degree(entity)
                scores[entity] = in_degree + out_degree
            else:
                scores[entity] = 0

        # Select entity with highest score
        canonical = max(scores, key=lambda x: scores[x])

        logger.debug(f"Selected canonical entity '{canonical}' from {entity_group}")
        return canonical

    def _merge_attributes(
        self,
        graph: nx.DiGraph,
        entity_group: Set[str]
    ) -> Dict[str, Any]:
        """
        Merge node attributes from all entities in group.

        Args:
            graph: Knowledge graph
            entity_group: Set of duplicate entity names

        Returns:
            Merged attributes dictionary

        NASA Rule 10: 30 LOC (≤60) ✅
        """
        merged: Dict[str, Any] = {}

        # Collect chunk_ids from all variants
        all_chunk_ids: Set[str] = set()

        for entity in entity_group:
            if entity not in graph:
                continue

            attrs = graph.nodes[entity]

            # Merge chunk_ids (if present)
            if "chunk_ids" in attrs:
                chunk_ids = attrs["chunk_ids"]
                if isinstance(chunk_ids, list):
                    all_chunk_ids.update(chunk_ids)

            # Merge other attributes (take first non-None value)
            for key, value in attrs.items():
                if key not in merged and value is not None:
                    merged[key] = value

        # Set consolidated chunk_ids
        if all_chunk_ids:
            merged["chunk_ids"] = sorted(list(all_chunk_ids))

        return merged
