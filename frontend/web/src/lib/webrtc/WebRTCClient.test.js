/**
 * Unit tests for WebRTCClient
 * 
 * Tests cover:
 * - Peer connection initialization with ICE servers (Req 1.1)
 * - Media stream attachment and cleanup (Req 1.5, 1.7)
 * - Audio/video toggle functionality (Req 3.1, 3.2, 3.6)
 * - Screen share start/stop (Req 4.1, 4.2, 4.5)
 * - Connection quality calculation (Req 9.6)
 * - Reconnection attempts with max limit (Req 1.6, 7.1)
 */

import WebRTCClient from './WebRTCClient';

// Mock WebRTC APIs
const mockAddTrack = jest.fn();
const mockCreateOffer = jest.fn();
const mockCreateAnswer = jest.fn();
const mockSetLocalDescription = jest.fn();
const mockSetRemoteDescription = jest.fn();
const mockAddIceCandidate = jest.fn();
const mockClose = jest.fn();
const mockGetSenders = jest.fn();
const mockGetStats = jest.fn();
const mockReplaceTrack = jest.fn();

const mockPeerConnection = {
  addTrack: mockAddTrack,
  createOffer: mockCreateOffer,
  createAnswer: mockCreateAnswer,
  setLocalDescription: mockSetLocalDescription,
  setRemoteDescription: mockSetRemoteDescription,
  addIceCandidate: mockAddIceCandidate,
  close: mockClose,
  getSenders: mockGetSenders,
  getStats: mockGetStats,
  connectionState: 'new',
  iceConnectionState: 'new',
  onicecandidate: null,
  ontrack: null,
  onconnectionstatechange: null,
  oniceconnectionstatechange: null,
};

global.RTCPeerConnection = jest.fn(() => ({ ...mockPeerConnection }));
global.RTCSessionDescription = jest.fn((desc) => desc);
global.RTCIceCandidate = jest.fn((candidate) => candidate);

// Mock MediaStream
const mockMediaStreamTrack = {
  kind: 'video',
  enabled: true,
  stop: jest.fn(),
  onended: null,
};

const mockAudioTrack = {
  kind: 'audio',
  enabled: true,
  stop: jest.fn(),
};

const mockMediaStream = {
  getTracks: jest.fn(() => [mockMediaStreamTrack, mockAudioTrack]),
  getVideoTracks: jest.fn(() => [mockMediaStreamTrack]),
  getAudioTracks: jest.fn(() => [mockAudioTrack]),
  addTrack: jest.fn(),
  removeTrack: jest.fn(),
};

// Mock navigator.mediaDevices
global.navigator.mediaDevices = {
  getUserMedia: jest.fn(() => Promise.resolve({ ...mockMediaStream })),
  getDisplayMedia: jest.fn(() => Promise.resolve({ ...mockMediaStream })),
};

