/**
 * WebRTC Mocking Infrastructure for E2E Tests
 * 
 * This module provides comprehensive mocks for WebRTC APIs to enable
 * automated end-to-end testing of video call functionality.
 * 
 * Mocked APIs:
 * - RTCPeerConnection
 * - navigator.mediaDevices.getUserMedia
 * - navigator.mediaDevices.getDisplayMedia
 * - MediaStream
 * - MediaStreamTrack
 * 
 * Requirements: 12.8
 */

/**
 * Mock MediaStreamTrack
 * Simulates audio/video tracks with enable/disable and stop functionality
 */
class MockMediaStreamTrack {
  constructor(kind = 'video', id = null) {
    this.kind = kind; // 'audio' or 'video'
    this.id = id || `mock-${kind}-track-${Math.random().toString(36).substr(2, 9)}`;
    this.label = `Mock ${kind} track`;
    this.enabled = true;
    this.muted = false;
    this.readyState = 'live';
    this.onended = null;
    this.onmute = null;
    this.onunmute = null;
    this._stopped = false;
  }

  stop() {
    this._stopped = true;
    this.readyState = 'ended';
    if (this.onended) {
      this.onended();
    }
  }

  clone() {
    const cloned = new MockMediaStreamTrack(this.kind);
    cloned.enabled = this.enabled;
    return cloned;
  }

  getSettings() {
    return {
      deviceId: this.id,
      groupId: 'mock-group',
      aspectRatio: this.kind === 'video' ? 1.777 : undefined,
      frameRate: this.kind === 'video' ? 30 : undefined,
      width: this.kind === 'video' ? 1280 : undefined,
      height: this.kind === 'video' ? 720 : undefined,
      sampleRate: this.kind === 'audio' ? 48000 : undefined,
      channelCount: this.kind === 'audio' ? 2 : undefined,
    };
  }

  getCapabilities() {
    return {
      deviceId: this.id,
      groupId: 'mock-group',
    };
  }

  getConstraints() {
    return {};
  }

  applyConstraints(constraints) {
    return Promise.resolve();
  }
}

/**
 * Mock MediaStream
 * Simulates a media stream with audio and video tracks
 */
class MockMediaStream {
  constructor(tracks = null) {
    this.id = `mock-stream-${Math.random().toString(36).substr(2, 9)}`;
    // When no tracks argument is provided (null), create default video+audio tracks.
    // When an explicit array is provided (even empty), use it as-is.
    this._tracks = tracks === null
      ? [new MockMediaStreamTrack('video'), new MockMediaStreamTrack('audio')]
      : [...tracks];
    this.active = true;
    this.onaddtrack = null;
    this.onremovetrack = null;
  }

  getTracks() {
    return [...this._tracks];
  }

  getVideoTracks() {
    return this._tracks.filter(track => track.kind === 'video');
  }

  getAudioTracks() {
    return this._tracks.filter(track => track.kind === 'audio');
  }

  getTrackById(trackId) {
    return this._tracks.find(track => track.id === trackId) || null;
  }

  addTrack(track) {
    if (!this._tracks.find(t => t.id === track.id)) {
      this._tracks.push(track);
      if (this.onaddtrack) {
        this.onaddtrack({ track });
      }
    }
  }

  removeTrack(track) {
    const index = this._tracks.findIndex(t => t.id === track.id);
    if (index !== -1) {
      this._tracks.splice(index, 1);
      if (this.onremovetrack) {
        this.onremovetrack({ track });
      }
    }
  }

  clone() {
    const clonedTracks = this._tracks.map(track => track.clone());
    return new MockMediaStream(clonedTracks);
  }
}

/**
 * Mock RTCPeerConnection
 * Simulates WebRTC peer connection with full signaling support
 */
class MockRTCPeerConnection {
  constructor(config) {
    this.config = config;
    this.localDescription = null;
    this.remoteDescription = null;
    this.signalingState = 'stable';
    this.iceConnectionState = 'new';
    this.connectionState = 'new';
    this.iceGatheringState = 'new';
    
    // Event handlers
    this.onicecandidate = null;
    this.ontrack = null;
    this.onconnectionstatechange = null;
    this.oniceconnectionstatechange = null;
    this.onsignalingstatechange = null;
    this.onicegatheringstatechange = null;
    this.ondatachannel = null;
    this.onnegotiationneeded = null;
    
    // Internal state
    this._localTracks = [];
    this._remoteTracks = [];
    this._senders = [];
    this._receivers = [];
    this._transceivers = [];
    this._iceCandidates = [];
    this._dataChannels = [];
    this._closed = false;
    
    // Stats tracking
    this._stats = new Map();
  }

