import { useRef, useEffect, useState } from 'react';
import { clsx } from 'clsx';
import { motion, AnimatePresence } from 'framer-motion';

export default function Dropdown({ trigger, items = [], align = 'left', className }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className={clsx('relative inline-block', className)}>
      <div onClick={() => setOpen((v) => !v)}>{trigger}</div>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -4 }}
            transition={{ duration: 0.1 }}
            className={clsx(
              'absolute z-50 mt-1 min-w-[160px] bg-bg-elevated border border-[var(--color-border)] rounded-xl shadow-dropdown py-1',
              align === 'right' ? 'right-0' : 'left-0'
            )}
          >
            {items.map((item, i) =>
              item.divider ? (
                <div key={i} className="my-1 border-t border-[var(--color-border)]" />
              ) : (
                <button
                  key={i}
                  onClick={() => { item.onClick?.(); setOpen(false); }}
                  disabled={item.disabled}
                  className={clsx(
                    'w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors',
                    item.danger
                      ? 'text-danger hover:bg-danger/10'
                      : 'text-[var(--color-text-body)] hover:bg-bg-panel hover:text-[var(--color-text-heading)]',
                    item.disabled && 'opacity-40 cursor-not-allowed'
                  )}
                >
                  {item.icon && <item.icon size={15} className="shrink-0" />}
                  {item.label}
                </button>
              )
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
