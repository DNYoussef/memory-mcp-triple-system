"""
Quarantine System - Isolation pattern for failed operations
Part of META-005: Apoptosis/Quarantine (Circuit Breakers)

Provides resource isolation, state rollback, and cleanup after failures.
Implements the bulkhead pattern for fault isolation.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Awaitable, TypeVar
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import traceback

logger = logging.getLogger(__name__)

T = TypeVar("T")


class QuarantineState(str, Enum):
    """State of a quarantined item"""

    PENDING = "pending"  # Awaiting quarantine
    ISOLATED = "isolated"  # In quarantine, resources held
    PROCESSING = "processing"  # Being evaluated for release/disposal
    RELEASED = "released"  # Cleared, resources returned
    DISPOSED = "disposed"  # Permanently removed


class QuarantineReason(str, Enum):
    """Reason for quarantine"""

    CIRCUIT_BREAKER = "circuit_breaker"
    TIMEOUT = "timeout"
    ERROR_THRESHOLD = "error_threshold"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    VALIDATION_FAILURE = "validation_failure"
    SECURITY_VIOLATION = "security_violation"
    MANUAL = "manual"


@dataclass
class QuarantinedItem:
    """An item in quarantine"""

    id: str
    resource_type: str
    resource_id: str
    reason: QuarantineReason
    state: QuarantineState
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    release_after: Optional[datetime] = None
    cleanup_callback: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "reason": self.reason.value,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "release_after": self.release_after.isoformat()
            if self.release_after
            else None,
            "metadata": self.metadata,
        }


@dataclass
class QuarantineMetrics:
    """Metrics for quarantine system"""

    total_quarantined: int = 0
    total_released: int = 0
    total_disposed: int = 0
    current_isolated: int = 0
    by_reason: Dict[str, int] = field(default_factory=dict)
    by_resource_type: Dict[str, int] = field(default_factory=dict)
    avg_quarantine_duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_quarantined": self.total_quarantined,
            "total_released": self.total_released,
            "total_disposed": self.total_disposed,
            "current_isolated": self.current_isolated,
            "by_reason": self.by_reason,
            "by_resource_type": self.by_resource_type,
            "avg_quarantine_duration_ms": self.avg_quarantine_duration_ms,
        }


class ResourcePool:
    """
    Bulkhead pattern - isolated resource pool.

    Prevents one failing component from consuming all resources.
    """

    def __init__(self, name: str, max_concurrent: int = 10):
        self.name = name
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0
        self._total_requests = 0
        self._rejected_requests = 0

    @asynccontextmanager
    async def acquire(self, timeout: float = 30.0):
        """Acquire a slot in the pool with timeout"""
        self._total_requests += 1

        try:
            acquired = await asyncio.wait_for(
                self._semaphore.acquire(), timeout=timeout
            )
            if acquired:
                self._active_count += 1
                try:
                    yield True
                finally:
                    self._active_count -= 1
                    self._semaphore.release()
        except asyncio.TimeoutError:
            self._rejected_requests += 1
            logger.warning(f"Pool {self.name} rejected request - timeout")
            yield False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "max_concurrent": self.max_concurrent,
            "active": self._active_count,
            "available": self.max_concurrent - self._active_count,
            "total_requests": self._total_requests,
            "rejected_requests": self._rejected_requests,
            "rejection_rate": (
                self._rejected_requests / self._total_requests
                if self._total_requests > 0
                else 0.0
            ),
        }


class QuarantineManager:
    """
    Manages quarantine operations and resource isolation.

    Features:
    1. Item quarantine with state tracking
    2. Bulkhead resource pools
    3. Automatic cleanup scheduling
    4. Release/disposal policies
    5. Metrics collection
    """

    # Default settings
    DEFAULT_QUARANTINE_DURATION = timedelta(hours=1)
    DEFAULT_MAX_RETRIES = 3
    CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes

    def __init__(
        self,
        default_duration: Optional[timedelta] = None,
        max_retries: int = 3,
        auto_cleanup: bool = True,
    ):
        self.default_duration = default_duration or self.DEFAULT_QUARANTINE_DURATION
        self.max_retries = max_retries
        self.auto_cleanup = auto_cleanup

        self._items: Dict[str, QuarantinedItem] = {}
        self._resource_pools: Dict[str, ResourcePool] = {}
        self._cleanup_callbacks: Dict[str, Callable[..., Awaitable[None]]] = {}
        self._metrics = QuarantineMetrics()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._durations: List[float] = []

    async def start(self) -> None:
        """Start the quarantine manager"""
        if self.auto_cleanup:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Quarantine manager started with auto-cleanup")

    async def stop(self) -> None:
        """Stop the quarantine manager"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Quarantine manager stopped")

    def register_pool(self, name: str, max_concurrent: int = 10) -> ResourcePool:
        """Register a new resource pool (bulkhead)"""
        pool = ResourcePool(name, max_concurrent)
        self._resource_pools[name] = pool
        logger.info(f"Registered resource pool: {name} (max={max_concurrent})")
        return pool

    def get_pool(self, name: str) -> Optional[ResourcePool]:
        """Get a resource pool by name"""
        return self._resource_pools.get(name)

    def register_cleanup_callback(
        self, resource_type: str, callback: Callable[..., Awaitable[None]]
    ) -> None:
        """Register a cleanup callback for a resource type"""
        self._cleanup_callbacks[resource_type] = callback
        logger.info(f"Registered cleanup callback for: {resource_type}")

    async def quarantine(
        self,
        resource_type: str,
        resource_id: str,
        reason: QuarantineReason,
        error: Optional[Exception] = None,
        metadata: Optional[Dict[str, Any]] = None,
        duration: Optional[timedelta] = None,
    ) -> QuarantinedItem:
        """
        Put a resource into quarantine.

        Args:
            resource_type: Type of resource (e.g., "memory_chunk", "api_call")
            resource_id: Unique identifier of the resource
            reason: Why the resource is being quarantined
            error: Optional exception that caused quarantine
            metadata: Additional context
            duration: How long to quarantine (None = default)

        Returns:
            QuarantinedItem tracking the quarantine
        """
        async with self._lock:
            item_id = str(uuid.uuid4())[:8]
            now = datetime.utcnow()

            release_after = now + (duration or self.default_duration)

            item = QuarantinedItem(
                id=item_id,
                resource_type=resource_type,
                resource_id=resource_id,
                reason=reason,
                state=QuarantineState.ISOLATED,
                created_at=now,
                updated_at=now,
                error_message=str(error) if error else None,
                stack_trace=traceback.format_exc() if error else None,
                metadata=metadata or {},
                max_retries=self.max_retries,
                release_after=release_after,
            )

            self._items[item_id] = item

            # Update metrics
            self._metrics.total_quarantined += 1
            self._metrics.current_isolated += 1
            self._metrics.by_reason[reason.value] = (
                self._metrics.by_reason.get(reason.value, 0) + 1
            )
            self._metrics.by_resource_type[resource_type] = (
                self._metrics.by_resource_type.get(resource_type, 0) + 1
            )

            logger.info(
                f"Quarantined {resource_type}:{resource_id} "
                f"(reason={reason.value}, id={item_id})"
            )

            return item

    async def release(self, item_id: str, force: bool = False) -> bool:
        """
        Release an item from quarantine.

        Args:
            item_id: Quarantine item ID
            force: Force release even if conditions not met

        Returns:
            True if released, False otherwise
        """
        async with self._lock:
            item = self._items.get(item_id)
            if not item:
                logger.warning(f"Quarantine item not found: {item_id}")
                return False

            if item.state not in [QuarantineState.ISOLATED, QuarantineState.PROCESSING]:
                logger.warning(f"Cannot release item in state: {item.state.value}")
                return False

            now = datetime.utcnow()

            # Check if release conditions met
            if not force:
                if item.release_after and now < item.release_after:
                    logger.info(f"Item {item_id} not ready for release yet")
                    return False

            # Update state
            item.state = QuarantineState.RELEASED
            item.updated_at = now

            # Track duration
            duration_ms = (now - item.created_at).total_seconds() * 1000
            self._durations.append(duration_ms)
            if len(self._durations) > 1000:
                self._durations = self._durations[-1000:]
            self._metrics.avg_quarantine_duration_ms = sum(self._durations) / len(
                self._durations
            )

            # Update metrics
            self._metrics.total_released += 1
            self._metrics.current_isolated -= 1

            logger.info(f"Released quarantine item: {item_id}")
            return True

    async def dispose(self, item_id: str, run_cleanup: bool = True) -> bool:
        """
        Permanently dispose of a quarantined item.

        Args:
            item_id: Quarantine item ID
            run_cleanup: Whether to run cleanup callback

        Returns:
            True if disposed, False otherwise
        """
        async with self._lock:
            item = self._items.get(item_id)
            if not item:
                return False

            # Run cleanup callback if registered
            if run_cleanup and item.resource_type in self._cleanup_callbacks:
                try:
                    callback = self._cleanup_callbacks[item.resource_type]
                    await callback(item.resource_id, item.metadata)
                except Exception as e:
                    logger.error(f"Cleanup callback failed for {item_id}: {e}")

            # Update state
            item.state = QuarantineState.DISPOSED
            item.updated_at = datetime.utcnow()

            # Track duration
            duration_ms = (item.updated_at - item.created_at).total_seconds() * 1000
            self._durations.append(duration_ms)

            # Update metrics
            self._metrics.total_disposed += 1
            self._metrics.current_isolated -= 1

            # Remove from active items
            del self._items[item_id]

            logger.info(f"Disposed quarantine item: {item_id}")
            return True

    async def retry(self, item_id: str) -> Optional[QuarantinedItem]:
        """
        Attempt to retry a quarantined operation.

        Returns updated item if retry allowed, None if max retries exceeded.
        """
        async with self._lock:
            item = self._items.get(item_id)
            if not item:
                return None

            if item.retry_count >= item.max_retries:
                logger.warning(f"Max retries exceeded for {item_id}")
                return None

            item.retry_count += 1
            item.updated_at = datetime.utcnow()
            item.state = QuarantineState.PROCESSING

            logger.info(f"Retry {item.retry_count}/{item.max_retries} for {item_id}")
            return item

    async def _cleanup_loop(self) -> None:
        """Background task to process quarantined items"""
        while True:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL_SECONDS)
                await self._process_expired_items()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    async def _process_expired_items(self) -> None:
        """Process items that have exceeded their quarantine duration"""
        now = datetime.utcnow()
        expired_ids = []

        async with self._lock:
            for item_id, item in self._items.items():
                if item.state != QuarantineState.ISOLATED:
                    continue

                if item.release_after and now >= item.release_after:
                    if item.retry_count < item.max_retries:
                        expired_ids.append(("retry", item_id))
                    else:
                        expired_ids.append(("dispose", item_id))

        # Process outside lock to avoid blocking
        for action, item_id in expired_ids:
            if action == "retry":
                await self.retry(item_id)
            else:
                await self.dispose(item_id)

    def get_item(self, item_id: str) -> Optional[QuarantinedItem]:
        """Get a quarantined item by ID"""
        return self._items.get(item_id)

    def list_items(
        self,
        state: Optional[QuarantineState] = None,
        resource_type: Optional[str] = None,
    ) -> List[QuarantinedItem]:
        """List quarantined items with optional filters"""
        items = list(self._items.values())

        if state:
            items = [i for i in items if i.state == state]
        if resource_type:
            items = [i for i in items if i.resource_type == resource_type]

        return items

    def get_metrics(self) -> Dict[str, Any]:
        """Get quarantine metrics"""
        return {
            "quarantine": self._metrics.to_dict(),
            "pools": {
                name: pool.get_stats() for name, pool in self._resource_pools.items()
            },
        }


# Singleton instance
_quarantine_manager: Optional[QuarantineManager] = None


def get_quarantine_manager(
    default_duration: Optional[timedelta] = None, max_retries: int = 3
) -> QuarantineManager:
    """Get singleton quarantine manager"""
    global _quarantine_manager
    if _quarantine_manager is None:
        _quarantine_manager = QuarantineManager(
            default_duration=default_duration, max_retries=max_retries
        )
    return _quarantine_manager
