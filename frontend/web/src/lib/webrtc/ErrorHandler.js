/**
 * ErrorHandler for WebRTC video calls
 * 
 * Handles various error scenarios:
 * - Peer connection errors with retry logic
 * - Media access errors with user-friendly messages
 * - Signaling errors with reconnection
 * - Room full errors with notifications
 */

class ErrorHandler {
  /**
   * Create a new ErrorHandler
   * @param {Object} options - Configuration options
   * @param {Function} options.onError - Callback for error notifications
   * @param {Function} options.onRetry - Callback when retry is attempted
   * @param {Function} options.onReconnect - Callback when reconnection is attempted
   */
  constructor(options = {}) {
    this.onError = options.onError || (() => {});
    this.onRetry = options.onRetry || (() => {});
    this.onReconnect = options.onReconnect || (() => {});
    
    // Track retry attempts per peer
    this.retryAttempts = new Map();
    
    // Maximum retry attempts
    this.maxRetries = 3;
    
    // Exponential backoff base (in milliseconds)
    this.backoffBase = 1000;
  }

  /**
   * Handle peer connection errors with retry logic
   * @param {Error} error - The error object
   * @param {string} remoteUserId - The remote user's ID
   * @param {Function} retryCallback - Function to call for retry
   * @returns {boolean} Whether retry will be attempted
   */
  handlePeerConnectionError(error, remoteUserId, retryCallback) {
    console.error(`Peer connection error with ${remoteUserId}:`, error);
    
    // Get current retry count
    const attempts = this.retryAttempts.get(remoteUserId) || 0;
    
    if (attempts >= this.maxRetries) {
      // Max retries reached
      this.retryAttempts.delete(remoteUserId);
      
      this.onError({
        type: 'peer_connection_failed',
        message: `Unable to connect to user. Connection failed after ${this.maxRetries} attempts.`,
        userId: remoteUserId,
        severity: 'error',
        action: 'dismiss'
      });
      
      return false;
    }
    
    // Increment retry count
    this.retryAttempts.set(remoteUserId, attempts + 1);
    
    // Calculate exponential backoff delay
    const delay = this.backoffBase * Math.pow(2, attempts);
    
    // Notify about retry
    this.onRetry({
      userId: remoteUserId,
      attempt: attempts + 1,
      maxAttempts: this.maxRetries,
      delay
    });
    
    this.onError({
      type: 'peer_connection_retry',
      message: `Connection issue detected. Retrying... (${attempts + 1}/${this.maxRetries})`,
      userId: remoteUserId,
      severity: 'warning',
      action: 'auto-dismiss',
      duration: delay
    });
    
    // Schedule retry
    setTimeout(() => {
      if (retryCallback) {
        retryCallback();
      }
    }, delay);
    
    return true;
  }

  /**
   * Reset retry attempts for a user (call when connection succeeds)
   * @param {string} remoteUserId - The remote user's ID
   */
  resetRetryAttempts(remoteUserId) {
    this.retryAttempts.delete(remoteUserId);
  }

  /**
   * Handle media access errors with user-friendly messages
   * @param {Error} error - The error object
   * @returns {Object} Error notification object
   */
  handleMediaAccessError(error) {
    console.error('Media access error:', error);
    
    let message = 'Unable to access camera or microphone.';
    let action = 'dismiss';
    let actionLabel = null;
    
    if (error.name === 'NotAllowedError') {
      message = 'Camera and microphone access denied. Please grant permissions in your browser settings and try again.';
      action = 'link';
      actionLabel = 'How to enable';
    } else if (error.name === 'NotFoundError') {
      message = 'No camera or microphone found. Please connect a device and try again.';
    } else if (error.name === 'NotReadableError') {
      message = 'Camera or microphone is already in use by another application. Please close other apps and try again.';
    } else if (error.name === 'OverconstrainedError') {
      message = 'Your camera does not support the required video quality. Trying with lower quality...';
      action = 'auto-dismiss';
    } else if (error.name === 'TypeError') {
      message = 'Media devices are not supported in this browser. Please use a modern browser like Chrome, Firefox, or Safari.';
    }
    
    const errorNotification = {
      type: 'media_access_error',
      message,
      severity: 'error',
      action,
      actionLabel,
      errorName: error.name
    };
    
    this.onError(errorNotification);
    
    return errorNotification;
  }

