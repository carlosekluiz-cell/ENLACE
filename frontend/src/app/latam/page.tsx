'use client';

import { useState, useEffect } from 'react';
import {
  Globe,
  BarChart3,
  Database,
  Clock,
  Code2,
  Loader2,
  Signal,
  Wifi,
  MapPin,
  Building2,
  Users,
  FileText,
  Shield,
  Heart,
  GraduationCap,
  AlertTriangle,
  Gauge,
  Radio,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatNumber, formatCompact } from '@/lib/format';

// ─── Static Data ─────────────────────────────────────────────────────────────

const PIPELINE_TYPES = [
  'census', 'nbi', 'broadband', 'providers', 'contracts',
  'health', 'schools', 'complaints', 'quality', 'peering',
] as const;

const PIPELINE_LABELS: Record<string, string> = {
  census: 'Censo',
  nbi: 'Plano Banda Larga',
  broadband: 'Assinantes',
  providers: 'Provedores',
  contracts: 'Contratos Gov.',
  health: 'Saúde',
  schools: 'Escolas',
  complaints: 'Reclamações',
  quality: 'Qualidade',
  peering: 'Peering/IXP',
};

interface CountryData {
  code: string;
  name: string;
  flag: string;
  tier: number;
  score: number;
  max: number;
  extra?: string[];
  pipelines: Record<string, number>;
}

