import { Outlet, useParams, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Menu, WifiOff } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '@/lib/axiosClient';
import { useWorkspaceStore } from '@/stores/workspaceStore';
import { useUiStore } from '@/stores/uiStore';
import Sidebar from '@/components/layout/Sidebar';
import BottomTabBar from '@/components/layout/BottomTabBar';
import NotificationPanel from '@/components/notifications/NotificationPanel';
import CallNotification from '@/components/calls/CallNotification';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useNotificationStore } from '@/stores/notificationStore';
import { useCallLifecycle } from '@/hooks/useCallLifecycle';
import { useCallStore } from '@/stores/callStore';

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export default function WorkspaceShell() {
  const { workspaceId } = useParams();
  const navigate = useNavigate();
  const { setWorkspaces, setCurrentWorkspace, setChannels } = useWorkspaceStore();
  const { sidebarOpen, setSidebarOpen, notifPanelOpen } = useUiStore();
  const { prependNotification, setUnreadCount, incrementUnread } = useNotificationStore();
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  // ── Call state ─────────────────────────────────────────────────────────
  const { callState, incomingCall } = useCallStore();

  // Online/offline detection
  useEffect(() => {
    const on = () => setIsOnline(true);
    const off = () => setIsOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); };
  }, []);

  // Load workspace data
  useQuery({
    queryKey: ['workspaces'],
    queryFn: async () => {
      const { data } = await api.get('/api/workspaces/list/');
      setWorkspaces(data);
      return data;
    },
  });

  useQuery({
    queryKey: ['channels', workspaceId],
    queryFn: async () => {
      const { data } = await api.get(`/api/workspaces/${workspaceId}/channels/`);
      setChannels(data);
      return data;
    },
    enabled: !!workspaceId,
  });

  useEffect(() => {
    if (workspaceId) setCurrentWorkspace(workspaceId);
  }, [workspaceId, setCurrentWorkspace]);

  // ── Call signaling WebSocket (/ws/calls/) ──────────────────────────────
  // This persistent connection receives call invitations regardless of which
  // chat channel (if any) is currently open.
  const { send: callSend } = useWebSocket({
    url: `${WS_BASE}/ws/calls/`,
    onMessage: {
      // Handlers are wired below via useCallLifecycle
      call_invite:  (data) => handleCallInvite(data),
      call_accept:  (data) => handleCallAccept(data),
      call_decline: (data) => handleCallDecline(data),
      call_end:     (data) => handleCallEnd(data),
      heartbeat_ack: () => {},
      connected: () => {},
    },
  });

  // ── Call lifecycle hook ────────────────────────────────────────────────
  const {
    acceptCall,
    declineCall,
    handleCallInvite,
    handleCallAccept,
    handleCallDecline,
    handleCallEnd,
  } = useCallLifecycle({ send: callSend, workspaceId });

  // ── Notifications WS ──────────────────────────────────────────────────
  useWebSocket({
    url: `${WS_BASE}/ws/notifications/`,
    onMessage: {
      notification: (data) => {
        prependNotification(data);
        incrementUnread();
      },
      unread_count: (data) => setUnreadCount(data.count),
      heartbeat_ack: () => {},
    },
  });

  // ── Incoming call handlers ─────────────────────────────────────────────
  const handleAcceptCall = () => {
    if (!incomingCall) return;
    acceptCall(incomingCall.roomId, incomingCall.callerId);
  };

  const handleDeclineCall = () => {
    if (!incomingCall) return;
    declineCall(incomingCall.roomId, incomingCall.callerId);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-bg-base">
      {/* Desktop sidebar */}
      <div className="hidden lg:flex">
        <Sidebar />
      </div>

      {/* Mobile drawer */}
      <AnimatePresence>
        {sidebarOpen && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/40 lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSidebarOpen(false)}
            />
            <motion.div
              className="fixed left-0 top-0 bottom-0 z-50 w-72 lg:hidden"
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ duration: 0.25, ease: 'easeOut' }}
            >
              <Sidebar />
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile top bar */}
        <div className="lg:hidden flex items-center gap-3 px-4 h-14 border-b border-[var(--color-border)] bg-bg-elevated shrink-0">
          <button onClick={() => setSidebarOpen(true)} className="p-1.5 rounded-md hover:bg-bg-panel">
            <Menu size={20} />
          </button>
          <span className="font-semibold text-[var(--color-text-heading)]">Collab</span>
        </div>

        {/* Offline banner */}
        {!isOnline && (
          <div className="flex items-center gap-2 px-4 py-2 bg-warning/10 border-b border-warning/20 text-warning text-sm">
            <WifiOff size={14} />
            Reconnecting... Changes may not sync.
          </div>
        )}

        {/* Page content */}
        <main className="flex-1 overflow-y-auto pb-16 lg:pb-0">
          <Outlet />
        </main>
      </div>

      {/* Notification panel */}
      <AnimatePresence>
        {notifPanelOpen && <NotificationPanel />}
      </AnimatePresence>

      {/* Incoming call notification (Requirement 5.2, 5.6) */}
      <AnimatePresence>
        {incomingCall && (
          <CallNotification
            callerId={incomingCall.callerId}
            callerName={incomingCall.callerName}
            callerAvatar={incomingCall.callerAvatar}
            roomId={incomingCall.roomId}
            isBusy={callState === 'active'}
            onAccept={handleAcceptCall}
            onDecline={handleDeclineCall}
          />
        )}
      </AnimatePresence>

      {/* Mobile bottom nav */}
      <div className="lg:hidden">
        <BottomTabBar />
      </div>
    </div>
  );
}
