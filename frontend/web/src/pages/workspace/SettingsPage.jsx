import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Save, Trash2, AlertTriangle } from 'lucide-react';
import api from '@/lib/axiosClient';
import { useAuth } from '@/hooks/useAuth';
import { useWorkspaceStore } from '@/stores/workspaceStore';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import Skeleton from '@/components/ui/Skeleton';
import toast from 'react-hot-toast';

export default function SettingsPage() {
  const { workspaceId } = useParams();
  const { user } = useAuth();
  const { workspaces } = useWorkspaceStore();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState('');

  const { data: ws, isLoading } = useQuery({
    queryKey: ['workspace-detail', workspaceId],
    queryFn: async () => {
      const { data } = await api.get(`/api/workspaces/${workspaceId}/`);
      setName(data.name);
      setDescription(data.description || '');
      return data;
    },
    enabled: !!workspaceId,
  });

  const updateMutation = useMutation({
    mutationFn: () => api.patch(`/api/workspaces/${workspaceId}/`, { name, description }),
    onSuccess: () => toast.success('Settings saved'),
    onError: () => toast.error('Failed to save settings'),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/api/workspaces/${workspaceId}/`),
    onSuccess: () => { window.location.href = '/workspaces'; },
    onError: () => toast.error('Failed to delete workspace'),
  });

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto p-6 lg:p-8 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-12 rounded-xl" />
        <Skeleton className="h-24 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6 lg:p-8">
      <h1 className="text-h1 mb-8">Workspace Settings</h1>

      {/* General */}
      <section className="bg-bg-elevated rounded-xl border border-[var(--color-border)] p-6 mb-6">
        <h2 className="text-h3 mb-4">General</h2>
        <div className="space-y-4">
          <Input
            label="Workspace name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-body)] mb-1.5">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 bg-bg-base rounded-xl border border-[var(--color-border)] text-sm outline-none focus:border-primary resize-none"
              placeholder="What is this workspace for?"
            />
          </div>
          <div className="flex justify-end">
            <Button onClick={() => updateMutation.mutate()} loading={updateMutation.isPending}>
              <Save size={16} className="mr-1.5" /> Save changes
            </Button>
          </div>
        </div>
      </section>

      {/* Danger zone */}
      <section className="bg-danger/5 rounded-xl border border-danger/20 p-6">
        <h2 className="text-h3 text-danger mb-2">Danger Zone</h2>
        <p className="text-sm text-[var(--color-text-hint)] mb-4">
          Deleting a workspace is permanent and cannot be undone.
        </p>
        <Button variant="danger" onClick={() => setDeleteOpen(true)}>
          <Trash2 size={16} className="mr-1.5" /> Delete Workspace
        </Button>
      </section>

      {/* Delete confirm modal */}
      <Modal open={deleteOpen} onClose={() => setDeleteOpen(false)} title="Delete Workspace">
        <div className="space-y-4">
          <div className="flex gap-3 p-3 bg-danger/10 rounded-lg">
            <AlertTriangle size={18} className="text-danger shrink-0 mt-0.5" />
            <p className="text-sm text-danger">This action is permanent. All data will be lost.</p>
          </div>
          <Input
            label={`Type "${ws?.name}" to confirm`}
            value={deleteConfirm}
            onChange={(e) => setDeleteConfirm(e.target.value)}
            placeholder={ws?.name}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDeleteOpen(false)}>Cancel</Button>
            <Button
              variant="danger"
              disabled={deleteConfirm !== ws?.name || deleteMutation.isPending}
              loading={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
            >
              Delete
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
