'use client';

import { usePathname } from 'next/navigation';
import { Bell, Search, User } from 'lucide-react';

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/map': 'Coverage Map',
  '/opportunities': 'Opportunity Scoring',
  '/compliance': 'Compliance Dashboard',
  '/rural': 'Rural Planner',
  '/reports': 'Report Generator',
};

export default function Header() {
  const pathname = usePathname();
  const title = pageTitles[pathname || '/'] || 'ENLACE';

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-700/50 bg-slate-900/80 px-6 backdrop-blur-sm">
      {/* Left: Page title */}
      <div className="flex items-center gap-4 pl-10 lg:pl-0">
        <h1 className="text-lg font-semibold text-slate-100">{title}</h1>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="hidden items-center gap-2 rounded-lg bg-slate-800 px-3 py-1.5 md:flex">
          <Search size={16} className="text-slate-400" />
          <input
            type="text"
            placeholder="Search municipalities..."
            className="w-48 bg-transparent text-sm text-slate-200 placeholder-slate-500 focus:outline-none"
          />
        </div>

        {/* Notifications */}
        <button
          className="relative rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
          aria-label="Notifications"
        >
          <Bell size={18} />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-blue-500" />
        </button>

        {/* User */}
        <button
          className="flex items-center gap-2 rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
          aria-label="User menu"
        >
          <User size={18} />
          <span className="hidden text-sm md:inline">Admin</span>
        </button>
      </div>
    </header>
  );
}
