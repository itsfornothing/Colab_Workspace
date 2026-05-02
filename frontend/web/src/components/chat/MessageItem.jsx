import { useState } from 'react';
import { format } from 'date-fns';
import { MoreHorizontal, Edit2, Trash2, SmilePlus } from 'lucide-react';
import { clsx } from 'clsx';
import Avatar from '@/components/ui/Avatar';
import Dropdown from '@/components/ui/Dropdown';

const COMMON_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '🎉'];

export default function MessageItem({ message, isOwn, onEdit, onDelete, onReact }) {
  const [showActions, setShowActions] = useState(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);

  if (message.is_deleted) {
    return (
      <div className="flex gap-3 px-4 py-1 group">
        <div className="w-8 shrink-0" />
        <p className="text-sm italic text-[var(--color-text-hint)]">This message was deleted.</p>
      </div>
    );
  }

  const menuItems = [
    ...(isOwn ? [
      { icon: Edit2, label: 'Edit', onClick: () => onEdit?.(message) },
      { divider: true },
      { icon: Trash2, label: 'Delete', danger: true, onClick: () => onDelete?.(message.id) },
    ] : []),
  ];

  return (
    <div
      className="flex gap-3 px-4 py-1.5 hover:bg-bg-elevated/50 group relative"
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => { setShowActions(false); setShowEmojiPicker(false); }}
    >
      <Avatar src={message.sender?.avatar_url} name={message.sender?.full_name} size="sm" className="mt-0.5 shrink-0" />

      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 mb-0.5">
          <span className="text-sm font-semibold text-[var(--color-text-heading)]">
            {message.sender?.full_name || 'Unknown'}
          </span>
          <span className="text-xs text-[var(--color-text-hint)]">
            {format(new Date(message.created_at), 'h:mm a')}
          </span>
          {message.is_edited && (
            <span className="text-xs text-[var(--color-text-hint)] italic">(edited)</span>
          )}
        </div>

        <p className="text-sm text-[var(--color-text-body)] whitespace-pre-wrap break-words">
          {message.content}
        </p>

        {/* Attachments */}
        {message.attachments?.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {message.attachments.map((att) => (
              <a
                key={att.id}
                href={att.file_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-bg-panel rounded-lg border border-[var(--color-border)] text-xs text-primary hover:underline"
              >
                📎 {att.filename}
              </a>
            ))}
          </div>
        )}

        {/* Reactions */}
        {message.reactions && Object.keys(message.reactions).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {Object.entries(message.reactions).map(([emoji, users]) => (
              <button
                key={emoji}
                onClick={() => onReact?.(message.id, emoji)}
                className="flex items-center gap-1 px-2 py-0.5 bg-bg-panel rounded-full border border-[var(--color-border)] text-xs hover:border-primary transition-colors"
              >
                {emoji} <span className="text-[var(--color-text-hint)]">{users.length}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Action toolbar */}
      {showActions && (
        <div className="absolute right-4 top-1 flex items-center gap-1 bg-bg-elevated border border-[var(--color-border)] rounded-lg shadow-card px-1 py-0.5">
          {/* Quick emoji */}
          <div className="relative">
            <button
              onClick={() => setShowEmojiPicker((v) => !v)}
              className="p-1.5 rounded hover:bg-bg-panel text-[var(--color-text-hint)] hover:text-[var(--color-text-body)]"
            >
              <SmilePlus size={15} />
            </button>
            {showEmojiPicker && (
              <div className="absolute right-0 bottom-full mb-1 flex gap-1 bg-bg-elevated border border-[var(--color-border)] rounded-xl shadow-dropdown p-2">
                {COMMON_EMOJIS.map((e) => (
                  <button
                    key={e}
                    onClick={() => { onReact?.(message.id, e); setShowEmojiPicker(false); }}
                    className="text-lg hover:scale-125 transition-transform"
                  >
                    {e}
                  </button>
                ))}
              </div>
            )}
          </div>

          {menuItems.length > 0 && (
            <Dropdown
              align="right"
              trigger={
                <button className="p-1.5 rounded hover:bg-bg-panel text-[var(--color-text-hint)] hover:text-[var(--color-text-body)]">
                  <MoreHorizontal size={15} />
                </button>
              }
              items={menuItems}
            />
          )}
        </div>
      )}
    </div>
  );
}
