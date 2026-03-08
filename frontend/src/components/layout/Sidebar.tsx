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
  Radio,
  Briefcase,
  Antenna,
  LogOut,
} from 'lucide-react';
import { clsx } from 'clsx';
import { clearToken, isAuthenticated } from '@/lib/api';

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { label: 'Mapa', href: '/map', icon: <Map size={20} /> },
  {
    label: 'Oportunidades',
    href: '/opportunities',
    icon: <TrendingUp size={20} />,
  },
  {
    label: 'Projeto RF',
    href: '/design',
    icon: <Antenna size={20} />,
  },
  { label: 'Conformidade', href: '/compliance', icon: <Shield size={20} /> },
  { label: 'Rural', href: '/rural', icon: <Mountain size={20} /> },
  {
    label: 'F&A',
    href: '/mna',
    icon: <Briefcase size={20} />,
  },
  { label: 'Relatórios', href: '/reports', icon: <FileText size={20} /> },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    clearToken();
    window.location.href = '/login';
  };

  // Esconder sidebar na tela de login
  if (pathname === '/login') return null;

  return (
    <>
      {/* Botão mobile */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed left-4 top-4 z-50 rounded-md bg-slate-800 p-2 text-slate-300 lg:hidden"
        aria-label="Abrir menu"
      >
        <Menu size={20} />
      </button>

      {/* Overlay mobile */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-slate-900 border-r border-slate-700/50 transition-transform duration-200 lg:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between px-6 border-b border-slate-700/50">
          <Link href="/" className="flex items-center gap-2">
            <Radio className="text-blue-500" size={24} />
            <span className="text-xl font-bold tracking-tight">
              <span className="text-blue-500">EN</span>
              <span className="text-slate-100">LACE</span>
            </span>
          </Link>
          <button
            onClick={() => setMobileOpen(false)}
            className="text-slate-400 hover:text-slate-200 lg:hidden"
            aria-label="Fechar menu"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navegação */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map((item) => {
            const isActive =
              pathname === item.href || pathname?.startsWith(item.href + '/');
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={clsx(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-blue-600/20 text-blue-400'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                )}
              >
                <span
                  className={clsx(
                    isActive ? 'text-blue-400' : 'text-slate-500'
                  )}
                >
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Rodapé */}
        <div className="border-t border-slate-700/50 px-3 py-4 space-y-2">
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
          >
            <LogOut size={20} className="text-slate-500" />
            Sair
          </button>
          <div className="px-3">
            <p className="text-xs text-slate-500">Plataforma ENLACE</p>
            <p className="text-xs text-slate-600">Inteligência Telecom Brasil</p>
          </div>
        </div>
      </aside>
    </>
  );
}
