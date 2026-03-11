'use client';

import { useState } from 'react';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatNumber, formatBRL } from '@/lib/format';
import SimpleChart from '@/components/charts/SimpleChart';
import {
  GitCompareArrows, BarChart3, Shield, Activity, TrendingUp, AlertTriangle,
  Loader2, ChevronDown,
} from 'lucide-react';

const STATES = [
  '', 'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO',
  'MA', 'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR',
  'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
];

type TabKey = 'competition' | 'coverage' | 'social' | 'correlations' | 'investment' | 'anomalies';

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'competition', label: 'Competição', icon: <BarChart3 size={14} /> },
  { key: 'coverage', label: 'Cobertura', icon: <Shield size={14} /> },
  { key: 'social', label: 'Social', icon: <Activity size={14} /> },
  { key: 'correlations', label: 'Correlações', icon: <TrendingUp size={14} /> },
  { key: 'investment', label: 'Investimento', icon: <TrendingUp size={14} /> },
  { key: 'anomalies', label: 'Anomalias', icon: <AlertTriangle size={14} /> },
];

function StateFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="pulso-input text-xs">
      {STATES.map((s) => (
        <option key={s || '__all'} value={s}>{s || 'Todos os estados'}</option>
      ))}
    </select>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent)' }} />
    </div>
  );
}

function Card({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`pulso-card p-4 ${className}`}>
      <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>{title}</h3>
      {children}
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-xs border-b" style={{ borderColor: 'var(--border)' }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{value ?? '--'}</span>
    </div>
  );
}

