'use client';

import { ReactNode, useEffect } from 'react';
import { AuthProvider } from '@/contexts/AuthContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { CountryProvider } from '@/contexts/CountryContext';
import AuthGuard from '@/components/auth/AuthGuard';

function LangAttribute() {
  useEffect(() => {
    const lang = localStorage.getItem('pulso_language') || 'pt-BR';
    document.documentElement.lang = lang;
  }, []);
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <CountryProvider>
          <LangAttribute />
          <AuthGuard>{children}</AuthGuard>
        </CountryProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
