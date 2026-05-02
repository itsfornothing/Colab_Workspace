import Avatar from '@/components/ui/Avatar';

export default function CollaboratorBar({ collaborators = [] }) {
  if (!collaborators.length) return null;

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-[var(--color-text-hint)] mr-1">Editing:</span>
      <div className="flex -space-x-2">
        {collaborators.slice(0, 5).map((c) => (
          <div key={c.clientId} title={c.name} className="ring-2 ring-bg-base rounded-full">
            <Avatar src={c.avatar_url} name={c.name} size="xs" status="online" />
          </div>
        ))}
        {collaborators.length > 5 && (
          <div className="w-6 h-6 rounded-full bg-bg-elevated border-2 border-bg-base flex items-center justify-center text-[10px] font-bold text-[var(--color-text-hint)]">
            +{collaborators.length - 5}
          </div>
        )}
      </div>
    </div>
  );
}
