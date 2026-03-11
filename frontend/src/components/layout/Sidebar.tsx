'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Menu,
  X,
  LogOut,
  Settings,
  User,
  Sun,
  Moon,
  ChevronDown,
  Map,
  TrendingUp,
  Antenna,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { navSections, findSectionForPath, type NavSection, type NavItem } from '@/lib/navigation';

// ── SidebarNavLink ───────────────────────────────────────────────────────

function SidebarNavLink({
  item,
  pathname,
  onClick,
}: {
  item: NavItem;
  pathname: string;
  onClick: () => void;
}) {
  const Icon = item.icon;
  const isActive =
    item.href === '/'
      ? pathname === '/'
      : pathname === item.href || pathname.startsWith(item.href + '/');

  return (
    <Link
      href={item.href}
      onClick={onClick}
      className={clsx(
        'flex items-center gap-3 rounded-md px-3 text-[13px] font-medium transition-colors',
        isActive ? 'border-l-2' : 'border-l-2 border-transparent'
      )}
      style={{
        height: '34px',
        color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
        background: isActive ? 'var(--accent-subtle)' : 'transparent',
        borderLeftColor: isActive ? 'var(--accent)' : 'transparent',
      }}
    >
      <span style={{ color: isActive ? 'var(--accent)' : 'var(--text-muted)' }}>
        <Icon size={15} />
      </span>
      <span className="flex-1">{item.label}</span>
      {item.badge && (
        <span
          className="rounded px-1.5 py-0.5 text-[9px] font-bold leading-none"
          style={{
            background: item.badge === 'NEW' ? 'var(--accent)' : 'var(--text-muted)',
            color: '#fff',
          }}
        >
          {item.badge}
        </span>
      )}
    </Link>
  );
}

// ── SidebarSection ───────────────────────────────────────────────────────

function SidebarSection({
  section,
  isOpen,
  onToggle,
  pathname,
  onNavigate,
}: {
  section: NavSection;
  isOpen: boolean;
  onToggle: () => void;
  pathname: string;
  onNavigate: () => void;
}) {
  return (
    <div className="mb-1">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between rounded px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider transition-colors hover:opacity-80"
        style={{ color: 'var(--text-muted)' }}
      >
        {section.label}
        <ChevronDown
          size={14}
          className={clsx('transition-transform duration-200', isOpen ? 'rotate-0' : '-rotate-90')}
        />
      </button>
      <div
        className={clsx(
          'overflow-hidden transition-all duration-200 ease-in-out',
          isOpen ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
        )}
      >
        <div className="space-y-0.5 py-0.5">
          {section.items.map((item) => (
            <SidebarNavLink
              key={item.href}
              item={item}
              pathname={pathname}
              onClick={onNavigate}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main Sidebar ─────────────────────────────────────────────────────────

export default function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, logout, hasRole } = useAuth();
  const { resolvedTheme, setTheme } = useTheme();

  // Track which sections are expanded
  const [openSections, setOpenSections] = useState<Set<string>>(new Set());

  // Auto-expand the section containing the active path
  useEffect(() => {
    const activeSection = findSectionForPath(pathname);
    if (activeSection) {
      setOpenSections((prev) => {
        if (prev.has(activeSection)) return prev;
        const next = new Set(prev);
        next.add(activeSection);
        return next;
      });
    }
  }, [pathname]);

  if (pathname === '/login') return null;

  const toggleSection = (id: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

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

        {/* Navigation — Grouped Sections */}
        <nav className="flex-1 overflow-y-auto px-2 py-2">
          {navSections.map((section) => (
            <SidebarSection
              key={section.id}
              section={section}
              isOpen={openSections.has(section.id)}
              onToggle={() => toggleSection(section.id)}
              pathname={pathname}
              onNavigate={() => setMobileOpen(false)}
            />
          ))}

          {/* Admin — role-gated, outside sections */}
          {hasRole('admin') && (
            <div className="mt-2 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
              <Link
                href="/admin"
                onClick={() => setMobileOpen(false)}
                className="flex items-center gap-3 rounded-md px-3 text-[13px] font-medium border-l-2 border-transparent"
                style={{
                  height: '34px',
                  color: pathname === '/admin' ? 'var(--accent)' : 'var(--text-muted)',
                  background: pathname === '/admin' ? 'var(--accent-subtle)' : 'transparent',
                  borderLeftColor: pathname === '/admin' ? 'var(--accent)' : 'transparent',
                }}
              >
                <Settings size={15} />
                Admin
              </Link>
            </div>
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
              <Link
                href="/configuracoes"
                onClick={() => setMobileOpen(false)}
                className="rounded p-1.5 transition-colors"
                style={{ color: 'var(--text-muted)' }}
                aria-label="Configurações"
              >
                <Settings size={16} />
              </Link>

              <button
                onClick={toggleTheme}
                className="rounded p-1.5 transition-colors"
                style={{ color: 'var(--text-muted)' }}
                aria-label={resolvedTheme === 'dark' ? 'Modo claro' : 'Modo escuro'}
              >
                {resolvedTheme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              </button>
            </div>

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

// ── Mobile Bottom Tab Bar ────────────────────────────────────────────────

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
