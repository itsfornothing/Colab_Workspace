import { useEffect, useRef, useState } from 'react';
import { Mic, MicOff, Video, VideoOff } from 'lucide-react';
import Button from '@/components/ui/Button';
import Avatar from '@/components/ui/Avatar';

export default function PreCallLobby({ room, currentUser, onJoin, onCancel }) {
  const videoRef = useRef(null);
  const [audioOn, setAudioOn] = useState(true);
  const [videoOn, setVideoOn] = useState(true);
  const [stream, setStream] = useState(null);

  useEffect(() => {
    let s;
    navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      .then((ms) => {
        s = ms;
        setStream(ms);
        if (videoRef.current) videoRef.current.srcObject = ms;
      })
      .catch(() => {});
    return () => s?.getTracks().forEach((t) => t.stop());
  }, []);

  const toggleAudio = () => {
    stream?.getAudioTracks().forEach((t) => { t.enabled = !audioOn; });
    setAudioOn((v) => !v);
  };

  const toggleVideo = () => {
    stream?.getVideoTracks().forEach((t) => { t.enabled = !videoOn; });
    setVideoOn((v) => !v);
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-bg-base p-6">
      <div className="w-full max-w-md bg-bg-elevated rounded-2xl border border-[var(--color-border)] overflow-hidden shadow-modal">
        {/* Preview */}
        <div className="relative aspect-video bg-bg-panel">
          {videoOn ? (
            <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
          ) : (
            <div className="flex items-center justify-center h-full">
              <Avatar src={currentUser?.avatar_url} name={currentUser?.full_name} size="xl" />
            </div>
          )}
        </div>

        <div className="p-6">
          <h2 className="text-h2 text-center mb-1">{room?.name || 'Call Room'}</h2>
          <p className="text-sm text-[var(--color-text-hint)] text-center mb-6">
            {room?.participant_count ? `${room.participant_count} participant(s) in call` : 'Ready to join'}
          </p>

          {/* Controls */}
          <div className="flex justify-center gap-3 mb-6">
            <button
              onClick={toggleAudio}
              className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${audioOn ? 'bg-bg-panel text-[var(--color-text-body)]' : 'bg-danger/10 text-danger'}`}
            >
              {audioOn ? <Mic size={20} /> : <MicOff size={20} />}
            </button>
            <button
              onClick={toggleVideo}
              className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${videoOn ? 'bg-bg-panel text-[var(--color-text-body)]' : 'bg-danger/10 text-danger'}`}
            >
              {videoOn ? <Video size={20} /> : <VideoOff size={20} />}
            </button>
          </div>

          <div className="flex gap-3">
            <Button variant="ghost" className="flex-1" onClick={onCancel}>Cancel</Button>
            <Button className="flex-1" onClick={() => onJoin({ audioOn, videoOn })}>Join Call</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
