import { useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react';
import WebRTCClient from '@/lib/webrtc/WebRTCClient';
import LocalVideoPreview from './LocalVideoPreview';
import RemoteVideoGrid from './RemoteVideoGrid';
import ScreenShareDisplay from './ScreenShareDisplay';
import CallControls from './CallControls';
import toast from 'react-hot-toast';

/**
 * VideoCallContainer - top-level video call component.
 *
 * Props:
 *   roomId        {string}   - The call room ID
 *   userId        {string}   - Current user's ID
 *   user          {object}   - Current user object { id, full_name, avatar_url }
 *   participants  {Array}    - Array of participant objects (excluding self)
 *   signalingChannel {object} - WebSocket channel with a .send() method
 *   iceServers    {Array}    - Optional ICE server config
 *   onCallEnd     {Function} - Called when the user leaves the call
 *
 * Ref methods (exposed via useImperativeHandle for parent page integration):
 *   handleWebRTCOffer(fromUserId, sdp)
 *   handleWebRTCAnswer(fromUserId, sdp)
 *   handleWebRTCIce(fromUserId, candidate)
 *   handleParticipantState(remoteUserId, state)
 *   handleUserJoined(userId)
 *   handleUserLeft(userId)
 *   connectToExistingParticipants(participantIds)
 */
const VideoCallContainer = forwardRef(function VideoCallContainer({
  roomId,
  userId,
  user,
  participants = [],
  signalingChannel,
  iceServers,
  onCallEnd,
}, ref) {
  const [localStream, setLocalStream] = useState(null);
  const [remoteStreams, setRemoteStreams] = useState({}); // { userId: MediaStream }
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [videoEnabled, setVideoEnabled] = useState(true);
  const [screenSharing, setScreenSharing] = useState(false);
  const [screenStream, setScreenStream] = useState(null);
  const [screenSharerId, setScreenSharerId] = useState(null); // who is sharing
  const [participantStates, setParticipantStates] = useState({}); // { userId: { is_muted, is_video_on } }
  const [connectionQualities, setConnectionQualities] = useState({}); // { userId: quality }

  const clientRef = useRef(null);

  // ── Initialise WebRTCClient ──────────────────────────────────────────────
  useEffect(() => {
    if (!signalingChannel) return;

    const client = new WebRTCClient(roomId, userId, signalingChannel);

    if (iceServers) client.setIceServers(iceServers);

    client.onRemoteStream = (remoteUserId, stream) => {
      setRemoteStreams((prev) => ({ ...prev, [remoteUserId]: stream }));
    };

    client.onRemoteStreamRemoved = (remoteUserId) => {
      setRemoteStreams((prev) => {
        const next = { ...prev };
        delete next[remoteUserId];
        return next;
      });
    };

    client.onConnectionQualityChange = (remoteUserId, quality) => {
      setConnectionQualities((prev) => ({ ...prev, [remoteUserId]: quality }));
    };

    client.onError = (type, error, remoteUserId) => {
      console.error(`WebRTC error [${type}]`, error);
      if (type === 'media_permission_denied') {
        toast.error('Camera/microphone access denied. Please grant permissions.');
      } else if (type === 'media_device_not_found') {
        toast.error('No camera or microphone found.');
      } else if (type === 'reconnection_failed') {
        toast.error(`Lost connection with a participant.`);
      }
    };

    clientRef.current = client;

    // Acquire local media
    client.getLocalMediaStream()
      .then((stream) => setLocalStream(stream))
      .catch(() => {
        // Error already handled via onError callback
      });

    return () => {
      client.releaseMediaStreams();
      clientRef.current = null;
    };
  }, [roomId, userId, signalingChannel, iceServers]);

  // ── Handle incoming signaling messages ──────────────────────────────────
  // The parent is expected to route these by calling the methods below.
  // Expose handlers via ref so the parent can call them.
  const handleWebRTCOffer = useCallback(async (fromUserId, sdp) => {
    await clientRef.current?.handleOffer(fromUserId, sdp);
  }, []);

  const handleWebRTCAnswer = useCallback(async (fromUserId, sdp) => {
    await clientRef.current?.handleAnswer(fromUserId, sdp);
  }, []);

  const handleWebRTCIce = useCallback(async (fromUserId, candidate) => {
    await clientRef.current?.handleIceCandidate(fromUserId, candidate);
  }, []);

  const handleParticipantState = useCallback((remoteUserId, state) => {
    setParticipantStates((prev) => ({ ...prev, [remoteUserId]: state }));
    if (state.is_screen_sharing) {
      setScreenSharerId(remoteUserId);
    } else if (screenSharerId === remoteUserId) {
      setScreenSharerId(null);
    }
  }, [screenSharerId]);

  const initiateConnectionWithPeer = useCallback(async (remoteUserId) => {
    await clientRef.current?.createOffer(remoteUserId);
  }, []);

  const handleUserJoined = useCallback(async (userId) => {
    await clientRef.current?.participantJoined(userId);
  }, []);

  const handleUserLeft = useCallback((userId) => {
    clientRef.current?.participantLeft(userId);
  }, []);

  const connectToExistingParticipants = useCallback(async (participantIds) => {
    await clientRef.current?.joinRoom(participantIds);
  }, []);

  // ── Expose methods to parent via ref ────────────────────────────────────
  useImperativeHandle(ref, () => ({
    handleWebRTCOffer,
    handleWebRTCAnswer,
    handleWebRTCIce,
    handleParticipantState,
    handleUserJoined,
    handleUserLeft,
    connectToExistingParticipants,
  }), [
    handleWebRTCOffer,
    handleWebRTCAnswer,
    handleWebRTCIce,
    handleParticipantState,
    handleUserJoined,
    handleUserLeft,
    connectToExistingParticipants,
  ]);

  // ── Call controls ────────────────────────────────────────────────────────
  const handleToggleAudio = () => {
    const next = !audioEnabled;
    clientRef.current?.toggleAudio(next);
    setAudioEnabled(next);
    signalingChannel?.send({
      type: 'participant_state',
      user_id: userId,
      room_id: roomId,
      is_muted: !next,
      is_video_on: videoEnabled,
      is_screen_sharing: screenSharing,
    });
  };

  const handleToggleVideo = () => {
    const next = !videoEnabled;
    clientRef.current?.toggleVideo(next);
    setVideoEnabled(next);
    signalingChannel?.send({
      type: 'participant_state',
      user_id: userId,
      room_id: roomId,
      is_muted: !audioEnabled,
      is_video_on: next,
      is_screen_sharing: screenSharing,
    });
  };

  const handleToggleScreen = async () => {
    if (screenSharing) {
      clientRef.current?.stopScreenShare();
      setScreenSharing(false);
      setScreenStream(null);
      signalingChannel?.send({
        type: 'participant_state',
        user_id: userId,
        room_id: roomId,
        is_muted: !audioEnabled,
        is_video_on: videoEnabled,
        is_screen_sharing: false,
      });
    } else {
      try {
        const stream = await clientRef.current?.startScreenShare();
        setScreenSharing(true);
        setScreenStream(stream);
        signalingChannel?.send({
          type: 'participant_state',
          user_id: userId,
          room_id: roomId,
          is_muted: !audioEnabled,
          is_video_on: videoEnabled,
          is_screen_sharing: true,
        });
      } catch {
        // Error handled in client.onError
      }
    }
  };

  const handleLeave = () => {
    clientRef.current?.releaseMediaStreams();
    onCallEnd?.();
  };

  // ── Layout ───────────────────────────────────────────────────────────────
  const remoteParticipants = participants.filter((p) => p.id !== userId);
  const activeScreenStream = screenSharing ? screenStream : (screenSharerId ? remoteStreams[screenSharerId] : null);
  const screenSharerName = screenSharing ? (user?.full_name || 'You') : participants.find((p) => p.id === screenSharerId)?.full_name;

  return (
    <div className="flex flex-col h-full bg-bg-base">
      {/* Main content area */}
      <div className="flex-1 flex flex-col md:flex-row gap-2 p-2 sm:p-4 min-h-0 overflow-hidden">
        {/* Screen share takes priority when active */}
        {activeScreenStream ? (
          <div className="flex flex-col gap-2 flex-1 min-h-0">
            <ScreenShareDisplay
              stream={activeScreenStream}
              sharerName={screenSharerName}
              className="flex-1 min-h-0"
            />
            {/* Compact participant strip below screen share */}
            <div className="flex gap-2 h-28 sm:h-36 shrink-0 overflow-x-auto">
              <LocalVideoPreview
                stream={localStream}
                user={user}
                isMuted={!audioEnabled}
                isVideoOff={!videoEnabled}
                className="w-40 sm:w-48 shrink-0 rounded-xl"
              />
              {remoteParticipants.map((p) => {
                const state = participantStates[p.id] || {};
                return (
                  <div key={p.id} className="w-40 sm:w-48 shrink-0">
                    <RemoteVideoGrid
                      participants={[p]}
                      streams={remoteStreams}
                      participantStates={participantStates}
                      connectionQualities={connectionQualities}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* Normal grid layout */
          <div className="flex-1 flex flex-col gap-2 min-h-0">
            {/* Local preview (self) */}
            <div className={remoteParticipants.length === 0 ? 'flex-1' : 'h-1/3 sm:h-40 shrink-0'}>
              <LocalVideoPreview
                stream={localStream}
                user={user}
                isMuted={!audioEnabled}
                isVideoOff={!videoEnabled}
                className="h-full w-full"
              />
            </div>

            {/* Remote participants grid */}
            {remoteParticipants.length > 0 && (
              <div className="flex-1 min-h-0">
                <RemoteVideoGrid
                  participants={remoteParticipants}
                  streams={remoteStreams}
                  participantStates={participantStates}
                  connectionQualities={connectionQualities}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Controls bar */}
      <CallControls
        audioEnabled={audioEnabled}
        videoEnabled={videoEnabled}
        screenSharing={screenSharing}
        onToggleAudio={handleToggleAudio}
        onToggleVideo={handleToggleVideo}
        onToggleScreen={handleToggleScreen}
        onLeave={handleLeave}
      />
    </div>
  );
});

export default VideoCallContainer;
