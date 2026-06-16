"""
Loop Interfaces - Storage interfaces for cognitive loops.

ORG-003: Create Loop 1.5 storage interface.

Loop 1.5 (Session Reflection) stores:
- Corrections: confidence 0.90
- Rules: confidence 0.90
- Approvals: confidence 0.75
- Observations: confidence 0.55

Storage namespace: expertise:{domain}:{topic}

Purpose:
- Store session learnings in Memory MCP
- Support Loop 3 query interface for meta-optimization
- Enable cross-session learning aggregation

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from loguru import logger


class SignalType(Enum):
    """Types of learning signals from Loop 1.5."""
    CORRECTION = "correction"  # User corrected Claude's output
    RULE = "rule"  # User stated explicit rule
    APPROVAL = "approval"  # User approved output
    OBSERVATION = "observation"  # Pattern observed


# Default confidence by signal type
SIGNAL_CONFIDENCE: Dict[SignalType, float] = {
    SignalType.CORRECTION: 0.90,
    SignalType.RULE: 0.90,
    SignalType.APPROVAL: 0.75,
    SignalType.OBSERVATION: 0.55,
}


@dataclass
class LearningSignal:
    """A learning signal from session reflection."""
    signal_type: SignalType
    domain: str
    topic: str
    content: str
    confidence: float
    session_id: str
    source_context: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signal_type": self.signal_type.value,
            "domain": self.domain,
            "topic": self.topic,
            "content": self.content,
            "confidence": self.confidence,
            "session_id": self.session_id,
            "source_context": self.source_context,
            "created_at": self.created_at
        }

    def to_namespace_key(self) -> str:
        """Generate namespace key for storage."""
        return f"expertise:{self.domain}:{self.topic}"


@dataclass
class Loop15StorageResult:
    """Result of Loop 1.5 storage operation."""
    success: bool
    signal_id: str
    namespace_key: str
    message: str
    stored_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class Loop15StorageInterface:
    """
    Storage interface for Loop 1.5 Session Reflection.

    Stores learning signals from session corrections and patterns
    in the expertise namespace for later retrieval by Loop 3.

    Signal Types:
    - Corrections (0.90): User fixed Claude's output
    - Rules (0.90): User stated explicit rules
    - Approvals (0.75): User approved patterns
    - Observations (0.55): Claude observed patterns

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    def __init__(self, namespace_router: Optional[Any] = None):
        """
        Initialize Loop 1.5 storage interface.

        Args:
            namespace_router: NamespaceRouter instance for storage

        NASA Rule 10: 12 LOC (<=60)
        """
        self.namespace_router = namespace_router
        self.pending_signals: List[LearningSignal] = []
        self.stored_count = 0

        logger.info("Loop15StorageInterface initialized")

    def store_correction(
        self,
        domain: str,
        topic: str,
        content: str,
        session_id: str,
        source_context: Optional[str] = None
    ) -> Loop15StorageResult:
        """
        Store a correction signal (confidence 0.90).

        Args:
            domain: Domain category (e.g., "coding", "communication")
            topic: Specific topic (e.g., "python_style", "email_tone")
            content: The correction content
            session_id: Current session identifier
            source_context: Optional source context

        Returns:
            Storage result

        NASA Rule 10: 20 LOC (<=60)
        """
        signal = LearningSignal(
            signal_type=SignalType.CORRECTION,
            domain=domain,
            topic=topic,
            content=content,
            confidence=SIGNAL_CONFIDENCE[SignalType.CORRECTION],
            session_id=session_id,
            source_context=source_context
        )

        return self._store_signal(signal)

    def store_rule(
        self,
        domain: str,
        topic: str,
        content: str,
        session_id: str,
        source_context: Optional[str] = None
    ) -> Loop15StorageResult:
        """
        Store an explicit rule signal (confidence 0.90).

        NASA Rule 10: 18 LOC (<=60)
        """
        signal = LearningSignal(
            signal_type=SignalType.RULE,
            domain=domain,
            topic=topic,
            content=content,
            confidence=SIGNAL_CONFIDENCE[SignalType.RULE],
            session_id=session_id,
            source_context=source_context
        )

        return self._store_signal(signal)

    def store_approval(
        self,
        domain: str,
        topic: str,
        content: str,
        session_id: str,
        source_context: Optional[str] = None
    ) -> Loop15StorageResult:
        """
        Store an approval signal (confidence 0.75).

        NASA Rule 10: 18 LOC (<=60)
        """
        signal = LearningSignal(
            signal_type=SignalType.APPROVAL,
            domain=domain,
            topic=topic,
            content=content,
            confidence=SIGNAL_CONFIDENCE[SignalType.APPROVAL],
            session_id=session_id,
            source_context=source_context
        )

        return self._store_signal(signal)

    def store_observation(
        self,
        domain: str,
        topic: str,
        content: str,
        session_id: str,
        source_context: Optional[str] = None
    ) -> Loop15StorageResult:
        """
        Store an observation signal (confidence 0.55).

        NASA Rule 10: 18 LOC (<=60)
        """
        signal = LearningSignal(
            signal_type=SignalType.OBSERVATION,
            domain=domain,
            topic=topic,
            content=content,
            confidence=SIGNAL_CONFIDENCE[SignalType.OBSERVATION],
            session_id=session_id,
            source_context=source_context
        )

        return self._store_signal(signal)

    def _store_signal(self, signal: LearningSignal) -> Loop15StorageResult:
        """
        Store a learning signal via namespace router.

        NASA Rule 10: 35 LOC (<=60)
        """
        import hashlib

        # Generate signal ID
        signal_hash = hashlib.md5(
            f"{signal.session_id}:{signal.domain}:{signal.topic}:{signal.created_at}".encode()
        ).hexdigest()[:12]
        signal_id = f"L15-{signal_hash}"

        namespace_key = signal.to_namespace_key()

        # Store via namespace router if available
        if self.namespace_router:
            try:
                success = self.namespace_router.store_expertise(
                    domain=signal.domain,
                    topic=signal.topic,
                    expertise_data={
                        "signal_id": signal_id,
                        **signal.to_dict()
                    }
                )
            except Exception as e:
                logger.error(f"Failed to store signal: {e}")
                success = False
        else:
            # Queue for later storage
            self.pending_signals.append(signal)
            success = True

        if success:
            self.stored_count += 1
            logger.info(f"Stored {signal.signal_type.value} signal: {signal_id}")

        return Loop15StorageResult(
            success=success,
            signal_id=signal_id,
            namespace_key=namespace_key,
            message=f"Stored {signal.signal_type.value} with confidence {signal.confidence}"
        )

    def flush_pending(self) -> int:
        """
        Flush pending signals to storage.

        Returns:
            Number of signals flushed

        NASA Rule 10: 18 LOC (<=60)
        """
        if not self.namespace_router or not self.pending_signals:
            return 0

        flushed = 0
        for signal in self.pending_signals:
            result = self._store_signal(signal)
            if result.success:
                flushed += 1

        self.pending_signals = []
        logger.info(f"Flushed {flushed} pending signals")
        return flushed

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.

        NASA Rule 10: 15 LOC (<=60)
        """
        return {
            "stored_count": self.stored_count,
            "pending_count": len(self.pending_signals),
            "signal_confidences": {
                st.value: conf for st, conf in SIGNAL_CONFIDENCE.items()
            }
        }


class Loop3QueryInterface:
    """
    Query interface for Loop 3 Meta-Optimization.

    Retrieves aggregated learnings from Loop 1.5 for
    meta-optimization cycles (every 3 days).

    NASA Rule 10 Compliant: All methods <=60 LOC
    """

    def __init__(self, namespace_router: Optional[Any] = None):
        """
        Initialize Loop 3 query interface.

        NASA Rule 10: 8 LOC (<=60)
        """
        self.namespace_router = namespace_router
        logger.info("Loop3QueryInterface initialized")

    def query_learnings(
        self,
        domain: Optional[str] = None,
        min_confidence: float = 0.5,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query learnings for meta-optimization.

        Args:
            domain: Optional domain filter
            min_confidence: Minimum confidence threshold
            limit: Maximum results

        Returns:
            List of learning entries

        NASA Rule 10: 30 LOC (<=60)
        """
        if not self.namespace_router:
            logger.warning("No namespace router configured")
            return []

        try:
            from ..telemetry.namespace_router import TelemetryNamespace

            # Build prefix filter
            prefix = domain if domain else ""

            # List expertise keys
            keys = self.namespace_router.list_by_namespace(
                TelemetryNamespace.EXPERTISE,
                prefix_filter=prefix
            )

            # Retrieve and filter
            results = []
            for key in keys[:limit * 2]:  # Over-fetch for filtering
                data = self.namespace_router.retrieve(key)
                if data and data.get("confidence", 0) >= min_confidence:
                    results.append(data)
                    if len(results) >= limit:
                        break

            logger.info(f"Retrieved {len(results)} learnings for Loop 3")
            return results

        except Exception as e:
            logger.error(f"Failed to query learnings: {e}")
            return []

    def aggregate_by_domain(
        self,
        learnings: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Aggregate learnings by domain for analysis.

        NASA Rule 10: 18 LOC (<=60)
        """
        aggregated: Dict[str, List[Dict[str, Any]]] = {}

        for learning in learnings:
            domain = learning.get("domain", "unknown")
            if domain not in aggregated:
                aggregated[domain] = []
            aggregated[domain].append(learning)

        logger.debug(f"Aggregated learnings into {len(aggregated)} domains")
        return aggregated

    def extract_globalmoo_5d(
        self,
        learnings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        ORG-004: Extract GlobalMOO 5D parameters for meta-optimization.

        5 Dimensions:
        1. evidential_frame: Weight for evidential reasoning (0-1)
        2. aspectual_frame: Weight for aspectual reasoning (0-1)
        3. verix_strictness: VERIX notation strictness (0-1)
        4. compression_level: Output compression (0-2)
        5. require_ground: Require grounding for claims (bool->float)

        Returns:
            Dict with 5D parameter estimates based on learnings

        NASA Rule 10: 40 LOC (<=60)
        """
        if not learnings:
            return self._default_5d_params()

        # Aggregate signals by type
        corrections = [l for l in learnings if l.get("signal_type") == "correction"]
        rules = [l for l in learnings if l.get("signal_type") == "rule"]
        approvals = [l for l in learnings if l.get("signal_type") == "approval"]

        # Estimate parameters from signal patterns
        correction_rate = len(corrections) / len(learnings) if learnings else 0
        rule_strictness = len(rules) / len(learnings) if learnings else 0

        params = {
            "evidential_frame": min(0.95, 0.7 + correction_rate * 0.25),
            "aspectual_frame": 0.8 if rule_strictness > 0.3 else 0.6,
            "verix_strictness": min(0.9, 0.5 + rule_strictness * 0.4),
            "compression_level": 1 if len(approvals) > len(corrections) else 2,
            "require_ground": 1.0 if correction_rate > 0.2 else 0.5,
            "_meta": {
                "total_learnings": len(learnings),
                "correction_rate": correction_rate,
                "rule_strictness": rule_strictness
            }
        }

        logger.info(f"Extracted GlobalMOO 5D params: {params}")
        return params

    def extract_pymoo_14d(
        self,
        learnings: List[Dict[str, Any]],
        current_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        ORG-004: Extract PyMOO 14D parameters for fine-tuning.

        14 Dimensions (VERILINGUA + VERIX + Mode):
        - 7 frame weights (evidential, aspectual, morphological, etc.)
        - 4 VERIX params (strictness, confidence_ceiling, etc.)
        - 3 mode params (execution, planning, brainstorm weights)

        Returns:
            Dict with 14D parameter estimates

        NASA Rule 10: 55 LOC (<=60)
        """
        base_5d = self.extract_globalmoo_5d(learnings)

        # Default 14D config
        params = {
            # VERILINGUA 7 frames
            "frame_evidential": base_5d.get("evidential_frame", 0.95),
            "frame_aspectual": base_5d.get("aspectual_frame", 0.80),
            "frame_morphological": 0.65,
            "frame_compositional": 0.60,
            "frame_honorific": 0.35,
            "frame_classifier": 0.45,
            "frame_spatial": 0.40,
            # VERIX 4 params
            "verix_strictness": base_5d.get("verix_strictness", 0.7),
            "verix_confidence_ceiling": 0.95,
            "verix_require_ground": base_5d.get("require_ground", 0.5),
            "verix_compression": base_5d.get("compression_level", 1),
            # Mode 3 params
            "mode_execution_weight": 0.8,
            "mode_planning_weight": 0.5,
            "mode_brainstorm_weight": 0.2,
        }

        # Apply current config overrides
        if current_config:
            for key in params:
                if key in current_config:
                    params[key] = current_config[key]

        # Add metadata
        params["_meta"] = {
            "source": "loop3_extraction",
            "learnings_count": len(learnings),
            "extracted_at": datetime.utcnow().isoformat()
        }

        logger.info("Extracted PyMOO 14D params")
        return params

    def _default_5d_params(self) -> Dict[str, Any]:
        """Return default 5D parameters."""
        return {
            "evidential_frame": 0.95,
            "aspectual_frame": 0.80,
            "verix_strictness": 0.70,
            "compression_level": 1,
            "require_ground": 0.5,
            "_meta": {"total_learnings": 0}
        }

    def prepare_optimization_input(
        self,
        days_back: int = 3
    ) -> Dict[str, Any]:
        """
        ORG-004: Prepare input for meta-optimization cycle.

        Aggregates learnings from the past N days and extracts
        both 5D and 14D parameters.

        Args:
            days_back: Number of days to look back

        Returns:
            Dict with 5D params, 14D params, and raw learnings

        NASA Rule 10: 25 LOC (<=60)
        """
        learnings = self.query_learnings(limit=500)

        # Filter by date if timestamp available
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        recent_learnings = []
        for l in learnings:
            created = l.get("created_at")
            if created:
                try:
                    if datetime.fromisoformat(created.replace("Z", "")) >= cutoff:
                        recent_learnings.append(l)
                except (ValueError, TypeError):
                    recent_learnings.append(l)
            else:
                recent_learnings.append(l)

        return {
            "globalmoo_5d": self.extract_globalmoo_5d(recent_learnings),
            "pymoo_14d": self.extract_pymoo_14d(recent_learnings),
            "learnings": recent_learnings,
            "aggregated": self.aggregate_by_domain(recent_learnings),
            "days_back": days_back
        }
