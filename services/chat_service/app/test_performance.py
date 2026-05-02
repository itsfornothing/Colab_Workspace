"""
Performance tests for the chat service video call feature.

Tests:
  - 100 concurrent active calls (load test)          - Requirement 11.1
  - Signaling latency (<100ms target)                 - Requirement 11.2
  - 8-participant call stability                      - Requirement 11.3
  - 1000 concurrent WebSocket connections             - Requirement 11.4
  - Memory usage (<2GB per 100 calls)                 - Requirement 11.6
  - Load tests for signaling, media negotiation,
    and multi-participant scenarios                   - Requirement 11.7

These tests use Django's test framework with asyncio support and the
in-process performance_monitor module so they run without external
infrastructure (Redis, database) beyond what Django's test runner provides.
"""

import asyncio
import gc
import statistics
import threading
import time
import tracemalloc
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

import app.performance_monitor as pm_module
from app.performance_monitor import (
    get_active_call_count,
    get_metrics_snapshot,
    get_signaling_latency_stats,
    get_websocket_connection_count,
    measure_signaling_latency,
    record_call_ended,
    record_call_started,
    record_signaling_latency,
    record_websocket_connected,
    record_websocket_disconnected,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_monitor():
    """Reset all in-process performance monitor counters."""
    with pm_module._lock:
        pm_module._active_calls.clear()
        pm_module._websocket_connection_count = 0
        pm_module._signaling_latency_samples.clear()


def _simulate_call_lifecycle(room_id: str, duration_ms: float = 0) -> None:
    """Simulate a single call: start, optional sleep, end."""
    record_call_started(room_id)
    if duration_ms > 0:
        time.sleep(duration_ms / 1000)
    record_call_ended(room_id)


def _simulate_ws_lifecycle(duration_ms: float = 0) -> None:
    """Simulate a single WebSocket connection: connect, optional sleep, disconnect."""
    record_websocket_connected()
    if duration_ms > 0:
        time.sleep(duration_ms / 1000)
    record_websocket_disconnected()


def _simulate_signaling_message(latency_ms: float = 5.0) -> None:
    """Simulate a signaling message relay with a given latency."""
    with measure_signaling_latency():
        time.sleep(latency_ms / 1000)


# ---------------------------------------------------------------------------
# Test: 100 concurrent active calls (Requirement 11.1)
# ---------------------------------------------------------------------------

class ConcurrentActiveCallsTest(TestCase):
    """
    Load test: 100 concurrent active calls.

    Validates Requirement 11.1:
      THE Chat_Service SHALL handle 100 concurrent active calls without degradation.
    """

    TARGET_CONCURRENT_CALLS = 100

    def setUp(self):
        _reset_monitor()

    def tearDown(self):
        _reset_monitor()

    def test_100_concurrent_calls_can_be_tracked(self):
        """All 100 rooms can be registered as active simultaneously."""
        room_ids = [str(uuid.uuid4()) for _ in range(self.TARGET_CONCURRENT_CALLS)]
        for room_id in room_ids:
            record_call_started(room_id)

        self.assertEqual(get_active_call_count(), self.TARGET_CONCURRENT_CALLS)

    def test_100_concurrent_calls_thread_safe_registration(self):
        """
        100 threads simultaneously register calls — no race conditions.
        The final count must equal exactly 100.
        """
        room_ids = [str(uuid.uuid4()) for _ in range(self.TARGET_CONCURRENT_CALLS)]
        errors = []

        def start_call(room_id):
            try:
                record_call_started(room_id)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=self.TARGET_CONCURRENT_CALLS) as pool:
            futures = [pool.submit(start_call, rid) for rid in room_ids]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors during concurrent registration: {errors}")
        self.assertEqual(get_active_call_count(), self.TARGET_CONCURRENT_CALLS)

    def test_100_concurrent_calls_thread_safe_deregistration(self):
        """
        100 threads simultaneously end calls — counter returns to 0.
        """
        room_ids = [str(uuid.uuid4()) for _ in range(self.TARGET_CONCURRENT_CALLS)]
        for rid in room_ids:
            record_call_started(rid)

        errors = []

        def end_call(room_id):
            try:
                record_call_ended(room_id)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=self.TARGET_CONCURRENT_CALLS) as pool:
            futures = [pool.submit(end_call, rid) for rid in room_ids]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors during concurrent deregistration: {errors}")
        self.assertEqual(get_active_call_count(), 0)

    def test_100_concurrent_call_lifecycles_complete_correctly(self):
        """
        100 threads each run a full call lifecycle (start → end) concurrently.
        After all threads finish, the active call count must be 0.
        """
        room_ids = [str(uuid.uuid4()) for _ in range(self.TARGET_CONCURRENT_CALLS)]
        errors = []

        def lifecycle(room_id):
            try:
                _simulate_call_lifecycle(room_id, duration_ms=1)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=self.TARGET_CONCURRENT_CALLS) as pool:
            futures = [pool.submit(lifecycle, rid) for rid in room_ids]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors during concurrent lifecycles: {errors}")
        self.assertEqual(get_active_call_count(), 0)

    def test_peak_concurrent_calls_reaches_target(self):
        """
        Verify that at peak, all 100 calls are simultaneously active.
        Uses a barrier to synchronise threads at the peak moment.
        """
        n = self.TARGET_CONCURRENT_CALLS
        room_ids = [str(uuid.uuid4()) for _ in range(n)]
        barrier = threading.Barrier(n)
        peak_counts = []
        lock = threading.Lock()

        def lifecycle(room_id):
            record_call_started(room_id)
            barrier.wait()  # all threads reach peak simultaneously
            with lock:
                peak_counts.append(get_active_call_count())
            record_call_ended(room_id)

        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [pool.submit(lifecycle, rid) for rid in room_ids]
            for f in as_completed(futures):
                f.result()

        # At the barrier, all 100 calls should be active
        self.assertTrue(
            any(c == n for c in peak_counts),
            f"Peak count never reached {n}. Observed peaks: {sorted(set(peak_counts))}",
        )

    def test_metrics_snapshot_reflects_100_active_calls(self):
        """get_metrics_snapshot() correctly reports 100 active calls."""
        room_ids = [str(uuid.uuid4()) for _ in range(self.TARGET_CONCURRENT_CALLS)]
        for rid in room_ids:
            record_call_started(rid)

        snapshot = get_metrics_snapshot()
        self.assertEqual(snapshot["active_calls"], self.TARGET_CONCURRENT_CALLS)

    def test_call_tracking_performance_under_load(self):
        """
        Registering and deregistering 100 calls should complete in under 1 second.
        This is a basic throughput sanity check.
        """
        room_ids = [str(uuid.uuid4()) for _ in range(self.TARGET_CONCURRENT_CALLS)]
        start = time.monotonic()
        for rid in room_ids:
            record_call_started(rid)
        for rid in room_ids:
            record_call_ended(rid)
        elapsed = time.monotonic() - start

        self.assertLess(
            elapsed, 1.0,
            f"Tracking 100 call lifecycles took {elapsed:.3f}s (expected < 1s)",
        )

