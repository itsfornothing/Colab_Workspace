"""
Tests for Video Call API endpoints
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from datetime import timedelta
from django.utils import timezone

from .models import Room, RoomParticipant, CallHistory, CallParticipant

User = get_user_model()


class RoomAPITestCase(TestCase):
    """Test Room CRUD endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.user3 = User.objects.create_user(username='user3', password='pass123')
        self.client.force_authenticate(user=self.user1)
    
    def test_create_room(self):
        """Test POST /api/rooms/ creates room and adds creator"""
        data = {
            'name': 'Test Room',
            'workspace_id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
        }
        response = self.client.post('/api/rooms/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Test Room')
        self.assertTrue(response.data['is_active'])
        self.assertEqual(response.data['participant_count'], 1)
        
        # Verify room was created in database
        room = Room.objects.get(id=response.data['id'])
        self.assertEqual(room.created_by, self.user1)
        
        # Verify creator was added as participant
        self.assertTrue(
            RoomParticipant.objects.filter(room=room, user=self.user1).exists()
        )
    
    def test_list_active_rooms(self):
        """Test GET /api/rooms/ returns only active rooms"""
        # Create active room
        active_room = Room.objects.create(
            name='Active Room',
            created_by=self.user1,
            is_active=True
        )
        RoomParticipant.objects.create(room=active_room, user=self.user1)
        
        # Create inactive room
        inactive_room = Room.objects.create(
            name='Inactive Room',
            created_by=self.user1,
            is_active=False,
            ended_at=timezone.now()
        )
        
        response = self.client.get('/api/rooms/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Active Room')
    
    def test_get_room_detail(self):
        """Test GET /api/rooms/{id}/ returns room details"""
        room = Room.objects.create(
            name='Detail Room',
            created_by=self.user1,
            is_active=True
        )
        RoomParticipant.objects.create(room=room, user=self.user1)
        
        response = self.client.get(f'/api/rooms/{room.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Detail Room')
        self.assertEqual(len(response.data['participants']), 1)
    
    def test_join_room(self):
        """Test POST /api/rooms/{id}/join/ adds participant"""
        room = Room.objects.create(
            name='Join Room',
            created_by=self.user1,
            is_active=True
        )
        RoomParticipant.objects.create(room=room, user=self.user1)
        
        # User2 joins the room
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(f'/api/rooms/{room.id}/join/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['participant_count'], 2)
        
        # Verify participant was added
        self.assertTrue(
            RoomParticipant.objects.filter(room=room, user=self.user2).exists()
        )
    
    def test_join_full_room_rejected(self):
        """Test joining full room returns error"""
        room = Room.objects.create(
            name='Full Room',
            created_by=self.user1,
            is_active=True,
            max_participants=2
        )
        RoomParticipant.objects.create(room=room, user=self.user1)
        RoomParticipant.objects.create(room=room, user=self.user2)
        
        # User3 tries to join full room
        self.client.force_authenticate(user=self.user3)
        response = self.client.post(f'/api/rooms/{room.id}/join/')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('maximum capacity', response.data['error'])
    
    def test_leave_room(self):
        """Test POST /api/rooms/{id}/leave/ removes participant"""
        room = Room.objects.create(
            name='Leave Room',
            created_by=self.user1,
            is_active=True
        )
        participant = RoomParticipant.objects.create(room=room, user=self.user1)
        
        response = self.client.post(f'/api/rooms/{room.id}/leave/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify left_at was set
        participant.refresh_from_db()
        self.assertIsNotNone(participant.left_at)
        
        # Verify room was ended (no active participants)
        room.refresh_from_db()
        self.assertFalse(room.is_active)
        self.assertIsNotNone(room.ended_at)
    
    def test_leave_room_with_other_participants(self):
        """Test leaving room doesn't end it if others remain"""
        room = Room.objects.create(
            name='Multi Room',
            created_by=self.user1,
            is_active=True
        )
        RoomParticipant.objects.create(room=room, user=self.user1)
        RoomParticipant.objects.create(room=room, user=self.user2)
        
        # User1 leaves
        response = self.client.post(f'/api/rooms/{room.id}/leave/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Room should still be active
        room.refresh_from_db()
        self.assertTrue(room.is_active)
        self.assertIsNone(room.ended_at)


class RoomInvitationTestCase(TestCase):
    """Test room invitation endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.user3 = User.objects.create_user(username='user3', password='pass123')
        self.client.force_authenticate(user=self.user1)
        
        self.room = Room.objects.create(
            name='Invite Room',
            created_by=self.user1,
            is_active=True
        )
        RoomParticipant.objects.create(room=self.room, user=self.user1)
    
    def test_invite_users_to_room(self):
        """Test POST /api/rooms/{id}/invite/ sends invitations"""
        data = {
            'user_ids': [str(self.user2.id), str(self.user3.id)]
        }
        response = self.client.post(f'/api/rooms/{self.room.id}/invite/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['invited_user_ids']), 2)
    
    def test_invite_requires_membership(self):
        """Test invitation requires being in the room"""
        # User2 tries to invite without being in room
        self.client.force_authenticate(user=self.user2)
        data = {'user_ids': [str(self.user3.id)]}
        response = self.client.post(f'/api/rooms/{self.room.id}/invite/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_invite_invalid_user_ids(self):
        """Test invitation with invalid user IDs"""
        data = {
            'user_ids': ['00000000-0000-0000-0000-000000000000']
        }
        response = self.client.post(f'/api/rooms/{self.room.id}/invite/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ParticipantManagementTestCase(TestCase):
    """Test participant management endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.client.force_authenticate(user=self.user1)
        
        self.room = Room.objects.create(
            name='Participant Room',
            created_by=self.user1,
            is_active=True
        )
        self.participant1 = RoomParticipant.objects.create(room=self.room, user=self.user1)
        self.participant2 = RoomParticipant.objects.create(room=self.room, user=self.user2)
    
    def test_list_participants(self):
        """Test GET /api/rooms/{id}/participants/ lists participants"""
        response = self.client.get(f'/api/rooms/{self.room.id}/participants/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_update_participant_state(self):
        """Test PATCH /api/rooms/{id}/participants/{user_id}/ updates state"""
        data = {
            'is_muted': True,
            'is_video_on': False,
            'is_screen_sharing': True
        }
        response = self.client.patch(
            f'/api/rooms/{self.room.id}/participants/{self.user1.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_muted'])
        self.assertFalse(response.data['is_video_on'])
        self.assertTrue(response.data['is_screen_sharing'])
        
        # Verify database was updated
        self.participant1.refresh_from_db()
        self.assertTrue(self.participant1.is_muted)
        self.assertFalse(self.participant1.is_video_on)
        self.assertTrue(self.participant1.is_screen_sharing)
    
    def test_cannot_update_other_user_state(self):
        """Test users can only update their own state"""
        data = {'is_muted': True}
        response = self.client.patch(
            f'/api/rooms/{self.room.id}/participants/{self.user2.id}/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CallHistoryTestCase(TestCase):
    """Test call history endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.client.force_authenticate(user=self.user1)
        
        # Create a room
        self.room = Room.objects.create(
            name='History Room',
            created_by=self.user1,
            is_active=False,
            ended_at=timezone.now()
        )
        
        # Create call history
        self.call = CallHistory.objects.create(
            room=self.room,
            started_at=timezone.now() - timedelta(hours=1),
            ended_at=timezone.now(),
            duration_seconds=3600,
            participant_count=2
        )
        
        # Add participants to call history
        CallParticipant.objects.create(
            call_history=self.call,
            user=self.user1,
            joined_at=self.call.started_at,
            left_at=self.call.ended_at,
            duration_seconds=3600
        )
        CallParticipant.objects.create(
            call_history=self.call,
            user=self.user2,
            joined_at=self.call.started_at,
            left_at=self.call.ended_at,
            duration_seconds=3600
        )
    
    def test_get_call_history(self):
        """Test GET /api/call-history/ returns user's calls"""
        response = self.client.get('/api/call-history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['duration_seconds'], 3600)
        self.assertEqual(response.data[0]['participant_count'], 2)
    
    def test_call_history_retention(self):
        """Test 90-day retention policy"""
        # Create old call (100 days ago)
        # Note: We need to manually set started_at after creation since auto_now_add=True
        old_room = Room.objects.create(
            name='Old Room',
            created_by=self.user1,
            is_active=False
        )
        old_call = CallHistory.objects.create(
            room=old_room,
            ended_at=timezone.now() - timedelta(days=100),
            duration_seconds=1800,
            participant_count=1
        )
        # Update started_at manually to bypass auto_now_add
        CallHistory.objects.filter(id=old_call.id).update(
            started_at=timezone.now() - timedelta(days=100)
        )
        old_call.refresh_from_db()
        
        CallParticipant.objects.create(
            call_history=old_call,
            user=self.user1,
            joined_at=old_call.started_at,
            left_at=old_call.ended_at,
            duration_seconds=1800
        )
        
        response = self.client.get('/api/call-history/')
        
        # Should only return recent call (within 90 days)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The old call should be filtered out by the 90-day retention
        # Only the recent call from setUp should be returned
        call_ids = [call['id'] for call in response.data]
        self.assertIn(str(self.call.id), call_ids)
        self.assertNotIn(str(old_call.id), call_ids)
    
    def test_call_history_only_user_calls(self):
        """Test call history only returns calls user participated in"""
        # Create another user and their call
        user3 = User.objects.create_user(username='user3', password='pass123')
        other_room = Room.objects.create(
            name='Other Room',
            created_by=user3,
            is_active=False
        )
        other_call = CallHistory.objects.create(
            room=other_room,
            started_at=timezone.now() - timedelta(hours=2),
            ended_at=timezone.now() - timedelta(hours=1),
            duration_seconds=3600,
            participant_count=1
        )
        CallParticipant.objects.create(
            call_history=other_call,
            user=user3,
            joined_at=other_call.started_at,
            left_at=other_call.ended_at,
            duration_seconds=3600
        )
        
        response = self.client.get('/api/call-history/')
        
        # Should only return user1's call
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.call.id))


class ICEServersTestCase(TestCase):
    """Test ICE servers endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='user1', password='pass123')
        self.client.force_authenticate(user=self.user)
    
    def test_ice_servers_endpoint(self):
        """Test GET /api/ice-servers/ returns configuration"""
        response = self.client.get('/api/ice-servers/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('iceServers', response.data)
        self.assertIsInstance(response.data['iceServers'], list)
        self.assertGreater(len(response.data['iceServers']), 0)
        
        # Verify STUN server format
        for server in response.data['iceServers']:
            self.assertIn('urls', server)
            self.assertTrue(server['urls'].startswith('stun:'))


class RoomCreationAndParticipantTestCase(TestCase):
    """Test room creation and participant addition flow (Requirement 12.1, 8.7)"""
    
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username='creator', password='pass123')
        self.user2 = User.objects.create_user(username='joiner', password='pass123')
        self.client.force_authenticate(user=self.user1)
    
    def test_complete_room_creation_flow(self):
        """Test complete flow: create room, add participants, verify state"""
        # Step 1: Create room
        room_data = {
            'name': 'Team Meeting',
            'workspace_id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
            'max_participants': 8
        }
        create_response = self.client.post('/api/rooms/', room_data, format='json')
        
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        room_id = create_response.data['id']
        
        # Verify creator is automatically added as participant
        self.assertEqual(create_response.data['participant_count'], 1)
        self.assertEqual(len(create_response.data['participants']), 1)
        self.assertEqual(
            create_response.data['participants'][0]['user']['username'],
            'creator'
        )
        
        # Step 2: Second user joins
        self.client.force_authenticate(user=self.user2)
        join_response = self.client.post(f'/api/rooms/{room_id}/join/')
        
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)
        self.assertEqual(join_response.data['participant_count'], 2)
        
        # Step 3: Verify room details show both participants
        detail_response = self.client.get(f'/api/rooms/{room_id}/')
        
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(detail_response.data['participants']), 2)
        
        participant_usernames = [
            p['user']['username'] for p in detail_response.data['participants']
        ]
        self.assertIn('creator', participant_usernames)
        self.assertIn('joiner', participant_usernames)


class RoomCapacityTestCase(TestCase):
    """Test 8 participant limit enforcement (Requirement 8.7)"""
    
    def setUp(self):
        self.client = APIClient()
        self.users = [
            User.objects.create_user(username=f'user{i}', password='pass123')
            for i in range(10)
        ]
        self.client.force_authenticate(user=self.users[0])
        
        # Create room with 8 participant limit
        room_data = {'name': 'Capacity Test', 'max_participants': 8}
        response = self.client.post('/api/rooms/', room_data, format='json')
        self.room_id = response.data['id']
    
    def test_join_full_room_rejected(self):
        """Test that 9th participant cannot join 8-person room"""
        # Add 7 more participants (creator is already in, so total will be 8)
        for i in range(1, 8):
            self.client.force_authenticate(user=self.users[i])
            response = self.client.post(f'/api/rooms/{self.room_id}/join/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify room is now full
        detail_response = self.client.get(f'/api/rooms/{self.room_id}/')
        self.assertEqual(detail_response.data['participant_count'], 8)
        self.assertTrue(detail_response.data['is_full'])
        
        # Try to add 9th participant
        self.client.force_authenticate(user=self.users[8])
        response = self.client.post(f'/api/rooms/{self.room_id}/join/')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('maximum capacity', response.data['error'].lower())
    
    def test_can_join_after_someone_leaves(self):
        """Test that new participant can join after someone leaves"""
        # Fill room to capacity
        for i in range(1, 8):
            self.client.force_authenticate(user=self.users[i])
            self.client.post(f'/api/rooms/{self.room_id}/join/')
        
        # One participant leaves
        self.client.force_authenticate(user=self.users[7])
        leave_response = self.client.post(f'/api/rooms/{self.room_id}/leave/')
        self.assertEqual(leave_response.status_code, status.HTTP_200_OK)
        
        # New participant can now join
        self.client.force_authenticate(user=self.users[8])
        join_response = self.client.post(f'/api/rooms/{self.room_id}/join/')
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)


class LeaveRoomTimestampTestCase(TestCase):
    """Test leave room and timestamp updates (Requirement 12.1)"""
    
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.client.force_authenticate(user=self.user1)
        
        # Create room with two participants
        response = self.client.post('/api/rooms/', {'name': 'Leave Test'}, format='json')
        self.room_id = response.data['id']
        
        self.client.force_authenticate(user=self.user2)
        self.client.post(f'/api/rooms/{self.room_id}/join/')
    
    def test_leave_room_updates_timestamp(self):
        """Test that leaving room sets left_at timestamp"""
        # User2 leaves
        before_leave = timezone.now()
        response = self.client.post(f'/api/rooms/{self.room_id}/leave/')
        after_leave = timezone.now()
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify left_at was set
        participant = RoomParticipant.objects.get(
            room_id=self.room_id, user=self.user2
        )
        self.assertIsNotNone(participant.left_at)
        self.assertGreaterEqual(participant.left_at, before_leave)
        self.assertLessEqual(participant.left_at, after_leave)
    
    def test_last_participant_leaving_ends_room(self):
        """Test that room ends when last participant leaves"""
        # User2 leaves
        self.client.force_authenticate(user=self.user2)
        self.client.post(f'/api/rooms/{self.room_id}/leave/')
        
        # User1 leaves (last participant)
        self.client.force_authenticate(user=self.user1)
        before_leave = timezone.now()
        response = self.client.post(f'/api/rooms/{self.room_id}/leave/')
        after_leave = timezone.now()
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify room is ended
        room = Room.objects.get(id=self.room_id)
        self.assertFalse(room.is_active)
        self.assertIsNotNone(room.ended_at)
        self.assertGreaterEqual(room.ended_at, before_leave)
        self.assertLessEqual(room.ended_at, after_leave)
    
    def test_room_stays_active_with_remaining_participants(self):
        """Test that room stays active when participants remain"""
        # User2 leaves but user1 remains
        self.client.force_authenticate(user=self.user2)
        self.client.post(f'/api/rooms/{self.room_id}/leave/')
        
        # Verify room is still active
        room = Room.objects.get(id=self.room_id)
        self.assertTrue(room.is_active)
        self.assertIsNone(room.ended_at)


class ParticipantStateUpdateTestCase(TestCase):
    """Test participant state updates (Requirement 3.8, 8.3)"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='user1', password='pass123')
        self.client.force_authenticate(user=self.user)
        
        # Create room and join
        response = self.client.post('/api/rooms/', {'name': 'State Test'}, format='json')
        self.room_id = response.data['id']
    
    def test_update_mute_state(self):
        """Test updating is_muted state"""
        response = self.client.patch(
            f'/api/rooms/{self.room_id}/participants/{self.user.id}/',
            {'is_muted': True},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_muted'])
        
        # Verify in database
        participant = RoomParticipant.objects.get(room_id=self.room_id, user=self.user)
        self.assertTrue(participant.is_muted)
    
    def test_update_video_state(self):
        """Test updating is_video_on state"""
        response = self.client.patch(
            f'/api/rooms/{self.room_id}/participants/{self.user.id}/',
            {'is_video_on': False},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_video_on'])
        
        # Verify in database
        participant = RoomParticipant.objects.get(room_id=self.room_id, user=self.user)
        self.assertFalse(participant.is_video_on)
    
    def test_update_screen_sharing_state(self):
        """Test updating is_screen_sharing state"""
        response = self.client.patch(
            f'/api/rooms/{self.room_id}/participants/{self.user.id}/',
            {'is_screen_sharing': True},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_screen_sharing'])
        
        # Verify in database
        participant = RoomParticipant.objects.get(room_id=self.room_id, user=self.user)
        self.assertTrue(participant.is_screen_sharing)
    
    def test_update_multiple_states_simultaneously(self):
        """Test updating multiple states in one request"""
        response = self.client.patch(
            f'/api/rooms/{self.room_id}/participants/{self.user.id}/',
            {
                'is_muted': True,
                'is_video_on': False,
                'is_screen_sharing': True
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_muted'])
        self.assertFalse(response.data['is_video_on'])
        self.assertTrue(response.data['is_screen_sharing'])
        
        # Verify all states in database
        participant = RoomParticipant.objects.get(room_id=self.room_id, user=self.user)
        self.assertTrue(participant.is_muted)
        self.assertFalse(participant.is_video_on)
        self.assertTrue(participant.is_screen_sharing)


class CallHistoryRetrievalTestCase(TestCase):
    """Test call history retrieval with filtering (Requirement 6.2, 6.3, 6.6)"""
    
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.user3 = User.objects.create_user(username='user3', password='pass123')
        self.client.force_authenticate(user=self.user1)
        
        # Create multiple call history records
        self.workspace_id = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
        self.other_workspace_id = 'b2c3d4e5-f6a7-8901-bcde-f12345678901'
        
        # Recent call in workspace 1
        room1 = Room.objects.create(
            name='Recent Call',
            workspace_id=self.workspace_id,
            created_by=self.user1,
            is_active=False,
            ended_at=timezone.now()
        )
        call1 = CallHistory.objects.create(
            room=room1,
            ended_at=timezone.now(),
            duration_seconds=1800,
            participant_count=2
        )
        CallParticipant.objects.create(
            call_history=call1,
            user=self.user1,
            joined_at=call1.started_at,
            left_at=call1.ended_at,
            duration_seconds=1800
        )
        CallParticipant.objects.create(
            call_history=call1,
            user=self.user2,
            joined_at=call1.started_at,
            left_at=call1.ended_at,
            duration_seconds=1800
        )
        
        # Call in different workspace
        room2 = Room.objects.create(
            name='Other Workspace Call',
            workspace_id=self.other_workspace_id,
            created_by=self.user1,
            is_active=False,
            ended_at=timezone.now()
        )
        call2 = CallHistory.objects.create(
            room=room2,
            ended_at=timezone.now(),
            duration_seconds=900,
            participant_count=2
        )
        CallParticipant.objects.create(
            call_history=call2,
            user=self.user1,
            joined_at=call2.started_at,
            left_at=call2.ended_at,
            duration_seconds=900
        )
        
        # Call user1 didn't participate in
        room3 = Room.objects.create(
            name='Other Users Call',
            workspace_id=self.workspace_id,
            created_by=self.user2,
            is_active=False,
            ended_at=timezone.now()
        )
        call3 = CallHistory.objects.create(
            room=room3,
            ended_at=timezone.now(),
            duration_seconds=600,
            participant_count=2
        )
        CallParticipant.objects.create(
            call_history=call3,
            user=self.user2,
            joined_at=call3.started_at,
            left_at=call3.ended_at,
            duration_seconds=600
        )
        CallParticipant.objects.create(
            call_history=call3,
            user=self.user3,
            joined_at=call3.started_at,
            left_at=call3.ended_at,
            duration_seconds=600
        )
    
    def test_get_user_call_history(self):
        """Test retrieving call history for authenticated user"""
        response = self.client.get('/api/call-history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # User1 participated in 2 calls
        self.assertEqual(len(response.data), 2)
        
        # Verify call details are included
        for call in response.data:
            self.assertIn('id', call)
            self.assertIn('room', call)
            self.assertIn('duration_seconds', call)
            self.assertIn('participant_count', call)
            self.assertIn('participants', call)
    
    def test_filter_call_history_by_workspace(self):
        """Test filtering call history by workspace_id"""
        response = self.client.get(
            f'/api/call-history/?workspace_id={self.workspace_id}'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only 1 call in this workspace that user1 participated in
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['room']['workspace_id'],
            self.workspace_id
        )
    
    def test_call_history_excludes_old_calls(self):
        """Test that calls older than 90 days are excluded"""
        # Create old call (100 days ago)
        old_room = Room.objects.create(
            name='Old Call',
            workspace_id=self.workspace_id,
            created_by=self.user1,
            is_active=False
        )
        old_call = CallHistory.objects.create(
            room=old_room,
            ended_at=timezone.now() - timedelta(days=100),
            duration_seconds=1200,
            participant_count=1
        )
        # Update started_at to be old
        CallHistory.objects.filter(id=old_call.id).update(
            started_at=timezone.now() - timedelta(days=100)
        )
        old_call.refresh_from_db()
        
        CallParticipant.objects.create(
            call_history=old_call,
            user=self.user1,
            joined_at=old_call.started_at,
            left_at=old_call.ended_at,
            duration_seconds=1200
        )
        
        response = self.client.get('/api/call-history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should not include the old call
        call_ids = [call['id'] for call in response.data]
        self.assertNotIn(str(old_call.id), call_ids)
    
    def test_call_history_includes_participant_details(self):
        """Test that call history includes participant information"""
        response = self.client.get('/api/call-history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)
        
        # Check first call has participant details
        first_call = response.data[0]
        self.assertIn('participants', first_call)
        self.assertGreater(len(first_call['participants']), 0)
        
        # Verify participant structure
        participant = first_call['participants'][0]
        self.assertIn('user', participant)
        self.assertIn('username', participant['user'])
        self.assertIn('joined_at', participant)
        self.assertIn('duration_seconds', participant)


class ICEServersConfigurationTestCase(TestCase):
    """Test ICE servers endpoint returns proper configuration (Requirement 1.1)"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='user1', password='pass123')
        self.client.force_authenticate(user=self.user)
    
    def test_ice_servers_returns_valid_configuration(self):
        """Test ICE servers endpoint returns valid WebRTC configuration"""
        response = self.client.get('/api/ice-servers/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('iceServers', response.data)
        
        ice_servers = response.data['iceServers']
        self.assertIsInstance(ice_servers, list)
        self.assertGreater(len(ice_servers), 0)
        
        # Verify each server has required fields
        for server in ice_servers:
            self.assertIn('urls', server)
            self.assertIsInstance(server['urls'], str)
            # Should be STUN or TURN server
            self.assertTrue(
                server['urls'].startswith('stun:') or 
                server['urls'].startswith('turn:')
            )
    
    def test_ice_servers_requires_authentication(self):
        """Test ICE servers endpoint requires authentication"""
        # Unauthenticated request
        client = APIClient()
        response = client.get('/api/ice-servers/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
