/**
 * Multi-Participant E2E Test
 * 
 * This test validates multi-participant video call functionality in a mesh topology:
 * 1. Four participants join a room sequentially
 * 2. Each new participant establishes connections with all existing participants
 * 3. Verify correct number of peer connections at each stage:
 *    - After participant 2 joins: 1 connection (1↔2)
 *    - After participant 3 joins: 3 connections (1↔2, 1↔3, 2↔3)
 *    - After participant 4 joins: 6 connections (1↔2, 1↔3, 1↔4, 2↔3, 2↔4, 3↔4)
 * 4. Test participant leave and verify remaining connections are intact
 * 
 * Requirements: 12.3
 */

import WebRTCClient from '@/lib/webrtc/WebRTCClient';
import {
  setupWebRTCMocks,
  teardownWebRTCMocks,
  MockMediaStream,
  flushPromises,
} from './mocks/webrtcMocks';

describe('Multi-Participant E2E', () => {
  let clients;
  let mockSignalingChannels;
  let messageHandlers;

  beforeEach(() => {
    // Setup WebRTC mocks
    setupWebRTCMocks();

    // Initialize data structures
    clients = {};
    mockSignalingChannels = {};
    messageHandlers = {};

    // Create message handlers map for all participants
    ['user-1', 'user-2', 'user-3', 'user-4'].forEach((userId) => {
      messageHandlers[userId] = [];
    });

    // Helper function to create a signaling channel for a user
    const createSignalingChannel = (userId) => {
      return {
        send: jest.fn((message) => {
          // Simulate message delivery to target user
          const targetUserId = message.to_user_id;
          if (targetUserId && messageHandlers[targetUserId]) {
            setTimeout(() => {
              messageHandlers[targetUserId].forEach((handler) => handler(message));
            }, 10);
          }
        }),
        onMessage: (handler) => {
          messageHandlers[userId].push(handler);
        },
      };
    };

    // Create signaling channels for all participants
    ['user-1', 'user-2', 'user-3', 'user-4'].forEach((userId) => {
      mockSignalingChannels[userId] = createSignalingChannel(userId);
    });

    // Create WebRTC clients for all participants
    ['user-1', 'user-2', 'user-3', 'user-4'].forEach((userId) => {
      clients[userId] = new WebRTCClient('room-123', userId, mockSignalingChannels[userId]);

      // Setup signaling message handlers
      mockSignalingChannels[userId].onMessage((message) => {
        if (message.type === 'webrtc_offer' && message.to_user_id === userId) {
          clients[userId].handleOffer(message.from_user_id, message.sdp);
        } else if (message.type === 'webrtc_answer' && message.to_user_id === userId) {
          clients[userId].handleAnswer(message.from_user_id, message.sdp);
        } else if (message.type === 'webrtc_ice' && message.to_user_id === userId) {
          clients[userId].handleIceCandidate(message.from_user_id, message.candidate);
        }
      });
    });
  });

  afterEach(() => {
    // Cleanup all clients
    Object.values(clients).forEach((client) => {
      if (client) {
        client.releaseMediaStreams();
      }
    });
    teardownWebRTCMocks();
  });

  /**
   * Helper function to wait for signaling to complete
   */
  const waitForSignaling = async (delayMs = 300) => {
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    await flushPromises();
  };

  /**
   * Helper function to simulate remote tracks for all peer connections
   */
  const simulateRemoteTracks = (client, remoteUserIds) => {
    remoteUserIds.forEach((remoteUserId) => {
      const peerConnection = client.peerConnections.get(remoteUserId);
      if (peerConnection && peerConnection.ontrack) {
        const mockRemoteStream = new MockMediaStream();
        peerConnection.ontrack({
          track: mockRemoteStream.getVideoTracks()[0],
          streams: [mockRemoteStream],
          receiver: { track: mockRemoteStream.getVideoTracks()[0] },
        });
      }
    });
  };

  /**
   * Helper function to count total connections across all clients
   */
  const countTotalConnections = () => {
    let total = 0;
    Object.values(clients).forEach((client) => {
      total += client.peerConnections.size;
    });
    // Each connection is counted twice (once per peer), so divide by 2
    return total / 2;
  };

  /**
   * Helper function to verify mesh topology connections
   */
  const verifyMeshTopology = (participantIds) => {
    // In a mesh topology, each participant should be connected to all others
    participantIds.forEach((userId) => {
      const client = clients[userId];
      const expectedConnections = participantIds.filter((id) => id !== userId);
      
      expectedConnections.forEach((expectedPeerId) => {
        expect(client.peerConnections.has(expectedPeerId)).toBe(true);
      });
      
      expect(client.peerConnections.size).toBe(expectedConnections.length);
    });
  };

  /**
   * Validates: Requirement 12.3
   * Test: 4 participants join sequentially and establish mesh connections
   */
  test('4 participants join sequentially and establish all peer connections', async () => {
    // ═══════════════════════════════════════════════════════════════════
    // STEP 1: All participants get local media streams
    // ═══════════════════════════════════════════════════════════════════
    await clients['user-1'].getLocalMediaStream();
    await clients['user-2'].getLocalMediaStream();
    await clients['user-3'].getLocalMediaStream();
    await clients['user-4'].getLocalMediaStream();

    // Track remote streams for verification
    const remoteStreams = {
      'user-1': [],
      'user-2': [],
      'user-3': [],
      'user-4': [],
    };

    Object.keys(clients).forEach((userId) => {
      clients[userId].onRemoteStream = (remoteUserId, stream) => {
        remoteStreams[userId].push(remoteUserId);
      };
    });

    // ═══════════════════════════════════════════════════════════════════
    // STEP 2: User 1 creates the room (already in room)
    // ═══════════════════════════════════════════════════════════════════
    // User 1 is the first participant, no connections yet
    expect(clients['user-1'].peerConnections.size).toBe(0);

    // ═══════════════════════════════════════════════════════════════════
    // STEP 3: User 2 joins - should establish 1 connection (1↔2)
    // ═══════════════════════════════════════════════════════════════════
    
    // User 2 joins and connects to User 1
    await clients['user-2'].joinRoom(['user-1']);
    await waitForSignaling();

    // Simulate remote tracks
    simulateRemoteTracks(clients['user-1'], ['user-2']);
    simulateRemoteTracks(clients['user-2'], ['user-1']);
    await flushPromises();

    // Verify: 1 connection total (1↔2)
    expect(clients['user-1'].peerConnections.size).toBe(1);
    expect(clients['user-2'].peerConnections.size).toBe(1);
    expect(clients['user-1'].peerConnections.has('user-2')).toBe(true);
    expect(clients['user-2'].peerConnections.has('user-1')).toBe(true);
    expect(countTotalConnections()).toBe(1);

    // ═══════════════════════════════════════════════════════════════════
    // STEP 4: User 3 joins - should establish 3 connections (1↔2, 1↔3, 2↔3)
    // ═══════════════════════════════════════════════════════════════════
    
    // User 3 joins and connects to User 1 and User 2
    await clients['user-3'].joinRoom(['user-1', 'user-2']);
    await waitForSignaling();

    // Simulate remote tracks
    simulateRemoteTracks(clients['user-1'], ['user-3']);
    simulateRemoteTracks(clients['user-2'], ['user-3']);
    simulateRemoteTracks(clients['user-3'], ['user-1', 'user-2']);
    await flushPromises();

    // Verify: 3 connections total (1↔2, 1↔3, 2↔3)
    expect(clients['user-1'].peerConnections.size).toBe(2); // connected to 2, 3
    expect(clients['user-2'].peerConnections.size).toBe(2); // connected to 1, 3
    expect(clients['user-3'].peerConnections.size).toBe(2); // connected to 1, 2
    expect(countTotalConnections()).toBe(3);

    // Verify mesh topology for 3 participants
    verifyMeshTopology(['user-1', 'user-2', 'user-3']);

    // ═══════════════════════════════════════════════════════════════════
    // STEP 5: User 4 joins - should establish 6 connections
    //         (1↔2, 1↔3, 1↔4, 2↔3, 2↔4, 3↔4)
    // ═══════════════════════════════════════════════════════════════════
    
    // User 4 joins and connects to User 1, 2, and 3
    await clients['user-4'].joinRoom(['user-1', 'user-2', 'user-3']);
    await waitForSignaling();

    // Simulate remote tracks
    simulateRemoteTracks(clients['user-1'], ['user-4']);
    simulateRemoteTracks(clients['user-2'], ['user-4']);
    simulateRemoteTracks(clients['user-3'], ['user-4']);
    simulateRemoteTracks(clients['user-4'], ['user-1', 'user-2', 'user-3']);
    await flushPromises();

    // Verify: 6 connections total (1↔2, 1↔3, 1↔4, 2↔3, 2↔4, 3↔4)
    expect(clients['user-1'].peerConnections.size).toBe(3); // connected to 2, 3, 4
    expect(clients['user-2'].peerConnections.size).toBe(3); // connected to 1, 3, 4
    expect(clients['user-3'].peerConnections.size).toBe(3); // connected to 1, 2, 4
    expect(clients['user-4'].peerConnections.size).toBe(3); // connected to 1, 2, 3
    expect(countTotalConnections()).toBe(6);

    // Verify complete mesh topology for all 4 participants
    verifyMeshTopology(['user-1', 'user-2', 'user-3', 'user-4']);

    // Verify all participants received remote streams
    expect(remoteStreams['user-1'].length).toBeGreaterThanOrEqual(3);
    expect(remoteStreams['user-2'].length).toBeGreaterThanOrEqual(3);
    expect(remoteStreams['user-3'].length).toBeGreaterThanOrEqual(2);
    expect(remoteStreams['user-4'].length).toBeGreaterThanOrEqual(3);
  });

  /**
   * Validates: Requirement 12.3
   * Test: Participant leaves and connections are cleaned up correctly
   */
  test('participant leaves and remaining connections stay intact', async () => {
    // ═══════════════════════════════════════════════════════════════════
    // SETUP: Establish 4-participant mesh (6 connections)
    // ═══════════════════════════════════════════════════════════════════
    
    // Get local streams
    await clients['user-1'].getLocalMediaStream();
    await clients['user-2'].getLocalMediaStream();
    await clients['user-3'].getLocalMediaStream();
    await clients['user-4'].getLocalMediaStream();

    // Track remote stream removal
    const removedStreams = {
      'user-1': [],
      'user-2': [],
      'user-3': [],
      'user-4': [],
    };

    Object.keys(clients).forEach((userId) => {
      clients[userId].onRemoteStreamRemoved = (remoteUserId) => {
        removedStreams[userId].push(remoteUserId);
      };
    });

    // Build mesh: User 2 joins
    await clients['user-2'].joinRoom(['user-1']);
    await waitForSignaling();
    simulateRemoteTracks(clients['user-1'], ['user-2']);
    simulateRemoteTracks(clients['user-2'], ['user-1']);

    // User 3 joins
    await clients['user-3'].joinRoom(['user-1', 'user-2']);
    await waitForSignaling();
    simulateRemoteTracks(clients['user-1'], ['user-3']);
    simulateRemoteTracks(clients['user-2'], ['user-3']);
    simulateRemoteTracks(clients['user-3'], ['user-1', 'user-2']);

    // User 4 joins
    await clients['user-4'].joinRoom(['user-1', 'user-2', 'user-3']);
    await waitForSignaling();
    simulateRemoteTracks(clients['user-1'], ['user-4']);
    simulateRemoteTracks(clients['user-2'], ['user-4']);
    simulateRemoteTracks(clients['user-3'], ['user-4']);
    simulateRemoteTracks(clients['user-4'], ['user-1', 'user-2', 'user-3']);
    await flushPromises();

    // Verify initial state: 6 connections
    expect(countTotalConnections()).toBe(6);
    verifyMeshTopology(['user-1', 'user-2', 'user-3', 'user-4']);

    // ═══════════════════════════════════════════════════════════════════
    // STEP 1: User 2 leaves the call
    // ═══════════════════════════════════════════════════════════════════
    
    // User 2 closes all connections
    clients['user-2'].releaseMediaStreams();

    // Other participants close their connections to User 2
    clients['user-1'].closePeerConnection('user-2');
    clients['user-3'].closePeerConnection('user-2');
    clients['user-4'].closePeerConnection('user-2');

    await flushPromises();

    // ═══════════════════════════════════════════════════════════════════
    // STEP 2: Verify User 2's connections are closed
    // ═══════════════════════════════════════════════════════════════════
    
    expect(clients['user-2'].peerConnections.size).toBe(0);
    expect(clients['user-2'].remoteStreams.size).toBe(0);

    // ═══════════════════════════════════════════════════════════════════
    // STEP 3: Verify remaining participants no longer have User 2 connections
    // ═══════════════════════════════════════════════════════════════════
    
    expect(clients['user-1'].peerConnections.has('user-2')).toBe(false);
    expect(clients['user-3'].peerConnections.has('user-2')).toBe(false);
    expect(clients['user-4'].peerConnections.has('user-2')).toBe(false);

    // ═══════════════════════════════════════════════════════════════════
    // STEP 4: Verify remaining connections are intact (1↔3, 1↔4, 3↔4)
    // ═══════════════════════════════════════════════════════════════════
    
    // User 1 should still be connected to User 3 and User 4
    expect(clients['user-1'].peerConnections.size).toBe(2);
    expect(clients['user-1'].peerConnections.has('user-3')).toBe(true);
    expect(clients['user-1'].peerConnections.has('user-4')).toBe(true);

    // User 3 should still be connected to User 1 and User 4
    expect(clients['user-3'].peerConnections.size).toBe(2);
    expect(clients['user-3'].peerConnections.has('user-1')).toBe(true);
    expect(clients['user-3'].peerConnections.has('user-4')).toBe(true);

    // User 4 should still be connected to User 1 and User 3
    expect(clients['user-4'].peerConnections.size).toBe(2);
    expect(clients['user-4'].peerConnections.has('user-1')).toBe(true);
    expect(clients['user-4'].peerConnections.has('user-3')).toBe(true);

    // Total connections should be 3 (1↔3, 1↔4, 3↔4)
    expect(countTotalConnections()).toBe(3);

    // Verify mesh topology for remaining participants
    verifyMeshTopology(['user-1', 'user-3', 'user-4']);

    // Verify remote stream removal callbacks were called
    expect(removedStreams['user-1']).toContain('user-2');
    expect(removedStreams['user-3']).toContain('user-2');
    expect(removedStreams['user-4']).toContain('user-2');
  });

  /**
   * Validates: Requirement 12.3
   * Test: Multiple participants leave sequentially
   */
  test('multiple participants leave sequentially and connections update correctly', async () => {
    // ═══════════════════════════════════════════════════════════════════
    // SETUP: Establish 4-participant mesh (6 connections)
    // ═══════════════════════════════════════════════════════════════════
    
    await clients['user-1'].getLocalMediaStream();
    await clients['user-2'].getLocalMediaStream();
    await clients['user-3'].getLocalMediaStream();
    await clients['user-4'].getLocalMediaStream();

    // Build mesh
    await clients['user-2'].joinRoom(['user-1']);
    await waitForSignaling();
    simulateRemoteTracks(clients['user-1'], ['user-2']);
    simulateRemoteTracks(clients['user-2'], ['user-1']);

    await clients['user-3'].joinRoom(['user-1', 'user-2']);
    await waitForSignaling();
    simulateRemoteTracks(clients['user-1'], ['user-3']);
    simulateRemoteTracks(clients['user-2'], ['user-3']);
    simulateRemoteTracks(clients['user-3'], ['user-1', 'user-2']);

    await clients['user-4'].joinRoom(['user-1', 'user-2', 'user-3']);
    await waitForSignaling();
    simulateRemoteTracks(clients['user-1'], ['user-4']);
    simulateRemoteTracks(clients['user-2'], ['user-4']);
    simulateRemoteTracks(clients['user-3'], ['user-4']);
    simulateRemoteTracks(clients['user-4'], ['user-1', 'user-2', 'user-3']);
    await flushPromises();

    // Verify initial state
    expect(countTotalConnections()).toBe(6);

    // ═══════════════════════════════════════════════════════════════════
    // User 3 leaves (3 connections remain: 1↔2, 1↔4, 2↔4)
    // ═══════════════════════════════════════════════════════════════════
    
    clients['user-3'].releaseMediaStreams();
    clients['user-1'].closePeerConnection('user-3');
    clients['user-2'].closePeerConnection('user-3');
    clients['user-4'].closePeerConnection('user-3');
    await flushPromises();

    expect(countTotalConnections()).toBe(3);
    verifyMeshTopology(['user-1', 'user-2', 'user-4']);

    // ═══════════════════════════════════════════════════════════════════
    // User 4 leaves (1 connection remains: 1↔2)
    // ═══════════════════════════════════════════════════════════════════
    
    clients['user-4'].releaseMediaStreams();
    clients['user-1'].closePeerConnection('user-4');
    clients['user-2'].closePeerConnection('user-4');
    await flushPromises();

    expect(countTotalConnections()).toBe(1);
    verifyMeshTopology(['user-1', 'user-2']);

    // ═══════════════════════════════════════════════════════════════════
    // User 2 leaves (0 connections remain)
    // ═══════════════════════════════════════════════════════════════════
    
    clients['user-2'].releaseMediaStreams();
    clients['user-1'].closePeerConnection('user-2');
    await flushPromises();

    expect(countTotalConnections()).toBe(0);
    expect(clients['user-1'].peerConnections.size).toBe(0);
  });

  /**
   * Validates: Requirement 12.3
   * Test: New participant joins after another leaves
   */
  test('new participant joins after another leaves', async () => {
    // ═══════════════════════════════════════════════════════════════════
    // SETUP: Establish 3-participant mesh
    // ═══════════════════════════════════════════════════════════════════
    
    await clients['user-1'].getLocalMediaStream();
    await clients['user-2'].getLocalMediaStream();
    await clients['user-3'].getLocalMediaStream();

    await clients['user-2'].joinRoom(['user-1']);
    await waitForSignaling();
    simulateRemoteTracks(clients['user-1'], ['user-2']);
    simulateRemoteTracks(clients['user-2'], ['user-1']);

    await clients['user-3'].joinRoom(['user-1', 'user-2']);
    await waitForSignaling();
    simulateRemoteTracks(clients['user-1'], ['user-3']);
    simulateRemoteTracks(clients['user-2'], ['user-3']);
    simulateRemoteTracks(clients['user-3'], ['user-1', 'user-2']);
    await flushPromises();

    // Verify: 3 connections (1↔2, 1↔3, 2↔3)
    expect(countTotalConnections()).toBe(3);

    // ═══════════════════════════════════════════════════════════════════
    // User 2 leaves
    // ═══════════════════════════════════════════════════════════════════
    
    clients['user-2'].releaseMediaStreams();
    clients['user-1'].closePeerConnection('user-2');
    clients['user-3'].closePeerConnection('user-2');
    await flushPromises();

    // Verify: 1 connection (1↔3)
    expect(countTotalConnections()).toBe(1);

    // ═══════════════════════════════════════════════════════════════════
    // User 4 joins (should establish 3 connections: 1↔3, 1↔4, 3↔4)
    // ═══════════════════════════════════════════════════════════════════
    
    await clients['user-4'].getLocalMediaStream();
    await clients['user-4'].joinRoom(['user-1', 'user-3']);
    await waitForSignaling();
    simulateRemoteTracks(clients['user-1'], ['user-4']);
    simulateRemoteTracks(clients['user-3'], ['user-4']);
    simulateRemoteTracks(clients['user-4'], ['user-1', 'user-3']);
    await flushPromises();

    // Verify: 3 connections (1↔3, 1↔4, 3↔4)
    expect(countTotalConnections()).toBe(3);
    verifyMeshTopology(['user-1', 'user-3', 'user-4']);

    // Verify User 4 is connected to User 1 and User 3
    expect(clients['user-4'].peerConnections.has('user-1')).toBe(true);
    expect(clients['user-4'].peerConnections.has('user-3')).toBe(true);
    expect(clients['user-4'].peerConnections.has('user-2')).toBe(false);
  });

  /**
   * Validates: Requirement 12.3
   * Test: Connection state tracking during multi-participant call
   */
  test('tracks connection states for all participants', async () => {
    // ═══════════════════════════════════════════════════════════════════
    // SETUP: Track connection state changes
    // ═══════════════════════════════════════════════════════════════════
    
    const stateChanges = {
      'user-1': [],
      'user-2': [],
      'user-3': [],
    };

    Object.keys(stateChanges).forEach((userId) => {
      clients[userId].onConnectionStateChange = (remoteUserId, state) => {
        stateChanges[userId].push({ remoteUserId, state });
      };
    });

    // Get local streams
    await clients['user-1'].getLocalMediaStream();
    await clients['user-2'].getLocalMediaStream();
    await clients['user-3'].getLocalMediaStream();

    // ═══════════════════════════════════════════════════════════════════
    // Build 3-participant mesh
    // ═══════════════════════════════════════════════════════════════════
    
    await clients['user-2'].joinRoom(['user-1']);
    await waitForSignaling();

    await clients['user-3'].joinRoom(['user-1', 'user-2']);
    await waitForSignaling();

    // Simulate connection establishment
    const peerConnection12 = clients['user-1'].peerConnections.get('user-2');
    const peerConnection21 = clients['user-2'].peerConnections.get('user-1');
    const peerConnection13 = clients['user-1'].peerConnections.get('user-3');
    const peerConnection31 = clients['user-3'].peerConnections.get('user-1');
    const peerConnection23 = clients['user-2'].peerConnections.get('user-3');
    const peerConnection32 = clients['user-3'].peerConnections.get('user-2');

    // Simulate connected state
    [peerConnection12, peerConnection21, peerConnection13, 
     peerConnection31, peerConnection23, peerConnection32].forEach((pc) => {
      if (pc) {
        pc.connectionState = 'connected';
        if (pc.onconnectionstatechange) {
          pc.onconnectionstatechange();
        }
      }
    });

    await flushPromises();

    // ═══════════════════════════════════════════════════════════════════
    // Verify connection states are tracked
    // ═══════════════════════════════════════════════════════════════════
    
    expect(clients['user-1'].getConnectionState('user-2')).toBe('connected');
    expect(clients['user-1'].getConnectionState('user-3')).toBe('connected');
    expect(clients['user-2'].getConnectionState('user-1')).toBe('connected');
    expect(clients['user-2'].getConnectionState('user-3')).toBe('connected');
    expect(clients['user-3'].getConnectionState('user-1')).toBe('connected');
    expect(clients['user-3'].getConnectionState('user-2')).toBe('connected');

    // Verify state change callbacks were called
    expect(stateChanges['user-1'].length).toBeGreaterThan(0);
    expect(stateChanges['user-2'].length).toBeGreaterThan(0);
    expect(stateChanges['user-3'].length).toBeGreaterThan(0);

    // ═══════════════════════════════════════════════════════════════════
    // User 2 leaves - verify state changes to 'closed'
    // ═══════════════════════════════════════════════════════════════════
    
    clients['user-1'].closePeerConnection('user-2');
    clients['user-3'].closePeerConnection('user-2');

    expect(clients['user-1'].getConnectionState('user-2')).toBe('closed');
    expect(clients['user-3'].getConnectionState('user-2')).toBe('closed');

    // Remaining connections should still be 'connected'
    expect(clients['user-1'].getConnectionState('user-3')).toBe('connected');
    expect(clients['user-3'].getConnectionState('user-1')).toBe('connected');
  });
});
