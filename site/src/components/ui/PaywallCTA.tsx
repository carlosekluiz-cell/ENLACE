'use client';

import Link from 'next/link';
import { Lock } from 'lucide-react';

interface PaywallCTAProps {
  /** Short value proposition text */
  title?: string;
  /** Which page to link for unlock */
  href?: string;
  /** Button label */
  buttonLabel?: string;
  children: React.ReactNode;
}

/**
 * Paywall overlay — blurs content and shows a lock icon + CTA button.
 * Used on Raio-X to tease locked intelligence data.
 */
export default function PaywallCTA({
  title = 'Desbloqueie dados completos',
  href = '/precos',
  buttonLabel = 'Desbloquear',
  children,
}: PaywallCTAProps) {
  return (
    <div className="relative">
      {/* Blurred content */}
      <div
        style={{ filter: 'blur(6px)', pointerEvents: 'none', userSelect: 'none' }}
        aria-hidden="true"
      >
        {children}
      </div>

      {/* Overlay */}
      <div
        className="absolute inset-0 flex flex-col items-center justify-center gap-3 z-10"
        style={{ background: 'rgba(255,255,255,0.6)' }}
      >
        <div
          className="flex items-center justify-center h-10 w-10"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
        >
          <Lock size={18} style={{ color: 'var(--accent)' }} />
        </div>
        <p className="text-sm font-medium text-center px-4" style={{ color: 'var(--text-primary)' }}>
          {title}
        </p>
        <Link
          href={href}
          className="pulso-btn-primary text-sm px-6 py-2 inline-flex items-center gap-2"
        >
          <Lock size={12} />
          {buttonLabel}
        </Link>
      </div>
    </div>
  );
}
