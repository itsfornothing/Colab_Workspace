import { motion } from 'framer-motion';

export default function TypingIndicator({ users = [] }) {
  if (!users.length) return null;

  const label =
    users.length === 1
      ? `${users[0]} is typing…`
      : users.length === 2
      ? `${users[0]} and ${users[1]} are typing…`
      : 'Several people are typing…';

  return (
    <div className="flex items-center gap-2 px-4 py-1 text-xs text-[var(--color-text-hint)]">
      <div className="flex gap-0.5">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-[var(--color-text-hint)]"
            animate={{ y: [0, -4, 0] }}
            transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
          />
        ))}
      </div>
      {label}
    </div>
  );
}
