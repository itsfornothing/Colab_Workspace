import { clsx } from 'clsx';

const variants = {
  default: 'bg-bg-elevated text-[var(--color-text-body)] border border-[var(--color-border)]',
  primary: 'bg-primary-light text-primary',
  success: 'bg-success/10 text-success',
  warning: 'bg-warning/10 text-warning',
  danger:  'bg-danger/10 text-danger',
  info:    'bg-info/10 text-info',
};

export default function Badge({ children, variant = 'default', className }) {
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium', variants[variant], className)}>
      {children}
    </span>
  );
}
