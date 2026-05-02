/**
 * Tests for WebRTC Mocking Infrastructure
 * 
 * Verifies that the mock infrastructure correctly simulates WebRTC APIs
 * and provides the necessary helpers for E2E testing.
 * 
 * Requirements: 12.8
 */

import {
  setupWebRTCMocks,
  teardownWebRTCMocks,
  simulateIceCandidate,
  simulateConnectionStateChange,
  simulateIceConnectionStateChange,
  simulateTrackEvent,
  simulateMediaPermissionDenied,
  simulateMediaDeviceNotFound,
  simulateScreenSharePermissionDenied,
  createMockSignalingChannel,
  flushPromises,
  MockRTCPeerConnection,
  MockMediaStream,
  MockMediaStreamTrack,
} from './webrtcMocks';

describe('WebRTC Mocking Infrastructure', () => {
  beforeEach(() => {
    setupWebRTCMocks();
  });

  afterEach(() => {
    teardownWebRTCMocks();
    jest.clearAllMocks();
  });

  // ─── MockMediaStreamTrack ────────────────────────────────────────────────────

  describe('MockMediaStreamTrack', () => {
    test('creates a video track with correct defaults', () => {
      const track = new MockMediaStreamTrack('video');

      expect(track.kind).toBe('video');
      expect(track.enabled).toBe(true);
      expect(track.readyState).toBe('live');
      expect(track._stopped).toBe(false);
    });

    test('creates an audio track with correct defaults', () => {
      const track = new MockMediaStreamTrack('audio');

      expect(track.kind).toBe('audio');
      expect(track.enabled).toBe(true);
    });

    test('stop() sets readyState to ended and fires onended', () => {
      const track = new MockMediaStreamTrack('video');
      const onEnded = jest.fn();
      track.onended = onEnded;

      track.stop();

      expect(track._stopped).toBe(true);
      expect(track.readyState).toBe('ended');
      expect(onEnded).toHaveBeenCalledTimes(1);
    });

    test('enabled property can be toggled', () => {
      const track = new MockMediaStreamTrack('audio');

      track.enabled = false;
      expect(track.enabled).toBe(false);

      track.enabled = true;
      expect(track.enabled).toBe(true);
    });

    test('clone() returns a new track with same kind', () => {
      const track = new MockMediaStreamTrack('video');
      track.enabled = false;

      const cloned = track.clone();

      expect(cloned).not.toBe(track);
      expect(cloned.kind).toBe('video');
      expect(cloned.enabled).toBe(false);
    });
  });

  // ─── MockMediaStream ─────────────────────────────────────────────────────────

  describe('MockMediaStream', () => {
    test('creates stream with default video and audio tracks', () => {
      const stream = new MockMediaStream();

      expect(stream.getTracks()).toHaveLength(2);
      expect(stream.getVideoTracks()).toHaveLength(1);
      expect(stream.getAudioTracks()).toHaveLength(1);
    });

    test('creates stream with custom tracks', () => {
      const videoTrack = new MockMediaStreamTrack('video');
      const audioTrack = new MockMediaStreamTrack('audio');
      const stream = new MockMediaStream([videoTrack, audioTrack]);

      expect(stream.getTracks()).toHaveLength(2);
      expect(stream.getVideoTracks()[0]).toBe(videoTrack);
      expect(stream.getAudioTracks()[0]).toBe(audioTrack);
    });

    test('addTrack() adds a track to the stream', () => {
      const stream = new MockMediaStream([]);
      const track = new MockMediaStreamTrack('video');

      stream.addTrack(track);

      expect(stream.getTracks()).toHaveLength(1);
      expect(stream.getVideoTracks()[0]).toBe(track);
    });

    test('addTrack() fires onaddtrack callback', () => {
      const stream = new MockMediaStream([]);
      const track = new MockMediaStreamTrack('video');
      const onAddTrack = jest.fn();
      stream.onaddtrack = onAddTrack;

      stream.addTrack(track);

      expect(onAddTrack).toHaveBeenCalledWith({ track });
    });

    test('removeTrack() removes a track from the stream', () => {
      const track = new MockMediaStreamTrack('video');
      const stream = new MockMediaStream([track]);

      stream.removeTrack(track);

      expect(stream.getTracks()).toHaveLength(0);
    });

    test('removeTrack() fires onremovetrack callback', () => {
      const track = new MockMediaStreamTrack('video');
      const stream = new MockMediaStream([track]);
      const onRemoveTrack = jest.fn();
      stream.onremovetrack = onRemoveTrack;

      stream.removeTrack(track);

      expect(onRemoveTrack).toHaveBeenCalledWith({ track });
    });

    test('getTrackById() returns the correct track', () => {
      const track = new MockMediaStreamTrack('video');
      const stream = new MockMediaStream([track]);

      const found = stream.getTrackById(track.id);

      expect(found).toBe(track);
    });

    test('getTrackById() returns null for unknown id', () => {
      const stream = new MockMediaStream();

      expect(stream.getTrackById('nonexistent')).toBeNull();
    });

    test('getTracks() returns a copy (not the internal array)', () => {
      const stream = new MockMediaStream();
      const tracks = stream.getTracks();

      tracks.push(new MockMediaStreamTrack('video'));

      expect(stream.getTracks()).toHaveLength(2); // unchanged
    });
  });

  // ─── MockRTCPeerConnection ───────────────────────────────────────────────────

  describe('MockRTCPeerConnection', () => {
    test('creates peer connection with correct initial state', () => {
      const pc = new MockRTCPeerConnection({ iceServers: [] });

      expect(pc.connectionState).toBe('new');
      expect(pc.iceConnectionState).toBe('new');
      expect(pc.signalingState).toBe('stable');
      expect(pc.localDescription).toBeNull();
      expect(pc.remoteDescription).toBeNull();
    });

    test('createOffer() returns a valid offer SDP', async () => {
      const pc = new MockRTCPeerConnection({});

      const offer = await pc.createOffer();

      expect(offer.type).toBe('offer');
      expect(offer.sdp).toContain('v=0');
      expect(offer.sdp).toContain('m=video');
      expect(offer.sdp).toContain('m=audio');
    });

    test('createAnswer() returns a valid answer SDP after remote description is set', async () => {
      const pc = new MockRTCPeerConnection({});
      const offer = await pc.createOffer();
      await pc.setRemoteDescription(offer);

      const answer = await pc.createAnswer();

      expect(answer.type).toBe('answer');
      expect(answer.sdp).toContain('v=0');
    });

    test('createAnswer() throws if no remote description is set', async () => {
      const pc = new MockRTCPeerConnection({});

      await expect(pc.createAnswer()).rejects.toThrow('No remote description set');
    });

    test('setLocalDescription() updates localDescription', async () => {
      const pc = new MockRTCPeerConnection({});
      const offer = await pc.createOffer();

      await pc.setLocalDescription(offer);

      expect(pc.localDescription).toEqual(offer);
      expect(pc.signalingState).toBe('have-local-offer');
    });

    test('setRemoteDescription() updates remoteDescription', async () => {
      const pc = new MockRTCPeerConnection({});
      const offer = await pc.createOffer();

      await pc.setRemoteDescription(offer);

      expect(pc.remoteDescription).toEqual(offer);
      expect(pc.signalingState).toBe('have-remote-offer');
    });

    test('addIceCandidate() stores the candidate', async () => {
      const pc = new MockRTCPeerConnection({});
      const candidate = { candidate: 'candidate:1 1 UDP 2130706431 192.168.1.1 54321 typ host' };

      await pc.addIceCandidate(candidate);

      expect(pc._iceCandidates).toHaveLength(1);
    });

    test('addTrack() adds track and returns sender', () => {
      const pc = new MockRTCPeerConnection({});
      const track = new MockMediaStreamTrack('video');
      const stream = new MockMediaStream([track]);

      const sender = pc.addTrack(track, stream);

      expect(sender).toBeDefined();
      expect(sender.track).toBe(track);
      expect(pc.getSenders()).toHaveLength(1);
    });

    test('getSenders() returns all senders', () => {
      const pc = new MockRTCPeerConnection({});
      const videoTrack = new MockMediaStreamTrack('video');
      const audioTrack = new MockMediaStreamTrack('audio');
      const stream = new MockMediaStream([videoTrack, audioTrack]);

      pc.addTrack(videoTrack, stream);
      pc.addTrack(audioTrack, stream);

      expect(pc.getSenders()).toHaveLength(2);
    });

    test('sender.replaceTrack() replaces the track', async () => {
      const pc = new MockRTCPeerConnection({});
      const originalTrack = new MockMediaStreamTrack('video');
      const newTrack = new MockMediaStreamTrack('video');
      const stream = new MockMediaStream([originalTrack]);

      const sender = pc.addTrack(originalTrack, stream);
      await sender.replaceTrack(newTrack);

      expect(sender.track).toBe(newTrack);
    });

    test('close() sets connection state to closed', () => {
      const pc = new MockRTCPeerConnection({});
      const onStateChange = jest.fn();
      pc.onconnectionstatechange = onStateChange;

      pc.close();

      expect(pc.connectionState).toBe('closed');
      expect(pc._closed).toBe(true);
      expect(onStateChange).toHaveBeenCalled();
    });

    test('close() prevents further operations', async () => {
      const pc = new MockRTCPeerConnection({});
      pc.close();

      await expect(pc.createOffer()).rejects.toThrow('Connection is closed');
    });

    test('getStats() returns a stats map', async () => {
      const pc = new MockRTCPeerConnection({});

      const stats = await pc.getStats();

      expect(stats).toBeInstanceOf(Map);
      expect(stats.has('inbound-rtp-video')).toBe(true);
      expect(stats.has('candidate-pair')).toBe(true);
    });

    test('addEventListener() and removeEventListener() work', () => {
      const pc = new MockRTCPeerConnection({});
      const handler = jest.fn();

      pc.addEventListener('icecandidate', handler);
      expect(pc.onicecandidate).toBe(handler);

      pc.removeEventListener('icecandidate', handler);
      expect(pc.onicecandidate).toBeNull();
    });
  });

  // ─── Global Mock Setup ───────────────────────────────────────────────────────

  describe('Global Mock Setup (setupWebRTCMocks)', () => {
    test('RTCPeerConnection is mocked globally', () => {
      expect(global.RTCPeerConnection).toBeDefined();
      expect(jest.isMockFunction(global.RTCPeerConnection)).toBe(true);
    });

    test('RTCSessionDescription is mocked globally', () => {
      expect(global.RTCSessionDescription).toBeDefined();
      expect(jest.isMockFunction(global.RTCSessionDescription)).toBe(true);
    });

    test('RTCIceCandidate is mocked globally', () => {
      expect(global.RTCIceCandidate).toBeDefined();
      expect(jest.isMockFunction(global.RTCIceCandidate)).toBe(true);
    });

    test('navigator.mediaDevices.getUserMedia is mocked', () => {
      expect(global.navigator.mediaDevices.getUserMedia).toBeDefined();
      expect(jest.isMockFunction(global.navigator.mediaDevices.getUserMedia)).toBe(true);
    });

    test('navigator.mediaDevices.getDisplayMedia is mocked', () => {
      expect(global.navigator.mediaDevices.getDisplayMedia).toBeDefined();
      expect(jest.isMockFunction(global.navigator.mediaDevices.getDisplayMedia)).toBe(true);
    });

    test('getUserMedia returns a MockMediaStream with video and audio tracks', async () => {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });

      expect(stream).toBeInstanceOf(MockMediaStream);
      expect(stream.getVideoTracks()).toHaveLength(1);
      expect(stream.getAudioTracks()).toHaveLength(1);
    });

    test('getUserMedia returns only video track when audio is false', async () => {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });

      expect(stream.getVideoTracks()).toHaveLength(1);
      expect(stream.getAudioTracks()).toHaveLength(0);
    });

    test('getUserMedia returns only audio track when video is false', async () => {
      const stream = await navigator.mediaDevices.getUserMedia({ video: false, audio: true });

      expect(stream.getVideoTracks()).toHaveLength(0);
      expect(stream.getAudioTracks()).toHaveLength(1);
    });

    test('getDisplayMedia returns a screen share stream', async () => {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });

      expect(stream).toBeInstanceOf(MockMediaStream);
      expect(stream.getVideoTracks()).toHaveLength(1);
      expect(stream.getVideoTracks()[0].label).toBe('Screen share');
    });

    test('new RTCPeerConnection() creates a MockRTCPeerConnection', () => {
      const pc = new RTCPeerConnection({ iceServers: [] });

      expect(pc).toBeInstanceOf(MockRTCPeerConnection);
    });

    test('new RTCSessionDescription() creates a mock description', () => {
      const desc = new RTCSessionDescription({ type: 'offer', sdp: 'v=0\r\n' });

      expect(desc.type).toBe('offer');
      expect(desc.sdp).toBe('v=0\r\n');
    });

    test('new RTCIceCandidate() creates a mock candidate', () => {
      const candidate = new RTCIceCandidate({
        candidate: 'candidate:1 1 UDP 2130706431 192.168.1.1 54321 typ host',
        sdpMLineIndex: 0,
      });

      expect(candidate.candidate).toContain('candidate:1');
      expect(candidate.sdpMLineIndex).toBe(0);
    });
  });

  // ─── Simulation Helpers ──────────────────────────────────────────────────────

  describe('Simulation Helpers', () => {
    test('simulateIceCandidate() fires onicecandidate handler', () => {
      const pc = new RTCPeerConnection({});
      const handler = jest.fn();
      pc.onicecandidate = handler;

      const candidate = { candidate: 'candidate:1 1 UDP 2130706431 192.168.1.1 54321 typ host' };
      simulateIceCandidate(pc, candidate);

      expect(handler).toHaveBeenCalledWith({ candidate });
    });

    test('simulateConnectionStateChange() updates state and fires handler', () => {
      const pc = new RTCPeerConnection({});
      const handler = jest.fn();
      pc.onconnectionstatechange = handler;

      simulateConnectionStateChange(pc, 'connected');

      expect(pc.connectionState).toBe('connected');
      expect(handler).toHaveBeenCalled();
    });

    test('simulateIceConnectionStateChange() updates state and fires handler', () => {
      const pc = new RTCPeerConnection({});
      const handler = jest.fn();
      pc.oniceconnectionstatechange = handler;

      simulateIceConnectionStateChange(pc, 'connected');

      expect(pc.iceConnectionState).toBe('connected');
      expect(handler).toHaveBeenCalled();
    });

    test('simulateTrackEvent() fires ontrack handler', () => {
      const pc = new RTCPeerConnection({});
      const handler = jest.fn();
      pc.ontrack = handler;

      const track = new MockMediaStreamTrack('video');
      const stream = new MockMediaStream([track]);
      simulateTrackEvent(pc, track, [stream]);

      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({
          track,
          streams: [stream],
        })
      );
    });

    test('simulateMediaPermissionDenied() makes getUserMedia reject', async () => {
      simulateMediaPermissionDenied();

      await expect(
        navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      ).rejects.toMatchObject({ name: 'NotAllowedError' });
    });

    test('simulateMediaDeviceNotFound() makes getUserMedia reject with NotFoundError', async () => {
      simulateMediaDeviceNotFound();

      await expect(
        navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      ).rejects.toMatchObject({ name: 'NotFoundError' });
    });

    test('simulateScreenSharePermissionDenied() makes getDisplayMedia reject', async () => {
      simulateScreenSharePermissionDenied();

      await expect(
        navigator.mediaDevices.getDisplayMedia({ video: true })
      ).rejects.toMatchObject({ name: 'NotAllowedError' });
    });

    test('createMockSignalingChannel() returns a mock channel', () => {
      const channel = createMockSignalingChannel();

      expect(channel.send).toBeDefined();
      expect(jest.isMockFunction(channel.send)).toBe(true);
      expect(channel.readyState).toBe(1);
    });
  });

  // ─── ICE Candidate Gathering Simulation ─────────────────────────────────────

  describe('ICE Candidate Gathering Simulation', () => {
    test('setLocalDescription triggers ICE candidate gathering', async () => {
      jest.useFakeTimers();

      const pc = new RTCPeerConnection({});
      const iceCandidateHandler = jest.fn();
      pc.onicecandidate = iceCandidateHandler;

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      // Advance timers to trigger ICE gathering
      jest.advanceTimersByTime(200);

      expect(iceCandidateHandler).toHaveBeenCalled();

      jest.useRealTimers();
    });

    test('ICE gathering completes with null candidate signal', async () => {
      jest.useFakeTimers();

      const pc = new RTCPeerConnection({});
      const candidates = [];
      pc.onicecandidate = (event) => candidates.push(event.candidate);

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      jest.advanceTimersByTime(200);

      // Last candidate should be null (end of gathering)
      const lastCandidate = candidates[candidates.length - 1];
      expect(lastCandidate).toBeNull();

      jest.useRealTimers();
    });
  });

  // ─── Connection Establishment Simulation ────────────────────────────────────

  describe('Connection Establishment Simulation', () => {
    test('connection transitions to connected state after ICE exchange', async () => {
      jest.useFakeTimers();

      const pc = new RTCPeerConnection({});
      const stateChanges = [];
      pc.oniceconnectionstatechange = () => stateChanges.push(pc.iceConnectionState);

      const offer = await pc.createOffer();
      await pc.setRemoteDescription(offer);

      // Add enough ICE candidates to trigger connection
      await pc.addIceCandidate({ candidate: 'candidate:1 1 UDP 2130706431 192.168.1.1 54321 typ host' });
      await pc.addIceCandidate({ candidate: 'candidate:2 1 UDP 1694498815 203.0.113.1 54322 typ srflx' });

      jest.advanceTimersByTime(200);

      expect(stateChanges).toContain('checking');
      expect(stateChanges).toContain('connected');

      jest.useRealTimers();
    });
  });

  // ─── Teardown ────────────────────────────────────────────────────────────────

  describe('teardownWebRTCMocks', () => {
    test('clears mock call counts after teardown', () => {
      // Make some calls
      new RTCPeerConnection({});
      navigator.mediaDevices.getUserMedia({ video: true, audio: true });

      teardownWebRTCMocks();

      // Mock functions should have cleared call counts
      expect(global.RTCPeerConnection.mock.calls.length).toBe(0);
      expect(global.navigator.mediaDevices.getUserMedia.mock.calls.length).toBe(0);
    });
  });
});
