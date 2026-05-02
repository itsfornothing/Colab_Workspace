import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import videoCallService from '@/lib/videoCallService';
import { useAuth } from '@/hooks/useAuth';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useCallLifecycle } from '@/hooks/useCallLifecycle';
import { useCallStore } from '@/stores/callStore';
import PreCallLobby from '@/components/calls/PreCallLobby';
import VideoCallContainer from '@/components/calls/VideoCallContainer';
import toast from 'react-hot-toast';

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

/**
 * CallRoomPage — refactored to use VideoCallContainer (Task 18.1).
 *
 * Flow:
 *  1. Fetch room details and ICE servers from API
 *  2. Show PreCallLobby before joining
 *  3. Establish WebSocket connection to /ws/calls/:roomId/ for room-level signaling
 *  4. Pass WebSocket send function as signalingChannel to VideoCallContainer
 *  5. Handle incoming signaling messages and forward to VideoCallContainer via refs
 *  6. On leave, call endCall(roomId) from useCallLifecycle and navigate back
 */
export default function CallRoomPage() {
  const { workspaceId, roomId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [joined, setJoined] = useState(false);
  const [participants, setParticipants] = useState([]); // Array of participant objects (excluding self)
  const [iceServers, setIceServers] = useState(null);

  const videoCallContainerRef = useRef(null);

  // ── Call state management (Requirement 5.6, 14.3) ─────────────────────
  const { setCallState, resetCall } = useCallStore();

  // ── Fetch room details ─────────────────────────────────────────────────
  const { data: room } = useQuery({
    queryKey: ['call-room', roomId],
    queryFn: () => videoCallService.getRoom(roomId),
    enabled: !!roomId,
  });

  // ── Fetch ICE servers ──────────────────────────────────────────────────
  useQuery({
    queryKey: ['ice-servers'],
    queryFn: async () => {
      const servers = await videoCallService.getIceServers();
      setIceServers(servers);
      return servers;
    },
    staleTime: 60_000, // Cache for 1 minute
  });

  // ── WebSocket for room-level signaling ────────────────────────────────
  const { send } = useWebSocket({
    url: `${WS_BASE}/ws/calls/${roomId}/`,
    enabled: joined,
    onMessage: {
      user_joined:     handleUserJoined,
      user_left:       handleUserLeft,
      webrtc_offer:    handleWebRTCOffer,
      webrtc_answer:   handleWebRTCAnswer,
      webrtc_ice:      handleWebRTCIce,
      participant_state: handleParticipantState,
      call_end:        handleRemoteCallEnd,
    },
  });

  // ── useCallLifecycle for endCall (Requirement 14.2) ───────────────────
  const { endCall } = useCallLifecycle({ send, workspaceId });

  // ── Signaling message handlers ─────────────────────────────────────────
  function handleUserJoined({ user_id }) {
    // Add to participants list if not already present
    setParticipants((prev) => {
      if (prev.some((p) => p.id === user_id)) return prev;
      // Fetch participant details (or use cached data from room.participants)
      const participant = room?.participants?.find((p) => p.user.id === user_id)?.user || { id: user_id };
      return [...prev, participant];
    });
    // Notify VideoCallContainer to initiate connection
    videoCallContainerRef.current?.handleUserJoined?.(user_id);
  }

  function handleUserLeft({ user_id }) {
    setParticipants((prev) => prev.filter((p) => p.id !== user_id));
    videoCallContainerRef.current?.handleUserLeft?.(user_id);
  }

  async function handleWebRTCOffer({ from_user_id, sdp }) {
    await videoCallContainerRef.current?.handleWebRTCOffer?.(from_user_id, sdp);
  }

  async function handleWebRTCAnswer({ from_user_id, sdp }) {
    await videoCallContainerRef.current?.handleWebRTCAnswer?.(from_user_id, sdp);
  }

  async function handleWebRTCIce({ from_user_id, candidate }) {
    await videoCallContainerRef.current?.handleWebRTCIce?.(from_user_id, candidate);
  }

  function handleParticipantState({ user_id, is_muted, is_video_on, is_screen_sharing }) {
    videoCallContainerRef.current?.handleParticipantState?.(user_id, {
      is_muted,
      is_video_on,
      is_screen_sharing,
    });
  }

  /**
   * Handle call_end from a remote participant (Requirement 14.2).
   * Force-leave the call and clean up.
   */
  async function handleRemoteCallEnd({ room_id }) {
    if (room_id === roomId || !room_id) {
      await performLeave(/* skipApiCall= */ false);
      navigate(`/w/${workspaceId}/calls`);
    }
  }

  // ── Join call ──────────────────────────────────────────────────────────
  const handleJoin = async ({ audioOn, videoOn }) => {
    try {
      // Join the room via API
      await videoCallService.joinRoom(roomId);

      // Fetch current participants
      const participantData = await videoCallService.getParticipants(roomId);
      const otherParticipants = participantData
        .filter((p) => p.user.id !== user.id)
        .map((p) => p.user);
      setParticipants(otherParticipants);

      setJoined(true);
      setCallState('active');

      // Notify other participants via WebSocket
      send({ type: 'user_joined', user_id: user.id, room_id: roomId });

      // Connect to existing participants
      const existingIds = otherParticipants.map((p) => p.id);
      videoCallContainerRef.current?.connectToExistingParticipants?.(existingIds);
    } catch (err) {
      console.error('Failed to join room:', err);
      toast.error('Failed to join call. Please try again.');
    }
  };

  // ── Leave call ─────────────────────────────────────────────────────────
  const performLeave = async (skipApiCall = false) => {
    setJoined(false);

    if (!skipApiCall) {
      // endCall sends call_end WS message + calls leave API + creates CallHistory
      await endCall(roomId);
    } else {
      // Just reset the store state
      resetCall();
    }
  };

  const handleLeave = async () => {
    await performLeave(false);
    navigate(`/w/${workspaceId}/calls`);
  };

  // ── Clean up on unmount ────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (joined) {
        resetCall();
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Render ─────────────────────────────────────────────────────────────
  if (!joined) {
    return (
      <PreCallLobby
        room={room}
        currentUser={user}
        onJoin={handleJoin}
        onCancel={() => navigate(`/w/${workspaceId}/calls`)}
      />
    );
  }

  return (
    <VideoCallContainer
      ref={videoCallContainerRef}
      roomId={roomId}
      userId={user.id}
      user={user}
      participants={participants}
      signalingChannel={{ send }}
      iceServers={iceServers}
      onCallEnd={handleLeave}
    />
  );
}
