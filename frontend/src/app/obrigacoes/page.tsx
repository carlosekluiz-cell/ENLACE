'use client';

import { useState } from 'react';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatNumber, formatPct } from '@/lib/format';
import { Shield, Clock, CheckCircle2, AlertTriangle, XCircle, ChevronDown } from 'lucide-react';

function statusStyle(status: string) {
  if (status === 'on_track') return { bg: 'color-mix(in srgb, var(--success) 15%, transparent)', text: 'var(--success)', label: 'No Prazo' };
  if (status === 'at_risk') return { bg: 'color-mix(in srgb, var(--warning) 15%, transparent)', text: 'var(--warning)', label: 'Em Risco' };
  return { bg: 'color-mix(in srgb, var(--danger) 15%, transparent)', text: 'var(--danger)', label: 'Atrasado' };
}

function daysLabel(days: number) {
  if (days < 0) return `${Math.abs(days)} dias atrasado`;
  if (days < 30) return `${days} dias`;
  if (days < 365) return `${Math.round(days / 30)} meses`;
  return `${(days / 365).toFixed(1)} anos`;
}

export default function ObrigacoesPage() {
  const [providerFilter, setProviderFilter] = useState('');

  const { data: obligations, loading } = useApi<any>(
    () => api.obligations.fiveG(),
    []
  );

  const { data: gapData, loading: gapLoading } = useApi<any>(
    () => api.obligations.gapAnalysis(),
    []
  );

  const obList = obligations?.obligations ?? [];
  const gaps = gapData?.states ?? [];

  return (
    <div className="space-y-6 p-6">
      {loading && (
        <div className="overflow-hidden absolute top-0 left-0 right-0 z-20" style={{ height: '2px' }}>
          <div className="pulso-progress-bar w-full" />
        </div>
      )}

      <div>
        <h1 className="flex items-center gap-3 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          <Shield size={28} style={{ color: 'var(--accent)' }} />
          Obrigações 5G
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Acompanhamento das obrigações do leilão 5G — CLARO, VIVO, TIM, WINITY
        </p>
      </div>

      {/* Obligation cards */}
      <div className="space-y-4">
        {obList.map((obl: any) => {
          const style = statusStyle(obl.status);
          return (
            <div key={obl.obligation_id} className="pulso-card">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{obl.description}</h3>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Prazo: {obl.deadline}</span>
                    <span className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ backgroundColor: style.bg, color: style.text }}>{style.label}</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="flex items-center gap-1">
                    <Clock size={14} style={{ color: obl.days_remaining < 365 ? 'var(--warning)' : 'var(--text-muted)' }} />
                    <span className="text-sm font-bold" style={{ color: obl.days_remaining < 365 ? 'var(--warning)' : 'var(--text-primary)' }}>
                      {daysLabel(obl.days_remaining)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Progress bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-[10px]">
                  <span style={{ color: 'var(--text-muted)' }}>Progresso: {obl.progress_pct?.toFixed(1)}%</span>
                  <span style={{ color: 'var(--text-muted)' }}>Meta: {formatNumber(obl.target)}</span>
                </div>
                <div className="h-3 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(obl.progress_pct, 100)}%`, backgroundColor: style.text }} />
                </div>
                <div className="flex justify-between text-[10px]">
                  <span style={{ color: 'var(--text-muted)' }}>Estimado: {formatNumber(obl.estimated_progress)}</span>
                  <span style={{ color: 'var(--text-muted)' }}>Tempo decorrido: {obl.elapsed_pct?.toFixed(1)}%</span>
                </div>
              </div>

              {/* Operators */}
              <div className="mt-3 flex flex-wrap gap-1">
                {obl.operators?.map((op: string) => (
                  <span key={op} className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ backgroundColor: 'var(--accent-subtle)', color: 'var(--accent)' }}>{op}</span>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Gap Analysis */}
      <div className="pulso-card">
        <h2 className="flex items-center gap-2 text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          <AlertTriangle size={16} style={{ color: 'var(--warning)' }} />
          Análise de Lacunas por Estado
        </h2>
        {gapData && (
          <div className="mb-4 grid grid-cols-2 gap-3">
            <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
              <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Municípios sem cobertura</p>
              <p className="text-xl font-bold" style={{ color: 'var(--danger)' }}>{formatNumber(gapData.total_uncovered)}</p>
            </div>
            <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
              <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>População sem cobertura</p>
              <p className="text-xl font-bold" style={{ color: 'var(--danger)' }}>{formatNumber(gapData.total_uncovered_population)}</p>
            </div>
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase" style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                <th className="pb-2 pr-4">Estado</th>
                <th className="pb-2 pr-4">Total</th>
                <th className="pb-2 pr-4">Cobertos</th>
                <th className="pb-2 pr-4">Sem cobertura</th>
                <th className="pb-2 pr-4">Cobertura %</th>
                <th className="pb-2">Pop. sem cobertura</th>
              </tr>
            </thead>
            <tbody>
              {gaps.slice(0, 27).map((g: any) => (
                <tr key={g.state} style={{ borderBottom: '1px solid color-mix(in srgb, var(--border) 50%, transparent)' }}>
                  <td className="py-2 pr-4 font-medium" style={{ color: 'var(--text-primary)' }}>{g.state}</td>
                  <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{g.total_municipalities}</td>
                  <td className="py-2 pr-4" style={{ color: 'var(--success)' }}>{g.covered}</td>
                  <td className="py-2 pr-4 font-bold" style={{ color: g.uncovered > 0 ? 'var(--danger)' : 'var(--success)' }}>{g.uncovered}</td>
                  <td className="py-2 pr-4">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-16 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                        <div className="h-full rounded-full" style={{ width: `${g.coverage_pct}%`, backgroundColor: g.coverage_pct > 80 ? 'var(--success)' : g.coverage_pct > 50 ? 'var(--warning)' : 'var(--danger)' }} />
                      </div>
                      <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{g.coverage_pct?.toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{formatNumber(g.uncovered_population)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
