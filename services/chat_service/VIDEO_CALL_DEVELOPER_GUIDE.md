# Video Call Developer Guide

This guide covers the architecture, APIs, and configuration of the video call feature in the collab_workspace chat service.

---

## 1. Overview

The video call system uses a **WebRTC mesh topology** for peer-to-peer media transmission, with Django Channels providing the WebSocket signaling layer and a Django REST API for room management.

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   Browser A     │         │  Django Channels │         │   Browser B     │
│  (WebRTC Client)│◄───────►│ (Signaling Server)│◄───────►│  (WebRTC Client)│
└────────┬────────┘         └──────────────────┘         └────────┬────────┘
         │                                                          │
         │                  ┌──────────────────┐                  │
         └─────────────────►│   STUN/TURN      │◄─────────────────┘
                            │   Servers        │
                            └──────────────────┘
                                     │
                            Direct P2P Media Stream
```

**Key design decisions:**

- **Mesh topology**: Each participant connects directly to every other participant. Supports up to 8 participants (beyond that, an SFU architecture would be needed).
- **Signaling via Django Channels**: WebSocket consumers relay SDP offers/answers and ICE candidates between peers. No media passes through the server.
- **Media encryption**: All WebRTC media is automatically encrypted with DTLS-SRTP (RFC 8827) — no application-level configuration required.
- **REST API**: Room lifecycle (create, join, leave, invite) is managed via a standard Django REST Framework API.

---

## 2. WebRTC Client API

The `WebRTCClient` class lives at `frontend/web/src/lib/webrtc/WebRTCClient.js`.

### Constructor

```javascript
const client = new WebRTCClient(roomId, userId, signalingChannel);
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `roomId` | `string` | UUID of the call room |
| `userId` | `string` | UUID of the current user |
| `signalingChannel` | `object` | Object with a `.send(message)` method (typically the WebSocket `send` from `useWebSocket`) |

### Key Methods

#### Connection Management

| Method | Signature | Description |
|--------|-----------|-------------|
| `initializePeerConnection` | `(remoteUserId) → RTCPeerConnection` | Creates a new RTCPeerConnection for the given peer, attaches local stream tracks, and sets up ICE/track event handlers. |
| `createOffer` | `async (remoteUserId) → void` | Creates an SDP offer and sends it via the signaling channel. |
| `handleAnswer` | `async (remoteUserId, answer) → void` | Sets the remote description from an incoming SDP answer. |
| `handleOffer` | `async (remoteUserId, offer) → void` | Handles an incoming SDP offer: sets remote description, creates answer, sends it back. |
| `handleIceCandidate` | `async (remoteUserId, candidate) → void` | Adds an incoming ICE candidate to the peer connection. |
| `closePeerConnection` | `(remoteUserId) → void` | Closes the connection, stops quality monitoring, clears reconnection state, and fires `onRemoteStreamRemoved`. |
| `joinRoom` | `async (existingParticipantIds) → void` | Sequentially creates offers to all existing participants (avoids overwhelming the signaling server). |
| `participantJoined` | `async (newParticipantId) → void` | Called by existing participants when a new user joins — creates an offer to the newcomer. |
| `participantLeft` | `(departedParticipantId) → void` | Closes only the departed participant's connection. |

#### Media Management

| Method | Signature | Description |
|--------|-----------|-------------|
| `getLocalMediaStream` | `async (constraints?) → MediaStream` | Requests camera + microphone access. Defaults to HD (1280×720). Fires `onError` on permission denial. |
| `attachLocalStream` | `(stream) → void` | Attaches a stream to all existing peer connections. |
| `releaseMediaStreams` | `() → void` | Stops all local/screen tracks and closes all peer connections. Call this on unmount. |

#### Call Controls

| Method | Signature | Description |
|--------|-----------|-------------|
| `toggleAudio` | `(enabled: boolean) → void` | Enables or disables all audio tracks on the local stream. |
| `toggleVideo` | `(enabled: boolean) → void` | Enables or disables all video tracks on the local stream. |
| `startScreenShare` | `async () → MediaStream` | Requests screen capture, replaces the video track in all peer connections. |
| `stopScreenShare` | `() → void` | Stops screen capture and restores the original camera track. |

#### Quality & Reconnection

| Method | Signature | Description |
|--------|-----------|-------------|
| `monitorConnectionQuality` | `(remoteUserId) → void` | Starts a 2-second interval that calls `getStats()` and fires `onConnectionQualityChange`. |
| `attemptReconnection` | `async (remoteUserId, maxAttempts=3) → void` | Retries connection with exponential backoff (2^n seconds). Fires `onError('reconnection_failed')` after max attempts. |
| `setIceServers` | `(iceServers) → void` | Overrides the default STUN servers. Validates the config before applying. |

