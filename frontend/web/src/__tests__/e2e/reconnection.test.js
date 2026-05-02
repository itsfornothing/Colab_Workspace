/**
 * Reconnection E2E Test
 * 
 * This test validates the reconnection logic when WebRTC connections fail:
 * 1. Simulate connection loss by setting ICE connection state to 'disconnected' or 'failed'
 * 2. Verify reconnection attempts are made (up to 3 times per spec)
 * 3. Test successful reconnection after initial failure
 * 4. Test failure after max attempts with appropriate error handling
 * 
 * Requirements: 12.7, 7.1, 7.2
 */

import WebRTCClient from '@/lib/webrtc/WebRTCClient';
import {
  setupWebRTCMocks,
  teardownWebRTCMocks,
  simulateIceConnectionStateChange,
} from './mocks/webrtcMocks';

/**
 * Helper to flush all pending promises and timers.
 * With fake timers, we need to advance timers AND flush promises together.
 */
async function flushAll() {
  // Run all pending timers
  jest.runAllTimers();
  // Flush microtasks (resolved promises)
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

describe('Reconnection E2E', () => {
  let client;
  let mockSignalingChannel;
  let errorCallback;
  let connectionStateCallback;

  beforeEach(() => {
    // Use fake timers to control reconnection delays
    jest.useFakeTimers();

    // Setup WebRTC mocks
    setupWebRTCMocks();

    // Create mock signaling channel
    mockSignalingChannel = {
      send: jest.fn(),
    };

    // Create WebRTC client
    client = new WebRTCClient('room-123', 'user-a', mockSignalingChannel);

    // Setup error callback to track errors
    errorCallback = jest.fn();
    client.onError = errorCallback;

    // Setup connection state callback
    connectionStateCallback = jest.fn();
    client.onConnectionStateChange = connectionStateCallback;
  });

  afterEach(() => {
    // Cleanup - use real timers to avoid issues with fake timer cleanup
    jest.useRealTimers();
    if (client) {
      // Manually clear reconnection timeouts to avoid leaks
      client.reconnectionState.forEach((state) => {
        if (state.timeout) clearTimeout(state.timeout);
      });
      client.reconnectionState.clear();
      client.peerConnections.forEach((pc) => pc.close());
      client.peerConnections.clear();
    }
    teardownWebRTCMocks();
  });

  /**
   * Validates: Requirements 7.1, 7.4
   * Test: Connection loss triggers reconnection attempt
   */
  test('connection loss triggers reconnection attempt', async () => {
    // Get local media stream
    await client.getLocalMediaStream();

    // Initialize peer connection
    const peerConnection = client.initializePeerConnection('user-b');
    expect(peerConnection).toBeDefined();

    // Verify initial state
    expect(client.reconnectionState.has('user-b')).toBe(false);

    // Simulate connection loss by changing ICE connection state to 'disconnected'
    simulateIceConnectionStateChange(peerConnection, 'disconnected');

    // Flush microtasks
    await Promise.resolve();

    // Verify reconnection state was created
    expect(client.reconnectionState.has('user-b')).toBe(true);
    const reconnection = client.reconnectionState.get('user-b');
    expect(reconnection.attempts).toBe(1);
    expect(reconnection.timeout).toBeDefined();

    // Fast-forward time to trigger reconnection (2^1 = 2 seconds)
    jest.advanceTimersByTime(2000);
    await Promise.resolve();
    await Promise.resolve();

    // Verify new offer was created (reconnection attempt)
    expect(mockSignalingChannel.send).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'webrtc_offer',
        from_user_id: 'user-a',
        to_user_id: 'user-b',
      })
    );
  });

  /**
   * Validates: Requirements 7.1, 7.4
   * Test: Connection failure (not just disconnected) also triggers reconnection
   */
  test('connection failure triggers reconnection attempt', async () => {
    // Get local media stream
    await client.getLocalMediaStream();

    // Initialize peer connection
    const peerConnection = client.initializePeerConnection('user-b');

    // Simulate connection failure by changing ICE connection state to 'failed'
    simulateIceConnectionStateChange(peerConnection, 'failed');

    await Promise.resolve();

    // Verify reconnection was triggered
    expect(client.reconnectionState.has('user-b')).toBe(true);
    const reconnection = client.reconnectionState.get('user-b');
    expect(reconnection.attempts).toBe(1);
  });

  /**
   * Validates: Requirements 7.1, 7.2
   * Test: Successful reconnection after first attempt fails
   */
  test('successful reconnection after first attempt fails', async () => {
    // Get local media stream
    await client.getLocalMediaStream();

    // Initialize peer connection
    let peerConnection = client.initializePeerConnection('user-b');

    // Simulate connection loss
    simulateIceConnectionStateChange(peerConnection, 'failed');
    await Promise.resolve();

    // Verify first reconnection attempt
    expect(client.reconnectionState.get('user-b').attempts).toBe(1);

    // Fast-forward to trigger first reconnection attempt (2^1 = 2 seconds)
    jest.advanceTimersByTime(2000);
    await Promise.resolve();
    await Promise.resolve();

    // Verify new peer connection was created
    peerConnection = client.peerConnections.get('user-b');
    expect(peerConnection).toBeDefined();

    // Simulate successful reconnection by changing state to 'connected'
    simulateIceConnectionStateChange(peerConnection, 'connected');
    await Promise.resolve();

    // Verify reconnection state was cleared on success
    expect(client.reconnectionState.has('user-b')).toBe(false);

    // Verify no error was reported
    expect(errorCallback).not.toHaveBeenCalledWith(
      'reconnection_failed',
      expect.anything(),
      'user-b'
    );
  });

  /**
   * Validates: Requirements 7.1, 7.2
   * Test: Reconnection with exponential backoff
   */
  test('reconnection uses exponential backoff', async () => {
    // Get local media stream
    await client.getLocalMediaStream();

    // Initialize peer connection
    let peerConnection = client.initializePeerConnection('user-b');

    // Simulate connection loss
    simulateIceConnectionStateChange(peerConnection, 'failed');
    await Promise.resolve();

    // First attempt: 2^1 = 2 seconds
    expect(client.reconnectionState.get('user-b').attempts).toBe(1);
    jest.advanceTimersByTime(2000);
    await Promise.resolve();
    await Promise.resolve();

    // Simulate failure again
    peerConnection = client.peerConnections.get('user-b');
    simulateIceConnectionStateChange(peerConnection, 'failed');
    await Promise.resolve();

    // Second attempt: 2^2 = 4 seconds
    expect(client.reconnectionState.get('user-b').attempts).toBe(2);

    // Count offers before advancing time
    const offerCountBefore = mockSignalingChannel.send.mock.calls.filter(
      call => call[0].type === 'webrtc_offer'
    ).length;

    // Advance only 3 seconds - should not trigger yet
    jest.advanceTimersByTime(3000);
    await Promise.resolve();
    await Promise.resolve();

    const offerCountMid = mockSignalingChannel.send.mock.calls.filter(
      call => call[0].type === 'webrtc_offer'
    ).length;
    // No new offer should have been sent yet
    expect(offerCountMid).toBe(offerCountBefore);

    // Advance remaining 1 second to reach 4 seconds total
    jest.advanceTimersByTime(1000);
    await Promise.resolve();
    await Promise.resolve();

    // Verify new offer was sent after full 4 seconds
    const offerCountAfter = mockSignalingChannel.send.mock.calls.filter(
      call => call[0].type === 'webrtc_offer'
    ).length;
    expect(offerCountAfter).toBeGreaterThan(offerCountBefore);
  });

  /**
   * Validates: Requirements 7.1, 7.2
   * Test: Failure after max attempts (3) triggers error callback
   */
  test('failure after max attempts triggers error callback', async () => {
    // Get local media stream
    await client.getLocalMediaStream();

    // Initialize peer connection
    let peerConnection = client.initializePeerConnection('user-b');

    // Simulate connection loss
    simulateIceConnectionStateChange(peerConnection, 'failed');
    await Promise.resolve();

    // Attempt 1: 2^1 = 2 seconds
    expect(client.reconnectionState.get('user-b').attempts).toBe(1);
    jest.advanceTimersByTime(2000);
    await Promise.resolve();
    await Promise.resolve();

    // Simulate failure again
    peerConnection = client.peerConnections.get('user-b');
    simulateIceConnectionStateChange(peerConnection, 'failed');
    await Promise.resolve();

    // Attempt 2: 2^2 = 4 seconds
    expect(client.reconnectionState.get('user-b').attempts).toBe(2);
    jest.advanceTimersByTime(4000);
    await Promise.resolve();
    await Promise.resolve();

    // Simulate failure again
    peerConnection = client.peerConnections.get('user-b');
    simulateIceConnectionStateChange(peerConnection, 'failed');
    await Promise.resolve();

    // Attempt 3: 2^3 = 8 seconds
    expect(client.reconnectionState.get('user-b').attempts).toBe(3);
    jest.advanceTimersByTime(8000);
    await Promise.resolve();
    await Promise.resolve();

    // Simulate failure again (this triggers the max attempts check)
    peerConnection = client.peerConnections.get('user-b');
    simulateIceConnectionStateChange(peerConnection, 'failed');
    await Promise.resolve();

    // Verify max attempts reached and error callback was called
    expect(errorCallback).toHaveBeenCalledWith(
      'reconnection_failed',
      expect.objectContaining({
        message: 'Max attempts reached',
      }),
      'user-b'
    );

    // Verify peer connection was closed
    expect(client.peerConnections.has('user-b')).toBe(false);

    // Verify reconnection state was cleared
    expect(client.reconnectionState.has('user-b')).toBe(false);
  });

  /**
   * Validates: Requirements 7.1, 7.2
   * Test: Reconnection attempts stop when max reached
   */
  test('no further reconnection attempts after max reached', async () => {
    // Get local media stream
    await client.getLocalMediaStream();

    // Initialize peer connection
    let peerConnection = client.initializePeerConnection('user-b');

    // Simulate connection loss
    simulateIceConnectionStateChange(peerConnection, 'failed');
    await Promise.resolve();

    // Go through all 3 attempts
    for (let i = 1; i <= 3; i++) {
      const delay = Math.pow(2, i) * 1000;
      jest.advanceTimersByTime(delay);
      await Promise.resolve();
      await Promise.resolve();

      if (i < 3) {
        peerConnection = client.peerConnections.get('user-b');
        if (peerConnection) {
          simulateIceConnectionStateChange(peerConnection, 'failed');
          await Promise.resolve();
        }
      }
    }

    // Simulate one more failure after max attempts
    peerConnection = client.peerConnections.get('user-b');
    if (peerConnection) {
      simulateIceConnectionStateChange(peerConnection, 'failed');
      await Promise.resolve();
    }

    // Verify error was called
    expect(errorCallback).toHaveBeenCalledWith(
      'reconnection_failed',
      expect.any(Error),
      'user-b'
    );

    // Clear the mock to count new calls
    mockSignalingChannel.send.mockClear();

    // Advance time significantly
    jest.advanceTimersByTime(30000); // 30 seconds
    await Promise.resolve();
    await Promise.resolve();

    // Verify no new offers were sent (no more reconnection attempts)
    const newOffers = mockSignalingChannel.send.mock.calls.filter(
      call => call[0].type === 'webrtc_offer'
    );
    expect(newOffers.length).toBe(0);
  });

  /**
   * Validates: Requirements 7.1, 7.5
   * Test: Successful connection resets reconnection attempts
   */
  test('successful connection resets reconnection attempts', async () => {
    // Get local media stream
    await client.getLocalMediaStream();

    // Initialize peer connection
    let peerConnection = client.initializePeerConnection('user-b');

    // Simulate connection loss
    simulateIceConnectionStateChange(peerConnection, 'failed');
    await Promise.resolve();

    // First reconnection attempt
    expect(client.reconnectionState.get('user-b').attempts).toBe(1);
    jest.advanceTimersByTime(2000);
    await Promise.resolve();
    await Promise.resolve();

    // Simulate successful connection
    peerConnection = client.peerConnections.get('user-b');
    simulateIceConnectionStateChange(peerConnection, 'connected');
    await Promise.resolve();

    // Verify reconnection state was cleared
    expect(client.reconnectionState.has('user-b')).toBe(false);

    // Simulate another connection loss
    simulateIceConnectionStateChange(peerConnection, 'failed');
    await Promise.resolve();

    // Verify reconnection attempts counter was reset (should be 1, not 2)
    expect(client.reconnectionState.get('user-b').attempts).toBe(1);
  });

  /**
   * Validates: Requirements 7.1, 7.4
   * Test: Multiple peers can reconnect independently
   */
  test('multiple peers can reconnect independently', async () => {
    // Get local media stream
    await client.getLocalMediaStream();

    // Initialize peer connections with two users
    const peerConnectionB = client.initializePeerConnection('user-b');
    const peerConnectionC = client.initializePeerConnection('user-c');

    // Simulate connection loss for user-b only
    simulateIceConnectionStateChange(peerConnectionB, 'failed');
    await Promise.resolve();

    // Verify only user-b has reconnection state
    expect(client.reconnectionState.has('user-b')).toBe(true);
    expect(client.reconnectionState.has('user-c')).toBe(false);

    // Fast-forward to trigger reconnection for user-b
    jest.advanceTimersByTime(2000);
    await Promise.resolve();
    await Promise.resolve();

    // Verify offer was sent only to user-b
    const offersToB = mockSignalingChannel.send.mock.calls.filter(
      call => call[0].type === 'webrtc_offer' && call[0].to_user_id === 'user-b'
    );
    const offersToC = mockSignalingChannel.send.mock.calls.filter(
      call => call[0].type === 'webrtc_offer' && call[0].to_user_id === 'user-c'
    );

    expect(offersToB.length).toBeGreaterThan(0);
    expect(offersToC.length).toBe(0);

    // Now simulate connection loss for user-c
    simulateIceConnectionStateChange(peerConnectionC, 'failed');
    await Promise.resolve();

    // Verify both have reconnection state
    expect(client.reconnectionState.has('user-b')).toBe(true);
    expect(client.reconnectionState.has('user-c')).toBe(true);

    // Verify they have independent attempt counters
    expect(client.reconnectionState.get('user-b').attempts).toBe(1);
    expect(client.reconnectionState.get('user-c').attempts).toBe(1);
  });

  /**
   * Validates: Requirements 7.1, 7.6
   * Test: Reconnection cleans up old connection before creating new one
   */
  test('reconnection cleans up old connection before creating new one', async () => {
    // Get local media stream
    await client.getLocalMediaStream();

    // Initialize peer connection
    const oldPeerConnection = client.initializePeerConnection('user-b');
    const closeSpy = jest.spyOn(oldPeerConnection, 'close');

    // Simulate connection loss
    simulateIceConnectionStateChange(oldPeerConnection, 'failed');
    await Promise.resolve();

    // Fast-forward to trigger reconnection
    jest.advanceTimersByTime(2000);
    await Promise.resolve();
    await Promise.resolve();

    // Verify old connection was closed
    expect(closeSpy).toHaveBeenCalled();

    // Verify new connection was created
    const newPeerConnection = client.peerConnections.get('user-b');
    expect(newPeerConnection).toBeDefined();
    expect(newPeerConnection).not.toBe(oldPeerConnection);
  });

  /**
   * Validates: Requirements 7.1, 7.2
   * Test: Connection state change callback is invoked during reconnection
   */
  test('connection state change callback is invoked during reconnection', async () => {
    // Get local media stream
    await client.getLocalMediaStream();

    // Initialize peer connection
    let peerConnection = client.initializePeerConnection('user-b');

    // Clear previous calls
    connectionStateCallback.mockClear();

    // Simulate connection loss via handleConnectionStateChange directly
    peerConnection.connectionState = 'failed';
    client.handleConnectionStateChange('user-b', 'failed');
    await Promise.resolve();

    // Verify callback was invoked with 'failed' state
    expect(connectionStateCallback).toHaveBeenCalledWith('user-b', 'failed');

    // Fast-forward to trigger reconnection
    jest.advanceTimersByTime(2000);
    await Promise.resolve();
    await Promise.resolve();

    // Simulate successful reconnection
    peerConnection = client.peerConnections.get('user-b');
    peerConnection.connectionState = 'connected';
    client.handleConnectionStateChange('user-b', 'connected');
    await Promise.resolve();

    // Verify callback was invoked with 'connected' state
    expect(connectionStateCallback).toHaveBeenCalledWith('user-b', 'connected');
  });

  /**
   * Validates: Requirements 7.1
   * Test: ICE connection state 'completed' also resets reconnection attempts
   */
  test('ICE connection state completed resets reconnection attempts', async () => {
    // Get local media stream
    await client.getLocalMediaStream();

    // Initialize peer connection
    const peerConnection = client.initializePeerConnection('user-b');

    // Simulate connection loss
    simulateIceConnectionStateChange(peerConnection, 'failed');
    await Promise.resolve();

    // Verify reconnection state exists
    expect(client.reconnectionState.has('user-b')).toBe(true);

    // Simulate successful connection with 'completed' state
    simulateIceConnectionStateChange(peerConnection, 'completed');
    await Promise.resolve();

    // Verify reconnection state was cleared
    expect(client.reconnectionState.has('user-b')).toBe(false);
  });

  /**
   * Validates: Requirements 7.1, 7.2
   * Test: Error callback receives correct error details
   */
  test('error callback receives correct error details on max attempts', async () => {
    // Get local media stream
    await client.getLocalMediaStream();

    // Initialize peer connection
    let peerConnection = client.initializePeerConnection('user-b');

    // Simulate connection loss and go through all attempts
    simulateIceConnectionStateChange(peerConnection, 'failed');
    await Promise.resolve();

    for (let i = 1; i <= 3; i++) {
      const delay = Math.pow(2, i) * 1000;
      jest.advanceTimersByTime(delay);
      await Promise.resolve();
      await Promise.resolve();

      if (i < 3) {
        peerConnection = client.peerConnections.get('user-b');
        if (peerConnection) {
          simulateIceConnectionStateChange(peerConnection, 'failed');
          await Promise.resolve();
        }
      }
    }

    // Simulate final failure
    peerConnection = client.peerConnections.get('user-b');
    if (peerConnection) {
      simulateIceConnectionStateChange(peerConnection, 'failed');
      await Promise.resolve();
    }

    // Verify error callback was called with correct parameters
    expect(errorCallback).toHaveBeenCalledWith(
      'reconnection_failed',
      expect.any(Error),
      'user-b'
    );

    // Verify error message
    const errorCall = errorCallback.mock.calls.find(
      call => call[0] === 'reconnection_failed'
    );
    expect(errorCall[1].message).toBe('Max attempts reached');
    expect(errorCall[2]).toBe('user-b');
  });
});
