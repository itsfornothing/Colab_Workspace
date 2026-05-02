import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { clsx } from 'clsx';

export default function Drawer({ open, onClose, title, children, side = 'right', width = 'w-80' }) {
  const variants = {
    right: { initial: { x: '100%' }, animate: { x: 0 }, exit: { x: '100%' } },
    left:  { initial: { x: '-100%' }, animate: { x: 0 }, exit: { x: '-100%' } },
    bottom:{ initial: { y: '100%' }, animate: { y: 0 }, exit: { y: '100%' } },
  };
  const v = variants[side];

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/40"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className={clsx(
              'fixed z-50 bg-bg-elevated border-[var(--color-border)] flex flex-col',
              side === 'right' && `right-0 top-0 bottom-0 border-l ${width}`,
              side === 'left'  && `left-0 top-0 bottom-0 border-r ${width}`,
              side === 'bottom' && 'bottom-0 left-0 right-0 border-t rounded-t-2xl max-h-[80vh]'
            )}
            initial={v.initial} animate={v.animate} exit={v.exit}
            transition={{ duration: 0.25, ease: 'easeOut' }}
          >
            {title && (
              <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)] shrink-0">
                <h2 className="font-semibold text-[var(--color-text-heading)]">{title}</h2>
                <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-bg-panel text-[var(--color-text-hint)]">
                  <X size={18} />
                </button>
              </div>
            )}
            <div className="flex-1 overflow-y-auto">{children}</div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