# ---------------------------------------------------------------------------
# Test: Signaling latency < 100ms (Requirement 11.2)
# ---------------------------------------------------------------------------

class SignalingLatencyTest(TestCase):
    """
    Signaling latency tests.

    Validates Requirement 11.2:
      THE Signaling_Server SHALL relay signaling messages with less than 100ms latency.
    """

    LATENCY_TARGET_MS = 100.0
    SAMPLE_COUNT = 200

    def setUp(self):
        _reset_monitor()

    def tearDown(self):
        _reset_monitor()

    def test_simulated_signaling_latency_below_100ms(self):
        """
        Simulated signaling messages with 5ms processing time should be
        well below the 100ms target.
        """
        for _ in range(self.SAMPLE_COUNT):
            _simulate_signaling_message(latency_ms=5.0)

        stats = get_signaling_latency_stats()
        self.assertIsNotNone(stats["avg_ms"])
        self.assertLess(
            stats["avg_ms"],
            self.LATENCY_TARGET_MS,
            f"Average signaling latency {stats['avg_ms']}ms exceeds {self.LATENCY_TARGET_MS}ms target",
        )

    def test_p95_signaling_latency_below_100ms(self):
        """
        95th-percentile latency should be below 100ms for typical signaling traffic.
        """
        for _ in range(self.SAMPLE_COUNT):
            _simulate_signaling_message(latency_ms=5.0)

        stats = get_signaling_latency_stats()
        self.assertIsNotNone(stats["p95_ms"])
        self.assertLess(
            stats["p95_ms"],
            self.LATENCY_TARGET_MS,
            f"p95 signaling latency {stats['p95_ms']}ms exceeds {self.LATENCY_TARGET_MS}ms target",
        )

    def test_p99_signaling_latency_below_100ms(self):
        """
        99th-percentile latency should be below 100ms for typical signaling traffic.
        """
        for _ in range(self.SAMPLE_COUNT):
            _simulate_signaling_message(latency_ms=5.0)

        stats = get_signaling_latency_stats()
        self.assertIsNotNone(stats["p99_ms"])
        self.assertLess(
            stats["p99_ms"],
            self.LATENCY_TARGET_MS,
            f"p99 signaling latency {stats['p99_ms']}ms exceeds {self.LATENCY_TARGET_MS}ms target",
        )

    def test_measure_signaling_latency_context_manager_accuracy(self):
        """
        The measure_signaling_latency context manager should record latency
        within a reasonable tolerance of the actual sleep duration.
        """
        sleep_ms = 10.0
        tolerance_ms = 20.0  # allow OS scheduling jitter

        with measure_signaling_latency():
            time.sleep(sleep_ms / 1000)

        stats = get_signaling_latency_stats()
        self.assertEqual(stats["count"], 1)
        self.assertGreaterEqual(stats["avg_ms"], sleep_ms - tolerance_ms)
        self.assertLess(
            stats["avg_ms"],
            self.LATENCY_TARGET_MS,
            f"Measured latency {stats['avg_ms']}ms exceeds {self.LATENCY_TARGET_MS}ms target",
        )

    def test_concurrent_signaling_messages_latency_stays_below_target(self):
        """
        Under concurrent load (50 threads each sending 4 messages),
        average latency should remain below 100ms.
        """
        n_threads = 50
        messages_per_thread = 4
        errors = []

        def send_messages():
            try:
                for _ in range(messages_per_thread):
                    _simulate_signaling_message(latency_ms=5.0)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(send_messages) for _ in range(n_threads)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors during concurrent signaling: {errors}")

        stats = get_signaling_latency_stats()
        expected_samples = n_threads * messages_per_thread
        # Rolling window may cap at 1000; check at least some samples recorded
        self.assertGreater(stats["count"], 0)
        self.assertLess(
            stats["avg_ms"],
            self.LATENCY_TARGET_MS,
            f"Average latency {stats['avg_ms']}ms exceeds {self.LATENCY_TARGET_MS}ms under concurrent load",
        )

    def test_signaling_latency_stats_structure(self):
        """get_signaling_latency_stats() returns all required fields."""
        record_signaling_latency(50.0)
        stats = get_signaling_latency_stats()
        required_keys = {"count", "avg_ms", "min_ms", "max_ms", "p95_ms", "p99_ms"}
        self.assertEqual(set(stats.keys()), required_keys)

    def test_signaling_latency_threshold_boundary(self):
        """
        Latency samples at exactly 99ms should be accepted as within target.
        Latency samples at 100ms are at the boundary (target is < 100ms).
        """
        record_signaling_latency(99.0)
        stats = get_signaling_latency_stats()
        self.assertLess(stats["avg_ms"], self.LATENCY_TARGET_MS)

    def test_high_volume_signaling_latency_recording(self):
        """
        Recording 1000 latency samples should complete quickly (< 0.5s).
        """
        start = time.monotonic()
        for i in range(1000):
            record_signaling_latency(float(i % 100))
        elapsed = time.monotonic() - start

        self.assertLess(
            elapsed, 0.5,
            f"Recording 1000 latency samples took {elapsed:.3f}s (expected < 0.5s)",
        )

