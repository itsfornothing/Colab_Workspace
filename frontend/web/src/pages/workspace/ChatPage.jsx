import { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Hash, Plus, Search, Lock } from 'lucide-react';
import { clsx } from 'clsx';
import api from '@/lib/axiosClient';
import { useAuth } from '@/hooks/useAuth';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useChatStore } from '@/stores/chatStore';
import { useWorkspaceStore } from '@/stores/workspaceStore';
import MessageList from '@/components/chat/MessageList';
import MessageInput from '@/components/chat/MessageInput';
import Skeleton from '@/components/ui/Skeleton';
import toast from 'react-hot-toast';

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

// ── Channel list panel ────────────────────────────────────────────
function ChannelListPanel({ channels, activeId, onSelect, workspaceId }) {
  const [search, setSearch] = useState('');
  const filtered = channels.filter((c) => c.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="w-64 shrink-0 border-r border-[var(--color-border)] flex flex-col bg-bg-panel h-full">
      <div className="p-3 border-b border-[var(--color-border)]">
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-hint)]" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search channels…"
            className="w-full pl-8 pr-3 py-1.5 text-sm bg-bg-elevated rounded-lg border border-[var(--color-border)] outline-none focus:border-primary"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        <div className="flex items-center justify-between px-2 py-1 mb-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-hint)]">Channels</span>
          <button className="p-0.5 rounded hover:bg-bg-elevated text-[var(--color-text-hint)]" title="New channel">
            <Plus size={14} />
          </button>
        </div>
        {filtered.map((ch) => (
          <button
            key={ch.id}
            onClick={() => onSelect(ch.id)}
            className={clsx(
              'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors text-left',
              ch.id === activeId
                ? 'bg-primary-light text-primary font-medium'
                : 'text-[var(--color-text-body)] hover:bg-bg-elevated'
            )}
          >
            {ch.is_private ? <Lock size={14} className="shrink-0" /> : <Hash size={14} className="shrink-0" />}
            <span className="flex-1 truncate">{ch.name}</span>
            {ch.unread_count > 0 && (
              <span className="bg-danger text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                {ch.unread_count > 99 ? '99+' : ch.unread_count}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Channel chat view ─────────────────────────────────────────────
function ChannelChat({ channelId, workspaceId }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { messages, typingUsers, addMessage, editMessage, softDeleteMessage, updateReaction, setTypingUsers, setMessages } = useChatStore();

  const channelMessages = messages[channelId] || [];
  const channelTyping = typingUsers[channelId] || [];

  // Load history
  const { isLoading } = useQuery({
    queryKey: ['messages', channelId],
    queryFn: async () => {
      const { data } = await api.get(`/api/chat/channels/${channelId}/messages/`);
      setMessages(channelId, data.results || data);
      return data;
    },
    enabled: !!channelId,
  });

  // Channel info
  const { data: channel } = useQuery({
    queryKey: ['channel', channelId],
    queryFn: async () => {
      const { data } = await api.get(`/api/chat/channels/${channelId}/`);
      return data;
    },
    enabled: !!channelId,
  });

  // WebSocket
  const { send, isConnected } = useWebSocket({
    url: `${WS_BASE}/ws/chat/${channelId}/`,
    onMessage: {
      message:        (d) => addMessage(channelId, d.message),
      message_edited: (d) => editMessage(channelId, d),
      message_deleted:(d) => softDeleteMessage(channelId, d),
      reaction_update:(d) => updateReaction(channelId, d),
      typing:         (d) => {
        const current = typingUsers[channelId] || [];
        if (d.is_typing) {
          if (!current.includes(d.user_name)) setTypingUsers(channelId, [...current, d.user_name]);
        } else {
          setTypingUsers(channelId, current.filter((n) => n !== d.user_name));
        }
      },
    },
    enabled: !!channelId,
  });

  // Send message
  const sendMutation = useMutation({
    mutationFn: async ({ content, files }) => {
      if (files?.length) {
        const fd = new FormData();
        fd.append('content', content);
        files.forEach((f) => fd.append('attachments', f));
        const { data } = await api.post(`/api/chat/channels/${channelId}/messages/`, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        return data;
      }
      const { data } = await api.post(`/api/chat/channels/${channelId}/messages/`, { content });
      return data;
    },
    onError: () => toast.error('Failed to send message'),
  });

  const handleSend = ({ content, files }) => {
    // Optimistic via WS
    send({ type: 'message', content });
    if (files?.length) sendMutation.mutate({ content, files });
  };

  const handleTyping = (isTyping) => send({ type: 'typing', is_typing: isTyping });

  const handleReact = (messageId, emoji) => send({ type: 'reaction', message_id: messageId, emoji });

  const handleDelete = async (messageId) => {
    try {
      await api.delete(`/api/chat/messages/${messageId}/`);
      softDeleteMessage(channelId, { message_id: messageId });
    } catch {
      toast.error('Failed to delete message');
    }
  };

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 h-14 border-b border-[var(--color-border)] shrink-0 bg-bg-base">
        <Hash size={18} className="text-[var(--color-text-hint)]" />
        <div>
          <h2 className="font-semibold text-[var(--color-text-heading)] text-sm">{channel?.name || '…'}</h2>
          {channel?.description && (
            <p className="text-xs text-[var(--color-text-hint)] truncate max-w-xs">{channel.description}</p>
          )}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className={clsx('w-2 h-2 rounded-full', isConnected ? 'bg-success' : 'bg-warning')} title={isConnected ? 'Connected' : 'Reconnecting…'} />
        </div>
      </div>

      <MessageList
        messages={channelMessages}
        typingUsers={channelTyping}
        isLoading={isLoading}
        currentUserId={user?.id}
        onDelete={handleDelete}
        onReact={handleReact}
      />

      <MessageInput
        onSend={handleSend}
        onTyping={handleTyping}
        placeholder={channel ? `Message #${channel.name}` : 'Message…'}
      />
    </div>
  );
}

// ── Main ChatPage ─────────────────────────────────────────────────
export default function ChatPage() {
  const { workspaceId, channelId } = useParams();
  const navigate = useNavigate();
  const { channels } = useWorkspaceStore();

  const activeChannelId = channelId || channels[0]?.id;

  const handleSelect = (id) => navigate(`/w/${workspaceId}/chat/${id}`);

  return (
    <div className="flex h-full">
      <ChannelListPanel
        channels={channels}
        activeId={activeChannelId}
        onSelect={handleSelect}
        workspaceId={workspaceId}
      />
      {activeChannelId ? (
        <ChannelChat channelId={activeChannelId} workspaceId={workspaceId} />
      ) : (
        <div className="flex-1 flex items-center justify-center text-[var(--color-text-hint)]">
          <div className="text-center">
            <Hash size={40} className="mx-auto mb-3 opacity-30" />
            <p>Select a channel to start chatting</p>
          </div>
        </div>
      )}
    </div>
  );
}