  /**
   * Handle signaling errors with reconnection
   * @param {Error} error - The error object
   * @param {Function} reconnectCallback - Function to call for reconnection
   */
  handleSignalingError(error, reconnectCallback) {
    console.error('Signaling error:', error);
    
    this.onError({
      type: 'signaling_error',
      message: 'Connection to call server lost. Attempting to reconnect...',
      severity: 'warning',
      action: 'auto-dismiss'
    });
    
    // Notify about reconnection attempt
    this.onReconnect({
      reason: 'signaling_error'
    });
    
    // Attempt reconnection
    if (reconnectCallback) {
      setTimeout(() => {
        reconnectCallback();
      }, 2000);
    }
  }

  /**
   * Handle room full error with notification
   * @param {string} roomId - The room ID
   * @param {number} maxParticipants - Maximum number of participants
   */
  handleRoomFullError(roomId, maxParticipants = 8) {
    console.error(`Room ${roomId} is full`);
    
    this.onError({
      type: 'room_full',
      message: `This call has reached its maximum capacity of ${maxParticipants} participants. Please try again later.`,
      severity: 'error',
      action: 'dismiss',
      roomId
    });
  }

  /**
   * Handle screen share errors
   * @param {Error} error - The error object
   * @returns {Object} Error notification object
   */
  handleScreenShareError(error) {
    console.error('Screen share error:', error);
    
    let message = 'Unable to start screen sharing.';
    
    if (error.name === 'NotAllowedError') {
      message = 'Screen sharing permission denied. Please allow screen sharing and try again.';
    } else if (error.name === 'NotFoundError') {
      message = 'No screen available to share.';
    } else if (error.name === 'AbortError') {
      message = 'Screen sharing was cancelled.';
    }
    
    const errorNotification = {
      type: 'screen_share_error',
      message,
      severity: 'error',
      action: 'auto-dismiss',
      errorName: error.name
    };
    
    this.onError(errorNotification);
    
    return errorNotification;
  }

  /**
   * Handle network quality degradation
   * @param {string} remoteUserId - The remote user's ID
   * @param {Object} quality - Quality metrics
   */
  handleQualityDegradation(remoteUserId, quality) {
    if (quality.quality === 'poor') {
      this.onError({
        type: 'poor_connection_quality',
        message: `Poor connection quality detected. Video quality may be reduced.`,
        severity: 'warning',
        action: 'auto-dismiss',
        duration: 5000,
        userId: remoteUserId,
        metrics: quality
      });
    }
  }

  /**
   * Handle audio quality degradation
   * @param {string} remoteUserId - The remote user's ID
   * @param {Object} audioMetrics - Audio quality metrics
   */
  handleAudioQualityDegradation(remoteUserId, audioMetrics) {
    this.onError({
      type: 'audio_quality_degraded',
      message: 'Audio quality has degraded. You may experience choppy audio.',
      severity: 'warning',
      action: 'auto-dismiss',
      duration: 5000,
      userId: remoteUserId,
      metrics: audioMetrics
    });
  }

  /**
   * Handle ICE connection failure
   * @param {string} remoteUserId - The remote user's ID
   */
  handleIceConnectionFailure(remoteUserId) {
    this.onError({
      type: 'ice_connection_failed',
      message: 'Unable to establish direct connection. This may be due to firewall or network restrictions.',
      severity: 'error',
      action: 'dismiss',
      userId: remoteUserId
    });
  }

  /**
   * Handle general WebRTC errors
   * @param {string} errorType - Type of error
   * @param {Error} error - The error object
   * @param {string} remoteUserId - The remote user's ID (optional)
   */
  handleGeneralError(errorType, error, remoteUserId = null) {
    console.error(`WebRTC error (${errorType}):`, error);
    
    const errorMessages = {
      'ice_candidate_error': 'Network connectivity issue detected.',
      'track_error': 'Media track error occurred.',
      'data_channel_error': 'Data channel error occurred.',
      'unknown': 'An unexpected error occurred.'
    };
    
    this.onError({
      type: errorType,
      message: errorMessages[errorType] || errorMessages['unknown'],
      severity: 'warning',
      action: 'auto-dismiss',
      userId: remoteUserId
    });
  }

  /**
   * Clear all retry attempts
   */
  clearAllRetries() {
    this.retryAttempts.clear();
  }

  /**
   * Get retry attempts for a user
   * @param {string} remoteUserId - The remote user's ID
   * @returns {number} Number of retry attempts
   */
  getRetryAttempts(remoteUserId) {
    return this.retryAttempts.get(remoteUserId) || 0;
  }
}

export default ErrorHandler;
