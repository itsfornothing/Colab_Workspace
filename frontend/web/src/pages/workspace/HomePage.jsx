import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus, Hash, Video, UserPlus, FileText } from 'lucide-react';
import { format } from 'date-fns';
import api from '@/lib/axiosClient';
import { useAuth } from '@/hooks/useAuth';
import { useWorkspaceStore } from '@/stores/workspaceStore';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';

export default function HomePage() {
  const { workspaceId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { channels } = useWorkspaceStore();

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const firstName = user?.full_name?.split(' ')[0] || user?.email?.split('@')[0] || 'there';

  const { data: activity = [], isLoading: activityLoading } = useQuery({
    queryKey: ['activity', workspaceId],
    queryFn: async () => {
      const { data } = await api.get('/api/notifications/?unread=true&limit=5');
      return data;
    },
  });

  const { data: wsData } = useQuery({
    queryKey: ['workspace-detail', workspaceId],
    queryFn: async () => {
      const { data } = await api.get(`/api/workspaces/${workspaceId}/`);
      return data;
    },
    enabled: !!workspaceId,
  });

  const quickActions = [
    { icon: FileText, label: 'New Document', color: 'text-blue-500', action: () => {} },
    { icon: Hash, label: 'New Channel', color: 'text-green-500', action: () => {} },
    { icon: Video, label: 'Start Call', color: 'text-purple-500', action: () => navigate(`/w/${workspaceId}/calls`) },
    { icon: UserPlus, label: 'Invite People', color: 'text-orange-500', action: () => {} },
  ];

  return (
    <div className="max-w-4xl mx-auto p-6 lg:p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-h1 mb-1">{greeting}, {firstName} 👋</h1>
        <p className="text-[var(--color-text-hint)]">{format(new Date(), 'EEEE, MMMM d')}</p>
      </div>

      {/* Quick actions */}
      <section className="mb-8">
        <h2 className="text-h3 mb-4">Quick actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {quickActions.map(({ icon: Icon, label, color, action }) => (
            <button
              key={label}
              onClick={action}
              className="flex flex-col items-center gap-3 p-4 bg-bg-elevated rounded-xl border border-[var(--color-border)] hover:border-primary hover:shadow-card transition-all group"
            >
              <div className={`w-12 h-12 rounded-xl bg-bg-panel flex items-center justify-center ${color} group-hover:scale-110 transition-transform`}>
                <Icon size={22} />
              </div>
              <span className="text-sm font-medium text-[var(--color-text-body)]">{label}</span>
            </button>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent activity */}
        <div className="lg:col-span-2">
          <h2 className="text-h3 mb-4">Recent activity</h2>
          <div className="bg-bg-elevated rounded-xl border border-[var(--color-border)] divide-y divide-[var(--color-border)]">
            {activityLoading ? (
              [1, 2, 3].map((i) => (
                <div key={i} className="p-4 flex gap-3">
                  <Skeleton className="w-8 h-8 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-3 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                </div>
              ))
            ) : activity.length === 0 ? (
              <div className="p-8 text-center text-[var(--color-text-hint)]">
                <p>No recent activity</p>
              </div>
            ) : (
              activity.map((item) => (
                <div key={item.id} className="p-4 flex gap-3 hover:bg-bg-panel transition-colors cursor-pointer">
                  <div className="w-8 h-8 rounded-full bg-primary-light flex items-center justify-center text-primary text-sm shrink-0">
                    {item.type === 'message' ? '💬' : item.type === 'document' ? '📝' : '🔔'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-[var(--color-text-body)] truncate">{item.body || item.title}</p>
                    <p className="text-xs text-[var(--color-text-hint)] mt-0.5">{item.created_at}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Workspace stats */}
        <div>
          <h2 className="text-h3 mb-4">Workspace</h2>
          <div className="bg-bg-elevated rounded-xl border border-[var(--color-border)] p-4 space-y-3">
            {[
              { label: 'Members', value: wsData?.member_count ?? '—' },
              { label: 'Channels', value: channels.length || '—' },
              { label: 'Documents', value: wsData?.document_count ?? '—' },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-sm text-[var(--color-text-hint)]">{label}</span>
                <span className="font-semibold text-[var(--color-text-heading)]">{value}</span>
              </div>
            ))}
          </div>

          {/* Active channels */}
          <h2 className="text-h3 mt-6 mb-4">Active channels</h2>
          <div className="space-y-2">
            {channels.slice(0, 5).map((ch) => (
              <button
                key={ch.id}
                onClick={() => navigate(`/w/${workspaceId}/chat/${ch.id}`)}
                className="w-full flex items-center gap-2 p-3 bg-bg-elevated rounded-lg border border-[var(--color-border)] hover:border-primary transition-colors text-left"
              >
                <span className="text-[var(--color-text-hint)]">#</span>
                <span className="flex-1 text-sm font-medium truncate">{ch.name}</span>
                {ch.unread_count > 0 && (
                  <span className="bg-danger text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                    {ch.unread_count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