### Event Callbacks

Set these properties on the client instance before calling `getLocalMediaStream()`:

```javascript
client.onRemoteStream = (remoteUserId, stream) => { /* attach stream to video element */ };
client.onRemoteStreamRemoved = (remoteUserId) => { /* remove video element */ };
client.onConnectionQualityChange = (remoteUserId, quality) => {
  // quality: { quality: 'good'|'fair'|'poor', packetLoss, latency, bandwidth }
};
client.onConnectionStateChange = (remoteUserId, state) => { /* 'connected', 'failed', etc. */ };
client.onError = (type, error, remoteUserId?) => {
  // type: 'media_permission_denied' | 'media_device_not_found' | 'peer_connection_error'
  //       | 'ice_candidate_error' | 'screen_share_permission_denied' | 'reconnection_failed'
};
```

---

## 3. Signaling Message Formats

All messages are JSON objects sent over WebSocket. The `type` field determines routing.

### Call Lifecycle Messages

#### `call_invite`
Sent by the caller to invite participants.
```json
{
  "type": "call_invite",
  "room_id": "uuid",
  "invited_user_ids": ["uuid", "uuid"]
}
```

#### `call_accept`
Sent by an invitee to accept the call.
```json
{
  "type": "call_accept",
  "room_id": "uuid",
  "caller_id": "uuid"
}
```

#### `call_decline`
Sent by an invitee to decline the call.
```json
{
  "type": "call_decline",
  "room_id": "uuid",
  "caller_id": "uuid"
}
```

#### `call_end`
Broadcast by any participant to terminate the call for everyone.
```json
{
  "type": "call_end",
  "room_id": "uuid"
}
```

### WebRTC Signaling Messages

#### `webrtc_offer`
SDP offer from the initiating peer.
```json
{
  "type": "webrtc_offer",
  "from_user_id": "uuid",
  "to_user_id": "uuid",
  "room_id": "uuid",
  "sdp": { "type": "offer", "sdp": "v=0\r\n..." }
}
```

#### `webrtc_answer`
SDP answer from the receiving peer.
```json
{
  "type": "webrtc_answer",
  "from_user_id": "uuid",
  "to_user_id": "uuid",
  "room_id": "uuid",
  "sdp": { "type": "answer", "sdp": "v=0\r\n..." }
}
```

#### `webrtc_ice`
ICE candidate exchange.
```json
{
  "type": "webrtc_ice",
  "from_user_id": "uuid",
  "to_user_id": "uuid",
  "room_id": "uuid",
  "candidate": {
    "candidate": "candidate:...",
    "sdpMid": "0",
    "sdpMLineIndex": 0
  }
}
```

### Participant State

#### `participant_state`
Broadcast when a participant changes their mute/video/screen-share state.
```json
{
  "type": "participant_state",
  "user_id": "uuid",
  "room_id": "uuid",
  "is_muted": false,
  "is_video_on": true,
  "is_screen_sharing": false
}
```

---

## 4. REST API Endpoints

All endpoints are prefixed with `/api/chat/` and require JWT authentication (`Authorization: Bearer <token>`).

### Rooms

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat/rooms/` | Create a new call room |
| `GET` | `/api/chat/rooms/` | List rooms (filter by `?workspace=<uuid>`) |
| `GET` | `/api/chat/rooms/<room_id>/` | Get room details |
| `POST` | `/api/chat/rooms/<room_id>/join/` | Join a room (adds current user as participant) |
| `POST` | `/api/chat/rooms/<room_id>/leave/` | Leave a room (creates CallHistory when last participant leaves) |
| `POST` | `/api/chat/rooms/<room_id>/invite/` | Invite users to a room |
| `GET` | `/api/chat/rooms/<room_id>/participants/` | List current participants |
| `PATCH` | `/api/chat/rooms/<room_id>/participants/<user_id>/` | Update participant state |

#### Create Room — Request Body
```json
{
  "name": "Team standup",
  "workspace": "workspace-uuid"
}
```

#### Create Room — Response
```json
{
  "id": "room-uuid",
  "name": "Team standup",
  "workspace_id": "workspace-uuid",
  "is_active": true,
  "participant_count": 1,
  "max_participants": 8,
  "created_at": "2024-01-15T10:00:00Z",
  "ended_at": null
}
```

#### Join Room — Response
Returns the updated room object. Returns `400` if the room is at capacity.

#### Invite — Request Body
```json
{
  "user_ids": ["uuid1", "uuid2"]
}
```

#### Update Participant State — Request Body
```json
{
  "is_muted": true,
  "is_video_on": false,
  "is_screen_sharing": false
}
```

### Call History

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/chat/call-history/` | Get call history for the current user |

