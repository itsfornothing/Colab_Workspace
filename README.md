# Colaba Workspace

A real-time collaboration platform built with a microservices backend and a cross-platform Flutter mobile app. Teams can write documents together, chat, jump on video calls, manage tasks, and share files — all in one place.

---

## What it does

| Feature | Description |
|---|---|
| **Collaborative documents** | Multiple people edit the same document simultaneously. Changes sync in real time via WebSocket + CRDT. Active editors appear as colored avatars. Version history lets you roll back any change. |
| **Rich text editing** | Full formatting toolbar (bold, italic, headers, lists, code blocks, undo/redo) powered by `flutter_quill` on mobile and a custom Quill.js editor on web. |
| **Real-time chat** | Workspace channels and direct messages with file attachments, typing indicators, and full message history backed by Elasticsearch. |
| **Video calls** | WebRTC mesh calls (up to 8 participants). Screen sharing, mute/unmute, camera toggle, connection quality indicators, and automatic reconnection with exponential backoff. |
| **Task management** | Create tasks, assign them to workspace members, update status, set due dates, and get notified when deadlines approach. |
| **File management** | Upload, browse, preview, and share files. Full-text search powered by Elasticsearch. |
| **Workspaces** | Create isolated workspaces, invite members, and manage roles and permissions. |
| **Push notifications** | Real-time in-app notifications and push notifications (Firebase) for mentions, task assignments, and call invites. |
| **Authentication** | JWT-based auth with secure token storage, refresh token rotation, login, registration, and password reset. |

---

## Architecture

The platform is split into six independent Django services, a Flutter mobile app, a React web app, and an nginx gateway that ties everything together.

```
                        ┌─────────────────────────────────┐
                        │         nginx Gateway           │
                        │  TLS termination · rate limiting │
                        │  JWT auth_request · WebSocket   │
                        └──────────────┬──────────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
   ┌──────▼──────┐             ┌───────▼──────┐            ┌───────▼──────┐
   │ User Service│             │  Workspace   │            │    Chat      │
   │  :8001      │             │  Service     │            │  Service     │
   │  Auth · JWT │             │  :8000       │            │  :8002       │
   │  Profiles   │             │  Workspaces  │            │  Messaging   │
   └──────┬──────┘             │  Tasks       │            │  Video calls │
          │                    │  Members     │            │  WebRTC sig. │
          │                    └──────┬───────┘            └──────┬───────┘
          │                           │                           │
   ┌──────▼──────┐             ┌──────▼───────┐           ┌──────▼───────┐
   │Collaboration│             │Notification  │           │    Media     │
   │  Service    │             │  Service     │           │  Service     │
   │  :8003      │             │  :8005       │           │  :8004       │
   │  Docs · CRDT│             │  Push · FCM  │           │  Files       │
   │  WebSocket  │             │  Real-time   │           │  Uploads     │
   └──────┬──────┘             └──────┬───────┘           └──────┬───────┘
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                  │
             ┌──────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
             │  PostgreSQL  │  │    Redis     │  │Elasticsearch │
             │  (per-svc DB)│  │  Cache · WS  │  │  Search      │
             └─────────────┘  └──────────────┘  └──────────────┘
```

### Services

| Service | Port | Stack | Responsibility |
|---|---|---|---|
| **User Service** | 8001 | Django + DRF | Registration, login, JWT issuance, user profiles |
| **Workspace Service** | 8000 | Django + DRF | Workspaces, members, roles, tasks |
| **Chat Service** | 8002 | Django Channels | Messaging, video call rooms, WebRTC signaling |
| **Collaboration Service** | 8003 | Django Channels | Document CRUD, real-time CRDT sync over WebSocket |
| **Notification Service** | 8005 | Django + DRF | In-app and push notifications via Firebase |
| **Media Service** | 8004 | Django + DRF | File uploads, storage, search |

### Frontend

| Client | Stack | Notes |
|---|---|---|
| **Mobile app** | Flutter 3 · Riverpod · flutter_quill · flutter_webrtc | iOS and Android |
| **Web app** | React · Vite · Zustand · Tailwind CSS | Full feature parity with mobile |

### Infrastructure

- **Gateway**: nginx with TLS termination, JWT `auth_request` subrequests, rate limiting, WebSocket proxying, and CORS
- **Message broker / cache**: Redis 7 (separate DBs for channel layer, cache, and Celery)
- **Search**: Elasticsearch 8 (message search, file search)
- **Databases**: PostgreSQL 16 — one isolated database per service

---

## Project structure

```
collab_workspace/
├── services/
│   ├── user_service/          # Auth, profiles
│   ├── workspace_service/     # Workspaces, tasks, members
│   ├── chat_service/          # Chat, video calls, WebRTC signaling
│   ├── collaboration_service/ # Documents, real-time CRDT sync
│   ├── notification_service/  # Push & in-app notifications
│   └── media_service/         # File uploads & storage
├── frontend/
│   ├── mobile/mobile_app/     # Flutter app (iOS + Android)
│   └── web/                   # React + Vite web app
├── gateway/                   # nginx config (TLS, routing, rate limits)
├── infrastructure/            # Docker Compose for local infra
├── shared/                    # Shared Python event bus utilities
├── scripts/                   # Start/stop and deploy scripts
├── tests/                     # Top-level integration tests
└── docker-compose.yml         # Full stack local development
```

