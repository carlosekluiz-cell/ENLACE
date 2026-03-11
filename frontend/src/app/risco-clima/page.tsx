'use client';

import { useState } from 'react';
import SimpleChart from '@/components/charts/SimpleChart';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatNumber } from '@/lib/format';
import { CloudRain, Wind, Thermometer, Zap, AlertTriangle } from 'lucide-react';

const STATES = ['', 'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO'];

function riskTierStyle(tier: string) {
  if (tier === 'critical') return { bg: 'color-mix(in srgb, var(--danger) 15%, transparent)', text: 'var(--danger)', label: 'Critico' };
  if (tier === 'high') return { bg: 'color-mix(in srgb, var(--warning) 15%, transparent)', text: 'var(--warning)', label: 'Alto' };
  if (tier === 'moderate') return { bg: 'color-mix(in srgb, var(--accent) 15%, transparent)', text: 'var(--accent)', label: 'Moderado' };
  return { bg: 'color-mix(in srgb, var(--success) 15%, transparent)', text: 'var(--success)', label: 'Baixo' };
}

export default function RiscoClimaPage() {
  const [stateFilter, setStateFilter] = useState('');
  const [view, setView] = useState<'risk' | 'seasonal'>('risk');

  const { data: riskData, loading: riskLoading } = useApi<any>(
    () => api.weatherRisk.risk({ state: stateFilter || undefined }),
    [stateFilter]
  );

  const { data: seasonalData, loading: seasonalLoading } = useApi<any>(
    () => api.weatherRisk.seasonal({ state: stateFilter || undefined }),
    [stateFilter]
  );

  const municipalities = riskData?.municipalities ?? [];
  const months = seasonalData?.months ?? [];

  const seasonalChartData = months.map((m: any) => ({
    name: m.month_name,
    risco: m.risk_score,
    vento: m.avg_wind_ms,
    chuva: m.avg_precip_mm,
  }));

  return (
    <div className="space-y-6 p-6">
      {(riskLoading || seasonalLoading) && (
        <div className="overflow-hidden absolute top-0 left-0 right-0 z-20" style={{ height: '2px' }}>
          <div className="pulso-progress-bar w-full" />
        </div>
      )}

      <div>
        <h1 className="flex items-center gap-3 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          <CloudRain size={28} style={{ color: 'var(--accent)' }} />
          Risco Climatico
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Correlacao entre condicoes climaticas e infraestrutura de telecomunicacoes
        </p>
      </div>

      <div className="flex gap-3 items-center">
        <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} className="pulso-input text-sm">
          {STATES.map((s) => <option key={s || '__all'} value={s}>{s || 'Todos os estados'}</option>)}
        </select>
        <div className="flex gap-1 rounded-lg p-0.5" style={{ backgroundColor: 'var(--bg-subtle)' }}>
          <button onClick={() => setView('risk')} className="rounded-md px-3 py-1 text-xs font-medium" style={{ backgroundColor: view === 'risk' ? 'var(--accent)' : 'transparent', color: view === 'risk' ? '#fff' : 'var(--text-muted)' }}>Risco</button>
          <button onClick={() => setView('seasonal')} className="rounded-md px-3 py-1 text-xs font-medium" style={{ backgroundColor: view === 'seasonal' ? 'var(--accent)' : 'transparent', color: view === 'seasonal' ? '#fff' : 'var(--text-muted)' }}>Sazonal</button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="pulso-card">
          <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Municipios</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>{riskLoading ? '...' : riskData?.total ?? 0}</p>
        </div>
        <div className="pulso-card">
          <div className="flex items-center gap-1"><AlertTriangle size={14} style={{ color: 'var(--danger)' }} /><p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Criticos</p></div>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--danger)' }}>{riskLoading ? '...' : riskData?.critical_count ?? 0}</p>
        </div>
        <div className="pulso-card">
          <div className="flex items-center gap-1"><Wind size={14} style={{ color: 'var(--warning)' }} /><p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Alto Risco</p></div>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--warning)' }}>{riskLoading ? '...' : riskData?.high_count ?? 0}</p>
        </div>
        <div className="pulso-card">
          <div className="flex items-center gap-1"><Zap size={14} style={{ color: 'var(--accent)' }} /><p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Mes mais arriscado</p></div>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--accent)' }}>{seasonalLoading ? '...' : seasonalData?.highest_risk_month ?? '--'}</p>
        </div>
      </div>

      {view === 'seasonal' && (
        <SimpleChart data={seasonalChartData} type="bar" xKey="name" yKey="risco" title="Risco Sazonal por Mes" height={280} loading={seasonalLoading} />
      )}

      {view === 'risk' && (
        <div className="pulso-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase" style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                <th className="pb-2 pr-4">Municipio</th>
                <th className="pb-2 pr-4">UF</th>
                <th className="pb-2 pr-4">Torres</th>
                <th className="pb-2 pr-4">Vento</th>
                <th className="pb-2 pr-4">Chuva</th>
                <th className="pb-2 pr-4">Temp</th>
                <th className="pb-2 pr-4">Score</th>
                <th className="pb-2">Risco</th>
              </tr>
            </thead>
            <tbody>
              {municipalities.slice(0, 50).map((m: any) => {
                const style = riskTierStyle(m.risk_tier);
                return (
                  <tr key={m.l2_id} style={{ borderBottom: '1px solid color-mix(in srgb, var(--border) 50%, transparent)' }}>
                    <td className="py-2 pr-4 font-medium" style={{ color: 'var(--text-primary)' }}>{m.name}</td>
                    <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{m.state}</td>
                    <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{m.tower_count}</td>
                    <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{m.weather?.max_wind_ms?.toFixed(1)} m/s</td>
                    <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{m.weather?.max_precip_mm?.toFixed(1)} mm</td>
                    <td className="py-2 pr-4" style={{ color: 'var(--text-secondary)' }}>{m.weather?.avg_temp_c?.toFixed(1)}&deg;C</td>
                    <td className="py-2 pr-4 font-bold" style={{ color: style.text }}>{m.risk_score}</td>
                    <td className="py-2">
                      <span className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ backgroundColor: style.bg, color: style.text }}>{style.label}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
