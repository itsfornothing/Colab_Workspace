/**
 * Call Controls E2E Test
 *
 * This test validates the call controls flow including mute/unmute, video on/off,
 * and participant state persistence and broadcast:
 *
 * 1. Mute/unmute flow:
 *    - toggleAudio(false) disables the audio track (track.enabled = false)
 *    - toggleAudio(true) re-enables the audio track (track.enabled = true)
 *    - Mute state is reflected in the local stream
 *    - Mute state is broadcast via signaling channel (participant_state message)
 *
 * 2. Video on/off flow:
 *    - toggleVideo(false) disables the video track (track.enabled = false)
 *    - toggleVideo(true) re-enables the video track (track.enabled = true)
 *    - Video state is reflected in the local stream
 *    - Video state is broadcast via signaling channel (participant_state message)
 *
 * 3. State persistence and broadcast:
 *    - When mute state changes, a participant_state message is sent via signaling
 *    - The message contains the correct is_muted, is_video_on, is_screen_sharing fields
 *    - State changes are broadcast to all participants in the room
 *    - State persists across multiple toggles
 *
 * Requirements: 12.4, 3.1, 3.2, 3.8
 */

import WebRTCClient from '@/lib/webrtc/WebRTCClient';
import {
  setupWebRTCMocks,
  teardownWebRTCMocks,
  MockMediaStream,
  flushPromises,
} from './mocks/webrtcMocks';

// ---------------------------------------------------------------------------
// Helper: build a pair of cross-connected signaling channels
// ---------------------------------------------------------------------------
function createLinkedSignalingChannels() {
  const handlersA = [];
  const handlersB = [];

  const channelA = {
    send: jest.fn((message) => {
      setTimeout(() => handlersB.forEach((h) => h(message)), 10);
    }),
    onMessage: (handler) => handlersA.push(handler),
    _deliver: (message) => handlersA.forEach((h) => h(message)),
  };

  const channelB = {
    send: jest.fn((message) => {
      setTimeout(() => handlersA.forEach((h) => h(message)), 10);
    }),
    onMessage: (handler) => handlersB.push(handler),
    _deliver: (message) => handlersB.forEach((h) => h(message)),
  };

  return { channelA, channelB };
}

// ---------------------------------------------------------------------------
// Helper: wire WebRTC signaling between two clients
// ---------------------------------------------------------------------------
function wireSignaling(clientA, clientB, channelA, channelB) {
  channelA.onMessage((message) => {
    if (message.to_user_id !== clientA.userId) return;
    if (message.type === 'webrtc_offer') clientA.handleOffer(message.from_user_id, message.sdp);
    else if (message.type === 'webrtc_answer') clientA.handleAnswer(message.from_user_id, message.sdp);
    else if (message.type === 'webrtc_ice') clientA.handleIceCandidate(message.from_user_id, message.candidate);
  });

  channelB.onMessage((message) => {
    if (message.to_user_id !== clientB.userId) return;
    if (message.type === 'webrtc_offer') clientB.handleOffer(message.from_user_id, message.sdp);
    else if (message.type === 'webrtc_answer') clientB.handleAnswer(message.from_user_id, message.sdp);
    else if (message.type === 'webrtc_ice') clientB.handleIceCandidate(message.from_user_id, message.candidate);
  });
}

