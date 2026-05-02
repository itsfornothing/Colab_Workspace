import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus, Users } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import api from '@/lib/axiosClient';
import { useWorkspaceStore } from '@/stores/workspaceStore';
import { useAuth } from '@/hooks/useAuth';
import Avatar from '@/components/ui/Avatar';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';

export default function WorkspacePickerPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { setWorkspaces, setCurrentWorkspace } = useWorkspaceStore();

  const { data: workspaces = [], isLoading } = useQuery({
    queryKey: ['workspaces'],
    queryFn: async () => {
      const { data } = await api.get('/api/workspaces/list/');
      return data;
    },
  });

  useEffect(() => {
    if (workspaces.length) setWorkspaces(workspaces);
  }, [workspaces, setWorkspaces]);

  const handleSelect = (ws) => {
    setCurrentWorkspace(ws.id);
    navigate(`/w/${ws.id}/home`);
  };

  return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center p-6">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-8">
          <h1 className="text-h1 mb-2">Your workspaces</h1>
          <p className="text-[var(--color-text-hint)]">Select a workspace to continue</p>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-28 rounded-xl" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            {workspaces.map((ws) => (
              <button
                key={ws.id}
                onClick={() => handleSelect(ws)}
                className="text-left p-5 bg-bg-elevated rounded-xl border border-[var(--color-border)] hover:border-primary hover:shadow-card transition-all group"
              >
                <div className="flex items-start gap-3">
                  <Avatar name={ws.name} size="lg" />
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-[var(--color-text-heading)] group-hover:text-primary transition-colors truncate">
                      {ws.name}
                    </p>
                    <div className="flex items-center gap-1 text-sm text-[var(--color-text-hint)] mt-1">
                      <Users size={13} />
                      <span>{ws.member_count} members</span>
                    </div>
                    {ws.last_active && (
                      <p className="text-xs text-[var(--color-text-hint)] mt-1">
                        Active {formatDistanceToNow(new Date(ws.last_active), { addSuffix: true })}
                      </p>
                    )}
                  </div>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    ws.role === 'admin'
                      ? 'bg-primary-light text-primary'
                      : 'bg-bg-panel text-[var(--color-text-body)]'
                  }`}>
                    {ws.role || 'Member'}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}

        <div className="text-center">
          <Button variant="secondary" className="gap-2">
            <Plus size={16} />
            Create new workspace
          </Button>
        </div>
      </div>
    </div>
  );
}
