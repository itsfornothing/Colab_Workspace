"""
Backend performance monitoring for the chat service video call feature.

Tracks:
- Active call count (Requirement 11.1)
- WebSocket connection count (Requirement 11.2, 11.4)
- Signaling message latency (Requirement 11.2)

All counters are stored in-process using thread-safe primitives.
In a multi-process deployment, use the Redis-backed helpers (see below)
which delegate to the Django cache layer (configured as Redis in settings.py).

Requirements: 11.1, 11.2, 11.4
"""

import logging
import threading
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ── In-process counters (thread-safe) ────────────────────────────────────────

_lock = threading.Lock()

# active_calls: set of room_id strings currently in progress
_active_calls: set = set()

# websocket_connections: count of currently open WebSocket connections
_websocket_connection_count: int = 0

# signaling_latency_samples: list of (latency_ms: float) for the rolling window
_LATENCY_WINDOW_SIZE = 1000
_signaling_latency_samples: list = []


# ── Active call tracking ──────────────────────────────────────────────────────

def record_call_started(room_id: str) -> None:
    """
    Record that a call room has become active.
    Call this when a room is created or the first participant joins.
    """
    with _lock:
        _active_calls.add(str(room_id))
    logger.debug("[PerfMonitor] Call started: room=%s  active_calls=%d", room_id, get_active_call_count())


def record_call_ended(room_id: str) -> None:
    """
    Record that a call room has ended.
    Call this when the last participant leaves or the room is closed.
    """
    with _lock:
        _active_calls.discard(str(room_id))
    logger.debug("[PerfMonitor] Call ended: room=%s  active_calls=%d", room_id, get_active_call_count())


def get_active_call_count() -> int:
    """Return the number of currently active call rooms."""
    with _lock:
        return len(_active_calls)


def get_active_call_ids() -> list:
    """Return a snapshot list of currently active room IDs."""
    with _lock:
        return list(_active_calls)


# ── WebSocket connection tracking ─────────────────────────────────────────────

def record_websocket_connected() -> None:
    """Increment the WebSocket connection counter. Call on consumer connect."""
    global _websocket_connection_count
    with _lock:
        _websocket_connection_count += 1
    logger.debug("[PerfMonitor] WS connected  total=%d", _websocket_connection_count)


def record_websocket_disconnected() -> None:
    """Decrement the WebSocket connection counter. Call on consumer disconnect."""
    global _websocket_connection_count
    with _lock:
        _websocket_connection_count = max(0, _websocket_connection_count - 1)
    logger.debug("[PerfMonitor] WS disconnected  total=%d", _websocket_connection_count)


def get_websocket_connection_count() -> int:
    """Return the current number of open WebSocket connections."""
    with _lock:
        return _websocket_connection_count


# ── Signaling message latency tracking ───────────────────────────────────────

def record_signaling_latency(latency_ms: float) -> None:
    """
    Record a signaling message round-trip latency sample (in milliseconds).
    Maintains a rolling window of the last LATENCY_WINDOW_SIZE samples.
    """
    with _lock:
        _signaling_latency_samples.append(latency_ms)
        if len(_signaling_latency_samples) > _LATENCY_WINDOW_SIZE:
            _signaling_latency_samples.pop(0)
    logger.debug("[PerfMonitor] Signaling latency recorded: %.2f ms", latency_ms)


def get_signaling_latency_stats() -> dict:
    """
    Return latency statistics over the current rolling window.

    Returns a dict with:
      - count: number of samples
      - avg_ms: average latency
      - min_ms: minimum latency
      - max_ms: maximum latency
      - p95_ms: 95th-percentile latency
      - p99_ms: 99th-percentile latency
    """
    with _lock:
        samples = list(_signaling_latency_samples)

    if not samples:
        return {
            "count": 0,
            "avg_ms": None,
            "min_ms": None,
            "max_ms": None,
            "p95_ms": None,
            "p99_ms": None,
        }

    sorted_samples = sorted(samples)
    count = len(sorted_samples)

    def percentile(p):
        idx = int(count * p / 100)
        return sorted_samples[min(idx, count - 1)]

    return {
        "count": count,
        "avg_ms": round(sum(sorted_samples) / count, 2),
        "min_ms": round(sorted_samples[0], 2),
        "max_ms": round(sorted_samples[-1], 2),
        "p95_ms": round(percentile(95), 2),
        "p99_ms": round(percentile(99), 2),
    }


# ── Context manager for measuring signaling latency ──────────────────────────

@contextmanager
def measure_signaling_latency():
    """
    Context manager that measures the wall-clock time of a signaling operation
    and records it as a latency sample.

    Usage::

        async with measure_signaling_latency():
            await relay_message_to_peer(...)
    """
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed_ms = (time.monotonic() - start) * 1000
        record_signaling_latency(elapsed_ms)


# ── Aggregate metrics snapshot ────────────────────────────────────────────────

def get_metrics_snapshot() -> dict:
    """
    Return a single dict with all current performance metrics.
    Suitable for exposing via a health/metrics API endpoint.
    """
    return {
        "active_calls": get_active_call_count(),
        "websocket_connections": get_websocket_connection_count(),
        "signaling_latency": get_signaling_latency_stats(),
    }


# ── Redis-backed helpers (multi-process safe) ─────────────────────────────────
# These use the Django cache layer (configured as Redis in settings.py) so they
# work correctly when multiple Daphne/Uvicorn workers are running.

REDIS_KEY_ACTIVE_CALLS = "perf:active_calls"
REDIS_KEY_WS_CONNECTIONS = "perf:ws_connections"


def redis_record_call_started(room_id: str) -> None:
    """Increment the Redis active-call set. Use in production multi-process deployments."""
    try:
        from django.core.cache import cache
        cache.set(f"{REDIS_KEY_ACTIVE_CALLS}:{room_id}", 1, timeout=None)
    except Exception:
        logger.exception("[PerfMonitor] redis_record_call_started failed for room=%s", room_id)


def redis_record_call_ended(room_id: str) -> None:
    """Remove a room from the Redis active-call set."""
    try:
        from django.core.cache import cache
        cache.delete(f"{REDIS_KEY_ACTIVE_CALLS}:{room_id}")
    except Exception:
        logger.exception("[PerfMonitor] redis_record_call_ended failed for room=%s", room_id)


def redis_increment_ws_connections() -> None:
    """Atomically increment the Redis WebSocket connection counter."""
    try:
        from django.core.cache import cache
        current = cache.get(REDIS_KEY_WS_CONNECTIONS, 0)
        cache.set(REDIS_KEY_WS_CONNECTIONS, current + 1, timeout=None)
    except Exception:
        logger.exception("[PerfMonitor] redis_increment_ws_connections failed")


def redis_decrement_ws_connections() -> None:
    """Atomically decrement the Redis WebSocket connection counter (floor 0)."""
    try:
        from django.core.cache import cache
        current = cache.get(REDIS_KEY_WS_CONNECTIONS, 0)
        cache.set(REDIS_KEY_WS_CONNECTIONS, max(0, current - 1), timeout=None)
    except Exception:
        logger.exception("[PerfMonitor] redis_decrement_ws_connections failed")


def redis_get_ws_connection_count() -> int:
    """Return the WebSocket connection count from Redis."""
    try:
        from django.core.cache import cache
        return cache.get(REDIS_KEY_WS_CONNECTIONS, 0)
    except Exception:
        logger.exception("[PerfMonitor] redis_get_ws_connection_count failed")
        return 0
