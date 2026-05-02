import { clsx } from 'clsx';

const STATUS_COLORS = {
  online: 'bg-[var(--color-online)]',
  away: 'bg-[var(--color-away)]',
  dnd: 'bg-[var(--color-dnd)]',
  offline: 'bg-[var(--color-offline)]',
};

const SIZES = {
  xs: 'w-5 h-5 text-[9px]',
  sm: 'w-7 h-7 text-xs',
  md: 'w-9 h-9 text-sm',
  lg: 'w-12 h-12 text-base',
  xl: 'w-16 h-16 text-xl',
  '2xl': 'w-24 h-24 text-3xl',
};

export default function Avatar({ src, name = '', size = 'md', status, className }) {
  const initials = name
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <div className={clsx('relative inline-flex shrink-0', className)}>
      <div
        className={clsx(
          'rounded-full flex items-center justify-center font-semibold overflow-hidden',
          SIZES[size],
          !src && 'bg-primary-light text-primary'
        )}
      >
        {src ? (
          <img src={src} alt={name} className="w-full h-full object-cover" />
        ) : (
          <span>{initials || '?'}</span>
        )}
      </div>
      {status && (
        <span
          className={clsx(
            'absolute bottom-0 right-0 rounded-full border-2 border-bg-elevated',
            STATUS_COLORS[status],
            size === 'xs' || size === 'sm' ? 'w-2 h-2' : 'w-2.5 h-2.5'
          )}
        />
      )}
    </div>
  );
}
