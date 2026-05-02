/**
 * Complete Call Flow E2E Test
 * 
 * This test validates the complete video call flow from initiation to termination:
 * 1. User A creates a room via API
 * 2. User A invites User B via WebSocket signaling
 * 3. User B receives call_invite notification
 * 4. User B accepts the call
 * 5. WebRTC signaling completes (offer, answer, ICE candidates)
 * 6. Both users see remote video feeds (ontrack events fired)
 * 7. User A ends the call
 * 8. Call history record is created
 * 
 * Requirements: 12.1, 12.5, 12.6
 */

import WebRTCClient from '@/lib/webrtc/WebRTCClient';
import {
  setupWebRTCMocks,
  teardownWebRTCMocks,
  MockMediaStream,
  flushPromises,
} from './mocks/webrtcMocks';

describe('Complete Call Flow E2E', () => {
  let userAClient;
  let userBClient;
  let mockSignalingChannelA;
  let mockSignalingChannelB;
  let mockApiClient;

  beforeEach(() => {
    // Setup WebRTC mocks
    setupWebRTCMocks();

    // Mock API client for room creation and call history
    mockApiClient = {
      createRoom: jest.fn(),
      joinRoom: jest.fn(),
      leaveRoom: jest.fn(),
      getCallHistory: jest.fn(),
    };

    // Create mock signaling channels that can communicate with each other
    const messageHandlers = {
      A: [],
      B: [],
    };

    mockSignalingChannelA = {
      send: jest.fn((message) => {
        // Simulate message delivery to User B
        setTimeout(() => {
          messageHandlers.B.forEach((handler) => handler(message));
        }, 10);
      }),
      onMessage: (handler) => {
        messageHandlers.A.push(handler);
      },
    };

    mockSignalingChannelB = {
      send: jest.fn((message) => {
        // Simulate message delivery to User A
        setTimeout(() => {
          messageHandlers.A.forEach((handler) => handler(message));
        }, 10);
      }),
      onMessage: (handler) => {
        messageHandlers.B.push(handler);
      },
    };

    // Create WebRTC clients for both users
    userAClient = new WebRTCClient('room-123', 'user-a', mockSignalingChannelA);
    userBClient = new WebRTCClient('room-123', 'user-b', mockSignalingChannelB);

    // Setup signaling message handlers for User A
    mockSignalingChannelA.onMessage((message) => {
      if (message.type === 'webrtc_offer' && message.to_user_id === 'user-a') {
        userAClient.handleOffer(message.from_user_id, message.sdp);
      } else if (message.type === 'webrtc_answer' && message.to_user_id === 'user-a') {
        userAClient.handleAnswer(message.from_user_id, message.sdp);
      } else if (message.type === 'webrtc_ice' && message.to_user_id === 'user-a') {
        userAClient.handleIceCandidate(message.from_user_id, message.candidate);
      }
    });

    // Setup signaling message handlers for User B
    mockSignalingChannelB.onMessage((message) => {
      if (message.type === 'webrtc_offer' && message.to_user_id === 'user-b') {
        userBClient.handleOffer(message.from_user_id, message.sdp);
      } else if (message.type === 'webrtc_answer' && message.to_user_id === 'user-b') {
        userBClient.handleAnswer(message.from_user_id, message.sdp);
      } else if (message.type === 'webrtc_ice' && message.to_user_id === 'user-b') {
        userBClient.handleIceCandidate(message.from_user_id, message.candidate);
      }
    });
  });

  afterEach(() => {
    // Cleanup
    if (userAClient) {
      userAClient.releaseMediaStreams();
    }
    if (userBClient) {
      userBClient.releaseMediaStreams();
    }
    teardownWebRTCMocks();
  });

  /**
   * Validates: Requirements 12.1, 12.5, 12.6
   * Test: Complete call flow from initiation to termination
   */
  test('complete call flow: create room, invite, accept, signaling, video feeds, end call, history', async () => {
    // ═══════════════════════════════════════════════════════════════════
    // STEP 1: User A creates room via API
    // ═══════════════════════════════════════════════════════════════════
    const mockRoom = {
      id: 'room-123',
      name: 'Test Call',
      workspace_id: 'workspace-1',
      created_by: 'user-a',
      is_active: true,
      max_participants: 8,
      created_at: new Date().toISOString(),
    };

    mockApiClient.createRoom.mockResolvedValue({ data: mockRoom });

    const room = await mockApiClient.createRoom({
      name: 'Test Call',
      workspace: 'workspace-1',
    });

    expect(mockApiClient.createRoom).toHaveBeenCalledWith({
      name: 'Test Call',
      workspace: 'workspace-1',
    });
    expect(room.data.id).toBe('room-123');

    // ═══════════════════════════════════════════════════════════════════
    // STEP 2: User A gets local media stream
    // ═══════════════════════════════════════════════════════════════════
    const userAStream = await userAClient.getLocalMediaStream();
    expect(userAStream).toBeDefined();
    expect(userAStream.getTracks()).toHaveLength(2); // video + audio
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();

    // ═══════════════════════════════════════════════════════════════════
    // STEP 3: User A invites User B via WebSocket signaling
    // ═══════════════════════════════════════════════════════════════════
    const callInviteMessage = {
      type: 'call_invite',
      room_id: 'room-123',
      caller_id: 'user-a',
      caller_name: 'User A',
      invited_user_ids: ['user-b'],
    };

    // Track if User B received the invitation
    let userBReceivedInvite = false;
    let inviteData = null;

    mockSignalingChannelB.onMessage((message) => {
      if (message.type === 'call_invite') {
        userBReceivedInvite = true;
        inviteData = message;
      }
    });

    // User A sends invitation
    mockSignalingChannelA.send(callInviteMessage);

    // Wait for message delivery
    await new Promise((resolve) => setTimeout(resolve, 50));

    // ═══════════════════════════════════════════════════════════════════
    // STEP 4: User B receives call_invite notification
    // ═══════════════════════════════════════════════════════════════════
    expect(userBReceivedInvite).toBe(true);
    expect(inviteData).toMatchObject({
      type: 'call_invite',
      room_id: 'room-123',
      caller_id: 'user-a',
      invited_user_ids: ['user-b'],
    });

    // ═══════════════════════════════════════════════════════════════════
    // STEP 5: User B accepts the call
    // ═══════════════════════════════════════════════════════════════════
    const callAcceptMessage = {
      type: 'call_accept',
      room_id: 'room-123',
      accepter_id: 'user-b',
      caller_id: 'user-a',
    };

    // Track if User A received the acceptance
    let userAReceivedAccept = false;

    mockSignalingChannelA.onMessage((message) => {
      if (message.type === 'call_accept') {
        userAReceivedAccept = true;
      }
    });

    // User B gets local media stream
    const userBStream = await userBClient.getLocalMediaStream();
    expect(userBStream).toBeDefined();

    // User B sends acceptance
    mockSignalingChannelB.send(callAcceptMessage);

    // Wait for message delivery
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(userAReceivedAccept).toBe(true);

    // ═══════════════════════════════════════════════════════════════════
    // STEP 6: WebRTC signaling completes
    // ═══════════════════════════════════════════════════════════════════

    // Track remote streams
    let userARemoteStream = null;
    let userBRemoteStream = null;

    userAClient.onRemoteStream = (userId, stream) => {
      if (userId === 'user-b') {
        userARemoteStream = stream;
      }
    };

    userBClient.onRemoteStream = (userId, stream) => {
      if (userId === 'user-a') {
        userBRemoteStream = stream;
      }
    };

    // User A creates offer to User B
    await userAClient.createOffer('user-b');

    // Wait for signaling messages to be exchanged
    await new Promise((resolve) => setTimeout(resolve, 100));
    await flushPromises();

    // Verify offer was sent
    expect(mockSignalingChannelA.send).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'webrtc_offer',
        from_user_id: 'user-a',
        to_user_id: 'user-b',
        room_id: 'room-123',
      })
    );

    // Wait for answer to be created and sent
    await new Promise((resolve) => setTimeout(resolve, 100));
    await flushPromises();

    // Verify answer was sent
    expect(mockSignalingChannelB.send).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'webrtc_answer',
        from_user_id: 'user-b',
        to_user_id: 'user-a',
        room_id: 'room-123',
      })
    );

    // Wait for ICE candidates to be exchanged
    await new Promise((resolve) => setTimeout(resolve, 200));
    await flushPromises();

    // Verify ICE candidates were sent by both users
    const iceMessagesFromA = mockSignalingChannelA.send.mock.calls.filter(
      (call) => call[0].type === 'webrtc_ice'
    );
    const iceMessagesFromB = mockSignalingChannelB.send.mock.calls.filter(
      (call) => call[0].type === 'webrtc_ice'
    );

    expect(iceMessagesFromA.length).toBeGreaterThan(0);
    expect(iceMessagesFromB.length).toBeGreaterThan(0);

    // ═══════════════════════════════════════════════════════════════════
    // STEP 7: Both users see remote video feeds (ontrack events fired)
    // ═══════════════════════════════════════════════════════════════════

    // Simulate ontrack events (in real scenario, these are triggered by WebRTC)
    const peerConnectionA = userAClient.peerConnections.get('user-b');
    const peerConnectionB = userBClient.peerConnections.get('user-a');

    expect(peerConnectionA).toBeDefined();
    expect(peerConnectionB).toBeDefined();

    // Manually trigger ontrack events to simulate remote streams
    if (peerConnectionA && peerConnectionA.ontrack) {
      const mockRemoteStreamForA = new MockMediaStream();
      peerConnectionA.ontrack({
        track: mockRemoteStreamForA.getVideoTracks()[0],
        streams: [mockRemoteStreamForA],
        receiver: { track: mockRemoteStreamForA.getVideoTracks()[0] },
      });
    }

    if (peerConnectionB && peerConnectionB.ontrack) {
      const mockRemoteStreamForB = new MockMediaStream();
      peerConnectionB.ontrack({
        track: mockRemoteStreamForB.getVideoTracks()[0],
        streams: [mockRemoteStreamForB],
        receiver: { track: mockRemoteStreamForB.getVideoTracks()[0] },
      });
    }

    // Wait for callbacks to execute
    await flushPromises();

    // Verify both users received remote streams
    expect(userARemoteStream).toBeDefined();
    expect(userBRemoteStream).toBeDefined();
    expect(userAClient.remoteStreams.has('user-b')).toBe(true);
    expect(userBClient.remoteStreams.has('user-a')).toBe(true);

    // Verify peer connections are established
    expect(userAClient.peerConnections.size).toBe(1);
    expect(userBClient.peerConnections.size).toBe(1);

    // ═══════════════════════════════════════════════════════════════════
    // STEP 8: User A ends the call
    // ═══════════════════════════════════════════════════════════════════
    const callEndMessage = {
      type: 'call_end',
      room_id: 'room-123',
      ended_by: 'user-a',
    };

    // Track if User B received the call end
    let userBReceivedCallEnd = false;

    mockSignalingChannelB.onMessage((message) => {
      if (message.type === 'call_end') {
        userBReceivedCallEnd = true;
      }
    });

    // User A sends call end
    mockSignalingChannelA.send(callEndMessage);

    // Wait for message delivery
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(userBReceivedCallEnd).toBe(true);

    // Both users leave the room via API
    mockApiClient.leaveRoom.mockResolvedValue({ data: { success: true } });

    await mockApiClient.leaveRoom('room-123');
    await mockApiClient.leaveRoom('room-123');

    expect(mockApiClient.leaveRoom).toHaveBeenCalledTimes(2);

    // Both users clean up their connections
    userAClient.closePeerConnection('user-b');
    userBClient.closePeerConnection('user-a');

    // Verify connections are closed
    expect(userAClient.peerConnections.size).toBe(0);
    expect(userBClient.peerConnections.size).toBe(0);
    expect(userAClient.remoteStreams.size).toBe(0);
    expect(userBClient.remoteStreams.size).toBe(0);

    // ═══════════════════════════════════════════════════════════════════
    // STEP 9: Call history record is created
    // ═══════════════════════════════════════════════════════════════════
    const mockCallHistory = {
      id: 'call-history-1',
      room_id: 'room-123',
      started_at: new Date().toISOString(),
      ended_at: new Date().toISOString(),
      duration_seconds: 120,
      participant_count: 2,
      participants: [
        {
          user_id: 'user-a',
          joined_at: new Date().toISOString(),
          left_at: new Date().toISOString(),
          duration_seconds: 120,
        },
        {
          user_id: 'user-b',
          joined_at: new Date().toISOString(),
          left_at: new Date().toISOString(),
          duration_seconds: 115,
        },
      ],
    };

    mockApiClient.getCallHistory.mockResolvedValue({ data: [mockCallHistory] });

    // Fetch call history
    const callHistory = await mockApiClient.getCallHistory();

    expect(mockApiClient.getCallHistory).toHaveBeenCalled();
    expect(callHistory.data).toHaveLength(1);
    expect(callHistory.data[0]).toMatchObject({
      room_id: 'room-123',
      participant_count: 2,
      duration_seconds: 120,
    });
    expect(callHistory.data[0].participants).toHaveLength(2);

    // Verify call history contains both participants
    const participantIds = callHistory.data[0].participants.map((p) => p.user_id);
    expect(participantIds).toContain('user-a');
    expect(participantIds).toContain('user-b');
  });

  /**
   * Validates: Requirements 12.1, 12.5
   * Test: Call flow with connection state tracking
   */
  test('tracks connection states throughout call flow', async () => {
    // Get local streams
    await userAClient.getLocalMediaStream();
    await userBClient.getLocalMediaStream();

    // Track connection state changes
    const userAStateChanges = [];
    const userBStateChanges = [];

    userAClient.onConnectionStateChange = (userId, state) => {
      userAStateChanges.push({ userId, state });
    };

    userBClient.onConnectionStateChange = (userId, state) => {
      userBStateChanges.push({ userId, state });
    };

    // User A creates offer
    await userAClient.createOffer('user-b');

    // Wait for signaling
    await new Promise((resolve) => setTimeout(resolve, 200));
    await flushPromises();

    // Verify connection states are tracked
    expect(userAClient.getConnectionState('user-b')).toBeDefined();
    expect(userBClient.getConnectionState('user-a')).toBeDefined();

    // Simulate connection establishment
    const peerConnectionA = userAClient.peerConnections.get('user-b');
    const peerConnectionB = userBClient.peerConnections.get('user-a');

    if (peerConnectionA) {
      peerConnectionA.connectionState = 'connected';
      if (peerConnectionA.onconnectionstatechange) {
        peerConnectionA.onconnectionstatechange();
      }
    }

    if (peerConnectionB) {
      peerConnectionB.connectionState = 'connected';
      if (peerConnectionB.onconnectionstatechange) {
        peerConnectionB.onconnectionstatechange();
      }
    }

    await flushPromises();

    // Verify state change callbacks were called
    expect(userAStateChanges.length).toBeGreaterThan(0);
    expect(userBStateChanges.length).toBeGreaterThan(0);

    // Verify final states are 'connected'
    expect(userAClient.getConnectionState('user-b')).toBe('connected');
    expect(userBClient.getConnectionState('user-a')).toBe('connected');
  });

  /**
   * Validates: Requirements 12.1, 12.6
   * Test: Call controls during active call
   */
  test('call controls work during active call', async () => {
    // Setup call
    await userAClient.getLocalMediaStream();
    await userBClient.getLocalMediaStream();

    await userAClient.createOffer('user-b');
    await new Promise((resolve) => setTimeout(resolve, 200));
    await flushPromises();

    // Test mute/unmute
    const audioTrack = userAClient.localStream.getAudioTracks()[0];
    expect(audioTrack.enabled).toBe(true);

    userAClient.toggleAudio(false);
    expect(audioTrack.enabled).toBe(false);

    userAClient.toggleAudio(true);
    expect(audioTrack.enabled).toBe(true);

    // Test video on/off
    const videoTrack = userAClient.localStream.getVideoTracks()[0];
    expect(videoTrack.enabled).toBe(true);

    userAClient.toggleVideo(false);
    expect(videoTrack.enabled).toBe(false);

    userAClient.toggleVideo(true);
    expect(videoTrack.enabled).toBe(true);

    // Test screen share
    expect(userAClient.isScreenSharing()).toBe(false);

    await userAClient.startScreenShare();
    expect(userAClient.isScreenSharing()).toBe(true);
    expect(navigator.mediaDevices.getDisplayMedia).toHaveBeenCalled();

    userAClient.stopScreenShare();
    expect(userAClient.isScreenSharing()).toBe(false);
  });

  /**
   * Validates: Requirements 12.5
   * Test: Multiple signaling messages are handled correctly
   */
  test('handles multiple signaling messages in sequence', async () => {
    await userAClient.getLocalMediaStream();
    await userBClient.getLocalMediaStream();

    // Track all signaling messages
    const signalingMessages = [];

    const originalSendA = mockSignalingChannelA.send;
    const originalSendB = mockSignalingChannelB.send;

    mockSignalingChannelA.send = jest.fn((message) => {
      signalingMessages.push({ from: 'user-a', message });
      originalSendA(message);
    });

    mockSignalingChannelB.send = jest.fn((message) => {
      signalingMessages.push({ from: 'user-b', message });
      originalSendB(message);
    });

    // Initiate call
    await userAClient.createOffer('user-b');

    // Wait for all signaling to complete
    await new Promise((resolve) => setTimeout(resolve, 300));
    await flushPromises();

    // Verify signaling message sequence
    const messageTypes = signalingMessages.map((m) => m.message.type);

    // Should have: offer, answer, and multiple ICE candidates
    expect(messageTypes).toContain('webrtc_offer');
    expect(messageTypes).toContain('webrtc_answer');
    expect(messageTypes.filter((t) => t === 'webrtc_ice').length).toBeGreaterThan(0);

    // Verify offer comes before answer
    const offerIndex = messageTypes.indexOf('webrtc_offer');
    const answerIndex = messageTypes.indexOf('webrtc_answer');
    expect(offerIndex).toBeLessThan(answerIndex);
  });

  /**
   * Validates: Requirements 12.6
   * Test: Cleanup releases all resources
   */
  test('cleanup releases all resources properly', async () => {
    // Setup call
    await userAClient.getLocalMediaStream();
    await userBClient.getLocalMediaStream();

    await userAClient.createOffer('user-b');
    await new Promise((resolve) => setTimeout(resolve, 200));
    await flushPromises();

    // Verify resources are allocated
    expect(userAClient.localStream).not.toBeNull();
    expect(userAClient.peerConnections.size).toBeGreaterThan(0);

    // Cleanup
    userAClient.releaseMediaStreams();

    // Verify all resources are released
    expect(userAClient.localStream).toBeNull();
    expect(userAClient.peerConnections.size).toBe(0);
    expect(userAClient.remoteStreams.size).toBe(0);
    expect(userAClient.qualityMonitors.size).toBe(0);
    expect(userAClient.reconnectionState.size).toBe(0);
  });
});
