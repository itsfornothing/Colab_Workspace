import { clsx } from 'clsx';

export default function Skeleton({ className }) {
  return (
    <div
      className={clsx(
        'animate-pulse rounded-md bg-[var(--color-border)]',
        className
      )}
    />
  );
}

export function SkeletonMessage() {
  return (
    <div className="flex gap-3 p-4">
      <Skeleton className="w-9 h-9 rounded-full shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    </div>
  );
}

export function SkeletonDoc() {
  return (
    <div className="flex gap-3 p-3 rounded-lg">
      <Skeleton className="w-10 h-10 rounded-lg shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
  );
}
