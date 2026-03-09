'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { Search, X } from 'lucide-react';

interface MapSearchProps {
  onSelect?: (municipality: { name: string; code: string; lat: number; lng: number }) => void;
  municipalities?: Array<{ name: string; code: string; lat: number; lng: number }>;
}

export default function MapSearch({ onSelect, municipalities = [] }: MapSearchProps) {
  const [query, setQuery] = useState('');
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = query.length >= 2
    ? municipalities
        .filter((m) => m.name.toLowerCase().includes(query.toLowerCase()))
        .slice(0, 8)
    : [];

  const handleSelect = useCallback(
    (item: typeof municipalities[0]) => {
      setQuery(item.name);
      setFocused(false);
      onSelect?.(item);
    },
    [onSelect]
  );

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setFocused(false);
        inputRef.current?.blur();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  return (
    <div className="absolute top-4 left-1/2 z-20 -translate-x-1/2" style={{ width: '320px' }}>
      <div
        className="relative rounded-md"
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        }}
      >
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2"
          style={{ color: 'var(--text-muted)' }}
        />
        <input
          ref={inputRef}
          type="text"
          placeholder="Buscar município..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          className="w-full rounded-md bg-transparent py-2 pl-9 pr-8 text-sm focus:outline-none"
          style={{ color: 'var(--text-primary)' }}
        />
        {query && (
          <button
            onClick={() => { setQuery(''); inputRef.current?.focus(); }}
            className="absolute right-3 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--text-muted)' }}
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* Autocomplete dropdown */}
      {focused && filtered.length > 0 && (
        <div
          className="mt-1 rounded-md py-1 max-h-64 overflow-y-auto"
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          }}
        >
          {filtered.map((item) => (
            <button
              key={item.code}
              onClick={() => handleSelect(item)}
              className="flex w-full items-center px-3 py-2 text-sm text-left transition-colors"
              style={{ color: 'var(--text-primary)' }}
            >
              {item.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