  /**
   * Create an SDP offer
   */
  async createOffer(options = {}) {
    if (this._closed) {
      throw new Error('Connection is closed');
    }
    
    return {
      type: 'offer',
      sdp: `v=0\r\no=- ${Date.now()} 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n` +
           `a=group:BUNDLE 0 1\r\na=msid-semantic: WMS mock-stream\r\n` +
           `m=video 9 UDP/TLS/RTP/SAVPF 96\r\nc=IN IP4 0.0.0.0\r\n` +
           `a=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:mock\r\na=ice-pwd:mock\r\n` +
           `a=fingerprint:sha-256 MOCK:FINGERPRINT\r\na=setup:actpass\r\n` +
           `a=mid:0\r\na=sendrecv\r\na=rtpmap:96 VP8/90000\r\n` +
           `m=audio 9 UDP/TLS/RTP/SAVPF 111\r\nc=IN IP4 0.0.0.0\r\n` +
           `a=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:mock\r\na=ice-pwd:mock\r\n` +
           `a=fingerprint:sha-256 MOCK:FINGERPRINT\r\na=setup:actpass\r\n` +
           `a=mid:1\r\na=sendrecv\r\na=rtpmap:111 opus/48000/2\r\n`,
    };
  }

  /**
   * Create an SDP answer
   */
  async createAnswer(options = {}) {
    if (this._closed) {
      throw new Error('Connection is closed');
    }
    
    if (!this.remoteDescription) {
      throw new Error('No remote description set');
    }
    
    return {
      type: 'answer',
      sdp: `v=0\r\no=- ${Date.now()} 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n` +
           `a=group:BUNDLE 0 1\r\na=msid-semantic: WMS mock-stream\r\n` +
           `m=video 9 UDP/TLS/RTP/SAVPF 96\r\nc=IN IP4 0.0.0.0\r\n` +
           `a=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:mock\r\na=ice-pwd:mock\r\n` +
           `a=fingerprint:sha-256 MOCK:FINGERPRINT\r\na=setup:active\r\n` +
           `a=mid:0\r\na=sendrecv\r\na=rtpmap:96 VP8/90000\r\n` +
           `m=audio 9 UDP/TLS/RTP/SAVPF 111\r\nc=IN IP4 0.0.0.0\r\n` +
           `a=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:mock\r\na=ice-pwd:mock\r\n` +
           `a=fingerprint:sha-256 MOCK:FINGERPRINT\r\na=setup:active\r\n` +
           `a=mid:1\r\na=sendrecv\r\na=rtpmap:111 opus/48000/2\r\n`,
    };
  }

  /**
   * Set local description
   */
  async setLocalDescription(description) {
    if (this._closed) {
      throw new Error('Connection is closed');
    }
    
    this.localDescription = description;
    this.signalingState = description.type === 'offer' ? 'have-local-offer' : 'stable';
    
    if (this.onsignalingstatechange) {
      this.onsignalingstatechange();
    }
    
    // Simulate ICE candidate gathering
    setTimeout(() => {
      this._simulateIceCandidateGathering();
    }, 10);
  }

  /**
   * Set remote description
   */
  async setRemoteDescription(description) {
    if (this._closed) {
      throw new Error('Connection is closed');
    }
    
    this.remoteDescription = description;
    this.signalingState = description.type === 'offer' ? 'have-remote-offer' : 'stable';
    
    if (this.onsignalingstatechange) {
      this.onsignalingstatechange();
    }
    
    // Simulate receiving remote tracks
    if (description.type === 'answer' || description.type === 'offer') {
      setTimeout(() => {
        this._simulateRemoteTracks();
      }, 20);
    }
  }

  /**
   * Add ICE candidate
   */
  async addIceCandidate(candidate) {
    if (this._closed) {
      throw new Error('Connection is closed');
    }
    
    if (candidate) {
      this._iceCandidates.push(candidate);
      
      // Simulate connection establishment after receiving candidates
      if (this._iceCandidates.length >= 2 && this.remoteDescription) {
        setTimeout(() => {
          this._simulateConnectionEstablishment();
        }, 50);
      }
    }
  }

