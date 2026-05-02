import { useEffect, useRef, useState, useCallback } from 'react';
import { MicOff, VideoOff, Wifi } from 'lucide-react';
import { clsx } from 'clsx';
import Avatar from '@/components/ui/Avatar';

const QUALITY_COLORS = {
  good: 'text-green-400',
  fair: 'text-yellow-400',
  poor: 'text-red-400',
};

/**
 * useIntersectionObserver
 *
 * Returns true when the observed element is intersecting the viewport.
 * Used to implement lazy rendering: video srcObject is only attached when
 * the tile is visible, avoiding unnecessary GPU decode work for off-screen
 * participants (Requirement 11.5).
 *
 * @param {React.RefObject} ref - ref to the element to observe
 * @param {IntersectionObserverInit} options
 * @returns {boolean} isVisible
 */
function useIntersectionObserver(ref, options = {}) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // IntersectionObserver is not available in all test environments
    if (typeof IntersectionObserver === 'undefined') {
      setIsVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting);
      },
      { threshold: 0.1, ...options }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [ref, options]);

  return isVisible;
}

/**
 * RemoteVideoTile - renders a single remote participant's video feed.
 *
 * Performance optimizations (Requirement 11.5):
 * - CSS transforms (translateZ(0)) promote the tile to a GPU compositor layer
 * - IntersectionObserver-based lazy rendering: video srcObject is only set
 *   when the tile is visible in the viewport, reducing GPU decode overhead
 *   for off-screen participants (e.g. on page 2 of a paginated grid)
 * - `contain: strict` on the video element limits layout/paint scope
 */
export default function RemoteVideoTile({
  userId,
  stream,
  participant,
  isMuted = false,
  isVideoOff = false,
  connectionQuality = null,
  className = '',
}) {
  const tileRef = useRef(null);
  const videoRef = useRef(null);

  // Lazy rendering: only attach stream when tile is visible
  const isVisible = useIntersectionObserver(tileRef, { threshold: 0.1 });

  // Attach / detach stream based on visibility
  useEffect(() => {
    const videoEl = videoRef.current;
    if (!videoEl) return;

    if (isVisible && stream) {
      // Attach stream only when visible (lazy rendering)
      if (videoEl.srcObject !== stream) {
        videoEl.srcObject = stream;
      }
    } else if (!isVisible) {
      // Detach stream when off-screen to free GPU decode resources
      videoEl.srcObject = null;
    }
  }, [stream, isVisible]);

  const hasVideo = !isVideoOff && stream && stream.getVideoTracks().some((t) => t.enabled);

  return (
    <div
      ref={tileRef}
      className={clsx(
        'video-tile',                                          // GPU-accelerated CSS class
        'relative bg-bg-panel rounded-xl overflow-hidden flex items-center justify-center',
        !isVisible && 'video-tile--offscreen',                 // hide off-screen tiles cheaply
        className
      )}
    >
      {hasVideo ? (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          className="w-full h-full object-cover"
          // Prevent layout thrashing from video resize events (handled via CSS contain)
        />
      ) : (
        <div className="flex flex-col items-center gap-2 p-4">
          <Avatar src={participant?.avatar_url} name={participant?.full_name} size="lg" />
          {isVideoOff && (
            <span className="text-xs text-[var(--color-text-hint)]">Camera off</span>
          )}
        </div>
      )}

      {/* Bottom overlay: name + indicators */}
      <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5 bg-black/50 rounded-lg px-2 py-1">
          <span className="text-white text-xs font-medium truncate max-w-[120px]">
            {participant?.full_name || 'Participant'}
          </span>
          {isMuted && <MicOff size={12} className="text-red-400 shrink-0" />}
        </div>

        {connectionQuality && (
          <div className={clsx('bg-black/50 rounded-lg p-1', QUALITY_COLORS[connectionQuality.quality])}>
            <Wifi size={12} />
          </div>
        )}
      </div>
    </div>
  );
}
