'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { useApi, useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatCompact, formatPct } from '@/lib/format';
import {
  TrendingUp, BarChart3, Users, Activity, Clock, Search,
  Loader2, Wifi, Radio, Zap, Globe, Play, Pause, Briefcase, FileText,
} from 'lucide-react';

/* =================================================================
   Types
   ================================================================= */

interface NationalPoint {
  period: string;
  total_subscribers: number;
  active_providers: number;
  active_municipalities: number;
  fiber_pct: number;
  radio_pct: number;
  dsl_pct: number;
  cable_pct: number;
}

interface ProviderPoint {
  period: string;
  subscribers: number;
  municipalities: number;
  fiber_pct: number;
  national_share: number;
}

type Tab = 'nacional' | 'provedor' | 'municipio' | 'fibra' | 'emprego' | 'gazette';

const TABS: { key: Tab; label: string; icon: typeof TrendingUp }[] = [
  { key: 'nacional', label: 'Tendências Nacionais', icon: Globe },
  { key: 'provedor', label: 'Provedor', icon: Users },
  { key: 'municipio', label: 'Município', icon: BarChart3 },
  { key: 'fibra', label: 'Corrida da Fibra', icon: Zap },
  { key: 'emprego', label: 'Emprego', icon: Briefcase },
  { key: 'gazette', label: 'Diário Oficial', icon: FileText },
];

const MONTH_NAMES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

function formatPeriod(period: string): string {
  const [year, month] = period.split('-');
  return `${MONTH_NAMES[parseInt(month, 10) - 1]} ${year}`;
}

/* =================================================================
   Canvas Chart Component — reusable multi-line chart
   ================================================================= */

interface ChartLine {
  data: number[];
  color: string;
  label: string;
  dashed?: boolean;
}