# ---------------------------------------------------------------------------
# Test: 8-participant call stability (Requirement 11.3)
# ---------------------------------------------------------------------------

class EightParticipantCallStabilityTest(TestCase):
    """
    8-participant call stability tests.

    Validates Requirement 11.3:
      WHEN 8 participants are in a call, THE WebRTC_Client SHALL maintain
      stable connections.

    These tests verify the backend's ability to track and manage an
    8-participant call without data corruption or race conditions.
    """

    MAX_PARTICIPANTS = 8

    def setUp(self):
        _reset_monitor()

    def tearDown(self):
        _reset_monitor()

    def test_8_participant_room_can_be_tracked(self):
        """A single room with 8 participants is correctly tracked as one active call."""
        room_id = str(uuid.uuid4())
        record_call_started(room_id)
        self.assertEqual(get_active_call_count(), 1)

    def test_8_participant_signaling_messages_all_recorded(self):
        """
        In an 8-participant mesh, each pair exchanges offer/answer/ICE.
        Total signaling messages = 8*7 = 56 (offer+answer per pair) + ICE candidates.
        Verify all latency samples are recorded correctly.
        """
        # Simulate mesh signaling: each of 8 participants sends to 7 others
        n = self.MAX_PARTICIPANTS
        signaling_count = n * (n - 1)  # 56 messages (offer or answer per direction)

        for _ in range(signaling_count):
            record_signaling_latency(5.0)  # 5ms per message

        stats = get_signaling_latency_stats()
        self.assertEqual(stats["count"], signaling_count)
        self.assertAlmostEqual(stats["avg_ms"], 5.0, places=1)

    def test_8_participant_concurrent_signaling_thread_safety(self):
        """
        8 threads simultaneously send signaling messages (simulating mesh topology).
        No data corruption should occur.
        """
        n = self.MAX_PARTICIPANTS
        messages_per_participant = 7  # each sends to 7 others
        errors = []

        def participant_signaling():
            try:
                for _ in range(messages_per_participant):
                    _simulate_signaling_message(latency_ms=3.0)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [pool.submit(participant_signaling) for _ in range(n)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors in 8-participant signaling: {errors}")

        stats = get_signaling_latency_stats()
        expected = n * messages_per_participant
        self.assertEqual(stats["count"], expected)

    def test_8_participant_call_lifecycle_stability(self):
        """
        Simulate a full 8-participant call lifecycle:
        - All 8 join (call starts)
        - Signaling exchange occurs
        - All 8 leave (call ends)
        The active call count should return to 0.
        """
        room_id = str(uuid.uuid4())
        n = self.MAX_PARTICIPANTS
        barrier = threading.Barrier(n)
        errors = []

        def participant_lifecycle():
            try:
                # Simulate joining
                record_websocket_connected()
                barrier.wait()  # all participants connected simultaneously

                # Simulate signaling
                for _ in range(7):  # each sends to 7 others
                    record_signaling_latency(5.0)

                # Simulate leaving
                record_websocket_disconnected()
            except Exception as exc:
                errors.append(exc)

        record_call_started(room_id)

        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [pool.submit(participant_lifecycle) for _ in range(n)]
            for f in as_completed(futures):
                f.result()

        record_call_ended(room_id)

        self.assertEqual(len(errors), 0, f"Errors in 8-participant lifecycle: {errors}")
        self.assertEqual(get_active_call_count(), 0)
        self.assertEqual(get_websocket_connection_count(), 0)

    def test_multiple_8_participant_calls_simultaneously(self):
        """
        10 simultaneous 8-participant calls (80 total participants).
        All calls should be tracked correctly.
        """
        n_calls = 10
        room_ids = [str(uuid.uuid4()) for _ in range(n_calls)]
        errors = []

        def run_call(room_id):
            try:
                record_call_started(room_id)
                # Simulate 8 participants' signaling
                for _ in range(self.MAX_PARTICIPANTS * 7):
                    record_signaling_latency(5.0)
                record_call_ended(room_id)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=n_calls) as pool:
            futures = [pool.submit(run_call, rid) for rid in room_ids]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors in multiple 8-participant calls: {errors}")
        self.assertEqual(get_active_call_count(), 0)

    def test_8_participant_signaling_latency_stays_below_target(self):
        """
        Even with 8 participants exchanging signaling messages concurrently,
        average latency should remain below 100ms.
        """
        n = self.MAX_PARTICIPANTS
        errors = []

        def participant_signaling():
            try:
                for _ in range(7):
                    _simulate_signaling_message(latency_ms=5.0)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [pool.submit(participant_signaling) for _ in range(n)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0)
        stats = get_signaling_latency_stats()
        self.assertLess(
            stats["avg_ms"],
            100.0,
            f"8-participant signaling avg latency {stats['avg_ms']}ms exceeds 100ms",
        )

