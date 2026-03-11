'use client';

import { useState, useCallback } from 'react';
import { useApi, useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatNumber, formatPct } from '@/lib/format';
import {
  Award,
  CreditCard,
  TrendingUp,
  BarChart3,
  Shield,
  Users,
  Filter,
  X,
  Loader2,
  AlertTriangle,
  Wifi,
  CheckCircle2,
  DollarSign,
  Building2,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BRAZILIAN_STATES = [
  { value: '', label: 'Todos os estados' },
  { value: 'AC', label: 'Acre' },
  { value: 'AL', label: 'Alagoas' },
  { value: 'AP', label: 'Amapa' },
  { value: 'AM', label: 'Amazonas' },
  { value: 'BA', label: 'Bahia' },
  { value: 'CE', label: 'Ceara' },
  { value: 'DF', label: 'Distrito Federal' },
  { value: 'ES', label: 'Espirito Santo' },
  { value: 'GO', label: 'Goias' },
  { value: 'MA', label: 'Maranhao' },
  { value: 'MT', label: 'Mato Grosso' },
  { value: 'MS', label: 'Mato Grosso do Sul' },
  { value: 'MG', label: 'Minas Gerais' },
  { value: 'PA', label: 'Para' },
  { value: 'PB', label: 'Paraiba' },
  { value: 'PR', label: 'Parana' },
  { value: 'PE', label: 'Pernambuco' },
  { value: 'PI', label: 'Piaui' },
  { value: 'RJ', label: 'Rio de Janeiro' },
  { value: 'RN', label: 'Rio Grande do Norte' },
  { value: 'RS', label: 'Rio Grande do Sul' },
  { value: 'RO', label: 'Rondonia' },
  { value: 'RR', label: 'Roraima' },
  { value: 'SC', label: 'Santa Catarina' },
  { value: 'SP', label: 'Sao Paulo' },
  { value: 'SE', label: 'Sergipe' },
  { value: 'TO', label: 'Tocantins' },
];

const TIER_OPTIONS = [
  { value: '', label: 'Todos os tiers' },
  { value: 'S', label: 'Tier S' },
  { value: 'A', label: 'Tier A' },
  { value: 'B', label: 'Tier B' },
  { value: 'C', label: 'Tier C' },
  { value: 'D', label: 'Tier D' },
];

const TIER_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  S: { bg: '#fef3c7', text: '#92400e', border: '#f59e0b' },
  A: { bg: '#d1fae5', text: '#065f46', border: '#10b981' },
  B: { bg: '#dbeafe', text: '#1e40af', border: '#3b82f6' },
  C: { bg: '#fef9c3', text: '#854d0e', border: '#eab308' },
  D: { bg: '#f3f4f6', text: '#374151', border: '#9ca3af' },
};

const TIER_ACCENT: Record<string, string> = {
  S: '#f59e0b',
  A: '#10b981',
  B: '#3b82f6',
  C: '#eab308',
  D: '#9ca3af',
};

const SUB_SCORE_LABELS: Record<string, { label: string; icon: React.ReactNode }> = {
  growth: { label: 'Crescimento', icon: <TrendingUp size={14} /> },
  fiber: { label: 'Fibra', icon: <Wifi size={14} /> },
  quality: { label: 'Qualidade', icon: <CheckCircle2 size={14} /> },
  compliance: { label: 'Conformidade', icon: <Shield size={14} /> },
  financial: { label: 'Financeiro', icon: <DollarSign size={14} /> },
  market: { label: 'Mercado', icon: <BarChart3 size={14} /> },
  bndes: { label: 'BNDES', icon: <Building2 size={14} /> },
};

// ---------------------------------------------------------------------------
// Tier Badge
// ---------------------------------------------------------------------------

