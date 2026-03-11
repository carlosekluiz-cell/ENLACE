'use client';

import { useState } from 'react';
import { Search, Database, ArrowRight, Sparkles } from 'lucide-react';

export default function ConsultaPage() {
  const [query, setQuery] = useState('');

  return (
    <div className="flex h-full flex-col" style={{ background: 'var(--bg-base)' }}>
      {/* Header */}
      <div className="px-6 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
        <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          Consulta SQL Natural
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
          Pergunte em português e receba dados do banco
        </p>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-6 py-8">
        <div className="mx-auto max-w-2xl space-y-6">
          {/* Welcome message */}
          <div className="text-center space-y-4 py-12">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full"
              style={{ background: 'var(--accent-subtle)' }}>
              <Sparkles size={28} style={{ color: 'var(--accent)' }} />
            </div>
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
              Consulta Inteligente
            </h2>
            <p className="text-sm max-w-md mx-auto" style={{ color: 'var(--text-muted)' }}>
              Faça perguntas sobre os dados da plataforma em linguagem natural.
              Exemplos: &ldquo;Quais municípios têm mais de 80% de fibra?&rdquo; ou
              &ldquo;Top 10 provedores por crescimento no último ano&rdquo;
            </p>
            <div className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-medium"
              style={{ background: 'var(--warning-subtle, color-mix(in srgb, var(--warning) 15%, transparent))', color: 'var(--warning)' }}>
              <Database size={14} /> Em breve — aguarde o módulo Text-to-SQL
            </div>
          </div>

          {/* Example queries */}
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {[
              'Municípios com penetração < 20%',
              'Provedores com mais de 10K assinantes',
              'Estados com maior crescimento de fibra',
              'Contratos governamentais últimos 12 meses',
            ].map((example) => (
              <button
                key={example}
                onClick={() => setQuery(example)}
                className="rounded-lg p-3 text-left text-sm transition-colors"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
              >
                <Search size={12} className="inline mr-2" style={{ color: 'var(--text-muted)' }} />
                {example}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Input bar */}
      <div className="px-6 py-4" style={{ borderTop: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
        <div className="mx-auto max-w-2xl flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Pergunte sobre os dados..."
            className="flex-1 rounded-lg px-4 py-2.5 text-sm outline-none"
            style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
          />
          <button
            disabled
            className="rounded-lg px-4 py-2.5 text-sm font-medium flex items-center gap-2 opacity-50"
            style={{ background: 'var(--accent)', color: 'white' }}
          >
            <ArrowRight size={16} /> Consultar
          </button>
        </div>
      </div>
    </div>
  );
}
