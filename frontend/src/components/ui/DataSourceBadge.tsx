import { Database } from 'lucide-react';

interface DataSourceBadgeProps {
  sources: string;
  className?: string;
}

export default function DataSourceBadge({ sources, className = '' }: DataSourceBadgeProps) {
  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium ${className}`}
      style={{
        backgroundColor: 'color-mix(in srgb, var(--accent) 10%, transparent)',
        color: 'var(--text-muted)',
        border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)',
      }}
    >
      <Database size={10} />
      {sources}
    </div>
  );
}
