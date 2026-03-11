'use client';

import { useState, useCallback, useRef, FormEvent } from 'react';
import Link from 'next/link';
import Section from '@/components/ui/Section';
import {
  Search, TrendingUp, TrendingDown, Shield, MapPin, BarChart3,
  Users, AlertTriangle, ArrowRight, Zap, Loader2, X,
} from 'lucide-react';

/* ═══════════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════════ */

interface Municipality {
  municipality: string;
  uf: string;
  subscribers: number;
  share_pct: number;
  hhi: number;
  total_market: number;
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
}

interface ApiResponse {
  query: string;
  match_count: number;
  results: ProviderResult[];
}

/* ═══════════════════════════════════════════════════════════════
   Helpers
   ═══════════════════════════════════════════════════════════════ */

const API_URL = 'https://api.pulso.network/api/v1/public/raio-x';

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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ApiResponse | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<ProviderResult | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const doSearch = useCallback(async (searchTerm: string) => {
    if (!searchTerm.trim()) return;
    setLoading(true);
    setError(null);
    setData(null);
    setSelectedProvider(null);

    try {
      const res = await fetch(`${API_URL}?q=${encodeURIComponent(searchTerm.trim())}`);
      if (!res.ok) throw new Error('Erro ao buscar dados');
      const json: ApiResponse = await res.json();

      if (json.match_count === 0) {
        setError('Provedor nao encontrado. Tente outro nome.');
        return;
      }

      setData(json);

      // Auto-select if single result
      if (json.match_count === 1) {
        setSelectedProvider(json.results[0]);
      }

      // Scroll to results
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } catch {
      setError('Erro de conexao. Verifique sua internet e tente novamente.');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    doSearch(query);
  };

  const handleSelectProvider = (provider: ProviderResult) => {
    setSelectedProvider(provider);
    setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  };

  const handleClear = () => {
    setQuery('');
    setData(null);
    setSelectedProvider(null);
    setError(null);
  };

  // Derived insights
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
                disabled={loading || !query.trim()}
                className="pulso-btn-primary flex items-center gap-2 px-8 disabled:opacity-50"
                style={{ height: '48px' }}
              >
                {loading ? (
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
        {error && (
          <Section background="primary">
            <div
              className="mx-auto max-w-xl text-center p-8"
              style={{ border: '1px solid var(--border)' }}
            >
              <AlertTriangle size={32} className="mx-auto mb-4" style={{ color: 'var(--warning)' }} />
              <p className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                {error}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                Verifique a grafia ou tente um nome parcial.
              </p>
            </div>
          </Section>
        )}

        {/* Loading skeleton */}
        {loading && (
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
        {data && data.match_count > 1 && !selectedProvider && (
          <Section background="primary">
            <div className="mx-auto max-w-3xl">
              <div className="mb-6">
                <p className="font-mono text-xs uppercase tracking-wider mb-2" style={{ color: 'var(--accent)' }}>
                  {data.match_count} provedores encontrados
                </p>
                <h2
                  className="font-serif text-2xl font-bold tracking-tight"
                  style={{ color: 'var(--text-primary)', lineHeight: 1.15 }}
                >
                  Selecione o provedor para ver o Raio-X completo.
                </h2>
              </div>

              <div className="space-y-0" style={{ border: '1px solid var(--border)' }}>
                {data.results.map((provider) => (
                  <button
                    key={provider.provider_id}
                    onClick={() => handleSelectProvider(provider)}
                    className="w-full text-left p-5 flex items-center justify-between gap-4 transition-colors hover:bg-stone-50"
                    style={{ borderBottom: '1px solid var(--border)' }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <span className="text-base font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                          {provider.name}
                        </span>
                        {provider.pulso_tier && (
                          <span
                            className="font-mono text-xs font-bold px-2 py-0.5"
                            style={{
                              color: '#fff',
                              background: tierColor(provider.pulso_tier),
                            }}
                          >
                            {provider.pulso_tier}
                          </span>
                        )}
                      </div>
                      <div className="mt-1 flex items-center gap-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                        <span className="flex items-center gap-1">
                          <Users size={12} />
                          {formatNumber(provider.total_subscribers)} assinantes
                        </span>
                        <span className="flex items-center gap-1">
                          <MapPin size={12} />
                          {provider.municipality_count} municipios
                        </span>
                      </div>
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
            {/* Back button if multiple matches */}
            {data && data.match_count > 1 && (
              <Section background="subtle" className="!py-4">
                <button
                  onClick={() => setSelectedProvider(null)}
                  className="text-sm flex items-center gap-2 transition-colors"
                  style={{ color: 'var(--accent)' }}
                >
                  <ArrowRight size={14} className="rotate-180" />
                  Voltar para {data.match_count} resultados
                </button>
              </Section>
            )}

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
                      <p className="mt-1 text-sm" style={{ color: 'var(--text-muted)' }}>
                        ID Anatel: {selectedProvider.provider_id}
                      </p>
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
                  <Link href="/cadastro" className="pulso-btn-dark inline-flex items-center gap-2">
                    Criar conta gratuita <ArrowRight size={14} />
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
        {!data && !loading && !error && (
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
