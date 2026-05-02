import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { ArrowLeft, Save, Users } from 'lucide-react';
import api from '@/lib/axiosClient';
import { useAuth } from '@/hooks/useAuth';
import DocEditor from '@/components/docs/DocEditor';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';
import toast from 'react-hot-toast';

export default function DocumentEditorPage() {
  const { workspaceId, docId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [title, setTitle] = useState('');
  const [titleEditing, setTitleEditing] = useState(false);

  const { data: doc, isLoading } = useQuery({
    queryKey: ['doc', docId],
    queryFn: async () => {
      const { data } = await api.get(`/api/docs/${docId}/`);
      setTitle(data.title);
      return data;
    },
    enabled: !!docId,
  });

  const updateTitle = useMutation({
    mutationFn: (t) => api.patch(`/api/docs/${docId}/`, { title: t }),
    onSuccess: () => toast.success('Title updated'),
    onError: () => toast.error('Failed to update title'),
  });

  if (isLoading) {
    return (
      <div className="p-8 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 h-14 border-b border-[var(--color-border)] shrink-0 bg-bg-base">
        <button
          onClick={() => navigate(`/w/${workspaceId}/docs`)}
          className="p-1.5 rounded-lg hover:bg-bg-elevated text-[var(--color-text-hint)]"
        >
          <ArrowLeft size={18} />
        </button>

        {titleEditing ? (
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={() => { setTitleEditing(false); updateTitle.mutate(title); }}
            onKeyDown={(e) => { if (e.key === 'Enter') { setTitleEditing(false); updateTitle.mutate(title); } }}
            autoFocus
            className="flex-1 text-lg font-semibold bg-transparent outline-none border-b border-primary text-[var(--color-text-heading)]"
          />
        ) : (
          <h1
            className="flex-1 text-lg font-semibold text-[var(--color-text-heading)] cursor-text hover:text-primary transition-colors truncate"
            onClick={() => setTitleEditing(true)}
          >
            {title || 'Untitled'}
          </h1>
        )}

        <div className="flex items-center gap-2 ml-auto">
          <span className="text-xs text-[var(--color-text-hint)] hidden sm:block">
            {doc?.updated_by?.full_name && `Last edited by ${doc.updated_by.full_name}`}
          </span>
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1 overflow-hidden">
        <DocEditor docId={docId} currentUser={user} />
      </div>
    </div>
  );
}
