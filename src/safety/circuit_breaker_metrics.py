"""
Circuit Breaker Metrics - Observability for circuit breaker state
Part of META-005: Apoptosis/Quarantine (Circuit Breakers)

Provides metrics export, state tracking, and coordination across services.
Supports Prometheus-compatible metrics format.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Standard circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerSnapshot:
    """Point-in-time snapshot of a circuit breaker"""

    name: str
    service: str
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: Optional[datetime]
    last_success_time: Optional[datetime]
    last_state_change: datetime
    open_duration_seconds: float
    trip_count: int
    recovery_count: int
    current_backoff_seconds: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "service": self.service,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat()
            if self.last_failure_time
            else None,
            "last_success_time": self.last_success_time.isoformat()
            if self.last_success_time
            else None,
            "last_state_change": self.last_state_change.isoformat(),
            "open_duration_seconds": round(self.open_duration_seconds, 3),
            "trip_count": self.trip_count,
            "recovery_count": self.recovery_count,
            "current_backoff_seconds": round(self.current_backoff_seconds, 3),
            "metadata": self.metadata,
        }


@dataclass
class CircuitBreakerEvent:
    """Event from a circuit breaker state change"""

    timestamp: datetime
    breaker_name: str
    service: str
    event_type: str  # "trip", "recover", "test", "state_change"
    old_state: Optional[CircuitState]
    new_state: CircuitState
    reason: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "breaker_name": self.breaker_name,
            "service": self.service,
            "event_type": self.event_type,
            "old_state": self.old_state.value if self.old_state else None,
            "new_state": self.new_state.value,
            "reason": self.reason,
            "metadata": self.metadata,
        }


class CircuitBreakerRegistry:
    """
    Central registry for circuit breaker state and metrics.

    Features:
    1. State registration from multiple services
    2. Prometheus-compatible metrics export
    3. Event history and auditing
    4. Cross-service coordination
    """

    # Prometheus metric names
    METRIC_STATE = "circuit_breaker_state"
    METRIC_TRIPS_TOTAL = "circuit_breaker_trips_total"
    METRIC_RECOVERIES_TOTAL = "circuit_breaker_recoveries_total"
    METRIC_OPEN_DURATION = "circuit_breaker_open_duration_seconds"
    METRIC_FAILURES = "circuit_breaker_failures_total"
    METRIC_SUCCESSES = "circuit_breaker_successes_total"

    def __init__(self, max_events: int = 10000):
        self._breakers: Dict[str, CircuitBreakerSnapshot] = {}
        self._events: List[CircuitBreakerEvent] = []
        self._max_events = max_events
        self._callbacks: List[Callable[[CircuitBreakerEvent], None]] = []
        self._lock = asyncio.Lock()

    def register_callback(
        self, callback: Callable[[CircuitBreakerEvent], None]
    ) -> None:
        """Register a callback for circuit breaker events"""
        self._callbacks.append(callback)

    async def register_breaker(
        self,
        name: str,
        service: str,
        state: CircuitState = CircuitState.CLOSED,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a new circuit breaker"""
        async with self._lock:
            key = f"{service}:{name}"
            now = datetime.utcnow()

            snapshot = CircuitBreakerSnapshot(
                name=name,
                service=service,
                state=state,
                failure_count=0,
                success_count=0,
                last_failure_time=None,
                last_success_time=None,
                last_state_change=now,
                open_duration_seconds=0.0,
                trip_count=0,
                recovery_count=0,
                current_backoff_seconds=0.0,
                metadata=metadata or {},
            )

            self._breakers[key] = snapshot
            logger.info(f"Registered circuit breaker: {key}")

    async def update_state(
        self,
        name: str,
        service: str,
        new_state: CircuitState,
        reason: Optional[str] = None,
        backoff_seconds: float = 0.0,
    ) -> None:
        """Update circuit breaker state"""
        async with self._lock:
            key = f"{service}:{name}"
            breaker = self._breakers.get(key)

            if not breaker:
                # Auto-register if not exists
                await self.register_breaker(name, service, new_state)
                breaker = self._breakers[key]

            old_state = breaker.state
            now = datetime.utcnow()

            # Calculate open duration if transitioning from OPEN
            if old_state == CircuitState.OPEN and new_state != CircuitState.OPEN:
                breaker.open_duration_seconds += (
                    now - breaker.last_state_change
                ).total_seconds()

            # Update state
            breaker.state = new_state
            breaker.last_state_change = now
            breaker.current_backoff_seconds = backoff_seconds

            # Track trips and recoveries
            if old_state != CircuitState.OPEN and new_state == CircuitState.OPEN:
                breaker.trip_count += 1
                event_type = "trip"
            elif old_state == CircuitState.OPEN and new_state == CircuitState.CLOSED:
                breaker.recovery_count += 1
                event_type = "recover"
            elif old_state != new_state:
                event_type = "state_change"
            else:
                return  # No change

            # Record event
            event = CircuitBreakerEvent(
                timestamp=now,
                breaker_name=name,
                service=service,
                event_type=event_type,
                old_state=old_state,
                new_state=new_state,
                reason=reason,
            )

            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events :]

            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

            logger.info(
                f"Circuit breaker {key}: {old_state.value} -> {new_state.value} "
                f"(reason={reason})"
            )

    async def record_failure(self, name: str, service: str) -> None:
        """Record a failure for a circuit breaker"""
        async with self._lock:
            key = f"{service}:{name}"
            breaker = self._breakers.get(key)

            if breaker:
                breaker.failure_count += 1
                breaker.last_failure_time = datetime.utcnow()

    async def record_success(self, name: str, service: str) -> None:
        """Record a success for a circuit breaker"""
        async with self._lock:
            key = f"{service}:{name}"
            breaker = self._breakers.get(key)

            if breaker:
                breaker.success_count += 1
                breaker.last_success_time = datetime.utcnow()

    def get_breaker(self, name: str, service: str) -> Optional[CircuitBreakerSnapshot]:
        """Get a specific circuit breaker snapshot"""
        key = f"{service}:{name}"
        return self._breakers.get(key)

    def get_all_breakers(
        self, service: Optional[str] = None, state: Optional[CircuitState] = None
    ) -> List[CircuitBreakerSnapshot]:
        """Get all circuit breakers with optional filters"""
        breakers = list(self._breakers.values())

        if service:
            breakers = [b for b in breakers if b.service == service]
        if state:
            breakers = [b for b in breakers if b.state == state]

        return breakers

    def get_events(
        self,
        service: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[CircuitBreakerEvent]:
        """Get recent events with optional filters"""
        events = self._events.copy()

        if service:
            events = [e for e in events if e.service == service]
        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:]

    def export_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus text format.

        Returns metrics string for Prometheus scraping.
        """
        lines = []

        # Circuit breaker state (0=closed, 1=half_open, 2=open)
        lines.append(
            f"# HELP {self.METRIC_STATE} Current state of circuit breaker (0=closed, 1=half_open, 2=open)"
        )
        lines.append(f"# TYPE {self.METRIC_STATE} gauge")
        for breaker in self._breakers.values():
            state_value = {"closed": 0, "half_open": 1, "open": 2}[breaker.state.value]
            lines.append(
                f'{self.METRIC_STATE}{{name="{breaker.name}",service="{breaker.service}"}} {state_value}'
            )

        # Trip count
        lines.append(
            f"# HELP {self.METRIC_TRIPS_TOTAL} Total number of times circuit breaker tripped"
        )
        lines.append(f"# TYPE {self.METRIC_TRIPS_TOTAL} counter")
        for breaker in self._breakers.values():
            lines.append(
                f'{self.METRIC_TRIPS_TOTAL}{{name="{breaker.name}",service="{breaker.service}"}} {breaker.trip_count}'
            )

        # Recovery count
        lines.append(
            f"# HELP {self.METRIC_RECOVERIES_TOTAL} Total number of circuit breaker recoveries"
        )
        lines.append(f"# TYPE {self.METRIC_RECOVERIES_TOTAL} counter")
        for breaker in self._breakers.values():
            lines.append(
                f'{self.METRIC_RECOVERIES_TOTAL}{{name="{breaker.name}",service="{breaker.service}"}} {breaker.recovery_count}'
            )

        # Open duration
        lines.append(
            f"# HELP {self.METRIC_OPEN_DURATION} Total time circuit breaker spent in open state"
        )
        lines.append(f"# TYPE {self.METRIC_OPEN_DURATION} counter")
        for breaker in self._breakers.values():
            duration = breaker.open_duration_seconds
            # Add current open duration if currently open
            if breaker.state == CircuitState.OPEN:
                duration += (
                    datetime.utcnow() - breaker.last_state_change
                ).total_seconds()
            lines.append(
                f'{self.METRIC_OPEN_DURATION}{{name="{breaker.name}",service="{breaker.service}"}} {duration:.3f}'
            )

        # Failure count
        lines.append(f"# HELP {self.METRIC_FAILURES} Total number of failures")
        lines.append(f"# TYPE {self.METRIC_FAILURES} counter")
        for breaker in self._breakers.values():
            lines.append(
                f'{self.METRIC_FAILURES}{{name="{breaker.name}",service="{breaker.service}"}} {breaker.failure_count}'
            )

        # Success count
        lines.append(f"# HELP {self.METRIC_SUCCESSES} Total number of successes")
        lines.append(f"# TYPE {self.METRIC_SUCCESSES} counter")
        for breaker in self._breakers.values():
            lines.append(
                f'{self.METRIC_SUCCESSES}{{name="{breaker.name}",service="{breaker.service}"}} {breaker.success_count}'
            )

        return "\n".join(lines) + "\n"

    def export_json_metrics(self) -> Dict[str, Any]:
        """Export metrics as JSON for dashboard consumption"""
        breakers_by_state = {"closed": 0, "half_open": 0, "open": 0}

        for breaker in self._breakers.values():
            breakers_by_state[breaker.state.value] += 1

        total_trips = sum(b.trip_count for b in self._breakers.values())
        total_recoveries = sum(b.recovery_count for b in self._breakers.values())
        total_open_duration = sum(
            b.open_duration_seconds for b in self._breakers.values()
        )

        return {
            "summary": {
                "total_breakers": len(self._breakers),
                "by_state": breakers_by_state,
                "total_trips": total_trips,
                "total_recoveries": total_recoveries,
                "total_open_duration_seconds": round(total_open_duration, 3),
                "total_events": len(self._events),
            },
            "breakers": [b.to_dict() for b in self._breakers.values()],
            "recent_events": [e.to_dict() for e in self._events[-20:]],
        }

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status based on circuit breakers"""
        breakers = list(self._breakers.values())

        if not breakers:
            return {"status": "unknown", "message": "No circuit breakers registered"}

        open_breakers = [b for b in breakers if b.state == CircuitState.OPEN]
        half_open_breakers = [b for b in breakers if b.state == CircuitState.HALF_OPEN]

        if len(open_breakers) > len(breakers) * 0.5:
            status = "critical"
            message = f"{len(open_breakers)}/{len(breakers)} circuit breakers open"
        elif open_breakers:
            status = "degraded"
            message = f"{len(open_breakers)} circuit breaker(s) open"
        elif half_open_breakers:
            status = "recovering"
            message = f"{len(half_open_breakers)} circuit breaker(s) testing recovery"
        else:
            status = "healthy"
            message = "All circuit breakers closed"

        return {
            "status": status,
            "message": message,
            "open_breakers": [b.name for b in open_breakers],
            "half_open_breakers": [b.name for b in half_open_breakers],
        }


# Singleton instance
_registry_instance: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry(max_events: int = 10000) -> CircuitBreakerRegistry:
    """Get singleton circuit breaker registry"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = CircuitBreakerRegistry(max_events)
    return _registry_instance
