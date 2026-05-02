import { clsx } from 'clsx';

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  className,
  ...props
}) {
  const base = 'inline-flex items-center justify-center gap-2 font-semibold rounded-md transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';

  const variants = {
    primary: 'bg-primary text-white hover:bg-primary-hover active:scale-[0.98] focus:ring-primary',
    secondary: 'bg-transparent border border-[var(--color-border)] text-[var(--color-text-body)] hover:bg-bg-panel',
    outline: 'bg-transparent border border-primary text-primary hover:bg-primary-light',
    danger: 'bg-danger text-white hover:bg-red-600 focus:ring-danger',
    ghost: 'bg-transparent text-[var(--color-text-body)] hover:bg-bg-panel',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-5 py-2.5 text-[15px]',
    lg: 'px-6 py-3 text-[15px]',
    icon: 'w-9 h-9 p-0',
  };

  return (
    <button
      className={clsx(base, variants[variant], sizes[size], className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <span className="spinner w-4 h-4" /> : children}
    </button>
  );
}
