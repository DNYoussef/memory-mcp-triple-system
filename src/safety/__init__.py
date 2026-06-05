"""
Safety module for circuit breakers, quarantine, and apoptosis.
Part of META-005: Apoptosis/Quarantine (Circuit Breakers)
"""
from .quarantine import (
    QuarantineManager,
    QuarantineState,
    QuarantineReason,
    QuarantinedItem,
    QuarantineMetrics,
    ResourcePool,
    get_quarantine_manager
)
from .apoptosis import (
    ApoptosisService,
    ApoptosisConfig,
    ApoptosisReason,
    HealthState,
    HealthMetrics,
    ComponentState,
    get_apoptosis_service
)
from .circuit_breaker_metrics import (
    CircuitBreakerRegistry,
    CircuitBreakerSnapshot,
    CircuitBreakerEvent,
    CircuitState,
    get_circuit_breaker_registry
)

__all__ = [
    # Quarantine (META-005)
    "QuarantineManager",
    "QuarantineState",
    "QuarantineReason",
    "QuarantinedItem",
    "QuarantineMetrics",
    "ResourcePool",
    "get_quarantine_manager",
    # Apoptosis (META-005)
    "ApoptosisService",
    "ApoptosisConfig",
    "ApoptosisReason",
    "HealthState",
    "HealthMetrics",
    "ComponentState",
    "get_apoptosis_service",
    # Circuit Breaker Metrics (META-005)
    "CircuitBreakerRegistry",
    "CircuitBreakerSnapshot",
    "CircuitBreakerEvent",
    "CircuitState",
    "get_circuit_breaker_registry",
]
