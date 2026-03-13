'use client';

import { useState, useCallback, useRef, useEffect, FormEvent } from 'react';
import Link from 'next/link';
import Section from '@/components/ui/Section';
import {
  Search, TrendingUp, TrendingDown, Shield, MapPin, BarChart3,
  Users, AlertTriangle, ArrowRight, Zap, Loader2, X, Activity,
  Award, Briefcase, FileText, Scale, Radio, DollarSign, Lock,
} from 'lucide-react';
import PaywallCTA from '@/components/ui/PaywallCTA';

/* ═══════════════════════════════════════════════════════════════
   Types — matches actual API response from /api/v1/public/raio-x
   ═══════════════════════════════════════════════════════════════ */

interface Municipality {
  municipality: string;
  uf: string;
  subscribers: number;
  share_pct: number;
  hhi: number;
  total_market: number;
}

interface EntityInfo {
  id: number;
  name: string;
}

interface ProviderResult {
  provider_id: number;
  name: string;
  pulso_score: number | null;
  pulso_tier: string | null;
  total_subscribers: number;
  growth_pct: number | null;
  fiber_pct: number | null;
  municipality_count: number;
  municipalities: Municipality[];
  is_group?: boolean;
  entities?: EntityInfo[];
  entity_count?: number;
}

interface HistoryPoint {
  period: string;
  subscribers: number;
  fiber_pct: number;
}

interface MuniHistory {
  municipality: string;
  state: string;
  history: { period: string; subscribers: number; share_pct: number }[];
}

interface HistoricoData {
  provider_id: number;
  name: string;
  history: HistoryPoint[];
  municipality_histories: MuniHistory[];
}

interface PositionData {
  provider_id: number;
  national_rank: number | null;
  national_share_pct: number | null;
  total_subscribers: number;
  municipalities: number;
  states: number;
  fiber_pct: number;
  radio_pct: number;
  growth_12m_pct: number | null;
  employment: {
    total_employees: number;
    avg_salary_brl: number | null;
    years_available: number;
  } | null;
}

interface IntelData {
  provider_id: number;
  gazette: { total_mentions: number; by_type: Record<string, number>; latest_date: string | null; locked: boolean };
  regulatory: { relevant_acts: number; latest_act_title: string | null; locked: boolean };
  bndes: { loans_count: number; total_value_brl: number; locked: boolean };
  spectrum: { licenses_count: number; locked: boolean };
  competition: { national_rank: number | null; national_share_pct: number | null; top_5_markets_locked: boolean };
}

interface QualityData {
  provider_id: number;
  seal_summary: Record<string, number>;
  total_evaluated: number;
  by_period: Record<string, { seal_level: string; avg_overall: number; municipality_count: number }[]>;
}

interface DynamicsData {
  provider_id: number;
  periods: { period: string; total_subscribers: number; municipalities: number; avg_market_share: number; markets_as_leader: number }[];
  summary: { subscriber_growth_pct: number; municipality_change: number; total_periods: number };
}

interface ContractsData {
  provider_id: number;
  total_contracts: number;
  total_value_brl: number;
  earliest_date: string | null;
  latest_date: string | null;
  by_sphere: { sphere: string; count: number; total_brl: number }[];
  locked: boolean;
}

// API returns different shapes for single/multiple/error
interface MatchItem {
  id: number;
  name: string;
}

type State =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'matches'; items: MatchItem[] }
  | { kind: 'result'; provider: ProviderResult };

/* ═══════════════════════════════════════════════════════════════
   Helpers
   ═══════════════════════════════════════════════════════════════ */

const API_URL = 'https://api.pulso.network/api/v1/public/raio-x';
const API_HIST_URL = 'https://api.pulso.network/api/v1/public/raio-x/historico';
const API_POS_URL = 'https://api.pulso.network/api/v1/public/raio-x/posicao';
const API_INTEL_URL = 'https://api.pulso.network/api/v1/public/raio-x/intel';
const API_QUAL_URL = 'https://api.pulso.network/api/v1/public/raio-x/qualidade';
const API_DYN_URL = 'https://api.pulso.network/api/v1/public/raio-x/dinamica';
const API_CONTR_URL = 'https://api.pulso.network/api/v1/public/raio-x/contratos';

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace('.', ',') + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace('.', ',') + 'K';
  return n.toLocaleString('pt-BR');
}

function tierColor(tier: string | null): string {
  switch (tier) {
    case 'S': return '#6366f1';
    case 'A': return '#059669';
    case 'B': return '#0ea5e9';
    case 'C': return '#d97706';
    case 'D': return '#dc2626';
    default: return '#78716c';
  }
}

function scoreBarColor(score: number): string {
  if (score >= 80) return '#6366f1';
  if (score >= 60) return '#059669';
  if (score >= 40) return '#0ea5e9';
  if (score >= 20) return '#d97706';
  return '#dc2626';
}

function hhiColor(hhi: number): string {
  if (hhi < 1500) return 'var(--success)';
  if (hhi <= 2500) return 'var(--warning)';
  return 'var(--danger)';
}

function hhiLabel(hhi: number): string {
  if (hhi < 1500) return 'Competitivo';
  if (hhi <= 2500) return 'Moderado';
  return 'Concentrado';
}

/* ═══════════════════════════════════════════════════════════════
   Component
   ═══════════════════════════════════════════════════════════════ */

