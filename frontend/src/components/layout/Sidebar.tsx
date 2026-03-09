'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Map,
  TrendingUp,
  Shield,
  Mountain,
  FileText,
  Menu,
  X,
  Antenna,
  LogOut,
  Settings,
  User,
  Users,
  Activity,
  Sun,
  Moon,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  minRole?: string;
}

const navItems: NavItem[] = [
  { label: 'Mapa', href: '/', icon: <Map size={16} /> },
  { label: 'Expansão', href: '/expansao', icon: <TrendingUp size={16} /> },
  { label: 'Concorrência', href: '/concorrencia', icon: <Users size={16} /> },
  { label: 'Projeto RF', href: '/projeto', icon: <Antenna size={16} /> },
  { label: 'Conformidade', href: '/conformidade', icon: <Shield size={16} /> },
  { label: 'Saúde', href: '/saude', icon: <Activity size={16} /> },
  { label: 'Rural', href: '/rural', icon: <Mountain size={16} /> },
  { label: 'Relatórios', href: '/relatorios', icon: <FileText size={16} /> },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, logout, hasRole } = useAuth();
  const { resolvedTheme, setTheme } = useTheme();

  if (pathname === '/login') return null;

  const toggleTheme = () => {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark');
  };

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed left-4 top-4 z-50 rounded-md p-2 lg:hidden"
        style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
        aria-label="Abrir menu"
      >
        <Menu size={20} />
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-50 flex w-60 flex-col transition-transform duration-200 lg:relative lg:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
        style={{
          background: 'var(--bg-subtle)',
          borderRight: '1px solid var(--border)',
        }}
      >
        {/* Logo */}
        <div className="flex h-12 items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2">
            <div
              className="flex h-7 w-7 items-center justify-center rounded-md text-white text-xs font-bold"
              style={{ background: 'var(--accent)' }}
            >
              P
            </div>
            <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Pulso
            </span>
          </Link>
          <button
            onClick={() => setMobileOpen(false)}
            className="lg:hidden"
            style={{ color: 'var(--text-muted)' }}
            aria-label="Fechar menu"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-0.5 px-2 py-3">
          {navItems.map((item) => {
            const isActive =
              item.href === '/'
                ? pathname === '/'
                : pathname === item.href || pathname?.startsWith(item.href + '/');
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={clsx(
                  'flex items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors',
                  isActive ? 'border-l-2' : 'border-l-2 border-transparent'
                )}
                style={{
                  height: '40px',
                  color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                  background: isActive ? 'var(--accent-subtle)' : 'transparent',
                  borderLeftColor: isActive ? 'var(--accent)' : 'transparent',
                }}
              >
                <span style={{ color: isActive ? 'var(--accent)' : 'var(--text-muted)' }}>
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}

          {/* Admin — hidden from nav but accessible */}
          {hasRole('admin') && (
            <Link
              href="/admin"
              onClick={() => setMobileOpen(false)}
              className="flex items-center gap-3 rounded-md px-3 text-sm font-medium border-l-2 border-transparent mt-4"
              style={{
                height: '40px',
                color: pathname === '/admin' ? 'var(--accent)' : 'var(--text-muted)',
                background: pathname === '/admin' ? 'var(--accent-subtle)' : 'transparent',
                borderLeftColor: pathname === '/admin' ? 'var(--accent)' : 'transparent',
              }}
            >
              <Settings size={16} />
              Admin
            </Link>
          )}
        </nav>

        {/* Footer */}
        <div className="px-3 py-3 space-y-2" style={{ borderTop: '1px solid var(--border)' }}>
          {user && (
            <div className="flex items-center gap-2 px-2">
              <div
                className="flex h-7 w-7 items-center justify-center rounded-full text-xs"
                style={{ background: 'var(--accent-subtle)', color: 'var(--accent)' }}
              >
                <User size={14} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  {user.full_name || user.email}
                </p>
                <p className="truncate text-xs" style={{ color: 'var(--text-muted)' }}>{user.role}</p>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between px-2">
            <div className="flex items-center gap-1">
              {/* Settings */}
              <Link
                href="/configuracoes"
                onClick={() => setMobileOpen(false)}
                className="rounded p-1.5 transition-colors"
                style={{ color: 'var(--text-muted)' }}
                aria-label="Configurações"
              >
                <Settings size={16} />
              </Link>

              {/* Theme toggle */}
              <button
                onClick={toggleTheme}
                className="rounded p-1.5 transition-colors"
                style={{ color: 'var(--text-muted)' }}
                aria-label={resolvedTheme === 'dark' ? 'Modo claro' : 'Modo escuro'}
              >
                {resolvedTheme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              </button>
            </div>

            {/* Logout */}
            <button
              onClick={logout}
              className="rounded p-1.5 transition-colors"
              style={{ color: 'var(--text-muted)' }}
              aria-label="Sair"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile bottom tab bar */}
      <BottomTabBar pathname={pathname} onNavigate={() => setMobileOpen(false)} />
    </>
  );
}

function BottomTabBar({ pathname, onNavigate }: { pathname: string; onNavigate: () => void }) {
  const tabs = [
    { label: 'Mapa', href: '/', icon: <Map size={20} /> },
    { label: 'Expansão', href: '/expansao', icon: <TrendingUp size={20} /> },
    { label: 'Projeto', href: '/projeto', icon: <Antenna size={20} /> },
    { label: 'Mais', href: '#', icon: <Menu size={20} /> },
  ];

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 flex items-center justify-around py-2 lg:hidden"
      style={{
        background: 'var(--bg-surface)',
        borderTop: '1px solid var(--border)',
      }}
    >
      {tabs.map((tab) => {
        const isActive =
          tab.href === '/'
            ? pathname === '/'
            : pathname?.startsWith(tab.href);
        return (
          <Link
            key={tab.label}
            href={tab.href}
            onClick={onNavigate}
            className="flex flex-col items-center gap-0.5 px-3 py-1"
            style={{ color: isActive ? 'var(--accent)' : 'var(--text-muted)' }}
          >
            {tab.icon}
            <span className="text-xs">{tab.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
