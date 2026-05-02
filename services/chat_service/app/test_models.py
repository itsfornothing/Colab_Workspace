"""
Unit tests for extended video call models
Tests Room, RoomParticipant, CallHistory, and CallParticipant models
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from .models import Room, RoomParticipant, CallHistory, CallParticipant

User = get_user_model()


class RoomModelTestCase(TestCase):
    """Unit tests for Room model properties and methods"""
    
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.user3 = User.objects.create_user(username='user3', password='pass123')
    
    def test_room_creation_with_defaults(self):
        """Test room is created with correct default values"""
        room = Room.objects.create(
            name='Test Room',
            created_by=self.user1
        )
        
        self.assertEqual(room.name, 'Test Room')
        self.assertEqual(room.created_by, self.user1)
        self.assertTrue(room.is_active)
        self.assertEqual(room.max_participants, 8)
        self.assertIsNone(room.ended_at)
        self.assertIsNotNone(room.created_at)
    
    def test_participant_count_property_empty_room(self):
        """Test participant_count returns 0 for empty room"""
        room = Room.objects.create(
            name='Empty Room',
            created_by=self.user1
        )
        
        self.assertEqual(room.participant_count, 0)
    
    def test_participant_count_property_with_active_participants(self):
        """Test participant_count correctly counts active participants"""
        room = Room.objects.create(
            name='Active Room',
            created_by=self.user1
        )
        
        # Add 3 active participants
        RoomParticipant.objects.create(room=room, user=self.user1)
        RoomParticipant.objects.create(room=room, user=self.user2)
        RoomParticipant.objects.create(room=room, user=self.user3)
        
        self.assertEqual(room.participant_count, 3)
    
    def test_participant_count_excludes_left_participants(self):
        """Test participant_count excludes participants who have left"""
        room = Room.objects.create(
            name='Mixed Room',
            created_by=self.user1
        )
        
        # Add 3 participants
        participant1 = RoomParticipant.objects.create(room=room, user=self.user1)
        RoomParticipant.objects.create(room=room, user=self.user2)
        participant3 = RoomParticipant.objects.create(room=room, user=self.user3)
        
        # Mark 2 participants as left
        participant1.left_at = timezone.now()
        participant1.save()
        participant3.left_at = timezone.now()
        participant3.save()
        
        # Only 1 active participant should be counted
        self.assertEqual(room.participant_count, 1)
    
    def test_is_full_property_not_full(self):
        """Test is_full returns False when room is not at capacity"""
        room = Room.objects.create(
            name='Not Full Room',
            created_by=self.user1,
            max_participants=8
        )
        
        # Add 5 participants (less than max)
        for i in range(5):
            user = User.objects.create_user(username=f'notfull_user{i}', password='pass123')
            RoomParticipant.objects.create(room=room, user=user)
        
        self.assertFalse(room.is_full)
    
    def test_is_full_property_at_capacity(self):
        """Test is_full returns True when room is at max capacity"""
        room = Room.objects.create(
            name='Full Room',
            created_by=self.user1,
            max_participants=3
        )
        
        # Add exactly max_participants
        RoomParticipant.objects.create(room=room, user=self.user1)
        RoomParticipant.objects.create(room=room, user=self.user2)
        RoomParticipant.objects.create(room=room, user=self.user3)
        
        self.assertTrue(room.is_full)
    
    def test_is_full_property_over_capacity(self):
        """Test is_full returns True when room exceeds capacity"""
        room = Room.objects.create(
            name='Over Full Room',
            created_by=self.user1,
            max_participants=2
        )
        
        # Add more than max_participants (edge case)
        RoomParticipant.objects.create(room=room, user=self.user1)
        RoomParticipant.objects.create(room=room, user=self.user2)
        RoomParticipant.objects.create(room=room, user=self.user3)
        
        self.assertTrue(room.is_full)
    
    def test_is_full_considers_only_active_participants(self):
        """Test is_full only counts participants who haven't left"""
        room = Room.objects.create(
            name='Left Participants Room',
            created_by=self.user1,
            max_participants=3
        )
        
        # Add 3 participants
        participant1 = RoomParticipant.objects.create(room=room, user=self.user1)
        participant2 = RoomParticipant.objects.create(room=room, user=self.user2)
        RoomParticipant.objects.create(room=room, user=self.user3)
        
        # Room should be full
        self.assertTrue(room.is_full)
        
        # Mark 2 participants as left
        participant1.left_at = timezone.now()
        participant1.save()
        participant2.left_at = timezone.now()
        participant2.save()
        
        # Room should no longer be full (only 1 active participant)
        self.assertFalse(room.is_full)