export default function RaioXPage() {
  const [query, setQuery] = useState('');
  const [state, setState] = useState<State>({ kind: 'idle' });
  const [historico, setHistorico] = useState<HistoricoData | null>(null);
  const [position, setPosition] = useState<PositionData | null>(null);
  const [intel, setIntel] = useState<IntelData | null>(null);
  const [quality, setQuality] = useState<QualityData | null>(null);
  const [dynamics, setDynamics] = useState<DynamicsData | null>(null);
  const [contracts, setContracts] = useState<ContractsData | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const scrollToResults = () => {
    setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  };

  // Fetch historical data when we get a provider result
  const fetchHistorico = useCallback(async (providerId: number) => {
    try {
      const res = await fetch(`${API_HIST_URL}?provider_id=${providerId}`);
      if (!res.ok) return;
      const json: HistoricoData = await res.json();
      setHistorico(json);
    } catch {
      // Silent fail — historical chart is enhancement, not critical
    }
  }, []);

  // Fetch competitive position + intel + quality + dynamics + contracts
  const fetchExtras = useCallback(async (providerId: number) => {
    try {
      const [posRes, intelRes, qualRes, dynRes, contrRes] = await Promise.all([
        fetch(`${API_POS_URL}?provider_id=${providerId}`),
        fetch(`${API_INTEL_URL}?provider_id=${providerId}`),
        fetch(`${API_QUAL_URL}?provider_id=${providerId}`),
        fetch(`${API_DYN_URL}?provider_id=${providerId}`),
        fetch(`${API_CONTR_URL}?provider_id=${providerId}`),
      ]);
      if (posRes.ok) setPosition(await posRes.json());
      if (intelRes.ok) setIntel(await intelRes.json());
      if (qualRes.ok) setQuality(await qualRes.json());
      if (dynRes.ok) setDynamics(await dynRes.json());
      if (contrRes.ok) setContracts(await contrRes.json());
    } catch {
      // Silent fail — extra data is enhancement
    }
  }, []);

  // Normalize API response into our State type
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const parseResponse = (json: any): State => {
    // Error response: { error: "...", query: "..." }
    if (json.error) {
      return { kind: 'error', message: json.error };
    }
    // Multiple matches: { matches: [...], message: "..." }
    if (json.matches) {
      return { kind: 'matches', items: json.matches };
    }
    // Single match: { provider: {...}, municipalities: [...], insights: {...} }
    if (json.provider) {
      const p = json.provider;
      const munis = (json.municipalities || []).map((m: any) => ({
        municipality: m.name,
        uf: m.state,
        subscribers: m.subscribers,
        share_pct: m.market_share_pct,
        hhi: m.hhi,
        total_market: m.total_market_subs,
      }));
      return {
        kind: 'result',
        provider: {
          provider_id: p.id,
          name: p.name,
          pulso_score: p.pulso_score ?? null,
          pulso_tier: p.pulso_tier ?? null,
          total_subscribers: p.total_subscribers,
          growth_pct: p.growth_pct ?? null,
          fiber_pct: p.fiber_pct ?? null,
          municipality_count: json.insights?.total_municipalities ?? munis.length,
          municipalities: munis,
          is_group: p.is_group ?? false,
          entities: p.entities ?? undefined,
          entity_count: p.entity_count ?? undefined,
        },
      };
    }
    return { kind: 'error', message: 'Resposta inesperada do servidor.' };
  };

  const doSearch = useCallback(async (searchTerm: string) => {
    if (!searchTerm.trim()) return;
    setState({ kind: 'loading' });
    setHistorico(null);
    setPosition(null);
    setIntel(null);
    setQuality(null);
    setDynamics(null);
    setContracts(null);

    try {
      const res = await fetch(`${API_URL}?q=${encodeURIComponent(searchTerm.trim())}`);
      if (!res.ok) throw new Error('Erro ao buscar dados');
      const json = await res.json();
      const newState = parseResponse(json);
      setState(newState);
      scrollToResults();

      // Fetch historical + extras if we got a single result
      if (newState.kind === 'result') {
        fetchHistorico(newState.provider.provider_id);
        fetchExtras(newState.provider.provider_id);
      }
    } catch {
      setState({ kind: 'error', message: 'Erro de conexao. Verifique sua internet e tente novamente.' });
    }
  }, [fetchHistorico, fetchExtras]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    doSearch(query);
  };

  // When user picks from disambiguation, re-search with exact name
  const handleSelectMatch = (item: MatchItem) => {
    setQuery(item.name);
    doSearch(item.name);
  };

  const handleClear = () => {
    setQuery('');
    setState({ kind: 'idle' });
  };

  // Derived
  const selectedProvider = state.kind === 'result' ? state.provider : null;
  const insights = selectedProvider ? computeInsights(selectedProvider) : null;

  return (
    <>
      {/* ───── Hero ───── */}
      <section
        className="relative overflow-hidden -mt-14 grain"
        style={{ background: 'var(--bg-dark)', minHeight: '60vh' }}
      >
        <div className="relative z-10 mx-auto max-w-6xl px-4 pt-32 pb-16 md:pt-40 md:pb-20">
          {/* Tag */}
          <div
            className="mb-6 inline-flex items-center gap-2 font-mono text-xs tracking-wider uppercase"
            style={{ color: 'var(--accent-hover)' }}
          >
            <span className="inline-block h-px w-8" style={{ background: 'var(--accent)' }} />
            Ferramenta gratuita
          </div>

          {/* Headline */}
          <h1
            className="font-serif text-4xl font-bold tracking-tight md:text-5xl lg:text-6xl max-w-3xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.05 }}
          >
            Raio-X do Provedor
          </h1>

          <p
            className="mt-5 max-w-xl text-base leading-relaxed md:text-lg"
            style={{ color: 'var(--text-on-dark-secondary)' }}
          >
            Descubra a posicao competitiva do seu provedor em segundos.
            Pulso Score, market share, municipios atendidos e ameaca Starlink — de graca.
          </p>

          {/* Search form */}
          <form onSubmit={handleSubmit} className="mt-10 max-w-2xl">
            <div className="flex gap-0">
              <div className="relative flex-1">
                <Search
                  size={16}
                  className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: 'var(--text-on-dark-muted)' }}
                />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Digite o nome do provedor..."
                  className="pulso-input-dark pl-10 pr-10"
                  style={{ height: '48px', fontSize: '15px' }}
                />
                {query && (
                  <button
                    type="button"
                    onClick={handleClear}
                    className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors"
                    style={{ color: 'var(--text-on-dark-muted)' }}
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
              <button
                type="submit"
                disabled={state.kind === 'loading' || !query.trim()}
                className="pulso-btn-primary flex items-center gap-2 px-8 disabled:opacity-50"
                style={{ height: '48px' }}
              >
                {state.kind === 'loading' ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Zap size={16} />
                )}
                <span className="hidden sm:inline">Analisar</span>
              </button>
            </div>
            <p className="mt-3 font-mono text-xs" style={{ color: 'var(--text-on-dark-muted)' }}>
              Ex: Claro, Vivo, Brisanet, Desktop, Algar, Unifique...
            </p>
          </form>

          {/* Social proof strip */}
          <div
            className="mt-10 flex flex-wrap items-center gap-4 font-mono text-xs"
            style={{ color: 'var(--text-on-dark-muted)' }}
          >
            <span className="flex items-center gap-2">
              <span className="inline-block h-2 w-2" style={{ background: 'var(--success)', borderRadius: '50%' }} />
              13.534 provedores indexados
            </span>
            <span style={{ color: 'var(--border-dark-strong)' }}>|</span>
            <span>Dados Anatel dez/2024</span>
            <span style={{ color: 'var(--border-dark-strong)' }}>|</span>
            <span>100% gratuito</span>
          </div>
        </div>
      </section>

      {/* ───── Results ───── */}
      <div ref={resultsRef}>
        {/* Error state */}
        {state.kind === 'error' && (
          <Section background="primary">
            <div
              className="mx-auto max-w-xl text-center p-8"
              style={{ border: '1px solid var(--border)' }}
            >
              <AlertTriangle size={32} className="mx-auto mb-4" style={{ color: 'var(--warning)' }} />
              <p className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                {state.message}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                Verifique a grafia ou tente um nome parcial.
              </p>
            </div>
          </Section>
        )}

        {/* Loading skeleton */}
        {state.kind === 'loading' && (
          <Section background="primary">
            <div className="mx-auto max-w-3xl space-y-6">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="animate-pulse p-6"
                  style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}
                >
                  <div className="h-4 w-1/3 mb-4" style={{ background: 'var(--bg-subtle)' }} />
                  <div className="h-3 w-2/3 mb-2" style={{ background: 'var(--bg-subtle)' }} />
                  <div className="h-3 w-1/2" style={{ background: 'var(--bg-subtle)' }} />
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Multiple matches — disambiguation list */}
        {state.kind === 'matches' && (
          <Section background="primary">
            <div className="mx-auto max-w-3xl">
              <div className="mb-6">
                <p className="font-mono text-xs uppercase tracking-wider mb-2" style={{ color: 'var(--accent)' }}>
                  {state.items.length} provedores encontrados
                </p>
                <h2
                  className="font-serif text-2xl font-bold tracking-tight"
                  style={{ color: 'var(--text-primary)', lineHeight: 1.15 }}
                >
                  Selecione o provedor para ver o Raio-X completo.
                </h2>
              </div>

              <div className="space-y-0" style={{ border: '1px solid var(--border)' }}>
                {state.items.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleSelectMatch(item)}
                    className="w-full text-left p-5 flex items-center justify-between gap-4 transition-colors hover:bg-stone-50"
                    style={{ borderBottom: '1px solid var(--border)' }}
                  >
                    <div className="flex-1 min-w-0">
                      <span className="text-base font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                        {item.name}
                      </span>
                    </div>
                    <ArrowRight size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                  </button>
                ))}
              </div>
            </div>
          </Section>
        )}

        {/* Full provider report */}
        {selectedProvider && (
          <>
            {/* Provider header card */}
            <Section background="primary">
              <div className="mx-auto max-w-4xl">
                <div
                  className="p-6 md:p-8"
                  style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}
                >
                  {/* Name + tier */}
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <h2
                        className="font-serif text-2xl font-bold tracking-tight md:text-3xl"
                        style={{ color: 'var(--text-primary)' }}
                      >
                        {selectedProvider.name}
                      </h2>
                      {selectedProvider.is_group && selectedProvider.entities ? (
                        <p className="mt-1 text-sm" style={{ color: 'var(--text-muted)' }}>
                          <span
                            className="inline-flex items-center gap-1 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider mr-2"
                            style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--accent)', border: '1px solid rgba(99,102,241,0.2)' }}
                          >
                            {selectedProvider.entity_count} entidades
                          </span>
                          {selectedProvider.entities.map(e => e.name).join(' + ')}
                        </p>
                      ) : (
                        <p className="mt-1 text-sm" style={{ color: 'var(--text-muted)' }}>
                          ID Anatel: {selectedProvider.provider_id}
                        </p>
                      )}
                    </div>
                    {selectedProvider.pulso_tier && (
                      <div className="text-center">
                        <div
                          className="font-mono text-3xl font-bold px-4 py-2"
                          style={{
                            color: '#fff',
                            background: tierColor(selectedProvider.pulso_tier),
                          }}
                        >
                          {selectedProvider.pulso_tier}
                        </div>
                        <p className="mt-1 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                          Pulso Tier
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Pulso Score bar */}
                  {selectedProvider.pulso_score !== null && (
                    <div className="mt-6">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                          Pulso Score
                        </span>
                        <span
                          className="font-mono text-xl font-bold"
                          style={{ color: scoreBarColor(selectedProvider.pulso_score) }}
                        >
                          {selectedProvider.pulso_score.toFixed(1)}
                        </span>
                      </div>
                      <div className="h-3 w-full" style={{ background: 'var(--bg-subtle)' }}>
                        <div
                          className="h-full transition-all duration-700"
                          style={{
                            width: `${Math.min(selectedProvider.pulso_score, 100)}%`,
                            background: scoreBarColor(selectedProvider.pulso_score),
                          }}
                        />
                      </div>
                      <div className="mt-1 flex justify-between font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                        <span>0</span>
                        <span>20</span>
                        <span>40</span>
                        <span>60</span>
                        <span>80</span>
                        <span>100</span>
                      </div>
                    </div>
                  )}

                  {/* Metrics row */}
                  <div
                    className="mt-6 grid grid-cols-2 gap-0 md:grid-cols-4"
                    style={{ borderTop: '1px solid var(--border)' }}
                  >
                    <MetricCell
                      label="Assinantes"
                      value={formatNumber(selectedProvider.total_subscribers)}
                      icon={<Users size={14} />}
                    />
                    <MetricCell
                      label="Crescimento"
                      value={
                        selectedProvider.growth_pct !== null
                          ? `${selectedProvider.growth_pct > 0 ? '+' : ''}${selectedProvider.growth_pct.toFixed(1)}%`
                          : 'N/D'
                      }
                      icon={
                        selectedProvider.growth_pct !== null && selectedProvider.growth_pct >= 0
                          ? <TrendingUp size={14} />
                          : <TrendingDown size={14} />
                      }
                      valueColor={
                        selectedProvider.growth_pct === null
                          ? 'var(--text-muted)'
                          : selectedProvider.growth_pct >= 0
                            ? 'var(--success)'
                            : 'var(--danger)'
                      }
                    />
                    <MetricCell
                      label="Fibra"
                      value={
                        selectedProvider.fiber_pct !== null
                          ? `${selectedProvider.fiber_pct.toFixed(1)}%`
                          : 'N/D'
                      }
                      icon={<Zap size={14} />}
                      valueColor={
                        selectedProvider.fiber_pct !== null && selectedProvider.fiber_pct >= 70
                          ? 'var(--success)'
                          : selectedProvider.fiber_pct !== null && selectedProvider.fiber_pct >= 40
                            ? 'var(--warning)'
                            : 'var(--text-muted)'
                      }
                    />
                    <MetricCell
                      label="Municipios"
                      value={selectedProvider.municipality_count.toLocaleString('pt-BR')}
                      icon={<MapPin size={14} />}
                    />
                  </div>
                </div>

                {/* Growth chart — 37-month subscriber + fiber % */}
                {historico && historico.history.length > 1 && (
                  <div className="mt-6" style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                    <div className="p-5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
                      <div className="flex items-center gap-2">
                        <TrendingUp size={16} style={{ color: 'var(--accent)' }} />
                        <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                          Evolucao historica
                        </h3>
                        <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                          {historico.history.length} meses
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs">
                        <span className="flex items-center gap-1.5">
                          <span className="inline-block h-2 w-6" style={{ background: 'var(--accent)', borderRadius: 1 }} />
                          <span style={{ color: 'var(--text-muted)' }}>Assinantes</span>
                        </span>
                        <span className="flex items-center gap-1.5">
                          <span className="inline-block h-2 w-6" style={{ background: '#22c55e', borderRadius: 1 }} />
                          <span style={{ color: 'var(--text-muted)' }}>% Fibra</span>
                        </span>
                      </div>
                    </div>
                    <div className="p-5">
                      <GrowthChart history={historico.history} />
                    </div>
                  </div>
                )}

                {/* Municipality sparklines */}
                {historico && historico.municipality_histories.length > 0 && (
                  <div className="mt-6" style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                    <div className="p-5 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
                      <Activity size={16} style={{ color: 'var(--accent)' }} />
                      <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                        Tendencia por municipio (top 5)
                      </h3>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-5 gap-0">
                      {historico.municipality_histories.map((mh, i) => (
                        <div
                          key={i}
                          className="p-4"
                          style={{ borderRight: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                              {mh.municipality}
                            </span>
                            <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                              {mh.state}
                            </span>
                          </div>
                          <Sparkline
                            data={mh.history.map(h => h.share_pct)}
                            label={`${mh.history[mh.history.length - 1]?.share_pct.toFixed(1)}%`}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Municipalities table */}
                {selectedProvider.municipalities.length > 0 && (
                  <div className="mt-6" style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                    <div className="p-5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
                      <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                        Municipios atendidos
                      </h3>
                      <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                        {selectedProvider.municipalities.length} municipios
                      </span>
                    </div>

                    {/* Desktop table */}
                    <div className="hidden md:block overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr style={{ borderBottom: '1px solid var(--border)' }}>
                            <th className="text-left py-3 px-5 font-medium text-xs uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                              Municipio
                            </th>
                            <th className="text-left py-3 px-5 font-medium text-xs uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                              UF
                            </th>
                            <th className="text-right py-3 px-5 font-medium text-xs uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                              Assinantes
                            </th>
                            <th className="text-right py-3 px-5 font-medium text-xs uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                              Share %
                            </th>
                            <th className="text-right py-3 px-5 font-medium text-xs uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                              HHI
                            </th>
                            <th className="text-right py-3 px-5 font-medium text-xs uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                              Mercado total
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedProvider.municipalities.map((mun, i) => (
                            <tr
                              key={i}
                              style={{
                                borderBottom: '1px solid var(--border)',
                                background: i % 2 === 0 ? 'transparent' : 'var(--bg-subtle)',
                              }}
                            >
                              <td className="py-3 px-5 font-medium" style={{ color: 'var(--text-primary)' }}>
                                {mun.municipality}
                              </td>
                              <td className="py-3 px-5 font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                                {mun.uf}
                              </td>
                              <td className="py-3 px-5 text-right font-mono" style={{ color: 'var(--text-primary)' }}>
                                {mun.subscribers.toLocaleString('pt-BR')}
                              </td>
                              <td className="py-3 px-5 text-right font-mono font-semibold" style={{ color: 'var(--accent)' }}>
                                {mun.share_pct.toFixed(1)}%
                              </td>
                              <td className="py-3 px-5 text-right">
                                <span className="inline-flex items-center gap-2 font-mono">
                                  <span
                                    className="inline-block h-2 w-2"
                                    style={{ background: hhiColor(mun.hhi), borderRadius: '50%' }}
                                  />
                                  <span style={{ color: hhiColor(mun.hhi) }}>
                                    {mun.hhi.toLocaleString('pt-BR')}
                                  </span>
                                </span>
                              </td>
                              <td className="py-3 px-5 text-right font-mono" style={{ color: 'var(--text-secondary)' }}>
                                {mun.total_market.toLocaleString('pt-BR')}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Mobile cards */}
                    <div className="md:hidden divide-y" style={{ borderColor: 'var(--border)' }}>
                      {selectedProvider.municipalities.map((mun, i) => (
                        <div key={i} className="p-4">
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
                              {mun.municipality}
                            </span>
                            <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                              {mun.uf}
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div>
                              <span style={{ color: 'var(--text-muted)' }}>Assinantes: </span>
                              <span className="font-mono" style={{ color: 'var(--text-primary)' }}>
                                {mun.subscribers.toLocaleString('pt-BR')}
                              </span>
                            </div>
                            <div>
                              <span style={{ color: 'var(--text-muted)' }}>Share: </span>
                              <span className="font-mono font-semibold" style={{ color: 'var(--accent)' }}>
                                {mun.share_pct.toFixed(1)}%
                              </span>
                            </div>
                            <div>
                              <span style={{ color: 'var(--text-muted)' }}>HHI: </span>
                              <span className="font-mono" style={{ color: hhiColor(mun.hhi) }}>
                                {mun.hhi.toLocaleString('pt-BR')}
                              </span>
                            </div>
                            <div>
                              <span style={{ color: 'var(--text-muted)' }}>Mercado: </span>
                              <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>
                                {mun.total_market.toLocaleString('pt-BR')}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Insights card */}
                {insights && (
                  <div className="mt-6" style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                    <div className="p-5 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
                      <BarChart3 size={16} style={{ color: 'var(--accent)' }} />
                      <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                        Insights automaticos
                      </h3>
                    </div>
                    <div className="p-5">
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                        <InsightCard
                          label="Municipios atendidos"
                          value={insights.totalMunicipalities.toString()}
                          icon={<MapPin size={14} />}
                        />
                        <InsightCard
                          label="Mercado mais forte"
                          value={insights.strongestMarket}
                          sub={`${insights.strongestShare.toFixed(1)}% share`}
                          icon={<Shield size={14} />}
                        />
                        <InsightCard
                          label="Mercado mais fraco"
                          value={insights.weakestMarket}
                          sub={`${insights.weakestShare.toFixed(1)}% share`}
                          icon={<AlertTriangle size={14} />}
                        />
                        <InsightCard
                          label="HHI medio"
                          value={insights.avgHHI.toLocaleString('pt-BR')}
                          sub={hhiLabel(insights.avgHHI)}
                          icon={<BarChart3 size={14} />}
                          valueColor={hhiColor(insights.avgHHI)}
                        />
                      </div>

                      {/* Alert messages */}
                      {insights.alerts.length > 0 && (
                        <div className="mt-5 space-y-2">
                          {insights.alerts.map((alert, i) => (
                            <div
                              key={i}
                              className="flex items-start gap-3 p-3 text-sm"
                              style={{
                                background: alert.type === 'warning' ? 'rgba(217,119,6,0.06)' : 'rgba(99,102,241,0.06)',
                                border: `1px solid ${alert.type === 'warning' ? 'rgba(217,119,6,0.15)' : 'rgba(99,102,241,0.15)'}`,
                              }}
                            >
                              {alert.type === 'warning' ? (
                                <AlertTriangle size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--warning)' }} />
                              ) : (
                                <Zap size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--accent)' }} />
                              )}
                              <span style={{ color: 'var(--text-secondary)' }}>{alert.message}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* ───── Competitive Position Card (FREE) ───── */}
              {position && (
                <div className="mx-auto max-w-4xl mt-8">
                  <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                    <div className="p-5 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
                      <Award size={16} style={{ color: 'var(--accent)' }} />
                      <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                        Posicao competitiva nacional
                      </h3>
                      <span className="ml-auto font-mono text-[10px] uppercase px-2 py-0.5" style={{ background: 'rgba(34,197,94,0.1)', color: 'var(--success)', border: '1px solid rgba(34,197,94,0.2)' }}>
                        Gratuito
                      </span>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-0">
                      <div className="p-4" style={{ borderRight: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
                        <div className="text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Ranking nacional</div>
                        <div className="font-mono text-2xl font-bold" style={{ color: 'var(--accent)' }}>
                          #{position.national_rank ?? '—'}
                        </div>
                      </div>
                      <div className="p-4" style={{ borderRight: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
                        <div className="text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Market share</div>
                        <div className="font-mono text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                          {position.national_share_pct != null ? `${position.national_share_pct}%` : '—'}
                        </div>
                      </div>
                      <div className="p-4" style={{ borderRight: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
                        <div className="text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Estados</div>
                        <div className="font-mono text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                          {position.states}
                        </div>
                      </div>
                      <div className="p-4" style={{ borderBottom: '1px solid var(--border)' }}>
                        <div className="text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Crescimento 12m</div>
                        <div className="font-mono text-2xl font-bold" style={{ color: position.growth_12m_pct != null && position.growth_12m_pct >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                          {position.growth_12m_pct != null ? `${position.growth_12m_pct > 0 ? '+' : ''}${position.growth_12m_pct}%` : '—'}
                        </div>
                      </div>
                    </div>

                    {/* Tech breakdown bar */}
                    <div className="p-4">
                      <div className="text-xs uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>Mix tecnologico</div>
                      <div className="h-4 flex w-full overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                        <div style={{ width: `${position.fiber_pct}%`, background: '#22c55e' }} title={`Fibra ${position.fiber_pct}%`} />
                        <div style={{ width: `${position.radio_pct}%`, background: '#f59e0b' }} title={`Radio ${position.radio_pct}%`} />
                        <div style={{ width: `${Math.max(0, 100 - position.fiber_pct - position.radio_pct)}%`, background: 'var(--bg-subtle)' }} title="Outros" />
                      </div>
                      <div className="mt-1.5 flex gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
                        <span className="flex items-center gap-1"><span className="inline-block h-2 w-3" style={{ background: '#22c55e' }} /> Fibra {position.fiber_pct}%</span>
                        <span className="flex items-center gap-1"><span className="inline-block h-2 w-3" style={{ background: '#f59e0b' }} /> Radio {position.radio_pct}%</span>
                        <span className="flex items-center gap-1"><span className="inline-block h-2 w-3" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }} /> Outros {(100 - position.fiber_pct - position.radio_pct).toFixed(1)}%</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ───── Employment Card (FREE) ───── */}
              {position?.employment && (
                <div className="mx-auto max-w-4xl mt-6">
                  <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                    <div className="p-5 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
                      <Briefcase size={16} style={{ color: 'var(--accent)' }} />
                      <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                        Emprego no setor (municipios atendidos)
                      </h3>
                      <span className="ml-auto font-mono text-[10px] uppercase px-2 py-0.5" style={{ background: 'rgba(34,197,94,0.1)', color: 'var(--success)', border: '1px solid rgba(34,197,94,0.2)' }}>
                        Gratuito
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-0">
                      <div className="p-4" style={{ borderRight: '1px solid var(--border)' }}>
                        <div className="text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Empregos telecom</div>
                        <div className="font-mono text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                          {position.employment.total_employees.toLocaleString('pt-BR')}
                        </div>
                      </div>
                      <div className="p-4" style={{ borderRight: '1px solid var(--border)' }}>
                        <div className="text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Salario medio</div>
                        <div className="font-mono text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                          {position.employment.avg_salary_brl
                            ? `R$ ${position.employment.avg_salary_brl.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
                            : 'N/D'}
                        </div>
                      </div>
                      <div className="p-4">
                        <div className="text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>Anos de dados</div>
                        <div className="font-mono text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                          {position.employment.years_available}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ───── Intelligence Feed (LOCKED) ───── */}
              {intel && (
                <div className="mx-auto max-w-4xl mt-6 space-y-4">
                  {/* Gazette mentions */}
                  {intel.gazette.total_mentions > 0 && (
                    <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                      <div className="p-5 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
                        <FileText size={16} style={{ color: 'var(--accent)' }} />
                        <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                          Diario Oficial
                        </h3>
                        <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                          {intel.gazette.total_mentions} mencoes encontradas
                        </span>
                        <span className="ml-auto flex items-center gap-1 font-mono text-[10px] uppercase px-2 py-0.5" style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--accent)', border: '1px solid rgba(99,102,241,0.2)' }}>
                          <Lock size={10} /> Pro
                        </span>
                      </div>
                      {/* Free: type breakdown */}
                      <div className="p-4 grid grid-cols-3 md:grid-cols-6 gap-2">
                        {Object.entries(intel.gazette.by_type).slice(0, 6).map(([type, count]) => (
                          <div key={type} className="text-center p-2" style={{ background: 'var(--bg-subtle)' }}>
                            <div className="font-mono text-sm font-bold" style={{ color: 'var(--accent)' }}>{count}</div>
                            <div className="text-[10px] capitalize" style={{ color: 'var(--text-muted)' }}>{type.replace('_', ' ')}</div>
                          </div>
                        ))}
                      </div>
                      {/* Locked: detail list */}
                      <PaywallCTA title="Veja todos os trechos do Diario Oficial">
                        <div className="p-4 space-y-2">
                          {[1, 2, 3].map(i => (
                            <div key={i} className="p-3" style={{ background: 'var(--bg-subtle)' }}>
                              <div className="h-3 w-1/3 mb-2" style={{ background: 'var(--border)' }} />
                              <div className="h-2 w-full mb-1" style={{ background: 'var(--border)' }} />
                              <div className="h-2 w-2/3" style={{ background: 'var(--border)' }} />
                            </div>
                          ))}
                        </div>
                      </PaywallCTA>
                    </div>
                  )}

                  {/* Regulatory acts */}
                  {intel.regulatory.relevant_acts > 0 && (
                    <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                      <div className="p-5 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
                        <Scale size={16} style={{ color: 'var(--accent)' }} />
                        <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                          Radar regulatorio
                        </h3>
                        <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                          {intel.regulatory.relevant_acts} atos relevantes
                        </span>
                        <span className="ml-auto flex items-center gap-1 font-mono text-[10px] uppercase px-2 py-0.5" style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--accent)', border: '1px solid rgba(99,102,241,0.2)' }}>
                          <Lock size={10} /> Pro
                        </span>
                      </div>
                      <div className="p-4">
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                          Ultimo ato: <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{intel.regulatory.latest_act_title || '—'}</span>
                        </p>
                      </div>
                      <PaywallCTA title="Acesse todos os atos regulatorios detalhados">
                        <div className="p-4 space-y-2">
                          {[1, 2].map(i => (
                            <div key={i} className="p-3" style={{ background: 'var(--bg-subtle)' }}>
                              <div className="h-3 w-1/2 mb-2" style={{ background: 'var(--border)' }} />
                              <div className="h-2 w-full" style={{ background: 'var(--border)' }} />
                            </div>
                          ))}
                        </div>
                      </PaywallCTA>
                    </div>
                  )}

                  {/* BNDES + Spectrum side by side */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* BNDES loans */}
                    <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                      <div className="p-4 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
                        <DollarSign size={16} style={{ color: 'var(--accent)' }} />
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>BNDES</h3>
                        <span className="ml-auto flex items-center gap-1 font-mono text-[10px] uppercase px-2 py-0.5" style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--accent)', border: '1px solid rgba(99,102,241,0.2)' }}>
                          <Lock size={10} /> Pro
                        </span>
                      </div>
                      <div className="p-4">
                        <div className="font-mono text-2xl font-bold" style={{ color: 'var(--accent)' }}>
                          {intel.bndes.loans_count}
                        </div>
                        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                          {intel.bndes.loans_count > 0
                            ? `R$ ${(intel.bndes.total_value_brl / 1_000_000).toFixed(1)}M em financiamentos`
                            : 'Nenhum financiamento encontrado'}
                        </div>
                      </div>
                      {intel.bndes.loans_count > 0 && (
                        <PaywallCTA title="Detalhes dos contratos BNDES">
                          <div className="p-4">
                            <div className="h-3 w-2/3 mb-2" style={{ background: 'var(--border)' }} />
                            <div className="h-2 w-full" style={{ background: 'var(--border)' }} />
                          </div>
                        </PaywallCTA>
                      )}
                    </div>

                    {/* Spectrum licenses */}
                    <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                      <div className="p-4 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
                        <Radio size={16} style={{ color: 'var(--accent)' }} />
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Espectro</h3>
                        <span className="ml-auto flex items-center gap-1 font-mono text-[10px] uppercase px-2 py-0.5" style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--accent)', border: '1px solid rgba(99,102,241,0.2)' }}>
                          <Lock size={10} /> Pro
                        </span>
                      </div>
                      <div className="p-4">
                        <div className="font-mono text-2xl font-bold" style={{ color: 'var(--accent)' }}>
                          {intel.spectrum.licenses_count}
                        </div>
                        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                          {intel.spectrum.licenses_count > 0 ? 'licencas de espectro' : 'Nenhuma licenca encontrada'}
                        </div>
                      </div>
                      {intel.spectrum.licenses_count > 0 && (
                        <PaywallCTA title="Detalhes das licencas de espectro">
                          <div className="p-4">
                            <div className="h-3 w-2/3 mb-2" style={{ background: 'var(--border)' }} />
                            <div className="h-2 w-full" style={{ background: 'var(--border)' }} />
                          </div>
                        </PaywallCTA>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </Section>

            {/* ───── Quality Seals (Anatel) ───── */}
            {quality && quality.total_evaluated > 0 && (
              <Section>
                <div className="mx-auto max-w-5xl">
                  <h2 className="font-serif text-xl font-bold tracking-tight mb-4" style={{ color: 'var(--text-primary)' }}>
                    <Award size={18} className="inline mr-2" style={{ color: 'var(--accent)' }} />
                    Selo de Qualidade Anatel
                  </h2>
                  <div className="grid md:grid-cols-4 gap-4 mb-4">
                    {['ouro', 'prata', 'bronze', 'sem_selo'].map(level => (
                      <div key={level} className="p-4 text-center" style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                        <div className="font-mono text-2xl font-bold" style={{
                          color: level === 'ouro' ? '#eab308' : level === 'prata' ? '#94a3b8' : level === 'bronze' ? '#b45309' : 'var(--text-muted)',
                        }}>
                          {quality.seal_summary[level] || 0}
                        </div>
                        <div className="text-xs mt-1 capitalize" style={{ color: 'var(--text-secondary)' }}>
                          {level === 'sem_selo' ? 'Sem Selo' : level.charAt(0).toUpperCase() + level.slice(1)}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {quality.total_evaluated} municipios avaliados pela Anatel
                  </div>
                </div>
              </Section>
            )}

            {/* ───── Competitive Dynamics ───── */}
            {dynamics && dynamics.periods.length > 0 && (
              <Section>
                <div className="mx-auto max-w-5xl">
                  <h2 className="font-serif text-xl font-bold tracking-tight mb-4" style={{ color: 'var(--text-primary)' }}>
                    <Activity size={18} className="inline mr-2" style={{ color: 'var(--accent)' }} />
                    Dinamica Competitiva ({dynamics.summary.total_periods} periodos)
                  </h2>
                  <div className="grid md:grid-cols-3 gap-4 mb-4">
                    <div className="p-4" style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Crescimento Assinantes</div>
                      <div className="font-mono text-2xl font-bold" style={{
                        color: dynamics.summary.subscriber_growth_pct >= 0 ? 'var(--success)' : 'var(--danger)',
                      }}>
                        {dynamics.summary.subscriber_growth_pct > 0 ? '+' : ''}{dynamics.summary.subscriber_growth_pct}%
                      </div>
                    </div>
                    <div className="p-4" style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Expansao Municipios</div>
                      <div className="font-mono text-2xl font-bold" style={{
                        color: dynamics.summary.municipality_change >= 0 ? 'var(--success)' : 'var(--danger)',
                      }}>
                        {dynamics.summary.municipality_change > 0 ? '+' : ''}{dynamics.summary.municipality_change}
                      </div>
                    </div>
                    <div className="p-4" style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Lider em Mercados (ultimo)</div>
                      <div className="font-mono text-2xl font-bold" style={{ color: 'var(--accent)' }}>
                        {dynamics.periods[dynamics.periods.length - 1]?.markets_as_leader || 0}
                      </div>
                    </div>
                  </div>
                  {/* Mini timeline */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs" style={{ color: 'var(--text-secondary)' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border)' }}>
                          <th className="text-left py-1 px-2">Periodo</th>
                          <th className="text-right py-1 px-2">Assinantes</th>
                          <th className="text-right py-1 px-2">Municipios</th>
                          <th className="text-right py-1 px-2">Market Share</th>
                          <th className="text-right py-1 px-2">Lider</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dynamics.periods.slice(-6).map(p => (
                          <tr key={p.period} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td className="py-1 px-2 font-mono">{p.period}</td>
                            <td className="py-1 px-2 text-right font-mono">{formatNumber(p.total_subscribers)}</td>
                            <td className="py-1 px-2 text-right">{p.municipalities}</td>
                            <td className="py-1 px-2 text-right">{p.avg_market_share}%</td>
                            <td className="py-1 px-2 text-right">{p.markets_as_leader}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </Section>
            )}

            {/* ───── Government Contracts (LOCKED) ───── */}
            {contracts && contracts.total_contracts > 0 && (
              <Section>
                <div className="mx-auto max-w-5xl">
                  <div className="p-4 flex items-center gap-2 mb-4" style={{ borderBottom: '1px solid var(--border)' }}>
                    <FileText size={18} style={{ color: 'var(--accent)' }} />
                    <h2 className="font-serif text-xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                      Contratos Governamentais
                    </h2>
                    <span className="ml-auto flex items-center gap-1 font-mono text-[10px] uppercase px-2 py-0.5" style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--accent)', border: '1px solid rgba(99,102,241,0.2)' }}>
                      <Lock size={10} /> Pro
                    </span>
                  </div>
                  <div className="grid md:grid-cols-2 gap-4 mb-4">
                    <div className="p-4" style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                      <div className="font-mono text-2xl font-bold" style={{ color: 'var(--accent)' }}>{contracts.total_contracts}</div>
                      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>contratos encontrados</div>
                    </div>
                    <div className="p-4" style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                      <div className="font-mono text-2xl font-bold" style={{ color: 'var(--success)' }}>
                        R${formatNumber(contracts.total_value_brl)}
                      </div>
                      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>valor total</div>
                    </div>
                  </div>
                  <PaywallCTA title="Detalhes dos contratos governamentais">
                    <div className="p-4 space-y-2">
                      {contracts.by_sphere.map(s => (
                        <div key={s.sphere} className="flex justify-between text-sm">
                          <span>{s.sphere}</span>
                          <span>R${formatNumber(s.total_brl)}</span>
                        </div>
                      ))}
                    </div>
                  </PaywallCTA>
                </div>
              </Section>
            )}

            {/* ───── Big CTA ───── */}
            <Section background="subtle">
              <div
                className="mx-auto max-w-3xl text-center p-10"
                style={{ border: '2px solid var(--accent)', background: 'var(--bg-surface)' }}
              >
                <div className="font-mono text-xs uppercase tracking-wider mb-3" style={{ color: 'var(--accent)' }}>
                  Valor estimado: R$2.000+ em consultoria
                </div>
                <h2 className="font-serif text-2xl font-bold tracking-tight md:text-3xl" style={{ color: 'var(--text-primary)', lineHeight: 1.15 }}>
                  Desbloqueie o relatorio completo
                </h2>
                <p className="mt-3 text-sm leading-relaxed max-w-xl mx-auto" style={{ color: 'var(--text-secondary)' }}>
                  Diario Oficial, atos regulatorios, financiamentos BNDES, licencas de espectro e analise competitiva detalhada.
                  Tudo em um unico relatorio.
                </p>
                <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                  <Link href="/precos" className="pulso-btn-primary inline-flex items-center gap-2 px-8 py-3">
                    A partir de R$99/mes <ArrowRight size={14} />
                  </Link>
                  <Link href="/precos" className="pulso-btn-outline px-6 py-3">
                    Relatorio avulso R$49
                  </Link>
                </div>
                <p className="mt-4 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                  Ou assine o plano Starter com 3 relatorios/mes inclusos.
                </p>
              </div>
            </Section>

            {/* CTA section */}
            <Section background="dark" grain>
              <div className="mx-auto max-w-2xl text-center">
                <div
                  className="mb-4 font-mono text-xs uppercase tracking-wider"
                  style={{ color: 'var(--accent-hover)' }}
                >
                  Pulso Network
                </div>
                <h2
                  className="font-serif text-2xl font-bold tracking-tight md:text-3xl"
                  style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}
                >
                  Quer a analise completa?
                </h2>
                <p className="mt-4 text-base leading-relaxed" style={{ color: 'var(--text-on-dark-secondary)' }}>
                  Expansao, M&A, conformidade, satelite e mais 24 modulos.
                  Dados cruzados de 19 fontes publicas, atualizados mensalmente.
                </p>
                <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                  <Link href="/precos" className="pulso-btn-dark inline-flex items-center gap-2">
                    Entrar na lista de espera <ArrowRight size={14} />
                  </Link>
                  <Link href="/produto" className="pulso-btn-ghost">
                    Ver plataforma
                  </Link>
                </div>
                <p className="mt-5 font-mono text-xs" style={{ color: 'var(--text-on-dark-muted)' }}>
                  Plano gratuito permanente. Sem cartao de credito.
                </p>
              </div>
            </Section>
          </>
        )}

        {/* Default state — no search yet */}
        {state.kind === 'idle' && (
          <Section background="subtle">
            <div className="mx-auto max-w-2xl text-center">
              <div className="mb-8">
                <div
                  className="mx-auto flex h-16 w-16 items-center justify-center mb-5"
                  style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}
                >
                  <Search size={24} style={{ color: 'var(--accent)' }} />
                </div>
                <h3
                  className="font-serif text-xl font-bold tracking-tight"
                  style={{ color: 'var(--text-primary)' }}
                >
                  Busque qualquer provedor brasileiro
                </h3>
                <p className="mt-3 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  Temos dados de 13.534 provedores em 5.572 municipios.
                  Dados oficiais da Anatel, processados pelo Pulso Score.
                </p>
              </div>

              {/* Example chips */}
              <div className="flex flex-wrap items-center justify-center gap-2">
                {['Claro', 'Vivo', 'Brisanet', 'Desktop', 'Algar', 'Unifique', 'Sumicity'].map((name) => (
                  <button
                    key={name}
                    onClick={() => {
                      setQuery(name);
                      doSearch(name);
                    }}
                    className="px-4 py-2 text-sm font-medium transition-colors"
                    style={{
                      border: '1px solid var(--border)',
                      background: 'var(--bg-surface)',
                      color: 'var(--text-secondary)',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--accent)';
                      e.currentTarget.style.color = 'var(--accent)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--border)';
                      e.currentTarget.style.color = 'var(--text-secondary)';
                    }}
                  >
                    {name}
                  </button>
                ))}
              </div>

              {/* How it works mini */}
              <div
                className="mt-12 grid grid-cols-1 gap-0 md:grid-cols-3 text-left"
                style={{ border: '1px solid var(--border)' }}
              >
                {[
                  { num: '01', title: 'Busque', desc: 'Digite o nome do provedor no campo acima.' },
                  { num: '02', title: 'Descubra', desc: 'Veja Pulso Score, market share e HHI por municipio.' },
                  { num: '03', title: 'Decida', desc: 'Use os insights para planejar sua estrategia.' },
                ].map((step) => (
                  <div
                    key={step.num}
                    className="p-6"
                    style={{ borderRight: '1px solid var(--border)', background: 'var(--bg-surface)' }}
                  >
                    <div className="font-mono text-2xl font-bold" style={{ color: 'var(--accent)' }}>
                      {step.num}
                    </div>
                    <h4 className="mt-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                      {step.title}
                    </h4>
                    <p className="mt-1 text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                      {step.desc}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </Section>
        )}
      </div>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Sub-components
   ═══════════════════════════════════════════════════════════════ */

function MetricCell({
  label,
  value,
  icon,
  valueColor,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  valueColor?: string;
}) {
  return (
    <div className="py-5 pr-5 pl-0 first:pl-0" style={{ borderBottom: '1px solid var(--border)' }}>
      <div className="flex items-center gap-1.5 mb-1" style={{ color: 'var(--text-muted)' }}>
        {icon}
        <span className="text-xs uppercase tracking-wider">{label}</span>
      </div>
      <div
        className="font-mono text-xl font-bold tabular-nums"
        style={{ color: valueColor || 'var(--accent)' }}
      >
        {value}
      </div>
    </div>
  );
}

function InsightCard({
  label,
  value,
  sub,
  icon,
  valueColor,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ReactNode;
  valueColor?: string;
}) {
  return (
    <div className="p-4" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
      <div className="flex items-center gap-1.5 mb-2" style={{ color: 'var(--text-muted)' }}>
        {icon}
        <span className="text-xs uppercase tracking-wider">{label}</span>
      </div>
      <div
        className="font-mono text-lg font-bold truncate"
        style={{ color: valueColor || 'var(--text-primary)' }}
      >
        {value}
      </div>
      {sub && (
        <p className="mt-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>
          {sub}
        </p>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Growth Chart — pure Canvas, no external library
   ═══════════════════════════════════════════════════════════════ */

function GrowthChart({ history }: { history: HistoryPoint[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || history.length < 2) return;

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

    // Clear
    ctx.clearRect(0, 0, W, H);

    // Data ranges
    const subs = history.map(h => h.subscribers);
    const fibers = history.map(h => h.fiber_pct);
    const minS = Math.min(...subs) * 0.95;
    const maxS = Math.max(...subs) * 1.02;
    const minF = Math.max(0, Math.min(...fibers) - 5);
    const maxF = Math.min(100, Math.max(...fibers) + 5);

    const xAt = (i: number) => padL + (i / (history.length - 1)) * chartW;
    const yS = (v: number) => padT + (1 - (v - minS) / (maxS - minS)) * chartH;
    const yF = (v: number) => padT + (1 - (v - minF) / (maxF - minF)) * chartH;

    // Grid lines
    ctx.strokeStyle = 'rgba(0,0,0,0.06)';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = padT + (i / 4) * chartH;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(W - padR, y);
      ctx.stroke();
    }

    // Y-axis labels (subscribers)
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.fillStyle = '#78716c';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const val = minS + ((4 - i) / 4) * (maxS - minS);
      const label = val >= 1_000_000
        ? (val / 1_000_000).toFixed(1) + 'M'
        : (val / 1_000).toFixed(0) + 'K';
      ctx.fillText(label, padL - 8, padT + (i / 4) * chartH + 4);
    }

    // X-axis labels (every 6 months)
    ctx.textAlign = 'center';
    for (let i = 0; i < history.length; i++) {
      if (i % 6 === 0 || i === history.length - 1) {
        const p = history[i].period;
        const label = p.substring(5) + '/' + p.substring(2, 4);
        ctx.fillText(label, xAt(i), H - padB + 18);
      }
    }

    // Subscriber line (blue/accent)
    ctx.strokeStyle = '#6366f1';
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    for (let i = 0; i < history.length; i++) {
      const x = xAt(i);
      const y = yS(subs[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Subscriber area fill
    ctx.fillStyle = 'rgba(99,102,241,0.08)';
    ctx.beginPath();
    ctx.moveTo(xAt(0), yS(subs[0]));
    for (let i = 1; i < history.length; i++) ctx.lineTo(xAt(i), yS(subs[i]));
    ctx.lineTo(xAt(history.length - 1), padT + chartH);
    ctx.lineTo(xAt(0), padT + chartH);
    ctx.closePath();
    ctx.fill();

    // Fiber % line (green)
    ctx.strokeStyle = '#22c55e';
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    for (let i = 0; i < history.length; i++) {
      const x = xAt(i);
      const y = yF(fibers[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Endpoint dots
    const lastIdx = history.length - 1;
    // Subscriber dot
    ctx.beginPath();
    ctx.arc(xAt(lastIdx), yS(subs[lastIdx]), 4, 0, Math.PI * 2);
    ctx.fillStyle = '#6366f1';
    ctx.fill();
    // Fiber dot
    ctx.beginPath();
    ctx.arc(xAt(lastIdx), yF(fibers[lastIdx]), 4, 0, Math.PI * 2);
    ctx.fillStyle = '#22c55e';
    ctx.fill();

    // End value labels
    ctx.font = 'bold 11px "JetBrains Mono", monospace';
    ctx.textAlign = 'left';
    ctx.fillStyle = '#6366f1';
    const subsLabel = subs[lastIdx] >= 1_000_000
      ? (subs[lastIdx] / 1_000_000).toFixed(1) + 'M'
      : (subs[lastIdx] / 1_000).toFixed(0) + 'K';
    ctx.fillText(subsLabel, xAt(lastIdx) + 8, yS(subs[lastIdx]) + 4);

    ctx.fillStyle = '#22c55e';
    ctx.fillText(fibers[lastIdx].toFixed(1) + '%', xAt(lastIdx) + 8, yF(fibers[lastIdx]) + 4);

    // Growth badge
    const first = subs[0];
    const last = subs[lastIdx];
    const growthPct = ((last - first) / first * 100).toFixed(1);
    const growing = last >= first;
    ctx.font = 'bold 11px "JetBrains Mono", monospace';
    ctx.fillStyle = growing ? '#059669' : '#dc2626';
    ctx.textAlign = 'left';
    ctx.fillText(
      `${growing ? '+' : ''}${growthPct}% em ${history.length} meses`,
      padL + 4,
      padT + 14,
    );
  }, [history]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '220px', display: 'block' }}
    />
  );
}

/* ═══════════════════════════════════════════════════════════════
   Sparkline — tiny inline chart for municipality share trends
   ═══════════════════════════════════════════════════════════════ */

function Sparkline({ data, label }: { data: number[]; label: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length < 2) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = rect.height;
    const pad = 2;

    const min = Math.min(...data) * 0.9;
    const max = Math.max(...data) * 1.1 || 1;

    ctx.strokeStyle = '#6366f1';
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      const x = pad + (i / (data.length - 1)) * (W - pad * 2);
      const y = pad + (1 - (data[i] - min) / (max - min)) * (H - pad * 2);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Endpoint dot
    const lastX = W - pad;
    const lastY = pad + (1 - (data[data.length - 1] - min) / (max - min)) * (H - pad * 2);
    ctx.beginPath();
    ctx.arc(lastX, lastY, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = '#6366f1';
    ctx.fill();
  }, [data]);

  const trend = data.length >= 2 ? data[data.length - 1] - data[0] : 0;

  return (
    <div>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '32px', display: 'block' }}
      />
      <div className="mt-1 flex items-center justify-between">
        <span
          className="font-mono text-xs font-semibold"
          style={{ color: trend >= 0 ? 'var(--success)' : 'var(--danger)' }}
        >
          {trend >= 0 ? '+' : ''}{trend.toFixed(1)}pp
        </span>
        <span className="font-mono text-xs" style={{ color: 'var(--accent)' }}>
          {label}
        </span>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Insights computation
   ═══════════════════════════════════════════════════════════════ */

interface Alert {
  type: 'warning' | 'info';
  message: string;
}

interface Insights {
  totalMunicipalities: number;
  strongestMarket: string;
  strongestShare: number;
  weakestMarket: string;
  weakestShare: number;
  avgHHI: number;
  alerts: Alert[];
}

function computeInsights(provider: ProviderResult): Insights {
  const munis = provider.municipalities;
  const alerts: Alert[] = [];

  // Strongest / weakest by share
  const sorted = [...munis].sort((a, b) => b.share_pct - a.share_pct);
  const strongest = sorted[0] || { municipality: 'N/D', share_pct: 0 };
  const weakest = sorted[sorted.length - 1] || { municipality: 'N/D', share_pct: 0 };

  // Avg HHI
  const avgHHI = munis.length > 0
    ? Math.round(munis.reduce((sum, m) => sum + m.hhi, 0) / munis.length)
    : 0;

  // Concentrated markets
  const concentrated = munis.filter((m) => m.hhi > 2500);
  if (concentrated.length > 0) {
    alerts.push({
      type: 'warning',
      message: `${concentrated.length} municipio(s) com HHI acima de 2.500 (mercado concentrado). Risco regulatorio elevado.`,
    });
  }

  // Growth alert
  if (provider.growth_pct !== null && provider.growth_pct < 0) {
    alerts.push({
      type: 'warning',
      message: `Crescimento negativo de ${provider.growth_pct.toFixed(1)}%. Investigar perda de assinantes.`,
    });
  }

  // Fiber adoption
  if (provider.fiber_pct !== null && provider.fiber_pct < 30) {
    alerts.push({
      type: 'warning',
      message: `Apenas ${provider.fiber_pct.toFixed(1)}% da base em fibra. A migracao tecnologica e urgente para competir.`,
    });
  }

  // Low share markets
  const lowShare = munis.filter((m) => m.share_pct < 5);
  if (lowShare.length > 3) {
    alerts.push({
      type: 'info',
      message: `${lowShare.length} municipios com share abaixo de 5%. Oportunidade de consolidacao ou saida estrategica.`,
    });
  }

  // Dominant position
  const dominant = munis.filter((m) => m.share_pct > 50);
  if (dominant.length > 0) {
    alerts.push({
      type: 'info',
      message: `Posicao dominante (>50% share) em ${dominant.length} municipio(s). Ativo valioso para M&A.`,
    });
  }

  return {
    totalMunicipalities: munis.length,
    strongestMarket: strongest.municipality,
    strongestShare: strongest.share_pct,
    weakestMarket: weakest.municipality,
    weakestShare: weakest.share_pct,
    avgHHI,
    alerts,
  };
}
