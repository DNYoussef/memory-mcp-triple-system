"""
Drift Detector - Detect concept drift in memory over time
Part of META-004: Waste System (Memory Compaction)

Detects when stored memories have drifted from current context,
enabling targeted cleanup of stale or outdated information.
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DriftSeverity(str, Enum):
    """Severity levels for detected drift"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DriftSignal:
    """A detected drift signal in memory"""
    chunk_id: str
    drift_score: float
    severity: DriftSeverity
    drift_type: str
    detected_at: datetime
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "drift_score": self.drift_score,
            "severity": self.severity.value,
            "drift_type": self.drift_type,
            "detected_at": self.detected_at.isoformat(),
            "context": self.context
        }


@dataclass
class DriftReport:
    """Summary report of drift detection run"""
    run_id: str
    started_at: datetime
    completed_at: datetime
    chunks_analyzed: int
    signals_detected: int
    by_severity: Dict[str, int]
    by_type: Dict[str, int]
    signals: List[DriftSignal]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "chunks_analyzed": self.chunks_analyzed,
            "signals_detected": self.signals_detected,
            "by_severity": self.by_severity,
            "by_type": self.by_type,
            "signals": [s.to_dict() for s in self.signals]
        }


class DriftDetector:
    """
    Detects concept drift in memory chunks over time.

    Drift Types Detected:
    1. Temporal Drift - Memory too old relative to access patterns
    2. Semantic Drift - Embedding space has shifted
    3. Relevance Drift - Low retrieval frequency indicates staleness
    4. Confidence Drift - Confidence degraded below threshold
    5. Project Drift - Memory no longer aligns with project context
    """

    # Thresholds for drift detection
    TEMPORAL_DRIFT_DAYS = 30
    SEMANTIC_DRIFT_THRESHOLD = 0.3
    RELEVANCE_MIN_ACCESSES = 2
    RELEVANCE_WINDOW_DAYS = 14
    CONFIDENCE_DRIFT_THRESHOLD = 0.4

    # Severity thresholds
    SEVERITY_THRESHOLDS = {
        DriftSeverity.LOW: 0.3,
        DriftSeverity.MEDIUM: 0.5,
        DriftSeverity.HIGH: 0.7,
        DriftSeverity.CRITICAL: 0.9
    }

    def __init__(
        self,
        temporal_days: int = 30,
        semantic_threshold: float = 0.3,
        confidence_threshold: float = 0.4
    ):
        self.temporal_days = temporal_days
        self.semantic_threshold = semantic_threshold
        self.confidence_threshold = confidence_threshold
        self._baseline_embeddings: Dict[str, np.ndarray] = {}
        self._access_log: Dict[str, List[datetime]] = {}
        self._run_counter = 0

    def detect_temporal_drift(
        self,
        chunk_id: str,
        created_at: datetime,
        last_accessed: Optional[datetime] = None
    ) -> Optional[DriftSignal]:
        """
        Detect if a chunk is temporally stale.

        Criteria:
        - Age > threshold AND not recently accessed
        - Last access > threshold AND low total accesses
        """
        now = datetime.utcnow()
        age_days = (now - created_at).days

        if last_accessed:
            days_since_access = (now - last_accessed).days
        else:
            days_since_access = age_days

        # Calculate drift score based on age and access patterns
        age_factor = min(1.0, age_days / (self.temporal_days * 2))
        access_factor = min(1.0, days_since_access / self.temporal_days)
        drift_score = (age_factor * 0.4) + (access_factor * 0.6)

        if drift_score > self.SEVERITY_THRESHOLDS[DriftSeverity.LOW]:
            return DriftSignal(
                chunk_id=chunk_id,
                drift_score=drift_score,
                severity=self._score_to_severity(drift_score),
                drift_type="temporal",
                detected_at=now,
                context={
                    "age_days": age_days,
                    "days_since_access": days_since_access,
                    "threshold_days": self.temporal_days
                }
            )
        return None

    def detect_semantic_drift(
        self,
        chunk_id: str,
        current_embedding: np.ndarray,
        baseline_embedding: Optional[np.ndarray] = None
    ) -> Optional[DriftSignal]:
        """
        Detect if chunk embedding has drifted from baseline.

        Uses cosine distance to measure semantic shift.
        """
        if baseline_embedding is None:
            baseline_embedding = self._baseline_embeddings.get(chunk_id)

        if baseline_embedding is None:
            # Store as new baseline
            self._baseline_embeddings[chunk_id] = current_embedding.copy()
            return None

        # Calculate cosine distance
        similarity = self._cosine_similarity(current_embedding, baseline_embedding)
        drift_score = 1.0 - similarity

        if drift_score > self.semantic_threshold:
            return DriftSignal(
                chunk_id=chunk_id,
                drift_score=drift_score,
                severity=self._score_to_severity(drift_score),
                drift_type="semantic",
                detected_at=datetime.utcnow(),
                context={
                    "cosine_similarity": float(similarity),
                    "threshold": self.semantic_threshold
                }
            )
        return None

    def detect_relevance_drift(
        self,
        chunk_id: str,
        access_count: int,
        window_days: int = 14
    ) -> Optional[DriftSignal]:
        """
        Detect if chunk has low retrieval relevance.

        Chunks that are rarely accessed may be candidates for archival.
        """
        # Check access log for this chunk
        accesses = self._access_log.get(chunk_id, [])
        now = datetime.utcnow()
        cutoff = now - timedelta(days=window_days)

        recent_accesses = [a for a in accesses if a > cutoff]
        total_recent = len(recent_accesses) + access_count

        if total_recent < self.RELEVANCE_MIN_ACCESSES:
            drift_score = 1.0 - (total_recent / self.RELEVANCE_MIN_ACCESSES)

            if drift_score > self.SEVERITY_THRESHOLDS[DriftSeverity.LOW]:
                return DriftSignal(
                    chunk_id=chunk_id,
                    drift_score=drift_score,
                    severity=self._score_to_severity(drift_score),
                    drift_type="relevance",
                    detected_at=now,
                    context={
                        "recent_accesses": total_recent,
                        "min_required": self.RELEVANCE_MIN_ACCESSES,
                        "window_days": window_days
                    }
                )
        return None

    def detect_confidence_drift(
        self,
        chunk_id: str,
        current_confidence: float,
        original_confidence: Optional[float] = None
    ) -> Optional[DriftSignal]:
        """
        Detect if confidence has degraded below threshold.

        Confidence may degrade due to:
        - Conflicting information added
        - Source deprecation
        - Time-based decay
        """
        if current_confidence < self.confidence_threshold:
            drift_score = 1.0 - (current_confidence / self.confidence_threshold)

            context = {
                "current_confidence": current_confidence,
                "threshold": self.confidence_threshold
            }

            if original_confidence:
                context["original_confidence"] = original_confidence
                context["confidence_delta"] = original_confidence - current_confidence

            return DriftSignal(
                chunk_id=chunk_id,
                drift_score=min(1.0, drift_score),
                severity=self._score_to_severity(drift_score),
                drift_type="confidence",
                detected_at=datetime.utcnow(),
                context=context
            )
        return None

    def detect_project_drift(
        self,
        chunk_id: str,
        chunk_project: str,
        active_projects: List[str]
    ) -> Optional[DriftSignal]:
        """
        Detect if chunk belongs to inactive/archived project.

        Memory from inactive projects may be candidates for archival.
        """
        if chunk_project and chunk_project not in active_projects:
            # Project is not in active list
            drift_score = 0.7  # Moderate score for project drift

            return DriftSignal(
                chunk_id=chunk_id,
                drift_score=drift_score,
                severity=DriftSeverity.MEDIUM,
                drift_type="project",
                detected_at=datetime.utcnow(),
                context={
                    "chunk_project": chunk_project,
                    "active_projects": active_projects,
                    "reason": "project_inactive"
                }
            )
        return None

    def analyze_chunk(
        self,
        chunk_id: str,
        created_at: datetime,
        last_accessed: Optional[datetime],
        embedding: Optional[np.ndarray],
        confidence: float,
        access_count: int,
        project: Optional[str],
        active_projects: List[str]
    ) -> List[DriftSignal]:
        """
        Run all drift detectors on a single chunk.

        Returns list of detected drift signals.
        """
        signals = []

        # Temporal drift
        signal = self.detect_temporal_drift(chunk_id, created_at, last_accessed)
        if signal:
            signals.append(signal)

        # Semantic drift (if embedding provided)
        if embedding is not None:
            signal = self.detect_semantic_drift(chunk_id, embedding)
            if signal:
                signals.append(signal)

        # Relevance drift
        signal = self.detect_relevance_drift(chunk_id, access_count)
        if signal:
            signals.append(signal)

        # Confidence drift
        signal = self.detect_confidence_drift(chunk_id, confidence)
        if signal:
            signals.append(signal)

        # Project drift
        if project:
            signal = self.detect_project_drift(chunk_id, project, active_projects)
            if signal:
                signals.append(signal)

        return signals

    def run_detection(
        self,
        chunks: List[Dict[str, Any]],
        active_projects: List[str]
    ) -> DriftReport:
        """
        Run drift detection on a batch of chunks.

        Args:
            chunks: List of chunk dicts with keys:
                - id, created_at, last_accessed, embedding,
                - confidence, access_count, project
            active_projects: List of currently active project names

        Returns:
            DriftReport with all detected signals
        """
        self._run_counter += 1
        run_id = f"drift-{self._run_counter}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        started_at = datetime.utcnow()

        all_signals = []
        by_severity = {s.value: 0 for s in DriftSeverity}
        by_type = {}

        for chunk in chunks:
            try:
                signals = self.analyze_chunk(
                    chunk_id=chunk.get("id", "unknown"),
                    created_at=chunk.get("created_at", datetime.utcnow()),
                    last_accessed=chunk.get("last_accessed"),
                    embedding=chunk.get("embedding"),
                    confidence=chunk.get("confidence", 0.5),
                    access_count=chunk.get("access_count", 0),
                    project=chunk.get("project"),
                    active_projects=active_projects
                )

                for signal in signals:
                    all_signals.append(signal)
                    by_severity[signal.severity.value] += 1
                    by_type[signal.drift_type] = by_type.get(signal.drift_type, 0) + 1

            except Exception as e:
                logger.error(f"Error analyzing chunk {chunk.get('id')}: {e}")

        completed_at = datetime.utcnow()

        report = DriftReport(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            chunks_analyzed=len(chunks),
            signals_detected=len(all_signals),
            by_severity=by_severity,
            by_type=by_type,
            signals=all_signals
        )

        logger.info(
            f"Drift detection complete: {len(chunks)} chunks analyzed, "
            f"{len(all_signals)} signals detected"
        )

        return report

    def record_access(self, chunk_id: str) -> None:
        """Record an access to a chunk for relevance tracking"""
        if chunk_id not in self._access_log:
            self._access_log[chunk_id] = []
        self._access_log[chunk_id].append(datetime.utcnow())

        # Keep only recent accesses (last 30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)
        self._access_log[chunk_id] = [
            a for a in self._access_log[chunk_id] if a > cutoff
        ]

    def update_baseline(self, chunk_id: str, embedding: np.ndarray) -> None:
        """Update the baseline embedding for a chunk"""
        self._baseline_embeddings[chunk_id] = embedding.copy()

    def get_candidates_for_cleanup(
        self,
        report: DriftReport,
        min_severity: DriftSeverity = DriftSeverity.MEDIUM
    ) -> List[str]:
        """
        Get chunk IDs that are candidates for cleanup based on drift signals.

        Args:
            report: DriftReport from run_detection
            min_severity: Minimum severity to include

        Returns:
            List of chunk IDs to consider for cleanup
        """
        # NONE must be included: _score_to_severity returns it for any drift
        # below the LOW threshold (e.g. detect_confidence_drift just under the
        # confidence threshold), so signal.severity / min_severity can be NONE.
        # Omitting it made severity_order.index(...) raise ValueError (E11).
        severity_order = [
            DriftSeverity.NONE,
            DriftSeverity.LOW,
            DriftSeverity.MEDIUM,
            DriftSeverity.HIGH,
            DriftSeverity.CRITICAL
        ]
        min_index = severity_order.index(min_severity)

        candidates = set()
        for signal in report.signals:
            signal_index = severity_order.index(signal.severity)
            if signal_index >= min_index:
                candidates.add(signal.chunk_id)

        return list(candidates)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _score_to_severity(self, score: float) -> DriftSeverity:
        """Convert drift score to severity level"""
        if score >= self.SEVERITY_THRESHOLDS[DriftSeverity.CRITICAL]:
            return DriftSeverity.CRITICAL
        elif score >= self.SEVERITY_THRESHOLDS[DriftSeverity.HIGH]:
            return DriftSeverity.HIGH
        elif score >= self.SEVERITY_THRESHOLDS[DriftSeverity.MEDIUM]:
            return DriftSeverity.MEDIUM
        elif score >= self.SEVERITY_THRESHOLDS[DriftSeverity.LOW]:
            return DriftSeverity.LOW
        return DriftSeverity.NONE


# Singleton instance
_detector_instance: Optional[DriftDetector] = None


def get_drift_detector(
    temporal_days: int = 30,
    semantic_threshold: float = 0.3,
    confidence_threshold: float = 0.4
) -> DriftDetector:
    """Get singleton drift detector instance"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = DriftDetector(
            temporal_days=temporal_days,
            semantic_threshold=semantic_threshold,
            confidence_threshold=confidence_threshold
        )
    return _detector_instance
