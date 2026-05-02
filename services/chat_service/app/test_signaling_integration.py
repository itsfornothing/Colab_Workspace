"""
Integration tests for WebRTC signaling flow through ChatConsumer.

These tests verify that WebRTC signaling messages (offers, answers, ICE candidates)
are correctly relayed between WebSocket clients, and that participant state updates
are broadcast to all participants in a room.

Requirements tested:
- 12.2: Test WebRTC signaling message exchange
- 12.4: Test call control operations and call notification delivery
- 12.5: Test call initiation, acceptance, and termination flows

Note: These tests use Django Channels' testing utilities to simulate WebSocket
connections and verify message relay functionality.
"""
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import path
from asgiref.sync import sync_to_async
import json
import asyncio

from .consumers import ChatConsumer
from .models import Room, RoomParticipant, Channel, ChannelMember

User = get_user_model()


class SignalingIntegrationTestCase(TestCase):
    """
    Integration tests for WebRTC signaling through ChatConsumer.
    
    These tests simulate WebSocket clients exchanging signaling messages
    to verify the relay functionality works correctly.
    """
    
    def setUp(self):
        """Set up test users, channel, and room for signaling tests."""
        # Create users
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.user3 = User.objects.create_user(username='user3', password='pass123')
        
        # Create a channel for WebSocket connection
        self.channel = Channel.objects.create(name='test-channel')
        
        # Add users as channel members
        ChannelMember.objects.create(channel=self.channel, user=self.user1)
        ChannelMember.objects.create(channel=self.channel, user=self.user2)
        ChannelMember.objects.create(channel=self.channel, user=self.user3)
        
        # Create a room for video call
        self.room = Room.objects.create(
            name='Test Room',
            created_by=self.user1,
            is_active=True
        )
        
        # Add participants to room
        RoomParticipant.objects.create(room=self.room, user=self.user1)
        RoomParticipant.objects.create(room=self.room, user=self.user2)
    
    # ====================== HELPER METHODS ======================
    
    async def _connect_websocket(self, user, channel_id):
        """
        Create and connect a WebSocket communicator for a user.
        
        Returns:
            WebsocketCommunicator: Connected communicator
        """
        # Create application with routing
        application = URLRouter([
            path('ws/chat/<str:channel_id>/', ChatConsumer.as_asgi()),
        ])
        
        # Create communicator with authenticated user in scope
        communicator = WebsocketCommunicator(
            application,
            f'/ws/chat/{channel_id}/',
        )
        communicator.scope['user'] = user
        communicator.scope['url_route'] = {'kwargs': {'channel_id': str(channel_id)}}
        
        # Connect
        connected, _ = await communicator.connect()
        self.assertTrue(connected, f"Failed to connect WebSocket for {user.username}")
        
        # Receive and discard the "connected" message
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'connected')
        
        return communicator
    
    def _get_channel_name(self, communicator):
        """Get the channel name from a connected communicator's scope."""
        return communicator.scope.get('channel_name', communicator.base_send.channel_name
                                      if hasattr(communicator, 'base_send') else None)
    
    async def _subscribe_to_user_group(self, communicator, user_id):
        """Subscribe a communicator's channel to a user-specific group for receiving messages."""
        channel_layer = get_channel_layer()
        channel_name = communicator.scope.get('channel_name')
        if channel_name:
            await channel_layer.group_add(
                f"user_{user_id}",
                channel_name
            )
    
    async def _subscribe_to_room_group(self, communicator, room_id):
        """Subscribe a communicator's channel to a room-specific group for receiving messages."""
        channel_layer = get_channel_layer()
        channel_name = communicator.scope.get('channel_name')
        if channel_name:
            await channel_layer.group_add(
                f"room_{room_id}",
                channel_name
            )
    
    # ====================== TEST CASES ======================
    
    async def test_webrtc_offer_relay_between_two_clients(self):
        """
        Test that WebRTC offer is relayed from user A to user B.
        
        Validates Requirement 12.2: Test WebRTC signaling message exchange
        """
        # Connect both users to the channel
        communicator1 = await self._connect_websocket(self.user1, self.channel.id)
        communicator2 = await self._connect_websocket(self.user2, self.channel.id)
        
        # Subscribe user2 to their user group to receive the offer
        await self._subscribe_to_user_group(communicator2, self.user2.id)
        
        try:
            # User1 sends WebRTC offer to User2
            offer_sdp = {
                'type': 'offer',
                'sdp': 'v=0\r\no=- 123456789 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n...'
            }
            
            offer_message = {
                'type': 'webrtc_offer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.user2.id),
                'sdp': offer_sdp
            }
            
            # Send offer from user1
            await communicator1.send_json_to(offer_message)
            
            # User2 should receive the offer
            response = await communicator2.receive_json_from(timeout=5)
            
            # Verify response structure
            self.assertEqual(response['type'], 'webrtc_offer')
            self.assertEqual(response['room_id'], str(self.room.id))
            self.assertEqual(response['from_user_id'], str(self.user1.id))
            self.assertEqual(response['to_user_id'], str(self.user2.id))
            self.assertEqual(response['sdp'], offer_sdp)
        finally:
            await communicator1.disconnect()
            await communicator2.disconnect()
    
    async def test_webrtc_answer_relay_back_to_initiator(self):
        """
        Test that WebRTC answer is relayed back to the call initiator.
        
        Validates Requirement 12.2: Test WebRTC signaling message exchange
        """
        # Connect both users
        communicator1 = await self._connect_websocket(self.user1, self.channel.id)
        communicator2 = await self._connect_websocket(self.user2, self.channel.id)
        
        # Subscribe user1 to their user group to receive the answer
        await self._subscribe_to_user_group(communicator1, self.user1.id)
        
        try:
            # User2 sends WebRTC answer to User1
            answer_sdp = {
                'type': 'answer',
                'sdp': 'v=0\r\no=- 987654321 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n...'
            }
            
            answer_message = {
                'type': 'webrtc_answer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.user1.id),
                'sdp': answer_sdp
            }
            
            # Send answer from user2
            await communicator2.send_json_to(answer_message)
            
            # User1 should receive the answer
            response = await communicator1.receive_json_from(timeout=5)
            
            # Verify response structure
            self.assertEqual(response['type'], 'webrtc_answer')
            self.assertEqual(response['room_id'], str(self.room.id))
            self.assertEqual(response['from_user_id'], str(self.user2.id))
            self.assertEqual(response['to_user_id'], str(self.user1.id))
            self.assertEqual(response['sdp'], answer_sdp)
        finally:
            await communicator1.disconnect()
            await communicator2.disconnect()
    
    async def test_ice_candidate_exchange(self):
        """
        Test that ICE candidates are exchanged between peers.
        
        Validates Requirement 12.2: Test WebRTC signaling message exchange
        """
        # Connect both users
        communicator1 = await self._connect_websocket(self.user1, self.channel.id)
        communicator2 = await self._connect_websocket(self.user2, self.channel.id)
        
        # Subscribe both users to their user groups
        await self._subscribe_to_user_group(communicator2, self.user2.id)
        await self._subscribe_to_user_group(communicator1, self.user1.id)
        
        try:
            # User1 sends ICE candidate to User2
            ice_candidate = {
                'candidate': 'candidate:1 1 UDP 2130706431 192.168.1.100 54321 typ host',
                'sdpMid': 'audio',
                'sdpMLineIndex': 0
            }
            
            ice_message = {
                'type': 'webrtc_ice',
                'room_id': str(self.room.id),
                'to_user_id': str(self.user2.id),
                'candidate': ice_candidate
            }
            
            # Send ICE candidate from user1
            await communicator1.send_json_to(ice_message)
            
            # User2 should receive the ICE candidate
            response = await communicator2.receive_json_from(timeout=5)
            
            # Verify response structure
            self.assertEqual(response['type'], 'webrtc_ice')
            self.assertEqual(response['room_id'], str(self.room.id))
            self.assertEqual(response['from_user_id'], str(self.user1.id))
            self.assertEqual(response['to_user_id'], str(self.user2.id))
            self.assertEqual(response['candidate'], ice_candidate)
            
            # Test bidirectional ICE exchange - User2 sends to User1
            ice_candidate_2 = {
                'candidate': 'candidate:2 1 UDP 2130706431 192.168.1.101 54322 typ host',
                'sdpMid': 'video',
                'sdpMLineIndex': 1
            }
            
            ice_message_2 = {
                'type': 'webrtc_ice',
                'room_id': str(self.room.id),
                'to_user_id': str(self.user1.id),
                'candidate': ice_candidate_2
            }
            
            await communicator2.send_json_to(ice_message_2)
            
            response2 = await communicator1.receive_json_from(timeout=5)
            self.assertEqual(response2['type'], 'webrtc_ice')
            self.assertEqual(response2['from_user_id'], str(self.user2.id))
            self.assertEqual(response2['candidate'], ice_candidate_2)
        finally:
            await communicator1.disconnect()
            await communicator2.disconnect()
    
    async def test_participant_state_broadcast_to_all_participants(self):
        """
        Test that participant state updates are broadcast to all participants in the room.
        
        Validates Requirement 12.4: Test call control operations
        """
        # Add user3 to the room
        await sync_to_async(RoomParticipant.objects.create)(room=self.room, user=self.user3)
        
        # Connect all three users
        communicator1 = await self._connect_websocket(self.user1, self.channel.id)
        communicator2 = await self._connect_websocket(self.user2, self.channel.id)
        communicator3 = await self._connect_websocket(self.user3, self.channel.id)
        
        # Subscribe all users to the room group
        await self._subscribe_to_room_group(communicator1, self.room.id)
        await self._subscribe_to_room_group(communicator2, self.room.id)
        await self._subscribe_to_room_group(communicator3, self.room.id)
        
        try:
            # User1 updates their state (mutes audio, turns off video, starts screen sharing)
            state_update = {
                'type': 'participant_state',
                'room_id': str(self.room.id),
                'is_muted': True,
                'is_video_on': False,
                'is_screen_sharing': True
            }
            
            # Send state update from user1
            await communicator1.send_json_to(state_update)
            
            # All participants should receive the broadcast
            responses = []
            for comm in [communicator1, communicator2, communicator3]:
                response = await comm.receive_json_from(timeout=5)
                responses.append(response)
            
            # Verify all received the same state update
            for response in responses:
                self.assertEqual(response['type'], 'participant_state')
                self.assertEqual(response['room_id'], str(self.room.id))
                self.assertEqual(response['user_id'], str(self.user1.id))
                self.assertTrue(response['is_muted'])
                self.assertFalse(response['is_video_on'])
                self.assertTrue(response['is_screen_sharing'])
            
            # Verify state was persisted in database
            participant = await sync_to_async(RoomParticipant.objects.get)(room=self.room, user=self.user1)
            self.assertTrue(participant.is_muted)
            self.assertFalse(participant.is_video_on)
            self.assertTrue(participant.is_screen_sharing)
        finally:
            await communicator1.disconnect()
            await communicator2.disconnect()
            await communicator3.disconnect()
    
    async def test_call_invitation_delivery(self):
        """
        Test that call invitations are delivered to invited users.
        
        Validates Requirement 12.5: Test call initiation flow
        """
        # Connect users
        communicator1 = await self._connect_websocket(self.user1, self.channel.id)
        communicator2 = await self._connect_websocket(self.user2, self.channel.id)
        communicator3 = await self._connect_websocket(self.user3, self.channel.id)
        
        # Subscribe users to their user groups
        await self._subscribe_to_user_group(communicator2, self.user2.id)
        await self._subscribe_to_user_group(communicator3, self.user3.id)
        
        try:
            # User1 invites User2 and User3 to a call
            invitation_message = {
                'type': 'call_invite',
                'room_id': str(self.room.id),
                'invited_user_ids': [str(self.user2.id), str(self.user3.id)]
            }
            
            # Send invitation from user1
            await communicator1.send_json_to(invitation_message)
            
            # User2 should receive invitation
            response2 = await communicator2.receive_json_from(timeout=5)
            self.assertEqual(response2['type'], 'call_invite')
            self.assertEqual(response2['room_id'], str(self.room.id))
            self.assertEqual(response2['caller_id'], str(self.user1.id))
            self.assertIn('caller_name', response2)
            
            # User3 should also receive invitation
            response3 = await communicator3.receive_json_from(timeout=5)
            self.assertEqual(response3['type'], 'call_invite')
            self.assertEqual(response3['room_id'], str(self.room.id))
            self.assertEqual(response3['caller_id'], str(self.user1.id))
        finally:
            await communicator1.disconnect()
            await communicator2.disconnect()
            await communicator3.disconnect()
    
    async def test_call_acceptance_notification(self):
        """
        Test that call acceptance is notified to the caller.
        
        Validates Requirement 12.5: Test call acceptance flow
        """
        # Connect users
        communicator1 = await self._connect_websocket(self.user1, self.channel.id)
        communicator2 = await self._connect_websocket(self.user2, self.channel.id)
        
        # Subscribe user1 to their user group and room group
        await self._subscribe_to_user_group(communicator1, self.user1.id)
        await self._subscribe_to_room_group(communicator1, self.room.id)
        await self._subscribe_to_room_group(communicator2, self.room.id)
        
        try:
            # User2 accepts the call
            accept_message = {
                'type': 'call_accept',
                'room_id': str(self.room.id),
                'caller_id': str(self.user1.id)
            }
            
            await communicator2.send_json_to(accept_message)
            
            # User1 should receive acceptance notification
            response = await communicator1.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'call_accept')
            self.assertEqual(response['room_id'], str(self.room.id))
            self.assertEqual(response['accepter_id'], str(self.user2.id))
            self.assertIn('accepter_name', response)
        finally:
            await communicator1.disconnect()
            await communicator2.disconnect()
    
    async def test_call_decline_notification(self):
        """
        Test that call decline is notified to the caller.
        
        Validates Requirement 12.5: Test call decline flow
        """
        # Connect users
        communicator1 = await self._connect_websocket(self.user1, self.channel.id)
        communicator2 = await self._connect_websocket(self.user2, self.channel.id)
        
        # Subscribe user1 to their user group
        await self._subscribe_to_user_group(communicator1, self.user1.id)
        
        try:
            # User2 declines the call
            decline_message = {
                'type': 'call_decline',
                'room_id': str(self.room.id),
                'caller_id': str(self.user1.id)
            }
            
            await communicator2.send_json_to(decline_message)
            
            # User1 should receive decline notification
            response = await communicator1.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'call_decline')
            self.assertEqual(response['room_id'], str(self.room.id))
            self.assertEqual(response['decliner_id'], str(self.user2.id))
            self.assertIn('decliner_name', response)
        finally:
            await communicator1.disconnect()
            await communicator2.disconnect()
    
    async def test_call_end_broadcast(self):
        """
        Test that call termination is broadcast to all participants.
        
        Validates Requirement 12.5: Test call termination flow
        """
        # Add user3 to room
        await sync_to_async(RoomParticipant.objects.create)(room=self.room, user=self.user3)
        
        # Connect all users
        communicator1 = await self._connect_websocket(self.user1, self.channel.id)
        communicator2 = await self._connect_websocket(self.user2, self.channel.id)
        communicator3 = await self._connect_websocket(self.user3, self.channel.id)
        
        # Subscribe all to room group
        await self._subscribe_to_room_group(communicator1, self.room.id)
        await self._subscribe_to_room_group(communicator2, self.room.id)
        await self._subscribe_to_room_group(communicator3, self.room.id)
        
        try:
            # User1 ends the call
            end_message = {
                'type': 'call_end',
                'room_id': str(self.room.id)
            }
            
            await communicator1.send_json_to(end_message)
            
            # All participants should receive call end notification
            for comm in [communicator1, communicator2, communicator3]:
                response = await comm.receive_json_from(timeout=5)
                self.assertEqual(response['type'], 'call_end')
                self.assertEqual(response['room_id'], str(self.room.id))
                self.assertEqual(response['ended_by'], str(self.user1.id))
        finally:
            await communicator1.disconnect()
            await communicator2.disconnect()
            await communicator3.disconnect()
    
    async def test_unauthorized_access_rejection(self):
        """
        Test that unauthorized users cannot relay signaling messages.
        
        Validates Requirement 10.2, 10.3: Test unauthorized access rejection
        """
        # Connect user1 (in room) and user3 (not in room)
        communicator1 = await self._connect_websocket(self.user1, self.channel.id)
        communicator3 = await self._connect_websocket(self.user3, self.channel.id)
        
        try:
            # User3 tries to send offer to User1 (but User3 is not in the room)
            offer_message = {
                'type': 'webrtc_offer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.user1.id),
                'sdp': {'type': 'offer', 'sdp': 'test'}
            }
            
            await communicator3.send_json_to(offer_message)
            
            # User3 should receive an error
            response = await communicator3.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'error')
            self.assertIn('not a member', response['detail'].lower())
        finally:
            await communicator1.disconnect()
            await communicator3.disconnect()
    
    async def test_signaling_to_non_member_rejected(self):
        """
        Test that signaling messages to non-room-members are rejected.
        
        Validates Requirement 10.4: Test message origin validation
        """
        # Connect user1 (in room) and user3 (not in room)
        communicator1 = await self._connect_websocket(self.user1, self.channel.id)
        communicator3 = await self._connect_websocket(self.user3, self.channel.id)
        
        try:
            # User1 tries to send offer to User3 (who is not in the room)
            offer_message = {
                'type': 'webrtc_offer',
                'room_id': str(self.room.id),
                'to_user_id': str(self.user3.id),
                'sdp': {'type': 'offer', 'sdp': 'test'}
            }
            
            await communicator1.send_json_to(offer_message)
            
            # User1 should receive an error
            response = await communicator1.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'error')
            self.assertIn('not a member', response['detail'].lower())
        finally:
            await communicator1.disconnect()
            await communicator3.disconnect()
    
    async def test_room_full_rejection(self):
        """
        Test that call invitation is rejected when room is at capacity.
        
        Validates Requirement 8.7: Test room capacity enforcement
        """
        # Create a room with max 2 participants
        small_room = await sync_to_async(Room.objects.create)(
            name='Small Room',
            created_by=self.user1,
            is_active=True,
            max_participants=2
        )
        
        # Add two participants (room is now full)
        await sync_to_async(RoomParticipant.objects.create)(room=small_room, user=self.user1)
        await sync_to_async(RoomParticipant.objects.create)(room=small_room, user=self.user2)
        
        # Connect user1
        communicator1 = await self._connect_websocket(self.user1, self.channel.id)
        
        try:
            # User1 tries to invite User3 to full room
            invitation_message = {
                'type': 'call_invite',
                'room_id': str(small_room.id),
                'invited_user_ids': [str(self.user3.id)]
            }
            
            await communicator1.send_json_to(invitation_message)
            
            # User1 should receive an error
            response = await communicator1.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'error')
            self.assertIn('maximum capacity', response['detail'].lower())
        finally:
            await communicator1.disconnect()
    
    async def test_participant_state_partial_update(self):
        """
        Test that participant state can be partially updated (only some fields).
        
        Validates Requirement 3.8: Test participant state persistence
        """
        # Connect user1
        communicator1 = await self._connect_websocket(self.user1, self.channel.id)
        
        # Subscribe to room group
        await self._subscribe_to_room_group(communicator1, self.room.id)
        
        try:
            # Update only is_muted
            await communicator1.send_json_to({
                'type': 'participant_state',
                'room_id': str(self.room.id),
                'is_muted': True,
                'is_video_on': None,
                'is_screen_sharing': None
            })
            
            response = await communicator1.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'participant_state')
            self.assertTrue(response['is_muted'])
            
            # Verify only is_muted was updated in database
            participant = await sync_to_async(RoomParticipant.objects.get)(room=self.room, user=self.user1)
            self.assertTrue(participant.is_muted)
            # Other fields should retain default values
            self.assertTrue(participant.is_video_on)  # Default is True
            self.assertFalse(participant.is_screen_sharing)  # Default is False
        finally:
            await communicator1.disconnect()
