"""
Security tests for the Chat Service video call feature.

Tests cover:
- Unauthorized room access rejection (Requirement 10.2, 10.3)
- Message origin validation (Requirement 10.4)
- Rate limiting enforcement (Requirement 10.4)

Requirements tested:
- 10.2: THE Chat_Service SHALL validate user authentication before allowing call access
- 10.3: THE Chat_Service SHALL verify Call_Room membership before allowing participants to join
- 10.4: THE Signaling_Server SHALL validate message origin before relaying signaling data
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import path
from asgiref.sync import sync_to_async
from unittest.mock import patch
import json

from .models import Room, RoomParticipant, Channel, ChannelMember
from .consumers import ChatConsumer

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Unauthorized Room Access Rejection (Requirements 10.2, 10.3)
# ─────────────────────────────────────────────────────────────────────────────

class UnauthenticatedRoomAccessTestCase(TestCase):
    """
    Test that unauthenticated users are rejected from all room API endpoints.

    Validates Requirement 10.2: THE Chat_Service SHALL validate user authentication
    before allowing call access.
    """

    def setUp(self):
        self.client = APIClient()  # No authentication
        self.owner = User.objects.create_user(username='owner', password='pass123')

        self.room = Room.objects.create(
            name='Secure Room',
            created_by=self.owner,
            is_active=True,
        )
        RoomParticipant.objects.create(room=self.room, user=self.owner)

    def test_unauthenticated_list_rooms_rejected(self):
        """Unauthenticated GET /api/rooms/ must return 401."""
        response = self.client.get('/api/rooms/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_create_room_rejected(self):
        """Unauthenticated POST /api/rooms/ must return 401."""
        response = self.client.post('/api/rooms/', {'name': 'Hack Room'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_room_detail_rejected(self):
        """Unauthenticated GET /api/rooms/{id}/ must return 401."""
        response = self.client.get(f'/api/rooms/{self.room.id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_join_room_rejected(self):
        """Unauthenticated POST /api/rooms/{id}/join/ must return 401."""
        response = self.client.post(f'/api/rooms/{self.room.id}/join/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_leave_room_rejected(self):
        """Unauthenticated POST /api/rooms/{id}/leave/ must return 401."""
        response = self.client.post(f'/api/rooms/{self.room.id}/leave/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_invite_to_room_rejected(self):
        """Unauthenticated POST /api/rooms/{id}/invite/ must return 401."""
        response = self.client.post(
            f'/api/rooms/{self.room.id}/invite/',
            {'user_ids': []},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_list_participants_rejected(self):
        """Unauthenticated GET /api/rooms/{id}/participants/ must return 401."""
        response = self.client.get(f'/api/rooms/{self.room.id}/participants/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_update_participant_state_rejected(self):
        """Unauthenticated PATCH /api/rooms/{id}/participants/{user_id}/ must return 401."""
        response = self.client.patch(
            f'/api/rooms/{self.room.id}/participants/{self.owner.id}/',
            {'is_muted': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_call_history_rejected(self):
        """Unauthenticated GET /api/call-history/ must return 401."""
        response = self.client.get('/api/call-history/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_ice_servers_rejected(self):
        """Unauthenticated GET /api/ice-servers/ must return 401."""
        response = self.client.get('/api/ice-servers/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RoomMembershipEnforcementTestCase(TestCase):
    """
    Test that room membership is verified before allowing participants to join
    or perform actions.

    Validates Requirement 10.3: THE Chat_Service SHALL verify Call_Room membership
    before allowing participants to join.
    """

    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username='owner', password='pass123')
        self.outsider = User.objects.create_user(username='outsider', password='pass123')
        self.member = User.objects.create_user(username='member', password='pass123')

        self.room = Room.objects.create(
            name='Members Only Room',
            created_by=self.owner,
            is_active=True,
        )
        RoomParticipant.objects.create(room=self.room, user=self.owner)
        RoomParticipant.objects.create(room=self.room, user=self.member)

    def test_non_member_cannot_invite_others(self):
        """
        A user who is not in the room cannot invite others.
        Validates Requirement 10.3.
        """
        self.client.force_authenticate(user=self.outsider)
        response = self.client.post(
            f'/api/rooms/{self.room.id}/invite/',
            {'user_ids': [str(self.outsider.id)]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_cannot_update_participant_state(self):
        """
        A user who is not an active participant cannot update participant state.
        Validates Requirement 10.3.
        """
        self.client.force_authenticate(user=self.outsider)
        response = self.client.patch(
            f'/api/rooms/{self.room.id}/participants/{self.outsider.id}/',
            {'is_muted': True},
            format='json',
        )
        # Either 403 (not authorized) or 400 (not an active participant)
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST],
        )

    def test_member_cannot_update_another_members_state(self):
        """
        A participant can only update their own state, not another participant's.
        Validates Requirement 10.3.
        """
        self.client.force_authenticate(user=self.member)
        response = self.client.patch(
            f'/api/rooms/{self.room.id}/participants/{self.owner.id}/',
            {'is_muted': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_leave_room_not_joined(self):
        """
        A user who never joined cannot leave a room.
        Validates Requirement 10.3.
        """
        self.client.force_authenticate(user=self.outsider)
        response = self.client.post(f'/api/rooms/{self.room.id}/leave/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_join_inactive_room(self):
        """
        A user cannot join a room that has ended.
        Validates Requirement 10.3.
        """
        from django.utils import timezone
        inactive_room = Room.objects.create(
            name='Ended Room',
            created_by=self.owner,
            is_active=False,
            ended_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.outsider)
        response = self.client.post(f'/api/rooms/{inactive_room.id}/join/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_join_nonexistent_room(self):
        """
        Joining a room that does not exist returns 404.
        Validates Requirement 10.3.
        """
        import uuid
        fake_id = uuid.uuid4()
        self.client.force_authenticate(user=self.outsider)
        response = self.client.post(f'/api/rooms/{fake_id}/join/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Message Origin Validation (Requirement 10.4)
# ─────────────────────────────────────────────────────────────────────────────

class MessageOriginValidationTestCase(TestCase):
    """
    Test that the Signaling_Server validates message origin before relaying
    signaling data.

    Validates Requirement 10.4: THE Signaling_Server SHALL validate message origin
    before relaying signaling data.
    """

    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.user3 = User.objects.create_user(username='user3', password='pass123')

        self.channel = Channel.objects.create(name='test-channel-origin')
        ChannelMember.objects.create(channel=self.channel, user=self.user1)
        ChannelMember.objects.create(channel=self.channel, user=self.user2)
        ChannelMember.objects.create(channel=self.channel, user=self.user3)

        self.room = Room.objects.create(
            name='Origin Test Room',
            created_by=self.user1,
            is_active=True,
        )
        RoomParticipant.objects.create(room=self.room, user=self.user1)
        RoomParticipant.objects.create(room=self.room, user=self.user2)

    async def _connect(self, user):
        """Connect a user to the WebSocket and consume the 'connected' message."""
        app = URLRouter([
            path('ws/chat/<str:channel_id>/', ChatConsumer.as_asgi()),
        ])
        comm = WebsocketCommunicator(app, f'/ws/chat/{self.channel.id}/')
        comm.scope['user'] = user
        comm.scope['url_route'] = {'kwargs': {'channel_id': str(self.channel.id)}}
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        # Consume the 'connected' handshake message
        msg = await comm.receive_json_from()
        self.assertEqual(msg['type'], 'connected')
        return comm

    async def test_spoofed_from_user_id_rejected(self):
        """
        A client that sends a webrtc_offer with a spoofed from_user_id
        (different from the authenticated user) must receive an error.

        Validates Requirement 10.4.
        """
        comm1 = await self._connect(self.user1)
        try:
            # user1 tries to impersonate user2 by setting from_user_id to user2's id
            await comm1.send_json_to({
                'type': 'webrtc_offer',
                'room_id': str(self.room.id),
                'from_user_id': str(self.user2.id),  # spoofed!
                'to_user_id': str(self.user2.id),
                'sdp': {'type': 'offer', 'sdp': 'v=0\r\n'},
            })

            response = await comm1.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'error')
            self.assertIn('from_user_id', response['detail'].lower())
        finally:
            await comm1.disconnect()

    async def test_non_room_member_cannot_send_offer(self):
        """
        A user who is not a member of the room cannot send a WebRTC offer.

        Validates Requirement 10.4.
        """
        # user3 is NOT in the room
        comm3 = await self._connect(self.user3)
        try:
            await comm3.send_json_to({
                'type': 'webrtc_offer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.user1.id),
                'sdp': {'type': 'offer', 'sdp': 'v=0\r\n'},
            })

            response = await comm3.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'error')
            self.assertIn('not a member', response['detail'].lower())
        finally:
            await comm3.disconnect()

    async def test_non_room_member_cannot_send_answer(self):
        """
        A user who is not a member of the room cannot send a WebRTC answer.

        Validates Requirement 10.4.
        """
        comm3 = await self._connect(self.user3)
        try:
            await comm3.send_json_to({
                'type': 'webrtc_answer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.user1.id),
                'sdp': {'type': 'answer', 'sdp': 'v=0\r\n'},
            })

            response = await comm3.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'error')
            self.assertIn('not a member', response['detail'].lower())
        finally:
            await comm3.disconnect()

    async def test_non_room_member_cannot_send_ice_candidate(self):
        """
        A user who is not a member of the room cannot send ICE candidates.

        Validates Requirement 10.4.
        """
        comm3 = await self._connect(self.user3)
        try:
            await comm3.send_json_to({
                'type': 'webrtc_ice',
                'room_id': str(self.room.id),
                'to_user_id': str(self.user1.id),
                'candidate': {
                    'candidate': 'candidate:1 1 UDP 2130706431 192.168.1.1 54321 typ host',
                    'sdpMid': 'audio',
                    'sdpMLineIndex': 0,
                },
            })

            response = await comm3.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'error')
            self.assertIn('not a member', response['detail'].lower())
        finally:
            await comm3.disconnect()

    async def test_offer_to_non_room_member_rejected(self):
        """
        A room member cannot send a WebRTC offer to a user who is not in the room.
        This prevents signaling data from leaking to non-participants.

        Validates Requirement 10.4.
        """
        comm1 = await self._connect(self.user1)
        try:
            # user3 is not in the room
            await comm1.send_json_to({
                'type': 'webrtc_offer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.user3.id),
                'sdp': {'type': 'offer', 'sdp': 'v=0\r\n'},
            })

            response = await comm1.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'error')
            self.assertIn('not a member', response['detail'].lower())
        finally:
            await comm1.disconnect()

    async def test_unauthenticated_websocket_rejected(self):
        """
        An unauthenticated WebSocket connection must be closed immediately.

        Validates Requirement 10.2.
        """
        from django.contrib.auth.models import AnonymousUser

        app = URLRouter([
            path('ws/chat/<str:channel_id>/', ChatConsumer.as_asgi()),
        ])
        comm = WebsocketCommunicator(app, f'/ws/chat/{self.channel.id}/')
        comm.scope['user'] = AnonymousUser()
        comm.scope['url_route'] = {'kwargs': {'channel_id': str(self.channel.id)}}

        connected, _ = await comm.connect()
        # The consumer should reject the connection
        self.assertFalse(connected)

    async def test_invalid_sdp_data_rejected(self):
        """
        Signaling messages with invalid/oversized SDP data are rejected.

        Validates Requirement 10.4 (sanitize user-provided data).
        """
        comm1 = await self._connect(self.user1)
        try:
            # Send an SDP that exceeds the 50KB size limit
            oversized_sdp = 'x' * 60000
            await comm1.send_json_to({
                'type': 'webrtc_offer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.user2.id),
                'sdp': {'type': 'offer', 'sdp': oversized_sdp},
            })

            response = await comm1.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'error')
        finally:
            await comm1.disconnect()

    async def test_invalid_sdp_type_rejected(self):
        """
        Signaling messages with an invalid SDP type are rejected.

        Validates Requirement 10.4 (sanitize user-provided data).
        """
        comm1 = await self._connect(self.user1)
        try:
            await comm1.send_json_to({
                'type': 'webrtc_offer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.user2.id),
                'sdp': {'type': 'malicious_type', 'sdp': 'v=0\r\n'},
            })

            response = await comm1.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'error')
        finally:
            await comm1.disconnect()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Rate Limiting Enforcement (Requirement 10.4)
# ─────────────────────────────────────────────────────────────────────────────

class RateLimitingEnforcementTestCase(TestCase):
    """
    Test that rate limiting is enforced for signaling messages.

    Validates Requirement 10.4: THE Signaling_Server SHALL validate message origin
    before relaying signaling data (includes rate limiting to prevent abuse).

    Note: Tests patch SignalingRateLimiter.MAX_MESSAGES_PER_MINUTE to a small
    value (5) so we can trigger the limit without sending 100 messages.
    """

    # Low limit used in all tests to make rate-limit triggering practical
    TEST_LIMIT = 5

    def setUp(self):
        self.user = User.objects.create_user(username='ratelimit_user', password='pass123')
        self.channel = Channel.objects.create(name='ratelimit-channel')
        ChannelMember.objects.create(channel=self.channel, user=self.user)

        self.target_user = User.objects.create_user(username='target_user', password='pass123')
        ChannelMember.objects.create(channel=self.channel, user=self.target_user)

        self.room = Room.objects.create(
            name='Rate Limit Room',
            created_by=self.user,
            is_active=True,
        )
        RoomParticipant.objects.create(room=self.room, user=self.user)
        RoomParticipant.objects.create(room=self.room, user=self.target_user)

    def tearDown(self):
        """Clear the rate limit cache after each test."""
        from django.core.cache import cache
        cache.clear()

    def test_rate_limiter_allows_messages_within_limit(self):
        """
        Messages within the rate limit are allowed.

        Validates Requirement 10.4.
        """
        from .rate_limiter import SignalingRateLimiter
        user_id = str(self.user.id)

        with patch.object(SignalingRateLimiter, 'MAX_MESSAGES_PER_MINUTE', self.TEST_LIMIT):
            for i in range(self.TEST_LIMIT):
                is_allowed, remaining = SignalingRateLimiter.check_rate_limit(
                    user_id, 'webrtc_offer'
                )
                self.assertTrue(is_allowed, f"Message {i+1} should be allowed")

    def test_rate_limiter_blocks_messages_over_limit(self):
        """
        Messages exceeding the rate limit are blocked.

        Validates Requirement 10.4.
        """
        from .rate_limiter import SignalingRateLimiter
        user_id = str(self.user.id)

        with patch.object(SignalingRateLimiter, 'MAX_MESSAGES_PER_MINUTE', self.TEST_LIMIT):
            # Exhaust the limit
            for _ in range(self.TEST_LIMIT):
                SignalingRateLimiter.check_rate_limit(user_id, 'webrtc_offer')

            # The next message should be blocked
            is_allowed, remaining = SignalingRateLimiter.check_rate_limit(
                user_id, 'webrtc_offer'
            )
            self.assertFalse(is_allowed)
            self.assertEqual(remaining, 0)

    def test_rate_limiter_tracks_remaining_quota(self):
        """
        The rate limiter correctly tracks the remaining message quota.

        Validates Requirement 10.4.
        """
        from .rate_limiter import SignalingRateLimiter
        user_id = str(self.user.id)

        with patch.object(SignalingRateLimiter, 'MAX_MESSAGES_PER_MINUTE', self.TEST_LIMIT):
            # First message: remaining should be limit - 1
            is_allowed, remaining = SignalingRateLimiter.check_rate_limit(
                user_id, 'webrtc_offer'
            )
            self.assertTrue(is_allowed)
            self.assertEqual(remaining, self.TEST_LIMIT - 1)

            # Second message: remaining should be limit - 2
            is_allowed, remaining = SignalingRateLimiter.check_rate_limit(
                user_id, 'webrtc_offer'
            )
            self.assertTrue(is_allowed)
            self.assertEqual(remaining, self.TEST_LIMIT - 2)

    def test_rate_limiter_is_per_user(self):
        """
        Rate limits are applied per user, not globally.

        Validates Requirement 10.4.
        """
        from .rate_limiter import SignalingRateLimiter
        user1_id = str(self.user.id)
        user2_id = str(self.target_user.id)

        with patch.object(SignalingRateLimiter, 'MAX_MESSAGES_PER_MINUTE', self.TEST_LIMIT):
            # Exhaust user1's limit
            for _ in range(self.TEST_LIMIT):
                SignalingRateLimiter.check_rate_limit(user1_id, 'webrtc_offer')

            # user1 is now blocked
            is_allowed, _ = SignalingRateLimiter.check_rate_limit(user1_id, 'webrtc_offer')
            self.assertFalse(is_allowed)

            # user2 should still be allowed (separate limit)
            is_allowed, _ = SignalingRateLimiter.check_rate_limit(user2_id, 'webrtc_offer')
            self.assertTrue(is_allowed)

    def test_rate_limiter_get_rate_limit_info(self):
        """
        get_rate_limit_info returns accurate status information.

        Validates Requirement 10.4.
        """
        from .rate_limiter import SignalingRateLimiter
        user_id = str(self.user.id)

        # Before any messages
        info = SignalingRateLimiter.get_rate_limit_info(user_id)
        self.assertEqual(info['count'], 0)
        self.assertEqual(info['remaining'], info['limit'])

        # After 3 messages
        for _ in range(3):
            SignalingRateLimiter.check_rate_limit(user_id, 'webrtc_offer')

        info = SignalingRateLimiter.get_rate_limit_info(user_id)
        self.assertEqual(info['count'], 3)
        self.assertEqual(info['remaining'], info['limit'] - 3)

    async def test_rate_limit_error_sent_over_websocket(self):
        """
        When a user exceeds the rate limit, the WebSocket consumer sends an
        error message with code RATE_LIMIT_EXCEEDED.

        Validates Requirement 10.4.
        """
        from django.core.cache import cache
        from .rate_limiter import SignalingRateLimiter
        cache.clear()

        # Patch the limit to a small value for this test
        original_limit = SignalingRateLimiter.MAX_MESSAGES_PER_MINUTE
        SignalingRateLimiter.MAX_MESSAGES_PER_MINUTE = self.TEST_LIMIT

        app = URLRouter([
            path('ws/chat/<str:channel_id>/', ChatConsumer.as_asgi()),
        ])
        comm = WebsocketCommunicator(app, f'/ws/chat/{self.channel.id}/')
        comm.scope['user'] = self.user
        comm.scope['url_route'] = {'kwargs': {'channel_id': str(self.channel.id)}}

        connected, _ = await comm.connect()
        self.assertTrue(connected)
        # Consume the 'connected' handshake message
        await comm.receive_json_from()

        try:
            user_id = str(self.user.id)

            # Pre-exhaust the rate limit via the rate limiter directly
            for _ in range(self.TEST_LIMIT):
                await sync_to_async(SignalingRateLimiter.check_rate_limit)(
                    user_id, 'webrtc_offer'
                )

            # Now send a message over WebSocket — should be rate-limited
            await comm.send_json_to({
                'type': 'webrtc_offer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.target_user.id),
                'sdp': {'type': 'offer', 'sdp': 'v=0\r\n'},
            })

            response = await comm.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'error')
            self.assertEqual(response.get('code'), 'RATE_LIMIT_EXCEEDED')
        finally:
            await comm.disconnect()
            SignalingRateLimiter.MAX_MESSAGES_PER_MINUTE = original_limit
            cache.clear()

    def test_rate_limit_applies_to_all_signaling_message_types(self):
        """
        Rate limiting applies to all signaling message types (offer, answer, ice, etc.)
        and they share the same per-user quota.

        Validates Requirement 10.4.
        """
        from django.core.cache import cache
        from .rate_limiter import SignalingRateLimiter
        cache.clear()

        user_id = str(self.user.id)

        with patch.object(SignalingRateLimiter, 'MAX_MESSAGES_PER_MINUTE', self.TEST_LIMIT):
            # Mix of different message types — all count toward the same limit
            SignalingRateLimiter.check_rate_limit(user_id, 'webrtc_offer')
            SignalingRateLimiter.check_rate_limit(user_id, 'webrtc_answer')
            SignalingRateLimiter.check_rate_limit(user_id, 'webrtc_ice')
            SignalingRateLimiter.check_rate_limit(user_id, 'call_invite')
            SignalingRateLimiter.check_rate_limit(user_id, 'participant_state')

            # 6th message of any type should be blocked
            is_allowed, remaining = SignalingRateLimiter.check_rate_limit(
                user_id, 'webrtc_offer'
            )
            self.assertFalse(is_allowed)
            self.assertEqual(remaining, 0)

        cache.clear()
