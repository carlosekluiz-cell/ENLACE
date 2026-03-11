'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { Search, X, MapPin } from 'lucide-react';
import { api } from '@/lib/api';

interface Municipality {
  name: string;
  code: string;
  state_abbrev: string;
  lat: number;
  lng: number;
}

interface MapSearchProps {
  onSelect?: (municipality: Municipality) => void;
}

export default function MapSearch({ onSelect }: MapSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Municipality[]>([]);
  const [focused, setFocused] = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const containerRef = useRef<HTMLDivElement>(null);

  // Debounced search against the API
  const searchMunicipalities = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const data = await api.geo.search(q, 10);
      setResults(
        data.map((m) => ({
          name: m.name,
          code: m.code,
          state_abbrev: m.state_abbrev,
          lat: m.latitude,
          lng: m.longitude,
        }))
      );
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChange = useCallback(
    (value: string) => {
      setQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => searchMunicipalities(value), 250);
    },
    [searchMunicipalities]
  );

  const handleSelect = useCallback(
    (item: Municipality) => {
      setQuery(`${item.name} - ${item.state_abbrev}`);
      setFocused(false);
      setResults([]);
      onSelect?.(item);
    },
    [onSelect]
  );

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setFocused(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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
    <div ref={containerRef} className="absolute top-4 left-1/2 z-20 -translate-x-1/2" style={{ width: '360px' }}>
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
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => setFocused(true)}
          className="w-full rounded-md bg-transparent py-2 pl-9 pr-8 text-sm focus:outline-none"
          style={{ color: 'var(--text-primary)' }}
        />
        {query && (
          <button
            onClick={() => {
              setQuery('');
              setResults([]);
              inputRef.current?.focus();
            }}
            className="absolute right-3 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--text-muted)' }}
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* Autocomplete dropdown */}
      {focused && results.length > 0 && (
        <div
          className="mt-1 rounded-md py-1 max-h-64 overflow-y-auto"
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
          }}
        >
          {results.map((item) => (
            <button
              key={item.code}
              onClick={() => handleSelect(item)}
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-left transition-colors hover:bg-[var(--bg-subtle)]"
              style={{ color: 'var(--text-primary)' }}
            >
              <MapPin size={14} className="shrink-0" style={{ color: 'var(--text-muted)' }} />
              <span>{item.name}</span>
              <span className="ml-auto text-xs" style={{ color: 'var(--text-muted)' }}>
                {item.state_abbrev}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Loading indicator */}
      {focused && loading && query.length >= 2 && results.length === 0 && (
        <div
          className="mt-1 rounded-md px-3 py-2 text-sm"
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            color: 'var(--text-muted)',
          }}
        >
          Buscando...
        </div>
      )}

      {/* No results */}
      {focused && !loading && query.length >= 2 && results.length === 0 && (
        <div
          className="mt-1 rounded-md px-3 py-2 text-sm"
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            color: 'var(--text-muted)',
          }}
        >
          Nenhum município encontrado
        </div>
      )}
    </div>
  );
}
