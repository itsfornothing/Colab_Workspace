import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { UserPlus, MoreHorizontal, Shield, UserX } from 'lucide-react';
import api from '@/lib/axiosClient';
import { useAuth } from '@/hooks/useAuth';
import Avatar from '@/components/ui/Avatar';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import Modal from '@/components/ui/Modal';
import Input from '@/components/ui/Input';
import Dropdown from '@/components/ui/Dropdown';
import Skeleton from '@/components/ui/Skeleton';
import toast from 'react-hot-toast';

const ROLE_BADGE = {
  owner: 'warning',
  admin: 'primary',
  member: 'default',
};

export default function MembersPage() {
  const { workspaceId } = useParams();
  const { user: currentUser } = useAuth();
  const qc = useQueryClient();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');

  const { data: members = [], isLoading } = useQuery({
    queryKey: ['members', workspaceId],
    queryFn: async () => {
      const { data } = await api.get(`/api/workspaces/${workspaceId}/members/`);
      return data.results || data;
    },
  });

  const inviteMutation = useMutation({
    mutationFn: (email) => api.post(`/api/workspaces/${workspaceId}/invite/`, { email }),
    onSuccess: () => {
      toast.success('Invitation sent');
      setInviteOpen(false);
      setInviteEmail('');
    },
    onError: () => toast.error('Failed to send invitation'),
  });

  const removeMutation = useMutation({
    mutationFn: (userId) => api.delete(`/api/workspaces/${workspaceId}/members/${userId}/`),
    onSuccess: () => { qc.invalidateQueries(['members', workspaceId]); toast.success('Member removed'); },
    onError: () => toast.error('Failed to remove member'),
  });

  const roleChangeMutation = useMutation({
    mutationFn: ({ userId, role }) => api.patch(`/api/workspaces/${workspaceId}/members/${userId}/`, { role }),
    onSuccess: () => qc.invalidateQueries(['members', workspaceId]),
    onError: () => toast.error('Failed to update role'),
  });

  const isAdmin = members.find((m) => m.user.id === currentUser?.id)?.role === 'admin'
               || members.find((m) => m.user.id === currentUser?.id)?.role === 'owner';

  return (
    <div className="max-w-3xl mx-auto p-6 lg:p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-h1">Members</h1>
          <p className="text-sm text-[var(--color-text-hint)] mt-0.5">{members.length} member{members.length !== 1 ? 's' : ''}</p>
        </div>
        {isAdmin && (
          <Button onClick={() => setInviteOpen(true)} size="sm">
            <UserPlus size={16} className="mr-1.5" /> Invite
          </Button>
        )}
      </div>

      <div className="bg-bg-elevated rounded-xl border border-[var(--color-border)] divide-y divide-[var(--color-border)] overflow-hidden">
        {isLoading ? (
          [1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-3 p-4">
              <Skeleton className="w-10 h-10 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3 w-40" />
                <Skeleton className="h-3 w-24" />
              </div>
            </div>
          ))
        ) : (
          members.map((member) => (
            <div key={member.user.id} className="flex items-center gap-3 p-4">
              <Avatar src={member.user.avatar_url} name={member.user.full_name} size="md" status="online" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-medium text-[var(--color-text-heading)] truncate">{member.user.full_name}</p>
                  <Badge variant={ROLE_BADGE[member.role] || 'default'}>{member.role}</Badge>
                </div>
                <p className="text-xs text-[var(--color-text-hint)] truncate">{member.user.email}</p>
              </div>
              {isAdmin && member.user.id !== currentUser?.id && member.role !== 'owner' && (
                <Dropdown
                  align="right"
                  trigger={
                    <button className="p-1.5 rounded-lg hover:bg-bg-panel text-[var(--color-text-hint)]">
                      <MoreHorizontal size={16} />
                    </button>
                  }
                  items={[
                    {
                      icon: Shield,
                      label: member.role === 'admin' ? 'Remove admin' : 'Make admin',
                      onClick: () => roleChangeMutation.mutate({
                        userId: member.user.id,
                        role: member.role === 'admin' ? 'member' : 'admin',
                      }),
                    },
                    { divider: true },
                    {
                      icon: UserX,
                      label: 'Remove from workspace',
                      danger: true,
                      onClick: () => removeMutation.mutate(member.user.id),
                    },
                  ]}
                />
              )}
            </div>
          ))
        )}
      </div>

      <Modal open={inviteOpen} onClose={() => setInviteOpen(false)} title="Invite Member">
        <div className="space-y-4">
          <Input
            label="Email address"
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="colleague@example.com"
            autoFocus
            onKeyDown={(e) => e.key === 'Enter' && inviteEmail && inviteMutation.mutate(inviteEmail)}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setInviteOpen(false)}>Cancel</Button>
            <Button
              onClick={() => inviteMutation.mutate(inviteEmail)}
              disabled={!inviteEmail || inviteMutation.isPending}
              loading={inviteMutation.isPending}
            >
              Send Invite
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