---

## Getting started

### Prerequisites

- Docker and Docker Compose
- Flutter SDK ≥ 3.0 (for mobile development)
- Node.js ≥ 18 (for web development)

### Run the full stack locally

```bash
# Clone the repo
git clone https://github.com/itsfornothing/Colaba_Workspace.git
cd Colaba_Workspace

# Copy environment files for each service
cp services/user_service/.env.local.example         services/user_service/.env.local
cp services/chat_service/.env.local.example         services/chat_service/.env.local
cp services/collaboration_service/.env.local.example services/collaboration_service/.env.local
cp services/notification_service/.env.local.example  services/notification_service/.env.local
cp services/media_service/.env.local.example         services/media_service/.env.local
cp services/workspace_service/.env.local.example     services/workspace_service/.env.local

# Start everything
docker-compose up -d
```

Services will be available at:

| Service | URL |
|---|---|
| Gateway (HTTP → HTTPS redirect) | `http://localhost` |
| User Service | `http://localhost:8001` |
| Workspace Service | `http://localhost:8000` |
| Chat Service | `http://localhost:8002` |
| Collaboration Service | `http://localhost:8003` |
| Notification Service | `http://localhost:8005` |
| Media Service | `http://localhost:8004` |

### Run the Flutter mobile app

```bash
cd frontend/mobile/mobile_app

# Install dependencies
flutter pub get

# Copy and configure the environment file
cp .env.example .env
# Edit .env and set your backend IP/host

# Run on a connected device or simulator
flutter run
```

### Run the web app

```bash
cd frontend/web

npm install
npm run dev
```

---

## Real-time collaboration — how it works

When a user opens a document, the Flutter app:

1. Fetches the current document content via `GET /api/docs/{id}/`
2. Connects to the WebSocket at `ws://{host}:8003/ws/docs/{id}/?token={jwt}`
3. Sends `crdt_update` events (base64-encoded Quill delta) as the user types
4. Receives `crdt_update` events from other editors and applies them to the local document
5. Tracks collaborator presence via `participant_joined` / `participant_left` events

The collaboration service uses Django Channels with a Redis channel layer to fan out updates to all connected clients in the same document group.

---

## Video calls — how it works

Video calls use a **WebRTC mesh topology** — media flows directly between browsers, never through the server.

1. A user creates a room via `POST /api/chat/rooms/`
2. Invitees receive a `call_invite` WebSocket message
3. On accept, each participant connects to the signaling WebSocket at `ws://{host}/ws/calls/`
4. The `WebRTCClient` exchanges SDP offers/answers and ICE candidates through the signaling server
5. Once ICE negotiation completes, media streams flow peer-to-peer (DTLS-SRTP encrypted)
6. The client monitors connection quality every 2 seconds and attempts reconnection with exponential backoff on failure

Supports up to 8 participants. Screen sharing replaces the video track in all active peer connections without dropping the call.

---

## API overview

All API endpoints are prefixed with `/api/` and require `Authorization: Bearer <jwt>` except for auth endpoints.

| Prefix | Service | Key endpoints |
|---|---|---|
| `/api/auth/` | User | `POST /register`, `POST /login`, `POST /token/refresh` |
| `/api/users/` | User | `GET /me`, `PATCH /me`, `GET /{id}/` |
| `/api/workspaces/` | Workspace | CRUD workspaces, members, tasks |
| `/api/chat/` | Chat | Rooms, messages, call history, ICE servers |
| `/api/docs/` | Collaboration | CRUD documents, version history |
| `/api/notifications/` | Notification | List, mark read, preferences |
| `/api/media/` | Media | Upload, list, search files |

WebSocket endpoints:

| Path | Service | Purpose |
|---|---|---|
| `ws://{host}/ws/docs/{doc_id}/` | Collaboration | Real-time document sync |
| `ws://{host}/ws/calls/` | Chat | Video call signaling |
| `ws://{host}/ws/chat/{room_id}/` | Chat | Real-time messaging |

---

## Tech stack

**Backend**
- Python 3.13 · Django 5 · Django REST Framework
- Django Channels 4 + channels-redis (WebSocket layer)
- Gunicorn + UvicornWorker (ASGI)
- PostgreSQL 16 · Redis 7 · Elasticsearch 8
- Celery (background tasks)
- Firebase Admin SDK (push notifications)

**Mobile**
- Flutter 3 · Dart
- Riverpod (state management)
- flutter_quill (rich text editor)
- flutter_webrtc (video calls)
- web_socket_channel (WebSocket client)
- flutter_secure_storage (JWT storage)

**Web**
- React 18 · Vite
- Zustand (state management)
- Tailwind CSS
- WebRTC (native browser API)

**Infrastructure**
- nginx (gateway, TLS, rate limiting)
- Docker + Docker Compose
- Prometheus + Grafana (monitoring)

---

## What's not pushed yet

- `frontend/mobile/` — the Flutter mobile app (iOS + Android)

This will be pushed separately. Everything else is in the `architecture` branch.

---

## License

MIT