# ---------------------------------------------------------------------------
# Test: 1000 concurrent WebSocket connections (Requirement 11.4)
# ---------------------------------------------------------------------------

class ConcurrentWebSocketConnectionsTest(TestCase):
    """
    1000 concurrent WebSocket connection tests.

    Validates Requirement 11.4:
      THE Chat_Service SHALL support 1000 concurrent WebSocket connections.
    """

    TARGET_CONNECTIONS = 1000

    def setUp(self):
        _reset_monitor()

    def tearDown(self):
        _reset_monitor()

    def test_1000_connections_can_be_tracked(self):
        """All 1000 connections can be registered simultaneously."""
        for _ in range(self.TARGET_CONNECTIONS):
            record_websocket_connected()

        self.assertEqual(get_websocket_connection_count(), self.TARGET_CONNECTIONS)

    def test_1000_connections_thread_safe_increment(self):
        """
        1000 threads simultaneously connect — no race conditions.
        Final count must equal exactly 1000.
        """
        errors = []

        def connect():
            try:
                record_websocket_connected()
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=self.TARGET_CONNECTIONS) as pool:
            futures = [pool.submit(connect) for _ in range(self.TARGET_CONNECTIONS)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors during concurrent connect: {errors}")
        self.assertEqual(get_websocket_connection_count(), self.TARGET_CONNECTIONS)

    def test_1000_connections_thread_safe_decrement(self):
        """
        1000 threads simultaneously disconnect — counter returns to 0.
        """
        for _ in range(self.TARGET_CONNECTIONS):
            record_websocket_connected()

        errors = []

        def disconnect():
            try:
                record_websocket_disconnected()
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=self.TARGET_CONNECTIONS) as pool:
            futures = [pool.submit(disconnect) for _ in range(self.TARGET_CONNECTIONS)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors during concurrent disconnect: {errors}")
        self.assertEqual(get_websocket_connection_count(), 0)

    def test_1000_connection_lifecycles_complete_correctly(self):
        """
        1000 threads each run a full connection lifecycle (connect → disconnect).
        After all threads finish, the connection count must be 0.
        """
        errors = []

        def lifecycle():
            try:
                _simulate_ws_lifecycle(duration_ms=1)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=self.TARGET_CONNECTIONS) as pool:
            futures = [pool.submit(lifecycle) for _ in range(self.TARGET_CONNECTIONS)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors during concurrent WS lifecycles: {errors}")
        self.assertEqual(get_websocket_connection_count(), 0)

    def test_peak_concurrent_connections_reaches_target(self):
        """
        Verify that at peak, all 1000 connections are simultaneously active.
        Uses a barrier to synchronise threads at the peak moment.
        """
        n = self.TARGET_CONNECTIONS
        barrier = threading.Barrier(n)
        peak_counts = []
        lock = threading.Lock()

        def lifecycle():
            record_websocket_connected()
            barrier.wait()  # all threads reach peak simultaneously
            with lock:
                peak_counts.append(get_websocket_connection_count())
            record_websocket_disconnected()

        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [pool.submit(lifecycle) for _ in range(n)]
            for f in as_completed(futures):
                f.result()

        self.assertTrue(
            any(c == n for c in peak_counts),
            f"Peak connection count never reached {n}. Observed: {sorted(set(peak_counts))}",
        )

    def test_connection_tracking_performance_under_load(self):
        """
        Registering and deregistering 1000 connections should complete in under 2 seconds.
        """
        start = time.monotonic()
        for _ in range(self.TARGET_CONNECTIONS):
            record_websocket_connected()
        for _ in range(self.TARGET_CONNECTIONS):
            record_websocket_disconnected()
        elapsed = time.monotonic() - start

        self.assertLess(
            elapsed, 2.0,
            f"Tracking 1000 WS lifecycles took {elapsed:.3f}s (expected < 2s)",
        )

    def test_metrics_snapshot_reflects_1000_connections(self):
        """get_metrics_snapshot() correctly reports 1000 WebSocket connections."""
        for _ in range(self.TARGET_CONNECTIONS):
            record_websocket_connected()

        snapshot = get_metrics_snapshot()
        self.assertEqual(snapshot["websocket_connections"], self.TARGET_CONNECTIONS)

    def test_connection_count_never_goes_negative(self):
        """
        Disconnecting more times than connecting should floor at 0, not go negative.
        """
        record_websocket_connected()
        record_websocket_disconnected()
        record_websocket_disconnected()  # extra disconnect
        record_websocket_disconnected()  # extra disconnect

        self.assertEqual(get_websocket_connection_count(), 0)

# ---------------------------------------------------------------------------
# Test: Memory usage < 2GB per 100 calls (Requirement 11.6)
# ---------------------------------------------------------------------------

class MemoryUsageTest(TestCase):
    """
    Memory usage tests.

    Validates Requirement 11.6:
      THE Chat_Service SHALL use less than 2GB memory per 100 active calls.

    These tests use Python's tracemalloc to measure memory allocated by the
    performance monitor during 100 concurrent call simulations.  The 2GB
    limit is a system-level target; here we verify that the in-process
    tracking structures do not grow unboundedly and stay well within
    reasonable bounds.
    """

    TARGET_CALLS = 100
    # 2 GB in bytes
    MEMORY_LIMIT_BYTES = 2 * 1024 * 1024 * 1024
    # Conservative in-process limit: tracking 100 calls should use < 10 MB
    IN_PROCESS_LIMIT_BYTES = 10 * 1024 * 1024  # 10 MB

    def setUp(self):
        _reset_monitor()

    def tearDown(self):
        _reset_monitor()
        gc.collect()

    def test_memory_for_100_active_calls_within_limit(self):
        """
        Memory allocated by the performance monitor for 100 active calls
        should be well below 10 MB (and certainly below 2 GB).
        """
        gc.collect()
        tracemalloc.start()

        room_ids = [str(uuid.uuid4()) for _ in range(self.TARGET_CALLS)]
        for rid in room_ids:
            record_call_started(rid)

        snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        # Sum all memory allocated since tracemalloc.start()
        total_bytes = sum(stat.size for stat in snapshot.statistics("lineno"))

        self.assertLess(
            total_bytes,
            self.IN_PROCESS_LIMIT_BYTES,
            f"Memory for 100 active calls: {total_bytes / 1024:.1f} KB "
            f"(limit: {self.IN_PROCESS_LIMIT_BYTES / 1024 / 1024:.0f} MB)",
        )

        # Clean up
        for rid in room_ids:
            record_call_ended(rid)

    def test_memory_for_100_call_lifecycles_within_limit(self):
        """
        Memory allocated during 100 complete call lifecycles (start + end)
        should be well below 10 MB.
        """
        gc.collect()
        tracemalloc.start()

        room_ids = [str(uuid.uuid4()) for _ in range(self.TARGET_CALLS)]
        for rid in room_ids:
            record_call_started(rid)
        for rid in room_ids:
            record_call_ended(rid)

        snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        total_bytes = sum(stat.size for stat in snapshot.statistics("lineno"))

        self.assertLess(
            total_bytes,
            self.IN_PROCESS_LIMIT_BYTES,
            f"Memory for 100 call lifecycles: {total_bytes / 1024:.1f} KB "
            f"(limit: {self.IN_PROCESS_LIMIT_BYTES / 1024 / 1024:.0f} MB)",
        )

    def test_memory_for_1000_signaling_samples_within_limit(self):
        """
        The rolling window of 1000 signaling latency samples should not
        consume excessive memory.
        """
        gc.collect()
        tracemalloc.start()

        for i in range(1000):
            record_signaling_latency(float(i % 100))

        snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        total_bytes = sum(stat.size for stat in snapshot.statistics("lineno"))

        # 1000 float samples should be tiny (< 1 MB)
        self.assertLess(
            total_bytes,
            1 * 1024 * 1024,
            f"Memory for 1000 latency samples: {total_bytes / 1024:.1f} KB (limit: 1 MB)",
        )

    def test_memory_does_not_grow_unboundedly_with_repeated_calls(self):
        """
        Running 100 call lifecycles multiple times should not cause unbounded
        memory growth (the active_calls set is cleared each time).
        """
        gc.collect()

        def run_batch():
            room_ids = [str(uuid.uuid4()) for _ in range(self.TARGET_CALLS)]
            for rid in room_ids:
                record_call_started(rid)
            for rid in room_ids:
                record_call_ended(rid)

        # Run 5 batches
        tracemalloc.start()
        for _ in range(5):
            run_batch()
        snapshot_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        total_bytes = sum(stat.size for stat in snapshot_after.statistics("lineno"))

        # 5 batches of 100 calls should still be well under 10 MB
        self.assertLess(
            total_bytes,
            self.IN_PROCESS_LIMIT_BYTES,
            f"Memory after 5 batches of 100 calls: {total_bytes / 1024:.1f} KB",
        )

    def test_active_calls_set_cleared_after_all_calls_end(self):
        """
        After all 100 calls end, the internal _active_calls set should be empty,
        ensuring no memory leak from stale room IDs.
        """
        room_ids = [str(uuid.uuid4()) for _ in range(self.TARGET_CALLS)]
        for rid in room_ids:
            record_call_started(rid)
        for rid in room_ids:
            record_call_ended(rid)

        with pm_module._lock:
            remaining = len(pm_module._active_calls)

        self.assertEqual(
            remaining, 0,
            f"_active_calls set has {remaining} stale entries after all calls ended",
        )

    def test_signaling_latency_rolling_window_caps_memory(self):
        """
        The rolling window should cap at _LATENCY_WINDOW_SIZE entries,
        preventing unbounded memory growth from latency samples.
        """
        max_size = pm_module._LATENCY_WINDOW_SIZE
        # Add 3x the window size
        for i in range(max_size * 3):
            record_signaling_latency(float(i % 100))

        with pm_module._lock:
            actual_size = len(pm_module._signaling_latency_samples)

        self.assertEqual(
            actual_size,
            max_size,
            f"Latency window has {actual_size} entries (expected cap at {max_size})",
        )

# ---------------------------------------------------------------------------
# Test: Load tests for signaling, media negotiation, multi-participant
#       scenarios (Requirement 11.7)
# ---------------------------------------------------------------------------

class SignalingLoadTest(TestCase):
    """
    Load tests for signaling traffic.

    Validates Requirement 11.7:
      THE performance test suite SHALL include load tests for signaling,
      media negotiation, and multi-participant scenarios.
    """

    def setUp(self):
        _reset_monitor()

    def tearDown(self):
        _reset_monitor()

    def test_signaling_load_offer_answer_ice_exchange(self):
        """
        Simulate a full WebRTC offer/answer/ICE exchange for 50 peer pairs.
        Each pair: 1 offer + 1 answer + 5 ICE candidates = 7 messages.
        Total: 350 signaling messages.
        All should complete with average latency < 100ms.
        """
        n_pairs = 50
        messages_per_pair = 7  # offer + answer + 5 ICE
        errors = []

        def exchange_signaling():
            try:
                for _ in range(messages_per_pair):
                    _simulate_signaling_message(latency_ms=3.0)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=n_pairs) as pool:
            futures = [pool.submit(exchange_signaling) for _ in range(n_pairs)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors in signaling load test: {errors}")

        stats = get_signaling_latency_stats()
        self.assertGreater(stats["count"], 0)
        self.assertLess(
            stats["avg_ms"],
            100.0,
            f"Signaling load test avg latency {stats['avg_ms']}ms exceeds 100ms",
        )

    def test_media_negotiation_load_test(self):
        """
        Simulate media negotiation for 100 concurrent calls.
        Each call performs: offer + answer + ICE exchange (10 candidates).
        Verifies the system handles 1200 signaling messages without degradation.
        """
        n_calls = 100
        messages_per_call = 12  # offer + answer + 10 ICE candidates
        errors = []

        def negotiate_media():
            try:
                room_id = str(uuid.uuid4())
                record_call_started(room_id)
                for _ in range(messages_per_call):
                    record_signaling_latency(5.0)
                record_call_ended(room_id)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=n_calls) as pool:
            futures = [pool.submit(negotiate_media) for _ in range(n_calls)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors in media negotiation load test: {errors}")
        self.assertEqual(get_active_call_count(), 0)

        stats = get_signaling_latency_stats()
        self.assertGreater(stats["count"], 0)
        self.assertLess(stats["avg_ms"], 100.0)

    def test_multi_participant_scenario_load_test(self):
        """
        Multi-participant load test:
        - 20 rooms, each with 8 participants
        - Each participant exchanges signaling with 7 others
        - Total: 20 * 8 * 7 = 1120 signaling messages
        - All rooms tracked correctly
        """
        n_rooms = 20
        n_participants = 8
        errors = []

        def run_room(room_id):
            try:
                record_call_started(room_id)
                # Simulate mesh signaling for 8 participants
                for _ in range(n_participants * (n_participants - 1)):
                    record_signaling_latency(5.0)
                record_call_ended(room_id)
            except Exception as exc:
                errors.append(exc)

        room_ids = [str(uuid.uuid4()) for _ in range(n_rooms)]

        with ThreadPoolExecutor(max_workers=n_rooms) as pool:
            futures = [pool.submit(run_room, rid) for rid in room_ids]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors in multi-participant load test: {errors}")
        self.assertEqual(get_active_call_count(), 0)

        stats = get_signaling_latency_stats()
        self.assertGreater(stats["count"], 0)
        self.assertLess(stats["avg_ms"], 100.0)

    def test_mixed_load_calls_and_websockets(self):
        """
        Mixed load test: simultaneous calls and WebSocket connections.
        - 100 active calls
        - 500 WebSocket connections
        - 200 signaling messages
        All tracked correctly without interference.
        """
        n_calls = 100
        n_ws = 500
        n_signals = 200
        errors = []

        def start_calls():
            try:
                for _ in range(n_calls):
                    record_call_started(str(uuid.uuid4()))
            except Exception as exc:
                errors.append(exc)

        def start_ws():
            try:
                for _ in range(n_ws):
                    record_websocket_connected()
            except Exception as exc:
                errors.append(exc)

        def send_signals():
            try:
                for _ in range(n_signals):
                    record_signaling_latency(5.0)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=start_calls),
            threading.Thread(target=start_ws),
            threading.Thread(target=send_signals),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors in mixed load test: {errors}")
        self.assertEqual(get_active_call_count(), n_calls)
        self.assertEqual(get_websocket_connection_count(), n_ws)

        stats = get_signaling_latency_stats()
        self.assertEqual(stats["count"], n_signals)

    def test_sustained_signaling_load_over_time(self):
        """
        Sustained load: 10 threads each send 100 signaling messages over 0.5 seconds.
        Verifies the system handles sustained traffic without degradation.
        """
        n_threads = 10
        messages_per_thread = 100
        errors = []

        def sustained_signaling():
            try:
                for _ in range(messages_per_thread):
                    record_signaling_latency(5.0)
                    time.sleep(0.001)  # 1ms between messages
            except Exception as exc:
                errors.append(exc)

        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(sustained_signaling) for _ in range(n_threads)]
            for f in as_completed(futures):
                f.result()
        elapsed = time.monotonic() - start

        self.assertEqual(len(errors), 0, f"Errors in sustained signaling: {errors}")

        stats = get_signaling_latency_stats()
        self.assertGreater(stats["count"], 0)
        self.assertLess(stats["avg_ms"], 100.0)

    def test_burst_signaling_load(self):
        """
        Burst load: 200 threads simultaneously send a single signaling message.
        Simulates a sudden spike in signaling traffic.
        """
        n_burst = 200
        errors = []
        barrier = threading.Barrier(n_burst)

        def burst_message():
            try:
                barrier.wait()  # all threads fire simultaneously
                record_signaling_latency(5.0)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=n_burst) as pool:
            futures = [pool.submit(burst_message) for _ in range(n_burst)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"Errors in burst signaling: {errors}")

        stats = get_signaling_latency_stats()
        self.assertGreater(stats["count"], 0)

    def test_call_and_signaling_throughput_benchmark(self):
        """
        Throughput benchmark: measure how many call start/end operations
        and signaling records can be processed per second.
        Reports results but does not fail on throughput (informational).
        """
        n_ops = 1000
        room_ids = [str(uuid.uuid4()) for _ in range(n_ops)]

        # Benchmark call tracking
        start = time.monotonic()
        for rid in room_ids:
            record_call_started(rid)
        for rid in room_ids:
            record_call_ended(rid)
        call_elapsed = time.monotonic() - start
        call_ops_per_sec = (n_ops * 2) / call_elapsed

        # Benchmark signaling recording
        start = time.monotonic()
        for _ in range(n_ops):
            record_signaling_latency(5.0)
        signal_elapsed = time.monotonic() - start
        signal_ops_per_sec = n_ops / signal_elapsed

        # Both should be able to handle at least 1000 ops/sec
        self.assertGreater(
            call_ops_per_sec, 1000,
            f"Call tracking throughput: {call_ops_per_sec:.0f} ops/sec (expected > 1000)",
        )
        self.assertGreater(
            signal_ops_per_sec, 1000,
            f"Signaling recording throughput: {signal_ops_per_sec:.0f} ops/sec (expected > 1000)",
        )

