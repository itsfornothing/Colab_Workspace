import { useEffect, useRef } from 'react';
import { Monitor } from 'lucide-react';

/**
 * ScreenShareDisplay - shows the active screen share prominently.
 * Displays the sharer's name and handles stream attachment.
 */
export default function ScreenShareDisplay({ stream, sharerName = 'Someone', className = '' }) {
  const videoRef = useRef(null);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  if (!stream) return null;

  return (
    <div className={`relative bg-black rounded-xl overflow-hidden flex items-center justify-center ${className}`}>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        className="w-full h-full object-contain"
      />

      {/* Sharer label */}
      <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-black/60 rounded-lg px-2 py-1">
        <Monitor size={12} className="text-blue-400" />
        <span className="text-white text-xs font-medium">{sharerName}'s screen</span>
      </div>
    </div>
  );
}
