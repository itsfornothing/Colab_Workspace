import { clsx } from 'clsx';
import { forwardRef } from 'react';

const Input = forwardRef(function Input({ label, error, className, ...props }, ref) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm font-medium text-[var(--color-text-body)]">{label}</label>
      )}
      <input
        ref={ref}
        className={clsx(
          'h-11 px-3.5 rounded-md text-[15px] bg-bg-elevated border transition-all outline-none',
          'text-[var(--color-text-heading)] placeholder:text-[var(--color-text-hint)]',
          error
            ? 'border-danger focus:ring-2 focus:ring-danger/20'
            : 'border-[var(--color-border)] focus:border-[var(--color-border-focus)] focus:ring-2 focus:ring-primary/15',
          className
        )}
        {...props}
      />
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
});

export default Input;
