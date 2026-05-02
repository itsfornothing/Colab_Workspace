import { useEffect, useRef, useState } from 'react';
import { Phone, PhoneOff, PhoneMissed, AlertCircle } from 'lucide-react';
import Avatar from '@/components/ui/Avatar';
import Button from '@/components/ui/Button';

const AUTO_DISMISS_MS = 30_000;

/**
 * CallNotification - incoming call banner with accept/decline buttons.
 * Auto-dismisses after 30 seconds if not answered.
 * Shows a "busy" indicator when the user is already in a call.
 * Can display error messages for call-related issues.
 */
export default function CallNotification({
  callerId,
  callerName,
  callerAvatar,
  roomId,
  isBusy = false,
  errorMessage = null,
  onAccept,
  onDecline,
  autoDismissTimeout = AUTO_DISMISS_MS,
}) {
  const [secondsLeft, setSecondsLeft] = useState(Math.round(autoDismissTimeout / 1000));
  const timerRef = useRef(null);

  useEffect(() => {
    // Countdown ticker
    timerRef.current = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          clearInterval(timerRef.current);
          onDecline?.();
          return 0;
        }
        return s - 1;
      });
    }, 1000);

    return () => clearInterval(timerRef.current);
  }, [onDecline]);

  const handleAccept = () => {
    clearInterval(timerRef.current);
    onAccept?.();
  };

  const handleDecline = () => {
    clearInterval(timerRef.current);
    onDecline?.();
  };

  return (
    <div
      role="alertdialog"
      aria-label="Incoming call"
      className="fixed bottom-6 right-6 z-50 w-80 bg-bg-elevated border border-[var(--color-border)] rounded-2xl shadow-modal p-4 flex flex-col gap-3 animate-slide-up"
    >
      {/* Caller info */}
      <div className="flex items-center gap-3">
        <div className="relative">
          <Avatar src={callerAvatar} name={callerName} size="lg" />
          {/* Pulsing ring */}
          <span className="absolute inset-0 rounded-full border-2 border-primary animate-ping opacity-60" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-[var(--color-text-heading)] truncate">{callerName}</p>
          <p className="text-xs text-[var(--color-text-hint)]">
            {isBusy ? 'You are in another call' : `Incoming video call · ${secondsLeft}s`}
          </p>
        </div>
      </div>

      {/* Busy indicator */}
      {isBusy && (
        <div className="flex items-center gap-1.5 text-xs text-yellow-500 bg-yellow-500/10 rounded-lg px-3 py-1.5">
          <PhoneMissed size={14} />
          <span>You're currently in a call</span>
        </div>
      )}

      {/* Error message */}
      {errorMessage && (
        <div className="flex items-center gap-1.5 text-xs text-red-500 bg-red-500/10 rounded-lg px-3 py-1.5">
          <AlertCircle size={14} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2">
        <Button
          variant="danger"
          size="sm"
          className="flex-1"
          onClick={handleDecline}
        >
          <PhoneOff size={16} />
          Decline
        </Button>
        <Button
          size="sm"
          className="flex-1 bg-green-600 hover:bg-green-700 text-white"
          onClick={handleAccept}
          disabled={isBusy}
        >
          <Phone size={16} />
          {isBusy ? 'Busy' : 'Accept'}
        </Button>
      </div>
    </div>
  );
}