Query parameters: `page`, `page_size`, `workspace`

#### Response
```json
{
  "count": 42,
  "next": "http://...",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "room": { "id": "uuid", "name": "Team standup" },
      "started_at": "2024-01-15T10:00:00Z",
      "ended_at": "2024-01-15T10:45:00Z",
      "duration_seconds": 2700,
      "participant_count": 4
    }
  ]
}
```

### ICE Servers

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/chat/ice-servers/` | Get STUN/TURN server configuration |

#### Response
```json
[
  { "urls": "stun:stun.l.google.com:19302" },
  { "urls": "stun:stun1.l.google.com:19302" }
]
```

---

## 5. Frontend Component Guide

### `VideoCallContainer`

The top-level call UI component. Manages the `WebRTCClient` lifecycle and renders all sub-components.

**File**: `frontend/web/src/components/calls/VideoCallContainer.jsx`

**Props:**

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `roomId` | `string` | ✅ | UUID of the call room |
| `userId` | `string` | ✅ | Current user's UUID |
| `user` | `object` | ✅ | Current user `{ id, full_name, avatar_url }` |
| `participants` | `Array` | — | Other participants (excluding self) |
| `signalingChannel` | `object` | ✅ | Object with `.send(message)` method |
| `iceServers` | `Array` | — | ICE server config (falls back to Google STUN) |
| `onCallEnd` | `Function` | — | Called when the user clicks Leave |

**Ref methods** (use `forwardRef` + `useImperativeHandle`):

```javascript
const containerRef = useRef(null);
// ...
<VideoCallContainer ref={containerRef} ... />

// Then call:
containerRef.current.handleWebRTCOffer(fromUserId, sdp);
containerRef.current.handleWebRTCAnswer(fromUserId, sdp);
containerRef.current.handleWebRTCIce(fromUserId, candidate);
containerRef.current.handleParticipantState(userId, state);
containerRef.current.handleUserJoined(userId);
containerRef.current.handleUserLeft(userId);
containerRef.current.connectToExistingParticipants(participantIds);
```

**Usage example:**

```jsx
import VideoCallContainer from '@/components/calls/VideoCallContainer';
import { useWebSocket } from '@/hooks/useWebSocket';

const { send } = useWebSocket({ url: `${WS_BASE}/ws/calls/${roomId}/`, enabled: joined });

<VideoCallContainer
  ref={containerRef}
  roomId={roomId}
  userId={user.id}
  user={user}
  participants={otherParticipants}
  signalingChannel={{ send }}
  iceServers={iceServers}
  onCallEnd={handleLeave}