const COUNTRIES: CountryData[] = [
  {
    code: 'CO', name: 'Colômbia', flag: '\u{1F1E8}\u{1F1F4}', tier: 0, score: 12, max: 12,
    extra: ['emf', 'digital_centers'],
    pipelines: { census: 1, nbi: 1, broadband: 1, providers: 1, contracts: 1, health: 1, schools: 1, complaints: 1, quality: 1, peering: 1 },
  },
  {
    code: 'BR', name: 'Brasil', flag: '\u{1F1E7}\u{1F1F7}', tier: 0, score: 10, max: 10,
    pipelines: { census: 1, nbi: 1, broadband: 1, providers: 1, contracts: 1, health: 1, schools: 1, complaints: 1, quality: 1, peering: 1 },
  },
  {
    code: 'MX', name: 'México', flag: '\u{1F1F2}\u{1F1FD}', tier: 1, score: 10, max: 10,
    pipelines: { census: 1, nbi: 1, broadband: 1, providers: 1, contracts: 1, health: 1, schools: 1, complaints: 1, quality: 1, peering: 1 },
  },
  {
    code: 'AR', name: 'Argentina', flag: '\u{1F1E6}\u{1F1F7}', tier: 1, score: 10, max: 10,
    pipelines: { census: 1, nbi: 1, broadband: 1, providers: 1, contracts: 1, health: 1, schools: 1, complaints: 1, quality: 1, peering: 1 },
  },
  {
    code: 'CL', name: 'Chile', flag: '\u{1F1E8}\u{1F1F1}', tier: 1, score: 10, max: 10,
    pipelines: { census: 1, nbi: 1, broadband: 1, providers: 1, contracts: 1, health: 1, schools: 1, complaints: 1, quality: 1, peering: 1 },
  },
  {
    code: 'PE', name: 'Peru', flag: '\u{1F1F5}\u{1F1EA}', tier: 1, score: 10, max: 10,
    pipelines: { census: 1, nbi: 1, broadband: 1, providers: 1, contracts: 1, health: 1, schools: 1, complaints: 1, quality: 1, peering: 1 },
  },
  {
    code: 'UY', name: 'Uruguai', flag: '\u{1F1FA}\u{1F1FE}', tier: 2, score: 9, max: 10,
    pipelines: { census: 1, nbi: 1, broadband: 1, providers: 1, contracts: 1, health: 1, schools: 1, complaints: 0, quality: 1, peering: 1 },
  },
  {
    code: 'EC', name: 'Equador', flag: '\u{1F1EA}\u{1F1E8}', tier: 2, score: 8, max: 10,
    pipelines: { census: 1, nbi: 1, broadband: 1, providers: 1, contracts: 0, health: 1, schools: 1, complaints: 0, quality: 1, peering: 1 },
  },
  {
    code: 'DO', name: 'Rep. Dominicana', flag: '\u{1F1E9}\u{1F1F4}', tier: 2, score: 7, max: 10,
    pipelines: { census: 1, nbi: 0, broadband: 1, providers: 1, contracts: 1, health: 1, schools: 1, complaints: 0, quality: 0, peering: 1 },
  },
  {
    code: 'PY', name: 'Paraguai', flag: '\u{1F1F5}\u{1F1FE}', tier: 2, score: 7, max: 10,
    pipelines: { census: 1, nbi: 1, broadband: 1, providers: 1, contracts: 0, health: 1, schools: 1, complaints: 0, quality: 0, peering: 1 },
  },
  {
    code: 'PA', name: 'Panamá', flag: '\u{1F1F5}\u{1F1E6}', tier: 3, score: 6, max: 10,
    pipelines: { census: 1, nbi: 0, broadband: 1, providers: 1, contracts: 0, health: 1, schools: 1, complaints: 0, quality: 0, peering: 1 },
  },
  {
    code: 'CR', name: 'Costa Rica', flag: '\u{1F1E8}\u{1F1F7}', tier: 3, score: 6, max: 10,
    pipelines: { census: 1, nbi: 0, broadband: 1, providers: 1, contracts: 0, health: 1, schools: 1, complaints: 0, quality: 0, peering: 1 },
  },
  {
    code: 'GT', name: 'Guatemala', flag: '\u{1F1EC}\u{1F1F9}', tier: 3, score: 5, max: 10,
    pipelines: { census: 1, nbi: 0, broadband: 1, providers: 1, contracts: 0, health: 1, schools: 1, complaints: 0, quality: 0, peering: 0 },
  },
  {
    code: 'BO', name: 'Bolívia', flag: '\u{1F1E7}\u{1F1F4}', tier: 3, score: 5, max: 10,
    pipelines: { census: 1, nbi: 0, broadband: 1, providers: 1, contracts: 0, health: 1, schools: 1, complaints: 0, quality: 0, peering: 0 },
  },
  {
    code: 'HN', name: 'Honduras', flag: '\u{1F1ED}\u{1F1F3}', tier: 3, score: 4, max: 10,
    pipelines: { census: 1, nbi: 0, broadband: 1, providers: 1, contracts: 0, health: 0, schools: 1, complaints: 0, quality: 0, peering: 0 },
  },
  {
    code: 'SV', name: 'El Salvador', flag: '\u{1F1F8}\u{1F1FB}', tier: 3, score: 4, max: 10,
    pipelines: { census: 1, nbi: 0, broadband: 1, providers: 1, contracts: 0, health: 0, schools: 1, complaints: 0, quality: 0, peering: 0 },
  },
  {
    code: 'VE', name: 'Venezuela', flag: '\u{1F1FB}\u{1F1EA}', tier: 3, score: 3, max: 10,
    pipelines: { census: 1, nbi: 0, broadband: 0, providers: 1, contracts: 0, health: 0, schools: 1, complaints: 0, quality: 0, peering: 0 },
  },
  {
    code: 'NI', name: 'Nicarágua', flag: '\u{1F1F3}\u{1F1EE}', tier: 3, score: 3, max: 10,
    pipelines: { census: 1, nbi: 0, broadband: 0, providers: 1, contracts: 0, health: 0, schools: 1, complaints: 0, quality: 0, peering: 0 },
  },
  {
    code: 'CU', name: 'Cuba', flag: '\u{1F1E8}\u{1F1FA}', tier: 3, score: 2, max: 10,
    pipelines: { census: 1, nbi: 0, broadband: 0, providers: 1, contracts: 0, health: 0, schools: 0, complaints: 0, quality: 0, peering: 0 },
  },
];

const GLOBAL_PIPELINES = [
  { key: 'opencelliD', label: 'OpenCelliD (Torres)', icon: Signal, countries: 19, total: 19 },
  { key: 'ookla', label: 'Ookla Speedtest', icon: Gauge, countries: 19, total: 19 },
  { key: 'osm', label: 'OpenStreetMap', icon: MapPin, countries: 19, total: 19 },
  { key: 'srtm', label: 'SRTM / Terreno', icon: Globe, countries: 19, total: 19 },
  { key: 'peeringdb', label: 'PeeringDB', icon: Radio, countries: 14, total: 19 },
  { key: 'quality', label: 'Qualidade de Rede', icon: Wifi, countries: 11, total: 19 },
  { key: 'providers', label: 'Provedores / Operadoras', icon: Building2, countries: 19, total: 19 },
];

