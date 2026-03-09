'use client';

import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { clsx } from 'clsx';

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  const options = [
    { value: 'light' as const, icon: Sun, label: 'Claro' },
    { value: 'dark' as const, icon: Moon, label: 'Escuro' },
    { value: 'system' as const, icon: Monitor, label: 'Sistema' },
  ];

  return (
    <div
      className="flex items-center gap-0.5 rounded p-0.5"
      style={{ background: 'var(--bg-subtle)' }}
    >
      {options.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          onClick={() => setTheme(value)}
          className={clsx(
            'rounded p-1.5 transition-colors',
            theme === value
              ? 'text-white'
              : ''
          )}
          style={{
            background: theme === value ? 'var(--accent)' : 'transparent',
            color: theme === value ? '#ffffff' : 'var(--text-muted)',
          }}
          title={label}
          aria-label={label}
        >
          <Icon size={14} />
        </button>
      ))}
    </div>
  );
}