/>
```

---

### `CallNotification`

Displays an incoming call notification with accept/decline buttons.

**File**: `frontend/web/src/components/calls/CallNotification.jsx`

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `callerId` | `string` | UUID of the caller |
| `callerName` | `string` | Display name of the caller |
| `callerAvatar` | `string?` | Avatar URL (optional) |
| `roomId` | `string` | Room UUID to join on accept |
| `isBusy` | `boolean` | If true, shows "busy" indicator instead of accept button |
| `onAccept` | `Function` | Called when user clicks Accept |
| `onDecline` | `Function` | Called when user clicks Decline |

Auto-dismisses after 30 seconds if not answered (Requirement 5.7).

---

### `CallHistoryList`

Fetches and displays the user's call history.

**File**: `frontend/web/src/components/calls/CallHistoryList.jsx`

No required props — fetches data internally via React Query. Displays date, participants, duration, and recording links where available.

---

### `useCallLifecycle` Hook

Orchestrates the full call lifecycle.

**File**: `frontend/web/src/hooks/useCallLifecycle.js`

**Usage:**

```javascript
const {
  // State
  callState,        // 'idle' | 'ringing' | 'active' | 'ended'
  activeRoomId,
  incomingCall,     // { callerId, callerName, callerAvatar, roomId } | null
  invitationStatuses, // { [userId]: 'pending' | 'accepted' | 'declined' }

  // Actions
  initiateCall,     // async (roomName, inviteeIds, workspaceId) → room
  acceptCall,       // (roomId, callerId) → void
  declineCall,      // (roomId, callerId) → void
  endCall,          // async (roomId) → void

  // WebSocket message handlers (wire into useWebSocket onMessage map)
  handleCallInvite,
  handleCallAccept,
  handleCallDecline,
  handleCallEnd,
} = useCallLifecycle({ send, workspaceId });
```

**Wire the handlers in `useWebSocket`:**

```javascript
useWebSocket({
  url: `${WS_BASE}/ws/calls/`,
  onMessage: {
    call_invite:  handleCallInvite,
    call_accept:  handleCallAccept,
    call_decline: handleCallDecline,
    call_end:     handleCallEnd,
  },
});
```

---

## 6. Configuration Reference

All settings live in `services/chat_service/chat_service/settings.py`.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `CHANNEL_LAYERS` | `dict` | Redis on `localhost:6379/0` | Django Channels layer. Must use Redis for multi-process deployments. |
| `WEBRTC_ICE_SERVERS` | `list` | Google STUN servers | ICE server config returned by the `/api/chat/ice-servers/` endpoint. |
| `WEBRTC_REQUIRE_SECURE_SIGNALING` | `bool` | `not DEBUG` | When `True`, logs a warning if a non-WSS WebSocket connection is detected. |
| `VIDEO_CALL_MAX_PARTICIPANTS` | `int` | `8` | Maximum participants per call room. Overridable via `VIDEO_CALL_MAX_PARTICIPANTS` env var. |
| `VIDEO_CALL_HISTORY_RETENTION_DAYS` | `int` | `90` | Days to retain call history records. Overridable via `VIDEO_CALL_HISTORY_RETENTION_DAYS` env var. |
| `STUN_SERVERS` | `list` | Google STUN servers | Separate STUN server list for clarity (mirrors `WEBRTC_ICE_SERVERS` STUN entries). |

**Environment variables** (see `.env.local.example` for the full list):

```bash
VIDEO_CALL_MAX_PARTICIPANTS=8
VIDEO_CALL_HISTORY_RETENTION_DAYS=90
REDIS_URL=redis://localhost:6379/0
TURN_SERVER_URL=turn:your-turn-server.example.com:3478
TURN_SERVER_USERNAME=your-username
TURN_SERVER_CREDENTIAL=your-credential
```

---

## 7. Troubleshooting Guide

### Camera/Microphone Permission Denied

**Symptom**: `onError` fires with type `media_permission_denied`. Users see "Camera/microphone access denied."

**Causes & Solutions**:
- Browser blocked the permission prompt. Open browser settings → Site permissions → Camera/Microphone → Allow for this site.
- HTTPS required: browsers only grant media permissions on `https://` or `localhost`. Ensure your dev server uses HTTPS or is accessed via `localhost`.
- Check `navigator.permissions.query({ name: 'camera' })` in the browser console to inspect current permission state.

---

### ICE Connection Failures (NAT Traversal)

**Symptom**: Peer connections get stuck in `checking` state and eventually fail. `onError` fires with `peer_connection_error`.

**Causes & Solutions**:
- **Symmetric NAT**: Google STUN servers alone cannot traverse symmetric NAT. Deploy a TURN server (e.g. coturn) and add it to `WEBRTC_ICE_SERVERS` in settings.
- **Firewall blocking UDP**: TURN with TCP fallback (`turns:` scheme) can help. Ensure port 3478 (UDP/TCP) is open.
- **ICE candidate gathering timeout**: Check browser console for `ICE gathering state: complete` — if it never fires, the STUN server may be unreachable.

**Quick test**: Open `chrome://webrtc-internals/` during a call to inspect ICE candidate pairs and connection states.

---

### WebSocket Connection Issues

**Symptom**: Signaling messages are not delivered. `useWebSocket` shows `isConnected: false`.

**Causes & Solutions**:
- **Token expired**: The WebSocket URL includes `?token=<jwt>`. If the token expires mid-call, the connection will close with code `4001`. The hook does not auto-reconnect on auth failures — the user needs to refresh.
- **Nginx/proxy not configured for WebSocket**: Ensure your reverse proxy passes `Upgrade` and `Connection` headers:
  ```nginx
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  ```
- **Redis not running**: Django Channels requires Redis for the channel layer. Check `REDIS_URL` and that the Redis service is up.

---

### Room Capacity Errors

**Symptom**: `POST /api/chat/rooms/<id>/join/` returns `400 Bad Request` with `"Room is at capacity"`.

**Cause**: The room already has `VIDEO_CALL_MAX_PARTICIPANTS` (default: 8) active participants.

**Solutions**:
- Increase `VIDEO_CALL_MAX_PARTICIPANTS` in settings (note: mesh topology degrades above 8).
- The frontend `CallRoomPage` should handle this error and show a toast notification.

---

### Reconnection Behavior

The `WebRTCClient` automatically attempts reconnection when:
- `iceConnectionState` transitions to `failed` or `disconnected`
- `connectionState` transitions to `failed`

**Reconnection strategy**: Exponential backoff — waits 2s, then 4s, then 8s before each attempt. After 3 failed attempts, `onError('reconnection_failed')` fires and the peer connection is closed.

**To debug**: Check the browser console for `[WebRTCClient] Reconnection attempt N for <userId> in Xms` log messages.

If reconnection consistently fails, the most likely cause is a TURN server issue (see ICE Connection Failures above).
