'use client';

import { useState } from 'react';
import SimpleChart from '@/components/charts/SimpleChart';
import { useApi, useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatNumber, formatPct } from '@/lib/format';
import { Gauge, AlertTriangle, Radio, TrendingUp } from 'lucide-react';

const STATES = ['', 'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO'];

function riskBadge(level: string) {
  if (level === 'critical') return { bg: 'color-mix(in srgb, var(--danger) 15%, transparent)', text: 'var(--danger)', label: 'Critico' };
  if (level === 'warning') return { bg: 'color-mix(in srgb, var(--warning) 15%, transparent)', text: 'var(--warning)', label: 'Alerta' };
  return { bg: 'color-mix(in srgb, var(--success) 15%, transparent)', text: 'var(--success)', label: 'Normal' };
}

export default function BackhaulPage() {
  const [stateFilter, setStateFilter] = useState('');
  const [selectedMuni, setSelectedMuni] = useState<number | null>(null);

  const { data, loading } = useApi<any>(
    () => api.backhaul.utilization({ state: stateFilter || undefined }),
    [stateFilter]
  );

  const { data: forecast, loading: forecastLoading, execute: fetchForecast } = useLazyApi<any, number>(
    (id) => api.backhaul.forecast(id)
  );

  const handleSelectMuni = (l2Id: number) => {
    setSelectedMuni(l2Id);
    fetchForecast(l2Id);
  };

  const municipalities = data?.municipalities ?? [];

  const chartData = municipalities.slice(0, 15).map((m: any) => ({
    name: m.name?.substring(0, 12) ?? String(m.l2_id),
    utilizacao: m.utilization_pct,
  }));

  return (
    <div className="space-y-6 p-6">
      {loading && (
        <div className="overflow-hidden absolute top-0 left-0 right-0 z-20" style={{ height: '2px' }}>
          <div className="pulso-progress-bar w-full" />
        </div>
      )}

      <div>
        <h1 className="flex items-center gap-3 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          <Gauge size={28} style={{ color: 'var(--accent)' }} />
          Backhaul
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Modelo de utilizacao e previsao de congestionamento do backhaul
        </p>
      </div>

      <div className="flex gap-3">
        <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} className="pulso-input text-sm">
          {STATES.map((s) => <option key={s || '__all'} value={s}>{s || 'Todos os estados'}</option>)}
        </select>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="pulso-card">
          <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Municipios</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>{loading ? '...' : data?.total ?? 0}</p>
        </div>
        <div className="pulso-card" style={{ borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)' }}>
          <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Criticos (&gt;85%)</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--danger)' }}>{loading ? '...' : data?.critical_count ?? 0}</p>
        </div>
        <div className="pulso-card" style={{ borderColor: 'color-mix(in srgb, var(--warning) 30%, transparent)' }}>
          <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Alertas (&gt;70%)</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--warning)' }}>{loading ? '...' : data?.warning_count ?? 0}</p>
        </div>
      </div>

      <SimpleChart data={chartData} type="bar" xKey="name" yKey="utilizacao" title="Utilizacao de Backhaul (%)" height={250} loading={loading} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Municipality list */}
        <div className="pulso-card overflow-y-auto" style={{ maxHeight: '500px' }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>Municipios</h3>
          <div className="space-y-2">
            {municipalities.map((m: any) => {
              const badge = riskBadge(m.risk_level);
              return (
                <button
                  key={m.l2_id}
                  onClick={() => handleSelectMuni(m.l2_id)}
                  className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left transition-colors hover:opacity-80"
                  style={{
                    backgroundColor: selectedMuni === m.l2_id ? 'var(--accent-subtle)' : 'var(--bg-subtle)',
                    border: selectedMuni === m.l2_id ? '1px solid var(--accent)' : '1px solid transparent',
                  }}
                >
                  <div>
                    <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{m.name}</p>
                    <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{m.state} | {formatNumber(m.subscribers)} assinantes | {m.tower_count} torres</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold" style={{ color: badge.text }}>{m.utilization_pct.toFixed(1)}%</span>
                    <span className="rounded-full px-1.5 py-0.5 text-[9px] font-medium" style={{ backgroundColor: badge.bg, color: badge.text }}>{badge.label}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Forecast panel */}
        <div className="pulso-card">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
            <TrendingUp size={16} style={{ color: 'var(--accent)' }} />
            Previsao de Utilizacao
          </h3>
          {!selectedMuni && (
            <p className="py-12 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              Selecione um municipio para ver a previsao
            </p>
          )}
          {forecastLoading && <p className="py-12 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Carregando previsao...</p>}
          {forecast && !forecastLoading && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Utilizacao Atual</p>
                  <p className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{forecast.current_utilization_pct?.toFixed(1)}%</p>
                </div>
                <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Congestionamento em</p>
                  <p className="text-xl font-bold" style={{ color: forecast.congestion_month ? 'var(--danger)' : 'var(--success)' }}>
                    {forecast.congestion_month ?? 'Nao previsto'}
                  </p>
                </div>
              </div>
              {forecast.forecast && (
                <SimpleChart
                  data={forecast.forecast.map((f: any) => ({ name: f.year_month, utilizacao: f.utilization_pct }))}
                  type="line"
                  xKey="name"
                  yKey="utilizacao"
                  title="Previsao de Utilizacao (%)"
                  height={200}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
