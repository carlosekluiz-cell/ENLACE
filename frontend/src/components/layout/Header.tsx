'use client';

import { usePathname } from 'next/navigation';
import { Bell, Search, User } from 'lucide-react';

const pageTitles: Record<string, string> = {
  '/': 'Painel',
  '/map': 'Mapa de Cobertura',
  '/opportunities': 'Scoring de Oportunidades',
  '/design': 'Projeto de Cobertura RF',
  '/compliance': 'Conformidade Regulatória',
  '/rural': 'Conectividade Rural',
  '/mna': 'Fusões & Aquisições',
  '/reports': 'Gerador de Relatórios',
  '/login': 'Entrar',
};

export default function Header() {
  const pathname = usePathname();
  const title = pageTitles[pathname || '/'] || 'ENLACE';

  // Esconder header na tela de login
  if (pathname === '/login') return null;

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-700/50 bg-slate-900/80 px-6 backdrop-blur-sm">
      {/* Título da página */}
      <div className="flex items-center gap-4 pl-10 lg:pl-0">
        <h1 className="text-lg font-semibold text-slate-100">{title}</h1>
      </div>

      {/* Ações */}
      <div className="flex items-center gap-3">
        {/* Busca */}
        <div className="hidden items-center gap-2 rounded-lg bg-slate-800 px-3 py-1.5 md:flex">
          <Search size={16} className="text-slate-400" />
          <input
            type="text"
            placeholder="Buscar municípios..."
            className="w-48 bg-transparent text-sm text-slate-200 placeholder-slate-500 focus:outline-none"
          />
        </div>

        {/* Notificações */}
        <button
          className="relative rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
          aria-label="Notificações"
        >
          <Bell size={18} />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-blue-500" />
        </button>

        {/* Usuário */}
        <button
          className="flex items-center gap-2 rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
          aria-label="Menu do usuário"
        >
          <User size={18} />
          <span className="hidden text-sm md:inline">Usuário</span>
        </button>
      </div>
    </header>
  );
}
