'use client';

import { useState } from 'react';
import { Info, X, Lock } from 'lucide-react';

interface DisclaimerBannerProps {
  /** 'yellow' for standard data pages, 'red' for contract-required pages */
  level?: 'yellow' | 'red';
  /** Override the default message */
  message?: string;
  /** Show a CTA link for contract-required features */
  ctaHref?: string;
  ctaLabel?: string;
  /** Allow dismissing the banner for the session */
  dismissible?: boolean;
}

export default function DisclaimerBanner({
  level = 'yellow',
  message,
  ctaHref,
  ctaLabel,
  dismissible = true,
}: DisclaimerBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const isRed = level === 'red';

  const defaultMessage = isRed
    ? 'Acesso completo a esta funcionalidade requer contratacao especifica com termo assinado. Os dados abaixo sao uma visualizacao limitada.'
    : 'Informacoes consolidadas de fontes publicas, apresentadas como referencia. Nao constitui recomendacao de investimento, parecer tecnico ou consultoria profissional.';

  const displayMessage = message || defaultMessage;

  const Icon = isRed ? Lock : Info;

  return (
    <div
      className="flex items-start gap-3 rounded-lg border px-4 py-3"
      style={{
        borderColor: isRed
          ? 'color-mix(in srgb, var(--accent) 40%, transparent)'
          : 'color-mix(in srgb, var(--warning) 30%, transparent)',
        backgroundColor: isRed
          ? 'color-mix(in srgb, var(--accent) 6%, transparent)'
          : 'color-mix(in srgb, var(--warning) 6%, transparent)',
      }}
    >
      <Icon
        size={16}
        className="mt-0.5 shrink-0"
        style={{ color: isRed ? 'var(--accent)' : 'var(--warning)' }}
      />
      <div className="flex-1 min-w-0">
        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          {displayMessage}
        </p>
        {ctaHref && (
          <a
            href={ctaHref}
            className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium"
            style={{ color: 'var(--accent)' }}
          >
            {ctaLabel || 'Solicitar contratacao'}
            <span aria-hidden="true">&rarr;</span>
          </a>
        )}
      </div>
      {dismissible && (
        <button
          onClick={() => setDismissed(true)}
          className="shrink-0 rounded p-0.5 transition-colors"
          style={{ color: 'var(--text-muted)' }}
          aria-label="Fechar aviso"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}
