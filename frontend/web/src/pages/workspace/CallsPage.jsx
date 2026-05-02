import { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Video, Plus, Users, Clock, History, Search, X, Check } from 'lucide-react';
import { format } from 'date-fns';
import api from '@/lib/axiosClient';
import { useCallLifecycle } from '@/hooks/useCallLifecycle';
import { useCallStore } from '@/stores/callStore';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';
import Modal from '@/components/ui/Modal';
import Input from '@/components/ui/Input';
import Badge from '@/components/ui/Badge';
import Avatar from '@/components/ui/Avatar';
import CallHistoryList from '@/components/calls/CallHistoryList';
import toast from 'react-hot-toast';

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export default function CallsPage() {
  const { workspaceId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [createOpen, setCreateOpen] = useState(false);
  const [roomName, setRoomName] = useState('');
  const [activeTab, setActiveTab] = useState('rooms'); // 'rooms' | 'history'

  // ── Invitee picker state ───────────────────────────────────────────────
  const [userSearch, setUserSearch] = useState('');
  const [selectedUsers, setSelectedUsers] = useState([]); // [{ id, username, full_name }]
  const [isInitiating, setIsInitiating] = useState(false);

  // ── Call lifecycle ─────────────────────────────────────────────────────
  // We don't have a persistent WS here; WorkspaceShell owns the /ws/calls/ WS.
  // For initiating a call we use the REST API + pass send=null (WorkspaceShell
  // will relay the WS invite via its own connection).
  const { initiateCall, invitationStatuses } = useCallLifecycle({ workspaceId });

  const { data: rooms = [], isLoading } = useQuery({
    queryKey: ['call-rooms', workspaceId],
    queryFn: async () => {
      const { data } = await api.get(`/api/chat/rooms/?workspace=${workspaceId}`);
      return data.results || data;
    },
  });

  // ── User search for invitee picker ────────────────────────────────────
  const { data: searchResults = [], isFetching: isSearching } = useQuery({
    queryKey: ['user-search', userSearch],
    queryFn: async () => {
      if (!userSearch.trim() || userSearch.trim().length < 1) return [];
      const { data } = await api.get(`/api/chat/users/search/?q=${encodeURIComponent(userSearch.trim())}`);
      return data.results || data || [];
    },
    enabled: userSearch.trim().length >= 1,
    staleTime: 5000,
  });

  const toggleUser = useCallback((u) => {
    setSelectedUsers((prev) => {
      const exists = prev.find((x) => x.id === u.id);
      return exists ? prev.filter((x) => x.id !== u.id) : [...prev, u];
    });
  }, []);

  const handleOpenCreate = () => {
    setRoomName('');
    setUserSearch('');
    setSelectedUsers([]);
    setCreateOpen(true);
  };

  const handleCloseCreate = () => {
    setCreateOpen(false);
    setRoomName('');
    setUserSearch('');
    setSelectedUsers([]);
  };

  // ── Initiate call (14.1) ───────────────────────────────────────────────
  const handleInitiateCall = async () => {
    if (!roomName.trim()) return;
    setIsInitiating(true);
    try {
      const inviteeIds = selectedUsers.map((u) => u.id);
      const room = await initiateCall(roomName.trim(), inviteeIds, workspaceId);
      qc.invalidateQueries(['call-rooms', workspaceId]);
      handleCloseCreate();
      navigate(`/w/${workspaceId}/calls/${room.id}`);
    } catch {
      // Error already toasted by initiateCall
    } finally {
      setIsInitiating(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 lg:p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-h1">Calls</h1>
        {activeTab === 'rooms' && (
          <Button onClick={handleOpenCreate} size="sm">
            <Plus size={16} className="mr-1.5" /> New Room
          </Button>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 mb-6 border-b border-[var(--color-border)]">
        <button
          onClick={() => setActiveTab('rooms')}
          className={`px-4 py-2 text-sm font-medium transition-colors relative ${
            activeTab === 'rooms'
              ? 'text-primary'
              : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-heading)]'
          }`}
        >
          <span className="flex items-center gap-2">
            <Video size={16} />
            Active Rooms
          </span>
          {activeTab === 'rooms' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
          )}
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`px-4 py-2 text-sm font-medium transition-colors relative ${
            activeTab === 'history'
              ? 'text-primary'
              : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-heading)]'
          }`}
        >
          <span className="flex items-center gap-2">
            <History size={16} />
            Call History
          </span>
          {activeTab === 'history' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
          )}
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'rooms' ? (
        isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
          </div>
        ) : rooms.length === 0 ? (
          <div className="text-center py-16 text-[var(--color-text-hint)]">
            <Video size={40} className="mx-auto mb-3 opacity-30" />
            <p className="font-medium">No call rooms yet</p>
            <p className="text-sm mt-1">Create a room to start a video call</p>
          </div>
        ) : (
          <div className="space-y-3">
            {rooms.map((room) => (
              <div
                key={room.id}
                className="flex items-center gap-4 p-4 bg-bg-elevated rounded-xl border border-[var(--color-border)] hover:border-primary transition-colors cursor-pointer"
                onClick={() => navigate(`/w/${workspaceId}/calls/${room.id}`)}
              >
                <div className="w-12 h-12 rounded-xl bg-primary-light flex items-center justify-center shrink-0">
                  <Video size={22} className="text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-[var(--color-text-heading)] truncate">{room.name}</p>
                    {room.is_active && <Badge variant="success">Live</Badge>}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-[var(--color-text-hint)]">
                    {room.participant_count > 0 && (
                      <span className="flex items-center gap-1">
                        <Users size={12} /> {room.participant_count} in call
                      </span>
                    )}
                    <span className="flex items-center gap-1">
                      <Clock size={12} /> {format(new Date(room.created_at), 'MMM d')}
                    </span>
                  </div>
                </div>
                <Button size="sm" variant={room.is_active ? 'primary' : 'outline'}>
                  {room.is_active ? 'Join' : 'Start'}
                </Button>
              </div>
            ))}
          </div>
        )
      ) : (
        <CallHistoryList />
      )}

      {/* New Room Modal with invitee picker (Requirement 5.1, 14.1) */}
      <Modal open={createOpen} onClose={handleCloseCreate} title="New Call Room">
        <div className="space-y-4">
          <Input
            label="Room name"
            value={roomName}
            onChange={(e) => setRoomName(e.target.value)}
            placeholder="e.g. Team standup"
            autoFocus
            onKeyDown={(e) => e.key === 'Enter' && roomName.trim() && !isInitiating && handleInitiateCall()}
          />

          {/* Invitee picker */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1.5">
              Invite people (optional)
            </label>

            {/* Selected users chips */}
            {selectedUsers.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {selectedUsers.map((u) => (
                  <span
                    key={u.id}
                    className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary/10 text-primary text-xs rounded-full"
                  >
                    {u.full_name || u.username}
                    <button
                      onClick={() => toggleUser(u)}
                      className="hover:text-primary/70"
                      aria-label={`Remove ${u.full_name || u.username}`}
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}

            {/* Search input */}
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-hint)]" />
              <input
                type="text"
                value={userSearch}
                onChange={(e) => setUserSearch(e.target.value)}
                placeholder="Search by name or username…"
                className="w-full pl-8 pr-3 py-2 text-sm bg-bg-panel border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-primary"
              />
            </div>

            {/* Search results */}
            {userSearch.trim().length >= 1 && (
              <div className="mt-1 max-h-40 overflow-y-auto border border-[var(--color-border)] rounded-lg bg-bg-elevated">
                {isSearching ? (
                  <div className="p-3 text-sm text-[var(--color-text-hint)]">Searching…</div>
                ) : searchResults.length === 0 ? (
                  <div className="p-3 text-sm text-[var(--color-text-hint)]">No users found</div>
                ) : (
                  searchResults.map((u) => {
                    const isSelected = selectedUsers.some((x) => x.id === u.id);
                    return (
                      <button
                        key={u.id}
                        onClick={() => toggleUser(u)}
                        className="w-full flex items-center gap-3 px-3 py-2 hover:bg-bg-panel transition-colors text-left"
                      >
                        <Avatar name={u.full_name || u.username} size="sm" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{u.full_name || u.username}</p>
                          {u.full_name && (
                            <p className="text-xs text-[var(--color-text-hint)] truncate">@{u.username}</p>
                          )}
                        </div>
                        {isSelected && <Check size={14} className="text-primary shrink-0" />}
                      </button>
                    );
                  })
                )}
              </div>
            )}
          </div>

          {/* Invitation status feedback */}
          {Object.keys(invitationStatuses).length > 0 && (
            <div className="text-xs text-[var(--color-text-hint)]">
              {Object.entries(invitationStatuses).map(([uid, status]) => {
                const u = selectedUsers.find((x) => x.id === uid);
                const name = u?.full_name || u?.username || uid;
                const icon = status === 'accepted' ? '✅' : status === 'declined' ? '❌' : '⏳';
                return (
                  <span key={uid} className="mr-2">
                    {icon} {name}: {status}
                  </span>
                );
              })}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={handleCloseCreate}>Cancel</Button>
            <Button
              onClick={handleInitiateCall}
              disabled={!roomName.trim() || isInitiating}
              loading={isInitiating}
            >
              {selectedUsers.length > 0 ? `Start & Invite ${selectedUsers.length}` : 'Create Room'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
