'use client';

import { useState } from 'react';
import { Globe } from 'lucide-react';
import { clsx } from 'clsx';

const LANGUAGES = [
  { code: 'pt-BR', label: 'Português (BR)', flag: '🇧🇷' },
  { code: 'en', label: 'English', flag: '🇺🇸' },
];

export default function LanguageSwitcher() {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState(() => {
    if (typeof window === 'undefined') return 'pt-BR';
    return localStorage.getItem('pulso_language') || 'pt-BR';
  });

  const handleSelect = (code: string) => {
    setCurrent(code);
    localStorage.setItem('pulso_language', code);
    setOpen(false);
    window.location.reload();
  };

  const currentLang = LANGUAGES.find((l) => l.code === current) || LANGUAGES[0];

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 rounded p-1.5 transition-colors"
        style={{ color: 'var(--text-muted)' }}
        title="Idioma"
        aria-label="Alterar idioma"
      >
        <Globe size={16} />
        <span className="hidden text-xs md:inline">{currentLang.flag}</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div
            className="absolute right-0 top-full z-20 mt-1 w-44 rounded-md border py-1"
            style={{
              background: 'var(--bg-surface)',
              borderColor: 'var(--border)',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            }}
          >
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => handleSelect(lang.code)}
                className={clsx(
                  'flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors',
                  current === lang.code
                    ? 'font-medium'
                    : ''
                )}
                style={{
                  color: current === lang.code ? 'var(--accent)' : 'var(--text-primary)',
                  background: current === lang.code ? 'var(--accent-subtle)' : 'transparent',
                }}
              >
                <span>{lang.flag}</span>
                {lang.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
