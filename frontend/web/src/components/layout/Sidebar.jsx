import { NavLink, useNavigate, useParams } from 'react-router-dom';
import { Home, MessageSquare, FileText, Video, Users, Settings, Bell, ChevronDown, Plus, LogOut } from 'lucide-react';
import { clsx } from 'clsx';
import { useAuth } from '@/hooks/useAuth';
import { useWorkspaceStore } from '@/stores/workspaceStore';
import { useNotificationStore } from '@/stores/notificationStore';
import { useUiStore } from '@/stores/uiStore';
import Avatar from '@/components/ui/Avatar';

const NAV_ITEMS = [
  { icon: Home, label: 'Home', path: 'home' },
  { icon: MessageSquare, label: 'Chat', path: 'chat' },
  { icon: FileText, label: 'Docs', path: 'docs' },
  { icon: Video, label: 'Calls', path: 'calls' },
  { icon: Users, label: 'Members', path: 'members' },
];

export default function Sidebar({ collapsed = false }) {
  const { workspaceId } = useParams();
  const { user, logout } = useAuth();
  const { workspaces, currentWorkspaceId, setCurrentWorkspace } = useWorkspaceStore();
  const { channels } = useWorkspaceStore();
  const { unreadCount } = useNotificationStore();
  const { toggleNotifPanel } = useUiStore();
  const navigate = useNavigate();

  const currentWs = workspaces.find((w) => w.id === currentWorkspaceId);

  const handleSwitchWorkspace = (id) => {
    setCurrentWorkspace(id);
    navigate(`/w/${id}/home`);
  };

  return (
    <aside
      className={clsx(
        'flex flex-col h-full bg-bg-panel border-r border-[var(--color-border)] transition-all duration-200',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Workspace switcher */}
      <div className="p-3 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2 p-2 rounded-lg hover:bg-bg-elevated cursor-pointer group">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-white font-bold text-sm shrink-0">
            {currentWs?.name?.[0]?.toUpperCase() || 'W'}
          </div>
          {!collapsed && (
            <>
              <span className="flex-1 font-semibold text-sm text-[var(--color-text-heading)] truncate">
                {currentWs?.name || 'Workspace'}
              </span>
              <ChevronDown size={14} className="text-[var(--color-text-hint)] group-hover:text-[var(--color-text-body)]" />
            </>
          )}
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {NAV_ITEMS.map(({ icon: Icon, label, path }) => (
          <NavLink
            key={path}
            to={`/w/${workspaceId}/${path}`}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary-light text-primary'
                  : 'text-[var(--color-text-body)] hover:bg-bg-elevated hover:text-[var(--color-text-heading)]'
              )
            }
          >
            <Icon size={18} className="shrink-0" />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}

        {/* Channels */}
        {!collapsed && channels.length > 0 && (
          <div className="pt-4">
            <div className="flex items-center justify-between px-3 mb-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-hint)]">
                Channels
              </span>
              <button className="p-0.5 rounded hover:bg-bg-elevated text-[var(--color-text-hint)]">
                <Plus size={14} />
              </button>
            </div>
            {channels.slice(0, 8).map((ch) => (
              <NavLink
                key={ch.id}
                to={`/w/${workspaceId}/chat/${ch.id}`}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors',
                    isActive
                      ? 'bg-primary-light text-primary font-medium'
                      : 'text-[var(--color-text-body)] hover:bg-bg-elevated'
                  )
                }
              >
                <span className="text-[var(--color-text-hint)]">#</span>
                <span className="flex-1 truncate">{ch.name}</span>
                {ch.unread_count > 0 && (
                  <span className="bg-danger text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                    {ch.unread_count > 99 ? '99+' : ch.unread_count}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        )}
      </nav>

      {/* Bottom */}
      <div className="p-2 border-t border-[var(--color-border)] space-y-0.5">
        {/* Notifications */}
        <button
          onClick={toggleNotifPanel}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[var(--color-text-body)] hover:bg-bg-elevated transition-colors"
        >
          <div className="relative">
            <Bell size={18} />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-danger text-white text-[9px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </div>
          {!collapsed && <span>Notifications</span>}
        </button>

        {/* Settings */}
        <NavLink
          to={`/w/${workspaceId}/settings`}
          className={({ isActive }) =>
            clsx(
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
              isActive
                ? 'bg-primary-light text-primary'
                : 'text-[var(--color-text-body)] hover:bg-bg-elevated'
            )
          }
        >
          <Settings size={18} />
          {!collapsed && <span>Settings</span>}
        </NavLink>

        {/* User */}
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-bg-elevated cursor-pointer group">
          <Avatar src={user?.avatar_url} name={user?.full_name || user?.email} size="sm" status="online" />
          {!collapsed && (
            <>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--color-text-heading)] truncate">
                  {user?.full_name || user?.email}
                </p>
              </div>
              <button
                onClick={logout}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-bg-panel text-[var(--color-text-hint)]"
                title="Sign out"
              >
                <LogOut size={14} />
              </button>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