function MultiLineChart({
  lines,
  xLabels,
  height = 280,
  yAxisFormat = 'number',
}: {
  lines: ChartLine[];
  xLabels: string[];
  height?: number;
  yAxisFormat?: 'number' | 'pct' | 'compact';
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || lines.length === 0 || lines[0].data.length < 2) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = rect.height;
    const padL = 70, padR = 20, padT = 20, padB = 40;
    const chartW = W - padL - padR;
    const chartH = H - padT - padB;
    const n = lines[0].data.length;

    ctx.clearRect(0, 0, W, H);

    // All values range
    let allMin = Infinity, allMax = -Infinity;
    for (const line of lines) {
      for (const v of line.data) {
        if (v < allMin) allMin = v;
        if (v > allMax) allMax = v;
      }
    }
    const range = allMax - allMin || 1;
    allMin -= range * 0.05;
    allMax += range * 0.02;

    const xAt = (i: number) => padL + (i / (n - 1)) * chartW;
    const yAt = (v: number) => padT + (1 - (v - allMin) / (allMax - allMin)) * chartH;

    // Grid
    ctx.strokeStyle = 'var(--border)';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = padT + (i / 4) * chartH;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(W - padR, y);
      ctx.stroke();
    }

    // Y-axis labels
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.fillStyle = 'var(--text-muted)';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const val = allMin + ((4 - i) / 4) * (allMax - allMin);
      let label: string;
      if (yAxisFormat === 'pct') label = val.toFixed(1) + '%';
      else if (yAxisFormat === 'compact') label = formatCompact(Math.round(val));
      else label = val >= 1_000_000 ? (val / 1_000_000).toFixed(1) + 'M' : (val / 1_000).toFixed(0) + 'K';
      ctx.fillText(label, padL - 8, padT + (i / 4) * chartH + 4);
    }

    // X-axis labels
    ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(n / 8));
    for (let i = 0; i < n; i++) {
      if (i % step === 0 || i === n - 1) {
        ctx.fillText(xLabels[i] || '', xAt(i), H - padB + 18);
      }
    }

    // Draw lines
    for (const line of lines) {
      ctx.strokeStyle = line.color;
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      if (line.dashed) ctx.setLineDash([4, 3]);
      else ctx.setLineDash([]);

      ctx.beginPath();
      for (let i = 0; i < line.data.length; i++) {
        const x = xAt(i);
        const y = yAt(line.data[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.setLineDash([]);

      // Endpoint dot
      const lastIdx = line.data.length - 1;
      ctx.beginPath();
      ctx.arc(xAt(lastIdx), yAt(line.data[lastIdx]), 3, 0, Math.PI * 2);
      ctx.fillStyle = line.color;
      ctx.fill();
    }
  }, [lines, xLabels, yAxisFormat]);

  return (
    <div>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: `${height}px`, display: 'block' }}
      />
      <div className="mt-2 flex flex-wrap gap-4 px-2">
        {lines.map((line) => (
          <span key={line.label} className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
            <span
              className="inline-block h-2 w-4"
              style={{ background: line.color, borderRadius: 1, opacity: line.dashed ? 0.6 : 1 }}
            />
            {line.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/* =================================================================
   Stat Card
   ================================================================= */

function StatCard({
  label, value, sub, icon, color,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ReactNode;
  color?: string;
}) {
  return (
    <div className="p-4" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
      <div className="flex items-center gap-1.5 mb-2" style={{ color: 'var(--text-muted)' }}>
        {icon}
        <span className="text-[10px] uppercase tracking-wider">{label}</span>
      </div>
      <div className="font-mono text-xl font-bold tabular-nums" style={{ color: color || 'var(--accent)' }}>
        {value}
      </div>
      {sub && (
        <div className="mt-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>{sub}</div>
      )}
    </div>
  );
}

/* =================================================================
   National Trends Tab
   ================================================================= */

function NacionalTab() {
  const { data, loading, error } = useApi<{ series: NationalPoint[] }>(
    () => api.timeseries.national(), []
  );

  if (loading) return <LoadingState />;
  if (error || !data?.series?.length) return <ErrorState message={error || 'Sem dados'} />;

  const series = data.series;
  const first = series[0];
  const last = series[series.length - 1];
  const xLabels = series.map(s => {
    const p = s.period;
    return p.substring(5) + '/' + p.substring(2, 4);
  });

  const growthPct = ((last.total_subscribers - first.total_subscribers) / first.total_subscribers * 100).toFixed(1);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-0">
        <StatCard
          label="Assinantes totais"
          value={formatCompact(last.total_subscribers)}
          sub={`${+growthPct > 0 ? '+' : ''}${growthPct}% em ${series.length} meses`}
          icon={<Users size={14} />}
          color={+growthPct >= 0 ? 'var(--success)' : 'var(--danger)'}
        />
        <StatCard
          label="Provedores ativos"
          value={last.active_providers.toLocaleString('pt-BR')}
          sub={`${first.active_providers.toLocaleString('pt-BR')} em ${formatPeriod(first.period)}`}
          icon={<Activity size={14} />}
        />
        <StatCard
          label="Fibra óptica"
          value={formatPct(last.fiber_pct)}
          sub={`Era ${formatPct(first.fiber_pct)} em ${formatPeriod(first.period)}`}
          icon={<Zap size={14} />}
          color="var(--success)"
        />
        <StatCard
          label="Municipios ativos"
          value={last.active_municipalities.toLocaleString('pt-BR')}
          icon={<BarChart3 size={14} />}
        />
      </div>

      {/* Subscriber growth chart */}
      <ChartCard title="Evolucao de assinantes" subtitle={`${series.length} meses`}>
        <MultiLineChart
          lines={[
            { data: series.map(s => s.total_subscribers), color: '#6366f1', label: 'Total assinantes' },
          ]}
          xLabels={xLabels}
          yAxisFormat="compact"
        />
      </ChartCard>

      {/* Technology mix chart */}
      <ChartCard title="Mix tecnologico" subtitle="% da base por tecnologia">
        <MultiLineChart
          lines={[
            { data: series.map(s => s.fiber_pct), color: '#22c55e', label: 'Fibra' },
            { data: series.map(s => s.radio_pct), color: '#f59e0b', label: 'Radio', dashed: true },
            { data: series.map(s => s.cable_pct), color: '#0ea5e9', label: 'Coaxial/HFC', dashed: true },
            { data: series.map(s => s.dsl_pct), color: '#ef4444', label: 'DSL', dashed: true },
          ]}
          xLabels={xLabels}
          yAxisFormat="pct"
        />
      </ChartCard>
    </div>
  );
}

/* =================================================================
   Provider Tab
   ================================================================= */

function ProvedorTab() {
  const [searchQuery, setSearchQuery] = useState('');
  const [providerId, setProviderId] = useState<number | null>(null);
  const [providerName, setProviderName] = useState('');

  const { data: provData, loading: provLoading, execute: fetchProvider } = useLazyApi(
    useCallback((pid: number) => api.timeseries.provider(pid), [])
  );

  // Search providers via public API
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'https://api.pulso.network'}/api/v1/public/raio-x?q=${encodeURIComponent(searchQuery)}`
      );
      const json = await res.json();
      if (json.provider) {
        setProviderId(json.provider.id);
        setProviderName(json.provider.name);
        fetchProvider(json.provider.id);
      } else if (json.matches?.length) {
        // Take the first match
        setProviderId(json.matches[0].id);
        setProviderName(json.matches[0].name);
        fetchProvider(json.matches[0].id);
      }
    } catch { /* silent */ }
  };

  const series: ProviderPoint[] = provData?.series || [];
  const xLabels = series.map(s => {
    const p = s.period;
    return p.substring(5) + '/' + p.substring(2, 4);
  });

  return (
    <div className="space-y-6">
      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Buscar provedor..."
            className="w-full pl-9 pr-4 py-2 text-sm"
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
            }}
          />
        </div>
        <button
          onClick={handleSearch}
          className="px-4 py-2 text-sm font-semibold"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          Buscar
        </button>
      </div>

      {provLoading && <LoadingState />}

      {series.length > 0 && (
        <>
          <div className="flex items-center gap-3 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
            <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{providerName}</h3>
            <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
              {series.length} periodos
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-0">
            <StatCard
              label="Assinantes atuais"
              value={formatCompact(series[series.length - 1].subscribers)}
              sub={`${formatCompact(series[0].subscribers)} em ${formatPeriod(series[0].period)}`}
              icon={<Users size={14} />}
            />
            <StatCard
              label="Market share"
              value={`${series[series.length - 1].national_share}%`}
              icon={<TrendingUp size={14} />}
            />
            <StatCard
              label="Fibra"
              value={formatPct(series[series.length - 1].fiber_pct)}
              sub={`Era ${formatPct(series[0].fiber_pct)}`}
              icon={<Zap size={14} />}
              color="var(--success)"
            />
            <StatCard
              label="Municipios"
              value={series[series.length - 1].municipalities.toLocaleString('pt-BR')}
              icon={<BarChart3 size={14} />}
            />
          </div>

          <ChartCard title="Crescimento de assinantes" subtitle={providerName}>
            <MultiLineChart
              lines={[
                { data: series.map(s => s.subscribers), color: '#6366f1', label: 'Assinantes' },
              ]}
              xLabels={xLabels}
              yAxisFormat="compact"
            />
          </ChartCard>

          <ChartCard title="Fibra % e market share" subtitle="Evolucao ao longo do tempo">
            <MultiLineChart
              lines={[
                { data: series.map(s => s.fiber_pct), color: '#22c55e', label: '% Fibra' },
                { data: series.map(s => s.national_share), color: '#6366f1', label: 'Market share %', dashed: true },
              ]}
              xLabels={xLabels}
              yAxisFormat="pct"
            />
          </ChartCard>
        </>
      )}

      {!provLoading && series.length === 0 && !providerId && (
        <div className="text-center py-16">
          <Search size={32} className="mx-auto mb-4" style={{ color: 'var(--text-muted)' }} />
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Busque um provedor para ver sua evolucao historica
          </p>
        </div>
      )}
    </div>
  );
}

/* =================================================================
   Municipality Tab
   ================================================================= */

function MunicipioTab() {
  const [muniId, setMuniId] = useState<number | null>(null);
  const [muniName, setMuniName] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: tsData, loading: tsLoading, execute: fetchTs } = useLazyApi(
    useCallback((params: { municipality_id: number }) => api.timeseries.subscribers(params), [])
  );

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'https://api.pulso.network'}/api/v1/municipalities/search?q=${encodeURIComponent(searchQuery)}`
      );
      const json = await res.json();
      if (json.length > 0) {
        setMuniId(json[0].id);
        setMuniName(`${json[0].name}, ${json[0].state}`);
        fetchTs({ municipality_id: json[0].id });
      }
    } catch { /* silent */ }
  };

  const series = tsData?.series || [];
  const xLabels = series.map((s: any) => {
    const p = s.period;
    return p.substring(5) + '/' + p.substring(2, 4);
  });

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Buscar municipio..."
            className="w-full pl-9 pr-4 py-2 text-sm"
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
            }}
          />
        </div>
        <button
          onClick={handleSearch}
          className="px-4 py-2 text-sm font-semibold"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          Buscar
        </button>
      </div>

      {tsLoading && <LoadingState />}

      {series.length > 0 && (
        <>
          <div className="flex items-center gap-3 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
            <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{muniName}</h3>
            <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
              {series.length} periodos
            </span>
          </div>

          <ChartCard title="Assinantes totais" subtitle={muniName}>
            <MultiLineChart
              lines={[
                { data: series.map((s: any) => s.total_subscribers || 0), color: '#6366f1', label: 'Total' },
                { data: series.map((s: any) => s.fiber_subscribers || 0), color: '#22c55e', label: 'Fibra' },
              ]}
              xLabels={xLabels}
              yAxisFormat="compact"
            />
          </ChartCard>

          <ChartCard title="Provedores e tecnologias" subtitle="Evolucao da competicao">
            <MultiLineChart
              lines={[
                { data: series.map((s: any) => s.provider_count || 0), color: '#f59e0b', label: 'Provedores' },
                { data: series.map((s: any) => s.tech_count || 0), color: '#0ea5e9', label: 'Tecnologias', dashed: true },
              ]}
              xLabels={xLabels}
              yAxisFormat="number"
              height={220}
            />
          </ChartCard>
        </>
      )}

      {!tsLoading && series.length === 0 && !muniId && (
        <div className="text-center py-16">
          <Search size={32} className="mx-auto mb-4" style={{ color: 'var(--text-muted)' }} />
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Busque um municipio para ver sua evolucao historica
          </p>
        </div>
      )}
    </div>
  );
}

