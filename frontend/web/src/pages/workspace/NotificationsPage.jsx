import { useQuery, useMutation } from '@tanstack/react-query';
import { CheckCheck } from 'lucide-react';
import api from '@/lib/axiosClient';
import { useNotificationStore } from '@/stores/notificationStore';
import NotificationItem from '@/components/notifications/NotificationItem';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';

export default function NotificationsPage() {
  const { notifications, setNotifications, markRead, markAllRead } = useNotificationStore();

  const { isLoading } = useQuery({
    queryKey: ['notifications'],
    queryFn: async () => {
      const { data } = await api.get('/api/notifications/?limit=50');
      setNotifications(data.results || data);
      return data;
    },
  });

  const readMutation = useMutation({
    mutationFn: (id) => api.post(`/api/notifications/${id}/read/`),
    onSuccess: (_, id) => markRead(id),
  });

  const readAllMutation = useMutation({
    mutationFn: () => api.post('/api/notifications/read-all/'),
    onSuccess: () => markAllRead(),
  });

  return (
    <div className="max-w-2xl mx-auto p-6 lg:p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-h1">Notifications</h1>
        <Button variant="ghost" size="sm" onClick={() => readAllMutation.mutate()} disabled={readAllMutation.isPending}>
          <CheckCheck size={16} className="mr-1.5" /> Mark all read
        </Button>
      </div>

      <div className="bg-bg-elevated rounded-xl border border-[var(--color-border)] divide-y divide-[var(--color-border)] overflow-hidden">
        {isLoading ? (
          [1, 2, 3, 4].map((i) => (
            <div key={i} className="flex gap-3 p-4">
              <Skeleton className="w-9 h-9 rounded-full shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </div>
          ))
        ) : notifications.length === 0 ? (
          <div className="py-16 text-center text-[var(--color-text-hint)]">
            <p className="text-3xl mb-3">🔔</p>
            <p>No notifications yet</p>
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
    </div>
  );
}
