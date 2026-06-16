"""Proactive Context Injector - RETRIEVE Level 4.

Injects context BEFORE user asks based on trigger events.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (RETRIEVE-001)
"""

import copy
from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger

from ..integrations.proactive_schema import (
    TriggerEvent,
    TriggerType,
    InjectedContext,
    InjectionRule,
    InjectionStats,
    DEFAULT_RULES,
)
from .ontology_bridge import OntologyBridge


class ProactiveContextInjector:
    """Proactively inject context based on trigger events.

    Usage:
        injector = ProactiveContextInjector(
            ontology_bridge=bridge,
            nexus_processor=nexus
        )

        # Register trigger
        event = TriggerEvent.from_file_open("src/main.py", "my-project")
        context = await injector.handle_trigger(event)

        # Get stats
        stats = injector.get_stats()
    """

    # Weight on retrieved-chunk relevance vs. the trigger's own confidence when
    # the trigger is probabilistic. 0.7 keeps chunk quality dominant.
    _CHUNK_RELEVANCE_WEIGHT = 0.7

    def __init__(
        self,
        ontology_bridge: OntologyBridge,
        nexus_processor: Optional[Any] = None,
        rules: Optional[List[InjectionRule]] = None,
    ):
        """Initialize proactive injector.

        Args:
            ontology_bridge: OntologyBridge for entity-aware retrieval
            nexus_processor: NexusProcessor for RAG retrieval (optional)
            rules: Custom injection rules (default: DEFAULT_RULES)
        """
        self.ontology_bridge = ontology_bridge
        self.nexus_processor = nexus_processor
        # Deep-copy so each injector owns its rules. DEFAULT_RULES is a shared
        # module-level list of mutable dataclasses; without copying, disabling a
        # rule on one injector (or in one test) would leak to every other.
        self.rules = {r.rule_id: copy.deepcopy(r) for r in (rules or DEFAULT_RULES)}

        # Track injections and cooldowns
        self._injection_history: List[InjectedContext] = []
        self._last_injection_by_type: Dict[TriggerType, datetime] = {}

        # Statistics
        self.stats = InjectionStats()

        logger.info("ProactiveContextInjector initialized")

    async def handle_trigger(
        self,
        event: TriggerEvent,
        mode: str = "execution",
        dry_run: bool = False,
    ) -> Optional[InjectedContext]:
        """Handle a trigger event and inject context if rules match.

        Args:
            event: TriggerEvent to process
            mode: Query mode (execution/planning/brainstorm)
            dry_run: If True, don't actually inject, just return what would be injected

        Returns:
            InjectedContext if injected, None if suppressed by rules
        """
        self.stats.total_triggers += 1
        self.stats.by_trigger_type[event.trigger_type.value] = (
            self.stats.by_trigger_type.get(event.trigger_type.value, 0) + 1
        )

        # Find matching rules
        matching_rules = self._find_matching_rules(event)
        if not matching_rules:
            logger.debug(f"No matching rules for trigger: {event.trigger_type}")
            return None

        # Check cooldown
        if self._is_in_cooldown(event, matching_rules):
            logger.debug(f"Trigger in cooldown: {event.trigger_type}")
            return None

        # Retrieve context
        context = await self._retrieve_context(event, matching_rules, mode)
        if not context:
            logger.debug(f"No relevant context found for trigger: {event.trigger_type}")
            return None

        # Check relevance threshold
        if context.relevance_score < min(r.min_relevance for r in matching_rules):
            logger.debug(
                f"Context relevance {context.relevance_score} below threshold "
                f"for trigger: {event.trigger_type}"
            )
            return None

        # Inject context (unless dry run)
        if not dry_run:
            self._inject_context(context)

        # Update stats
        self.stats.total_injections += 1
        self.stats.by_priority[event.priority.value] = (
            self.stats.by_priority.get(event.priority.value, 0) + 1
        )
        self.stats.total_tokens_injected += context.token_count

        # Update average relevance
        if self.stats.total_injections == 1:
            self.stats.average_relevance = context.relevance_score
        else:
            self.stats.average_relevance = (
                self.stats.average_relevance * (self.stats.total_injections - 1)
                + context.relevance_score
            ) / self.stats.total_injections

        # Record last injection time
        self._last_injection_by_type[event.trigger_type] = datetime.utcnow()

        logger.info(
            f"Injected context for {event.trigger_type.value}: "
            f"{len(context.chunks)} chunks, relevance={context.relevance_score:.2f}"
        )

        return context

    async def _retrieve_context(
        self,
        event: TriggerEvent,
        rules: List[InjectionRule],
        mode: str,
    ) -> Optional[InjectedContext]:
        """Retrieve relevant context for trigger event."""
        max_tokens = min(r.max_tokens for r in rules)

        # Strategy: Multi-source retrieval
        # 1. Ontology-aware query (using OntologyBridge)
        # 2. RAG query (using NexusProcessor if available)
        # 3. Combine and deduplicate

        all_chunks = []
        source_ontologies = []

        # Query ontology bridge
        ontology_results = await self._query_ontology(event, mode, limit=10)
        if ontology_results:
            for ontology, chunks in ontology_results.items():
                if chunks:
                    all_chunks.extend(chunks)
                    source_ontologies.append(ontology)

        # Query nexus processor if available
        if self.nexus_processor:
            nexus_results = await self._query_nexus(event, mode, max_tokens)
            if nexus_results:
                all_chunks.extend(nexus_results.get("core", []))
                source_ontologies.append("memory")

        if not all_chunks:
            return None

        # Deduplicate and score
        unique_chunks = self._deduplicate_chunks(all_chunks)
        relevance_score = self._calculate_relevance(unique_chunks, event)
        token_count = self._estimate_tokens(unique_chunks)

        # Truncate to max tokens
        if token_count > max_tokens:
            unique_chunks = self._truncate_to_tokens(unique_chunks, max_tokens)
            token_count = max_tokens

        return InjectedContext(
            trigger_event=event,
            injected_at=datetime.utcnow(),
            chunks=unique_chunks,
            relevance_score=relevance_score,
            token_count=token_count,
            source_ontologies=list(set(source_ontologies)),
        )

    async def _query_ontology(
        self,
        event: TriggerEvent,
        mode: str,
        limit: int,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Query ontology bridge for relevant entities."""
        # Build query based on trigger source data
        query = event.context_query

        # Use ontology bridge mode-aware query
        try:
            results = await self.ontology_bridge.query(query, mode=mode, limit=limit)
            return results
        except Exception as e:
            logger.warning(f"Ontology query failed: {e}")
            return {}

    async def _query_nexus(
        self,
        event: TriggerEvent,
        mode: str,
        token_budget: int,
    ) -> Optional[Dict[str, Any]]:
        """Query nexus processor for RAG results."""
        query = event.context_query

        try:
            results = self.nexus_processor.process(
                query=query,
                mode=mode,
                token_budget=token_budget,
            )
            return results
        except Exception as e:
            logger.warning(f"Nexus query failed: {e}")
            return None

    def _find_matching_rules(self, event: TriggerEvent) -> List[InjectionRule]:
        """Find rules that match this trigger event."""
        matching = []
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            if event.trigger_type in rule.trigger_types:
                matching.append(rule)
        return matching

    def _is_in_cooldown(
        self,
        event: TriggerEvent,
        rules: List[InjectionRule],
    ) -> bool:
        """Check if trigger is in cooldown period."""
        last_injection = self._last_injection_by_type.get(event.trigger_type)
        if not last_injection:
            return False

        min_cooldown = min(r.cooldown_seconds for r in rules)
        elapsed = (datetime.utcnow() - last_injection).total_seconds()
        return elapsed < min_cooldown

    def _deduplicate_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate chunks based on content similarity."""
        # Simple deduplication by chunk ID
        seen_ids = set()
        unique = []
        for chunk in chunks:
            chunk_id = chunk.get("id") or chunk.get("chunk_id") or str(chunk)
            if chunk_id not in seen_ids:
                seen_ids.add(chunk_id)
                unique.append(chunk)
        return unique

    def _calculate_relevance(
        self,
        chunks: List[Dict[str, Any]],
        event: TriggerEvent,
    ) -> float:
        """Calculate relevance score for retrieved chunks.

        When the trigger is probabilistic (carries its own ``confidence`` in
        source_data, e.g. an activity pattern), the detection confidence is
        blended in so a strong signal is not suppressed by middling chunk
        scores. Deterministic triggers (file open, git checkout, time of day)
        have no confidence and use the chunk-score average directly.
        """
        if not chunks:
            return 0.0

        # Average confidence/score from chunks
        scores = []
        for chunk in chunks:
            score = (
                chunk.get("score")
                or chunk.get("confidence")
                or chunk.get("relevance")
                or 0.5
            )
            scores.append(score)
        chunk_relevance = sum(scores) / len(scores) if scores else 0.0

        trigger_confidence = event.source_data.get("confidence")
        if trigger_confidence is None:
            return chunk_relevance
        return (
            self._CHUNK_RELEVANCE_WEIGHT * chunk_relevance
            + (1.0 - self._CHUNK_RELEVANCE_WEIGHT) * trigger_confidence
        )

    def _estimate_tokens(self, chunks: List[Dict[str, Any]]) -> int:
        """Estimate token count for chunks."""
        total_chars = 0
        for chunk in chunks:
            text = chunk.get("text") or chunk.get("content") or ""
            total_chars += len(text)

        # Rough estimate: 4 chars per token
        return total_chars // 4

    def _truncate_to_tokens(
        self,
        chunks: List[Dict[str, Any]],
        max_tokens: int,
    ) -> List[Dict[str, Any]]:
        """Truncate chunks to fit within token budget."""
        truncated = []
        token_count = 0

        for chunk in chunks:
            chunk_tokens = self._estimate_tokens([chunk])
            if token_count + chunk_tokens <= max_tokens:
                truncated.append(chunk)
                token_count += chunk_tokens
            else:
                break

        return truncated

    def _inject_context(self, context: InjectedContext) -> None:
        """Inject context into current session."""
        # Store in injection history
        self._injection_history.append(context)

        # Keep history bounded (last 100 injections)
        if len(self._injection_history) > 100:
            self._injection_history = self._injection_history[-100:]

        logger.info(
            f"Context injected: {len(context.chunks)} chunks "
            f"from {context.source_ontologies}"
        )

    def mark_context_used(self, injection_index: int) -> None:
        """Mark injected context as used by user."""
        if 0 <= injection_index < len(self._injection_history):
            self._injection_history[injection_index].was_used = True
            self.stats.used_count += 1
        else:
            self.stats.unused_count += 1

    def get_stats(self) -> InjectionStats:
        """Get injection statistics."""
        return self.stats

    def get_injection_history(
        self,
        limit: int = 10,
        trigger_type: Optional[TriggerType] = None,
    ) -> List[InjectedContext]:
        """Get recent injection history."""
        history = self._injection_history

        if trigger_type:
            history = [
                ctx for ctx in history if ctx.trigger_event.trigger_type == trigger_type
            ]

        return history[-limit:]

    def add_rule(self, rule: InjectionRule) -> None:
        """Add or update an injection rule."""
        self.rules[rule.rule_id] = rule
        logger.info(f"Added injection rule: {rule.rule_id}")

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an injection rule."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Removed injection rule: {rule_id}")
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """Enable an injection rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable an injection rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            return True
        return False

    def list_rules(self) -> List[InjectionRule]:
        """List all injection rules."""
        return list(self.rules.values())


# Singleton instance
_injector_instance: Optional[ProactiveContextInjector] = None


def get_proactive_injector(
    ontology_bridge: Optional[OntologyBridge] = None,
    nexus_processor: Optional[Any] = None,
) -> ProactiveContextInjector:
    """Get singleton proactive injector instance."""
    global _injector_instance
    if _injector_instance is None:
        if not ontology_bridge:
            raise ValueError("ontology_bridge required for first initialization")
        _injector_instance = ProactiveContextInjector(
            ontology_bridge=ontology_bridge,
            nexus_processor=nexus_processor,
        )
    return _injector_instance
