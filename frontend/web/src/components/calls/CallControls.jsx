import { useState } from 'react';
import { Mic, MicOff, Video, VideoOff, Monitor, MonitorOff, PhoneOff } from 'lucide-react';
import { clsx } from 'clsx';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';

function ControlBtn({ onClick, active, danger, title, children, className = '' }) {
  return (
    <button
      onClick={onClick}
      title={title}
      aria-label={title}
      className={clsx(
        'w-12 h-12 rounded-full flex items-center justify-center transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2',
        danger
          ? 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500'
          : active
          ? 'bg-bg-elevated text-[var(--color-text-heading)] hover:bg-bg-panel'
          : 'bg-bg-panel text-[var(--color-text-hint)] hover:bg-bg-elevated',
        className
      )}
    >
      {children}
    </button>
  );
}

/**
 * CallControls - mute, video toggle, screen share, and leave call buttons.
 * Wires to WebRTCClient methods via callbacks.
 * Shows a confirmation dialog before leaving.
 */
export default function CallControls({
  audioEnabled = true,
  videoEnabled = true,
  screenSharing = false,
  onToggleAudio,
  onToggleVideo,
  onToggleScreen,
  onLeave,
}) {
  const [confirmLeave, setConfirmLeave] = useState(false);

  return (
    <>
      <div className="flex items-center justify-center gap-3 sm:gap-4 px-4 sm:px-6 py-3 sm:py-4 bg-bg-elevated border-t border-[var(--color-border)]">
        {/* Mute / Unmute */}
        <ControlBtn
          onClick={onToggleAudio}
          active={audioEnabled}
          title={audioEnabled ? 'Mute microphone' : 'Unmute microphone'}
        >
          {audioEnabled ? <Mic size={20} /> : <MicOff size={20} />}
        </ControlBtn>

        {/* Video on / off */}
        <ControlBtn
          onClick={onToggleVideo}
          active={videoEnabled}
          title={videoEnabled ? 'Turn off camera' : 'Turn on camera'}
        >
          {videoEnabled ? <Video size={20} /> : <VideoOff size={20} />}
        </ControlBtn>

        {/* Screen share */}
        <ControlBtn
          onClick={onToggleScreen}
          active={screenSharing}
          title={screenSharing ? 'Stop sharing screen' : 'Share screen'}
        >
          {screenSharing ? <MonitorOff size={20} /> : <Monitor size={20} />}
        </ControlBtn>

        {/* Leave call */}
        <ControlBtn
          onClick={() => setConfirmLeave(true)}
          danger
          title="Leave call"
        >
          <PhoneOff size={20} />
        </ControlBtn>
      </div>

      {/* Leave confirmation */}
      <Modal open={confirmLeave} onClose={() => setConfirmLeave(false)} title="Leave call?">
        <p className="text-sm text-[var(--color-text-body)] mb-4">
          Are you sure you want to leave this call?
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirmLeave(false)}>Stay</Button>
          <Button variant="danger" onClick={() => { setConfirmLeave(false); onLeave?.(); }}>Leave</Button>
        </div>
      </Modal>
    </>
  );
}
