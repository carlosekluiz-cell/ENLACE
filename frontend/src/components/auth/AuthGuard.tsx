'use client';

import { useAuth } from '@/contexts/AuthContext';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Radio, Lock } from 'lucide-react';

const PUBLIC_PATHS = ['/login'];
const ACCESS_PIN = '2707';
const PIN_STORAGE_KEY = 'pulso_pin_unlocked';

function PinGate({ onUnlock }: { onUnlock: () => void }) {
  const [pin, setPin] = useState('');
  const [error, setError] = useState(false);
  const [shake, setShake] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (pin === ACCESS_PIN) {
      localStorage.setItem(PIN_STORAGE_KEY, '1');
      onUnlock();
    } else {
      setError(true);
      setShake(true);
      setPin('');
      setTimeout(() => setShake(false), 500);
    }
  }

  return (
    <div
      className="flex min-h-screen items-center justify-center px-4"
      style={{ backgroundColor: 'var(--bg-primary)' }}
    >
      <div className="w-full max-w-xs text-center">
        <div className="mb-6 flex items-center justify-center gap-3">
          <Radio style={{ color: 'var(--accent)' }} size={28} />
          <span className="text-xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
            Pulso
          </span>
        </div>

        <div className="pulso-card p-6">
          <Lock size={20} className="mx-auto mb-3" style={{ color: 'var(--text-muted)' }} />
          <p className="mb-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Acesso restrito. Digite o PIN.
          </p>

          <form onSubmit={handleSubmit}>
            <input
              type="password"
              inputMode="numeric"
              maxLength={4}
              value={pin}
              onChange={(e) => { setPin(e.target.value.replace(/\D/g, '')); setError(false); }}
              placeholder="----"
              autoFocus
              className={`pulso-input w-full text-center text-2xl tracking-[0.5em] ${shake ? 'animate-shake' : ''}`}
              style={error ? { borderColor: 'var(--danger)' } : undefined}
            />
            {error && (
              <p className="mt-2 text-xs" style={{ color: 'var(--danger)' }}>
                PIN incorreto.
              </p>
            )}
            <button
              type="submit"
              className="pulso-btn-primary w-full mt-4"
              disabled={pin.length < 4}
            >
              Entrar
            </button>
          </form>
        </div>

        <p className="mt-4 text-xs" style={{ color: 'var(--text-muted)' }}>
          Acesso antecipado
        </p>
      </div>
    </div>
  );
}

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [pinUnlocked, setPinUnlocked] = useState<boolean | null>(null);

  useEffect(() => {
    setPinUnlocked(localStorage.getItem(PIN_STORAGE_KEY) === '1');
  }, []);

  const isPublic = PUBLIC_PATHS.includes(pathname);

  useEffect(() => {
    if (!loading && !isAuthenticated && !isPublic && pinUnlocked) {
      router.replace('/login');
    }
  }, [loading, isAuthenticated, isPublic, pinUnlocked, router]);

  // Still checking localStorage
  if (pinUnlocked === null || loading) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
        <div className="text-sm" style={{ color: 'var(--text-muted)' }}>Carregando...</div>
      </div>
    );
  }

  // PIN gate — show before anything else
  if (!pinUnlocked) {
    return <PinGate onUnlock={() => setPinUnlocked(true)} />;
  }

  if (!isAuthenticated && !isPublic) {
    return null;
  }

  return <>{children}</>;
}
