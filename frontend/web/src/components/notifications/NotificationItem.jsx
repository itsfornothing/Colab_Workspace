import { format } from 'date-fns';
import { MessageSquare, FileText, Bell, Users } from 'lucide-react';
import { clsx } from 'clsx';

const ICONS = {
  message:  { icon: MessageSquare, color: 'text-primary bg-primary-light' },
  document: { icon: FileText,      color: 'text-success bg-success/10' },
  mention:  { icon: Bell,          color: 'text-warning bg-warning/10' },
  member:   { icon: Users,         color: 'text-info bg-info/10' },
};

export default function NotificationItem({ notification, onRead }) {
  const { icon: Icon, color } = ICONS[notification.type] || ICONS.mention;

  return (
    <button
      onClick={() => onRead?.(notification.id)}
      className={clsx(
        'w-full flex gap-3 px-4 py-3 text-left hover:bg-bg-panel transition-colors',
        !notification.is_read && 'bg-primary-light/30'
      )}
    >
      <div className={clsx('w-9 h-9 rounded-full flex items-center justify-center shrink-0', color)}>
        <Icon size={16} />
      </div>
      <div className="flex-1 min-w-0">
        <p className={clsx('text-sm', !notification.is_read ? 'font-semibold text-[var(--color-text-heading)]' : 'text-[var(--color-text-body)]')}>
          {notification.title}
        </p>
        {notification.body && (
          <p className="text-xs text-[var(--color-text-hint)] mt-0.5 truncate">{notification.body}</p>
        )}
        <p className="text-xs text-[var(--color-text-hint)] mt-1">
          {format(new Date(notification.created_at), 'MMM d, h:mm a')}
        </p>
      </div>
      {!notification.is_read && (
        <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
      )}
    </button>
  );
}
