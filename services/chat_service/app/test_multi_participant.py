"""
Multi-participant signaling tests for WebRTC video calls.

These tests verify that WebRTC signaling works correctly with 4 and 8 participants
(mesh topology), and that participant leave/cleanup is handled properly.

Requirements tested:
- 8.2: Multi-participant connection establishment (mesh topology)
- 8.3: Participant leave and connection cleanup
- 12.3: Multi-participant call scenarios
"""
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import path
from asgiref.sync import sync_to_async
import json
from django.utils import timezone

from .consumers import ChatConsumer
from .models import Room, RoomParticipant, Channel, ChannelMember

User = get_user_model()


class MultiParticipantSignalingTestCase(TestCase):
    """
    Integration tests for multi-participant WebRTC signaling through ChatConsumer.

    Tests mesh topology signaling with 4 and 8 participants, and verifies
    that participant leave/cleanup is handled correctly.
    """

    def setUp(self):
        """Set up test users, channel, and room for multi-participant tests."""
        # Create 8 users for maximum-capacity tests
        self.users = []
        for i in range(1, 9):
            user = User.objects.create_user(
                username=f'mp_user{i}', password='pass123'
            )
            self.users.append(user)

        # Create a channel for WebSocket connections
        self.channel = Channel.objects.create(name='multi-participant-test-channel')

        # Add all users as channel members
        for user in self.users:
            ChannelMember.objects.create(channel=self.channel, user=user)

        # Create a room for video calls (max 8 participants)
        self.room = Room.objects.create(
            name='Multi-Participant Test Room',
            created_by=self.users[0],
            is_active=True,
            max_participants=8,
        )

    # ====================== HELPER METHODS ======================

    async def _connect_websocket(self, user, channel_id):
        """Create and connect a WebSocket communicator for a user."""
        application = URLRouter([
            path('ws/chat/<str:channel_id>/', ChatConsumer.as_asgi()),
        ])

        communicator = WebsocketCommunicator(
            application,
            f'/ws/chat/{channel_id}/',
        )
        communicator.scope['user'] = user
        communicator.scope['url_route'] = {'kwargs': {'channel_id': str(channel_id)}}

        connected, _ = await communicator.connect()
        self.assertTrue(connected, f"Failed to connect WebSocket for {user.username}")

        # Discard the "connected" message
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'connected')

        return communicator

    async def _subscribe_to_user_group(self, communicator, user_id):
        """Subscribe a communicator's channel to a user-specific group."""
        channel_layer = get_channel_layer()
        channel_name = communicator.scope.get('channel_name')
        if channel_name:
            await channel_layer.group_add(f"user_{user_id}", channel_name)

    async def _subscribe_to_room_group(self, communicator, room_id):
        """Subscribe a communicator's channel to a room-specific group."""
        channel_layer = get_channel_layer()
        channel_name = communicator.scope.get('channel_name')
        if channel_name:
            await channel_layer.group_add(f"room_{room_id}", channel_name)

    async def _add_room_participant(self, user):
        """Add a user as an active room participant."""
        await sync_to_async(RoomParticipant.objects.get_or_create)(
            room=self.room, user=user
        )

    # ====================== TEST CASES ======================

    async def test_4_participant_offer_relay(self):
        """
        Test that WebRTC offers from user1 are relayed to user2, user3, and user4.

        Simulates joinRoom() where user1 sends offers to all 3 existing participants.
        Verifies all 3 offers are relayed correctly (mesh topology).

        Validates Requirements 8.2, 12.3
        """
        # Add 4 participants to the room
        for i in range(4):
            await self._add_room_participant(self.users[i])

        # Connect all 4 users via WebSocket
        communicators = []
        try:
            for i in range(4):
                comm = await self._connect_websocket(self.users[i], self.channel.id)
                communicators.append(comm)

            # Subscribe users 2, 3, 4 to their user groups so they receive offers
            for i in range(1, 4):
                await self._subscribe_to_user_group(communicators[i], self.users[i].id)

            offer_sdp = {
                'type': 'offer',
                'sdp': 'v=0\r\no=- 111111 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n'
            }

            # user1 sends offers to user2, user3, user4 (simulating joinRoom)
            for target_idx in range(1, 4):
                offer_message = {
                    'type': 'webrtc_offer',
                    'room_id': str(self.room.id),
                    'to_user_id': str(self.users[target_idx].id),
                    'sdp': offer_sdp,
                }
                await communicators[0].send_json_to(offer_message)

            # Verify each target user received their offer
            for target_idx in range(1, 4):
                response = await communicators[target_idx].receive_json_from(timeout=5)
                self.assertEqual(response['type'], 'webrtc_offer',
                                 f"user{target_idx + 1} did not receive offer")
                self.assertEqual(response['room_id'], str(self.room.id))
                self.assertEqual(response['from_user_id'], str(self.users[0].id))
                self.assertEqual(response['to_user_id'], str(self.users[target_idx].id))
                self.assertEqual(response['sdp'], offer_sdp)

        finally:
            for comm in communicators:
                await comm.disconnect()

    async def test_8_participant_offer_relay(self):
        """
        Test that a new participant (user8) can send offers to all 7 existing
        participants and each receives their offer.

        Tests mesh topology at maximum capacity (8 participants).

        Validates Requirements 8.2, 8.3, 12.3
        """
        # Add all 8 participants to the room
        for user in self.users:
            await self._add_room_participant(user)

        communicators = []
        try:
            # Connect all 8 users
            for user in self.users:
                comm = await self._connect_websocket(user, self.channel.id)
                communicators.append(comm)

            # Subscribe users 1-7 (indices 0-6) to their user groups
            # so they can receive offers from user8 (index 7)
            for i in range(7):
                await self._subscribe_to_user_group(communicators[i], self.users[i].id)

            offer_sdp = {
                'type': 'offer',
                'sdp': 'v=0\r\no=- 888888 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n'
            }

            # user8 (index 7) sends offers to all 7 existing participants
            for target_idx in range(7):
                offer_message = {
                    'type': 'webrtc_offer',
                    'room_id': str(self.room.id),
                    'to_user_id': str(self.users[target_idx].id),
                    'sdp': offer_sdp,
                }
                await communicators[7].send_json_to(offer_message)

            # Verify each of the 7 existing participants received their offer
            for target_idx in range(7):
                response = await communicators[target_idx].receive_json_from(timeout=5)
                self.assertEqual(response['type'], 'webrtc_offer',
                                 f"user{target_idx + 1} did not receive offer from user8")
                self.assertEqual(response['room_id'], str(self.room.id))
                self.assertEqual(response['from_user_id'], str(self.users[7].id))
                self.assertEqual(response['to_user_id'], str(self.users[target_idx].id))
                self.assertEqual(response['sdp'], offer_sdp)

        finally:
            for comm in communicators:
                await comm.disconnect()

    async def test_participant_leave_and_connection_cleanup(self):
        """
        Test that after a participant leaves, their signaling is rejected while
        remaining participants can still signal each other.

        Scenario:
        - 4 users in a room (user1, user2, user3, user4)
        - user2 leaves (left_at is set on their RoomParticipant)
        - Verify user2 cannot send signaling (is_room_member check fails)
        - Verify user1 can still send offers to user3 and user4

        Validates Requirements 8.3, 12.3
        """
        # Add 4 participants to the room
        for i in range(4):
            await self._add_room_participant(self.users[i])

        communicators = []
        try:
            # Connect all 4 users
            for i in range(4):
                comm = await self._connect_websocket(self.users[i], self.channel.id)
                communicators.append(comm)

            # Subscribe users 1, 3, 4 to their user groups
            for i in [0, 2, 3]:
                await self._subscribe_to_user_group(communicators[i], self.users[i].id)

            # Simulate user2 (index 1) leaving by setting left_at
            await sync_to_async(
                RoomParticipant.objects.filter(room=self.room, user=self.users[1]).update
            )(left_at=timezone.now())

            offer_sdp = {
                'type': 'offer',
                'sdp': 'v=0\r\no=- 444444 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n'
            }

            # --- Verify user2 signaling is rejected ---
            # user2 tries to send an offer to user1 (but user2 has left)
            rejected_offer = {
                'type': 'webrtc_offer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.users[0].id),
                'sdp': offer_sdp,
            }
            await communicators[1].send_json_to(rejected_offer)

            # user2 should receive an error (not a room member)
            error_response = await communicators[1].receive_json_from(timeout=5)
            self.assertEqual(error_response['type'], 'error',
                             "user2 should have received an error after leaving")
            self.assertIn('not a member', error_response['detail'].lower())

            # --- Verify remaining participants can still signal each other ---
            # user1 sends offer to user3
            offer_to_user3 = {
                'type': 'webrtc_offer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.users[2].id),
                'sdp': offer_sdp,
            }
            await communicators[0].send_json_to(offer_to_user3)

            response_user3 = await communicators[2].receive_json_from(timeout=5)
            self.assertEqual(response_user3['type'], 'webrtc_offer',
                             "user3 should still receive offers after user2 left")
            self.assertEqual(response_user3['from_user_id'], str(self.users[0].id))
            self.assertEqual(response_user3['to_user_id'], str(self.users[2].id))

            # user1 sends offer to user4
            offer_to_user4 = {
                'type': 'webrtc_offer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.users[3].id),
                'sdp': offer_sdp,
            }
            await communicators[0].send_json_to(offer_to_user4)

            response_user4 = await communicators[3].receive_json_from(timeout=5)
            self.assertEqual(response_user4['type'], 'webrtc_offer',
                             "user4 should still receive offers after user2 left")
            self.assertEqual(response_user4['from_user_id'], str(self.users[0].id))
            self.assertEqual(response_user4['to_user_id'], str(self.users[3].id))

        finally:
            for comm in communicators:
                await comm.disconnect()
