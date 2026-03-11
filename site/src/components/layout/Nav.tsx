'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Menu, X } from 'lucide-react';
import { NAV_LINKS } from '@/lib/constants';

export default function Nav() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
      style={{
        background: scrolled ? 'rgba(250,250,249,0.95)' : 'transparent',
        borderBottom: scrolled ? '1px solid var(--border)' : '1px solid transparent',
        backdropFilter: scrolled ? 'blur(12px)' : 'none',
      }}
    >
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div
            className="flex h-8 w-8 items-center justify-center text-sm font-bold"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            P
          </div>
          <span
            className="font-serif text-lg font-semibold tracking-tight transition-colors duration-300"
            style={{ color: scrolled ? 'var(--text-primary)' : 'var(--text-on-dark)' }}
          >
            Pulso
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden items-center gap-7 md:flex">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.label}
              href={link.href}
              className="text-sm transition-colors duration-300"
              style={{ color: scrolled ? 'var(--text-secondary)' : 'var(--text-on-dark-secondary)' }}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* CTA */}
        <div className="hidden items-center gap-4 md:flex">
          <Link
            href="/login"
            className="text-sm transition-colors duration-300"
            style={{ color: scrolled ? 'var(--text-secondary)' : 'var(--text-on-dark-secondary)' }}
          >
            Entrar
          </Link>
          <Link href="/cadastro" className={scrolled ? 'pulso-btn-primary' : 'pulso-btn-dark'}>
            Começar
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="md:hidden transition-colors duration-300"
          style={{ color: scrolled ? 'var(--text-secondary)' : 'var(--text-on-dark-secondary)' }}
          aria-label="Menu"
        >
          {mobileOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div
          className="px-4 py-4 md:hidden"
          style={{
            background: 'var(--bg-surface)',
            borderTop: '1px solid var(--border)',
          }}
        >
          <nav className="space-y-3">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.label}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className="block text-sm"
                style={{ color: 'var(--text-secondary)' }}
              >
                {link.label}
              </Link>
            ))}
            <div className="pt-3" style={{ borderTop: '1px solid var(--border)' }}>
              <Link
                href="/cadastro"
                className="pulso-btn-primary w-full text-center"
                onClick={() => setMobileOpen(false)}
              >
                Começar
              </Link>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