const TIER_CONFIG = [
  { tier: 0, label: 'Referência', badge: 'Modelo Completo', color: '#059669', bg: '#ecfdf5', borderColor: '#a7f3d0' },
  { tier: 1, label: 'T1 — Paridade Total', badge: '10/10', color: '#059669', bg: '#ecfdf5', borderColor: '#a7f3d0' },
  { tier: 2, label: 'T2 — Quase Paridade', badge: '7-9/10', color: '#d97706', bg: '#fffbeb', borderColor: '#fde68a' },
  { tier: 3, label: 'T3 — Em Desenvolvimento', badge: '<7/10', color: '#6b7280', bg: '#f9fafb', borderColor: '#e5e7eb' },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function scoreColor(score: number, max: number): string {
  const ratio = score / max;
  if (ratio >= 0.8) return '#059669';
  if (ratio >= 0.5) return '#d97706';
  return '#ef4444';
}

function pipelineCoverage(): { type: string; covered: number; total: number }[] {
  return PIPELINE_TYPES.map((type) => {
    const covered = COUNTRIES.filter((c) => c.pipelines[type] === 1).length;
    return { type, covered, total: COUNTRIES.length };
  });
}

const DONUT_COLORS = [
  '#059669', '#0d9488', '#0f766e', '#14b8a6', '#10b981',
  '#d97706', '#f59e0b', '#84cc16', '#6366f1', '#8b5cf6',
];

// ─── Custom Tooltip ──────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-md border px-3 py-2 text-xs"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}
    >
      <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} style={{ color: entry.color }}>
          {entry.name}: {typeof entry.value === 'number' ? entry.value.toLocaleString('pt-BR') : entry.value}
        </p>
      ))}
    </div>
  );
}

// ─── KPI Card ────────────────────────────────────────────────────────────────

function KpiCard({ icon: Icon, value, label }: { icon: any; value: string; label: string }) {
  return (
    <div className="pulso-card p-5 flex items-center gap-4">
      <div
        className="h-12 w-12 rounded-lg flex items-center justify-center shrink-0"
        style={{ background: 'var(--accent)', color: '#fff' }}
      >
        <Icon size={22} />
      </div>
      <div>
        <div className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{value}</div>
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</div>
      </div>
    </div>
  );
}

// ─── Progress Bar ────────────────────────────────────────────────────────────

