import { NavLink, useParams } from 'react-router-dom';
import { Home, MessageSquare, FileText, Video, MoreHorizontal } from 'lucide-react';
import { clsx } from 'clsx';
import { useNotificationStore } from '@/stores/notificationStore';

const TABS = [
  { icon: Home, label: 'Home', path: 'home' },
  { icon: MessageSquare, label: 'Chat', path: 'chat' },
  { icon: FileText, label: 'Docs', path: 'docs' },
  { icon: Video, label: 'Calls', path: 'calls' },
  { icon: MoreHorizontal, label: 'More', path: 'members' },
];

export default function BottomTabBar() {
  const { workspaceId } = useParams();
  const { unreadCount } = useNotificationStore();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-bg-elevated border-t border-[var(--color-border)] flex safe-area-pb">
      {TABS.map(({ icon: Icon, label, path }) => (
        <NavLink
          key={path}
          to={`/w/${workspaceId}/${path}`}
          className={({ isActive }) =>
            clsx(
              'flex-1 flex flex-col items-center justify-center py-2 gap-0.5 text-xs font-medium transition-colors',
              isActive
                ? 'text-primary'
                : 'text-[var(--color-text-hint)]'
            )
          }
        >
          <div className="relative">
            <Icon size={22} />
            {path === 'chat' && unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-danger text-white text-[9px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </div>
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
