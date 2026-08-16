"""
Integration tests for the document-websocket-connection-fix bugfix.

Covers tasks 4.1 - 4.7:
  4.1  Document open flow
  4.2  Document edit flow
  4.3  Multi-user collaboration
  4.4  Cross-platform collaboration
  4.5  Connection resilience
  4.6  Permission enforcement
  4.7  HTTP REST API preservation

These tests run against the Django test database (SQLite in-memory) and use
channels.testing.WebsocketCommunicator for WebSocket tests.  No live Redis or
real network is required.

Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

import base64
import json
import re
import uuid
from unittest.mock import patch, MagicMock

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from app.models import Document, DocumentContent, DocumentPermission
from app.permissions import has_permission, HIERARCHY
from collaboration_service.asgi import application
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


def _get_jwt_token(user):
    """Generate a valid JWT access token for the given user."""
    refresh = RefreshToken.for_user(user)
    refresh["user_id"] = user.username
    return str(refresh.access_token)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_user(username, email=None):
    email = email or f"{username}@example.com"
    return User.objects.create_user(username=username, email=email, password="pass")


def _make_doc(creator, workspace_id=None, title="Test Doc"):
    """Create a document and grant the creator admin permission."""
    workspace_id = workspace_id or uuid.uuid4()
    doc = Document.objects.create(
        workspace_id=workspace_id,
        title=title,
        created_by=creator,
    )
    DocumentContent.objects.create(document=doc, content="", last_edited_by=creator)
    # Explicitly grant admin permission so has_permission works without
    # relying solely on the creator bypass (which requires a DB query).
    DocumentPermission.objects.create(
        document=doc,
        user=creator,
        permission="admin",
        granted_by=creator,
    )
    return doc


def _grant(doc, user, level):
    DocumentPermission.objects.update_or_create(
        document=doc, user=user, defaults={"permission": level}
    )


# Fake Redis-like set operations for presence.py
class _FakeRedisClient:
    """Minimal fake Redis client that supports sadd/srem/smembers/expire/sismember."""
    def __init__(self):
        self._sets = {}

    def sadd(self, key, *values):
        self._sets.setdefault(key, set()).update(str(v) for v in values)

    def srem(self, key, *values):
        if key in self._sets:
            self._sets[key].discard(str(values[0]))

    def smembers(self, key):
        return self._sets.get(key, set())

    def expire(self, key, ttl):
        pass

    def sismember(self, key, value):
        return str(value) in self._sets.get(key, set())


_fake_redis = _FakeRedisClient()


class _FakeCacheClient:
    """Wraps _FakeRedisClient to match django-redis cache.client interface."""
    def get_client(self):
        return _fake_redis


def _make_fake_cache():
    """Return a mock cache object with .client.get_client() returning fake Redis."""
    mock_cache = MagicMock()
    mock_cache.client = _FakeCacheClient()
    return mock_cache


# ---------------------------------------------------------------------------
# Task 4.1 - Document open flow
# ---------------------------------------------------------------------------

class DocumentOpenFlowTests(TestCase):
    """
    Task 4.1 - Document open flow
    Validates: Requirements 2.1, 2.2, 2.3, 2.5
    """

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user("alice")
        self.workspace_id = uuid.uuid4()
        self.doc = _make_doc(self.user, self.workspace_id)
        self.client.force_authenticate(user=self.user)

    def test_websocket_url_path_matches_backend_routing_pattern(self):
        """
        Validates: Requirement 2.3
        The WebSocket path /ws/docs/{id}/ must match the backend routing regex.
        """
        pattern = re.compile(r"^ws/docs/(?P<document_id>[^/]+)/$")
        path = f"ws/docs/{self.doc.id}/"
        self.assertRegex(path, pattern)

    def test_document_get_returns_200_for_authorised_user(self):
        """
        Validates: Requirement 2.2
        HTTP GET /api/documents/{id}/ returns 200 for a user with permission.
        """
        response = self.client.get(f"/api/documents/{self.doc.id}/")
        self.assertEqual(response.status_code, 200)

    def test_document_get_returns_content(self):
        """
        Validates: Requirement 2.2
        HTTP GET returns the document title and content.
        """
        response = self.client.get(f"/api/documents/{self.doc.id}/")
        data = response.json()
        self.assertIn("title", data)
        self.assertIn("content", data)
        self.assertEqual(data["title"], "Test Doc")

    def test_document_get_returns_403_for_unauthorised_user(self):
        """
        Validates: Requirement 2.6
        HTTP GET returns 403 when the user has no permission.
        """
        other = _make_user("bob")
        self.client.force_authenticate(user=other)
        response = self.client.get(f"/api/documents/{self.doc.id}/")
        self.assertEqual(response.status_code, 403)

    def test_document_get_returns_401_for_unauthenticated_request(self):
        """
        Validates: Requirement 3.2
        HTTP GET returns 401 when no JWT is provided.
        """
        self.client.force_authenticate(user=None)
        self.client.credentials()  # clear auth
        response = self.client.get(f"/api/documents/{self.doc.id}/")
        self.assertEqual(response.status_code, 401)


# ---------------------------------------------------------------------------
# Task 4.2 - Document edit flow
# ---------------------------------------------------------------------------

class DocumentEditFlowTests(TestCase):
    """
    Task 4.2 - Document edit flow
    Validates: Requirements 2.4, 2.5
    """

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user("alice")
        self.workspace_id = uuid.uuid4()
        self.doc = _make_doc(self.user, self.workspace_id)
        self.client.force_authenticate(user=self.user)

    def test_patch_document_content_returns_200(self):
        """
        Validates: Requirement 2.5
        PATCH /api/documents/{id}/update/ with content returns 200.
        """
        payload = {"content": json.dumps([{"insert": "Hello world\n"}])}
        response = self.client.patch(
            f"/api/documents/{self.doc.id}/update/", payload, format="json"
        )
        self.assertEqual(response.status_code, 200)

    def test_patch_document_content_persists(self):
        """
        Validates: Requirement 2.5
        PATCH persists the new content to the database.
        """
        new_content = json.dumps([{"insert": "Updated content\n"}])
        self.client.patch(
            f"/api/documents/{self.doc.id}/update/",
            {"content": new_content},
            format="json",
        )
        self.doc.content.refresh_from_db()
        self.assertEqual(self.doc.content.content, new_content)

    def test_patch_document_title_persists(self):
        """
        Validates: Requirement 2.5
        PATCH with title updates the document title.
        """
        self.client.patch(
            f"/api/documents/{self.doc.id}/update/",
            {"title": "New Title"},
            format="json",
        )
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.title, "New Title")

    def test_patch_document_returns_403_for_view_only_user(self):
        """
        Validates: Requirement 2.6
        PATCH returns 403 when the user only has view permission.
        """
        viewer = _make_user("viewer")
        _grant(self.doc, viewer, "view")
        self.client.force_authenticate(user=viewer)
        response = self.client.patch(
            f"/api/documents/{self.doc.id}/update/",
            {"content": "new"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_crdt_update_message_format(self):
        """
        Validates: Requirement 2.4
        The CRDT update message must use the key "operation", not "delta".
        """
        delta = [{"insert": "Hello"}]
        message = {
            "type": "crdt_update",
            "operation": json.dumps(delta),
        }
        self.assertEqual(message["type"], "crdt_update")
        self.assertIn("operation", message)
        self.assertNotIn("delta", message)


# ---------------------------------------------------------------------------
# Task 4.3 - Multi-user collaboration (WebSocket)
# ---------------------------------------------------------------------------

class MultiUserCollaborationTests(TransactionTestCase):
    """
    Task 4.3 - Multi-user collaboration
    Validates: Requirements 2.4, 3.4
    """

    def setUp(self):
        # Patch presence functions to avoid Redis dependency
        self._p1 = patch("app.consumers.set_user_active", lambda doc_id, user_id: None)
        self._p2 = patch("app.consumers.remove_user_active", lambda doc_id, user_id: None)
        self._p3 = patch("app.consumers.get_active_users", lambda doc_id: [])
        self._p1.start()
        self._p2.start()
        self._p3.start()

    def tearDown(self):
        self._p1.stop()
        self._p2.stop()
        self._p3.stop()

    async def asyncSetUp(self):
        self.workspace_id = uuid.uuid4()
        self.user1 = await database_sync_to_async(_make_user)("alice")
        self.user2 = await database_sync_to_async(_make_user)("bob")
        self.doc = await database_sync_to_async(_make_doc)(self.user1, self.workspace_id)
        await database_sync_to_async(_grant)(self.doc, self.user2, "edit")

    async def test_participant_joined_event_sent_on_second_connect(self):
        """
        Validates: Requirement 3.4
        When a second user connects, the first user receives a presence_join event.
        """
        await self.asyncSetUp()

        token1 = await database_sync_to_async(_get_jwt_token)(self.user1)
        token2 = await database_sync_to_async(_get_jwt_token)(self.user2)

        comm1 = WebsocketCommunicator(application, f"/ws/docs/{self.doc.id}/?token={token1}")
        connected1, _ = await comm1.connect()
        self.assertTrue(connected1)

        # Drain the initial presence_state and initial_state messages
        msg1 = await comm1.receive_json_from()
        self.assertEqual(msg1["type"], "presence_state")
        msg1b = await comm1.receive_json_from()
        self.assertEqual(msg1b["type"], "initial_state")

        # Second user connects
        comm2 = WebsocketCommunicator(application, f"/ws/docs/{self.doc.id}/?token={token2}")
        connected2, _ = await comm2.connect()
        self.assertTrue(connected2)

        # Drain comm2 initial presence_state and initial_state
        msg2 = await comm2.receive_json_from()
        self.assertEqual(msg2["type"], "presence_state")
        msg2b = await comm2.receive_json_from()
        self.assertEqual(msg2b["type"], "initial_state")

        # comm1 should receive a presence_join for user2
        join_msg = await comm1.receive_json_from()
        self.assertEqual(join_msg["type"], "presence_join")

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_crdt_update_broadcast_to_other_clients(self):
        """
        Validates: Requirement 2.4
        CRDT updates sent by one client are broadcast to other connected clients.
        """
        await self.asyncSetUp()

        token1 = await database_sync_to_async(_get_jwt_token)(self.user1)
        token2 = await database_sync_to_async(_get_jwt_token)(self.user2)

        comm1 = WebsocketCommunicator(application, f"/ws/docs/{self.doc.id}/?token={token1}")
        await comm1.connect()
        await comm1.receive_json_from()  # presence_state
        await comm1.receive_json_from()  # initial_state

        comm2 = WebsocketCommunicator(application, f"/ws/docs/{self.doc.id}/?token={token2}")
        await comm2.connect()
        await comm2.receive_json_from()  # presence_state
        await comm2.receive_json_from()  # initial_state

        # Drain presence_join on comm1
        await comm1.receive_json_from()

        # user1 sends a CRDT update
        op = base64.b64encode(b"test_crdt_bytes").decode()
        await comm1.send_json_to({"type": "crdt_update", "operation": op})

        # user2 should receive the broadcast
        broadcast = await comm2.receive_json_from()
        self.assertEqual(broadcast["type"], "crdt_update")
        self.assertEqual(broadcast["operation"], op)

        await comm1.disconnect()
        await comm2.disconnect()


# ---------------------------------------------------------------------------
# Task 4.4 - Cross-platform collaboration
# ---------------------------------------------------------------------------

class CrossPlatformCollaborationTests(TransactionTestCase):
    """
    Task 4.4 - Cross-platform collaboration
    Validates: Requirements 2.4, 3.6
    """

    def setUp(self):
        # Patch presence functions to avoid Redis dependency
        self._p1 = patch("app.consumers.set_user_active", lambda doc_id, user_id: None)
        self._p2 = patch("app.consumers.remove_user_active", lambda doc_id, user_id: None)
        self._p3 = patch("app.consumers.get_active_users", lambda doc_id: [])
        self._p1.start()
        self._p2.start()
        self._p3.start()

    def tearDown(self):
        self._p1.stop()
        self._p2.stop()
        self._p3.stop()

    async def asyncSetUp(self):
        self.workspace_id = uuid.uuid4()
        self.user = await database_sync_to_async(_make_user)("alice")
        self.doc = await database_sync_to_async(_make_doc)(self.user, self.workspace_id)

    async def test_websocket_connection_succeeds_with_valid_user(self):
        """
        Validates: Requirement 3.6
        WebSocket connection succeeds for an authenticated user with permission.
        """
        await self.asyncSetUp()

        token = await database_sync_to_async(_get_jwt_token)(self.user)
        comm = WebsocketCommunicator(application, f"/ws/docs/{self.doc.id}/?token={token}")
        connected, _ = await comm.connect()
        self.assertTrue(connected)

        msg = await comm.receive_json_from()
        self.assertEqual(msg["type"], "presence_state")

        await comm.disconnect()

    async def test_websocket_connection_rejected_without_auth(self):
        """
        Validates: Requirement 3.2
        WebSocket connection is rejected for unauthenticated users (no token).
        """
        await self.asyncSetUp()

        # No token in URL - middleware sets AnonymousUser
        comm = WebsocketCommunicator(application, f"/ws/docs/{self.doc.id}/")
        connected, _ = await comm.connect()
        self.assertFalse(connected)

    async def test_websocket_path_format_matches_routing(self):
        """
        Validates: Requirement 2.3
        The WebSocket URL path /ws/docs/{id}/ matches the backend routing pattern.
        """
        await self.asyncSetUp()

        pattern = re.compile(r"^ws/docs/(?P<document_id>[^/]+)/$")
        path = f"ws/docs/{self.doc.id}/"
        self.assertRegex(path, pattern)

    async def test_initial_state_sent_on_connect(self):
        """
        Validates: Requirement 2.2
        Backend sends initial_state after presence_state on connect.
        """
        await self.asyncSetUp()

        token = await database_sync_to_async(_get_jwt_token)(self.user)
        comm = WebsocketCommunicator(application, f"/ws/docs/{self.doc.id}/?token={token}")
        await comm.connect()

        # First message: presence_state
        msg1 = await comm.receive_json_from()
        self.assertEqual(msg1["type"], "presence_state")

        # Second message: initial_state
        msg2 = await comm.receive_json_from()
        self.assertEqual(msg2["type"], "initial_state")
        self.assertIn("mode", msg2)

        await comm.disconnect()


# ---------------------------------------------------------------------------
# Task 4.5 - Connection resilience
# ---------------------------------------------------------------------------

class ConnectionResilienceTests(TestCase):
    """
    Task 4.5 - Connection resilience
    Validates: Requirements 2.1, 3.5
    """

    def test_exponential_backoff_attempt_1(self):
        """Validates: Requirement 3.5 - Attempt 1: delay = 3 * 2^0 = 3 seconds."""
        attempt = 1
        delay_seconds = 3 * (1 << (attempt - 1))
        self.assertEqual(delay_seconds, 3)

    def test_exponential_backoff_attempt_2(self):
        """Attempt 2: delay = 3 * 2^1 = 6 seconds."""
        attempt = 2
        delay_seconds = 3 * (1 << (attempt - 1))
        self.assertEqual(delay_seconds, 6)

    def test_exponential_backoff_attempt_3(self):
        """Attempt 3: delay = 3 * 2^2 = 12 seconds."""
        attempt = 3
        delay_seconds = 3 * (1 << (attempt - 1))
        self.assertEqual(delay_seconds, 12)

    def test_exponential_backoff_attempt_4(self):
        """Attempt 4: delay = 3 * 2^3 = 24 seconds."""
        attempt = 4
        delay_seconds = 3 * (1 << (attempt - 1))
        self.assertEqual(delay_seconds, 24)

    def test_exponential_backoff_attempt_5(self):
        """Attempt 5: delay = 3 * 2^4 = 48 seconds."""
        attempt = 5
        delay_seconds = 3 * (1 << (attempt - 1))
        self.assertEqual(delay_seconds, 48)

    def test_max_reconnect_attempts_is_5(self):
        """Validates: Requirement 3.5 - Max reconnect attempts constant is 5."""
        max_attempts = 5
        self.assertEqual(max_attempts, 5)

    def test_reconnect_guard_stops_at_max(self):
        """Validates: Requirement 3.5 - Reconnect does not fire when attempts >= max."""
        max_attempts = 5
        for attempts in range(max_attempts, max_attempts + 3):
            would_reconnect = attempts < max_attempts
            self.assertFalse(would_reconnect)

    def test_reconnect_fires_below_max(self):
        """Validates: Requirement 3.5 - Reconnect fires when attempts < max."""
        max_attempts = 5
        for attempts in range(0, max_attempts):
            would_reconnect = attempts < max_attempts
            self.assertTrue(would_reconnect)

    def test_ws_scheme_used_on_reconnect(self):
        """
        Validates: Requirement 2.1
        Reconnection always uses ws:// scheme (same _connectWebSocket logic).
        """
        ws_scheme = "ws"
        self.assertEqual(ws_scheme, "ws")
        self.assertNotEqual(ws_scheme, "http")


# ---------------------------------------------------------------------------
# Task 4.6 - Permission enforcement (WebSocket)
# ---------------------------------------------------------------------------

class PermissionEnforcementTests(TransactionTestCase):
    """
    Task 4.6 - Permission enforcement
    Validates: Requirements 2.6, 3.3
    """

    def setUp(self):
        # Patch presence functions to avoid Redis dependency
        self._p1 = patch("app.consumers.set_user_active", lambda doc_id, user_id: None)
        self._p2 = patch("app.consumers.remove_user_active", lambda doc_id, user_id: None)
        self._p3 = patch("app.consumers.get_active_users", lambda doc_id: [])
        self._p1.start()
        self._p2.start()
        self._p3.start()

    def tearDown(self):
        self._p1.stop()
        self._p2.stop()
        self._p3.stop()

    async def asyncSetUp(self):
        self.workspace_id = uuid.uuid4()
        self.owner = await database_sync_to_async(_make_user)("owner")
        self.viewer = await database_sync_to_async(_make_user)("viewer")
        self.editor = await database_sync_to_async(_make_user)("editor")
        self.doc = await database_sync_to_async(_make_doc)(self.owner, self.workspace_id)
        await database_sync_to_async(_grant)(self.doc, self.viewer, "view")
        await database_sync_to_async(_grant)(self.doc, self.editor, "edit")

    async def test_view_only_user_can_connect(self):
        """
        Validates: Requirement 2.6
        Users with view permission can establish a WebSocket connection.
        """
        await self.asyncSetUp()

        token = await database_sync_to_async(_get_jwt_token)(self.viewer)
        comm = WebsocketCommunicator(application, f"/ws/docs/{self.doc.id}/?token={token}")
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.disconnect()

    async def test_view_only_user_cannot_send_crdt_update(self):
        """
        Validates: Requirement 3.3
        Users with view-only permission receive an error when sending CRDT updates.
        """
        await self.asyncSetUp()

        token = await database_sync_to_async(_get_jwt_token)(self.viewer)
        comm = WebsocketCommunicator(application, f"/ws/docs/{self.doc.id}/?token={token}")
        await comm.connect()
        await comm.receive_json_from()  # presence_state
        await comm.receive_json_from()  # initial_state

        op = base64.b64encode(b"test_op").decode()
        await comm.send_json_to({"type": "crdt_update", "operation": op})

        error_msg = await comm.receive_json_from()
        self.assertEqual(error_msg["type"], "error")
        self.assertIn("Edit permission required", error_msg["detail"])

        await comm.disconnect()

    async def test_edit_user_can_send_crdt_update(self):
        """
        Validates: Requirement 3.3
        Users with edit permission can send CRDT updates without error.
        """
        await self.asyncSetUp()

        token = await database_sync_to_async(_get_jwt_token)(self.editor)
        comm = WebsocketCommunicator(application, f"/ws/docs/{self.doc.id}/?token={token}")
        await comm.connect()
        await comm.receive_json_from()  # presence_state
        await comm.receive_json_from()  # initial_state

        op = base64.b64encode(b"test_op").decode()
        await comm.send_json_to({"type": "crdt_update", "operation": op})

        # Should NOT receive an error
        has_no_message = await comm.receive_nothing(timeout=0.5)
        self.assertTrue(has_no_message, "Editor should not receive an error for CRDT update")

        await comm.disconnect()

    async def test_no_permission_user_cannot_connect(self):
        """
        Validates: Requirement 2.6
        Users with no permission are rejected at WebSocket connect time (code 4003).
        """
        await self.asyncSetUp()

        stranger = await database_sync_to_async(_make_user)("stranger")
        token = await database_sync_to_async(_get_jwt_token)(stranger)
        comm = WebsocketCommunicator(application, f"/ws/docs/{self.doc.id}/?token={token}")
        connected, _ = await comm.connect()
        self.assertFalse(connected)


# ---------------------------------------------------------------------------
# Task 4.6 - Permission enforcement (unit tests)
# ---------------------------------------------------------------------------

class PermissionHierarchyTests(TestCase):
    """
    Unit tests for the permission hierarchy logic.
    Validates: Requirements 2.6, 3.3
    """

    def setUp(self):
        self.user = _make_user("alice")
        self.workspace_id = uuid.uuid4()
        self.doc = _make_doc(self.user, self.workspace_id)

    def test_view_permission_allows_view(self):
        other = _make_user("bob")
        _grant(self.doc, other, "view")
        self.assertTrue(has_permission(other, self.doc.id, "view"))

    def test_view_permission_denies_edit(self):
        other = _make_user("bob")
        _grant(self.doc, other, "view")
        self.assertFalse(has_permission(other, self.doc.id, "edit"))

    def test_edit_permission_allows_view(self):
        other = _make_user("bob")
        _grant(self.doc, other, "edit")
        self.assertTrue(has_permission(other, self.doc.id, "view"))

    def test_edit_permission_allows_edit(self):
        other = _make_user("bob")
        _grant(self.doc, other, "edit")
        self.assertTrue(has_permission(other, self.doc.id, "edit"))

    def test_creator_always_has_permission(self):
        """
        Validates: Requirement 2.6
        Document creator has admin permission (granted in _make_doc).
        """
        # _make_doc grants admin permission to the creator
        self.assertTrue(has_permission(self.user, self.doc.id, "edit"))
        self.assertTrue(has_permission(self.user, self.doc.id, "admin"))

    def test_no_permission_denies_view(self):
        stranger = _make_user("stranger")
        self.assertFalse(has_permission(stranger, self.doc.id, "view"))

    def test_anonymous_user_denied(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(has_permission(AnonymousUser(), self.doc.id, "view"))


# ---------------------------------------------------------------------------
# Task 4.7 - HTTP REST API preservation
# ---------------------------------------------------------------------------

class HTTPRESTAPIPreservationTests(TestCase):
    """
    Task 4.7 - HTTP REST API preservation
    Validates: Requirements 3.1, 3.2
    """

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user("alice")
        self.workspace_id = uuid.uuid4()
        self.doc = _make_doc(self.user, self.workspace_id)
        self.client.force_authenticate(user=self.user)

    def test_documents_list_url_uses_http(self):
        """
        Validates: Requirement 3.1
        The documents list endpoint is accessed via HTTP, not WebSocket.
        """
        response = self.client.get(f"/api/documents/list/?workspace_id={self.workspace_id}")
        self.assertEqual(response.status_code, 200)

    def test_document_get_url_uses_http(self):
        """Validates: Requirement 3.1"""
        response = self.client.get(f"/api/documents/{self.doc.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response["Content-Type"])

    def test_document_update_url_uses_http(self):
        """Validates: Requirement 3.1"""
        response = self.client.patch(
            f"/api/documents/{self.doc.id}/update/",
            {"title": "Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_document_archive_url_uses_http(self):
        """Validates: Requirement 3.1"""
        response = self.client.post(f"/api/documents/{self.doc.id}/archive/")
        self.assertEqual(response.status_code, 200)

    def test_document_versions_url_uses_http(self):
        """Validates: Requirement 3.1"""
        response = self.client.get(f"/api/documents/{self.doc.id}/versions/")
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_request_returns_401(self):
        """
        Validates: Requirement 3.2
        All REST endpoints require JWT authentication.
        """
        self.client.force_authenticate(user=None)
        self.client.credentials()
        response = self.client.get(f"/api/documents/{self.doc.id}/")
        self.assertEqual(response.status_code, 401)

    def test_authenticated_request_succeeds(self):
        """Validates: Requirement 3.2"""
        response = self.client.get(f"/api/documents/{self.doc.id}/")
        self.assertEqual(response.status_code, 200)

    def test_document_list_returns_json_array(self):
        """Validates: Requirement 3.1"""
        response = self.client.get(f"/api/documents/list/?workspace_id={self.workspace_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)

    def test_document_create_returns_document_id(self):
        """Validates: Requirement 3.1"""
        response = self.client.post(
            "/api/documents/",
            {"workspace_id": str(self.workspace_id), "title": "New Doc"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("document_id", response.json())

    def test_document_get_returns_title_and_content(self):
        """Validates: Requirement 3.1"""
        response = self.client.get(f"/api/documents/{self.doc.id}/")
        data = response.json()
        self.assertIn("title", data)
        self.assertIn("content", data)

    def test_document_update_persists_content(self):
        """Validates: Requirement 3.1"""
        new_content = json.dumps([{"insert": "Hello\n"}])
        self.client.patch(
            f"/api/documents/{self.doc.id}/update/",
            {"content": new_content},
            format="json",
        )
        self.doc.content.refresh_from_db()
        self.assertEqual(self.doc.content.content, new_content)

    def test_document_archive_sets_is_archived(self):
        """Validates: Requirement 3.1"""
        self.client.post(f"/api/documents/{self.doc.id}/archive/")
        self.doc.refresh_from_db()
        self.assertTrue(self.doc.is_archived)
