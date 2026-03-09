'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Shield } from 'lucide-react';

interface RoleGuardProps {
  minRole: 'viewer' | 'analyst' | 'manager' | 'admin';
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export default function RoleGuard({ minRole, children, fallback }: RoleGuardProps) {
  const { hasRole, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Carregando...</p>
      </div>
    );
  }

  if (!hasRole(minRole)) {
    if (fallback) return <>{fallback}</>;
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12 text-center">
        <Shield size={48} style={{ color: 'var(--text-muted)' }} />
        <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Acesso Negado</h2>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Você não tem permissão para acessar esta página.
          Nível necessário: <span className="font-medium" style={{ color: 'var(--text-secondary)' }}>{minRole}</span>
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
