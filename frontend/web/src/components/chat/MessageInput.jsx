import { useState, useRef, useCallback } from 'react';
import { Paperclip, Send, X } from 'lucide-react';
import { clsx } from 'clsx';

export default function MessageInput({ onSend, onTyping, disabled, placeholder = 'Message…' }) {
  const [text, setText] = useState('');
  const [files, setFiles] = useState([]);
  const fileRef = useRef(null);
  const typingTimer = useRef(null);

  const handleChange = (e) => {
    setText(e.target.value);
    // Notify typing
    onTyping?.(true);
    clearTimeout(typingTimer.current);
    typingTimer.current = setTimeout(() => onTyping?.(false), 2000);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const submit = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed && files.length === 0) return;
    onSend?.({ content: trimmed, files });
    setText('');
    setFiles([]);
    onTyping?.(false);
  }, [text, files, onSend, onTyping]);

  const handleFiles = (e) => {
    const picked = Array.from(e.target.files || []);
    setFiles((prev) => [...prev, ...picked]);
    e.target.value = '';
  };

  const removeFile = (i) => setFiles((prev) => prev.filter((_, idx) => idx !== i));

  return (
    <div className="px-4 py-3 border-t border-[var(--color-border)] bg-bg-base">
      {/* File previews */}
      {files.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {files.map((f, i) => (
            <div key={i} className="flex items-center gap-1.5 px-2 py-1 bg-bg-elevated rounded-lg border border-[var(--color-border)] text-xs">
              📎 {f.name}
              <button onClick={() => removeFile(i)} className="text-[var(--color-text-hint)] hover:text-danger">
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className={clsx(
        'flex items-end gap-2 bg-bg-elevated rounded-xl border border-[var(--color-border)] px-3 py-2',
        'focus-within:border-primary transition-colors'
      )}>
        <button
          onClick={() => fileRef.current?.click()}
          className="p-1.5 rounded-lg text-[var(--color-text-hint)] hover:text-[var(--color-text-body)] hover:bg-bg-panel transition-colors shrink-0"
          title="Attach file"
        >
          <Paperclip size={18} />
        </button>
        <input ref={fileRef} type="file" multiple className="hidden" onChange={handleFiles} />

        <textarea
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          rows={1}
          className="flex-1 bg-transparent resize-none outline-none text-sm text-[var(--color-text-body)] placeholder:text-[var(--color-text-hint)] max-h-32 overflow-y-auto"
          style={{ lineHeight: '1.5' }}
        />

        <button
          onClick={submit}
          disabled={disabled || (!text.trim() && files.length === 0)}
          className={clsx(
            'p-1.5 rounded-lg transition-colors shrink-0',
            text.trim() || files.length > 0
              ? 'bg-primary text-white hover:bg-primary-dark'
              : 'text-[var(--color-text-hint)] cursor-not-allowed'
          )}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
