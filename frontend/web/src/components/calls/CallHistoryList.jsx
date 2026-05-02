import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Clock, Users, Download, Phone, ChevronLeft, ChevronRight } from 'lucide-react';
import { format, formatDistanceToNow, formatDuration, intervalToDuration } from 'date-fns';
import api from '@/lib/axiosClient';
import Avatar from '@/components/ui/Avatar';
import Button from '@/components/ui/Button';
import Skeleton from '@/components/ui/Skeleton';

export default function CallHistoryList() {
  const { workspaceId } = useParams();
  const [page, setPage] = useState(1);
  const itemsPerPage = 20;

  const { data: callHistory = [], isLoading } = useQuery({
    queryKey: ['call-history', workspaceId, page],
    queryFn: async () => {
      const params = new URLSearchParams({
        workspace_id: workspaceId,
        limit: itemsPerPage * page, // Fetch all items up to current page
      });
      const { data } = await api.get(`/api/chat/call-history/?${params}`);
      return data;
    },
  });

  // Client-side pagination
  const totalPages = Math.ceil(callHistory.length / itemsPerPage);
  const startIndex = (page - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentPageItems = callHistory.slice(startIndex, endIndex);
  const hasMore = callHistory.length === itemsPerPage * page;

  const formatCallDuration = (seconds) => {
    if (!seconds) return 'N/A';
    
    const duration = intervalToDuration({ start: 0, end: seconds * 1000 });
    const parts = [];
    
    if (duration.hours) parts.push(`${duration.hours}h`);
    if (duration.minutes) parts.push(`${duration.minutes}m`);
    if (duration.seconds || parts.length === 0) parts.push(`${duration.seconds || 0}s`);
    
    return parts.join(' ');
  };

  const getParticipantNames = (participants) => {
    if (!participants || participants.length === 0) return 'No participants';
    
    const names = participants.map(p => p.user?.full_name || p.user?.username || 'Unknown');
    
    if (names.length <= 2) {
      return names.join(' and ');
    } else if (names.length === 3) {
      return `${names[0]}, ${names[1]}, and ${names[2]}`;
    } else {
      return `${names[0]}, ${names[1]}, and ${names.length - 2} others`;
    }
  };

  const handleNextPage = () => {
    if (hasMore || page < totalPages) {
      setPage(page + 1);
    }
  };

  const handlePrevPage = () => {
    if (page > 1) {
      setPage(page - 1);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
    );
  }

  if (callHistory.length === 0) {
    return (
      <div className="text-center py-16 text-[var(--color-text-hint)]">
        <Phone size={40} className="mx-auto mb-3 opacity-30" />
        <p className="font-medium">No call history</p>
        <p className="text-sm mt-1">Your past calls will appear here</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        {currentPageItems.map((call) => (
          <div
            key={call.id}
            className="p-4 bg-bg-elevated rounded-xl border border-[var(--color-border)] hover:border-primary/30 transition-colors"
          >
            <div className="flex items-start gap-4">
              {/* Call Icon */}
              <div className="w-12 h-12 rounded-xl bg-primary-light flex items-center justify-center shrink-0">
                <Phone size={22} className="text-primary" />
              </div>

              {/* Call Details */}
              <div className="flex-1 min-w-0">
                {/* Room Name */}
                <div className="flex items-center gap-2 mb-1">
                  <p className="font-semibold text-[var(--color-text-heading)] truncate">
                    {call.room?.name || 'Unnamed Call'}
                  </p>
                </div>

                {/* Participants */}
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex -space-x-2">
                    {call.participants?.slice(0, 3).map((participant) => (
                      <Avatar
                        key={participant.id}
                        name={participant.user?.full_name || participant.user?.username}
                        size="sm"
                        className="ring-2 ring-bg-elevated"
                      />
                    ))}
                    {call.participants?.length > 3 && (
                      <div className="w-7 h-7 rounded-full bg-[var(--color-bg-tertiary)] flex items-center justify-center text-xs font-medium text-[var(--color-text-hint)] ring-2 ring-bg-elevated">
                        +{call.participants.length - 3}
                      </div>
                    )}
                  </div>
                  <span className="text-sm text-[var(--color-text-secondary)]">
                    {getParticipantNames(call.participants)}
                  </span>
                </div>

                {/* Call Metadata */}
                <div className="flex items-center gap-4 text-xs text-[var(--color-text-hint)]">
                  <span className="flex items-center gap-1">
                    <Clock size={12} />
                    {call.started_at && formatDistanceToNow(new Date(call.started_at), { addSuffix: true })}
                  </span>
                  {call.duration_seconds !== null && (
                    <span className="flex items-center gap-1">
                      Duration: {formatCallDuration(call.duration_seconds)}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <Users size={12} />
                    {call.participant_count || call.participants?.length || 0} participant{(call.participant_count || call.participants?.length) !== 1 ? 's' : ''}
                  </span>
                </div>

                {/* Date */}
                <div className="text-xs text-[var(--color-text-hint)] mt-1">
                  {call.started_at && format(new Date(call.started_at), 'PPpp')}
                </div>
              </div>

              {/* Recording Download Link */}
              {call.recording_url && (
                <div className="shrink-0">
                  <Button
                    as="a"
                    href={call.recording_url}
                    download
                    size="sm"
                    variant="outline"
                    className="gap-1.5"
                  >
                    <Download size={14} />
                    Recording
                  </Button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Pagination Controls */}
      {(totalPages > 1 || hasMore) && (
        <div className="flex items-center justify-between pt-4 border-t border-[var(--color-border)]">
          <div className="text-sm text-[var(--color-text-hint)]">
            Showing {startIndex + 1}-{Math.min(endIndex, callHistory.length)} of {callHistory.length}
            {hasMore && '+'}
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={handlePrevPage}
              disabled={page === 1}
            >
              <ChevronLeft size={16} />
              Previous
            </Button>
            <span className="text-sm text-[var(--color-text-secondary)] px-2">
              Page {page}
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={handleNextPage}
              disabled={!hasMore && page >= totalPages}
            >
              Next
              <ChevronRight size={16} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
