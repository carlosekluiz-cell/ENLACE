'use client';

import { useState } from 'react';
import { Download, ChevronDown } from 'lucide-react';
import { clsx } from 'clsx';

interface ExportButtonProps {
  onExport: (format: 'csv' | 'xlsx' | 'pdf') => Promise<void>;
  className?: string;
}

export default function ExportButton({ onExport, className }: ExportButtonProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);

  const handleExport = async (format: 'csv' | 'xlsx' | 'pdf') => {
    setLoading(format);
    setOpen(false);
    try {
      await onExport(format);
    } finally {
      setLoading(null);
    }
  };

  const formats = [
    { key: 'csv' as const, label: 'CSV', desc: 'Planilha simples' },
    { key: 'xlsx' as const, label: 'Excel', desc: 'Microsoft Excel' },
    { key: 'pdf' as const, label: 'PDF', desc: 'Documento PDF' },
  ];

  return (
    <div className={clsx('relative', className)}>
      <button
        onClick={() => setOpen(!open)}
        disabled={loading !== null}
        className="pulso-btn-primary flex items-center gap-2"
      >
        <Download size={16} />
        {loading ? 'Exportando...' : 'Exportar'}
        <ChevronDown size={14} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div
            className="absolute right-0 top-full z-20 mt-1 w-48 rounded-md border py-1"
            style={{
              background: 'var(--bg-surface)',
              borderColor: 'var(--border)',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            }}
          >
            {formats.map((f) => (
              <button
                key={f.key}
                onClick={() => handleExport(f.key)}
                className="flex w-full items-center gap-3 px-4 py-2 text-left text-sm transition-colors hover:opacity-80"
                style={{ color: 'var(--text-primary)' }}
              >
                <div>
                  <div className="font-medium">{f.label}</div>
                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{f.desc}</div>
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
