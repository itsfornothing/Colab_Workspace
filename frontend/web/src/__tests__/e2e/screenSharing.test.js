/**
 * Screen Sharing E2E Test
 *
 * Tests the complete screen sharing flow including:
 * 1. Screen share activation (getDisplayMedia called, screen track obtained)
 * 2. Screen track replaces video track in all peer connections
 * 3. Original camera track is preserved for restoration
 * 4. Screen share stop and camera restoration
 * 5. Screen share permission denied error handling
 * 6. Screen share with multiple active peer connections
 *
 * Requirements: 12.4, 4.1, 4.5
 */

import WebRTCClient from '@/lib/webrtc/WebRTCClient';
import {
  setupWebRTCMocks,
  teardownWebRTCMocks,
  MockMediaStream,
  MockMediaStreamTrack,
  simulateScreenSharePermissionDenied,
  flushPromises,
} from './mocks/webrtcMocks';

describe('Screen Sharing E2E', () => {
  let client;
  let mockSignalingChannel;

  beforeEach(() => {
    setupWebRTCMocks();

    mockSignalingChannel = {
      send: jest.fn(),
    };

    client = new WebRTCClient('room-123', 'user-a', mockSignalingChannel);
  });

  afterEach(() => {
    client.releaseMediaStreams();
    teardownWebRTCMocks();
  });

  // ─────────────────────────────────────────────────────────────────────────
  // 1. Screen share activation
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Validates: Requirements 12.4, 4.1
   * Test: startScreenShare() calls getDisplayMedia with correct constraints
   */
  test('startScreenShare calls getDisplayMedia with correct constraints', async () => {
    await client.getLocalMediaStream();

    await client.startScreenShare();

    expect(navigator.mediaDevices.getDisplayMedia).toHaveBeenCalledWith(
      expect.objectContaining({
        video: expect.objectContaining({ cursor: 'always' }),
        audio: false,
      })
    );
  });

  /**
   * Validates: Requirements 12.4, 4.1
   * Test: startScreenShare() returns a screen stream with a video track
   */
  test('startScreenShare returns screen stream with video track', async () => {
    await client.getLocalMediaStream();

    const screenStream = await client.startScreenShare();

    expect(screenStream).toBeDefined();
    const videoTracks = screenStream.getVideoTracks();
    expect(videoTracks).toHaveLength(1);
    expect(videoTracks[0].id).toBe('screen-share-track');
    expect(videoTracks[0].label).toBe('Screen share');
  });

  /**
   * Validates: Requirements 12.4, 4.1
   * Test: isScreenSharing() returns true after startScreenShare()
   */
  test('isScreenSharing returns true after screen share starts', async () => {
    await client.getLocalMediaStream();

    expect(client.isScreenSharing()).toBe(false);

    await client.startScreenShare();

    expect(client.isScreenSharing()).toBe(true);
  });

  // ─────────────────────────────────────────────────────────────────────────
  // 2. Screen track replaces video track in peer connections
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Validates: Requirements 12.4, 4.2
   * Test: replaceTrack is called on the video sender with the screen track
   */
  test('screen track replaces video track in peer connection', async () => {
    await client.getLocalMediaStream();

    // Establish a peer connection
    client.initializePeerConnection('user-b');
    const peerConnection = client.peerConnections.get('user-b');

    // Spy on the video sender's replaceTrack
    const videoSender = peerConnection.getSenders().find(
      (s) => s.track && s.track.kind === 'video'
    );
    expect(videoSender).toBeDefined();
    const replaceTrackSpy = jest.spyOn(videoSender, 'replaceTrack');

    await client.startScreenShare();

    // replaceTrack should have been called with the screen track
    expect(replaceTrackSpy).toHaveBeenCalledTimes(1);
    const screenTrack = client.screenStream.getVideoTracks()[0];
    expect(replaceTrackSpy).toHaveBeenCalledWith(screenTrack);
  });

  /**
   * Validates: Requirements 12.4, 4.2
   * Test: Original camera track is preserved in originalVideoTrack
   */
  test('original camera track is preserved when screen sharing starts', async () => {
    await client.getLocalMediaStream();

    const originalVideoTrack = client.localStream.getVideoTracks()[0];
    expect(client.originalVideoTrack).toBeNull();

    await client.startScreenShare();

    expect(client.originalVideoTrack).toBe(originalVideoTrack);
  });

  /**
   * Validates: Requirements 12.4, 4.2
   * Test: Screen track is different from the original camera track
   */
  test('screen track is distinct from the original camera track', async () => {
    await client.getLocalMediaStream();

    const originalVideoTrack = client.localStream.getVideoTracks()[0];

    await client.startScreenShare();

    const screenTrack = client.screenStream.getVideoTracks()[0];
    expect(screenTrack).not.toBe(originalVideoTrack);
    expect(screenTrack.id).toBe('screen-share-track');
  });

  // ─────────────────────────────────────────────────────────────────────────
  // 3. Screen share stop and camera restoration
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Validates: Requirements 12.4, 4.5
   * Test: stopScreenShare() stops all screen stream tracks
   */
  test('stopScreenShare stops all screen stream tracks', async () => {
    await client.getLocalMediaStream();
    await client.startScreenShare();

    const screenTrack = client.screenStream.getVideoTracks()[0];
    const stopSpy = jest.spyOn(screenTrack, 'stop');

    client.stopScreenShare();

    expect(stopSpy).toHaveBeenCalled();
    expect(screenTrack._stopped).toBe(true);
  });

  /**
   * Validates: Requirements 12.4, 4.5
   * Test: stopScreenShare() restores the original camera track via replaceTrack
   */
  test('stopScreenShare restores original camera track in peer connection', async () => {
    await client.getLocalMediaStream();

    const originalVideoTrack = client.localStream.getVideoTracks()[0];

    client.initializePeerConnection('user-b');
    const peerConnection = client.peerConnections.get('user-b');

    await client.startScreenShare();

    // After screen share starts, find the video sender and spy on replaceTrack
    const videoSender = peerConnection.getSenders().find(
      (s) => s.track && s.track.kind === 'video'
    );
    const replaceTrackSpy = jest.spyOn(videoSender, 'replaceTrack');

    client.stopScreenShare();

    // replaceTrack should be called with the original camera track
    expect(replaceTrackSpy).toHaveBeenCalledWith(originalVideoTrack);
  });

  /**
   * Validates: Requirements 12.4, 4.5
   * Test: isScreenSharing() returns false after stopScreenShare()
   */
  test('isScreenSharing returns false after screen share stops', async () => {
    await client.getLocalMediaStream();
    await client.startScreenShare();

    expect(client.isScreenSharing()).toBe(true);

    client.stopScreenShare();

    expect(client.isScreenSharing()).toBe(false);
  });

  /**
   * Validates: Requirements 12.4, 4.5
   * Test: originalVideoTrack is cleared after stopScreenShare()
   */
  test('originalVideoTrack is cleared after stopScreenShare', async () => {
    await client.getLocalMediaStream();
    await client.startScreenShare();

    expect(client.originalVideoTrack).not.toBeNull();

    client.stopScreenShare();

    expect(client.originalVideoTrack).toBeNull();
  });

  /**
   * Validates: Requirements 12.4, 4.5
   * Test: screenStream is cleared after stopScreenShare()
   */
  test('screenStream is null after stopScreenShare', async () => {
    await client.getLocalMediaStream();
    await client.startScreenShare();

    expect(client.screenStream).not.toBeNull();

    client.stopScreenShare();

    expect(client.screenStream).toBeNull();
  });

  /**
   * Validates: Requirements 12.4, 4.5
   * Test: Browser stop-sharing button (track.onended) triggers stopScreenShare
   */
  test('browser stop-sharing button triggers stopScreenShare via track.onended', async () => {
    await client.getLocalMediaStream();
    client.initializePeerConnection('user-b');

    await client.startScreenShare();

    expect(client.isScreenSharing()).toBe(true);

    // Simulate the user clicking the browser's "Stop sharing" button
    const screenTrack = client.screenStream.getVideoTracks()[0];
    screenTrack.onended();

    expect(client.isScreenSharing()).toBe(false);
    expect(client.originalVideoTrack).toBeNull();
  });

  // ─────────────────────────────────────────────────────────────────────────
  // 4. Screen share permission denied
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Validates: Requirements 12.4, 4.6
   * Test: NotAllowedError from getDisplayMedia is handled gracefully
   */
  test('screen share permission denied is handled gracefully', async () => {
    await client.getLocalMediaStream();

    simulateScreenSharePermissionDenied();

    const errors = [];
    client.onError = (type, error) => {
      errors.push({ type, error });
    };

    await expect(client.startScreenShare()).rejects.toThrow('Permission denied');

    expect(errors).toHaveLength(1);
    expect(errors[0].type).toBe('screen_share_permission_denied');
    expect(errors[0].error.name).toBe('NotAllowedError');
  });

  /**
   * Validates: Requirements 12.4, 4.6
   * Test: isScreenSharing() remains false when permission is denied
   */
  test('isScreenSharing remains false when permission is denied', async () => {
    await client.getLocalMediaStream();

    simulateScreenSharePermissionDenied();
    client.onError = jest.fn();

    try {
      await client.startScreenShare();
    } catch {
      // expected
    }

    expect(client.isScreenSharing()).toBe(false);
  });

  /**
   * Validates: Requirements 12.4, 4.6
   * Test: originalVideoTrack is not set when permission is denied
   */
  test('originalVideoTrack is not set when screen share permission is denied', async () => {
    await client.getLocalMediaStream();

    simulateScreenSharePermissionDenied();
    client.onError = jest.fn();

    try {
      await client.startScreenShare();
    } catch {
      // expected
    }

    expect(client.originalVideoTrack).toBeNull();
  });

  // ─────────────────────────────────────────────────────────────────────────
  // 5. Screen share with multiple active peer connections
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Validates: Requirements 12.4, 4.2
   * Test: replaceTrack is called on all peer connections' video senders
   */
  test('screen track replaces video track in all peer connections', async () => {
    await client.getLocalMediaStream();

    // Establish connections with three remote participants
    const remoteUsers = ['user-b', 'user-c', 'user-d'];
    const replaceTrackSpies = [];

    for (const userId of remoteUsers) {
      client.initializePeerConnection(userId);
      const pc = client.peerConnections.get(userId);
      const videoSender = pc.getSenders().find(
        (s) => s.track && s.track.kind === 'video'
      );
      expect(videoSender).toBeDefined();
      replaceTrackSpies.push(jest.spyOn(videoSender, 'replaceTrack'));
    }

    await client.startScreenShare();

    const screenTrack = client.screenStream.getVideoTracks()[0];

    // Every peer connection's video sender should have received the screen track
    for (const spy of replaceTrackSpies) {
      expect(spy).toHaveBeenCalledTimes(1);
      expect(spy).toHaveBeenCalledWith(screenTrack);
    }
  });

  /**
   * Validates: Requirements 12.4, 4.5
   * Test: Camera track is restored in all peer connections when screen share stops
   */
  test('camera track is restored in all peer connections when screen share stops', async () => {
    await client.getLocalMediaStream();

    const originalVideoTrack = client.localStream.getVideoTracks()[0];
    const remoteUsers = ['user-b', 'user-c', 'user-d'];

    for (const userId of remoteUsers) {
      client.initializePeerConnection(userId);
    }

    await client.startScreenShare();

    // Collect spies after screen share has started (senders now hold the screen track)
    const restoreSpies = [];
    for (const userId of remoteUsers) {
      const pc = client.peerConnections.get(userId);
      const videoSender = pc.getSenders().find(
        (s) => s.track && s.track.kind === 'video'
      );
      restoreSpies.push(jest.spyOn(videoSender, 'replaceTrack'));
    }

    client.stopScreenShare();

    for (const spy of restoreSpies) {
      expect(spy).toHaveBeenCalledWith(originalVideoTrack);
    }
  });

  /**
   * Validates: Requirements 12.4, 4.2
   * Test: All remote participants receive the screen track (same track instance)
   */
  test('all remote participants receive the same screen track instance', async () => {
    await client.getLocalMediaStream();

    const remoteUsers = ['user-b', 'user-c'];
    const capturedTracks = [];

    for (const userId of remoteUsers) {
      client.initializePeerConnection(userId);
      const pc = client.peerConnections.get(userId);
      const videoSender = pc.getSenders().find(
        (s) => s.track && s.track.kind === 'video'
      );
      videoSender.replaceTrack = jest.fn(async (track) => {
        capturedTracks.push(track);
      });
    }

    await client.startScreenShare();

    // Both senders should have received the exact same screen track
    expect(capturedTracks).toHaveLength(2);
    expect(capturedTracks[0]).toBe(capturedTracks[1]);
    expect(capturedTracks[0].id).toBe('screen-share-track');
  });

  // ─────────────────────────────────────────────────────────────────────────
  // 6. Full screen share lifecycle with signaling
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Validates: Requirements 12.4, 4.1, 4.5
   * Test: Complete screen share lifecycle — start, verify, stop, verify restoration
   */
  test('complete screen share lifecycle: start, verify track replacement, stop, verify restoration', async () => {
    // ── Setup ──────────────────────────────────────────────────────────────
    await client.getLocalMediaStream();
    client.initializePeerConnection('user-b');

    const peerConnection = client.peerConnections.get('user-b');
    const originalVideoTrack = client.localStream.getVideoTracks()[0];

    // ── Phase 1: Before screen share ───────────────────────────────────────
    expect(client.isScreenSharing()).toBe(false);
    expect(client.originalVideoTrack).toBeNull();
    expect(client.screenStream).toBeNull();

    // ── Phase 2: Start screen share ────────────────────────────────────────
    const videoSender = peerConnection.getSenders().find(
      (s) => s.track && s.track.kind === 'video'
    );
    const replaceTrackSpy = jest.spyOn(videoSender, 'replaceTrack');

    const screenStream = await client.startScreenShare();

    expect(client.isScreenSharing()).toBe(true);
    expect(client.originalVideoTrack).toBe(originalVideoTrack);
    expect(client.screenStream).toBe(screenStream);

    const screenTrack = screenStream.getVideoTracks()[0];
    expect(replaceTrackSpy).toHaveBeenCalledWith(screenTrack);
    expect(screenTrack.id).toBe('screen-share-track');

    // ── Phase 3: Stop screen share ─────────────────────────────────────────
    const stopSpy = jest.spyOn(screenTrack, 'stop');
    const restoreTrackSpy = jest.spyOn(videoSender, 'replaceTrack');

    client.stopScreenShare();

    expect(client.isScreenSharing()).toBe(false);
    expect(client.originalVideoTrack).toBeNull();
    expect(client.screenStream).toBeNull();
    expect(stopSpy).toHaveBeenCalled();
    expect(restoreTrackSpy).toHaveBeenCalledWith(originalVideoTrack);
  });

  /**
   * Validates: Requirements 12.4, 4.5
   * Test: stopScreenShare is a no-op when screen sharing is not active
   */
  test('stopScreenShare is a no-op when not screen sharing', async () => {
    await client.getLocalMediaStream();
    client.initializePeerConnection('user-b');

    // Should not throw
    expect(() => client.stopScreenShare()).not.toThrow();
    expect(client.isScreenSharing()).toBe(false);
  });

  /**
   * Validates: Requirements 12.4, 4.1, 4.5
   * Test: Screen share can be restarted after stopping
   */
  test('screen share can be restarted after stopping', async () => {
    await client.getLocalMediaStream();
    client.initializePeerConnection('user-b');

    // First screen share session
    await client.startScreenShare();
    expect(client.isScreenSharing()).toBe(true);

    client.stopScreenShare();
    expect(client.isScreenSharing()).toBe(false);

    // Second screen share session
    await client.startScreenShare();
    expect(client.isScreenSharing()).toBe(true);

    expect(navigator.mediaDevices.getDisplayMedia).toHaveBeenCalledTimes(2);

    client.stopScreenShare();
    expect(client.isScreenSharing()).toBe(false);
  });
});
