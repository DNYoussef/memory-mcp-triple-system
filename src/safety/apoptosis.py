"""
Apoptosis Service - Graceful degradation and self-termination
Part of META-005: Apoptosis/Quarantine (Circuit Breakers)

Implements controlled shutdown when a component becomes irreparably broken.
Provides cascade protection and health-based degradation.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class HealthState(str, Enum):
    """Component health states"""
    HEALTHY = "healthy"           # Normal operation
    DEGRADED = "degraded"         # Reduced functionality
    CRITICAL = "critical"         # Imminent failure
    TERMINAL = "terminal"         # Shutting down
    DEAD = "dead"                 # Shutdown complete


class ApoptosisReason(str, Enum):
    """Reasons for triggering apoptosis"""
    HEALTH_DEGRADATION = "health_degradation"
    CIRCUIT_BREAKER_EXHAUSTED = "circuit_breaker_exhausted"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DEPENDENCY_FAILURE = "dependency_failure"
    MANUAL_TRIGGER = "manual_trigger"
    CASCADE_FROM_PARENT = "cascade_from_parent"
    UNRECOVERABLE_ERROR = "unrecoverable_error"
    HEARTBEAT_TIMEOUT = "heartbeat_timeout"


@dataclass
class HealthMetrics:
    """Health metrics for a component"""
    error_rate: float = 0.0           # Errors / total requests
    latency_p95_ms: float = 0.0       # 95th percentile latency
    success_rate: float = 1.0         # Successful requests / total
    circuit_breakers_open: int = 0    # Number of open circuit breakers
    memory_usage_pct: float = 0.0     # Memory usage percentage
    cpu_usage_pct: float = 0.0        # CPU usage percentage
    last_heartbeat: Optional[datetime] = None
    consecutive_failures: int = 0
    uptime_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_rate": round(self.error_rate, 4),
            "latency_p95_ms": round(self.latency_p95_ms, 2),
            "success_rate": round(self.success_rate, 4),
            "circuit_breakers_open": self.circuit_breakers_open,
            "memory_usage_pct": round(self.memory_usage_pct, 2),
            "cpu_usage_pct": round(self.cpu_usage_pct, 2),
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "consecutive_failures": self.consecutive_failures,
            "uptime_seconds": round(self.uptime_seconds, 2)
        }


@dataclass
class ApoptosisConfig:
    """Configuration for apoptosis thresholds"""
    # Health score thresholds (0.0 - 1.0)
    degraded_threshold: float = 0.7
    critical_threshold: float = 0.4
    terminal_threshold: float = 0.2

    # Individual metric thresholds
    max_error_rate: float = 0.3
    max_latency_ms: float = 5000
    max_consecutive_failures: int = 10
    max_circuit_breakers_open: int = 3
    max_memory_pct: float = 90.0
    heartbeat_timeout_seconds: float = 60.0

    # Cascade settings
    enable_cascade: bool = True
    cascade_delay_seconds: float = 5.0

    # Recovery settings
    recovery_check_interval: float = 30.0
    min_recovery_duration: float = 60.0


@dataclass
class ComponentState:
    """State of a registered component"""
    name: str
    state: HealthState
    health_score: float
    metrics: HealthMetrics
    dependencies: List[str]
    dependents: List[str]
    registered_at: datetime
    state_changed_at: datetime
    apoptosis_reason: Optional[ApoptosisReason] = None
    shutdown_callbacks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "health_score": round(self.health_score, 4),
            "metrics": self.metrics.to_dict(),
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "registered_at": self.registered_at.isoformat(),
            "state_changed_at": self.state_changed_at.isoformat(),
            "apoptosis_reason": self.apoptosis_reason.value if self.apoptosis_reason else None
        }


class ApoptosisService:
    """
    Manages graceful degradation and controlled shutdown.

    Features:
    1. Health score calculation from multiple metrics
    2. State transitions (healthy -> degraded -> critical -> terminal -> dead)
    3. Cascade shutdown of dependent components
    4. Recovery detection and state improvement
    5. Shutdown callback orchestration
    """

    def __init__(self, config: Optional[ApoptosisConfig] = None):
        self.config = config or ApoptosisConfig()
        self._components: Dict[str, ComponentState] = {}
        self._shutdown_callbacks: Dict[str, List[Callable[..., Awaitable[None]]]] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._started_at: Optional[datetime] = None
        self._shutting_down = False

    async def start(self) -> None:
        """Start the apoptosis service"""
        self._started_at = datetime.utcnow()
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Apoptosis service started")

    async def stop(self) -> None:
        """Stop the apoptosis service"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Apoptosis service stopped")

    async def register_component(
        self,
        name: str,
        dependencies: Optional[List[str]] = None
    ) -> ComponentState:
        """
        Register a component for health monitoring.

        Args:
            name: Unique component name
            dependencies: List of component names this depends on

        Returns:
            ComponentState for the registered component
        """
        async with self._lock:
            now = datetime.utcnow()
            state = ComponentState(
                name=name,
                state=HealthState.HEALTHY,
                health_score=1.0,
                metrics=HealthMetrics(last_heartbeat=now),
                dependencies=dependencies or [],
                dependents=[],
                registered_at=now,
                state_changed_at=now
            )

            self._components[name] = state

            # Update dependents for dependencies
            for dep_name in state.dependencies:
                if dep_name in self._components:
                    self._components[dep_name].dependents.append(name)

            logger.info(f"Registered component: {name}")
            return state

    def register_shutdown_callback(
        self,
        component_name: str,
        callback: Callable[..., Awaitable[None]]
    ) -> None:
        """Register a callback to run when component shuts down"""
        if component_name not in self._shutdown_callbacks:
            self._shutdown_callbacks[component_name] = []
        self._shutdown_callbacks[component_name].append(callback)

    async def update_metrics(
        self,
        component_name: str,
        metrics: HealthMetrics
    ) -> Optional[HealthState]:
        """
        Update health metrics for a component.

        Returns the new health state if it changed.
        """
        async with self._lock:
            component = self._components.get(component_name)
            if not component:
                return None

            old_state = component.state
            component.metrics = metrics
            component.metrics.last_heartbeat = datetime.utcnow()

            # Calculate health score
            health_score = self._calculate_health_score(metrics)
            component.health_score = health_score

            # Determine state transition
            new_state = self._determine_state(health_score, component)

            if new_state != old_state:
                component.state = new_state
                component.state_changed_at = datetime.utcnow()
                logger.info(
                    f"Component {component_name} state: {old_state.value} -> {new_state.value} "
                    f"(score={health_score:.3f})"
                )

                # Check if apoptosis triggered
                if new_state == HealthState.TERMINAL:
                    await self._initiate_apoptosis(
                        component_name,
                        ApoptosisReason.HEALTH_DEGRADATION
                    )

                return new_state

            return None

    async def heartbeat(self, component_name: str) -> bool:
        """
        Record a heartbeat for a component.

        Returns True if component is healthy enough to continue.
        """
        async with self._lock:
            component = self._components.get(component_name)
            if not component:
                return False

            component.metrics.last_heartbeat = datetime.utcnow()
            component.metrics.consecutive_failures = 0

            if self._started_at:
                component.metrics.uptime_seconds = (
                    datetime.utcnow() - self._started_at
                ).total_seconds()

            return component.state in [HealthState.HEALTHY, HealthState.DEGRADED]

    async def record_failure(self, component_name: str) -> None:
        """Record a failure for a component"""
        async with self._lock:
            component = self._components.get(component_name)
            if not component:
                return

            component.metrics.consecutive_failures += 1

            # Check if consecutive failures exceeded
            if component.metrics.consecutive_failures >= self.config.max_consecutive_failures:
                logger.warning(
                    f"Component {component_name} exceeded max consecutive failures"
                )
                await self._initiate_apoptosis(
                    component_name,
                    ApoptosisReason.UNRECOVERABLE_ERROR
                )

    async def trigger_apoptosis(
        self,
        component_name: str,
        reason: ApoptosisReason = ApoptosisReason.MANUAL_TRIGGER
    ) -> bool:
        """
        Manually trigger apoptosis for a component.

        Returns True if apoptosis was initiated.
        """
        return await self._initiate_apoptosis(component_name, reason)

    async def _initiate_apoptosis(
        self,
        component_name: str,
        reason: ApoptosisReason
    ) -> bool:
        """Internal: initiate apoptosis sequence"""
        component = self._components.get(component_name)
        if not component:
            return False

        if component.state == HealthState.TERMINAL:
            return False  # Already shutting down

        logger.warning(
            f"Initiating apoptosis for {component_name} (reason={reason.value})"
        )

        component.state = HealthState.TERMINAL
        component.apoptosis_reason = reason
        component.state_changed_at = datetime.utcnow()

        # Run shutdown callbacks
        await self._run_shutdown_callbacks(component_name)

        # Cascade to dependents if enabled
        if self.config.enable_cascade and component.dependents:
            await self._cascade_apoptosis(component_name)

        # Mark as dead
        component.state = HealthState.DEAD
        component.state_changed_at = datetime.utcnow()

        return True

    async def _cascade_apoptosis(self, component_name: str) -> None:
        """Cascade apoptosis to dependent components"""
        component = self._components.get(component_name)
        if not component:
            return

        logger.info(
            f"Cascading apoptosis from {component_name} to dependents: "
            f"{component.dependents}"
        )

        # Delay to allow for graceful handling
        await asyncio.sleep(self.config.cascade_delay_seconds)

        for dependent_name in component.dependents:
            await self._initiate_apoptosis(
                dependent_name,
                ApoptosisReason.CASCADE_FROM_PARENT
            )

    async def _run_shutdown_callbacks(self, component_name: str) -> None:
        """Run all shutdown callbacks for a component"""
        callbacks = self._shutdown_callbacks.get(component_name, [])

        for callback in callbacks:
            try:
                await asyncio.wait_for(callback(), timeout=30.0)
            except asyncio.TimeoutError:
                logger.error(f"Shutdown callback timeout for {component_name}")
            except Exception as e:
                logger.error(f"Shutdown callback error for {component_name}: {e}")

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop"""
        while True:
            try:
                await asyncio.sleep(self.config.recovery_check_interval)
                await self._check_heartbeats()
                await self._check_recovery()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")

    async def _check_heartbeats(self) -> None:
        """Check for heartbeat timeouts"""
        now = datetime.utcnow()
        timeout = timedelta(seconds=self.config.heartbeat_timeout_seconds)

        async with self._lock:
            for name, component in self._components.items():
                if component.state in [HealthState.TERMINAL, HealthState.DEAD]:
                    continue

                if component.metrics.last_heartbeat:
                    elapsed = now - component.metrics.last_heartbeat
                    if elapsed > timeout:
                        logger.warning(f"Heartbeat timeout for {name}")
                        await self._initiate_apoptosis(
                            name,
                            ApoptosisReason.HEARTBEAT_TIMEOUT
                        )

    async def _check_recovery(self) -> None:
        """Check if degraded components have recovered"""
        async with self._lock:
            for name, component in self._components.items():
                if component.state == HealthState.DEGRADED:
                    # Check if health score improved
                    if component.health_score >= self.config.degraded_threshold:
                        duration = (
                            datetime.utcnow() - component.state_changed_at
                        ).total_seconds()

                        if duration >= self.config.min_recovery_duration:
                            component.state = HealthState.HEALTHY
                            component.state_changed_at = datetime.utcnow()
                            logger.info(f"Component {name} recovered to HEALTHY")

    def _calculate_health_score(self, metrics: HealthMetrics) -> float:
        """
        Calculate overall health score from metrics.

        Returns score between 0.0 (dead) and 1.0 (healthy).
        """
        scores = []

        # Error rate (inverted - lower is better)
        error_score = max(0, 1.0 - (metrics.error_rate / self.config.max_error_rate))
        scores.append(error_score * 0.25)

        # Success rate
        scores.append(metrics.success_rate * 0.25)

        # Latency (inverted - lower is better)
        latency_score = max(0, 1.0 - (metrics.latency_p95_ms / self.config.max_latency_ms))
        scores.append(latency_score * 0.15)

        # Circuit breakers (inverted - fewer is better)
        cb_score = max(0, 1.0 - (
            metrics.circuit_breakers_open / self.config.max_circuit_breakers_open
        ))
        scores.append(cb_score * 0.15)

        # Memory usage (inverted)
        memory_score = max(0, 1.0 - (metrics.memory_usage_pct / self.config.max_memory_pct))
        scores.append(memory_score * 0.10)

        # Consecutive failures (inverted)
        failure_score = max(0, 1.0 - (
            metrics.consecutive_failures / self.config.max_consecutive_failures
        ))
        scores.append(failure_score * 0.10)

        return sum(scores)

    def _determine_state(
        self,
        health_score: float,
        component: ComponentState
    ) -> HealthState:
        """Determine component state from health score"""
        # Don't resurrect terminal/dead components
        if component.state in [HealthState.TERMINAL, HealthState.DEAD]:
            return component.state

        if health_score >= self.config.degraded_threshold:
            return HealthState.HEALTHY
        elif health_score >= self.config.critical_threshold:
            return HealthState.DEGRADED
        elif health_score >= self.config.terminal_threshold:
            return HealthState.CRITICAL
        else:
            return HealthState.TERMINAL

    def get_component_state(self, name: str) -> Optional[ComponentState]:
        """Get state of a component"""
        return self._components.get(name)

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all components"""
        return {
            name: state.to_dict()
            for name, state in self._components.items()
        }

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health summary"""
        states = list(self._components.values())

        if not states:
            return {"status": "unknown", "components": 0}

        health_scores = [s.health_score for s in states]
        state_counts = {}
        for s in states:
            state_counts[s.state.value] = state_counts.get(s.state.value, 0) + 1

        avg_health = sum(health_scores) / len(health_scores)

        # System status based on worst component
        if any(s.state == HealthState.DEAD for s in states):
            status = "critical"
        elif any(s.state == HealthState.TERMINAL for s in states):
            status = "terminal"
        elif any(s.state == HealthState.CRITICAL for s in states):
            status = "critical"
        elif any(s.state == HealthState.DEGRADED for s in states):
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "average_health_score": round(avg_health, 4),
            "components": len(states),
            "by_state": state_counts,
            "uptime_seconds": (
                (datetime.utcnow() - self._started_at).total_seconds()
                if self._started_at else 0
            )
        }


# Singleton instance
_apoptosis_service: Optional[ApoptosisService] = None


def get_apoptosis_service(
    config: Optional[ApoptosisConfig] = None
) -> ApoptosisService:
    """Get singleton apoptosis service"""
    global _apoptosis_service
    if _apoptosis_service is None:
        _apoptosis_service = ApoptosisService(config)
    return _apoptosis_service