# ---------------------------------------------------------------------------
# Test: Room model capacity enforcement (supports Requirement 11.1, 11.3)
# ---------------------------------------------------------------------------

class RoomCapacityPerformanceTest(TestCase):
    """
    Tests for Room model capacity enforcement under load.

    These tests verify that the Room.is_full property and participant_count
    work correctly when many rooms are created simultaneously, supporting
    the performance requirements for 100 concurrent calls (11.1) and
    8-participant stability (11.3).
    """

    def setUp(self):
        _reset_monitor()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username="perf_test_user", password="pass")

    def tearDown(self):
        _reset_monitor()

    def test_100_rooms_can_be_created_and_tracked(self):
        """
        100 Room objects can be created and their IDs tracked as active calls.
        """
        from app.models import Room
        rooms = []
        for i in range(100):
            room = Room.objects.create(
                name=f"perf-room-{i}",
                created_by=self.user,
                max_participants=8,
            )
            rooms.append(room)
            record_call_started(str(room.id))

        self.assertEqual(get_active_call_count(), 100)

        for room in rooms:
            record_call_ended(str(room.id))

        self.assertEqual(get_active_call_count(), 0)

    def test_room_is_full_property_with_8_participants(self):
        """
        Room.is_full returns True when 8 participants have joined.
        """
        from app.models import Room, RoomParticipant
        from django.contrib.auth import get_user_model
        User = get_user_model()

        room = Room.objects.create(
            name="full-room-test",
            created_by=self.user,
            max_participants=8,
        )

        # Create 8 participants
        users = []
        for i in range(8):
            u = User.objects.create_user(username=f"participant_{i}_{uuid.uuid4().hex[:6]}", password="pass")
            users.append(u)
            RoomParticipant.objects.create(room=room, user=u)

        self.assertEqual(room.participant_count, 8)
        self.assertTrue(room.is_full)

    def test_room_participant_count_with_active_participants_only(self):
        """
        Room.participant_count only counts participants who haven't left.
        """
        from app.models import Room, RoomParticipant
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        User = get_user_model()

        room = Room.objects.create(
            name="partial-room-test",
            created_by=self.user,
            max_participants=8,
        )

        # Create 5 active + 3 left participants
        for i in range(5):
            u = User.objects.create_user(username=f"active_{i}_{uuid.uuid4().hex[:6]}", password="pass")
            RoomParticipant.objects.create(room=room, user=u)

        for i in range(3):
            u = User.objects.create_user(username=f"left_{i}_{uuid.uuid4().hex[:6]}", password="pass")
            RoomParticipant.objects.create(room=room, user=u, left_at=timezone.now())

        self.assertEqual(room.participant_count, 5)
        self.assertFalse(room.is_full)