  /**
   * Add track to connection
   */
  addTrack(track, stream) {
    if (this._closed) {
      throw new Error('Connection is closed');
    }
    
    const sender = {
      track,
      streams: [stream],
      replaceTrack: async (newTrack) => {
        sender.track = newTrack;
        return Promise.resolve();
      },
      getParameters: () => ({}),
      setParameters: () => Promise.resolve(),
    };
    
    this._localTracks.push(track);
    this._senders.push(sender);
    
    return sender;
  }

  /**
   * Remove track from connection
   */
  removeTrack(sender) {
    const index = this._senders.indexOf(sender);
    if (index !== -1) {
      this._senders.splice(index, 1);
      const trackIndex = this._localTracks.indexOf(sender.track);
      if (trackIndex !== -1) {
        this._localTracks.splice(trackIndex, 1);
      }
    }
  }

  /**
   * Get senders
   */
  getSenders() {
    return [...this._senders];
  }

  /**
   * Get receivers
   */
  getReceivers() {
    return [...this._receivers];
  }

  /**
   * Get transceivers
   */
  getTransceivers() {
    return [...this._transceivers];
  }

  /**
   * Get connection statistics
   */
  async getStats(selector = null) {
    const stats = new Map();
    
    // Inbound RTP stats (video)
    stats.set('inbound-rtp-video', {
      type: 'inbound-rtp',
      kind: 'video',
      packetsReceived: 1000,
      packetsLost: 5,
      bytesReceived: 1000000,
      timestamp: Date.now(),
      jitter: 0.01,
    });
    
    // Inbound RTP stats (audio)
    stats.set('inbound-rtp-audio', {
      type: 'inbound-rtp',
      kind: 'audio',
      packetsReceived: 2000,
      packetsLost: 2,
      bytesReceived: 500000,
      timestamp: Date.now(),
      jitter: 0.005,
    });
    
    // Candidate pair stats
    stats.set('candidate-pair', {
      type: 'candidate-pair',
      state: 'succeeded',
      currentRoundTripTime: 0.05, // 50ms
      availableOutgoingBitrate: 1000000,
      availableIncomingBitrate: 1000000,
    });
    
    return stats;
  }

  /**
   * Close the connection
   */
  close() {
    if (this._closed) return;
    
    this._closed = true;
    this.connectionState = 'closed';
    this.iceConnectionState = 'closed';
    this.signalingState = 'closed';
    
    if (this.onconnectionstatechange) {
      this.onconnectionstatechange();
    }
    
    if (this.oniceconnectionstatechange) {
      this.oniceconnectionstatechange();
    }
  }

  /**
   * Create data channel
   */
  createDataChannel(label, options = {}) {
    const channel = {
      label,
      ordered: options.ordered !== false,
      maxPacketLifeTime: options.maxPacketLifeTime || null,
      maxRetransmits: options.maxRetransmits || null,
      protocol: options.protocol || '',
      negotiated: options.negotiated || false,
      id: options.id || this._dataChannels.length,
      readyState: 'connecting',
      bufferedAmount: 0,
      send: jest.fn(),
      close: jest.fn(() => {
        channel.readyState = 'closed';
      }),
      onopen: null,
      onclose: null,
      onmessage: null,
      onerror: null,
    };
    
    this._dataChannels.push(channel);
    
    // Simulate channel opening
    setTimeout(() => {
      channel.readyState = 'open';
      if (channel.onopen) {
        channel.onopen();
      }
    }, 50);
    
    return channel;
  }

  /**
   * Add event listener (for compatibility)
   */
  addEventListener(event, handler) {
    const eventName = `on${event}`;
    if (eventName in this) {
      this[eventName] = handler;
    }
  }

  /**
   * Remove event listener (for compatibility)
   */
  removeEventListener(event, handler) {
    const eventName = `on${event}`;
    if (eventName in this && this[eventName] === handler) {
      this[eventName] = null;
    }
  }

  // Private helper methods