// ── Tab 1: Competição ──────────────────────────────────────────────
function CompetitionTab({ state }: { state: string }) {
  const { data, loading } = useApi<any>(
    () => api.analytics.hhi({ state: state || undefined, limit: 100 }),
    [state]
  );

  if (loading) return <LoadingSpinner />;

  const dist = data?.distribution;
  const chartData = dist ? [
    { name: 'Competitivo', value: dist.competitive, fill: '#10b981' },
    { name: 'Moderado', value: dist.moderate, fill: '#f59e0b' },
    { name: 'Concentrado', value: dist.concentrated, fill: '#f97316' },
    { name: 'Dominante', value: dist.dominant, fill: '#ef4444' },
  ] : [];

  const hhiColor = (c: string) =>
    c === 'competitive' ? '#10b981' : c === 'moderate' ? '#f59e0b' : c === 'concentrated' ? '#f97316' : '#ef4444';

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        {chartData.map((d) => (
          <div key={d.name} className="pulso-card p-3 text-center">
            <p className="text-2xl font-bold" style={{ color: d.fill }}>{d.value}</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{d.name}</p>
          </div>
        ))}
      </div>

      {chartData.length > 0 && (
        <Card title="Distribuição HHI">
          <SimpleChart data={chartData} type="bar" xKey="name" yKey="value" height={200} />
        </Card>
      )}

      <Card title={`Municípios (${data?.total_municipalities ?? 0})`}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>Município</th>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>UF</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>HHI</th>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>Classificação</th>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>Líder</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>População</th>
              </tr>
            </thead>
            <tbody>
              {(data?.municipalities ?? []).slice(0, 50).map((m: any) => (
                <tr key={m.l2_id} className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <td className="py-1.5 px-2 font-medium" style={{ color: 'var(--text-primary)' }}>{m.municipality}</td>
                  <td className="py-1.5 px-2" style={{ color: 'var(--text-muted)' }}>{m.state}</td>
                  <td className="py-1.5 px-2 text-right font-mono" style={{ color: hhiColor(m.classification) }}>{m.hhi_index}</td>
                  <td className="py-1.5 px-2">
                    <span className="rounded-full px-2 py-0.5 text-[10px] font-medium text-white" style={{ backgroundColor: hhiColor(m.classification) }}>
                      {m.classification}
                    </span>
                  </td>
                  <td className="py-1.5 px-2" style={{ color: 'var(--text-muted)' }}>{m.leader ?? '--'}</td>
                  <td className="py-1.5 px-2 text-right" style={{ color: 'var(--text-primary)' }}>{formatNumber(m.population)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ── Tab 2: Cobertura ──────────────────────────────────────────────
function CoverageTab({ state }: { state: string }) {
  const { data: gaps, loading: gLoading } = useApi<any>(
    () => api.analytics.coverageGaps({ state: state || undefined, limit: 50 }),
    [state]
  );
  const { data: density, loading: dLoading } = useApi<any>(
    () => api.analytics.towerDensity({ state: state || undefined, limit: 30 }),
    [state]
  );

  if (gLoading || dLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      <Card title={`Lacunas de Cobertura (${gaps?.total_gaps ?? 0} municípios)`}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>Município</th>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>UF</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>População</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Provedores</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Assinantes</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Penetração %</th>
              </tr>
            </thead>
            <tbody>
              {(gaps?.gaps ?? []).map((g: any) => (
                <tr key={g.l2_id} className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <td className="py-1.5 px-2 font-medium" style={{ color: 'var(--text-primary)' }}>{g.municipality}</td>
                  <td className="py-1.5 px-2" style={{ color: 'var(--text-muted)' }}>{g.state}</td>
                  <td className="py-1.5 px-2 text-right" style={{ color: 'var(--text-primary)' }}>{formatNumber(g.population)}</td>
                  <td className="py-1.5 px-2 text-right" style={{ color: g.providers === 0 ? '#ef4444' : 'var(--text-primary)' }}>{g.providers}</td>
                  <td className="py-1.5 px-2 text-right font-mono" style={{ color: '#f59e0b' }}>{formatNumber(g.subscribers)}</td>
                  <td className="py-1.5 px-2 text-right" style={{ color: g.broadband_penetration_pct < 10 ? '#ef4444' : 'var(--text-primary)' }}>{g.broadband_penetration_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title={`Menor Penetração Banda Larga (${density?.total_ranked ?? 0})`}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                <th className="text-center py-2 px-2" style={{ color: 'var(--text-muted)' }}>#</th>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>Município</th>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>UF</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>População</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Provedores</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Penetração %</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Assin./km²</th>
              </tr>
            </thead>
            <tbody>
              {(density?.rankings ?? []).map((r: any) => (
                <tr key={r.l2_id} className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <td className="py-1.5 px-2 text-center" style={{ color: 'var(--text-muted)' }}>{r.rank}</td>
                  <td className="py-1.5 px-2 font-medium" style={{ color: 'var(--text-primary)' }}>{r.municipality}</td>
                  <td className="py-1.5 px-2" style={{ color: 'var(--text-muted)' }}>{r.state}</td>
                  <td className="py-1.5 px-2 text-right" style={{ color: 'var(--text-primary)' }}>{formatNumber(r.population)}</td>
                  <td className="py-1.5 px-2 text-right" style={{ color: r.providers === 0 ? '#ef4444' : 'var(--text-primary)' }}>{r.providers}</td>
                  <td className="py-1.5 px-2 text-right font-mono" style={{ color: '#f59e0b' }}>{r.penetration_pct}%</td>
                  <td className="py-1.5 px-2 text-right font-mono" style={{ color: 'var(--text-muted)' }}>{r.subs_per_km2}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ── Tab 3: Social ──────────────────────────────────────────────
function SocialTab({ state }: { state: string }) {
  const { data: schools, loading: sLoading } = useApi<any>(
    () => api.analytics.schoolGaps({ state: state || undefined, limit: 30 }),
    [state]
  );
  const { data: health, loading: hLoading } = useApi<any>(
    () => api.analytics.healthGaps({ state: state || undefined, limit: 30 }),
    [state]
  );

  if (sLoading || hLoading) return <LoadingSpinner />;

  const schoolChart = (schools?.by_state ?? []).slice(0, 15).map((s: any) => ({
    name: s.state,
    connected: s.connected_pct,
  }));

  const healthChart = (health?.by_state ?? []).slice(0, 15).map((h: any) => ({
    name: h.state,
    connected: h.connected_pct,
  }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Escolas - Resumo">
          <MetricRow label="Total de escolas" value={formatNumber(schools?.summary?.total_schools)} />
          <MetricRow label="Com internet" value={`${formatNumber(schools?.summary?.with_internet)} (${schools?.summary?.internet_pct ?? 0}%)`} />
          <MetricRow label="Total de alunos" value={formatNumber(schools?.summary?.total_students)} />
          <MetricRow label="Escolas rurais" value={formatNumber(schools?.summary?.rural_schools)} />
        </Card>
        <Card title="Unidades de Saúde - Resumo">
          <MetricRow label="Total de unidades" value={formatNumber(health?.summary?.total_facilities)} />
          <MetricRow label="Com internet" value={`${formatNumber(health?.summary?.with_internet)} (${health?.summary?.internet_pct ?? 0}%)`} />
          <MetricRow label="Total de leitos" value={formatNumber(health?.summary?.total_beds)} />
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Escolas - Conectividade por Estado (%)">
          <SimpleChart data={schoolChart} type="bar" xKey="name" yKey="connected" height={180} />
        </Card>
        <Card title="Saúde - Conectividade por Estado (%)">
          <SimpleChart data={healthChart} type="bar" xKey="name" yKey="connected" height={180} />
        </Card>
      </div>

      <Card title={`Escolas sem Internet (${schools?.gap_schools?.length ?? 0})`}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>Escola</th>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>Município</th>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>UF</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Alunos</th>
                <th className="text-center py-2 px-2" style={{ color: 'var(--text-muted)' }}>Rural</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Cobertura Mun. %</th>
              </tr>
            </thead>
            <tbody>
              {(schools?.gap_schools ?? []).slice(0, 20).map((s: any) => (
                <tr key={s.id} className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <td className="py-1.5 px-2 font-medium truncate max-w-[200px]" style={{ color: 'var(--text-primary)' }}>{s.school_name}</td>
                  <td className="py-1.5 px-2" style={{ color: 'var(--text-muted)' }}>{s.municipality}</td>
                  <td className="py-1.5 px-2" style={{ color: 'var(--text-muted)' }}>{s.state}</td>
                  <td className="py-1.5 px-2 text-right" style={{ color: 'var(--text-primary)' }}>{s.student_count ?? '--'}</td>
                  <td className="py-1.5 px-2 text-center">{s.rural ? 'Sim' : 'Não'}</td>
                  <td className="py-1.5 px-2 text-right font-mono" style={{ color: s.muni_penetration_pct < 10 ? '#ef4444' : 'var(--text-muted)' }}>{s.muni_penetration_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ── Tab 4: Correlações ──────────────────────────────────────────────
function CorrelationsTab({ state }: { state: string }) {
  const { data: weather, loading: wLoading } = useApi<any>(
    () => api.analytics.weatherCorrelation({ state: state || undefined }),
    [state]
  );
  const { data: employment, loading: eLoading } = useApi<any>(
    () => api.analytics.employmentCorrelation({ state: state || undefined, limit: 200 }),
    [state]
  );

  if (wLoading || eLoading) return <LoadingSpinner />;

  const weatherChart = (weather?.correlations ?? []).map((c: any) => ({
    name: c.state,
    correlation: c.correlation ?? 0,
    precipitation: c.mean_precipitation_mm ?? 0,
  }));

  const employmentChart = (employment?.data_points ?? []).slice(0, 50).map((d: any) => ({
    name: d.municipality?.substring(0, 12),
    jobs: d.formal_jobs,
    penetration: d.penetration_pct,
  }));

  return (
    <div className="space-y-4">
      <Card title="Correlação Clima × Qualidade">
        <div className="mb-2">
          <MetricRow label="Estados com dados" value={weather?.states_with_data ?? 0} />
          <MetricRow label="Meses analisados" value={weather?.months_analyzed ?? 0} />
        </div>
        {weatherChart.length > 0 ? (
          <SimpleChart data={weatherChart} type="bar" xKey="name" yKey="correlation" height={200} />
        ) : (
          <p className="text-xs py-4 text-center" style={{ color: 'var(--text-muted)' }}>Dados insuficientes para correlação</p>
        )}
        <div className="overflow-x-auto mt-3">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>Estado</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Correlação</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Precip. Média (mm)</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Qualidade Média</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Pontos</th>
              </tr>
            </thead>
            <tbody>
              {(weather?.correlations ?? []).map((c: any) => (
                <tr key={c.state} className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <td className="py-1.5 px-2 font-medium" style={{ color: 'var(--text-primary)' }}>{c.state}</td>
                  <td className="py-1.5 px-2 text-right font-mono" style={{ color: c.correlation && c.correlation < -0.3 ? '#ef4444' : c.correlation && c.correlation > 0.3 ? '#10b981' : 'var(--text-primary)' }}>
                    {c.correlation ?? '--'}
                  </td>
                  <td className="py-1.5 px-2 text-right" style={{ color: 'var(--text-muted)' }}>{c.mean_precipitation_mm ?? '--'}</td>
                  <td className="py-1.5 px-2 text-right" style={{ color: 'var(--text-muted)' }}>{c.mean_quality ?? '--'}</td>
                  <td className="py-1.5 px-2 text-right" style={{ color: 'var(--text-muted)' }}>{c.data_points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title={`Correlação Emprego × Banda Larga (r=${employment?.correlation_jobs_penetration ?? '--'})`}>
        {employmentChart.length > 0 ? (
          <SimpleChart data={employmentChart} type="bar" xKey="name" yKeys={['jobs', 'penetration']} height={200} />
        ) : (
          <p className="text-xs py-4 text-center" style={{ color: 'var(--text-muted)' }}>Dados insuficientes</p>
        )}
      </Card>
    </div>
  );
}

// ── Tab 5: Investimento ──────────────────────────────────────────────
function InvestmentTab({ state }: { state: string }) {
  const { data, loading } = useApi<any>(
    () => api.analytics.investmentPriority({ state: state || undefined, limit: 50 }),
    [state]
  );

  if (loading) return <LoadingSpinner />;

  const chartData = (data?.rankings ?? []).slice(0, 15).map((r: any) => ({
    name: r.municipality?.substring(0, 12),
    score: r.composite_score,
  }));

  return (
    <div className="space-y-4">
      <Card title="Pesos do Score Composto">
        <div className="flex flex-wrap gap-2">
          {data?.weights && Object.entries(data.weights).map(([k, v]: [string, any]) => (
            <span key={k} className="rounded-full px-3 py-1 text-xs" style={{ background: 'var(--bg-subtle)', color: 'var(--text-primary)' }}>
              {k}: {(v * 100).toFixed(0)}%
            </span>
          ))}
        </div>
      </Card>

      {chartData.length > 0 && (
        <Card title="Top 15 Municípios por Score">
          <SimpleChart data={chartData} type="bar" xKey="name" yKey="score" height={220} />
        </Card>
      )}

      <Card title={`Ranking de Prioridade (${data?.total_ranked ?? 0})`}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                <th className="text-center py-2 px-1" style={{ color: 'var(--text-muted)' }}>#</th>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>Município</th>
                <th className="text-left py-2 px-1" style={{ color: 'var(--text-muted)' }}>UF</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Score</th>
                <th className="text-right py-2 px-1" style={{ color: 'var(--text-muted)' }}>Oport.</th>
                <th className="text-right py-2 px-1" style={{ color: 'var(--text-muted)' }}>Pop.</th>
                <th className="text-right py-2 px-1" style={{ color: 'var(--text-muted)' }}>PIB</th>
                <th className="text-right py-2 px-1" style={{ color: 'var(--text-muted)' }}>Gap</th>
                <th className="text-right py-2 px-1" style={{ color: 'var(--text-muted)' }}>Cresc.</th>
              </tr>
            </thead>
            <tbody>
              {(data?.rankings ?? []).map((r: any) => (
                <tr key={r.l2_id} className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <td className="py-1.5 px-1 text-center" style={{ color: 'var(--text-muted)' }}>{r.rank}</td>
                  <td className="py-1.5 px-2 font-medium" style={{ color: 'var(--text-primary)' }}>{r.municipality}</td>
                  <td className="py-1.5 px-1" style={{ color: 'var(--text-muted)' }}>{r.state}</td>
                  <td className="py-1.5 px-2 text-right font-mono font-bold" style={{ color: 'var(--accent)' }}>{r.composite_score}</td>
                  <td className="py-1.5 px-1 text-right font-mono" style={{ color: 'var(--text-muted)' }}>{r.sub_scores?.opportunity}</td>
                  <td className="py-1.5 px-1 text-right font-mono" style={{ color: 'var(--text-muted)' }}>{r.sub_scores?.population}</td>
                  <td className="py-1.5 px-1 text-right font-mono" style={{ color: 'var(--text-muted)' }}>{r.sub_scores?.gdp}</td>
                  <td className="py-1.5 px-1 text-right font-mono" style={{ color: 'var(--text-muted)' }}>{r.sub_scores?.coverage_gap}</td>
                  <td className="py-1.5 px-1 text-right font-mono" style={{ color: 'var(--text-muted)' }}>{r.sub_scores?.growth_trend}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ── Tab 6: Anomalias ──────────────────────────────────────────────
function AnomaliesTab({ state }: { state: string }) {
  const { data, loading } = useApi<any>(
    () => api.analytics.anomalies({ state: state || undefined, limit: 50 }),
    [state]
  );

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="pulso-card p-3 text-center">
          <p className="text-2xl font-bold" style={{ color: 'var(--accent)' }}>{data?.total_anomalies ?? 0}</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>Anomalias Detectadas</p>
        </div>
        <div className="pulso-card p-3 text-center">
          <p className="text-2xl font-bold" style={{ color: '#ef4444' }}>
            {(data?.anomalies ?? []).filter((a: any) => a.severity === 'high').length}
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>Severidade Alta</p>
        </div>
        <div className="pulso-card p-3 text-center">
          <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{data?.method ?? '--'}</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>Método</p>
        </div>
      </div>

      <Card title="Anomalias de Qualidade">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>Município</th>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>UF</th>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>Métrica</th>
                <th className="text-left py-2 px-2" style={{ color: 'var(--text-muted)' }}>Período</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Valor</th>
                <th className="text-right py-2 px-2" style={{ color: 'var(--text-muted)' }}>Score</th>
                <th className="text-center py-2 px-2" style={{ color: 'var(--text-muted)' }}>Severidade</th>
              </tr>
            </thead>
            <tbody>
              {(data?.anomalies ?? []).map((a: any, i: number) => (
                <tr key={i} className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <td className="py-1.5 px-2 font-medium" style={{ color: 'var(--text-primary)' }}>{a.municipality}</td>
                  <td className="py-1.5 px-2" style={{ color: 'var(--text-muted)' }}>{a.state}</td>
                  <td className="py-1.5 px-2" style={{ color: 'var(--text-muted)' }}>{a.metric_type}</td>
                  <td className="py-1.5 px-2" style={{ color: 'var(--text-muted)' }}>{a.year_month}</td>
                  <td className="py-1.5 px-2 text-right font-mono" style={{ color: 'var(--text-primary)' }}>{a.value?.toLocaleString('pt-BR')}</td>
                  <td className="py-1.5 px-2 text-right font-mono" style={{ color: 'var(--text-primary)' }}>{a.anomaly_score}</td>
                  <td className="py-1.5 px-2 text-center">
                    <span className="rounded-full px-2 py-0.5 text-[10px] font-medium text-white" style={{
                      backgroundColor: a.severity === 'high' ? '#ef4444' : '#f59e0b',
                    }}>
                      {a.severity}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {(data?.anomalies ?? []).length === 0 && (
            <p className="text-xs py-6 text-center" style={{ color: 'var(--text-muted)' }}>Nenhuma anomalia detectada no período</p>
          )}
        </div>
      </Card>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────
export default function AnaliseCruzadaPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('competition');
  const [stateFilter, setStateFilter] = useState('');

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-base)' }}>
      <div className="mx-auto max-w-7xl px-4 py-6">
        {/* Header */}
        <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg" style={{ background: 'var(--accent)', color: '#fff' }}>
              <GitCompareArrows size={20} />
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Análise Cruzada</h1>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Cross-reference analytics em 11.7M+ registros</p>
            </div>
          </div>
          <div className="w-48">
            <StateFilter value={stateFilter} onChange={setStateFilter} />
          </div>
        </div>

        {/* Tabs */}
        <div className="flex flex-wrap gap-1 mb-6 p-1 rounded-lg" style={{ background: 'var(--bg-subtle)' }}>
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className="flex items-center gap-1.5 rounded-md px-3 py-2 text-xs font-medium transition-colors"
              style={{
                backgroundColor: activeTab === tab.key ? 'var(--accent)' : 'transparent',
                color: activeTab === tab.key ? '#fff' : 'var(--text-muted)',
              }}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'competition' && <CompetitionTab state={stateFilter} />}
        {activeTab === 'coverage' && <CoverageTab state={stateFilter} />}
        {activeTab === 'social' && <SocialTab state={stateFilter} />}
        {activeTab === 'correlations' && <CorrelationsTab state={stateFilter} />}
        {activeTab === 'investment' && <InvestmentTab state={stateFilter} />}
        {activeTab === 'anomalies' && <AnomaliesTab state={stateFilter} />}
      </div>
    </div>
  );
}
