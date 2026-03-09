'use client';

/**
 * AuthGuard desabilitado temporariamente para desenvolvimento.
 * Quando pronto para produção, restaurar a verificação de autenticação.
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
