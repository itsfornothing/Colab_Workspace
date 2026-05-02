import { useEffect, useRef } from 'react';
import { MicOff, VideoOff } from 'lucide-react';
import Avatar from '@/components/ui/Avatar';

/**
 * LocalVideoPreview - displays the local user's video stream.
 * Shows camera feed when video is on, or avatar/initials when off.
 * Displays a muted indicator when audio is off.
 */
export default function LocalVideoPreview({ stream, user, isMuted = false, isVideoOff = false, className = '' }) {
  const videoRef = useRef(null);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  return (
    <div className={`relative bg-bg-panel rounded-xl overflow-hidden flex items-center justify-center ${className}`}>
      {!isVideoOff && stream ? (
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className="w-full h-full object-cover"
        />
      ) : (
        <div className="flex flex-col items-center gap-2 p-4">
          <Avatar src={user?.avatar_url} name={user?.full_name || 'You'} size="lg" />
          <span className="text-xs text-[var(--color-text-hint)]">Camera off</span>
        </div>
      )}

      {/* Name + mute indicator */}
      <div className="absolute bottom-2 left-2 flex items-center gap-1.5 bg-black/50 rounded-lg px-2 py-1">
        <span className="text-white text-xs font-medium">You</span>
        {isMuted && <MicOff size={12} className="text-red-400" />}
        {isVideoOff && <VideoOff size={12} className="text-[var(--color-text-hint)]" />}
      </div>
    </div>
  );
}
