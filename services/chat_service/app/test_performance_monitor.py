"""
Tests for the backend performance monitoring module.
Requirements: 11.1, 11.2, 11.4
"""

import time
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model

from .performance_monitor import (
    record_call_started,
    record_call_ended,
    get_active_call_count,
    get_active_call_ids,
    record_websocket_connected,
    record_websocket_disconnected,
    get_websocket_connection_count,
    record_signaling_latency,
    get_signaling_latency_stats,
    measure_signaling_latency,
    get_metrics_snapshot,
    _active_calls,
    _signaling_latency_samples,
)
import app.performance_monitor as pm_module

User = get_user_model()


def _reset_state():
    """Reset all in-process counters between tests."""
    with pm_module._lock:
        pm_module._active_calls.clear()
        pm_module._websocket_connection_count = 0
        pm_module._signaling_latency_samples.clear()


class ActiveCallTrackingTests(TestCase):
    """Tests for active call count tracking (Requirement 11.1)."""

    def setUp(self):
        _reset_state()

    def test_initial_active_call_count_is_zero(self):
        self.assertEqual(get_active_call_count(), 0)

    def test_record_call_started_increments_count(self):
        record_call_started("room-1")
        self.assertEqual(get_active_call_count(), 1)

    def test_record_multiple_calls_started(self):
        record_call_started("room-1")
        record_call_started("room-2")
        record_call_started("room-3")
        self.assertEqual(get_active_call_count(), 3)

    def test_record_call_ended_decrements_count(self):
        record_call_started("room-1")
        record_call_started("room-2")
        record_call_ended("room-1")
        self.assertEqual(get_active_call_count(), 1)

    def test_record_call_ended_for_unknown_room_is_noop(self):
        record_call_started("room-1")
        record_call_ended("room-nonexistent")
        self.assertEqual(get_active_call_count(), 1)

    def test_duplicate_call_started_does_not_double_count(self):
        record_call_started("room-1")
        record_call_started("room-1")  # same room
        self.assertEqual(get_active_call_count(), 1)

    def test_get_active_call_ids_returns_all_active_rooms(self):
        record_call_started("room-a")
        record_call_started("room-b")
        ids = get_active_call_ids()
        self.assertIn("room-a", ids)
        self.assertIn("room-b", ids)
        self.assertEqual(len(ids), 2)

    def test_get_active_call_ids_excludes_ended_rooms(self):
        record_call_started("room-a")
        record_call_started("room-b")
        record_call_ended("room-a")
        ids = get_active_call_ids()
        self.assertNotIn("room-a", ids)
        self.assertIn("room-b", ids)

    def test_room_id_is_coerced_to_string(self):
        """record_call_started should accept non-string room IDs."""
        import uuid
        room_uuid = uuid.uuid4()
        record_call_started(room_uuid)
        self.assertEqual(get_active_call_count(), 1)
        record_call_ended(room_uuid)
        self.assertEqual(get_active_call_count(), 0)


class WebSocketConnectionTrackingTests(TestCase):
    """Tests for WebSocket connection count tracking (Requirements 11.2, 11.4)."""

    def setUp(self):
        _reset_state()

    def test_initial_connection_count_is_zero(self):
        self.assertEqual(get_websocket_connection_count(), 0)

    def test_record_connected_increments_count(self):
        record_websocket_connected()
        self.assertEqual(get_websocket_connection_count(), 1)

    def test_record_multiple_connections(self):
        for _ in range(5):
            record_websocket_connected()
        self.assertEqual(get_websocket_connection_count(), 5)

    def test_record_disconnected_decrements_count(self):
        record_websocket_connected()
        record_websocket_connected()
        record_websocket_disconnected()
        self.assertEqual(get_websocket_connection_count(), 1)

    def test_record_disconnected_does_not_go_below_zero(self):
        record_websocket_disconnected()  # no connections open
        self.assertEqual(get_websocket_connection_count(), 0)

    def test_connect_then_disconnect_returns_to_zero(self):
        record_websocket_connected()
        record_websocket_disconnected()
        self.assertEqual(get_websocket_connection_count(), 0)