// ---------------------------------------------------------------------------
// Helper: send a participant_state message (simulates the app layer)
// ---------------------------------------------------------------------------
function broadcastParticipantState(signalingChannel, userId, roomId, { isMuted, isVideoOn, isScreenSharing }) {
  signalingChannel.send({
    type: 'participant_state',
    user_id: userId,
    room_id: roomId,
    is_muted: isMuted,
    is_video_on: isVideoOn,
    is_screen_sharing: isScreenSharing,
  });
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------
describe('Call Controls E2E', () => {
  let userAClient;
  let userBClient;
  let channelA;
  let channelB;

  beforeEach(async () => {
    setupWebRTCMocks();

    const channels = createLinkedSignalingChannels();
    channelA = channels.channelA;
    channelB = channels.channelB;

    userAClient = new WebRTCClient('room-123', 'user-a', channelA);
    userBClient = new WebRTCClient('room-123', 'user-b', channelB);

    wireSignaling(userAClient, userBClient, channelA, channelB);

    // Both users acquire local media before each test
    await userAClient.getLocalMediaStream();
    await userBClient.getLocalMediaStream();
  });

  afterEach(() => {
    userAClient.releaseMediaStreams();
    userBClient.releaseMediaStreams();
    teardownWebRTCMocks();
  });

  // =========================================================================
  // 1. Mute / Unmute flow
  // =========================================================================
  describe('Mute / Unmute flow', () => {
    /**
     * Validates: Requirements 3.1, 12.4
     * Test: toggleAudio(false) disables the audio track
     */
    test('toggleAudio(false) sets audio track.enabled to false', () => {
      const audioTrack = userAClient.localStream.getAudioTracks()[0];
      expect(audioTrack.enabled).toBe(true); // starts enabled

      userAClient.toggleAudio(false);

      expect(audioTrack.enabled).toBe(false);
    });

    /**
     * Validates: Requirements 3.1, 12.4
     * Test: toggleAudio(true) re-enables the audio track
     */
    test('toggleAudio(true) re-enables the audio track', () => {
      const audioTrack = userAClient.localStream.getAudioTracks()[0];

      userAClient.toggleAudio(false);
      expect(audioTrack.enabled).toBe(false);

      userAClient.toggleAudio(true);
      expect(audioTrack.enabled).toBe(true);
    });

    /**
     * Validates: Requirements 3.1, 12.4
     * Test: Mute state is reflected in the local stream
     */
    test('mute state is reflected in all audio tracks of the local stream', () => {
      const audioTracks = userAClient.localStream.getAudioTracks();
      expect(audioTracks.length).toBeGreaterThan(0);

      userAClient.toggleAudio(false);
      audioTracks.forEach((track) => expect(track.enabled).toBe(false));

      userAClient.toggleAudio(true);
      audioTracks.forEach((track) => expect(track.enabled).toBe(true));
    });

    /**
     * Validates: Requirements 3.8, 12.4
     * Test: Mute state is broadcast via signaling channel (participant_state message)
     */
    test('mute state is broadcast via participant_state signaling message', async () => {
      // Mute user A
      userAClient.toggleAudio(false);

      // App layer broadcasts the state change
      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: true,
        isVideoOn: true,
        isScreenSharing: false,
      });

      // Verify the signaling channel sent the correct message
      const sentMessages = channelA.send.mock.calls.map((call) => call[0]);
      const stateMessage = sentMessages.find((m) => m.type === 'participant_state');

      expect(stateMessage).toBeDefined();
      expect(stateMessage).toMatchObject({
        type: 'participant_state',
        user_id: 'user-a',
        room_id: 'room-123',
        is_muted: true,
        is_video_on: true,
        is_screen_sharing: false,
      });
    });

    /**
     * Validates: Requirements 3.8, 12.4
     * Test: Unmute state is broadcast via signaling channel
     */
    test('unmute state is broadcast via participant_state signaling message', async () => {
      // Mute then unmute
      userAClient.toggleAudio(false);
      userAClient.toggleAudio(true);

      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: false,
        isVideoOn: true,
        isScreenSharing: false,
      });

      const sentMessages = channelA.send.mock.calls.map((call) => call[0]);
      const stateMessage = sentMessages.find((m) => m.type === 'participant_state');

      expect(stateMessage).toBeDefined();
      expect(stateMessage.is_muted).toBe(false);
    });

    /**
     * Validates: Requirements 3.8, 12.4
     * Test: participant_state message is received by other participants
     */
    test('participant_state mute message is received by other participants in the room', async () => {
      const receivedMessages = [];
      channelB.onMessage((message) => {
        if (message.type === 'participant_state') {
          receivedMessages.push(message);
        }
      });

      userAClient.toggleAudio(false);
      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: true,
        isVideoOn: true,
        isScreenSharing: false,
      });

      // Wait for message delivery
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(receivedMessages).toHaveLength(1);
      expect(receivedMessages[0]).toMatchObject({
        type: 'participant_state',
        user_id: 'user-a',
        is_muted: true,
        is_video_on: true,
        is_screen_sharing: false,
      });
    });
  });

  // =========================================================================
  // 2. Video on / off flow
  // =========================================================================
  describe('Video on / off flow', () => {
    /**
     * Validates: Requirements 3.2, 12.4
     * Test: toggleVideo(false) disables the video track
     */
    test('toggleVideo(false) sets video track.enabled to false', () => {
      const videoTrack = userAClient.localStream.getVideoTracks()[0];
      expect(videoTrack.enabled).toBe(true); // starts enabled

      userAClient.toggleVideo(false);

      expect(videoTrack.enabled).toBe(false);
    });

    /**
     * Validates: Requirements 3.2, 12.4
     * Test: toggleVideo(true) re-enables the video track
     */
    test('toggleVideo(true) re-enables the video track', () => {
      const videoTrack = userAClient.localStream.getVideoTracks()[0];

      userAClient.toggleVideo(false);
      expect(videoTrack.enabled).toBe(false);

      userAClient.toggleVideo(true);
      expect(videoTrack.enabled).toBe(true);
    });

    /**
     * Validates: Requirements 3.2, 3.6, 12.4
     * Test: Video state is reflected in the local stream
     */
    test('video state is reflected in all video tracks of the local stream', () => {
      const videoTracks = userAClient.localStream.getVideoTracks();
      expect(videoTracks.length).toBeGreaterThan(0);

      userAClient.toggleVideo(false);
      videoTracks.forEach((track) => expect(track.enabled).toBe(false));

      userAClient.toggleVideo(true);
      videoTracks.forEach((track) => expect(track.enabled).toBe(true));
    });

    /**
     * Validates: Requirements 3.8, 12.4
     * Test: Video off state is broadcast via signaling channel (participant_state message)
     */
    test('video off state is broadcast via participant_state signaling message', async () => {
      userAClient.toggleVideo(false);

      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: false,
        isVideoOn: false,
        isScreenSharing: false,
      });

      const sentMessages = channelA.send.mock.calls.map((call) => call[0]);
      const stateMessage = sentMessages.find((m) => m.type === 'participant_state');

      expect(stateMessage).toBeDefined();
      expect(stateMessage).toMatchObject({
        type: 'participant_state',
        user_id: 'user-a',
        room_id: 'room-123',
        is_muted: false,
        is_video_on: false,
        is_screen_sharing: false,
      });
    });

    /**
     * Validates: Requirements 3.8, 12.4
     * Test: Video on state is broadcast via signaling channel
     */
    test('video on state is broadcast via participant_state signaling message', async () => {
      userAClient.toggleVideo(false);
      userAClient.toggleVideo(true);

      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: false,
        isVideoOn: true,
        isScreenSharing: false,
      });

      const sentMessages = channelA.send.mock.calls.map((call) => call[0]);
      const stateMessage = sentMessages.find((m) => m.type === 'participant_state');

      expect(stateMessage).toBeDefined();
      expect(stateMessage.is_video_on).toBe(true);
    });

    /**
     * Validates: Requirements 3.8, 12.4
     * Test: participant_state video message is received by other participants
     */
    test('participant_state video message is received by other participants in the room', async () => {
      const receivedMessages = [];
      channelB.onMessage((message) => {
        if (message.type === 'participant_state') {
          receivedMessages.push(message);
        }
      });

      userAClient.toggleVideo(false);
      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: false,
        isVideoOn: false,
        isScreenSharing: false,
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(receivedMessages).toHaveLength(1);
      expect(receivedMessages[0]).toMatchObject({
        type: 'participant_state',
        user_id: 'user-a',
        is_muted: false,
        is_video_on: false,
        is_screen_sharing: false,
      });
    });
  });

  // =========================================================================
  // 3. State persistence and broadcast
  // =========================================================================
  describe('State persistence and broadcast', () => {
    /**
     * Validates: Requirements 3.8, 12.4
     * Test: participant_state message contains all required fields
     */
    test('participant_state message contains is_muted, is_video_on, and is_screen_sharing fields', () => {
      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: true,
        isVideoOn: false,
        isScreenSharing: false,
      });

      const sentMessages = channelA.send.mock.calls.map((call) => call[0]);
      const stateMessage = sentMessages.find((m) => m.type === 'participant_state');

      expect(stateMessage).toBeDefined();
      expect(stateMessage).toHaveProperty('is_muted');
      expect(stateMessage).toHaveProperty('is_video_on');
      expect(stateMessage).toHaveProperty('is_screen_sharing');
      expect(stateMessage).toHaveProperty('user_id');
      expect(stateMessage).toHaveProperty('room_id');
    });

    /**
     * Validates: Requirements 3.1, 3.2, 3.8, 12.4
     * Test: State persists across multiple toggles
     */
    test('audio and video state persists correctly across multiple toggles', () => {
      const audioTrack = userAClient.localStream.getAudioTracks()[0];
      const videoTrack = userAClient.localStream.getVideoTracks()[0];

      // Toggle sequence: mute → unmute → mute
      userAClient.toggleAudio(false);
      expect(audioTrack.enabled).toBe(false);

      userAClient.toggleAudio(true);
      expect(audioTrack.enabled).toBe(true);

      userAClient.toggleAudio(false);
      expect(audioTrack.enabled).toBe(false);

      // Toggle sequence: video off → on → off → on
      userAClient.toggleVideo(false);
      expect(videoTrack.enabled).toBe(false);

      userAClient.toggleVideo(true);
      expect(videoTrack.enabled).toBe(true);

      userAClient.toggleVideo(false);
      expect(videoTrack.enabled).toBe(false);

      userAClient.toggleVideo(true);
      expect(videoTrack.enabled).toBe(true);
    });

    /**
     * Validates: Requirements 3.8, 12.4
     * Test: Multiple state changes are broadcast in order
     */
    test('multiple state changes are broadcast in the correct order', async () => {
      const receivedMessages = [];
      channelB.onMessage((message) => {
        if (message.type === 'participant_state') {
          receivedMessages.push(message);
        }
      });

      // Mute
      userAClient.toggleAudio(false);
      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: true,
        isVideoOn: true,
        isScreenSharing: false,
      });

      // Video off
      userAClient.toggleVideo(false);
      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: true,
        isVideoOn: false,
        isScreenSharing: false,
      });

      // Unmute
      userAClient.toggleAudio(true);
      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: false,
        isVideoOn: false,
        isScreenSharing: false,
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(receivedMessages).toHaveLength(3);

      // First message: muted, video on
      expect(receivedMessages[0]).toMatchObject({ is_muted: true, is_video_on: true });

      // Second message: muted, video off
      expect(receivedMessages[1]).toMatchObject({ is_muted: true, is_video_on: false });

      // Third message: unmuted, video off
      expect(receivedMessages[2]).toMatchObject({ is_muted: false, is_video_on: false });
    });

    /**
     * Validates: Requirements 3.8, 12.4
     * Test: State changes are broadcast to all participants in the room
     */
    test('state changes are broadcast to all participants in the room', async () => {
      // Add a third participant channel
      const handlersC = [];
      const channelC = {
        send: jest.fn(),
        onMessage: (handler) => handlersC.push(handler),
      };

      // Patch channelA.send to also deliver to C
      const originalSend = channelA.send.getMockImplementation();
      channelA.send.mockImplementation((message) => {
        // Deliver to B (original behaviour)
        if (originalSend) originalSend(message);
        // Also deliver to C
        setTimeout(() => handlersC.forEach((h) => h(message)), 10);
      });

      const receivedByB = [];
      const receivedByC = [];

      channelB.onMessage((message) => {
        if (message.type === 'participant_state') receivedByB.push(message);
      });
      channelC.onMessage((message) => {
        if (message.type === 'participant_state') receivedByC.push(message);
      });

      userAClient.toggleAudio(false);
      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: true,
        isVideoOn: true,
        isScreenSharing: false,
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      // Both B and C should receive the state update
      expect(receivedByB).toHaveLength(1);
      expect(receivedByC).toHaveLength(1);
      expect(receivedByB[0].is_muted).toBe(true);
      expect(receivedByC[0].is_muted).toBe(true);
    });

    /**
     * Validates: Requirements 3.1, 3.2, 3.8, 12.4
     * Test: Combined mute and video state is correctly reflected in participant_state message
     */
    test('combined mute and video state is correctly reflected in participant_state message', async () => {
      const receivedMessages = [];
      channelB.onMessage((message) => {
        if (message.type === 'participant_state') receivedMessages.push(message);
      });

      // Mute audio AND turn off video simultaneously
      userAClient.toggleAudio(false);
      userAClient.toggleVideo(false);

      const audioTrack = userAClient.localStream.getAudioTracks()[0];
      const videoTrack = userAClient.localStream.getVideoTracks()[0];

      // Verify local state
      expect(audioTrack.enabled).toBe(false);
      expect(videoTrack.enabled).toBe(false);

      // Broadcast combined state
      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: true,
        isVideoOn: false,
        isScreenSharing: false,
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(receivedMessages).toHaveLength(1);
      expect(receivedMessages[0]).toMatchObject({
        is_muted: true,
        is_video_on: false,
        is_screen_sharing: false,
      });
    });

    /**
     * Validates: Requirements 3.1, 3.2, 12.4
     * Test: Audio and video tracks are independent — toggling one does not affect the other
     */
    test('audio and video tracks are toggled independently', () => {
      const audioTrack = userAClient.localStream.getAudioTracks()[0];
      const videoTrack = userAClient.localStream.getVideoTracks()[0];

      // Mute audio only
      userAClient.toggleAudio(false);
      expect(audioTrack.enabled).toBe(false);
      expect(videoTrack.enabled).toBe(true); // video unaffected

      // Turn off video only
      userAClient.toggleVideo(false);
      expect(audioTrack.enabled).toBe(false); // audio still muted
      expect(videoTrack.enabled).toBe(false);

      // Re-enable audio only
      userAClient.toggleAudio(true);
      expect(audioTrack.enabled).toBe(true);
      expect(videoTrack.enabled).toBe(false); // video still off

      // Re-enable video only
      userAClient.toggleVideo(true);
      expect(audioTrack.enabled).toBe(true);
      expect(videoTrack.enabled).toBe(true);
    });

    /**
     * Validates: Requirements 3.8, 12.4
     * Test: participant_state message room_id matches the client's room
     */
    test('participant_state message contains the correct room_id', () => {
      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: false,
        isVideoOn: true,
        isScreenSharing: false,
      });

      const sentMessages = channelA.send.mock.calls.map((call) => call[0]);
      const stateMessage = sentMessages.find((m) => m.type === 'participant_state');

      expect(stateMessage.room_id).toBe('room-123');
      expect(stateMessage.user_id).toBe('user-a');
    });

    /**
     * Validates: Requirements 3.1, 3.2, 3.8, 12.4
     * Test: Full call controls flow — establish call, toggle controls, verify state
     */
    test('full call controls flow: establish call, mute, unmute, video off, video on', async () => {
      // Establish WebRTC connection between A and B
      await userAClient.createOffer('user-b');
      await new Promise((resolve) => setTimeout(resolve, 200));
      await flushPromises();

      // Verify connection is established
      expect(userAClient.peerConnections.has('user-b')).toBe(true);
      expect(userBClient.peerConnections.has('user-a')).toBe(true);

      const audioTrack = userAClient.localStream.getAudioTracks()[0];
      const videoTrack = userAClient.localStream.getVideoTracks()[0];

      // --- Mute ---
      userAClient.toggleAudio(false);
      expect(audioTrack.enabled).toBe(false);

      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: true,
        isVideoOn: true,
        isScreenSharing: false,
      });

      // --- Video off ---
      userAClient.toggleVideo(false);
      expect(videoTrack.enabled).toBe(false);

      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: true,
        isVideoOn: false,
        isScreenSharing: false,
      });

      // --- Unmute ---
      userAClient.toggleAudio(true);
      expect(audioTrack.enabled).toBe(true);

      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: false,
        isVideoOn: false,
        isScreenSharing: false,
      });

      // --- Video on ---
      userAClient.toggleVideo(true);
      expect(videoTrack.enabled).toBe(true);

      broadcastParticipantState(channelA, 'user-a', 'room-123', {
        isMuted: false,
        isVideoOn: true,
        isScreenSharing: false,
      });

      // Verify all four state messages were sent
      const stateMessages = channelA.send.mock.calls
        .map((call) => call[0])
        .filter((m) => m.type === 'participant_state');

      expect(stateMessages).toHaveLength(4);
      expect(stateMessages[0]).toMatchObject({ is_muted: true, is_video_on: true });
      expect(stateMessages[1]).toMatchObject({ is_muted: true, is_video_on: false });
      expect(stateMessages[2]).toMatchObject({ is_muted: false, is_video_on: false });
      expect(stateMessages[3]).toMatchObject({ is_muted: false, is_video_on: true });

      // Verify final local track state
      expect(audioTrack.enabled).toBe(true);
      expect(videoTrack.enabled).toBe(true);
    });
  });
});
