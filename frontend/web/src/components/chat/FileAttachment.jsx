import { Download, FileText, Image } from 'lucide-react';

const isImage = (filename) => /\.(png|jpe?g|gif|webp|svg)$/i.test(filename);

export default function FileAttachment({ attachment }) {
  const { filename, file_url, file_size } = attachment;
  const img = isImage(filename);

  if (img) {
    return (
      <a href={file_url} target="_blank" rel="noopener noreferrer" className="block mt-2 max-w-xs">
        <img src={file_url} alt={filename} className="rounded-lg border border-[var(--color-border)] max-h-64 object-cover" />
      </a>
    );
  }

  return (
    <a
      href={file_url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 mt-2 px-3 py-2 bg-bg-panel rounded-lg border border-[var(--color-border)] hover:border-primary transition-colors text-sm"
    >
      <FileText size={16} className="text-primary shrink-0" />
      <span className="flex-1 truncate max-w-[200px] text-[var(--color-text-body)]">{filename}</span>
      {file_size && <span className="text-xs text-[var(--color-text-hint)]">{(file_size / 1024).toFixed(0)} KB</span>}
      <Download size={14} className="text-[var(--color-text-hint)]" />
    </a>
  );
}
