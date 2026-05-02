/**
 * frontend/web/src/hooks/useWebSocket.js
 *
 * Authenticated WebSocket hook with:
 *  - JWT passed as ?token= query param (browsers cannot set WS headers)
 *  - Exponential backoff reconnection (1s → 30s max)
 *  - Heartbeat ping every 30s to keep the connection alive through Nginx
 *  - Message queue: messages sent while disconnected are replayed on reconnect
 *  - Type-based message routing via the onMessage map
 *  - Auth failure codes (4001 / 4003) skip reconnection entirely
 *
 * Usage:
 *   const { send, isConnected } = useWebSocket({
 *     url: `wss://api.yourapp.com/ws/chat/${workspaceId}/`,
 *     onMessage: {
 *       message:  (data) => addMessage(data),
 *       typing:   (data) => setTyping(data),
 *       presence: (data) => updatePresence(data),
 *     },
 *   });
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { getTokens } from '../lib/tokenStorage';

const HEARTBEAT_MS  = 30_000;   // 30 s — keep-alive ping interval
const INITIAL_DELAY = 1_000;    // 1 s  — first reconnect delay
const MAX_DELAY     = 30_000;   // 30 s — maximum reconnect delay

export function useWebSocket({ url, onMessage = {}, enabled = true }) {
  const wsRef          = useRef(null);
  const reconnectTimer = useRef(null);
  const heartbeatTimer = useRef(null);
  const backoffRef     = useRef(INITIAL_DELAY);
  const messageQueue   = useRef([]);
  const isMounted      = useRef(true);
  // Stable ref for the handler map (avoids stale closures)
  const handlersRef    = useRef(onMessage);
  handlersRef.current  = onMessage;

  const [isConnected, setIsConnected] = useState(false);
  const [lastError,   setLastError]   = useState(null);

  const connect = useCallback(() => {
    if (!isMounted.current || !enabled) return;

    const { accessToken } = getTokens();
    if (!accessToken) {
      setLastError('No access token — skipping WebSocket connection');
      return;
    }

    const sep   = url.includes('?') ? '&' : '?';
    const wsUrl = `${url}${sep}token=${accessToken}`;
    const ws    = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMounted.current) return;
      setIsConnected(true);
      setLastError(null);
      backoffRef.current = INITIAL_DELAY;

      // Flush any messages queued while disconnected
      while (messageQueue.current.length > 0) {
        ws.send(JSON.stringify(messageQueue.current.shift()));
      }

      // Start heartbeat
      heartbeatTimer.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'heartbeat' }));
        }
      }, HEARTBEAT_MS);
    };

    ws.onmessage = (event) => {
      try {
        const data    = JSON.parse(event.data);
        const handler = handlersRef.current[data.type];
        if (handler) handler(data);
      } catch (e) {
        console.error('[WS] Failed to parse message:', e);
      }
    };

    ws.onerror = () => {
      setLastError('WebSocket connection error');
    };

    ws.onclose = (event) => {
      if (!isMounted.current) return;
      setIsConnected(false);
      clearInterval(heartbeatTimer.current);

      // Auth failure or intentional close — do not reconnect
      if (event.code === 4001 || event.code === 4003 || event.code === 1000) {
        return;
      }

      // Exponential backoff reconnect
      const delay = Math.min(backoffRef.current * 2, MAX_DELAY);
      backoffRef.current    = delay;
      reconnectTimer.current = setTimeout(connect, delay);
    };
  }, [url, enabled]);

  useEffect(() => {
    isMounted.current = true;
    connect();
    return () => {
      isMounted.current = false;
      clearTimeout(reconnectTimer.current);
      clearInterval(heartbeatTimer.current);
      wsRef.current?.close(1000, 'Component unmounted');
    };
  }, [connect]);

  // ── send ──────────────────────────────────────────────────
  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      // Queue for replay when connection resumes
      messageQueue.current.push(data);
    }
  }, []);

  return { send, isConnected, lastError };
}