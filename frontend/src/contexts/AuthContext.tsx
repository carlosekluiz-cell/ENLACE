'use client';

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import { api, setToken, clearToken, isAuthenticated } from '@/lib/api';
import type { UserProfile } from '@/lib/types';

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  loading: boolean;
  role: string;
  login: (token: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  hasRole: (minRole: string) => boolean;
}

const ROLE_HIERARCHY = ['viewer', 'analyst', 'manager', 'admin'];

const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  loading: true,
  role: 'viewer',
  login: async () => {},
  logout: () => {},
  refresh: async () => {},
  hasRole: () => false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    if (!isAuthenticated()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const profile = await api.auth.me();
      setUser(profile);
    } catch {
      // Token inválido ou expirado — limpar silenciosamente
      setUser(null);
      clearToken();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = async (token: string) => {
    setToken(token);
    await fetchUser();
  };

  const logout = () => {
    clearToken();
    setUser(null);
    window.location.href = '/login';
  };

  const hasRole = (minRole: string) => {
    if (!user) return false;
    const userLevel = ROLE_HIERARCHY.indexOf(user.role);
    const requiredLevel = ROLE_HIERARCHY.indexOf(minRole);
    return userLevel >= requiredLevel;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        loading,
        role: user?.role || 'viewer',
        login,
        logout,
        refresh: fetchUser,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
