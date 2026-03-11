'use client';

import { useEffect } from 'react';
import { APP_URL } from '@/lib/constants';

export default function LoginPage() {
  useEffect(() => {
    window.location.href = `${APP_URL}/login`;
  }, []);

  return (
    <div className="flex items-center justify-center py-32" style={{ background: 'var(--bg-primary)' }}>
      <p className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>Redirecionando para app.pulso.network...</p>
    </div>
  );
}