function TierBadge({ tier, size = 'sm' }: { tier: string; size?: 'sm' | 'lg' }) {
  const colors = TIER_COLORS[tier] || TIER_COLORS.D;
  const isSm = size === 'sm';
  return (
    <span
      className="inline-flex items-center justify-center font-bold"
      style={{
        backgroundColor: colors.bg,
        color: colors.text,
        border: `1.5px solid ${colors.border}`,
        borderRadius: isSm ? '4px' : '6px',
        padding: isSm ? '1px 8px' : '2px 12px',
        fontSize: isSm ? '11px' : '14px',
        lineHeight: isSm ? '18px' : '24px',
      }}
    >
      {tier}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Score Bar
// ---------------------------------------------------------------------------

function ScoreBar({ value, color, label, maxValue = 100 }: { value: number | null; color: string; label: string; maxValue?: number }) {
  const safeVal = value ?? 0;
  const pct = Math.min((safeVal / maxValue) * 100, 100);
  return (
    <div className="flex items-center gap-3">
      <div className="flex w-28 items-center gap-2 shrink-0">
        {SUB_SCORE_LABELS[label]?.icon || <BarChart3 size={14} />}
        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          {SUB_SCORE_LABELS[label]?.label || label}
        </span>
      </div>
      <div className="flex-1">
        <div
          className="overflow-hidden"
          style={{ height: '8px', borderRadius: '4px', backgroundColor: 'var(--bg-subtle)' }}
        >
          <div
            style={{
              height: '100%',
              width: `${pct}%`,
              borderRadius: '4px',
              backgroundColor: color,
              transition: 'width 0.4s ease-out',
            }}
          />
        </div>
      </div>
      <span
        className="w-10 text-right text-sm font-semibold"
        style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}
      >
        {safeVal.toFixed(0)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score Gauge (visual arc display)
// ---------------------------------------------------------------------------

function ScoreGauge({ score, tier }: { score: number; tier: string }) {
  const accent = TIER_ACCENT[tier] || TIER_ACCENT.D;
  const pct = Math.min(score / 100, 1);
  // We build a simple semi-circular arc using CSS conic gradient
  const deg = pct * 180;

  return (
    <div className="flex flex-col items-center">
      <div
        className="relative flex items-end justify-center"
        style={{ width: '140px', height: '70px', overflow: 'hidden' }}
      >
        {/* Background arc */}
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            width: '140px',
            height: '140px',
            borderRadius: '50%',
            background: `conic-gradient(
              ${accent} 0deg ${deg}deg,
              var(--bg-subtle) ${deg}deg 180deg,
              transparent 180deg 360deg
            )`,
            mask: 'radial-gradient(circle at center, transparent 50px, black 51px)',
            WebkitMask: 'radial-gradient(circle at center, transparent 50px, black 51px)',
          }}
        />
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span
          className="text-3xl font-bold"
          style={{ color: accent, fontVariantNumeric: 'tabular-nums' }}
        >
          {score.toFixed(0)}
        </span>
        <span className="text-sm" style={{ color: 'var(--text-muted)' }}>/100</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 px-4 py-3">
      <div className="h-4 w-8 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
      <div className="h-4 flex-1 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
      <div className="h-4 w-16 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
      <div className="h-4 w-10 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
      <div className="h-4 w-12 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse space-y-2">
      {Array.from({ length: 10 }).map((_, i) => (
        <SkeletonRow key={i} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error Banner
// ---------------------------------------------------------------------------

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border px-4 py-3"
      style={{
        borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)',
        backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
      }}
    >
      <AlertTriangle size={18} className="shrink-0" style={{ color: 'var(--danger)' }} />
      <p className="text-sm" style={{ color: 'var(--danger)' }}>{message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Distribution Cards
// ---------------------------------------------------------------------------

function DistributionCards({ distribution }: { distribution: any }) {
  if (!distribution) return null;

  const tiers = ['S', 'A', 'B', 'C', 'D'];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {tiers.map((tier) => {
        const tierData = distribution.tiers?.[tier] || distribution[tier] || {};
        const count = tierData.count ?? tierData.total ?? 0;
        const avgScore = tierData.avg_score ?? tierData.average ?? 0;
        const colors = TIER_COLORS[tier];
        const accent = TIER_ACCENT[tier];

        return (
          <div
            key={tier}
            className="rounded-lg p-4"
            style={{
              backgroundColor: 'var(--bg-surface)',
              border: `1px solid ${colors.border}30`,
            }}
          >
            <div className="flex items-center justify-between mb-2">
              <TierBadge tier={tier} size="lg" />
              <Award size={18} style={{ color: accent, opacity: 0.6 }} />
            </div>
            <p
              className="text-2xl font-bold"
              style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}
            >
              {formatNumber(count)}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              provedores
            </p>
            {avgScore > 0 && (
              <p className="mt-1 text-xs" style={{ color: accent }}>
                Score medio: {avgScore.toFixed(1)}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ranking Table
// ---------------------------------------------------------------------------

function RankingTable({
  data,
  loading,
  onSelectProvider,
  selectedId,
}: {
  data: any[] | null;
  loading: boolean;
  onSelectProvider: (provider: any) => void;
  selectedId: number | null;
}) {
  if (loading) return <LoadingSkeleton />;
  if (!data || data.length === 0) {
    return (
      <div className="py-12 text-center">
        <Users size={32} style={{ color: 'var(--text-muted)', margin: '0 auto 8px' }} />
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Nenhum provedor encontrado com os filtros selecionados.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" style={{ borderCollapse: 'separate', borderSpacing: 0 }}>
        <thead>
          <tr>
            {['#', 'Provedor', 'Pulso Score', 'Tier', 'Estado'].map((h) => (
              <th
                key={h}
                className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider"
                style={{ backgroundColor: 'var(--bg-subtle)', color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row: any, idx: number) => {
            const rank = row.rank ?? idx + 1;
            const isSelected = selectedId === (row.provider_id ?? row.id);
            const tier = row.tier || 'D';
            const accent = TIER_ACCENT[tier] || TIER_ACCENT.D;

            return (
              <tr
                key={row.provider_id ?? row.id ?? idx}
                onClick={() => onSelectProvider(row)}
                className="cursor-pointer transition-colors"
                style={{
                  backgroundColor: isSelected
                    ? 'var(--accent-subtle)'
                    : idx % 2 === 0
                    ? 'transparent'
                    : 'color-mix(in srgb, var(--bg-subtle) 50%, transparent)',
                  borderBottom: '1px solid var(--border)',
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) (e.currentTarget.style.backgroundColor = 'var(--bg-subtle)');
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.backgroundColor =
                      idx % 2 === 0 ? 'transparent' : 'color-mix(in srgb, var(--bg-subtle) 50%, transparent)';
                  }
                }}
              >
                <td
                  className="px-4 py-2.5 font-medium"
                  style={{ color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums', width: '60px' }}
                >
                  {rank}
                </td>
                <td className="px-4 py-2.5">
                  <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
                    {row.provider_name ?? row.name ?? '--'}
                  </span>
                </td>
                <td className="px-4 py-2.5" style={{ width: '160px' }}>
                  <div className="flex items-center gap-2">
                    <div
                      className="overflow-hidden"
                      style={{ width: '60px', height: '6px', borderRadius: '3px', backgroundColor: 'var(--bg-subtle)' }}
                    >
                      <div
                        style={{
                          height: '100%',
                          width: `${Math.min((row.score ?? 0), 100)}%`,
                          borderRadius: '3px',
                          backgroundColor: accent,
                        }}
                      />
                    </div>
                    <span
                      className="text-sm font-bold"
                      style={{ color: accent, fontVariantNumeric: 'tabular-nums' }}
                    >
                      {(row.score ?? 0).toFixed(0)}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-2.5" style={{ width: '80px' }}>
                  <TierBadge tier={tier} />
                </td>
                <td className="px-4 py-2.5" style={{ color: 'var(--text-secondary)', width: '80px' }}>
                  {row.state ?? row.state_code ?? '--'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail Panel
// ---------------------------------------------------------------------------

function DetailPanel({
  provider,
  providerDetail,
  creditData,
  loadingDetail,
  loadingCredit,
  onClose,
}: {
  provider: any;
  providerDetail: any;
  creditData: any;
  loadingDetail: boolean;
  loadingCredit: boolean;
  onClose: () => void;
}) {
  const tier = providerDetail?.tier ?? provider?.tier ?? 'D';
  const accent = TIER_ACCENT[tier] || TIER_ACCENT.D;
  const score = providerDetail?.score ?? provider?.score ?? 0;
  const subScores = providerDetail?.sub_scores ?? {};

  return (
    <div
      className="rounded-xl"
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-4"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-3">
          <Award size={20} style={{ color: accent }} />
          <div>
            <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
              {provider?.provider_name ?? provider?.name ?? 'Provedor'}
            </h3>
            <div className="mt-1 flex items-center gap-2">
              <TierBadge tier={tier} />
              {providerDetail?.rank != null && (
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  Rank #{providerDetail.rank}
                </span>
              )}
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1.5 transition-colors"
          style={{ color: 'var(--text-muted)' }}
          aria-label="Fechar"
        >
          <X size={18} />
        </button>
      </div>

      {/* Body */}
      <div className="px-5 py-5 space-y-6">
        {loadingDetail ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent)' }} />
          </div>
        ) : (
          <>
            {/* Score Gauge */}
            <div className="flex justify-center">
              <ScoreGauge score={score} tier={tier} />
            </div>

            {/* Sub-scores */}
            <div>
              <h4
                className="mb-3 text-xs font-semibold uppercase tracking-wider"
                style={{ color: 'var(--text-muted)' }}
              >
                Componentes do Score
              </h4>
              <div className="space-y-2.5">
                {Object.entries(subScores).map(([key, val]) => (
                  <ScoreBar
                    key={key}
                    label={key}
                    value={val as number}
                    color={accent}
                  />
                ))}
                {Object.keys(subScores).length === 0 && (
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    Sub-scores nao disponiveis.
                  </p>
                )}
              </div>
            </div>
          </>
        )}

        {/* Credit Section */}
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
          <h4
            className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--text-muted)' }}
          >
            <CreditCard size={14} />
            Analise de Credito
          </h4>

          {loadingCredit ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 size={18} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
            </div>
          ) : creditData ? (
            <div className="space-y-3">
              {/* Rating + PD */}
              <div className="flex items-center gap-4">
                <div
                  className="flex h-12 w-12 items-center justify-center rounded-lg text-xl font-black"
                  style={{
                    backgroundColor: ratingColor(creditData.rating).bg,
                    color: ratingColor(creditData.rating).text,
                    border: `2px solid ${ratingColor(creditData.rating).border}`,
                  }}
                >
                  {creditData.rating ?? '--'}
                </div>
                <div>
                  <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Score: {(creditData.score ?? 0).toFixed(0)}
                  </p>
                  {creditData.probability_of_default != null && (
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      PD: {formatPct(creditData.probability_of_default * 100, 2)}
                    </p>
                  )}
                </div>
              </div>

              {/* Credit factors */}
              {creditData.factors && Object.keys(creditData.factors).length > 0 && (
                <div className="space-y-1.5">
                  {Object.entries(creditData.factors).map(([key, val]) => (
                    <div
                      key={key}
                      className="flex items-center justify-between rounded px-3 py-1.5"
                      style={{ backgroundColor: 'var(--bg-subtle)' }}
                    >
                      <span className="text-xs capitalize" style={{ color: 'var(--text-muted)' }}>
                        {key.replace(/_/g, ' ')}
                      </span>
                      <span
                        className="text-xs font-medium"
                        style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}
                      >
                        {typeof val === 'number' ? (val as number).toFixed(1) : String(val)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Credito nao disponivel para este provedor.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function ratingColor(rating: string | null): { bg: string; text: string; border: string } {
  const r = rating?.toUpperCase();
  if (r === 'AAA' || r === 'AA' || r === 'A') return { bg: '#d1fae5', text: '#065f46', border: '#10b981' };
  if (r === 'BBB' || r === 'BB' || r === 'B') return { bg: '#dbeafe', text: '#1e40af', border: '#3b82f6' };
  if (r === 'CCC' || r === 'CC' || r === 'C') return { bg: '#fef9c3', text: '#854d0e', border: '#eab308' };
  if (r === 'D') return { bg: '#fee2e2', text: '#991b1b', border: '#ef4444' };
  return { bg: '#f3f4f6', text: '#374151', border: '#9ca3af' };
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ProvedorPage() {
  // -- Filters --
  const [stateFilter, setStateFilter] = useState('');
  const [tierFilter, setTierFilter] = useState('');

  // -- Selected provider for detail panel --
  const [selectedProvider, setSelectedProvider] = useState<any>(null);

  // -- Distribution data --
  const { data: distribution, loading: distLoading, error: distError } = useApi<any>(
    () => api.pulsoScore.distribution(),
    []
  );

  // -- Ranking data (re-fetches when filters change) --
  const { data: ranking, loading: rankLoading, error: rankError } = useApi<any[]>(
    () =>
      api.pulsoScore.ranking({
        state: stateFilter || undefined,
        tier: tierFilter || undefined,
        limit: 100,
      }),
    [stateFilter, tierFilter]
  );

  // -- Provider detail (lazy) --
  const {
    data: providerDetail,
    loading: detailLoading,
    execute: fetchDetail,
    reset: resetDetail,
  } = useLazyApi<any, number>(
    useCallback((id: number) => api.pulsoScore.provider(id), [])
  );

  // -- Credit score (lazy) --
  const {
    data: creditData,
    loading: creditLoading,
    execute: fetchCredit,
    reset: resetCredit,
  } = useLazyApi<any, number>(
    useCallback((id: number) => api.credit.score(id), [])
  );

  // -- Handler: select provider --
  const handleSelectProvider = useCallback(
    (provider: any) => {
      const id = provider.provider_id ?? provider.id;
      if (id == null) return;

      // Toggle off if same provider
      if (selectedProvider && (selectedProvider.provider_id ?? selectedProvider.id) === id) {
        setSelectedProvider(null);
        resetDetail();
        resetCredit();
        return;
      }

      setSelectedProvider(provider);
      fetchDetail(id);
      fetchCredit(id);
    },
    [selectedProvider, fetchDetail, fetchCredit, resetDetail, resetCredit]
  );

  const handleCloseDetail = useCallback(() => {
    setSelectedProvider(null);
    resetDetail();
    resetCredit();
  }, [resetDetail, resetCredit]);

  const selectedId = selectedProvider ? (selectedProvider.provider_id ?? selectedProvider.id) : null;

  const hasError = distError || rankError;

  return (
    <div className="space-y-6 p-6">
      {/* Page Header */}
      <div>
        <h1
          className="flex items-center gap-3 text-2xl font-bold"
          style={{ color: 'var(--text-primary)' }}
        >
          <Award size={28} style={{ color: 'var(--accent)' }} />
          Perfil do Provedor
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Visao 360 do ISP com Pulso Score, rating de credito e ranking de provedores
        </p>
      </div>

      {/* Error banner */}
      {hasError && (
        <ErrorBanner
          message={distError || rankError || 'Erro ao carregar dados.'}
        />
      )}

      {/* Distribution Overview */}
      <div>
        <h2
          className="mb-3 flex items-center gap-2 text-sm font-semibold"
          style={{ color: 'var(--text-secondary)' }}
        >
          <BarChart3 size={16} style={{ color: 'var(--text-muted)' }} />
          Distribuicao por Tier
        </h2>
        {distLoading ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse rounded-lg p-4"
                style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border)' }}
              >
                <div className="h-6 w-10 rounded mb-3" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                <div className="h-8 w-16 rounded mb-1" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                <div className="h-3 w-20 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
              </div>
            ))}
          </div>
        ) : (
          <DistributionCards distribution={distribution} />
        )}
      </div>

      {/* Filters + Table + Detail panel */}
      <div className="flex gap-6">
        {/* Left: Table */}
        <div className="flex-1 min-w-0">
          {/* Filter row */}
          <div
            className="mb-4 flex flex-wrap items-center gap-3 rounded-lg px-4 py-3"
            style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border)' }}
          >
            <Filter size={16} style={{ color: 'var(--text-muted)' }} />
            <div>
              <select
                className="pulso-input text-sm"
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value)}
                style={{ minWidth: '180px' }}
              >
                {BRAZILIAN_STATES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.value ? `${s.value} - ${s.label}` : s.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <select
                className="pulso-input text-sm"
                value={tierFilter}
                onChange={(e) => setTierFilter(e.target.value)}
                style={{ minWidth: '140px' }}
              >
                {TIER_OPTIONS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            {(stateFilter || tierFilter) && (
              <button
                onClick={() => { setStateFilter(''); setTierFilter(''); }}
                className="flex items-center gap-1 rounded px-2 py-1 text-xs transition-colors"
                style={{ color: 'var(--text-muted)' }}
              >
                <X size={12} />
                Limpar filtros
              </button>
            )}
            {ranking && !rankLoading && (
              <span className="ml-auto text-xs" style={{ color: 'var(--text-muted)' }}>
                {ranking.length} provedor{ranking.length !== 1 ? 'es' : ''}
              </span>
            )}
          </div>

          {/* Table Card */}
          <div
            className="rounded-xl overflow-hidden"
            style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border)' }}
          >
            <RankingTable
              data={ranking}
              loading={rankLoading}
              onSelectProvider={handleSelectProvider}
              selectedId={selectedId}
            />
          </div>
        </div>

        {/* Right: Detail Panel */}
        {selectedProvider && (
          <div className="w-96 shrink-0">
            <div className="sticky top-6">
              <DetailPanel
                provider={selectedProvider}
                providerDetail={providerDetail}
                creditData={creditData}
                loadingDetail={detailLoading}
                loadingCredit={creditLoading}
                onClose={handleCloseDetail}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
