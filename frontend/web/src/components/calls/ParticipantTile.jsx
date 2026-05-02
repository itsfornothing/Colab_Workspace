import { useEffect, useRef } from 'react';
import { MicOff, VideoOff } from 'lucide-react';
import { clsx } from 'clsx';
import Avatar from '@/components/ui/Avatar';

export default function ParticipantTile({ participant, stream, isLocal = false, className }) {
  const videoRef = useRef(null);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  const hasVideo = stream?.getVideoTracks().some((t) => t.enabled);
  const hasAudio = stream?.getAudioTracks().some((t) => t.enabled);

  return (
    <div className={clsx('relative bg-bg-panel rounded-xl overflow-hidden flex items-center justify-center', className)}>
      {hasVideo ? (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted={isLocal}
          className="w-full h-full object-cover"
        />
      ) : (
        <div className="flex flex-col items-center gap-2">
          <Avatar src={participant?.avatar_url} name={participant?.full_name} size="lg" />
          <span className="text-sm text-[var(--color-text-hint)]">{participant?.full_name}</span>
        </div>
      )}

      {/* Name tag */}
      <div className="absolute bottom-2 left-2 flex items-center gap-1.5 bg-black/50 rounded-lg px-2 py-1">
        <span className="text-white text-xs font-medium">
          {isLocal ? 'You' : participant?.full_name}
        </span>
        {!hasAudio && <MicOff size={12} className="text-danger" />}
        {!hasVideo && <VideoOff size={12} className="text-[var(--color-text-hint)]" />}
      </div>
    </div>
  );
}
