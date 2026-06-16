"""Entity Extraction Confidence Scorer for CAPTURE-003.

Scores confidence for entity extraction (people, places, projects, topics).

WHO: confidence-scoring:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-003)
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field

from src.integrations.confidence_scoring_schema import (
    ClassificationResult,
    ClassificationType,
    EscalationReason,
    combine_confidences,
    ESCALATION_THRESHOLD,
)

logger = logging.getLogger(__name__)


class EntityType:
    """Types of entities that can be extracted."""
    PERSON = "person"
    PLACE = "place"
    PROJECT = "project"
    TOPIC = "topic"
    DATE = "date"
    TIME = "time"
    URL = "url"
    EMAIL = "email"
    HASHTAG = "hashtag"
    MENTION = "mention"
    ORGANIZATION = "organization"
    MONEY = "money"
    PHONE = "phone"


# Entity extraction patterns with confidence weights
ENTITY_PATTERNS = {
    EntityType.EMAIL: {
        "patterns": [
            (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", 0.95),
        ],
        "base_confidence": 0.9,
    },
    EntityType.URL: {
        "patterns": [
            (r"https?://[^\s<>\"']+", 0.95),
            (r"www\.[^\s<>\"']+", 0.85),
        ],
        "base_confidence": 0.9,
    },
    EntityType.HASHTAG: {
        "patterns": [
            (r"#[A-Za-z][A-Za-z0-9_]*", 0.9),
        ],
        "base_confidence": 0.85,
    },
    EntityType.MENTION: {
        "patterns": [
            (r"@[A-Za-z][A-Za-z0-9_]*", 0.9),
        ],
        "base_confidence": 0.85,
    },
    EntityType.PHONE: {
        "patterns": [
            (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", 0.8),
            (r"\(\d{3}\)\s*\d{3}[-.]?\d{4}", 0.85),
            (r"\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}", 0.8),
        ],
        "base_confidence": 0.75,
    },
    EntityType.MONEY: {
        "patterns": [
            (r"\$\d+(?:,\d{3})*(?:\.\d{2})?", 0.9),
            (r"\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP|JPY)", 0.85),
        ],
        "base_confidence": 0.85,
    },
    EntityType.DATE: {
        "patterns": [
            (r"\b\d{4}-\d{2}-\d{2}\b", 0.95),  # ISO format
            (r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", 0.7),  # US format
            (r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b", 0.85),
            (r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b", 0.85),
        ],
        "base_confidence": 0.8,
    },
    EntityType.TIME: {
        "patterns": [
            (r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b", 0.8),
            (r"\b\d{1,2}\s*(?:AM|PM|am|pm)\b", 0.7),
        ],
        "base_confidence": 0.75,
    },
    EntityType.PERSON: {
        "patterns": [
            # Capitalized names (2-3 words)
            (r"\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", 0.6),
            # Title + name
            (r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", 0.8),
        ],
        "base_confidence": 0.5,
        "requires_context": True,
    },
    EntityType.ORGANIZATION: {
        "patterns": [
            (r"\b[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*\s+(?:Inc|Corp|LLC|Ltd|Co|Company|Organization|Foundation)\b", 0.85),
            (r"\b(?:Google|Microsoft|Apple|Amazon|Meta|Facebook|Twitter|LinkedIn)\b", 0.9),
        ],
        "base_confidence": 0.7,
    },
    EntityType.PLACE: {
        "patterns": [
            # US States
            (r"\b(?:Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New\s+Hampshire|New\s+Jersey|New\s+Mexico|New\s+York|North\s+Carolina|North\s+Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode\s+Island|South\s+Carolina|South\s+Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West\s+Virginia|Wisconsin|Wyoming)\b", 0.9),
            # Major cities
            (r"\b(?:New York|Los Angeles|Chicago|Houston|Phoenix|Philadelphia|San Antonio|San Diego|Dallas|San Jose|Austin|Jacksonville|Fort Worth|Columbus|Charlotte|Seattle|Denver|Boston|El Paso|Nashville|Detroit|Portland|Memphis|Oklahoma City|Las Vegas|Louisville|Baltimore|Milwaukee|Albuquerque|Tucson|Fresno|Sacramento|Mesa|Kansas City|Atlanta|Miami|Minneapolis|Tulsa|Cleveland|Wichita|Arlington|New Orleans|Bakersfield|Tampa|Honolulu|Aurora|Anaheim|Santa Ana|St\. Louis|Riverside|Corpus Christi|Lexington|Pittsburgh|Anchorage|Stockton|Cincinnati|Saint Paul|Toledo|Greensboro|Newark|Plano|Henderson|Lincoln|Buffalo|Jersey City|Chula Vista|Fort Wayne|Orlando|St\. Petersburg|Chandler|Laredo|Norfolk|Durham|Madison|Lubbock|Irvine|Winston-Salem|Glendale|Garland|Hialeah|Reno|Chesapeake|Gilbert|Baton Rouge|Irving|Scottsdale|North Las Vegas|Fremont|Boise|Richmond|San Bernardino|Birmingham|Spokane|Rochester|Des Moines|Modesto|Fayetteville|Tacoma|Oxnard|Fontana|Columbus|Montgomery|Moreno Valley|Shreveport|Aurora|Yonkers|Akron|Huntington Beach|Little Rock|Augusta|Amarillo|Glendale|Mobile|Grand Rapids|Salt Lake City|Tallahassee|Huntsville|Grand Prairie|Knoxville|Worcester|Newport News|Brownsville|Overland Park|Santa Clarita|Providence|Garden Grove|Chattanooga|Oceanside|Jackson|Fort Lauderdale|Santa Rosa|Rancho Cucamonga|Port St\. Lucie|Tempe|Ontario|Vancouver|Cape Coral|Sioux Falls|Springfield|Peoria|Pembroke Pines|Elk Grove|Salem|Lancaster|Corona|Eugene|Palmdale|Salinas|Springfield|Pasadena|Fort Collins|Hayward|Pomona|Cary|Rockford|Alexandria|Escondido|McKinney|Kansas City|Joliet|Sunnyvale|Torrance|Bridgeport|Lakewood|Hollywood|Paterson|Naperville|Syracuse|Mesquite|Dayton|Savannah|Clarksville|Orange|Pasadena|Fullerton|Killeen|Frisco|Hampton|McAllen|Warren|Bellevue|West Valley City|Columbia|Olathe|Sterling Heights|New Haven|Miramar|Waco|Thousand Oaks|Cedar Rapids|Charleston|Visalia|Topeka|Elizabeth|Gainesville|Thornton|Roseville|Carrollton|Coral Springs|Stamford|Simi Valley|Concord|Hartford|Kent|Lafayette|Midland|Surprise|Denton|Victorville|Evansville|Santa Clara|Abilene|Athens|Vallejo|Allentown|Norman|Beaumont|Independence|Murfreesboro|Ann Arbor|Springfield|Berkeley|Peoria|Provo|El Monte|Columbia|Lansing|Fargo|Downey|Costa Mesa|Wilmington|Arvada|Inglewood|Miami Gardens|Carlsbad|Westminster|Rochester|Odessa|Manchester|Elgin|West Jordan|Round Rock|Clearwater|Waterbury|Gresham|Fairfield|Billings|Lowell|San Buenaventura|Pueblo|High Point|West Covina|Richmond|Murrieta|Cambridge|Antioch|Temecula|Norwalk|Centennial|Everett|Palm Bay|Wichita Falls|Green Bay|Daly City|Burbank|Richardson|Pompano Beach|North Charleston|Broken Arrow|Boulder|West Palm Beach|Santa Maria|El Cajon|Davenport|Rialto|Las Cruces|San Mateo|Lewisville|South Bend|Lakeland|Erie|Tyler|Pearland|College Station|Kenosha|Sandy Springs|Clovis|Flint|Roanoke|Albany|Jurupa Valley|Compton|San Angelo|Hillsboro|Lawton|Renton|Vista|Davie|Greeley|Mission Viejo|Portsmouth|Dearborn|South Gate|Tuscaloosa|Livonia|New Bedford|Vacaville|Brockton|Roswell|Beaverton|Quincy|Sparks|Yakima)\b", 0.85),
        ],
        "base_confidence": 0.6,
    },
    EntityType.PROJECT: {
        "patterns": [
            # Project naming patterns
            (r"\b(?:memory-mcp|context-cascade|trader-ai|life-os|fog-compute)\b", 0.95),
            (r"\b[a-z]+-[a-z]+(?:-[a-z]+)*\b", 0.4),  # kebab-case names
        ],
        "base_confidence": 0.5,
        "requires_context": True,
    },
    EntityType.TOPIC: {
        "patterns": [
            # Tech topics
            (r"\b(?:machine learning|deep learning|neural network|artificial intelligence|natural language processing|computer vision|reinforcement learning|data science|big data|cloud computing|devops|microservices|kubernetes|docker|api|rest|graphql|database|sql|nosql|blockchain|cryptocurrency|cybersecurity|web development|mobile development|frontend|backend|fullstack)\b", 0.8),
        ],
        "base_confidence": 0.6,
        "requires_context": True,
    },
}


# Context keywords that boost entity confidence
CONTEXT_BOOSTERS = {
    EntityType.PERSON: [
        "said", "told", "asked", "mentioned", "according to",
        "contacted", "emailed", "called", "met with", "spoke with",
        "CEO", "CTO", "manager", "engineer", "developer", "designer",
    ],
    EntityType.PROJECT: [
        "project", "repo", "repository", "codebase", "module",
        "feature", "task", "ticket", "issue", "PR", "branch",
    ],
    EntityType.TOPIC: [
        "about", "regarding", "concerning", "related to",
        "topic", "subject", "discussion", "conversation",
    ],
    EntityType.PLACE: [
        "in", "at", "from", "to", "near", "around",
        "located", "based", "headquartered", "office",
    ],
    EntityType.ORGANIZATION: [
        "company", "corporation", "organization", "firm",
        "startup", "enterprise", "business", "agency",
    ],
}


@dataclass
class ExtractedEntity:
    """An extracted entity with confidence score."""

    entity_type: str
    value: str
    confidence: float
    start_pos: int
    end_pos: int
    context: str = ""
    components: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "entity_type": self.entity_type,
            "value": self.value,
            "confidence": round(self.confidence, 4),
            "position": {"start": self.start_pos, "end": self.end_pos},
            "context": self.context[:100] if self.context else "",
            "components": {k: round(v, 4) for k, v in self.components.items()},
        }


@dataclass
class EntityExtractionConfig:
    """Configuration for entity extraction scorer."""

    escalation_threshold: float = ESCALATION_THRESHOLD
    min_confidence: float = 0.3
    context_window: int = 50  # Characters around entity
    enable_caching: bool = True
    max_entities_per_type: int = 100


class EntityExtractionScorer:
    """Confidence scorer for entity extraction.

    Extracts entities from text and scores confidence for each.
    """

    def __init__(self, config: Optional[EntityExtractionConfig] = None):
        """Initialize entity extraction scorer.

        Args:
            config: Scorer configuration
        """
        self.config = config or EntityExtractionConfig()
        self._cache: Dict[str, List[ExtractedEntity]] = {}
        self._stats = {
            "total_extractions": 0,
            "by_type": {},
            "low_confidence": 0,
            "high_confidence": 0,
        }

    def extract_entities(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
    ) -> List[ExtractedEntity]:
        """Extract all entities from text with confidence scores.

        Args:
            text: Input text to analyze
            entity_types: Optional list of entity types to extract

        Returns:
            List of extracted entities with confidence scores
        """
        # Check cache
        cache_key = text[:500].lower()
        if self.config.enable_caching and cache_key in self._cache:
            cached = self._cache[cache_key]
            if entity_types:
                return [e for e in cached if e.entity_type in entity_types]
            return cached

        entities: List[ExtractedEntity] = []
        types_to_extract = entity_types or list(ENTITY_PATTERNS.keys())

        for entity_type in types_to_extract:
            if entity_type not in ENTITY_PATTERNS:
                continue

            type_entities = self._extract_type(text, entity_type)
            entities.extend(type_entities)

        # Sort by position
        entities.sort(key=lambda e: e.start_pos)

        # Remove overlapping entities (keep higher confidence)
        entities = self._remove_overlaps(entities)

        # Filter by minimum confidence
        entities = [e for e in entities if e.confidence >= self.config.min_confidence]

        # Update cache
        if self.config.enable_caching:
            self._cache[cache_key] = entities

        # Update stats
        self._update_stats(entities)

        return entities

    def extract_with_result(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
    ) -> ClassificationResult:
        """Extract entities and return as ClassificationResult.

        Args:
            text: Input text to analyze
            entity_types: Optional list of entity types to extract

        Returns:
            ClassificationResult with entities and overall confidence
        """
        entities = self.extract_entities(text, entity_types)

        # Calculate overall confidence
        if not entities:
            overall_confidence = 0.3
        else:
            confidences = [e.confidence for e in entities]
            overall_confidence = combine_confidences(
                confidences,
                method="geometric_mean",
            )

        # Build alternatives (entity types with counts)
        type_counts: Dict[str, int] = {}
        for entity in entities:
            type_counts[entity.entity_type] = type_counts.get(entity.entity_type, 0) + 1

        alternatives = [
            {"entity_type": t, "count": c}
            for t, c in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return ClassificationResult.create(
            classification_type=ClassificationType.ENTITY_EXTRACTION,
            value=[e.to_dict() for e in entities],
            confidence_score=overall_confidence,
            input_text=text,
            alternatives=alternatives,
            confidence_components={
                "entity_count": len(entities),
                "type_diversity": len(type_counts),
                "avg_confidence": sum(e.confidence for e in entities) / len(entities) if entities else 0,
            },
        )

    def _extract_type(
        self,
        text: str,
        entity_type: str,
    ) -> List[ExtractedEntity]:
        """Extract entities of a specific type."""
        config = ENTITY_PATTERNS[entity_type]
        entities: List[ExtractedEntity] = []
        seen_values: Set[str] = set()

        for pattern, pattern_weight in config["patterns"]:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                value = match.group()

                # Skip duplicates
                value_normalized = value.lower().strip()
                if value_normalized in seen_values:
                    continue
                seen_values.add(value_normalized)

                # Calculate confidence
                confidence, components = self._calculate_confidence(
                    text, match, entity_type, pattern_weight, config
                )

                # Get context
                context = self._get_context(text, match.start(), match.end())

                entity = ExtractedEntity(
                    entity_type=entity_type,
                    value=value,
                    confidence=confidence,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    context=context,
                    components=components,
                )

                entities.append(entity)

                if len(entities) >= self.config.max_entities_per_type:
                    break

        return entities

    def _calculate_confidence(
        self,
        text: str,
        match: re.Match,
        entity_type: str,
        pattern_weight: float,
        config: Dict[str, Any],
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate confidence score for an entity match."""
        components: Dict[str, float] = {}

        # Base confidence from pattern
        base_confidence = config["base_confidence"]
        components["base_confidence"] = base_confidence
        components["pattern_weight"] = pattern_weight

        # Pattern match score
        pattern_score = pattern_weight * 0.5 + base_confidence * 0.5
        components["pattern_score"] = pattern_score

        # Context boost
        context_boost = 0.0
        if entity_type in CONTEXT_BOOSTERS:
            context = self._get_context(text, match.start(), match.end(), window=100)
            context_lower = context.lower()

            boosters = CONTEXT_BOOSTERS[entity_type]
            matches = sum(1 for b in boosters if b.lower() in context_lower)

            if matches > 0:
                context_boost = min(0.2, matches * 0.05)
                components["context_boost"] = context_boost

        # Length penalty for very short entities
        value = match.group()
        if len(value) < 3:
            length_penalty = 0.1
            components["length_penalty"] = length_penalty
        else:
            length_penalty = 0.0

        # Requires context check
        requires_context = config.get("requires_context", False)
        if requires_context and context_boost == 0:
            context_penalty = 0.15
            components["context_penalty"] = context_penalty
        else:
            context_penalty = 0.0

        # Final confidence
        final_confidence = min(1.0, max(0.0,
            pattern_score + context_boost - length_penalty - context_penalty
        ))
        components["final_confidence"] = final_confidence

        return final_confidence, components

    def _get_context(
        self,
        text: str,
        start: int,
        end: int,
        window: Optional[int] = None,
    ) -> str:
        """Get surrounding context for an entity."""
        window = window or self.config.context_window
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]

    def _remove_overlaps(
        self,
        entities: List[ExtractedEntity],
    ) -> List[ExtractedEntity]:
        """Remove overlapping entities, keeping higher confidence ones."""
        if not entities:
            return []

        # Sort by confidence (descending)
        sorted_entities = sorted(entities, key=lambda e: e.confidence, reverse=True)

        result: List[ExtractedEntity] = []
        used_ranges: List[Tuple[int, int]] = []

        for entity in sorted_entities:
            # Check for overlap with existing entities
            overlaps = False
            for start, end in used_ranges:
                if not (entity.end_pos <= start or entity.start_pos >= end):
                    overlaps = True
                    break

            if not overlaps:
                result.append(entity)
                used_ranges.append((entity.start_pos, entity.end_pos))

        # Sort by position again
        result.sort(key=lambda e: e.start_pos)
        return result

    def _update_stats(self, entities: List[ExtractedEntity]) -> None:
        """Update internal statistics."""
        self._stats["total_extractions"] += len(entities)

        for entity in entities:
            self._stats["by_type"][entity.entity_type] = (
                self._stats["by_type"].get(entity.entity_type, 0) + 1
            )

            if entity.confidence < self.config.escalation_threshold:
                self._stats["low_confidence"] += 1
            else:
                self._stats["high_confidence"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        return {
            **self._stats,
            "cache_size": len(self._cache),
        }

    def clear_cache(self) -> None:
        """Clear the extraction cache."""
        self._cache.clear()

    def get_entities_needing_review(
        self,
        entities: List[ExtractedEntity],
    ) -> List[ExtractedEntity]:
        """Get entities with low confidence that need human review."""
        return [
            e for e in entities
            if e.confidence < self.config.escalation_threshold
        ]

    def get_escalation_reason(
        self,
        entity: ExtractedEntity,
    ) -> Optional[EscalationReason]:
        """Determine escalation reason for an entity."""
        if entity.confidence >= self.config.escalation_threshold:
            return None

        if entity.confidence < 0.4:
            return EscalationReason.LOW_CONFIDENCE

        # Check if requires context
        config = ENTITY_PATTERNS.get(entity.entity_type, {})
        if config.get("requires_context") and entity.components.get("context_penalty", 0) > 0:
            return EscalationReason.AMBIGUOUS_CLASSIFICATION

        return EscalationReason.MODEL_UNCERTAINTY