class SignalingLatencyTrackingTests(TestCase):
    """Tests for signaling message latency tracking (Requirement 11.2)."""

    def setUp(self):
        _reset_state()

    def test_initial_stats_are_empty(self):
        stats = get_signaling_latency_stats()
        self.assertEqual(stats["count"], 0)
        self.assertIsNone(stats["avg_ms"])
        self.assertIsNone(stats["min_ms"])
        self.assertIsNone(stats["max_ms"])
        self.assertIsNone(stats["p95_ms"])
        self.assertIsNone(stats["p99_ms"])

    def test_record_single_sample(self):
        record_signaling_latency(50.0)
        stats = get_signaling_latency_stats()
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["avg_ms"], 50.0)
        self.assertEqual(stats["min_ms"], 50.0)
        self.assertEqual(stats["max_ms"], 50.0)

    def test_record_multiple_samples_calculates_avg(self):
        record_signaling_latency(10.0)
        record_signaling_latency(20.0)
        record_signaling_latency(30.0)
        stats = get_signaling_latency_stats()
        self.assertEqual(stats["count"], 3)
        self.assertAlmostEqual(stats["avg_ms"], 20.0, places=1)
        self.assertEqual(stats["min_ms"], 10.0)
        self.assertEqual(stats["max_ms"], 30.0)

    def test_p95_and_p99_percentiles(self):
        # Add 100 samples: 1ms to 100ms
        for i in range(1, 101):
            record_signaling_latency(float(i))
        stats = get_signaling_latency_stats()
        # p95 should be around 95ms
        self.assertGreaterEqual(stats["p95_ms"], 90.0)
        self.assertLessEqual(stats["p95_ms"], 100.0)
        # p99 should be around 99ms
        self.assertGreaterEqual(stats["p99_ms"], 95.0)
        self.assertLessEqual(stats["p99_ms"], 100.0)

    def test_rolling_window_caps_at_max_size(self):
        max_size = pm_module._LATENCY_WINDOW_SIZE
        for i in range(max_size + 50):
            record_signaling_latency(float(i))
        with pm_module._lock:
            actual_size = len(pm_module._signaling_latency_samples)
        self.assertEqual(actual_size, max_size)

    def test_rolling_window_drops_oldest_samples(self):
        max_size = pm_module._LATENCY_WINDOW_SIZE
        # Fill window with 1.0
        for _ in range(max_size):
            record_signaling_latency(1.0)
        # Add one more with a distinct value
        record_signaling_latency(999.0)
        with pm_module._lock:
            samples = list(pm_module._signaling_latency_samples)
        # The oldest 1.0 should have been dropped; 999.0 should be the last
        self.assertEqual(len(samples), max_size)
        self.assertEqual(samples[-1], 999.0)


class MeasureSignalingLatencyContextManagerTests(TestCase):
    """Tests for the measure_signaling_latency context manager."""

    def setUp(self):
        _reset_state()

    def test_records_a_latency_sample_after_block(self):
        with measure_signaling_latency():
            time.sleep(0.001)  # 1ms sleep
        stats = get_signaling_latency_stats()
        self.assertEqual(stats["count"], 1)
        # Should be at least 1ms
        self.assertGreater(stats["avg_ms"], 0)

    def test_records_sample_even_when_exception_is_raised(self):
        try:
            with measure_signaling_latency():
                raise ValueError("test error")
        except ValueError:
            pass
        stats = get_signaling_latency_stats()
        self.assertEqual(stats["count"], 1)


class MetricsSnapshotTests(TestCase):
    """Tests for the aggregate metrics snapshot."""

    def setUp(self):
        _reset_state()

    def test_snapshot_contains_all_keys(self):
        snapshot = get_metrics_snapshot()
        self.assertIn("active_calls", snapshot)
        self.assertIn("websocket_connections", snapshot)
        self.assertIn("signaling_latency", snapshot)

    def test_snapshot_reflects_current_state(self):
        record_call_started("room-x")
        record_websocket_connected()
        record_websocket_connected()
        record_signaling_latency(42.0)

        snapshot = get_metrics_snapshot()
        self.assertEqual(snapshot["active_calls"], 1)
        self.assertEqual(snapshot["websocket_connections"], 2)
        self.assertEqual(snapshot["signaling_latency"]["count"], 1)
        self.assertEqual(snapshot["signaling_latency"]["avg_ms"], 42.0)


class PerformanceMetricsAPITests(TestCase):
    """Tests for the GET /api/metrics/ endpoint."""

    def setUp(self):
        _reset_state()
        self.user = User.objects.create_user(username="testuser", password="pass")

    def test_metrics_endpoint_returns_200(self):
        from .views import performance_metrics
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get("/api/metrics/")
        # Force authentication so the IsAuthenticated permission check passes
        request.user = self.user

        # Bypass DRF authentication by calling the view with force_authenticate
        from rest_framework.test import force_authenticate
        force_authenticate(request, user=self.user)

        response = performance_metrics(request)
        self.assertEqual(response.status_code, 200)

    def test_metrics_endpoint_returns_correct_structure(self):
        from .views import performance_metrics
        from rest_framework.test import APIRequestFactory, force_authenticate

        record_call_started("room-test")
        record_websocket_connected()

        factory = APIRequestFactory()
        request = factory.get("/api/metrics/")
        force_authenticate(request, user=self.user)

        response = performance_metrics(request)
        # DRF Response.data is a dict — no need to render to JSON
        data = response.data
        self.assertIn("active_calls", data)
        self.assertIn("websocket_connections", data)
        self.assertIn("signaling_latency", data)
        self.assertEqual(data["active_calls"], 1)
        self.assertEqual(data["websocket_connections"], 1)
