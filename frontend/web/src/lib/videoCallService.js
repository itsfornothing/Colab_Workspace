/**
 * videoCallService.js
 *
 * API service module wrapping all video call REST endpoints.
 * All paths are prefixed with /api/chat/ (chat service).
 *
 * Usage:
 *   import videoCallService from '@/lib/videoCallService';
 *   const room = await videoCallService.createRoom('Team standup', workspaceId);
 */

import api from '@/lib/axiosClient';

const BASE = '/api/chat';

const videoCallService = {
  /**
   * Create a new call room.
   * POST /api/chat/rooms/
   * @param {string} name - Room name
   * @param {string} workspaceId - Workspace UUID
   * @returns {Promise<Object>} Created room object
   */
  createRoom: (name, workspaceId) =>
    api.post(`${BASE}/rooms/`, { name, workspace: workspaceId }).then((r) => r.data),

  /**
   * Get details for a specific room.
   * GET /api/chat/rooms/:roomId/
   * @param {string} roomId - Room UUID
   * @returns {Promise<Object>} Room object
   */
  getRoom: (roomId) =>
    api.get(`${BASE}/rooms/${roomId}/`).then((r) => r.data),

  /**
   * List rooms for a workspace.
   * GET /api/chat/rooms/?workspace=:workspaceId
   * @param {string} workspaceId - Workspace UUID
   * @returns {Promise<Array>} Array of room objects
   */
  listRooms: (workspaceId) =>
    api.get(`${BASE}/rooms/`, { params: { workspace: workspaceId } }).then((r) => r.data),

  /**
   * Join a room (adds current user as participant).
   * POST /api/chat/rooms/:roomId/join/
   * @param {string} roomId - Room UUID
   * @returns {Promise<Object>} Updated room or participant object
   */
  joinRoom: (roomId) =>
    api.post(`${BASE}/rooms/${roomId}/join/`).then((r) => r.data),

  /**
   * Leave a room (removes current user as participant, may create CallHistory).
   * POST /api/chat/rooms/:roomId/leave/
   * @param {string} roomId - Room UUID
   * @returns {Promise<Object>} Response data
   */
  leaveRoom: (roomId) =>
    api.post(`${BASE}/rooms/${roomId}/leave/`).then((r) => r.data),

  /**
   * Invite users to a room.
   * POST /api/chat/rooms/:roomId/invite/
   * @param {string} roomId - Room UUID
   * @param {string[]} userIds - Array of user UUIDs to invite
   * @returns {Promise<Object>} Response data
   */
  inviteToRoom: (roomId, userIds) =>
    api.post(`${BASE}/rooms/${roomId}/invite/`, { user_ids: userIds }).then((r) => r.data),

  /**
   * Get participants for a room.
   * GET /api/chat/rooms/:roomId/participants/
   * @param {string} roomId - Room UUID
   * @returns {Promise<Array>} Array of participant objects
   */
  getParticipants: (roomId) =>
    api.get(`${BASE}/rooms/${roomId}/participants/`).then((r) => r.data),

  /**
   * Update a participant's state (muted, video, screen sharing).
   * PATCH /api/chat/rooms/:roomId/participants/:userId/
   * @param {string} roomId - Room UUID
   * @param {string} userId - User UUID
   * @param {Object} state - Partial state: { is_muted, is_video_on, is_screen_sharing }
   * @returns {Promise<Object>} Updated participant object
   */
  updateParticipantState: (roomId, userId, state) =>
    api.patch(`${BASE}/rooms/${roomId}/participants/${userId}/`, state).then((r) => r.data),

  /**
   * Get call history for the current user.
   * GET /api/chat/call-history/
   * @param {Object} [params] - Optional query params (e.g. { page, page_size, workspace })
   * @returns {Promise<Object>} Paginated call history response
   */
  getCallHistory: (params = {}) =>
    api.get(`${BASE}/call-history/`, { params }).then((r) => r.data),

  /**
   * Get STUN/TURN ICE server configuration.
   * GET /api/chat/ice-servers/
   * @returns {Promise<Array>} Array of ICE server config objects
   */
  getIceServers: () =>
    api.get(`${BASE}/ice-servers/`).then((r) => r.data),
};

export default videoCallService;