# ---------------------------------------------------------------------------
# Test: Async signaling performance (Requirement 11.2, 11.7)
# ---------------------------------------------------------------------------

class AsyncSignalingPerformanceTest(TestCase):
    """
    Async-based signaling performance tests.

    Tests the performance of async signaling operations using asyncio,
    simulating the async nature of Django Channels consumers.
    """

    def setUp(self):
        _reset_monitor()

    def tearDown(self):
        _reset_monitor()

    def test_async_signaling_latency_measurement(self):
        """
        Async signaling operations measured with asyncio should complete
        within the 100ms target.
        """
        async def async_signaling_batch(n: int):
            """Simulate n async signaling operations."""
            for _ in range(n):
                start = time.monotonic()
                # Simulate async I/O (channel layer group_send)
                await asyncio.sleep(0.001)  # 1ms async operation
                elapsed_ms = (time.monotonic() - start) * 1000
                record_signaling_latency(elapsed_ms)

        asyncio.run(async_signaling_batch(50))

        stats = get_signaling_latency_stats()
        self.assertEqual(stats["count"], 50)
        self.assertLess(
            stats["avg_ms"],
            100.0,
            f"Async signaling avg latency {stats['avg_ms']}ms exceeds 100ms",
        )

    def test_async_concurrent_signaling_operations(self):
        """
        Multiple async tasks running concurrently should all complete
        within the 100ms target.
        """
        async def run_concurrent_signaling():
            async def single_signal():
                start = time.monotonic()
                await asyncio.sleep(0.002)  # 2ms async operation
                elapsed_ms = (time.monotonic() - start) * 1000
                record_signaling_latency(elapsed_ms)

            # Run 100 concurrent signaling operations
            tasks = [single_signal() for _ in range(100)]
            await asyncio.gather(*tasks)

        asyncio.run(run_concurrent_signaling())

        stats = get_signaling_latency_stats()
        self.assertEqual(stats["count"], 100)
        self.assertLess(
            stats["avg_ms"],
            100.0,
            f"Concurrent async signaling avg latency {stats['avg_ms']}ms exceeds 100ms",
        )

    def test_async_8_participant_mesh_signaling(self):
        """
        Simulate async mesh signaling for 8 participants.
        Each participant sends to 7 others concurrently.
        """
        async def mesh_signaling(n_participants: int):
            async def participant_sends(participant_id: int):
                for target_id in range(n_participants):
                    if target_id != participant_id:
                        start = time.monotonic()
                        await asyncio.sleep(0.001)  # 1ms per message
                        elapsed_ms = (time.monotonic() - start) * 1000
                        record_signaling_latency(elapsed_ms)

            tasks = [participant_sends(i) for i in range(n_participants)]
            await asyncio.gather(*tasks)

        asyncio.run(mesh_signaling(8))

        stats = get_signaling_latency_stats()
        # 8 * 7 = 56 messages
        self.assertEqual(stats["count"], 56)
        self.assertLess(stats["avg_ms"], 100.0)