/* =================================================================
   Fiber Race Tab
   ================================================================= */

function FibraTab() {
  const { data, loading, error } = useApi<{ states: number; data: Record<string, { period: string; fiber_pct: number; total_subs: number }[]> }>(
    () => api.timeseries.fiberRace(), []
  );

  if (loading) return <LoadingState />;
  if (error || !data?.data) return <ErrorState message={error || 'Sem dados'} />;

  // Find states with most subscribers (top 10)
  const stateEntries = Object.entries(data.data);
  const stateLatest = stateEntries.map(([state, history]) => ({
    state,
    fiberPct: history[history.length - 1]?.fiber_pct || 0,
    subs: history[history.length - 1]?.total_subs || 0,
    firstFiber: history[0]?.fiber_pct || 0,
    history,
  }));
  stateLatest.sort((a, b) => b.subs - a.subs);

  const top10 = stateLatest.slice(0, 10);
  const COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#0ea5e9', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#64748b'];

  const xLabels = top10[0]?.history.map(h => {
    const p = h.period;
    return p.substring(5) + '/' + p.substring(2, 4);
  }) || [];

  return (
    <div className="space-y-6">
      {/* Leader board */}
      <div style={{ border: '1px solid var(--border)' }}>
        <div className="p-4 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
          <Zap size={16} style={{ color: 'var(--accent)' }} />
          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Ranking de fibra por estado (top 10 por assinantes)
          </h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-0">
          {top10.map((s, i) => (
            <div key={s.state} className="p-3" style={{ borderRight: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
              <div className="flex items-center gap-2 mb-1">
                <span className="inline-block h-2.5 w-2.5" style={{ background: COLORS[i], borderRadius: '50%' }} />
                <span className="font-mono text-xs font-bold" style={{ color: 'var(--text-primary)' }}>{s.state}</span>
              </div>
              <div className="font-mono text-lg font-bold" style={{ color: COLORS[i] }}>
                {s.fiberPct.toFixed(1)}%
              </div>
              <div className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                {s.firstFiber.toFixed(1)}% → {s.fiberPct.toFixed(1)}%
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Fiber race chart */}
      <ChartCard title="Corrida da fibra" subtitle="% de assinantes em fibra por estado">
        <MultiLineChart
          lines={top10.map((s, i) => ({
            data: s.history.map(h => h.fiber_pct),
            color: COLORS[i],
            label: s.state,
          }))}
          xLabels={xLabels}
          yAxisFormat="pct"
          height={360}
        />
      </ChartCard>
    </div>
  );
}

/* =================================================================
   Employment Tab
   ================================================================= */

function EmpregoTab() {
  const [muniId, setMuniId] = useState<number | null>(null);
  const [muniName, setMuniName] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: empData, loading: empLoading, execute: fetchEmp } = useLazyApi(
    useCallback((params: { municipality_id: number }) => api.timeseries.employment(params), [])
  );

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'https://api.pulso.network'}/api/v1/municipalities/search?q=${encodeURIComponent(searchQuery)}`
      );
      const json = await res.json();
      if (json.length > 0) {
        setMuniId(json[0].id);
        setMuniName(`${json[0].name}, ${json[0].state}`);
        fetchEmp({ municipality_id: json[0].id });
      }
    } catch { /* silent */ }
  };

  const series = empData?.series || [];
  const xLabels = series.map((s: any) => {
    const p = s.period;
    return p.substring(5) + '/' + p.substring(2, 4);
  });

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Buscar municipio..."
            className="w-full pl-9 pr-4 py-2 text-sm"
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
            }}
          />
        </div>
        <button
          onClick={handleSearch}
          className="px-4 py-2 text-sm font-semibold"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          Buscar
        </button>
      </div>

      {empLoading && <LoadingState />}

      {series.length > 0 && (
        <>
          <div className="flex items-center gap-3 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
            <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{muniName}</h3>
            <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
              {series.length} periodos
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-0">
            <StatCard
              label="Empregos telecom"
              value={formatCompact(series[series.length - 1].formal_jobs_telecom)}
              sub={`${formatCompact(series[0].formal_jobs_telecom)} no inicio`}
              icon={<Briefcase size={14} />}
            />
            <StatCard
              label="Salario medio"
              value={series[series.length - 1].avg_salary_brl
                ? `R$ ${Math.round(series[series.length - 1].avg_salary_brl).toLocaleString('pt-BR')}`
                : 'N/D'}
              icon={<Activity size={14} />}
              color="var(--success)"
            />
            <StatCard
              label="Empregos servicos"
              value={formatCompact(series[series.length - 1].formal_jobs_services)}
              icon={<Users size={14} />}
            />
            <StatCard
              label="Saldo contratacoes"
              value={series[series.length - 1].net_hires.toLocaleString('pt-BR')}
              icon={<TrendingUp size={14} />}
              color={series[series.length - 1].net_hires >= 0 ? 'var(--success)' : 'var(--danger)'}
            />
          </div>

          <ChartCard title="Empregos em telecom" subtitle={muniName}>
            <MultiLineChart
              lines={[
                { data: series.map((s: any) => s.formal_jobs_telecom || 0), color: '#6366f1', label: 'Telecom' },
                { data: series.map((s: any) => s.formal_jobs_services || 0), color: '#22c55e', label: 'Servicos', dashed: true },
              ]}
              xLabels={xLabels}
              yAxisFormat="compact"
            />
          </ChartCard>

          {series[0].avg_salary_brl && (
            <ChartCard title="Salario medio mensal (R$)" subtitle="Evolucao ao longo do tempo">
              <MultiLineChart
                lines={[
                  { data: series.map((s: any) => s.avg_salary_brl || 0), color: '#f59e0b', label: 'Salario medio R$' },
                ]}
                xLabels={xLabels}
                yAxisFormat="compact"
              />
            </ChartCard>
          )}
        </>
      )}

      {!empLoading && series.length === 0 && !muniId && (
        <div className="text-center py-16">
          <Briefcase size={32} className="mx-auto mb-4" style={{ color: 'var(--text-muted)' }} />
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Busque um municipio para ver indicadores de emprego (2021-2025)
          </p>
          <p className="mt-1 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
            11.141 registros de indicadores de emprego formal
          </p>
        </div>
      )}
    </div>
  );
}

/* =================================================================
   Gazette Tab
   ================================================================= */

function GazetteTab() {
  const [searchQuery, setSearchQuery] = useState('');
  const [muniId, setMuniId] = useState<number | null>(null);
  const [muniName, setMuniName] = useState('');
  const [typeFilter, setTypeFilter] = useState<string | null>(null);

  const { data: gazData, loading: gazLoading, execute: fetchGaz } = useLazyApi(
    useCallback((params: any) => api.timeseries.gazette(params), [])
  );

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    // Try municipality search first
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'https://api.pulso.network'}/api/v1/municipalities/search?q=${encodeURIComponent(searchQuery)}`
      );
      const json = await res.json();
      if (json.length > 0) {
        setMuniId(json[0].id);
        setMuniName(`${json[0].name}, ${json[0].state}`);
        fetchGaz({ municipality_id: json[0].id, limit: 50 });
        return;
      }
    } catch { /* fallthrough */ }
    // Fallback: text search
    fetchGaz({ q: searchQuery, limit: 50 });
  };

  const handleTypeFilter = (type: string | null) => {
    setTypeFilter(type);
    const params: any = { limit: 50 };
    if (muniId) params.municipality_id = muniId;
    if (type) params.mention_type = type;
    fetchGaz(params);
  };

  const results = gazData?.results || [];
  const types = gazData?.mention_types || {};
  const total = gazData?.total || 0;

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Buscar municipio ou palavra-chave (fibra, licitacao...)"
            className="w-full pl-9 pr-4 py-2 text-sm"
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
            }}
          />
        </div>
        <button
          onClick={handleSearch}
          className="px-4 py-2 text-sm font-semibold"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          Buscar
        </button>
      </div>

      {gazLoading && <LoadingState />}

      {results.length > 0 && (
        <>
          <div className="flex items-center gap-3 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
            <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
              {muniName || 'Resultados da busca'}
            </h3>
            <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
              {total.toLocaleString('pt-BR')} mencoes
            </span>
          </div>

          {/* Type filters */}
          {Object.keys(types).length > 0 && (
            <div className="flex flex-wrap gap-1">
              <button
                onClick={() => handleTypeFilter(null)}
                className="px-3 py-1 text-xs font-semibold"
                style={{
                  background: typeFilter === null ? 'var(--accent)' : 'var(--bg-surface)',
                  color: typeFilter === null ? '#fff' : 'var(--text-muted)',
                  border: '1px solid var(--border)',
                }}
              >
                Todos ({total})
              </button>
              {Object.entries(types).slice(0, 8).map(([type, count]) => (
                <button
                  key={type}
                  onClick={() => handleTypeFilter(type)}
                  className="px-3 py-1 text-xs font-semibold capitalize"
                  style={{
                    background: typeFilter === type ? 'var(--accent)' : 'var(--bg-surface)',
                    color: typeFilter === type ? '#fff' : 'var(--text-muted)',
                    border: '1px solid var(--border)',
                  }}
                >
                  {type.replace('_', ' ')} ({count as number})
                </button>
              ))}
            </div>
          )}

          {/* Results timeline */}
          <div style={{ border: '1px solid var(--border)' }}>
            {results.map((item: any, i: number) => (
              <div
                key={item.id || i}
                className="p-4"
                style={{
                  borderBottom: '1px solid var(--border)',
                  background: i % 2 === 0 ? 'var(--bg-surface)' : 'transparent',
                }}
              >
                <div className="flex items-center gap-3 mb-2">
                  <span className="font-mono text-xs" style={{ color: 'var(--accent)' }}>
                    {item.published_date || '—'}
                  </span>
                  <span
                    className="px-2 py-0.5 text-[10px] uppercase tracking-wider font-semibold capitalize"
                    style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--accent)', border: '1px solid rgba(99,102,241,0.2)' }}
                  >
                    {(item.mention_type || '').replace('_', ' ')}
                  </span>
                  {item.municipality && (
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {item.municipality}, {item.state}
                    </span>
                  )}
                </div>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  {item.excerpt}
                </p>
                {item.keywords?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {item.keywords.slice(0, 5).map((kw: string) => (
                      <span key={kw} className="font-mono text-[10px] px-1.5 py-0.5" style={{ background: 'var(--bg-subtle)', color: 'var(--text-muted)' }}>
                        {kw}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {!gazLoading && results.length === 0 && (
        <div className="text-center py-16">
          <FileText size={32} className="mx-auto mb-4" style={{ color: 'var(--text-muted)' }} />
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Busque um municipio ou palavra-chave para explorar o Diario Oficial
          </p>
          <p className="mt-1 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
            60.581 mencoes de 1961 a 2026 — 64 anos de dados
          </p>
        </div>
      )}
    </div>
  );
}

/* =================================================================
   Shared Components
   ================================================================= */

function ChartCard({ title, subtitle, children }: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
      <div className="p-4 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{title}</h3>
        {subtitle && (
          <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>{subtitle}</span>
        )}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-20">
      <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent)' }} />
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="text-center py-16">
      <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{message}</p>
    </div>
  );
}

/* =================================================================
   Main Page
   ================================================================= */

export default function HistoricoPage() {
  const [tab, setTab] = useState<Tab>('nacional');

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
      {/* Header */}
      <div className="px-6 pt-6 pb-4" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-3 mb-1">
          <Clock size={20} style={{ color: 'var(--accent)' }} />
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Historico
          </h1>
          <span
            className="px-2 py-0.5 font-mono text-[10px] font-semibold uppercase"
            style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--accent)', border: '1px solid rgba(99,102,241,0.2)' }}
          >
            37 meses
          </span>
        </div>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Serie historica de Jan 2023 a Jan 2026. 4,3M registros de assinantes, evolucao de mercado e tendencias.
        </p>
      </div>

      {/* Tabs */}
      <div className="px-6 py-3 flex gap-1 overflow-x-auto" style={{ borderBottom: '1px solid var(--border)' }}>
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold whitespace-nowrap transition-all"
              style={{
                background: active ? 'var(--accent)' : 'transparent',
                color: active ? '#fff' : 'var(--text-muted)',
                border: active ? '1px solid var(--accent)' : '1px solid var(--border)',
              }}
            >
              <Icon size={14} />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div className="px-6 py-6 max-w-6xl">
        {tab === 'nacional' && <NacionalTab />}
        {tab === 'provedor' && <ProvedorTab />}
        {tab === 'municipio' && <MunicipioTab />}
        {tab === 'fibra' && <FibraTab />}
        {tab === 'emprego' && <EmpregoTab />}
        {tab === 'gazette' && <GazetteTab />}
      </div>
    </div>
  );
}
