# WebRTC Integration Guide

Quick reference for integrating video calls into a page using the existing components and hooks.

---

## Using `VideoCallContainer` in a Page

`VideoCallContainer` is a `forwardRef` component that manages the full call UI and WebRTC lifecycle. Mount it after the user has joined the call.

```jsx
import { useRef } from 'react';
import VideoCallContainer from '@/components/calls/VideoCallContainer';

function MyCallPage({ roomId, user, participants, signalingChannel, iceServers }) {
  const containerRef = useRef(null);

  const handleCallEnd = () => {
    // Navigate away or clean up
  };

  return (
    <VideoCallContainer
      ref={containerRef}
      roomId={roomId}
      userId={user.id}
      user={user}
      participants={participants}       // Array of other participants (excluding self)
      signalingChannel={signalingChannel} // { send: (message) => void }
      iceServers={iceServers}           // Optional — falls back to Google STUN
      onCallEnd={handleCallEnd}
    />
  );
}
```

The component handles:
- Acquiring local camera/microphone via `WebRTCClient.getLocalMediaStream()`
- Rendering `LocalVideoPreview`, `RemoteVideoGrid`, `ScreenShareDisplay`, and `CallControls`
- Sending `participant_state` messages when the user mutes/unmutes or toggles video

---

## Wiring WebSocket Signaling

Use the `useWebSocket` hook to establish the room-level signaling connection. Forward incoming messages to `VideoCallContainer` via its ref methods.

```jsx
import { useRef } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import VideoCallContainer from '@/components/calls/VideoCallContainer';

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

function CallRoomPage({ roomId, user, participants }) {
  const containerRef = useRef(null);

  const { send } = useWebSocket({
    url: `${WS_BASE}/ws/calls/${roomId}/`,
    enabled: true, // set to false until user joins
    onMessage: {
      // New participant joined — initiate WebRTC connection
      user_joined: ({ user_id }) => {
        containerRef.current?.handleUserJoined(user_id);
      },
      // Participant left — close their connection
      user_left: ({ user_id }) => {
        containerRef.current?.handleUserLeft(user_id);
      },
      // WebRTC signaling
      webrtc_offer: ({ from_user_id, sdp }) => {
        containerRef.current?.handleWebRTCOffer(from_user_id, sdp);
      },
      webrtc_answer: ({ from_user_id, sdp }) => {
        containerRef.current?.handleWebRTCAnswer(from_user_id, sdp);
      },
      webrtc_ice: ({ from_user_id, candidate }) => {
        containerRef.current?.handleWebRTCIce(from_user_id, candidate);
      },
      // Participant mute/video state
      participant_state: ({ user_id, is_muted, is_video_on, is_screen_sharing }) => {
        containerRef.current?.handleParticipantState(user_id, {
          is_muted, is_video_on, is_screen_sharing,
        });
      },
      // Remote participant ended the call
      call_end: ({ room_id }) => {
        // Navigate away
      },
    },
  });

  return (
    <VideoCallContainer
      ref={containerRef}
      roomId={roomId}
      userId={user.id}
      user={user}
      participants={participants}
      signalingChannel={{ send }}
      onCallEnd={() => { /* navigate back */ }}
    />
  );
}
```

After the user joins, connect to existing participants:

```javascript
// After joining the room and fetching participants:
const existingIds = otherParticipants.map((p) => p.id);
containerRef.current?.connectToExistingParticipants(existingIds);
```

---

## Using `useCallLifecycle`

`useCallLifecycle` orchestrates the full call lifecycle — creating rooms, sending invitations, accepting/declining calls, and ending calls.

```javascript
import { useCallLifecycle } from '@/hooks/useCallLifecycle';

// In WorkspaceShell (persistent connection for incoming calls):
const { send: callSend } = useWebSocket({
  url: `${WS_BASE}/ws/calls/`,
  onMessage: {
    call_invite:  (data) => handleCallInvite(data),
    call_accept:  (data) => handleCallAccept(data),
    call_decline: (data) => handleCallDecline(data),
    call_end:     (data) => handleCallEnd(data),
  },
});

const {
  initiateCall,
  acceptCall,
  declineCall,
  endCall,
  handleCallInvite,
  handleCallAccept,
  handleCallDecline,
  handleCallEnd,
  callState,
  incomingCall,
  invitationStatuses,
} = useCallLifecycle({ send: callSend, workspaceId });
```

### Initiating a Call

```javascript
// Creates a room, invites users, sets callState to 'ringing'
const room = await initiateCall('Team standup', ['user-uuid-1', 'user-uuid-2'], workspaceId);
navigate(`/w/${workspaceId}/calls/${room.id}`);
```

### Accepting an Incoming Call

```javascript
// Sends call_accept via WS, navigates to the room, sets callState to 'active'
acceptCall(incomingCall.roomId, incomingCall.callerId);
```

### Ending a Call

```javascript
// Sends call_end via WS, calls POST /api/chat/rooms/:id/leave/, resets state
await endCall(roomId);
navigate(`/w/${workspaceId}/calls`);
```

---

## Complete Call Flow

Here is the sequence of events for a two-user call:

```
User A                          Signaling Server              User B
  │                                    │                         │
  │── POST /api/chat/rooms/ ──────────►│                         │
  │◄─ { id: roomId } ─────────────────│                         │
  │                                    │                         │
  │── WS: call_invite ────────────────►│──── call_invite ───────►│
  │                                    │                         │
  │                                    │◄─── call_accept ────────│
  │◄─ call_accept ─────────────────────│                         │
  │                                    │                         │
  │  [User B navigates to /calls/roomId]                         │
  │                                    │                         │
  │  [Both join WebSocket /ws/calls/roomId/]                     │
  │                                    │                         │
  │── WS: user_joined ────────────────►│──── user_joined ───────►│
  │                                    │                         │
  │◄─ user_joined (User B) ────────────│                         │
  │                                    │                         │
  │── WS: webrtc_offer ───────────────►│──── webrtc_offer ──────►│
  │                                    │                         │
  │◄─ webrtc_answer ───────────────────│◄─── webrtc_answer ──────│
  │                                    │                         │
  │── WS: webrtc_ice ─────────────────►│──── webrtc_ice ────────►│
  │◄─ webrtc_ice ──────────────────────│◄─── webrtc_ice ─────────│
  │                                    │                         │
  │  [P2P media stream established]                              │
  │◄══════════════════════════════════════════════════════════════│
  │                                    │                         │
  │── WS: call_end ───────────────────►│──── call_end ──────────►│
  │── POST /api/chat/rooms/:id/leave/ ►│                         │
  │                                    │◄─ POST /rooms/:id/leave/─│
  │                                    │  [CallHistory created]  │
```
