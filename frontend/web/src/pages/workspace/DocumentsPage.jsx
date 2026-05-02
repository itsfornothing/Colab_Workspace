import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FileText, Plus, Search, MoreHorizontal, Trash2, Edit2 } from 'lucide-react';
import { format } from 'date-fns';
import api from '@/lib/axiosClient';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';
import Modal from '@/components/ui/Modal';
import Input from '@/components/ui/Input';
import Dropdown from '@/components/ui/Dropdown';
import toast from 'react-hot-toast';

export default function DocumentsPage() {
  const { workspaceId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');

  const { data: docs = [], isLoading } = useQuery({
    queryKey: ['docs', workspaceId],
    queryFn: async () => {
      const { data } = await api.get(`/api/docs/?workspace=${workspaceId}`);
      return data.results || data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (title) => {
      const { data } = await api.post('/api/docs/', { title, workspace: workspaceId });
      return data;
    },
    onSuccess: (doc) => {
      qc.invalidateQueries(['docs', workspaceId]);
      setCreateOpen(false);
      setNewTitle('');
      navigate(`/w/${workspaceId}/docs/${doc.id}`);
    },
    onError: () => toast.error('Failed to create document'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/api/docs/${id}/`),
    onSuccess: () => qc.invalidateQueries(['docs', workspaceId]),
    onError: () => toast.error('Failed to delete document'),
  });

  const filtered = docs.filter((d) => d.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="max-w-4xl mx-auto p-6 lg:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-h1">Documents</h1>
        <Button onClick={() => setCreateOpen(true)} size="sm">
          <Plus size={16} className="mr-1.5" /> New Document
        </Button>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-hint)]" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search documents…"
          className="w-full pl-10 pr-4 py-2 bg-bg-elevated rounded-xl border border-[var(--color-border)] text-sm outline-none focus:border-primary"
        />
      </div>

      {/* List */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-[var(--color-text-hint)]">
          <FileText size={40} className="mx-auto mb-3 opacity-30" />
          <p className="font-medium">No documents yet</p>
          <p className="text-sm mt-1">Create your first document to get started</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-4 p-4 bg-bg-elevated rounded-xl border border-[var(--color-border)] hover:border-primary transition-colors cursor-pointer group"
              onClick={() => navigate(`/w/${workspaceId}/docs/${doc.id}`)}
            >
              <FileText size={20} className="text-primary shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-[var(--color-text-heading)] truncate">{doc.title}</p>
                <p className="text-xs text-[var(--color-text-hint)] mt-0.5">
                  Updated {format(new Date(doc.updated_at), 'MMM d, yyyy')}
                  {doc.updated_by && ` · ${doc.updated_by.full_name}`}
                </p>
              </div>
              <Dropdown
                align="right"
                trigger={
                  <button
                    onClick={(e) => e.stopPropagation()}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-bg-panel text-[var(--color-text-hint)]"
                  >
                    <MoreHorizontal size={16} />
                  </button>
                }
                items={[
                  { icon: Edit2, label: 'Open', onClick: () => navigate(`/w/${workspaceId}/docs/${doc.id}`) },
                  { divider: true },
                  { icon: Trash2, label: 'Delete', danger: true, onClick: () => deleteMutation.mutate(doc.id) },
                ]}
              />
            </div>
          ))}
        </div>
      )}

      {/* Create modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New Document">
        <div className="space-y-4">
          <Input
            label="Document title"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="Untitled document"
            autoFocus
            onKeyDown={(e) => e.key === 'Enter' && newTitle.trim() && createMutation.mutate(newTitle.trim())}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              onClick={() => createMutation.mutate(newTitle.trim())}
              disabled={!newTitle.trim() || createMutation.isPending}
              loading={createMutation.isPending}
            >
              Create
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