function ProgressBar({ value, max, color }: { value: number; max: number; color?: string }) {
  const pct = Math.round((value / max) * 100);
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-full" style={{ background: 'var(--bg-subtle)' }}>
        <div
          className="h-2 rounded-full transition-all"
          style={{ width: `${pct}%`, background: color || 'var(--accent)' }}
        />
      </div>
      <span className="text-xs font-medium tabular-nums w-12 text-right" style={{ color: 'var(--text-secondary)' }}>
        {value}/{max}
      </span>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function LatamPage() {
  const { data: dynamicStats, loading: statsLoading } = useApi<any>(
    () => api.latam.platformStats(),
    []
  );

  // Prepare bar chart data sorted by score descending
  const barData = [...COUNTRIES]
    .sort((a, b) => b.score - a.score)
    .map((c) => ({
      name: `${c.flag} ${c.code}`,
      score: c.score,
      fill: scoreColor(c.score, c.max),
    }));

  // Prepare donut data
  const donutData = pipelineCoverage().map((p) => ({
    name: PIPELINE_LABELS[p.type],
    value: p.covered,
  }));

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-base)' }}>
      <div className="mx-auto max-w-7xl px-4 py-6 space-y-8">

        {/* ── Seção 1: Hero ────────────────────────────────────────────────── */}
        <div>
          <div className="mb-6 flex items-center gap-3">
            <div
              className="h-10 w-10 rounded-lg flex items-center justify-center"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              <Globe size={20} />
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                Pulso LATAM — Inteligência de Telecomunicações
              </h1>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Inventário completo de pipelines, cobertura e métricas da plataforma
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiCard icon={Database} value="120" label="Pipelines de Dados" />
            <KpiCard icon={Code2} value="41.5K" label="Linhas de Código" />
            <KpiCard icon={Globe} value="19" label="Países Cobertos" />
            <KpiCard icon={Clock} value="25" label="Grupos Cron" />
          </div>
        </div>

        {/* ── Seção 2: Gráfico de Barras — Paridade por País ───────────────── */}
        <div className="pulso-card p-5">
          <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            <BarChart3 size={16} className="inline mr-2" style={{ verticalAlign: '-2px' }} />
            Paridade de Pipelines por País
          </h2>
          <ResponsiveContainer width="100%" height={460}>
            <BarChart data={barData} layout="vertical" margin={{ left: 60, right: 20, top: 5, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
              <XAxis
                type="number"
                domain={[0, 12]}
                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                axisLine={{ stroke: 'var(--border-strong)' }}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={55}
                tick={{ fill: 'var(--text-primary)', fontSize: 12 }}
                axisLine={{ stroke: 'var(--border-strong)' }}
              />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={18}>
                {barData.map((entry, idx) => (
                  <Cell key={idx} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* ── Seção 3: Matriz de Cobertura ────────────────────────────────── */}
        <div className="pulso-card p-5 overflow-x-auto">
          <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            Matriz de Cobertura — Países x Pipelines
          </h2>
          <table className="w-full text-xs border-collapse min-w-[700px]">
            <thead>
              <tr>
                <th className="text-left py-2 px-2 font-medium" style={{ color: 'var(--text-secondary)' }}>País</th>
                {PIPELINE_TYPES.map((t) => (
                  <th key={t} className="text-center py-2 px-1 font-medium" style={{ color: 'var(--text-secondary)' }}>
                    {PIPELINE_LABELS[t]}
                  </th>
                ))}
                <th className="text-center py-2 px-2 font-medium" style={{ color: 'var(--text-secondary)' }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {COUNTRIES.map((c) => {
                const total = Object.values(c.pipelines).reduce((a, b) => a + b, 0);
                return (
                  <tr key={c.code} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td className="py-1.5 px-2 font-medium whitespace-nowrap" style={{ color: 'var(--text-primary)' }}>
                      {c.flag} {c.name}
                    </td>
                    {PIPELINE_TYPES.map((t) => (
                      <td key={t} className="text-center py-1.5 px-1">
                        {c.pipelines[t] ? (
                          <span className="inline-block w-5 h-5 rounded text-[10px] font-bold leading-5"
                            style={{ background: '#ecfdf5', color: '#059669' }}>
                            ✓
                          </span>
                        ) : (
                          <span className="inline-block w-5 h-5 rounded text-[10px] leading-5"
                            style={{ background: 'var(--bg-subtle)', color: 'var(--text-muted)' }}>
                            —
                          </span>
                        )}
                      </td>
                    ))}
                    <td className="text-center py-1.5 px-2 font-bold" style={{ color: scoreColor(total, 10) }}>
                      {total}/{PIPELINE_TYPES.length}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr style={{ borderTop: '2px solid var(--border-strong)' }}>
                <td className="py-2 px-2 font-semibold" style={{ color: 'var(--text-primary)' }}>Cobertura</td>
                {PIPELINE_TYPES.map((t) => {
                  const covered = COUNTRIES.filter((c) => c.pipelines[t] === 1).length;
                  return (
                    <td key={t} className="text-center py-2 px-1 font-bold text-[11px]" style={{ color: scoreColor(covered, 19) }}>
                      {covered}/{COUNTRIES.length}
                    </td>
                  );
                })}
                <td />
              </tr>
            </tfoot>
          </table>
        </div>

        {/* ── Seção 4 + 5: Donut Chart + Global Pipelines ─────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          {/* Donut Chart */}
          <div className="pulso-card p-5">
            <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Cobertura por Tipo de Pipeline
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={donutData}
                  cx="50%"
                  cy="50%"
                  innerRadius={65}
                  outerRadius={110}
                  paddingAngle={3}
                  dataKey="value"
                  nameKey="name"
                  label={({ name, value }) => `${name}: ${value}`}
                  labelLine={{ stroke: 'var(--text-muted)' }}
                >
                  {donutData.map((_, i) => (
                    <Cell key={i} fill={DONUT_COLORS[i % DONUT_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: any, name: any) => [`${value}/19 países`, name]}
                  contentStyle={{
                    background: 'var(--bg-surface)',
                    borderColor: 'var(--border)',
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Global Pipelines */}
          <div className="pulso-card p-5">
            <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Pipelines Globais
            </h2>
            <div className="space-y-4">
              {GLOBAL_PIPELINES.map((gp) => {
                const pct = Math.round((gp.countries / gp.total) * 100);
                const color = pct === 100 ? '#059669' : pct >= 60 ? '#d97706' : '#ef4444';
                return (
                  <div key={gp.key}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <gp.icon size={14} style={{ color: 'var(--text-secondary)' }} />
                        <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                          {gp.label}
                        </span>
                      </div>
                      <span className="text-xs font-medium tabular-nums" style={{ color }}>
                        {pct}%
                      </span>
                    </div>
                    <ProgressBar value={gp.countries} max={gp.total} color={color} />
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* ── Seção 6: Tiers ──────────────────────────────────────────────── */}
        <div className="pulso-card p-5">
          <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            Classificação por Tier
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {TIER_CONFIG.map((tc) => {
              const tierCountries = COUNTRIES.filter((c) => c.tier === tc.tier);
              return (
                <div
                  key={tc.tier}
                  className="rounded-lg border p-4"
                  style={{ borderColor: tc.borderColor, background: tc.bg }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-semibold" style={{ color: tc.color }}>
                      {tc.label}
                    </span>
                    <span
                      className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                      style={{ background: tc.color, color: '#fff' }}
                    >
                      {tc.badge}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {tierCountries.map((c) => (
                      <span
                        key={c.code}
                        className="text-xs px-2 py-0.5 rounded border"
                        style={{ borderColor: tc.borderColor, color: tc.color }}
                      >
                        {c.flag} {c.code}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Seção 7: Métricas Dinâmicas do Banco ────────────────────────── */}
        <div className="pulso-card p-5">
          <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            <Database size={16} className="inline mr-2" style={{ verticalAlign: '-2px' }} />
            Métricas Dinâmicas do Banco de Dados
          </h2>

          {statsLoading ? (
            <div className="flex items-center justify-center py-12 gap-2" style={{ color: 'var(--text-muted)' }}>
              <Loader2 size={18} className="animate-spin" />
              <span className="text-sm">Carregando métricas...</span>
            </div>
          ) : dynamicStats ? (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {dynamicStats.tables?.map((t: { table: string; count: number; label: string }) => (
                <div
                  key={t.table}
                  className="rounded-lg border p-3"
                  style={{ borderColor: 'var(--border)', background: 'var(--bg-subtle)' }}
                >
                  <div className="text-lg font-bold tabular-nums" style={{ color: 'var(--accent)' }}>
                    {formatCompact(t.count)}
                  </div>
                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {t.label}
                  </div>
                </div>
              ))}

              {dynamicStats.by_country && dynamicStats.by_country.length > 0 && (
                <div className="col-span-full mt-4">
                  <h3 className="text-xs font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>
                    Municípios por País
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-2">
                    {dynamicStats.by_country.map((cc: { country_code: string; municipalities: number; providers: number }) => {
                      const country = COUNTRIES.find((c) => c.code === cc.country_code);
                      return (
                        <div
                          key={cc.country_code}
                          className="rounded border p-2 text-xs"
                          style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}
                        >
                          <div className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                            {country?.flag || ''} {cc.country_code}
                          </div>
                          <div style={{ color: 'var(--text-muted)' }}>
                            {formatNumber(cc.municipalities)} municípios
                          </div>
                          <div style={{ color: 'var(--text-muted)' }}>
                            {formatNumber(cc.providers)} provedores
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-sm" style={{ color: 'var(--text-muted)' }}>
              Sem dados disponíveis. Verifique a conexão com a API.
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