  _simulateIceCandidateGathering() {
    if (this._closed) return;
    
    this.iceGatheringState = 'gathering';
    if (this.onicegatheringstatechange) {
      this.onicegatheringstatechange();
    }
    
    // Generate mock ICE candidates
    const candidates = [
      {
        candidate: 'candidate:1 1 UDP 2130706431 192.168.1.100 54321 typ host',
        sdpMLineIndex: 0,
        sdpMid: '0',
        toJSON: function() { return this; },
      },
      {
        candidate: 'candidate:2 1 UDP 1694498815 203.0.113.1 54322 typ srflx raddr 192.168.1.100 rport 54321',
        sdpMLineIndex: 0,
        sdpMid: '0',
        toJSON: function() { return this; },
      },
    ];
    
    candidates.forEach((candidate, index) => {
      setTimeout(() => {
        if (this.onicecandidate && !this._closed) {
          this.onicecandidate({ candidate });
        }
      }, 20 * (index + 1));
    });
    
    // Signal gathering complete
    setTimeout(() => {
      if (this._closed) return;
      
      this.iceGatheringState = 'complete';
      if (this.onicegatheringstatechange) {
        this.onicegatheringstatechange();
      }
      
      // Send null candidate to signal end
      if (this.onicecandidate) {
        this.onicecandidate({ candidate: null });
      }
    }, 100);
  }

  _simulateRemoteTracks() {
    if (this._closed) return;
    
    // Create mock remote stream with tracks
    const remoteStream = new MockMediaStream();
    
    remoteStream.getTracks().forEach(track => {
      this._remoteTracks.push(track);
      
      const receiver = {
        track,
        getParameters: () => ({}),
      };
      
      this._receivers.push(receiver);
      
      if (this.ontrack) {
        this.ontrack({
          track,
          streams: [remoteStream],
          receiver,
        });
      }
    });
  }

  _simulateConnectionEstablishment() {
    if (this._closed) return;
    
    // Simulate ICE connection state progression
    this.iceConnectionState = 'checking';
    if (this.oniceconnectionstatechange) {
      this.oniceconnectionstatechange();
    }
    
    setTimeout(() => {
      if (this._closed) return;
      
      this.iceConnectionState = 'connected';
      this.connectionState = 'connected';
      
      if (this.oniceconnectionstatechange) {
        this.oniceconnectionstatechange();
      }
      
      if (this.onconnectionstatechange) {
        this.onconnectionstatechange();
      }
    }, 100);
  }
}

/**
 * Mock RTCSessionDescription
 */
class MockRTCSessionDescription {
  constructor(descriptionInitDict) {
    this.type = descriptionInitDict.type;
    this.sdp = descriptionInitDict.sdp;
  }

  toJSON() {
    return {
      type: this.type,
      sdp: this.sdp,
    };
  }
}

/**
 * Mock RTCIceCandidate
 */
class MockRTCIceCandidate {
  constructor(candidateInitDict) {
    this.candidate = candidateInitDict.candidate || '';
    this.sdpMLineIndex = candidateInitDict.sdpMLineIndex || 0;
    this.sdpMid = candidateInitDict.sdpMid || '0';
  }

  toJSON() {
    return {
      candidate: this.candidate,
      sdpMLineIndex: this.sdpMLineIndex,
      sdpMid: this.sdpMid,
    };
  }
}

/**
 * Setup WebRTC mocks
 * Call this in beforeEach to install all mocks
 */
export function setupWebRTCMocks() {
  // Mock RTCPeerConnection
  global.RTCPeerConnection = jest.fn((config) => new MockRTCPeerConnection(config));
  
  // Mock RTCSessionDescription
  global.RTCSessionDescription = jest.fn((desc) => new MockRTCSessionDescription(desc));
  
  // Mock RTCIceCandidate
  global.RTCIceCandidate = jest.fn((candidate) => new MockRTCIceCandidate(candidate));
  
  // Mock navigator.mediaDevices
  if (!global.navigator) {
    global.navigator = {};
  }
  
  global.navigator.mediaDevices = {
    getUserMedia: jest.fn(async (constraints) => {
      // Simulate permission check
      if (constraints.video === false && constraints.audio === false) {
        throw new Error('At least one media type must be requested');
      }
      
      const tracks = [];
      
      if (constraints.video) {
        tracks.push(new MockMediaStreamTrack('video'));
      }
      
      if (constraints.audio) {
        tracks.push(new MockMediaStreamTrack('audio'));
      }
      
      return new MockMediaStream(tracks);
    }),
    
    getDisplayMedia: jest.fn(async (constraints) => {
      // Simulate screen capture
      const screenTrack = new MockMediaStreamTrack('video', 'screen-share-track');
      screenTrack.label = 'Screen share';
      
      const tracks = [screenTrack];
      
      if (constraints.audio) {
        tracks.push(new MockMediaStreamTrack('audio', 'screen-audio-track'));
      }
      
      return new MockMediaStream(tracks);
    }),
    
    enumerateDevices: jest.fn(async () => [
      {
        deviceId: 'default',
        kind: 'audioinput',
        label: 'Default Microphone',
        groupId: 'group1',
      },
      {
        deviceId: 'default',
        kind: 'videoinput',
        label: 'Default Camera',
        groupId: 'group1',
      },
      {
        deviceId: 'default',
        kind: 'audiooutput',
        label: 'Default Speaker',
        groupId: 'group1',
      },
    ]),
  };
  
  // Export mock classes for test access
  return {
    MockRTCPeerConnection,
    MockMediaStream,
    MockMediaStreamTrack,
    MockRTCSessionDescription,
    MockRTCIceCandidate,
  };
}

