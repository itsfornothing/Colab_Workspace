import { useMutation, useQueryClient } from '@tanstack/react-query';
import { X, CheckCheck } from 'lucide-react';
import { motion } from 'framer-motion';
import api from '@/lib/axiosClient';
import { useNotificationStore } from '@/stores/notificationStore';
import { useUiStore } from '@/stores/uiStore';
import NotificationItem from './NotificationItem';

export default function NotificationPanel() {
  const { notifications, markRead, markAllRead } = useNotificationStore();
  const { toggleNotifPanel } = useUiStore();
  const qc = useQueryClient();

  const readMutation = useMutation({
    mutationFn: (id) => api.post(`/api/notifications/${id}/read/`),
    onSuccess: (_, id) => markRead(id),
  });

  const readAllMutation = useMutation({
    mutationFn: () => api.post('/api/notifications/read-all/'),
    onSuccess: () => markAllRead(),
  });

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      exit={{ x: '100%' }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="fixed right-0 top-0 bottom-0 z-50 w-80 bg-bg-elevated border-l border-[var(--color-border)] flex flex-col shadow-modal"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)] shrink-0">
        <h2 className="font-semibold text-[var(--color-text-heading)]">Notifications</h2>
        <div className="flex items-center gap-1">
          <button
            onClick={() => readAllMutation.mutate()}
            className="p-1.5 rounded-lg hover:bg-bg-panel text-[var(--color-text-hint)] hover:text-[var(--color-text-body)]"
            title="Mark all as read"
          >
            <CheckCheck size={16} />
          </button>
          <button
            onClick={toggleNotifPanel}
            className="p-1.5 rounded-lg hover:bg-bg-panel text-[var(--color-text-hint)]"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto divide-y divide-[var(--color-border)]">
        {notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[var(--color-text-hint)] p-8">
            <p className="text-3xl mb-3">🔔</p>
            <p className="font-medium">All caught up!</p>
            <p className="text-sm mt-1">No new notifications</p>
          </div>
        ) : (
          notifications.map((n) => (
            <NotificationItem
              key={n.id}
              notification={n}
              onRead={(id) => !n.is_read && readMutation.mutate(id)}
            />
          ))
        )}
      </div>
    </motion.div>
  );
}
