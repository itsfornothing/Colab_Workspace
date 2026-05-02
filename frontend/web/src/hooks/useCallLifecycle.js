/**
 * useCallLifecycle.js
 *
 * Hook that orchestrates the full call lifecycle:
 *  - initiateCall(roomName, inviteeIds, workspaceId) — create room, invite, set state to 'ringing'
 *  - acceptCall(roomId, callerId)                    — send call_accept, navigate to room, set 'active'
 *  - declineCall(roomId, callerId)                   — send call_decline, reset state
 *  - endCall(roomId)                                 — send call_end, leave API, cleanup, set 'ended'
 *
 * Handles incoming WebSocket messages:
 *  - call_invite  → sets incomingCall + state 'ringing'
 *  - call_accept  → updates invitation status to 'accepted'
 *  - call_decline → updates invitation status to 'declined'
 *  - call_end     → triggers cleanup, sets state 'ended'
 *
 * Requirements: 5.1, 5.2, 5.6, 1.7, 6.1
 */

import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '@/lib/axiosClient';
import { useCallStore } from '@/stores/callStore';
import toast from 'react-hot-toast';

export function useCallLifecycle({ send, workspaceId } = {}) {
  const navigate = useNavigate();
  const {
    callState,
    activeRoomId,
    incomingCall,
    invitationStatuses,
    setCallState,
    setActiveRoomId,
    setIncomingCall,
    setInvitationStatus,
    clearInvitationStatuses,
    resetCall,
  } = useCallStore();

  // ── 14.1: Initiate a call ──────────────────────────────────────────────
  /**
   * Create a room via API, then send invitations to selected participants.
   * Sets call state to 'ringing' and tracks invitation statuses as 'pending'.
   *
   * @param {string} roomName - Name for the new room
   * @param {string[]} inviteeIds - User IDs to invite
   * @param {string} wsId - Workspace ID (falls back to prop)
   */
  const initiateCall = useCallback(
    async (roomName, inviteeIds = [], wsId) => {
      const wid = wsId || workspaceId;
      try {
        // Create the room
        const { data: room } = await api.post('/api/chat/rooms/', {
          name: roomName,
          workspace: wid,
        });

        setActiveRoomId(room.id);
        setCallState('ringing');
        clearInvitationStatuses();

        // Mark all invitees as pending
        inviteeIds.forEach((uid) => setInvitationStatus(uid, 'pending'));

        // Send REST invitation (backend validates users)
        if (inviteeIds.length > 0) {
          try {
            await api.post(`/api/chat/rooms/${room.id}/invite/`, {
              user_ids: inviteeIds,
            });
          } catch (err) {
            console.warn('REST invite failed, continuing with WS invite:', err);
          }

          // Also send WebSocket call_invite so recipients get real-time notification
          if (send) {
            send({
              type: 'call_invite',
              room_id: room.id,
              invited_user_ids: inviteeIds,
            });
          }
        }

        return room;
      } catch (err) {
        console.error('Failed to initiate call:', err);
        toast.error('Failed to start call. Please try again.');
        resetCall();
        throw err;
      }
    },
    [workspaceId, send, setActiveRoomId, setCallState, clearInvitationStatuses, setInvitationStatus, resetCall],
  );

  // ── 14.1: Accept an incoming call ─────────────────────────────────────
  /**
   * Accept an incoming call invitation.
   * Sends call_accept via WebSocket, sets state to 'active', navigates to room.
   *
   * @param {string} roomId - The room to join
   * @param {string} callerId - The user who initiated the call
   */
  const acceptCall = useCallback(
    (roomId, callerId) => {
      if (send) {
        send({ type: 'call_accept', room_id: roomId, caller_id: callerId });
      }
      setActiveRoomId(roomId);
      setCallState('active');
      setIncomingCall(null);

      if (workspaceId) {
        navigate(`/w/${workspaceId}/calls/${roomId}`);
      }
    },
    [send, workspaceId, navigate, setActiveRoomId, setCallState, setIncomingCall],
  );

  // ── 14.1: Decline an incoming call ────────────────────────────────────
  /**
   * Decline an incoming call invitation.
   * Sends call_decline via WebSocket and resets call state.
   *
   * @param {string} roomId - The room being declined
   * @param {string} callerId - The user who initiated the call
   */
  const declineCall = useCallback(
    (roomId, callerId) => {
      if (send) {
        send({ type: 'call_decline', room_id: roomId, caller_id: callerId });
      }
      setIncomingCall(null);
      // Only reset if we're not already in an active call
      if (callState !== 'active') {
        resetCall();
      }
    },
    [send, callState, setIncomingCall, resetCall],
  );

  // ── 14.2: End a call ──────────────────────────────────────────────────
  /**
   * End the current call:
   *  1. Send call_end via WebSocket (broadcasts to all participants)
   *  2. Call POST /api/chat/rooms/{id}/leave/ (backend creates CallHistory when last person leaves)
   *  3. Set state to 'ended', then reset
   *
   * @param {string} roomId - The room to leave
   */
  const endCall = useCallback(
    async (roomId) => {
      const rid = roomId || activeRoomId;
      if (!rid) return;

      // Broadcast call end to all participants
      if (send) {
        send({ type: 'call_end', room_id: rid });
      }

      // Leave the room via REST API (backend handles ended_at + CallHistory)
      try {
        await api.post(`/api/chat/rooms/${rid}/leave/`);
      } catch (err) {
        // Non-fatal — user may have already left or room may be gone
        console.warn('Leave room API call failed:', err);
      }

      setCallState('ended');

      // Brief delay then reset so UI can show 'ended' state momentarily
      setTimeout(() => {
        resetCall();
      }, 500);
    },
    [activeRoomId, send, setCallState, resetCall],
  );

  // ── 14.3: WebSocket message handlers ──────────────────────────────────
  /**
   * Handle incoming call_invite WebSocket message.
   * Sets incomingCall and transitions state to 'ringing'.
   * If already in an active call, the notification will show busy state.
   */
  const handleCallInvite = useCallback(
    (data) => {
      const { room_id, caller_id, caller_name, caller_avatar } = data;
      setIncomingCall({
        callerId: caller_id,
        callerName: caller_name || 'Someone',
        callerAvatar: caller_avatar || null,
        roomId: room_id,
      });
      // Only transition to ringing if currently idle
      if (callState === 'idle') {
        setCallState('ringing');
      }
    },
    [callState, setIncomingCall, setCallState],
  );

  /**
   * Handle incoming call_accept WebSocket message.
   * Updates invitation status for the accepting user.
   */
  const handleCallAccept = useCallback(
    (data) => {
      const { accepter_id } = data;
      if (accepter_id) {
        setInvitationStatus(accepter_id, 'accepted');
      }
      // If we were ringing (outgoing call), transition to active
      if (callState === 'ringing') {
        setCallState('active');
      }
    },
    [callState, setInvitationStatus, setCallState],
  );

  /**
   * Handle incoming call_decline WebSocket message.
   * Updates invitation status for the declining user.
   */
  const handleCallDecline = useCallback(
    (data) => {
      const { decliner_id, decliner_name } = data;
      if (decliner_id) {
        setInvitationStatus(decliner_id, 'declined');
      }
      if (decliner_name) {
        toast(`${decliner_name} declined the call`, { icon: '📵' });
      }
    },
    [setInvitationStatus],
  );

  /**
   * Handle incoming call_end WebSocket message.
   * Triggers cleanup and sets state to 'ended'.
   */
  const handleCallEnd = useCallback(
    async (data) => {
      const { room_id } = data;
      const rid = room_id || activeRoomId;

      // Leave the room via REST API to ensure CallHistory is created
      if (rid) {
        try {
          await api.post(`/api/chat/rooms/${rid}/leave/`);
        } catch {
          // Non-fatal
        }
      }

      setCallState('ended');
      setTimeout(() => {
        resetCall();
      }, 500);
    },
    [activeRoomId, setCallState, resetCall],
  );

  // ── Return public API ──────────────────────────────────────────────────
  return {
    // State
    callState,
    activeRoomId,
    incomingCall,
    invitationStatuses,

    // Actions
    initiateCall,
    acceptCall,
    declineCall,
    endCall,

    // WebSocket message handlers (to be wired into useWebSocket onMessage map)
    handleCallInvite,
    handleCallAccept,
    handleCallDecline,
    handleCallEnd,
  };
}
