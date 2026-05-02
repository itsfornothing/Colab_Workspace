/**
 * Unit tests for ErrorHandler class
 */

import ErrorHandler from './ErrorHandler';

describe('ErrorHandler', () => {
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
  });

  describe('handlePeerConnectionError', () => {
    it('should attempt retry on first error', () => {
      const error = new Error('Connection failed');
      const remoteUserId = 'user123';
      const retryCallback = jest.fn();

      const willRetry = errorHandler.handlePeerConnectionError(
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
          userId: remoteUserId,
          severity: 'warning'
        })
      );

      // Fast-forward time to trigger retry
      jest.advanceTimersByTime(1000);
      expect(retryCallback).toHaveBeenCalled();
    });

    it('should use exponential backoff for retries', () => {
      const error = new Error('Connection failed');
      const remoteUserId = 'user123';
      const retryCallback = jest.fn();

      // First retry - 1 second delay
      errorHandler.handlePeerConnectionError(error, remoteUserId, retryCallback);
      expect(mockOnRetry).toHaveBeenCalledWith(
        expect.objectContaining({ delay: 1000 })
      );

      // Second retry - 2 second delay
      errorHandler.handlePeerConnectionError(error, remoteUserId, retryCallback);
      expect(mockOnRetry).toHaveBeenCalledWith(
        expect.objectContaining({ delay: 2000 })
      );

      // Third retry - 4 second delay
      errorHandler.handlePeerConnectionError(error, remoteUserId, retryCallback);
      expect(mockOnRetry).toHaveBeenCalledWith(
        expect.objectContaining({ delay: 4000 })
      );
    });

    it('should stop retrying after max attempts', () => {
      const error = new Error('Connection failed');
      const remoteUserId = 'user123';
      const retryCallback = jest.fn();

      // Exhaust all retry attempts
      errorHandler.handlePeerConnectionError(error, remoteUserId, retryCallback);
      errorHandler.handlePeerConnectionError(error, remoteUserId, retryCallback);
      errorHandler.handlePeerConnectionError(error, remoteUserId, retryCallback);

      // Fourth attempt should fail
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
          userId: remoteUserId
        })
      );
    });

    it('should reset retry attempts', () => {
      const error = new Error('Connection failed');
      const remoteUserId = 'user123';
      const retryCallback = jest.fn();

      // Make some retry attempts
      errorHandler.handlePeerConnectionError(error, remoteUserId, retryCallback);
      errorHandler.handlePeerConnectionError(error, remoteUserId, retryCallback);

      // Reset attempts
      errorHandler.resetRetryAttempts(remoteUserId);

      // Next attempt should be attempt 1 again
      errorHandler.handlePeerConnectionError(error, remoteUserId, retryCallback);
      expect(mockOnRetry).toHaveBeenLastCalledWith(
        expect.objectContaining({ attempt: 1 })
      );
    });
  });

  describe('handleMediaAccessError', () => {
    it('should handle NotAllowedError with permission message', () => {
      const error = new Error('Permission denied');
      error.name = 'NotAllowedError';

      const result = errorHandler.handleMediaAccessError(error);

      expect(result.type).toBe('media_access_error');
      expect(result.message).toContain('access denied');
      expect(result.action).toBe('link');
      expect(result.severity).toBe('error');
      expect(mockOnError).toHaveBeenCalled();
    });

    it('should handle NotFoundError with device not found message', () => {
      const error = new Error('Device not found');
      error.name = 'NotFoundError';

      const result = errorHandler.handleMediaAccessError(error);

      expect(result.message).toContain('No camera or microphone found');
      expect(result.action).toBe('dismiss');
    });

    it('should handle NotReadableError with device in use message', () => {
      const error = new Error('Device in use');
      error.name = 'NotReadableError';

      const result = errorHandler.handleMediaAccessError(error);

      expect(result.message).toContain('already in use');
    });

    it('should handle OverconstrainedError with quality message', () => {
      const error = new Error('Constraints not satisfied');
      error.name = 'OverconstrainedError';

      const result = errorHandler.handleMediaAccessError(error);

      expect(result.message).toContain('does not support');
      expect(result.action).toBe('auto-dismiss');
    });

    it('should handle TypeError with browser support message', () => {
      const error = new TypeError('Not supported');

      const result = errorHandler.handleMediaAccessError(error);

      expect(result.message).toContain('not supported in this browser');
    });

    it('should handle unknown errors with generic message', () => {
      const error = new Error('Unknown error');
      error.name = 'UnknownError';

      const result = errorHandler.handleMediaAccessError(error);

      expect(result.message).toContain('Unable to access');
    });
  });

  describe('handleSignalingError', () => {
    it('should trigger reconnection on signaling error', () => {
      const error = new Error('WebSocket closed');
      const reconnectCallback = jest.fn();

      errorHandler.handleSignalingError(error, reconnectCallback);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'signaling_error',
          severity: 'warning'
        })
      );
      expect(mockOnReconnect).toHaveBeenCalledWith({
        reason: 'signaling_error'
      });

      // Fast-forward time to trigger reconnection
      jest.advanceTimersByTime(2000);
      expect(reconnectCallback).toHaveBeenCalled();
    });
  });

  describe('handleRoomFullError', () => {
    it('should show room full error with max participants', () => {
      const roomId = 'room123';
      const maxParticipants = 8;

      errorHandler.handleRoomFullError(roomId, maxParticipants);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'room_full',
          message: expect.stringContaining('8 participants'),
          severity: 'error',
          roomId
        })
      );
    });
  });

  describe('handleScreenShareError', () => {
    it('should handle NotAllowedError for screen share', () => {
      const error = new Error('Permission denied');
      error.name = 'NotAllowedError';

      const result = errorHandler.handleScreenShareError(error);

      expect(result.type).toBe('screen_share_error');
      expect(result.message).toContain('permission denied');
    });

    it('should handle AbortError for cancelled screen share', () => {
      const error = new Error('User cancelled');
      error.name = 'AbortError';

      const result = errorHandler.handleScreenShareError(error);

      expect(result.message).toContain('cancelled');
      expect(result.action).toBe('auto-dismiss');
    });
  });

  describe('handleQualityDegradation', () => {
    it('should show warning for poor quality', () => {
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
          severity: 'warning',
          userId: remoteUserId,
          metrics: quality
        })
      );
    });

    it('should not show warning for good quality', () => {
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
  });

  describe('handleAudioQualityDegradation', () => {
    it('should show audio quality warning', () => {
      const remoteUserId = 'user123';
      const audioMetrics = {
        jitter: 50,
        packetLoss: 5
      };

      errorHandler.handleAudioQualityDegradation(remoteUserId, audioMetrics);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'audio_quality_degraded',
          severity: 'warning',
          userId: remoteUserId
        })
      );
    });
  });

  describe('handleIceConnectionFailure', () => {
    it('should show ICE connection failure error', () => {
      const remoteUserId = 'user123';

      errorHandler.handleIceConnectionFailure(remoteUserId);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'ice_connection_failed',
          severity: 'error',
          userId: remoteUserId
        })
      );
    });
  });

  describe('handleGeneralError', () => {
    it('should handle ice_candidate_error', () => {
      const error = new Error('ICE error');
      const remoteUserId = 'user123';

      errorHandler.handleGeneralError('ice_candidate_error', error, remoteUserId);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'ice_candidate_error',
          severity: 'warning',
          userId: remoteUserId
        })
      );
    });

    it('should handle unknown error types', () => {
      const error = new Error('Unknown');

      errorHandler.handleGeneralError('unknown_type', error);

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'unknown_type',
          message: expect.stringContaining('unexpected error')
        })
      );
    });
  });

  describe('utility methods', () => {
    it('should clear all retry attempts', () => {
      const error = new Error('Connection failed');
      const retryCallback = jest.fn();

      // Make some retry attempts
      errorHandler.handlePeerConnectionError(error, 'user1', retryCallback);
      errorHandler.handlePeerConnectionError(error, 'user2', retryCallback);

      expect(errorHandler.getRetryAttempts('user1')).toBe(1);
      expect(errorHandler.getRetryAttempts('user2')).toBe(1);

      // Clear all
      errorHandler.clearAllRetries();

      expect(errorHandler.getRetryAttempts('user1')).toBe(0);
      expect(errorHandler.getRetryAttempts('user2')).toBe(0);
    });

    it('should get retry attempts for a user', () => {
      const error = new Error('Connection failed');
      const retryCallback = jest.fn();

      expect(errorHandler.getRetryAttempts('user123')).toBe(0);

      errorHandler.handlePeerConnectionError(error, 'user123', retryCallback);
      expect(errorHandler.getRetryAttempts('user123')).toBe(1);

      errorHandler.handlePeerConnectionError(error, 'user123', retryCallback);
      expect(errorHandler.getRetryAttempts('user123')).toBe(2);
    });
  });
});
