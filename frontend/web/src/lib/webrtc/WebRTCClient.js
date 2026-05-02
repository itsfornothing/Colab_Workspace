/**
 * WebRTC Client for managing peer-to-peer video call connections
 * 
 * This client handles:
 * - Peer connection management (create, close, reconnect)
 * - Media stream management (local/remote video and audio)
 * - Call controls (mute, video toggle, screen share)
 * - Connection quality monitoring
 * - Reconnection logic with exponential backoff
 * - Adaptive quality management
 * - WebRTC stats collection via WebRTCStatsCollector
 */

import WebRTCStatsCollector from './WebRTCStatsCollector.js';

// ICE server configuration
const DEFAULT_ICE_SERVERS = [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' }
];

// Media constraints for HD video
const HD_VIDEO_CONSTRAINTS = {
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true
  },
  video: {
    width: { ideal: 1280 },
    height: { ideal: 720 },
    frameRate: { ideal: 30 }
  }
};

// Reduced quality constraints for bandwidth issues
const REDUCED_VIDEO_CONSTRAINTS = {
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true
  },
  video: {
    width: { ideal: 640 },
    height: { ideal: 480 },
    frameRate: { ideal: 24 }
  }
};

class WebRTCClient {
  /**
   * Create a new WebRTC client
   * @param {string} roomId - The room ID for the call
   * @param {string} userId - The current user's ID
   * @param {Object} signalingChannel - WebSocket channel for signaling
   */
  constructor(roomId, userId, signalingChannel) {
    this.roomId = roomId;
    this.userId = userId;
    this.signalingChannel = signalingChannel;
    
    // Map of peer connections: userId -> RTCPeerConnection
    this.peerConnections = new Map();
    
    // Map of remote streams: userId -> MediaStream
    this.remoteStreams = new Map();
    
    // Local media stream
    this.localStream = null;
    
    // Screen share stream
    this.screenStream = null;
    
    // Original video track (before screen share)
    this.originalVideoTrack = null;
    
    // Reconnection tracking: userId -> { attempts, timeout }
    this.reconnectionState = new Map();
    
    // Connection quality monitoring intervals
    this.qualityMonitors = new Map();

    // Connection state tracking: userId -> state string
    // Possible states: 'new', 'connecting', 'connected', 'failed', 'closed'
    this.connectionStates = new Map();
    
    // Event handlers
    this.onRemoteStream = null;
    this.onRemoteStreamRemoved = null;
    this.onConnectionQualityChange = null;
    this.onConnectionStateChange = null;
    this.onError = null;
    
    // ICE servers configuration
    this.iceServers = DEFAULT_ICE_SERVERS;

    // Stats collector for performance analysis (Requirements 11.3, 11.5)
    this.statsCollector = new WebRTCStatsCollector();
  }

  /**
   * Validate ICE server configuration
   * @param {Array} iceServers - ICE server configurations to validate
   * @returns {boolean} Whether the configuration is valid
   */
  _validateIceServers(iceServers) {
    if (!Array.isArray(iceServers) || iceServers.length === 0) {
      console.warn('Invalid ICE servers: must be a non-empty array');
      return false;
    }

    for (const server of iceServers) {
      const urls = Array.isArray(server.urls) ? server.urls : [server.urls];
      for (const url of urls) {
        if (!url || typeof url !== 'string') {
          console.warn('Invalid ICE server URL:', url);
          return false;
        }
        if (!url.startsWith('stun:') && !url.startsWith('stuns:') &&
            !url.startsWith('turn:') && !url.startsWith('turns:')) {
          console.warn('Invalid ICE server URL scheme:', url);
          return false;
        }
        // TURN servers require credentials
        if ((url.startsWith('turn:') || url.startsWith('turns:')) &&
            (!server.username || !server.credential)) {
          console.warn('TURN server missing credentials:', url);
          return false;
        }
      }
    }
    return true;
  }

  /**
   * Set ICE servers configuration
   * @param {Array} iceServers - Array of ICE server configurations
   */
  setIceServers(iceServers) {
    if (this._validateIceServers(iceServers)) {
      this.iceServers = iceServers;
    } else {
      console.warn('Invalid ICE server configuration, using defaults');
      this.iceServers = DEFAULT_ICE_SERVERS;
    }
  }

