import { Mic, MicOff, Video, VideoOff, PhoneOff, Monitor, MonitorOff } from 'lucide-react';
import { clsx } from 'clsx';

function ControlBtn({ onClick, active, danger, title, children }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={clsx(
        'w-12 h-12 rounded-full flex items-center justify-center transition-colors',
        danger
          ? 'bg-danger text-white hover:bg-danger/80'
          : active
          ? 'bg-bg-elevated text-[var(--color-text-heading)] hover:bg-bg-panel'
          : 'bg-bg-panel text-[var(--color-text-hint)] hover:bg-bg-elevated'
      )}
    >
      {children}
    </button>
  );
}

export default function ControlBar({ audioEnabled, videoEnabled, screenSharing, onToggleAudio, onToggleVideo, onToggleScreen, onLeave }) {
  return (
    <div className="flex items-center justify-center gap-4 px-6 py-4 bg-bg-elevated border-t border-[var(--color-border)]">
      <ControlBtn onClick={onToggleAudio} active={audioEnabled} title={audioEnabled ? 'Mute' : 'Unmute'}>
        {audioEnabled ? <Mic size={20} /> : <MicOff size={20} />}
      </ControlBtn>

      <ControlBtn onClick={onToggleVideo} active={videoEnabled} title={videoEnabled ? 'Stop video' : 'Start video'}>
        {videoEnabled ? <Video size={20} /> : <VideoOff size={20} />}
      </ControlBtn>

      <ControlBtn onClick={onToggleScreen} active={screenSharing} title={screenSharing ? 'Stop sharing' : 'Share screen'}>
        {screenSharing ? <MonitorOff size={20} /> : <Monitor size={20} />}
      </ControlBtn>

      <ControlBtn onClick={onLeave} danger title="Leave call">
        <PhoneOff size={20} />
      </ControlBtn>
    </div>
  );
}