/**
 * Teardown WebRTC mocks
 * Call this in afterEach to clean up
 */
export function teardownWebRTCMocks() {
  // Clear all mock implementations
  if (global.RTCPeerConnection) {
    global.RTCPeerConnection.mockClear();
  }
  
  if (global.RTCSessionDescription) {
    global.RTCSessionDescription.mockClear();
  }
  
  if (global.RTCIceCandidate) {
    global.RTCIceCandidate.mockClear();
  }
  
  if (global.navigator?.mediaDevices?.getUserMedia) {
    global.navigator.mediaDevices.getUserMedia.mockClear();
  }
  
  if (global.navigator?.mediaDevices?.getDisplayMedia) {
    global.navigator.mediaDevices.getDisplayMedia.mockClear();
  }
}

/**
 * Simulate ICE candidate event
 * Helper to manually trigger ICE candidate events in tests
 */
export function simulateIceCandidate(peerConnection, candidate) {
  if (peerConnection.onicecandidate) {
    peerConnection.onicecandidate({ candidate });
  }
}

/**
 * Simulate connection state change
 * Helper to manually trigger connection state changes in tests
 */
export function simulateConnectionStateChange(peerConnection, state) {
  peerConnection.connectionState = state;
  if (peerConnection.onconnectionstatechange) {
    peerConnection.onconnectionstatechange();
  }
}

/**
 * Simulate ICE connection state change
 * Helper to manually trigger ICE connection state changes in tests
 */
export function simulateIceConnectionStateChange(peerConnection, state) {
  peerConnection.iceConnectionState = state;
  if (peerConnection.oniceconnectionstatechange) {
    peerConnection.oniceconnectionstatechange();
  }
}

/**
 * Simulate track event
 * Helper to manually trigger track events (remote stream received)
 */
export function simulateTrackEvent(peerConnection, track, streams = []) {
  if (peerConnection.ontrack) {
    const receiver = {
      track,
      getParameters: () => ({}),
    };
    
    peerConnection.ontrack({
      track,
      streams,
      receiver,
    });
  }
}

/**
 * Simulate media permission denied error
 * Helper to make getUserMedia throw permission denied error
 */
export function simulateMediaPermissionDenied() {
  const error = new Error('Permission denied');
  error.name = 'NotAllowedError';
  global.navigator.mediaDevices.getUserMedia.mockRejectedValueOnce(error);
}

/**
 * Simulate media device not found error
 * Helper to make getUserMedia throw device not found error
 */
export function simulateMediaDeviceNotFound() {
  const error = new Error('Requested device not found');
  error.name = 'NotFoundError';
  global.navigator.mediaDevices.getUserMedia.mockRejectedValueOnce(error);
}

/**
 * Simulate screen share permission denied error
 * Helper to make getDisplayMedia throw permission denied error
 */
export function simulateScreenSharePermissionDenied() {
  const error = new Error('Permission denied');
  error.name = 'NotAllowedError';
  global.navigator.mediaDevices.getDisplayMedia.mockRejectedValueOnce(error);
}

/**
 * Create a mock signaling channel
 * Helper to create a mock WebSocket-like signaling channel
 */
export function createMockSignalingChannel() {
  return {
    send: jest.fn(),
    close: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    readyState: 1, // OPEN
  };
}

/**
 * Wait for async operations
 * Helper to wait for promises and timers to resolve
 */
export async function flushPromises() {
  return new Promise((resolve) => {
    setTimeout(resolve, 0);
  });
}

// Export mock classes for direct use in tests
export {
  MockRTCPeerConnection,
  MockMediaStream,
  MockMediaStreamTrack,
  MockRTCSessionDescription,
  MockRTCIceCandidate,
};
