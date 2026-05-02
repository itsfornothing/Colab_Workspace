import { useState, useMemo } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import RemoteVideoTile from './RemoteVideoTile';

const PAGE_SIZE = 4; // max tiles visible at once before pagination

/**
 * getGridClass
 *
 * Returns a Tailwind grid-cols class based on participant count.
 *
 * Performance note (Requirement 11.5): this function is pure and cheap, but
 * we memoize the result in the component via useMemo so it is not recomputed
 * on every render when participants haven't changed.
 *
 * @param {number} count - number of visible participants
 * @returns {string} Tailwind grid-cols class
 */
function getGridClass(count) {
  if (count <= 1) return 'grid-cols-1';
  if (count <= 2) return 'grid-cols-2';
  if (count <= 4) return 'grid-cols-2';
  return 'grid-cols-3';
}

/**
 * RemoteVideoGrid - responsive grid of remote participant video tiles.
 *
 * Supports 2, 4, 6, 8 participant layouts and paginates when >4 participants.
 *
 * Performance optimizations (Requirement 11.5):
 * - Grid class is memoized via useMemo to avoid recomputation on unrelated renders
 * - Paged participant slice is memoized to avoid re-slicing on every render
 * - The `video-grid` CSS class applies `contain: layout style` to limit the
 *   scope of layout recalculations to the grid container
 * - Individual tiles use CSS transforms (GPU compositor layers) via the
 *   `video-tile` class in RemoteVideoTile
 */
export default function RemoteVideoGrid({
  participants,
  streams,
  participantStates = {},
  connectionQualities = {},
}) {
  const [page, setPage] = useState(0);

  const totalPages = Math.ceil(participants.length / PAGE_SIZE);

  // Memoize the paged slice — only recomputes when participants or page changes
  const paged = useMemo(
    () => participants.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE),
    [participants, page]
  );

  // Memoize the grid class — only recomputes when the visible count changes
  const gridClass = useMemo(() => getGridClass(paged.length), [paged.length]);

  return (
    <div className="flex flex-col h-full gap-2">
      {/* video-grid applies contain:layout style for scoped layout recalculations */}
      <div className={`video-grid flex-1 grid ${gridClass} gap-2 min-h-0`}>
        {paged.map((participant) => {
          const state = participantStates[participant.id] || {};
          return (
            <RemoteVideoTile
              key={participant.id}
              userId={participant.id}
              stream={streams[participant.id] || null}
              participant={participant}
              isMuted={state.is_muted ?? false}
              isVideoOff={!(state.is_video_on ?? true)}
              connectionQuality={connectionQualities[participant.id] || null}
              className="min-h-0"
            />
          );
        })}
      </div>

      {/* Pagination controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 py-1 shrink-0">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="w-8 h-8 rounded-full bg-bg-elevated flex items-center justify-center disabled:opacity-40 hover:bg-bg-panel transition-colors"
            aria-label="Previous page"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-xs text-[var(--color-text-hint)]">
            {page + 1} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page === totalPages - 1}
            className="w-8 h-8 rounded-full bg-bg-elevated flex items-center justify-center disabled:opacity-40 hover:bg-bg-panel transition-colors"
            aria-label="Next page"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
