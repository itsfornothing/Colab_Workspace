/**
 * callStore.js — Global call state management (Zustand)
 *
 * Tracks:
 *  - callState: 'idle' | 'ringing' | 'active' | 'ended'
 *  - activeRoomId: the room the user is currently in (or was invited to)
 *  - incomingCall: { callerId, callerName, callerAvatar, roomId } | null
 *  - invitationStatuses: { [userId]: 'pending' | 'accepted' | 'declined' }
 */

import { create } from 'zustand';

export const useCallStore = create((set) => ({
  // ── State ──────────────────────────────────────────────────────────────
  callState: 'idle',          // 'idle' | 'ringing' | 'active' | 'ended'
  activeRoomId: null,         // string | null
  incomingCall: null,         // { callerId, callerName, callerAvatar, roomId } | null
  invitationStatuses: {},     // { [userId]: 'pending' | 'accepted' | 'declined' }

  // ── Actions ────────────────────────────────────────────────────────────
  setCallState: (callState) => set({ callState }),

  setActiveRoomId: (activeRoomId) => set({ activeRoomId }),

  setIncomingCall: (incomingCall) => set({ incomingCall }),

  setInvitationStatus: (userId, status) =>
    set((s) => ({
      invitationStatuses: { ...s.invitationStatuses, [userId]: status },
    })),

  clearInvitationStatuses: () => set({ invitationStatuses: {} }),

  resetCall: () =>
    set({
      callState: 'idle',
      activeRoomId: null,
      incomingCall: null,
      invitationStatuses: {},
    }),
}));
