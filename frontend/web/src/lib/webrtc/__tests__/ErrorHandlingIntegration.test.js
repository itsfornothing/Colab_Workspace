/**
 * Integration tests for error handling in WebRTC video calls
 * 
 * Tests the complete error handling flow:
 * - Peer connection error retry logic
 * - Media access error messages
 * - Reconnection attempts
 * - Error UI display
 * 
 * Requirements: 7.1, 7.2, 12.7
 */

import ErrorHandler from '../ErrorHandler';
import { showErrorToast } from '../../../components/calls/ErrorToast';

// Mock the toast library
jest.mock('react-hot-toast', () => {
  const mockToast = jest.fn();
  mockToast.custom = jest.fn();
  mockToast.success = jest.fn();
  mockToast.dismiss = jest.fn();
  return {
    __esModule: true,
    default: mockToast,
  };
});

describe('Error Handling Integration Tests', () => {
  let errorHandler;
  let mockOnError;
  let mockOnRetry;
  let mockOnReconnect;

  beforeEach(() => {
    jest.useFakeTimers();
    mockOnError = jest.fn();
    mockOnRetry = jest.fn();
    mockOnReconnect = jest.fn();

    errorHandler = new ErrorHandler({
      onError: mockOnError,
      onRetry: mockOnRetry,
      onReconnect: mockOnReconnect
    });
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
    jest.clearAllMocks();
  });

  describe('Peer Connection Error Retry Logic (Requirement 7.1)', () => {
    it('should retry peer connection errors up to 3 times with exponential backoff', () => {
      const error = new Error('Peer connection failed');
      const remoteUserId = 'user123';
      const retryCallback = jest.fn();

      // First attempt - should retry with 1 second delay
      let willRetry = errorHandler.handlePeerConnectionError(
        error,
        remoteUserId,
        retryCallback
      );

      expect(willRetry).toBe(true);
      expect(mockOnRetry).toHaveBeenCalledWith({
        userId: remoteUserId,
        attempt: 1,
        maxAttempts: 3,
        delay: 1000
      });
      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'peer_connection_retry',
          message: expect.stringContaining('Retrying... (1/3)'),
          severity: 'warning'
        })
      );

      jest.advanceTimersByTime(1000);
      expect(retryCallback).toHaveBeenCalledTimes(1);

      // Second attempt - should retry with 2 second delay
      willRetry = errorHandler.handlePeerConnectionError(
        error,
        remoteUserId,
        retryCallback
      );

      expect(willRetry).toBe(true);
      expect(mockOnRetry).toHaveBeenCalledWith(
        expect.objectContaining({
          attempt: 2,
          delay: 2000
        })
      );

      jest.advanceTimersByTime(2000);
      expect(retryCallback).toHaveBeenCalledTimes(2);

      // Third attempt - should retry with 4 second delay
      willRetry = errorHandler.handlePeerConnectionError(
        error,
        remoteUserId,
        retryCallback
      );

      expect(willRetry).toBe(true);
      expect(mockOnRetry).toHaveBeenCalledWith(
        expect.objectContaining({
          attempt: 3,
          delay: 4000
        })
      );

      jest.advanceTimersByTime(4000);
      expect(retryCallback).toHaveBeenCalledTimes(3);

      // Fourth attempt - should fail (max retries reached)
      willRetry = errorHandler.handlePeerConnectionError(
        error,
        remoteUserId,
        retryCallback
      );

      expect(willRetry).toBe(false);
      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'peer_connection_failed',
          message: expect.stringContaining('failed after 3 attempts'),
          severity: 'error',
          userId: remoteUserId
        })
      );

      // Should not schedule another retry
      jest.advanceTimersByTime(10000);
      expect(retryCallback).toHaveBeenCalledTimes(3); // Still 3, no new calls
    });

    it('should reset retry attempts after successful connection', () => {
      const error = new Error('Connection failed');
      const remoteUserId = 'user123';
      const retryCallback = jest.fn();

      // Make 2 failed attempts
      errorHandler.handlePeerConnectionError(error, remoteUserId, retryCallback);
      errorHandler.handlePeerConnectionError(error, remoteUserId, retryCallback);

      expect(errorHandler.getRetryAttempts(remoteUserId)).toBe(2);

      // Simulate successful connection
      errorHandler.resetRetryAttempts(remoteUserId);

      expect(errorHandler.getRetryAttempts(remoteUserId)).toBe(0);

      // Next attempt should start from attempt 1 again
      errorHandler.handlePeerConnectionError(error, remoteUserId, retryCallback);
      expect(mockOnRetry).toHaveBeenLastCalledWith(
        expect.objectContaining({ attempt: 1 })
      );
    });

    it('should handle multiple peer connections independently', () => {
      const error = new Error('Connection failed');
      const user1 = 'user1';
      const user2 = 'user2';
      const retryCallback = jest.fn();

      // User 1 - 2 attempts
      errorHandler.handlePeerConnectionError(error, user1, retryCallback);
      errorHandler.handlePeerConnectionError(error, user1, retryCallback);

      // User 2 - 1 attempt
      errorHandler.handlePeerConnectionError(error, user2, retryCallback);

      expect(errorHandler.getRetryAttempts(user1)).toBe(2);
      expect(errorHandler.getRetryAttempts(user2)).toBe(1);

      // Reset user 1
      errorHandler.resetRetryAttempts(user1);

      expect(errorHandler.getRetryAttempts(user1)).toBe(0);
      expect(errorHandler.getRetryAttempts(user2)).toBe(1); // User 2 unaffected
    });
  });

  describe('Media Access Error Messages (Requirement 7.2)', () => {
    it('should display appropriate error for NotAllowedError (permission denied)', () => {
      const error = new Error('Permission denied');
      error.name = 'NotAllowedError';

      const result = errorHandler.handleMediaAccessError(error);

      expect(result).toMatchObject({
        type: 'media_access_error',
        message: expect.stringContaining('access denied'),
        severity: 'error',
        action: 'link',
        actionLabel: 'How to enable',
        errorName: 'NotAllowedError'
      });

      expect(mockOnError).toHaveBeenCalledWith(result);
    });

    it('should display appropriate error for NotFoundError (no device)', () => {
      const error = new Error('Device not found');
      error.name = 'NotFoundError';

      const result = errorHandler.handleMediaAccessError(error);

      expect(result).toMatchObject({
        type: 'media_access_error',
        message: expect.stringContaining('No camera or microphone found'),
        severity: 'error',
        action: 'dismiss',
        errorName: 'NotFoundError'
      });
    });

    it('should display appropriate error for NotReadableError (device in use)', () => {
      const error = new Error('Device in use');
      error.name = 'NotReadableError';

      const result = errorHandler.handleMediaAccessError(error);

      expect(result).toMatchObject({
        type: 'media_access_error',
        message: expect.stringContaining('already in use'),
        severity: 'error',
        errorName: 'NotReadableError'
      });
    });

    it('should display appropriate error for OverconstrainedError (quality not supported)', () => {
      const error = new Error('Constraints not satisfied');
      error.name = 'OverconstrainedError';

      const result = errorHandler.handleMediaAccessError(error);

      expect(result).toMatchObject({
        type: 'media_access_error',
        message: expect.stringContaining('does not support'),
        action: 'auto-dismiss',
        errorName: 'OverconstrainedError'
      });
    });

    it('should display appropriate error for TypeError (browser not supported)', () => {
      const error = new TypeError('Not supported');

      const result = errorHandler.handleMediaAccessError(error);

      expect(result).toMatchObject({
        type: 'media_access_error',
        message: expect.stringContaining('not supported in this browser'),
        severity: 'error',
        errorName: 'TypeError'
      });
    });

    it('should display generic error for unknown error types', () => {
      const error = new Error('Unknown error');
      error.name = 'UnknownError';

      const result = errorHandler.handleMediaAccessError(error);

      expect(result).toMatchObject({
        type: 'media_access_error',
        message: expect.stringContaining('Unable to access'),
        severity: 'error'
      });
    });
  });

  describe('Reconnection Attempts (Requirement 7.1, 7.6)', () => {
    it('should attempt reconnection on signaling error', () => {
      const error = new Error('WebSocket closed');
      const reconnectCallback = jest.fn();

      errorHandler.handleSignalingError(error, reconnectCallback);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'signaling_error',
          message: expect.stringContaining('Connection to call server lost'),
          severity: 'warning',
          action: 'auto-dismiss'
        })
      );

      expect(mockOnReconnect).toHaveBeenCalledWith({
        reason: 'signaling_error'
      });

      // Should attempt reconnection after 2 seconds
      expect(reconnectCallback).not.toHaveBeenCalled();
      jest.advanceTimersByTime(2000);
      expect(reconnectCallback).toHaveBeenCalledTimes(1);
    });

    it('should handle ICE connection failure', () => {
      const remoteUserId = 'user123';

      errorHandler.handleIceConnectionFailure(remoteUserId);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'ice_connection_failed',
          message: expect.stringContaining('Unable to establish direct connection'),
          severity: 'error',
          userId: remoteUserId
        })
      );
    });

    it('should handle room full error', () => {
      const roomId = 'room123';
      const maxParticipants = 8;

      errorHandler.handleRoomFullError(roomId, maxParticipants);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'room_full',
          message: expect.stringContaining('maximum capacity of 8 participants'),
          severity: 'error',
          roomId
        })
      );
    });
  });

  describe('Error UI Display (Requirement 7.2)', () => {
    it('should display connection quality warnings for poor quality', () => {
      const remoteUserId = 'user123';
      const quality = {
        quality: 'poor',
        packetLoss: 10,
        latency: 350,
        bandwidth: 100
      };

      errorHandler.handleQualityDegradation(remoteUserId, quality);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'poor_connection_quality',
          message: expect.stringContaining('Poor connection quality detected'),
          severity: 'warning',
          action: 'auto-dismiss',
          duration: 5000,
          userId: remoteUserId,
          metrics: quality
        })
      );
    });

    it('should not display warnings for good quality', () => {
      const remoteUserId = 'user123';
      const quality = {
        quality: 'good',
        packetLoss: 0,
        latency: 50,
        bandwidth: 1000
      };

      errorHandler.handleQualityDegradation(remoteUserId, quality);

      expect(mockOnError).not.toHaveBeenCalled();
    });

    it('should display audio quality degradation warnings', () => {
      const remoteUserId = 'user123';
      const audioMetrics = {
        jitter: 50,
        packetLoss: 5
      };

      errorHandler.handleAudioQualityDegradation(remoteUserId, audioMetrics);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'audio_quality_degraded',
          message: expect.stringContaining('Audio quality has degraded'),
          severity: 'warning',
          action: 'auto-dismiss',
          userId: remoteUserId,
          metrics: audioMetrics
        })
      );
    });

    it('should display screen share errors', () => {
      const error = new Error('Permission denied');
      error.name = 'NotAllowedError';

      const result = errorHandler.handleScreenShareError(error);

      expect(result).toMatchObject({
        type: 'screen_share_error',
        message: expect.stringContaining('permission denied'),
        severity: 'error',
        action: 'auto-dismiss',
        errorName: 'NotAllowedError'
      });

      expect(mockOnError).toHaveBeenCalledWith(result);
    });

    it('should handle cancelled screen share gracefully', () => {
      const error = new Error('User cancelled');
      error.name = 'AbortError';

      const result = errorHandler.handleScreenShareError(error);

      expect(result).toMatchObject({
        type: 'screen_share_error',
        message: expect.stringContaining('cancelled'),
        action: 'auto-dismiss'
      });
    });
  });

  describe('Complete Error Flow Integration', () => {
    it('should handle complete peer connection failure flow', () => {
      const error = new Error('Connection failed');
      const remoteUserId = 'user123';
      const retryCallback = jest.fn();

      // Simulate 3 failed connection attempts
      for (let i = 0; i < 3; i++) {
        const willRetry = errorHandler.handlePeerConnectionError(
          error,
          remoteUserId,
          retryCallback
        );
        expect(willRetry).toBe(true);
        
        // Verify retry notification
        expect(mockOnError).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'peer_connection_retry',
            severity: 'warning'
          })
        );
        
        // Advance time to trigger retry
        jest.advanceTimersByTime(Math.pow(2, i) * 1000);
      }

      // Fourth attempt should fail permanently
      const willRetry = errorHandler.handlePeerConnectionError(
        error,
        remoteUserId,
        retryCallback
      );

      expect(willRetry).toBe(false);
      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'peer_connection_failed',
          severity: 'error',
          message: expect.stringContaining('failed after 3 attempts')
        })
      );
    });

    it('should handle media access error followed by retry', () => {
      // First, media access fails
      const mediaError = new Error('Permission denied');
      mediaError.name = 'NotAllowedError';

      errorHandler.handleMediaAccessError(mediaError);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'media_access_error',
          message: expect.stringContaining('access denied')
        })
      );

      // User grants permission and retries
      mockOnError.mockClear();

      // Simulate successful connection (no error)
      expect(mockOnError).not.toHaveBeenCalled();
    });

    it('should handle signaling error with automatic reconnection', () => {
      const signalingError = new Error('WebSocket disconnected');
      const reconnectCallback = jest.fn();

      errorHandler.handleSignalingError(signalingError, reconnectCallback);

      // Should show reconnecting message
      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'signaling_error',
          severity: 'warning'
        })
      );

      // Should trigger reconnection callback
      expect(mockOnReconnect).toHaveBeenCalled();

      jest.advanceTimersByTime(2000);
      expect(reconnectCallback).toHaveBeenCalled();
    });

    it('should clear all retry attempts on cleanup', () => {
      const error = new Error('Connection failed');
      const retryCallback = jest.fn();

      // Create retry attempts for multiple users
      errorHandler.handlePeerConnectionError(error, 'user1', retryCallback);
      errorHandler.handlePeerConnectionError(error, 'user2', retryCallback);
      errorHandler.handlePeerConnectionError(error, 'user3', retryCallback);

      expect(errorHandler.getRetryAttempts('user1')).toBe(1);
      expect(errorHandler.getRetryAttempts('user2')).toBe(1);
      expect(errorHandler.getRetryAttempts('user3')).toBe(1);

      // Clear all
      errorHandler.clearAllRetries();

      expect(errorHandler.getRetryAttempts('user1')).toBe(0);
      expect(errorHandler.getRetryAttempts('user2')).toBe(0);
      expect(errorHandler.getRetryAttempts('user3')).toBe(0);
    });
  });

  describe('General Error Handling', () => {
    it('should handle ICE candidate errors', () => {
      const error = new Error('ICE gathering failed');
      const remoteUserId = 'user123';

      errorHandler.handleGeneralError('ice_candidate_error', error, remoteUserId);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'ice_candidate_error',
          message: expect.stringContaining('Network connectivity issue'),
          severity: 'warning',
          userId: remoteUserId
        })
      );
    });

    it('should handle track errors', () => {
      const error = new Error('Track error');

      errorHandler.handleGeneralError('track_error', error);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'track_error',
          message: expect.stringContaining('Media track error'),
          severity: 'warning'
        })
      );
    });

    it('should handle unknown error types with generic message', () => {
      const error = new Error('Something went wrong');

      errorHandler.handleGeneralError('unknown_error_type', error);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'unknown_error_type',
          message: expect.stringContaining('unexpected error'),
          severity: 'warning'
        })
      );
    });
  });
});
