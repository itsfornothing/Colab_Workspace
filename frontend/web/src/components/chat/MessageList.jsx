import { useEffect, useRef } from 'react';
import { format, isToday, isYesterday } from 'date-fns';
import MessageItem from './MessageItem';
import TypingIndicator from './TypingIndicator';
import Skeleton from '@/components/ui/Skeleton';

function DateDivider({ date }) {
  const d = new Date(date);
  const label = isToday(d) ? 'Today' : isYesterday(d) ? 'Yesterday' : format(d, 'MMMM d, yyyy');
  return (
    <div className="flex items-center gap-3 px-4 py-2">
      <div className="flex-1 h-px bg-[var(--color-border)]" />
      <span className="text-xs text-[var(--color-text-hint)] font-medium">{label}</span>
      <div className="flex-1 h-px bg-[var(--color-border)]" />
    </div>
  );
}

export default function MessageList({ messages = [], typingUsers = [], isLoading, currentUserId, onEdit, onDelete, onReact }) {
  const bottomRef = useRef(null);
  const prevLenRef = useRef(0);

  useEffect(() => {
    if (messages.length > prevLenRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
    prevLenRef.current = messages.length;
  }, [messages.length]);

  if (isLoading) {
    return (
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="flex gap-3">
            <Skeleton className="w-8 h-8 rounded-full shrink-0" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-32" />
              <Skeleton className="h-3 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Group messages by date
  const grouped = [];
  let lastDate = null;
  for (const msg of messages) {
    const d = format(new Date(msg.created_at), 'yyyy-MM-dd');
    if (d !== lastDate) {
      grouped.push({ type: 'divider', date: msg.created_at });
      lastDate = d;
    }
    grouped.push({ type: 'message', msg });
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {messages.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-full text-[var(--color-text-hint)]">
          <p className="text-4xl mb-3">💬</p>
          <p className="font-medium">No messages yet</p>
          <p className="text-sm">Be the first to say something!</p>
        </div>
      ) : (
        <>
          {grouped.map((item, i) =>
            item.type === 'divider' ? (
              <DateDivider key={`d-${i}`} date={item.date} />
            ) : (
              <MessageItem
                key={item.msg.id}
                message={item.msg}
                isOwn={item.msg.sender?.id === currentUserId}
                onEdit={onEdit}
                onDelete={onDelete}
                onReact={onReact}
              />
            )
          )}
          <TypingIndicator users={typingUsers} />
          <div ref={bottomRef} />
        </>
      )}
    </div>
  );
}
