"""
DocumentConsumer — Django Channels WebSocket consumer for the collaboration service.

Responsibilities:
  - Authenticate the connection via JWT (set by JWTAuthMiddleware)
  - Enforce view/edit permissions at the WebSocket layer
  - Route Yjs CRDT binary updates and awareness payloads
  - Maintain per-document presence (active editors)
  - Place each consumer in a shard-scoped channel-layer group so
    Redis pub/sub fan-out is bounded per document
  - Deliver operation history (or a snapshot + delta) on connect
  - Handle graceful disconnect (presence cleanup, lock release)
"""

import json
import base64
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

from .crdt_service import (
    save_operation,
    get_operations_since,
    get_latest_snapshot,
)
from .permissions import has_permission
from .presence import set_user_active, remove_user_active, get_active_users
from .lock_service import release_lock
from .sharding import get_shard

logger = logging.getLogger(__name__)


class DocumentConsumer(AsyncWebsocketConsumer):

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    async def connect(self):
        # BUG FIX 1: document_id MUST be assigned before any use of it.
        # Original code called has_permission(self.document_id) before the
        # assignment — guaranteed NameError/AttributeError on every connect.
        self.document_id = self.scope["url_route"]["kwargs"]["document_id"]
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        allowed = await sync_to_async(has_permission)(
            self.user, self.document_id, "view"
        )
        if not allowed:
            await self.close(code=4003)
            return

        # BUG FIX 2: group_name must use the shard-aware prefix.
        # Original code computed group_name at module level (outside the
        # class, referencing self — a crash), then silently re-assigned it
        # inside connect() WITHOUT the shard prefix, so all the sharding
        # logic in sharding.py was completely ignored.
        shard_id = get_shard(self.document_id)
        self.group_name = f"doc_{shard_id}_{self.document_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Mark this user as an active editor in Redis
        await sync_to_async(set_user_active)(self.document_id, self.user.id)

        # Tell the joining client who else is already in the document
        active = await sync_to_async(get_active_users)(self.document_id)
        await self.send(text_data=json.dumps({
            "type": "presence_state",
            "users": active,
        }))

        # Broadcast join event to all other peers in this shard group
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "presence_join",
                "user_id": str(self.user.id),
                "username": str(self.user),
                "sender_channel": self.channel_name,
            }
        )

        # Deliver document state: snapshot + delta or full op log
        await self._send_initial_state()

    async def disconnect(self, close_code):
        if hasattr(self, "document_id") and hasattr(self, "user"):
            await sync_to_async(remove_user_active)(self.document_id, self.user.id)
            # Release any document lock this user held
            await sync_to_async(release_lock)(self.user, self.document_id)

            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "presence_leave",
                    "user_id": str(self.user.id),
                    "username": str(self.user),
                }
            )

        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ------------------------------------------------------------------ #
    # Receive (client → server)                                           #
    # ------------------------------------------------------------------ #

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            await self._send_error("Invalid JSON.")
            return

        event_type = data.get("type")
        handlers = {
            "crdt_update":   self._handle_crdt_update,
            "awareness":     self._handle_awareness,
            "request_state": self._handle_request_state,
            "heartbeat":     self._handle_heartbeat,
        }
        handler = handlers.get(event_type)
        if handler:
            await handler(data)
        else:
            await self._send_error(f"Unknown event type: {event_type!r}")

    # ------------------------------------------------------------------ #
    # Incoming event handlers                                             #
    # ------------------------------------------------------------------ #

    async def _handle_crdt_update(self, data):
        # BUG FIX 3: original code had a redundant nested
        # `if data["type"] == "crdt_update"` inside itself — cleaned up.
        allowed = await sync_to_async(has_permission)(
            self.user, self.document_id, "edit"
        )
        if not allowed:
            await self._send_error("Edit permission required.")
            return

        op_base64 = data.get("operation")
        if not op_base64:
            await self._send_error("crdt_update requires 'operation'.")
            return

        try:
            op_bytes = base64.b64decode(op_base64)
        except Exception:
            await self._send_error("Invalid base64 in 'operation'.")
            return

        await sync_to_async(save_operation)(self.user, self.document_id, op_bytes)

        # Fan-out Yjs update to all peers in this shard group.
        # Include sender_channel so each consumer can skip echoing back
        # to the originator (they already applied the op locally).
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "broadcast_update",
                "operation": op_base64,
                "sender_channel": self.channel_name,
            }
        )

    async def _handle_awareness(self, data):
        """
        Awareness carries live cursor positions, user colours, and
        selection ranges in the Yjs awareness protocol format.
        We fan it out to all peers without persisting it.
        """
        payload = data.get("payload")
        if payload is None:
            await self._send_error("awareness requires 'payload'.")
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "awareness_event",
                "payload": payload,
                "user_id": str(self.user.id),
                "sender_channel": self.channel_name,
            }
        )

    async def _handle_request_state(self, data):
        """
        Explicit state request — used by clients resuming from offline.
        The client may pass a `since` ISO timestamp so we only send delta.
        """
        await self._send_initial_state(since=data.get("since"))

    async def _handle_heartbeat(self, data):
        """Refresh Redis presence TTL; reply with ack."""
        await sync_to_async(set_user_active)(self.document_id, self.user.id)
        await self.send(text_data=json.dumps({"type": "heartbeat_ack"}))

    # ------------------------------------------------------------------ #
    # Outgoing event senders (channel-layer → this WebSocket)            #
    # ------------------------------------------------------------------ #

    async def broadcast_update(self, event):
        # Don't echo back to the originating connection
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            "type": "crdt_update",
            "operation": event["operation"],
        }))

    async def awareness_event(self, event):
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            "type": "awareness",
            "payload": event["payload"],
            "user_id": event.get("user_id"),
        }))

    async def presence_join(self, event):
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            "type": "presence_join",
            "user_id": event["user_id"],
            "username": event["username"],
        }))

    async def presence_leave(self, event):
        await self.send(text_data=json.dumps({
            "type": "presence_leave",
            "user_id": event["user_id"],
            "username": event["username"],
        }))

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    async def _send_initial_state(self, since=None):
        """
        Deliver document state to the client.

        Strategy (snapshot-first):
          1. If a snapshot exists, send it + only operations after the
             snapshot timestamp (or the `since` hint from the client).
             This avoids replaying the full log on every reconnect.
          2. If no snapshot exists, send the full operation log.

        The client is expected to:
          - Apply snapshot via Y.applyUpdate(doc, fromBase64(snapshot))
          - Then apply each delta op in order
        """
        snapshot = await sync_to_async(get_latest_snapshot)(self.document_id)

        if snapshot:
            cutoff = snapshot.updated_at
            snapshot_b64 = base64.b64encode(bytes(snapshot.snapshot)).decode()
            ops_qs = await sync_to_async(get_operations_since)(
                self.document_id, cutoff
            )
            ops = await sync_to_async(list)(ops_qs)
            delta = [base64.b64encode(bytes(op.operation)).decode() for op in ops]

            await self.send(text_data=json.dumps({
                "type": "initial_state",
                "mode": "snapshot",
                "snapshot": snapshot_b64,
                "delta": delta,
            }))
        else:
            ops_qs = await sync_to_async(get_operations_since)(
                self.document_id, since
            )
            ops = await sync_to_async(list)(ops_qs)
            history = [base64.b64encode(bytes(op.operation)).decode() for op in ops]

            await self.send(text_data=json.dumps({
                "type": "initial_state",
                "mode": "full_log",
                "operations": history,
            }))

    async def _send_error(self, detail: str):
        await self.send(text_data=json.dumps({
            "type": "error",
            "detail": detail,
        }))