  /**
   * Initialize a peer connection with a remote user
   *
   * Security note (Requirement 10.1 — DTLS-SRTP):
   * All media transmitted through this peer connection is automatically
   * encrypted using DTLS-SRTP as mandated by the WebRTC specification
   * (RFC 8827). This is enforced by the browser's WebRTC implementation
   * and requires no additional application-level configuration.
   *
   * @param {string} remoteUserId - The remote user's ID
   * @returns {RTCPeerConnection} The created peer connection
   */
  initializePeerConnection(remoteUserId) {
    // Close existing connection if any, preserving reconnection state
    if (this.peerConnections.has(remoteUserId)) {
      // Save reconnection state before closing (closePeerConnection clears it)
      const savedReconnection = this.reconnectionState.get(remoteUserId);
      this.closePeerConnection(remoteUserId);
      // Restore reconnection state so attempt count is preserved across reconnections
      if (savedReconnection) {
        this.reconnectionState.set(remoteUserId, savedReconnection);
      }
    }

    const config = {
      iceServers: this.iceServers,
      iceTransportPolicy: 'all'
    };

    const peerConnection = new RTCPeerConnection(config);

    // Add local stream tracks to peer connection
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => {
        peerConnection.addTrack(track, this.localStream);
      });
    }

    // Handle ICE candidates
    peerConnection.onicecandidate = (event) => {
      if (event.candidate) {
        this.signalingChannel.send({
          type: 'webrtc_ice',
          from_user_id: this.userId,
          to_user_id: remoteUserId,
          room_id: this.roomId,
          candidate: event.candidate.toJSON()
        });
      }
    };

    // Handle remote stream
    peerConnection.ontrack = (event) => {
      const [remoteStream] = event.streams;
      this.remoteStreams.set(remoteUserId, remoteStream);
      
      if (this.onRemoteStream) {
        this.onRemoteStream(remoteUserId, remoteStream);
      }
    };

    // Handle connection state changes
    peerConnection.onconnectionstatechange = () => {
      this.handleConnectionStateChange(remoteUserId, peerConnection.connectionState);
    };

    // Handle ICE connection state changes
    peerConnection.oniceconnectionstatechange = () => {
      const state = peerConnection.iceConnectionState;
      
      if (state === 'failed' || state === 'disconnected') {
        // Attempt reconnection
        this.attemptReconnection(remoteUserId);
      } else if (state === 'connected' || state === 'completed') {
        // Reset reconnection attempts on successful connection
        this.reconnectionState.delete(remoteUserId);
        
        // Start monitoring connection quality
        this.monitorConnectionQuality(remoteUserId);
      }
    };

    this.peerConnections.set(remoteUserId, peerConnection);
    this.connectionStates.set(remoteUserId, 'new');
    return peerConnection;
  }

  /**
   * Create an offer for a remote peer
   * @param {string} remoteUserId - The remote user's ID
   */
  async createOffer(remoteUserId) {
    try {
      const peerConnection = this.peerConnections.get(remoteUserId) || 
                            this.initializePeerConnection(remoteUserId);

      const offer = await peerConnection.createOffer({
        offerToReceiveAudio: true,
        offerToReceiveVideo: true
      });

      await peerConnection.setLocalDescription(offer);

      this.signalingChannel.send({
        type: 'webrtc_offer',
        from_user_id: this.userId,
        to_user_id: remoteUserId,
        room_id: this.roomId,
        sdp: offer
      });
    } catch (error) {
      console.error(`Error creating offer for ${remoteUserId}:`, error);
      if (this.onError) {
        this.onError('peer_connection_error', error, remoteUserId);
      }
    }
  }

  /**
   * Handle an answer from a remote peer
   * @param {string} remoteUserId - The remote user's ID
   * @param {RTCSessionDescriptionInit} answer - The answer SDP
   */
  async handleAnswer(remoteUserId, answer) {
    try {
      const peerConnection = this.peerConnections.get(remoteUserId);
      
      if (!peerConnection) {
        console.error(`No peer connection found for ${remoteUserId}`);
        return;
      }

      await peerConnection.setRemoteDescription(new RTCSessionDescription(answer));
    } catch (error) {
      console.error(`Error handling answer from ${remoteUserId}:`, error);
      if (this.onError) {
        this.onError('peer_connection_error', error, remoteUserId);
      }
    }
  }

  /**
   * Handle an offer from a remote peer
   * @param {string} remoteUserId - The remote user's ID
   * @param {RTCSessionDescriptionInit} offer - The offer SDP
   */
  async handleOffer(remoteUserId, offer) {
    try {
      const peerConnection = this.peerConnections.get(remoteUserId) || 
                            this.initializePeerConnection(remoteUserId);

      await peerConnection.setRemoteDescription(new RTCSessionDescription(offer));

      const answer = await peerConnection.createAnswer();
      await peerConnection.setLocalDescription(answer);

      this.signalingChannel.send({
        type: 'webrtc_answer',
        from_user_id: this.userId,
        to_user_id: remoteUserId,
        room_id: this.roomId,
        sdp: answer
      });
    } catch (error) {
      console.error(`Error handling offer from ${remoteUserId}:`, error);
      if (this.onError) {
        this.onError('peer_connection_error', error, remoteUserId);
      }
    }
  }

  /**
   * Handle an ICE candidate from a remote peer
   * @param {string} remoteUserId - The remote user's ID
   * @param {RTCIceCandidateInit} candidate - The ICE candidate
   */
  async handleIceCandidate(remoteUserId, candidate) {
    try {
      const peerConnection = this.peerConnections.get(remoteUserId);
      
      if (!peerConnection) {
        console.error(`No peer connection found for ${remoteUserId}`);
        return;
      }

      await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
    } catch (error) {
      console.error(`Error adding ICE candidate from ${remoteUserId}:`, error);
      if (this.onError) {
        this.onError('ice_candidate_error', error, remoteUserId);
      }
    }
  }

  /**
   * Close peer connection with a remote user
   * @param {string} remoteUserId - The remote user's ID
   */
  closePeerConnection(remoteUserId) {
    const peerConnection = this.peerConnections.get(remoteUserId);
    
    if (peerConnection) {
      peerConnection.close();
      this.peerConnections.delete(remoteUserId);
    }

    // Update connection state
    this.connectionStates.set(remoteUserId, 'closed');

    // Stop quality monitoring
    const monitor = this.qualityMonitors.get(remoteUserId);
    if (monitor) {
      clearInterval(monitor);
      this.qualityMonitors.delete(remoteUserId);
    }

    // Clear reconnection state
    const reconnection = this.reconnectionState.get(remoteUserId);
    if (reconnection && reconnection.timeout) {
      clearTimeout(reconnection.timeout);
    }
    this.reconnectionState.delete(remoteUserId);

    // Remove remote stream
    this.remoteStreams.delete(remoteUserId);
    
    if (this.onRemoteStreamRemoved) {
      this.onRemoteStreamRemoved(remoteUserId);
    }
  }

  /**
   * Get local media stream (camera and microphone)
   * @param {MediaStreamConstraints} constraints - Media constraints
   * @returns {Promise<MediaStream>} The local media stream
   */
  async getLocalMediaStream(constraints = HD_VIDEO_CONSTRAINTS) {
    try {
      this.localStream = await navigator.mediaDevices.getUserMedia(constraints);
      return this.localStream;
    } catch (error) {
      console.error('Error accessing media devices:', error);
      
      if (this.onError) {
        let errorType = 'media_access_error';
        
        if (error.name === 'NotAllowedError') {
          errorType = 'media_permission_denied';
        } else if (error.name === 'NotFoundError') {
          errorType = 'media_device_not_found';
        }
        
        this.onError(errorType, error);
      }
      
      throw error;
    }
  }

  /**
   * Attach local stream to existing peer connections
   * @param {MediaStream} stream - The local media stream
   */
  attachLocalStream(stream) {
    this.localStream = stream;
    
    // Add tracks to all existing peer connections
    this.peerConnections.forEach((peerConnection) => {
      stream.getTracks().forEach(track => {
        peerConnection.addTrack(track, stream);
      });
    });
  }

  /**
   * Attach remote stream (handled automatically via ontrack event)
   * @param {string} remoteUserId - The remote user's ID
   * @param {MediaStream} stream - The remote media stream
   */
  attachRemoteStream(remoteUserId, stream) {
    this.remoteStreams.set(remoteUserId, stream);
  }

  /**
   * Release all media streams and close connections
   */
  releaseMediaStreams() {
    // Stop local stream
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => track.stop());
      this.localStream = null;
    }

    // Stop screen stream
    if (this.screenStream) {
      this.screenStream.getTracks().forEach(track => track.stop());
      this.screenStream = null;
    }

    // Close all peer connections
    this.peerConnections.forEach((_, remoteUserId) => {
      this.closePeerConnection(remoteUserId);
    });

    // Clear all maps
    this.peerConnections.clear();
    this.remoteStreams.clear();
    this.qualityMonitors.clear();
    this.reconnectionState.clear();
  }

  /**
   * Toggle audio (mute/unmute)
   * @param {boolean} enabled - Whether audio should be enabled
   */
  toggleAudio(enabled) {
    if (!this.localStream) return;

    const audioTracks = this.localStream.getAudioTracks();
    audioTracks.forEach(track => {
      track.enabled = enabled;
    });
  }

  /**
   * Toggle video (enable/disable camera)
   * @param {boolean} enabled - Whether video should be enabled
   */
  toggleVideo(enabled) {
    if (!this.localStream) return;

    const videoTracks = this.localStream.getVideoTracks();
    videoTracks.forEach(track => {
      track.enabled = enabled;
    });
  }

  /**
   * Start screen sharing
   * @returns {Promise<MediaStream>} The screen share stream
   */
  async startScreenShare() {
    try {
      this.screenStream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          cursor: 'always'
        },
        audio: false
      });

      // Save original video track
      const videoTrack = this.localStream?.getVideoTracks()[0];
      if (videoTrack) {
        this.originalVideoTrack = videoTrack;
      }

      // Replace video track in all peer connections
      const screenTrack = this.screenStream.getVideoTracks()[0];
      
      this.peerConnections.forEach((peerConnection) => {
        const senders = peerConnection.getSenders();
        const videoSender = senders.find(sender => 
          sender.track && sender.track.kind === 'video'
        );
        
        if (videoSender) {
          videoSender.replaceTrack(screenTrack);
        }
      });

      // Handle screen share stop (user clicks browser's stop sharing button)
      screenTrack.onended = () => {
        this.stopScreenShare();
      };

      return this.screenStream;
    } catch (error) {
      console.error('Error starting screen share:', error);
      
      if (this.onError) {
        let errorType = 'screen_share_error';
        
        if (error.name === 'NotAllowedError') {
          errorType = 'screen_share_permission_denied';
        }
        
        this.onError(errorType, error);
      }
      
      throw error;
    }
  }

  /**
   * Stop screen sharing and restore camera
   */
  stopScreenShare() {
    if (!this.screenStream) return;

    // Null out screenStream first to prevent re-entrant calls via track.onended
    const streamToStop = this.screenStream;
    this.screenStream = null;

    // Stop screen stream
    streamToStop.getTracks().forEach(track => track.stop());

    // Restore original video track
    if (this.originalVideoTrack) {
      this.peerConnections.forEach((peerConnection) => {
        const senders = peerConnection.getSenders();
        const videoSender = senders.find(sender => 
          sender.track && sender.track.kind === 'video'
        );
        
        if (videoSender) {
          videoSender.replaceTrack(this.originalVideoTrack);
        }
      });
      
      this.originalVideoTrack = null;
    }
  }

  /**
   * Monitor connection quality for a peer
   * @param {string} remoteUserId - The remote user's ID
   */
  monitorConnectionQuality(remoteUserId) {
    // Clear existing monitor
    const existingMonitor = this.qualityMonitors.get(remoteUserId);
    if (existingMonitor) {
      clearInterval(existingMonitor);
    }

    // Monitor every 2 seconds
    const monitor = setInterval(async () => {
      const peerConnection = this.peerConnections.get(remoteUserId);
      
      if (!peerConnection) {
        clearInterval(monitor);
        this.qualityMonitors.delete(remoteUserId);
        return;
      }

      try {
        const stats = await peerConnection.getStats();
        const quality = this.calculateConnectionQuality(stats);
        
        if (this.onConnectionQualityChange) {
          this.onConnectionQualityChange(remoteUserId, quality);
        }

        // Collect detailed stats for performance analysis (Requirements 11.3, 11.5)
        // Run asynchronously so it does not block the quality callback
        this.statsCollector.collectStats(remoteUserId, peerConnection).catch((err) => {
          console.error(`[WebRTCClient] Stats collection failed for ${remoteUserId}:`, err);
        });
      } catch (error) {
        console.error(`Error monitoring quality for ${remoteUserId}:`, error);
      }
    }, 2000);

    this.qualityMonitors.set(remoteUserId, monitor);
  }

  /**
   * Calculate connection quality from WebRTC stats
   * @param {RTCStatsReport} stats - WebRTC stats
   * @returns {Object} Connection quality metrics
   */
  calculateConnectionQuality(stats) {
    let packetLoss = 0;
    let latency = 0;
    let bandwidth = 0;
    let quality = 'good';

    stats.forEach(report => {
      if (report.type === 'inbound-rtp' && report.kind === 'video') {
        // Calculate packet loss
        if (report.packetsLost && report.packetsReceived) {
          const totalPackets = report.packetsLost + report.packetsReceived;
          packetLoss = (report.packetsLost / totalPackets) * 100;
        }

        // Get bandwidth
        if (report.bytesReceived && report.timestamp) {
          bandwidth = report.bytesReceived * 8 / 1000; // kbps
        }
      }

      if (report.type === 'candidate-pair' && report.state === 'succeeded') {
        // Get latency (RTT)
        if (report.currentRoundTripTime) {
          latency = report.currentRoundTripTime * 1000; // ms
        }
      }
    });

    // Determine quality level
    if (packetLoss > 5 || latency > 300) {
      quality = 'poor';
    } else if (packetLoss > 2 || latency > 150) {
      quality = 'fair';
    }

    return {
      quality,
      packetLoss: Math.round(packetLoss * 100) / 100,
      latency: Math.round(latency),
      bandwidth: Math.round(bandwidth)
    };
  }

  /**
   * Handle connection state changes
   * @param {string} remoteUserId - The remote user's ID
   * @param {string} state - The connection state
   */
  handleConnectionStateChange(remoteUserId, state) {
    console.log(`Connection state for ${remoteUserId}: ${state}`);

    // Track the connection state
    this.connectionStates.set(remoteUserId, state);
    
    if (this.onConnectionStateChange) {
      this.onConnectionStateChange(remoteUserId, state);
    }

    if (state === 'failed') {
      this.attemptReconnection(remoteUserId);
    }
  }

  /**
   * Attempt to reconnect to a peer
   * @param {string} remoteUserId - The remote user's ID
   * @param {number} maxAttempts - Maximum reconnection attempts (default: 3)
   */
  async attemptReconnection(remoteUserId, maxAttempts = 3) {
    let reconnection = this.reconnectionState.get(remoteUserId);
    
    if (!reconnection) {
      reconnection = { attempts: 0, timeout: null };
      this.reconnectionState.set(remoteUserId, reconnection);
    }

    if (reconnection.attempts >= maxAttempts) {
      console.error(`Max reconnection attempts reached for ${remoteUserId}`);
      
      if (this.onError) {
        this.onError('reconnection_failed', new Error('Max attempts reached'), remoteUserId);
      }
      
      this.closePeerConnection(remoteUserId);
      return;
    }

    reconnection.attempts++;
    
    // Exponential backoff: 2^attempts seconds
    const delay = Math.pow(2, reconnection.attempts) * 1000;
    
    console.log(`Reconnection attempt ${reconnection.attempts} for ${remoteUserId} in ${delay}ms`);

    reconnection.timeout = setTimeout(async () => {
      try {
        // Close existing connection
        const oldConnection = this.peerConnections.get(remoteUserId);
        if (oldConnection) {
          oldConnection.close();
        }

        // Create new connection and offer
        this.initializePeerConnection(remoteUserId);
        await this.createOffer(remoteUserId);
      } catch (error) {
        console.error(`Reconnection error for ${remoteUserId}:`, error);
        
        // Try again
        this.attemptReconnection(remoteUserId, maxAttempts);
      }
    }, delay);
  }

  /**
   * Reduce video quality due to bandwidth constraints
   */
  async reduceVideoQuality() {
    try {
      // Get new stream with reduced constraints
      const reducedStream = await navigator.mediaDevices.getUserMedia(REDUCED_VIDEO_CONSTRAINTS);
      
      // Replace video track in all peer connections
      const newVideoTrack = reducedStream.getVideoTracks()[0];
      
      this.peerConnections.forEach((peerConnection) => {
        const senders = peerConnection.getSenders();
        const videoSender = senders.find(sender => 
          sender.track && sender.track.kind === 'video'
        );
        
        if (videoSender) {
          videoSender.replaceTrack(newVideoTrack);
        }
      });

      // Stop old video track
      if (this.localStream) {
        const oldVideoTrack = this.localStream.getVideoTracks()[0];
        if (oldVideoTrack) {
          oldVideoTrack.stop();
        }
        
        // Replace track in local stream
        this.localStream.removeTrack(oldVideoTrack);
        this.localStream.addTrack(newVideoTrack);
      }

      console.log('Video quality reduced due to bandwidth constraints');
    } catch (error) {
      console.error('Error reducing video quality:', error);
    }
  }

  /**
   * Join a room with existing participants, establishing connections sequentially.
   * Sequential (not parallel) connection establishment avoids overwhelming the
   * signaling server.
   * @param {string[]} existingParticipantIds - Array of existing participant user IDs
   */
  async joinRoom(existingParticipantIds) {
    if (!existingParticipantIds || existingParticipantIds.length === 0) {
      console.log('joinRoom: no existing participants to connect to');
      return;
    }

    console.log(`joinRoom: establishing connections with ${existingParticipantIds.length} participant(s)`);

    for (const participantId of existingParticipantIds) {
      // Skip peers that already have an active (non-failed, non-closed) connection
      const existingState = this.connectionStates.get(participantId);
      if (this.peerConnections.has(participantId) &&
          existingState !== 'failed' && existingState !== 'closed') {
        console.log(`joinRoom: skipping ${participantId} — already connected (state: ${existingState})`);
        continue;
      }

      console.log(`joinRoom: creating offer for ${participantId}`);
      await this.createOffer(participantId);
    }

    console.log('joinRoom: all connections established');
  }

  /**
   * Handle a new participant joining the call.
   * Called by existing participants when they receive a user_joined signaling event.
   * @param {string} newParticipantId - The new participant's user ID
   */
  async participantJoined(newParticipantId) {
    console.log(`participantJoined: creating offer for new participant ${newParticipantId}`);
    await this.createOffer(newParticipantId);
  }

  /**
   * Handle a participant leaving the call.
   * Closes only that participant's connection, leaving all others intact.
   * @param {string} departedParticipantId - The departed participant's user ID
   */
  participantLeft(departedParticipantId) {
    console.log(`participantLeft: closing connection for ${departedParticipantId}`);
    this.closePeerConnection(departedParticipantId);
  }

  /**
   * Get the tracked connection state for a given peer.
   * @param {string} remoteUserId - The remote user's ID
   * @returns {string|undefined} The connection state, or undefined if not tracked
   */
  getConnectionState(remoteUserId) {
    return this.connectionStates.get(remoteUserId);
  }

  /**
   * Get the count of peers with 'connected' or 'completed' ICE connection state.
   * @returns {number} Number of connected peers
   */
  getConnectedPeerCount() {
    let count = 0;
    this.peerConnections.forEach((peerConnection) => {
      const state = peerConnection.iceConnectionState;
      if (state === 'connected' || state === 'completed') {
        count++;
      }
    });
    return count;
  }

  /**
   * Check if screen sharing is active
   * @returns {boolean} Whether screen sharing is active
   */
  isScreenSharing() {
    return this.screenStream !== null;
  }

  /**
   * Get all active peer connections
   * @returns {Map<string, RTCPeerConnection>} Map of peer connections
   */
  getPeerConnections() {
    return this.peerConnections;
  }

  /**
   * Get remote stream for a user
   * @param {string} remoteUserId - The remote user's ID
   * @returns {MediaStream|null} The remote stream or null
   */
  getRemoteStream(remoteUserId) {
    return this.remoteStreams.get(remoteUserId) || null;
  }

  /**
   * Get the WebRTCStatsCollector instance for external access.
   * @returns {WebRTCStatsCollector}
   */
  getStatsCollector() {
    return this.statsCollector;
  }

  /**
   * Log a performance report for all currently connected peers.
   * Delegates to statsCollector.logStatsReport() for each peer.
   */
  logPerformanceReport() {
    if (this.peerConnections.size === 0) {
      console.log('[WebRTCClient] logPerformanceReport: no connected peers');
      return;
    }
    this.peerConnections.forEach((_, remoteUserId) => {
      this.statsCollector.logStatsReport(remoteUserId);
    });
  }
}

export default WebRTCClient;