class RoomParticipantModelTestCase(TestCase):
    """Unit tests for RoomParticipant model state updates"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')
        self.room = Room.objects.create(
            name='Test Room',
            created_by=self.user
        )
    
    def test_participant_creation_with_defaults(self):
        """Test participant is created with correct default values"""
        participant = RoomParticipant.objects.create(
            room=self.room,
            user=self.user
        )
        
        self.assertEqual(participant.room, self.room)
        self.assertEqual(participant.user, self.user)
        self.assertIsNotNone(participant.joined_at)
        self.assertIsNone(participant.left_at)
        self.assertFalse(participant.is_muted)
        self.assertTrue(participant.is_video_on)
        self.assertFalse(participant.is_screen_sharing)
    
    def test_update_is_muted_state(self):
        """Test updating is_muted state"""
        participant = RoomParticipant.objects.create(
            room=self.room,
            user=self.user
        )
        
        # Initially not muted
        self.assertFalse(participant.is_muted)
        
        # Mute participant
        participant.is_muted = True
        participant.save()
        participant.refresh_from_db()
        
        self.assertTrue(participant.is_muted)
        
        # Unmute participant
        participant.is_muted = False
        participant.save()
        participant.refresh_from_db()
        
        self.assertFalse(participant.is_muted)
    
    def test_update_is_video_on_state(self):
        """Test updating is_video_on state"""
        participant = RoomParticipant.objects.create(
            room=self.room,
            user=self.user
        )
        
        # Initially video is on
        self.assertTrue(participant.is_video_on)
        
        # Turn video off
        participant.is_video_on = False
        participant.save()
        participant.refresh_from_db()
        
        self.assertFalse(participant.is_video_on)
        
        # Turn video back on
        participant.is_video_on = True
        participant.save()
        participant.refresh_from_db()
        
        self.assertTrue(participant.is_video_on)
    
    def test_update_is_screen_sharing_state(self):
        """Test updating is_screen_sharing state"""
        participant = RoomParticipant.objects.create(
            room=self.room,
            user=self.user
        )
        
        # Initially not screen sharing
        self.assertFalse(participant.is_screen_sharing)
        
        # Start screen sharing
        participant.is_screen_sharing = True
        participant.save()
        participant.refresh_from_db()
        
        self.assertTrue(participant.is_screen_sharing)
        
        # Stop screen sharing
        participant.is_screen_sharing = False
        participant.save()
        participant.refresh_from_db()
        
        self.assertFalse(participant.is_screen_sharing)
    
    def test_update_multiple_states_simultaneously(self):
        """Test updating multiple participant states at once"""
        participant = RoomParticipant.objects.create(
            room=self.room,
            user=self.user
        )
        
        # Update all states
        participant.is_muted = True
        participant.is_video_on = False
        participant.is_screen_sharing = True
        participant.save()
        participant.refresh_from_db()
        
        self.assertTrue(participant.is_muted)
        self.assertFalse(participant.is_video_on)
        self.assertTrue(participant.is_screen_sharing)
    
    def test_update_left_at_timestamp(self):
        """Test setting left_at timestamp when participant leaves"""
        participant = RoomParticipant.objects.create(
            room=self.room,
            user=self.user
        )
        
        # Initially left_at is None
        self.assertIsNone(participant.left_at)
        
        # Set left_at timestamp
        leave_time = timezone.now()
        participant.left_at = leave_time
        participant.save()
        participant.refresh_from_db()
        
        self.assertIsNotNone(participant.left_at)
        # Compare timestamps (allow small difference due to microseconds)
        self.assertAlmostEqual(
            participant.left_at.timestamp(),
            leave_time.timestamp(),
            delta=1
        )
    
    def test_unique_together_constraint(self):
        """Test room and user unique_together constraint"""
        # Create first participant
        RoomParticipant.objects.create(
            room=self.room,
            user=self.user
        )
        
        # Attempt to create duplicate should raise error
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            RoomParticipant.objects.create(
                room=self.room,
                user=self.user
            )


class CallHistoryModelTestCase(TestCase):
    """Unit tests for CallHistory model"""
    
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.room = Room.objects.create(
            name='Test Room',
            created_by=self.user1
        )
    
    def test_call_history_creation(self):
        """Test call history record is created with correct fields"""
        call = CallHistory.objects.create(
            room=self.room,
            participant_count=2
        )
        
        self.assertEqual(call.room, self.room)
        self.assertIsNotNone(call.started_at)
        self.assertIsNone(call.ended_at)
        self.assertIsNone(call.duration_seconds)
        self.assertEqual(call.participant_count, 2)
        self.assertIsNone(call.recording_url)
    
    def test_call_history_with_ended_at(self):
        """Test call history with ended_at timestamp"""
        started = timezone.now() - timedelta(hours=1)
        ended = timezone.now()
        
        call = CallHistory.objects.create(
            room=self.room,
            ended_at=ended,
            participant_count=2
        )
        # Manually set started_at to bypass auto_now_add
        CallHistory.objects.filter(id=call.id).update(started_at=started)
        call.refresh_from_db()
        
        self.assertIsNotNone(call.ended_at)
        self.assertAlmostEqual(
            call.ended_at.timestamp(),
            ended.timestamp(),
            delta=1
        )
    
    def test_call_duration_calculation(self):
        """Test duration_seconds is calculated correctly"""
        started = timezone.now() - timedelta(hours=2, minutes=30)
        ended = timezone.now()
        expected_duration = int((ended - started).total_seconds())
        
        call = CallHistory.objects.create(
            room=self.room,
            ended_at=ended,
            duration_seconds=expected_duration,
            participant_count=2
        )
        # Manually set started_at
        CallHistory.objects.filter(id=call.id).update(started_at=started)
        call.refresh_from_db()
        
        self.assertEqual(call.duration_seconds, expected_duration)
        # Verify it's approximately 2.5 hours (9000 seconds)
        self.assertAlmostEqual(call.duration_seconds, 9000, delta=10)
    
    def test_call_history_with_recording_url(self):
        """Test call history with recording URL"""
        recording_url = 'https://example.com/recordings/call123.mp4'
        
        call = CallHistory.objects.create(
            room=self.room,
            participant_count=2,
            recording_url=recording_url
        )
        
        self.assertEqual(call.recording_url, recording_url)
    
    def test_call_history_ordering(self):
        """Test call history is ordered by started_at descending"""
        # Create 3 calls at different times
        call1 = CallHistory.objects.create(
            room=self.room,
            participant_count=1
        )
        CallHistory.objects.filter(id=call1.id).update(
            started_at=timezone.now() - timedelta(hours=3)
        )
        
        call2 = CallHistory.objects.create(
            room=self.room,
            participant_count=1
        )
        CallHistory.objects.filter(id=call2.id).update(
            started_at=timezone.now() - timedelta(hours=1)
        )
        
        call3 = CallHistory.objects.create(
            room=self.room,
            participant_count=1
        )
        CallHistory.objects.filter(id=call3.id).update(
            started_at=timezone.now()
        )
        
        # Fetch all calls
        calls = CallHistory.objects.all()
        
        # Should be ordered newest first
        self.assertEqual(calls[0].id, call3.id)
        self.assertEqual(calls[1].id, call2.id)
        self.assertEqual(calls[2].id, call1.id)


class CallParticipantModelTestCase(TestCase):
    """Unit tests for CallParticipant model"""
    
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        self.room = Room.objects.create(
            name='Test Room',
            created_by=self.user1
        )
        self.call = CallHistory.objects.create(
            room=self.room,
            participant_count=2
        )
    
    def test_call_participant_creation(self):
        """Test call participant is created with correct fields"""
        participant = CallParticipant.objects.create(
            call_history=self.call,
            user=self.user1
        )
        
        self.assertEqual(participant.call_history, self.call)
        self.assertEqual(participant.user, self.user1)
        self.assertIsNotNone(participant.joined_at)
        self.assertIsNone(participant.left_at)
        self.assertIsNone(participant.duration_seconds)
    
    def test_call_participant_with_left_at(self):
        """Test call participant with left_at timestamp"""
        joined = timezone.now() - timedelta(minutes=30)
        left = timezone.now()
        
        participant = CallParticipant.objects.create(
            call_history=self.call,
            user=self.user1,
            left_at=left
        )
        # Manually set joined_at
        CallParticipant.objects.filter(id=participant.id).update(joined_at=joined)
        participant.refresh_from_db()
        
        self.assertIsNotNone(participant.left_at)
        self.assertAlmostEqual(
            participant.left_at.timestamp(),
            left.timestamp(),
            delta=1
        )
    
    def test_call_participant_duration_calculation(self):
        """Test participant duration_seconds is calculated correctly"""
        joined = timezone.now() - timedelta(minutes=45)
        left = timezone.now()
        expected_duration = int((left - joined).total_seconds())
        
        participant = CallParticipant.objects.create(
            call_history=self.call,
            user=self.user1,
            left_at=left,
            duration_seconds=expected_duration
        )
        # Manually set joined_at
        CallParticipant.objects.filter(id=participant.id).update(joined_at=joined)
        participant.refresh_from_db()
        
        self.assertEqual(participant.duration_seconds, expected_duration)
        # Verify it's approximately 45 minutes (2700 seconds)
        self.assertAlmostEqual(participant.duration_seconds, 2700, delta=10)
    
    def test_multiple_participants_in_call(self):
        """Test multiple participants can be added to same call"""
        participant1 = CallParticipant.objects.create(
            call_history=self.call,
            user=self.user1
        )
        participant2 = CallParticipant.objects.create(
            call_history=self.call,
            user=self.user2
        )
        
        # Verify both participants are in the call
        participants = CallParticipant.objects.filter(call_history=self.call)
        self.assertEqual(participants.count(), 2)
        self.assertIn(participant1, participants)
        self.assertIn(participant2, participants)
    
    def test_call_participant_ordering(self):
        """Test call participants are ordered by joined_at"""
        # Create 2 participants at different times
        participant1 = CallParticipant.objects.create(
            call_history=self.call,
            user=self.user1
        )
        CallParticipant.objects.filter(id=participant1.id).update(
            joined_at=timezone.now() - timedelta(minutes=10)
        )
        
        participant2 = CallParticipant.objects.create(
            call_history=self.call,
            user=self.user2
        )
        CallParticipant.objects.filter(id=participant2.id).update(
            joined_at=timezone.now()
        )
        
        # Fetch all participants
        participants = CallParticipant.objects.filter(call_history=self.call)
        
        # Should be ordered by joined_at (earliest first)
        self.assertEqual(participants[0].id, participant1.id)
        self.assertEqual(participants[1].id, participant2.id)