describe('WebRTCClient', () => {
  let client;
  let mockSignalingChannel;

  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks();
    
    // Create mock signaling channel
    mockSignalingChannel = {
      send: jest.fn(),
    };

    // Create client instance
    client = new WebRTCClient('room-123', 'user-1', mockSignalingChannel);

    // Reset mock implementations
    mockCreateOffer.mockResolvedValue({ type: 'offer', sdp: 'mock-offer-sdp' });
    mockCreateAnswer.mockResolvedValue({ type: 'answer', sdp: 'mock-answer-sdp' });
    mockSetLocalDescription.mockResolvedValue();
    mockSetRemoteDescription.mockResolvedValue();
    mockAddIceCandidate.mockResolvedValue();
    mockGetSenders.mockReturnValue([
      { track: { kind: 'video' }, replaceTrack: mockReplaceTrack },
      { track: { kind: 'audio' }, replaceTrack: jest.fn() },
    ]);
    mockGetStats.mockResolvedValue(new Map());
  });

  afterEach(() => {
    // Clean up
    if (client) {
      client.releaseMediaStreams();
    }
  });

  describe('Peer Connection Initialization', () => {
    /**
     * Validates: Requirements 1.1
     * Test: Peer connection is created with ICE server configuration
     */
    test('creates peer connection with ICE servers', () => {
      const remoteUserId = 'user-2';
      
      const peerConnection = client.initializePeerConnection(remoteUserId);

      expect(RTCPeerConnection).toHaveBeenCalledWith({
        iceServers: expect.arrayContaining([
          { urls: 'stun:stun.l.google.com:19302' },
        ]),
        iceTransportPolicy: 'all',
      });
      expect(peerConnection).toBeDefined();
      expect(client.peerConnections.has(remoteUserId)).toBe(true);
    });

    /**
     * Validates: Requirements 1.1
     * Test: Custom ICE servers can be set
     */
    test('uses custom ICE servers when set', () => {
      const customIceServers = [
        { urls: 'stun:custom.stun.server:3478' },
        { urls: 'turn:custom.turn.server:3478', username: 'user', credential: 'pass' },
      ];

      client.setIceServers(customIceServers);
      client.initializePeerConnection('user-2');

      expect(RTCPeerConnection).toHaveBeenCalledWith({
        iceServers: customIceServers,
        iceTransportPolicy: 'all',
      });
    });

    /**
     * Validates: Requirements 1.1, 1.5
     * Test: Local stream tracks are added to peer connection
     */
    test('adds local stream tracks to peer connection', async () => {
      await client.getLocalMediaStream();
      
      client.initializePeerConnection('user-2');

      expect(mockAddTrack).toHaveBeenCalledTimes(2); // video + audio
    });

    /**
     * Validates: Requirements 1.1
     * Test: Closes existing connection before creating new one
     */
    test('closes existing peer connection before creating new one', () => {
      const remoteUserId = 'user-2';
      
      // Create first connection
      client.initializePeerConnection(remoteUserId);
      const firstClose = mockClose;
      
      // Create second connection
      client.initializePeerConnection(remoteUserId);

      expect(firstClose).toHaveBeenCalled();
    });
  });

  describe('Media Stream Management', () => {
    /**
     * Validates: Requirements 1.5
     * Test: Gets local media stream with constraints
     */
    test('gets local media stream with default HD constraints', async () => {
      const stream = await client.getLocalMediaStream();

      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith(
        expect.objectContaining({
          audio: expect.any(Object),
          video: expect.objectContaining({
            width: { ideal: 1280 },
            height: { ideal: 720 },
          }),
        })
      );
      expect(stream).toBeDefined();
      expect(client.localStream).toBe(stream);
    });

    /**
     * Validates: Requirements 1.5
     * Test: Handles media access errors
     */
    test('handles media permission denied error', async () => {
      const mockError = new Error('Permission denied');
      mockError.name = 'NotAllowedError';
      navigator.mediaDevices.getUserMedia.mockRejectedValueOnce(mockError);

      const onError = jest.fn();
      client.onError = onError;

      await expect(client.getLocalMediaStream()).rejects.toThrow();
      expect(onError).toHaveBeenCalledWith('media_permission_denied', mockError);
    });

    /**
     * Validates: Requirements 1.5
     * Test: Handles device not found error
     */
    test('handles media device not found error', async () => {
      const mockError = new Error('Device not found');
      mockError.name = 'NotFoundError';
      navigator.mediaDevices.getUserMedia.mockRejectedValueOnce(mockError);

      const onError = jest.fn();
      client.onError = onError;

      await expect(client.getLocalMediaStream()).rejects.toThrow();
      expect(onError).toHaveBeenCalledWith('media_device_not_found', mockError);
    });

    /**
     * Validates: Requirements 1.5
     * Test: Attaches local stream to existing peer connections
     */
    test('attaches local stream to existing peer connections', async () => {
      // Create peer connection first
      client.initializePeerConnection('user-2');
      mockAddTrack.mockClear();

      // Get and attach stream
      const stream = await client.getLocalMediaStream();
      client.attachLocalStream(stream);

      expect(mockAddTrack).toHaveBeenCalledTimes(2); // video + audio
    });

    /**
     * Validates: Requirements 1.7
     * Test: Releases all media streams and closes connections
     */
    test('releases all media streams and closes connections', async () => {
      // Setup: create stream and connections
      await client.getLocalMediaStream();
      client.initializePeerConnection('user-2');
      client.initializePeerConnection('user-3');

      const trackStop = jest.fn();
      client.localStream.getTracks = jest.fn(() => [
        { stop: trackStop },
        { stop: trackStop },
      ]);

      // Release
      client.releaseMediaStreams();

      expect(trackStop).toHaveBeenCalledTimes(2);
      expect(mockClose).toHaveBeenCalledTimes(2);
      expect(client.localStream).toBeNull();
      expect(client.peerConnections.size).toBe(0);
    });
  });

  describe('Audio/Video Toggle Functionality', () => {
    /**
     * Validates: Requirements 3.1, 3.6
     * Test: Toggles audio track enabled state
     */
    test('toggles audio on and off', async () => {
      await client.getLocalMediaStream();

      // Mute audio
      client.toggleAudio(false);
      expect(mockAudioTrack.enabled).toBe(false);

      // Unmute audio
      client.toggleAudio(true);
      expect(mockAudioTrack.enabled).toBe(true);
    });

    /**
     * Validates: Requirements 3.2, 3.6
     * Test: Toggles video track enabled state
     */
    test('toggles video on and off', async () => {
      await client.getLocalMediaStream();

      // Turn video off
      client.toggleVideo(false);
      expect(mockMediaStreamTrack.enabled).toBe(false);

      // Turn video on
      client.toggleVideo(true);
      expect(mockMediaStreamTrack.enabled).toBe(true);
    });

    /**
     * Validates: Requirements 3.1, 3.2
     * Test: Handles toggle when no local stream exists
     */
    test('handles audio/video toggle when no local stream', () => {
      // Should not throw error
      expect(() => client.toggleAudio(false)).not.toThrow();
      expect(() => client.toggleVideo(false)).not.toThrow();
    });
  });

  describe('Screen Share Functionality', () => {
    /**
     * Validates: Requirements 4.1, 4.2
     * Test: Starts screen sharing and replaces video track
     */
    test('starts screen sharing and replaces video track', async () => {
      // Setup: get local stream and create peer connection
      await client.getLocalMediaStream();
      client.initializePeerConnection('user-2');

      // Start screen share
      const screenStream = await client.startScreenShare();

      expect(navigator.mediaDevices.getDisplayMedia).toHaveBeenCalledWith({
        video: { cursor: 'always' },
        audio: false,
      });
      expect(screenStream).toBeDefined();
      expect(client.screenStream).toBe(screenStream);
      expect(mockReplaceTrack).toHaveBeenCalled();
    });

    /**
     * Validates: Requirements 4.5
     * Test: Stops screen sharing and restores camera
     */
    test('stops screen sharing and restores camera video', async () => {
      // Setup: start screen share
      await client.getLocalMediaStream();
      client.initializePeerConnection('user-2');
      await client.startScreenShare();

      const screenTrackStop = jest.fn();
      client.screenStream.getTracks = jest.fn(() => [{ stop: screenTrackStop }]);

      mockReplaceTrack.mockClear();

      // Stop screen share
      client.stopScreenShare();

      expect(screenTrackStop).toHaveBeenCalled();
      expect(client.screenStream).toBeNull();
      expect(mockReplaceTrack).toHaveBeenCalled(); // Restores original track
    });

    /**
     * Validates: Requirements 4.1
     * Test: Handles screen share permission denied
     */
    test('handles screen share permission denied', async () => {
      const mockError = new Error('Permission denied');
      mockError.name = 'NotAllowedError';
      navigator.mediaDevices.getDisplayMedia.mockRejectedValueOnce(mockError);

      const onError = jest.fn();
      client.onError = onError;

      await expect(client.startScreenShare()).rejects.toThrow();
      expect(onError).toHaveBeenCalledWith('screen_share_permission_denied', mockError);
    });

    /**
     * Validates: Requirements 4.5
     * Test: Handles screen share stop via browser button
     */
    test('handles screen share stop via browser stop button', async () => {
      await client.getLocalMediaStream();
      client.initializePeerConnection('user-2');
      await client.startScreenShare();

      const screenTrack = client.screenStream.getVideoTracks()[0];
      
      // Simulate browser stop button click
      if (screenTrack.onended) {
        screenTrack.onended();
      }

      // stopScreenShare should have been called
      expect(client.screenStream).toBeNull();
    });

    /**
     * Validates: Requirements 4.1, 4.5
     * Test: Checks screen sharing status
     */
    test('checks if screen sharing is active', async () => {
      expect(client.isScreenSharing()).toBe(false);

      await client.getLocalMediaStream();
      await client.startScreenShare();
      expect(client.isScreenSharing()).toBe(true);

      client.stopScreenShare();
      expect(client.isScreenSharing()).toBe(false);
    });
  });

  describe('Connection Quality Monitoring', () => {
    /**
     * Validates: Requirements 9.6
     * Test: Calculates connection quality from stats
     */
    test('calculates connection quality with good metrics', () => {
      const mockStats = new Map([
        ['inbound-rtp-video', {
          type: 'inbound-rtp',
          kind: 'video',
          packetsLost: 5,
          packetsReceived: 995,
          bytesReceived: 1000000,
          timestamp: 1000,
        }],
        ['candidate-pair', {
          type: 'candidate-pair',
          state: 'succeeded',
          currentRoundTripTime: 0.05, // 50ms
        }],
      ]);

      const quality = client.calculateConnectionQuality(mockStats);

      expect(quality.quality).toBe('good');
      expect(quality.packetLoss).toBeLessThan(1);
      expect(quality.latency).toBe(50);
    });

    /**
     * Validates: Requirements 9.6
     * Test: Detects fair connection quality
     */
    test('calculates fair connection quality', () => {
      const mockStats = new Map([
        ['inbound-rtp-video', {
          type: 'inbound-rtp',
          kind: 'video',
          packetsLost: 30,
          packetsReceived: 970,
          bytesReceived: 1000000,
          timestamp: 1000,
        }],
        ['candidate-pair', {
          type: 'candidate-pair',
          state: 'succeeded',
          currentRoundTripTime: 0.2, // 200ms
        }],
      ]);

      const quality = client.calculateConnectionQuality(mockStats);

      expect(quality.quality).toBe('fair');
      expect(quality.packetLoss).toBeGreaterThan(2);
      expect(quality.latency).toBe(200);
    });

    /**
     * Validates: Requirements 9.6
     * Test: Detects poor connection quality
     */
    test('calculates poor connection quality', () => {
      const mockStats = new Map([
        ['inbound-rtp-video', {
          type: 'inbound-rtp',
          kind: 'video',
          packetsLost: 60,
          packetsReceived: 940,
          bytesReceived: 1000000,
          timestamp: 1000,
        }],
        ['candidate-pair', {
          type: 'candidate-pair',
          state: 'succeeded',
          currentRoundTripTime: 0.4, // 400ms
        }],
      ]);

      const quality = client.calculateConnectionQuality(mockStats);

      expect(quality.quality).toBe('poor');
      expect(quality.packetLoss).toBeGreaterThan(5);
      expect(quality.latency).toBe(400);
    });

    /**
     * Validates: Requirements 9.6, 7.1
     * Test: Monitors connection quality periodically
     */
    test('monitors connection quality periodically', async () => {
      jest.useFakeTimers();

      client.initializePeerConnection('user-2');
      const onQualityChange = jest.fn();
      client.onConnectionQualityChange = onQualityChange;

      mockGetStats.mockResolvedValue(new Map([
        ['inbound-rtp-video', {
          type: 'inbound-rtp',
          kind: 'video',
          packetsLost: 5,
          packetsReceived: 995,
        }],
      ]));

      // Start monitoring
      client.monitorConnectionQuality('user-2');

      // Fast-forward time
      jest.advanceTimersByTime(2000);
      await Promise.resolve(); // Allow promises to resolve

      expect(onQualityChange).toHaveBeenCalled();

      jest.useRealTimers();
    });
  });

  describe('Reconnection Logic', () => {
    /**
     * Validates: Requirements 1.6, 7.1
     * Test: Attempts reconnection on connection failure
     */
    test('attempts reconnection on connection failure', async () => {
      jest.useFakeTimers();

      client.initializePeerConnection('user-2');
      const createOfferSpy = jest.spyOn(client, 'createOffer');

      // Trigger reconnection
      await client.attemptReconnection('user-2', 3);

      // Fast-forward through first attempt (2^1 = 2 seconds)
      jest.advanceTimersByTime(2000);
      await Promise.resolve();

      expect(createOfferSpy).toHaveBeenCalledWith('user-2');

      jest.useRealTimers();
    });

    /**
     * Validates: Requirements 1.6, 7.1
     * Test: Respects maximum reconnection attempts
     */
    test('stops reconnection after max attempts', async () => {
      jest.useFakeTimers();

      const onError = jest.fn();
      client.onError = onError;

      // Simulate 3 failed attempts
      client.reconnectionState.set('user-2', { attempts: 3, timeout: null });

      await client.attemptReconnection('user-2', 3);

      expect(onError).toHaveBeenCalledWith(
        'reconnection_failed',
        expect.any(Error),
        'user-2'
      );

      jest.useRealTimers();
    });

    /**
     * Validates: Requirements 7.1
     * Test: Uses exponential backoff for reconnection
     */
    test('uses exponential backoff for reconnection attempts', async () => {
      jest.useFakeTimers();

      client.initializePeerConnection('user-2');
      const createOfferSpy = jest.spyOn(client, 'createOffer').mockResolvedValue();

      // First attempt: 2^1 = 2 seconds
      await client.attemptReconnection('user-2', 3);
      let reconnection = client.reconnectionState.get('user-2');
      expect(reconnection.attempts).toBe(1);

      // Fast-forward and resolve promises
      jest.advanceTimersByTime(2000);
      await Promise.resolve();
      await Promise.resolve();

      // Verify first reconnection was attempted
      expect(createOfferSpy).toHaveBeenCalledWith('user-2');

      jest.useRealTimers();
    });

    /**
     * Validates: Requirements 7.1
     * Test: Resets reconnection state on successful connection
     */
    test('resets reconnection state on successful connection', () => {
      client.reconnectionState.set('user-2', { attempts: 2, timeout: null });
      
      const peerConnection = client.initializePeerConnection('user-2');
      
      // Simulate successful connection
      peerConnection.iceConnectionState = 'connected';
      if (peerConnection.oniceconnectionstatechange) {
        peerConnection.oniceconnectionstatechange();
      }

      expect(client.reconnectionState.has('user-2')).toBe(false);
    });
  });

  describe('WebRTC Signaling', () => {
    /**
     * Validates: Requirements 1.2
     * Test: Creates and sends offer
     */
    test('creates and sends offer to remote peer', async () => {
      await client.createOffer('user-2');

      expect(mockCreateOffer).toHaveBeenCalled();
      expect(mockSetLocalDescription).toHaveBeenCalled();
      expect(mockSignalingChannel.send).toHaveBeenCalledWith({
        type: 'webrtc_offer',
        from_user_id: 'user-1',
        to_user_id: 'user-2',
        room_id: 'room-123',
        sdp: expect.any(Object),
      });
    });

    /**
     * Validates: Requirements 1.3
     * Test: Handles answer from remote peer
     */
    test('handles answer from remote peer', async () => {
      client.initializePeerConnection('user-2');

      const answer = { type: 'answer', sdp: 'mock-answer-sdp' };
      await client.handleAnswer('user-2', answer);

      expect(mockSetRemoteDescription).toHaveBeenCalledWith(
        expect.objectContaining(answer)
      );
    });

    /**
     * Validates: Requirements 1.2, 1.3
     * Test: Handles offer and creates answer
     */
    test('handles offer and creates answer', async () => {
      const offer = { type: 'offer', sdp: 'mock-offer-sdp' };
      await client.handleOffer('user-2', offer);

      expect(mockSetRemoteDescription).toHaveBeenCalled();
      expect(mockCreateAnswer).toHaveBeenCalled();
      expect(mockSetLocalDescription).toHaveBeenCalled();
      expect(mockSignalingChannel.send).toHaveBeenCalledWith({
        type: 'webrtc_answer',
        from_user_id: 'user-1',
        to_user_id: 'user-2',
        room_id: 'room-123',
        sdp: expect.any(Object),
      });
    });

    /**
     * Validates: Requirements 1.4
     * Test: Handles ICE candidate
     */
    test('handles ICE candidate from remote peer', async () => {
      client.initializePeerConnection('user-2');

      const candidate = {
        candidate: 'candidate:1 1 UDP 2130706431 192.168.1.1 54321 typ host',
        sdpMLineIndex: 0,
      };

      await client.handleIceCandidate('user-2', candidate);

      expect(mockAddIceCandidate).toHaveBeenCalledWith(
        expect.objectContaining(candidate)
      );
    });

    /**
     * Validates: Requirements 1.4
     * Test: Sends ICE candidates via signaling channel
     */
    test('sends ICE candidates via signaling channel', () => {
      const peerConnection = client.initializePeerConnection('user-2');

      const mockCandidate = {
        candidate: 'candidate:1 1 UDP 2130706431 192.168.1.1 54321 typ host',
        toJSON: () => ({ candidate: 'mock-candidate' }),
      };

      // Trigger ICE candidate event
      if (peerConnection.onicecandidate) {
        peerConnection.onicecandidate({ candidate: mockCandidate });
      }

      expect(mockSignalingChannel.send).toHaveBeenCalledWith({
        type: 'webrtc_ice',
        from_user_id: 'user-1',
        to_user_id: 'user-2',
        room_id: 'room-123',
        candidate: { candidate: 'mock-candidate' },
      });
    });
  });

  describe('Peer Connection Cleanup', () => {
    /**
     * Validates: Requirements 1.7
     * Test: Closes peer connection and cleans up resources
     */
    test('closes peer connection and cleans up resources', () => {
      client.initializePeerConnection('user-2');
      client.monitorConnectionQuality('user-2');

      client.closePeerConnection('user-2');

      expect(mockClose).toHaveBeenCalled();
      expect(client.peerConnections.has('user-2')).toBe(false);
      expect(client.remoteStreams.has('user-2')).toBe(false);
      expect(client.qualityMonitors.has('user-2')).toBe(false);
    });

    /**
     * Validates: Requirements 1.7
     * Test: Calls onRemoteStreamRemoved callback
     */
    test('calls onRemoteStreamRemoved callback on cleanup', () => {
      const onRemoteStreamRemoved = jest.fn();
      client.onRemoteStreamRemoved = onRemoteStreamRemoved;

      client.initializePeerConnection('user-2');
      client.closePeerConnection('user-2');

      expect(onRemoteStreamRemoved).toHaveBeenCalledWith('user-2');
    });
  });

  describe('Error Handling', () => {
    /**
     * Validates: Requirements 7.1
     * Test: Handles peer connection errors
     */
    test('handles peer connection errors during offer creation', async () => {
      const mockError = new Error('Connection failed');
      mockCreateOffer.mockRejectedValueOnce(mockError);

      const onError = jest.fn();
      client.onError = onError;

      await client.createOffer('user-2');

      expect(onError).toHaveBeenCalledWith('peer_connection_error', mockError, 'user-2');
    });

    /**
     * Validates: Requirements 7.1
     * Test: Handles ICE candidate errors
     */
    test('handles ICE candidate errors', async () => {
      client.initializePeerConnection('user-2');

      const mockError = new Error('Invalid candidate');
      mockAddIceCandidate.mockRejectedValueOnce(mockError);

      const onError = jest.fn();
      client.onError = onError;

      await client.handleIceCandidate('user-2', { candidate: 'invalid' });

      expect(onError).toHaveBeenCalledWith('ice_candidate_error', mockError, 'user-2');
    });
  });

  describe('Utility Methods', () => {
    /**
     * Test: Gets all peer connections
     */
    test('gets all active peer connections', () => {
      client.initializePeerConnection('user-2');
      client.initializePeerConnection('user-3');

      const connections = client.getPeerConnections();

      expect(connections.size).toBe(2);
      expect(connections.has('user-2')).toBe(true);
      expect(connections.has('user-3')).toBe(true);
    });

    /**
     * Test: Gets remote stream for a user
     */
    test('gets remote stream for a user', () => {
      const mockStream = { id: 'stream-123' };
      client.remoteStreams.set('user-2', mockStream);

      const stream = client.getRemoteStream('user-2');

      expect(stream).toBe(mockStream);
    });

    /**
     * Test: Returns null for non-existent remote stream
     */
    test('returns null for non-existent remote stream', () => {
      const stream = client.getRemoteStream('user-999');

      expect(stream).toBeNull();
    });
  });

  describe('Multi-Participant Connection Management', () => {
    /**
     * Validates: Requirements 8.2, 8.3
     * Test: joinRoom establishes connections sequentially with all existing participants
     */
    test('joinRoom establishes connections sequentially with all existing participants', async () => {
      const callOrder = [];
      jest.spyOn(client, 'createOffer').mockImplementation(async (userId) => {
        callOrder.push(userId);
      });

      await client.joinRoom(['user-2', 'user-3', 'user-4']);

      expect(client.createOffer).toHaveBeenCalledTimes(3);
      expect(callOrder).toEqual(['user-2', 'user-3', 'user-4']);
    });

    /**
     * Validates: Requirements 8.2, 8.3
     * Test: participantJoined creates offer to new participant
     */
    test('participantJoined creates offer to new participant', async () => {
      jest.spyOn(client, 'createOffer').mockResolvedValue();

      await client.participantJoined('user-5');

      expect(client.createOffer).toHaveBeenCalledWith('user-5');
    });

    /**
     * Validates: Requirements 8.3
     * Test: participantLeft closes only that participant's connection
     */
    test('participantLeft closes only that participant\'s connection', () => {
      client.initializePeerConnection('user-2');
      client.initializePeerConnection('user-3');

      client.participantLeft('user-2');

      expect(client.peerConnections.has('user-2')).toBe(false);
      expect(client.peerConnections.has('user-3')).toBe(true);
    });

    /**
     * Validates: Requirements 8.2
     * Test: getConnectionState returns tracked state for peer
     */
    test('getConnectionState returns tracked state for peer', () => {
      client.initializePeerConnection('user-2');

      const state = client.getConnectionState('user-2');

      expect(state).toBe('new');
    });

    /**
     * Validates: Requirements 8.2, 8.3
     * Test: joinRoom with empty list does nothing
     */
    test('joinRoom with empty list does nothing', async () => {
      jest.spyOn(client, 'createOffer').mockResolvedValue();

      await client.joinRoom([]);

      expect(client.createOffer).not.toHaveBeenCalled();
    });

    /**
     * Validates: Requirements 8.2
     * Test: joinRoom skips already-connected peers
     */
    test('joinRoom skips already-connected peers', async () => {
      jest.spyOn(client, 'createOffer').mockResolvedValue();

      // Initialize a connection for user-2 and mark it as connected
      client.initializePeerConnection('user-2');
      client.connectionStates.set('user-2', 'connected');

      await client.joinRoom(['user-2', 'user-3']);

      // Should only call createOffer for user-3, not user-2
      expect(client.createOffer).toHaveBeenCalledTimes(1);
      expect(client.createOffer).toHaveBeenCalledWith('user-3');
      expect(client.createOffer).not.toHaveBeenCalledWith('user-2');
    });
  });

  describe('Multi-Participant Scenarios', () => {
    /**
     * Validates: Requirements 8.2, 8.3
     * Test: 4-participant connection establishment
     */
    test('4-participant: joinRoom creates offers for 3 peers and tracks connections', async () => {
      const createOfferSpy = jest.spyOn(client, 'createOffer').mockResolvedValue();

      await client.joinRoom(['user-2', 'user-3', 'user-4']);

      // createOffer called exactly 3 times
      expect(createOfferSpy).toHaveBeenCalledTimes(3);
      expect(createOfferSpy).toHaveBeenNthCalledWith(1, 'user-2');
      expect(createOfferSpy).toHaveBeenNthCalledWith(2, 'user-3');
      expect(createOfferSpy).toHaveBeenNthCalledWith(3, 'user-4');

      // 3 peer connections should exist (created inside createOffer via initializePeerConnection)
      // Since createOffer is mocked, we manually initialize to verify tracking
      client.initializePeerConnection('user-2');
      client.initializePeerConnection('user-3');
      client.initializePeerConnection('user-4');

      expect(client.peerConnections.size).toBe(3);
      expect(client.peerConnections.has('user-2')).toBe(true);
      expect(client.peerConnections.has('user-3')).toBe(true);
      expect(client.peerConnections.has('user-4')).toBe(true);

      // Connection states are tracked
      expect(client.getConnectionState('user-2')).toBe('new');
      expect(client.getConnectionState('user-3')).toBe('new');
      expect(client.getConnectionState('user-4')).toBe('new');
    });

    /**
     * Validates: Requirements 8.2, 8.3
     * Test: 8-participant connection establishment
     */
    test('8-participant: joinRoom creates offers for 7 peers', async () => {
      const createOfferSpy = jest.spyOn(client, 'createOffer').mockResolvedValue();

      const participants = ['user-2', 'user-3', 'user-4', 'user-5', 'user-6', 'user-7', 'user-8'];
      await client.joinRoom(participants);

      // createOffer called exactly 7 times
      expect(createOfferSpy).toHaveBeenCalledTimes(7);

      // Verify each participant got an offer
      participants.forEach((userId, idx) => {
        expect(createOfferSpy).toHaveBeenNthCalledWith(idx + 1, userId);
      });

      // Manually initialize connections to verify 7 peer connections can be tracked
      participants.forEach(userId => client.initializePeerConnection(userId));
      expect(client.peerConnections.size).toBe(7);
    });

    /**
     * Validates: Requirements 8.3
     * Test: Participant leave closes connection, removes from peerConnections and remoteStreams,
     *       calls onRemoteStreamRemoved, and leaves other connections intact
     */
    test('participant leave closes connection and cleans up without affecting others', () => {
      const onRemoteStreamRemoved = jest.fn();
      client.onRemoteStreamRemoved = onRemoteStreamRemoved;

      // Initialize connections for 4 peers
      client.initializePeerConnection('user-2');
      client.initializePeerConnection('user-3');
      client.initializePeerConnection('user-4');

      // Simulate remote streams for all peers
      const mockStream2 = { id: 'stream-2' };
      const mockStream3 = { id: 'stream-3' };
      const mockStream4 = { id: 'stream-4' };
      client.remoteStreams.set('user-2', mockStream2);
      client.remoteStreams.set('user-3', mockStream3);
      client.remoteStreams.set('user-4', mockStream4);

      // user-2 leaves
      client.participantLeft('user-2');

      // user-2's connection is closed and removed
      expect(client.peerConnections.has('user-2')).toBe(false);
      expect(client.remoteStreams.has('user-2')).toBe(false);

      // onRemoteStreamRemoved called with user-2
      expect(onRemoteStreamRemoved).toHaveBeenCalledWith('user-2');
      expect(onRemoteStreamRemoved).toHaveBeenCalledTimes(1);

      // user-3 and user-4 connections remain intact
      expect(client.peerConnections.has('user-3')).toBe(true);
      expect(client.peerConnections.has('user-4')).toBe(true);
      expect(client.remoteStreams.has('user-3')).toBe(true);
      expect(client.remoteStreams.has('user-4')).toBe(true);
      expect(client.remoteStreams.get('user-3')).toBe(mockStream3);
      expect(client.remoteStreams.get('user-4')).toBe(mockStream4);
    });

    /**
     * Validates: Requirements 8.2
     * Test: Sequential connection order is preserved in joinRoom
     */
    test('sequential connection order preserved in joinRoom', async () => {
      const callOrder = [];
      jest.spyOn(client, 'createOffer').mockImplementation(async (userId) => {
        callOrder.push(userId);
      });

      const participants = ['user-2', 'user-3', 'user-4', 'user-5'];
      await client.joinRoom(participants);

      // Connections must be established in the exact order provided
      expect(callOrder).toEqual(['user-2', 'user-3', 'user-4', 'user-5']);
    });

    /**
     * Validates: Requirements 8.3
     * Test: Partial leave (2 of 4 participants) doesn't affect remaining 2
     */
    test('partial leave does not affect remaining connections', () => {
      const onRemoteStreamRemoved = jest.fn();
      client.onRemoteStreamRemoved = onRemoteStreamRemoved;

      // Initialize 4 peer connections
      ['user-2', 'user-3', 'user-4', 'user-5'].forEach(userId => {
        client.initializePeerConnection(userId);
        client.remoteStreams.set(userId, { id: `stream-${userId}` });
      });

      expect(client.peerConnections.size).toBe(4);

      // user-2 and user-3 leave
      client.participantLeft('user-2');
      client.participantLeft('user-3');

      // user-2 and user-3 are gone
      expect(client.peerConnections.has('user-2')).toBe(false);
      expect(client.peerConnections.has('user-3')).toBe(false);
      expect(client.remoteStreams.has('user-2')).toBe(false);
      expect(client.remoteStreams.has('user-3')).toBe(false);

      // user-4 and user-5 remain connected
      expect(client.peerConnections.has('user-4')).toBe(true);
      expect(client.peerConnections.has('user-5')).toBe(true);
      expect(client.remoteStreams.has('user-4')).toBe(true);
      expect(client.remoteStreams.has('user-5')).toBe(true);

      // onRemoteStreamRemoved called exactly twice
      expect(onRemoteStreamRemoved).toHaveBeenCalledTimes(2);
      expect(onRemoteStreamRemoved).toHaveBeenCalledWith('user-2');
      expect(onRemoteStreamRemoved).toHaveBeenCalledWith('user-3');

      // Remaining count is 2
      expect(client.peerConnections.size).toBe(2);
    });
  });

  describe('ICE Server Validation', () => {
    /**
     * Test: _validateIceServers rejects empty array
     */
    test('_validateIceServers rejects empty array', () => {
      expect(client._validateIceServers([])).toBe(false);
    });

    /**
     * Test: _validateIceServers rejects non-array
     */
    test('_validateIceServers rejects non-array', () => {
      expect(client._validateIceServers(null)).toBe(false);
      expect(client._validateIceServers('stun:stun.l.google.com')).toBe(false);
    });

    /**
     * Test: _validateIceServers rejects invalid URL scheme
     */
    test('_validateIceServers rejects invalid URL scheme', () => {
      expect(client._validateIceServers([{ urls: 'http://example.com' }])).toBe(false);
    });

    /**
     * Test: _validateIceServers rejects TURN server without credentials
     */
    test('_validateIceServers rejects TURN server without credentials', () => {
      expect(client._validateIceServers([{ urls: 'turn:turn.example.com' }])).toBe(false);
    });

    /**
     * Test: _validateIceServers accepts valid STUN server
     */
    test('_validateIceServers accepts valid STUN server', () => {
      expect(client._validateIceServers([{ urls: 'stun:stun.l.google.com:19302' }])).toBe(true);
    });

    /**
     * Test: _validateIceServers accepts valid TURN server with credentials
     */
    test('_validateIceServers accepts valid TURN server with credentials', () => {
      expect(client._validateIceServers([{
        urls: 'turn:turn.example.com',
        username: 'user',
        credential: 'pass'
      }])).toBe(true);
    });

    /**
     * Test: setIceServers falls back to defaults on invalid config
     */
    test('setIceServers falls back to defaults on invalid config', () => {
      const originalServers = client.iceServers;
      client.setIceServers([]);
      // Should fall back to defaults (not empty)
      expect(client.iceServers.length).toBeGreaterThan(0);
    });

    /**
     * Test: setIceServers updates servers on valid config
     */
    test('setIceServers updates servers on valid config', () => {
      const newServers = [{ urls: 'stun:custom.stun.server:3478' }];
      client.setIceServers(newServers);
      expect(client.iceServers).toEqual(newServers);
    });
  });

  describe('Signaling Error Paths', () => {
    /**
     * Test: handleAnswer with no peer connection logs error
     */
    test('handleAnswer with no peer connection does not throw', async () => {
      // No peer connection initialized for user-99
      await expect(client.handleAnswer('user-99', { type: 'answer', sdp: 'sdp' })).resolves.toBeUndefined();
    });

    /**
     * Test: handleAnswer error path calls onError
     */
    test('handleAnswer error calls onError', async () => {
      const onError = jest.fn();
      client.onError = onError;
      client.initializePeerConnection('user-2');
      mockSetRemoteDescription.mockRejectedValueOnce(new Error('SDP error'));

      await client.handleAnswer('user-2', { type: 'answer', sdp: 'bad-sdp' });

      expect(onError).toHaveBeenCalledWith('peer_connection_error', expect.any(Error), 'user-2');
    });

    /**
     * Test: handleOffer error path calls onError
     */
    test('handleOffer error calls onError', async () => {
      const onError = jest.fn();
      client.onError = onError;
      mockSetRemoteDescription.mockRejectedValueOnce(new Error('SDP error'));

      await client.handleOffer('user-2', { type: 'offer', sdp: 'bad-sdp' });

      expect(onError).toHaveBeenCalledWith('peer_connection_error', expect.any(Error), 'user-2');
    });

    /**
     * Test: handleIceCandidate with no peer connection does not throw
     */
    test('handleIceCandidate with no peer connection does not throw', async () => {
      await expect(client.handleIceCandidate('user-99', { candidate: 'c' })).resolves.toBeUndefined();
    });
  });

  describe('Stream Management', () => {
    /**
     * Test: attachRemoteStream stores stream for user
     */
    test('attachRemoteStream stores stream for user', () => {
      const mockStream = { id: 'remote-stream-1' };
      client.attachRemoteStream('user-2', mockStream);
      expect(client.remoteStreams.get('user-2')).toBe(mockStream);
    });

    /**
     * Test: releaseMediaStreams also stops screen stream
     */
    test('releaseMediaStreams stops screen stream if active', async () => {
      await client.getLocalMediaStream();
      await client.startScreenShare();

      expect(client.screenStream).not.toBeNull();

      client.releaseMediaStreams();

      expect(client.screenStream).toBeNull();
      expect(client.localStream).toBeNull();
    });
  });

  describe('Adaptive Quality', () => {
    /**
     * Validates: Requirements 9.2
     * Test: reduceVideoQuality replaces video track in peer connections
     */
    test('reduceVideoQuality replaces video track in peer connections', async () => {
      await client.getLocalMediaStream();
      client.initializePeerConnection('user-2');

      const reducedVideoTrack = { kind: 'video', enabled: true, stop: jest.fn() };
      const reducedStream = {
        getVideoTracks: jest.fn(() => [reducedVideoTrack]),
        getTracks: jest.fn(() => [reducedVideoTrack]),
      };
      global.navigator.mediaDevices.getUserMedia.mockResolvedValueOnce(reducedStream);

      await client.reduceVideoQuality();

      expect(mockReplaceTrack).toHaveBeenCalledWith(reducedVideoTrack);
    });

    /**
     * Validates: Requirements 9.2
     * Test: reduceVideoQuality handles errors gracefully
     */
    test('reduceVideoQuality handles getUserMedia error gracefully', async () => {
      global.navigator.mediaDevices.getUserMedia.mockRejectedValueOnce(new Error('Device error'));

      // Should not throw
      await expect(client.reduceVideoQuality()).resolves.toBeUndefined();
    });
  });

  describe('Stats and Performance', () => {
    /**
     * Validates: Requirements 11.3, 11.5
     * Test: getStatsCollector returns the stats collector instance
     */
    test('getStatsCollector returns stats collector instance', () => {
      const collector = client.getStatsCollector();
      expect(collector).toBeDefined();
      expect(typeof collector.collectStats).toBe('function');
    });

    /**
     * Validates: Requirements 11.3, 11.5
     * Test: logPerformanceReport does nothing when no peers connected
     */
    test('logPerformanceReport does nothing when no peers connected', () => {
      // Should not throw
      expect(() => client.logPerformanceReport()).not.toThrow();
    });

    /**
     * Validates: Requirements 11.3, 11.5
     * Test: logPerformanceReport calls logStatsReport for each peer
     */
    test('logPerformanceReport calls logStatsReport for each connected peer', () => {
      client.initializePeerConnection('user-2');
      client.initializePeerConnection('user-3');

      const logStatsReportSpy = jest.spyOn(client.getStatsCollector(), 'logStatsReport').mockImplementation(() => {});

      client.logPerformanceReport();

      expect(logStatsReportSpy).toHaveBeenCalledTimes(2);
      expect(logStatsReportSpy).toHaveBeenCalledWith('user-2');
      expect(logStatsReportSpy).toHaveBeenCalledWith('user-3');
    });

    /**
     * Validates: Requirements 8.2
     * Test: getConnectedPeerCount returns count of connected peers
     */
    test('getConnectedPeerCount returns count of connected peers', () => {
      // No connections
      expect(client.getConnectedPeerCount()).toBe(0);

      // Initialize connections with different states
      const pc2 = client.initializePeerConnection('user-2');
      const pc3 = client.initializePeerConnection('user-3');
      const pc4 = client.initializePeerConnection('user-4');

      // Simulate connection states
      pc2.iceConnectionState = 'connected';
      pc3.iceConnectionState = 'completed';
      pc4.iceConnectionState = 'checking';

      expect(client.getConnectedPeerCount()).toBe(2);
    });
  });
});
