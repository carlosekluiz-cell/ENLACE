'use client';

import { useState, useCallback } from 'react';
import { useApi, useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatNumber, formatCompact, formatPct, formatDecimal } from '@/lib/format';
import {
  CreditCard,
  TrendingUp,
  Shield,
  BarChart3,
  Building2,
  Users,
  Filter,
  ChevronDown,
  AlertTriangle,
  RefreshCw,
  X,
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

const RATINGS = ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'CCC'] as const;

const RATING_OPTIONS = [
  { value: '', label: 'Todos os ratings' },
  ...RATINGS.map((r) => ({ value: r, label: r })),
];

type RatingTier = (typeof RATINGS)[number];

function ratingColor(rating: string): string {
  switch (rating) {
    case 'AAA':
    case 'AA':
      return '#15803d'; // dark green
    case 'A':
    case 'BBB':
      return '#22c55e'; // green
    case 'BB':
      return '#eab308'; // yellow
    case 'B':
    case 'CCC':
      return '#ef4444'; // red
    default:
      return 'var(--text-muted)';
  }
}

function ratingBg(rating: string): string {
  switch (rating) {
    case 'AAA':
    case 'AA':
      return 'rgba(21, 128, 61, 0.15)';
    case 'A':
    case 'BBB':
      return 'rgba(34, 197, 94, 0.15)';
    case 'BB':
      return 'rgba(234, 179, 8, 0.15)';
    case 'B':
    case 'CCC':
      return 'rgba(239, 68, 68, 0.15)';
    default:
      return 'var(--bg-subtle)';
  }
}

function factorBarColor(value: number): string {
  if (value > 70) return '#22c55e';
  if (value >= 40) return '#eab308';
  return '#ef4444';
}

interface DistributionItem {
  rating: string;
  count: number;
  percentage: number;
}

interface RankingItem {
  provider_id: number;
  provider_name: string;
  rating: string;
  score: number;
  total_subscribers: number;
  probability_of_default?: number;
  states: string[];
}

interface CreditFactors {
  revenue_stability: number;
  growth_trajectory: number;
  market_position: number;
  infrastructure_quality: number;
  regulatory_compliance: number;
  subscriber_concentration: number;
}

interface CreditDetail {
  provider_id: number;
  provider_name?: string;
  rating: string;
  composite_score: number;
  probability_of_default: number;
  factors: CreditFactors;
}

const FACTOR_LABELS: Record<keyof CreditFactors, string> = {
  revenue_stability: 'Estabilidade de Receita',
  growth_trajectory: 'Trajetoria de Crescimento',
  market_position: 'Posicao de Mercado',
  infrastructure_quality: 'Qualidade de Infraestrutura',
  regulatory_compliance: 'Conformidade Regulatoria',
  subscriber_concentration: 'Concentracao Geografica',
};

const FACTOR_ICONS: Record<keyof CreditFactors, React.ReactNode> = {
  revenue_stability: <BarChart3 size={14} />,
  growth_trajectory: <TrendingUp size={14} />,
  market_position: <Building2 size={14} />,
  infrastructure_quality: <Shield size={14} />,
  regulatory_compliance: <CreditCard size={14} />,
  subscriber_concentration: <Users size={14} />,
};

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
// Loading Spinner
// ---------------------------------------------------------------------------

function Spinner() {
  return (
    <div
      className="h-4 w-4 animate-spin rounded-full border-2 border-current"
      style={{ borderTopColor: 'transparent' }}
    />
  );
}

// ---------------------------------------------------------------------------
// Distribution Cards
// ---------------------------------------------------------------------------

function DistributionCards({ data, loading }: { data: DistributionItem[] | null; loading: boolean }) {
  // Build a map for quick lookup
  const byRating = new Map<string, DistributionItem>();
  data?.forEach((d) => byRating.set(d.rating, d));

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
      {RATINGS.map((rating) => {
        const item = byRating.get(rating);
        const count = item?.count ?? 0;
        const pct = item?.percentage ?? 0;

        return (
          <div
            key={rating}
            className="rounded-lg p-3 text-center transition-all"
            style={{
              backgroundColor: ratingBg(rating),
              border: `1px solid ${ratingColor(rating)}30`,
            }}
          >
            <div
              className="text-xl font-bold"
              style={{ color: ratingColor(rating), fontVariantNumeric: 'tabular-nums' }}
            >
              {rating}
            </div>
            {loading ? (
              <div className="mt-1 flex justify-center">
                <Spinner />
              </div>
            ) : (
              <>
                <div
                  className="mt-1 text-lg font-semibold"
                  style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}
                >
                  {formatNumber(count)}
                </div>
                <div
                  className="text-xs"
                  style={{ color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}
                >
                  {formatPct(pct)}
                </div>
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rating Badge
// ---------------------------------------------------------------------------

function RatingBadge({ rating, size = 'sm' }: { rating: string; size?: 'sm' | 'lg' }) {
  const isLarge = size === 'lg';
  return (
    <span
      className="inline-flex items-center justify-center rounded-md font-bold"
      style={{
        width: isLarge ? '64px' : '40px',
        height: isLarge ? '64px' : '28px',
        fontSize: isLarge ? '24px' : '12px',
        color: ratingColor(rating),
        backgroundColor: ratingBg(rating),
        border: `1.5px solid ${ratingColor(rating)}50`,
      }}
    >
      {rating}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Factor Bar
// ---------------------------------------------------------------------------

function FactorBar({
  factorKey,
  value,
}: {
  factorKey: keyof CreditFactors;
  value: number;
}) {
  const normalizedValue = Math.min(Math.max(value, 0), 100);
  const color = factorBarColor(normalizedValue);

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span style={{ color: 'var(--text-muted)' }}>{FACTOR_ICONS[factorKey]}</span>
          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            {FACTOR_LABELS[factorKey]}
          </span>
        </div>
        <span
          className="text-sm font-semibold"
          style={{ color, fontVariantNumeric: 'tabular-nums' }}
        >
          {formatDecimal(normalizedValue, 1)}
        </span>
      </div>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full"
        style={{ backgroundColor: 'var(--bg-subtle)' }}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${normalizedValue}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail Panel
// ---------------------------------------------------------------------------

function DetailPanel({
  detail,
  loading,
  onClose,
  onRecompute,
  recomputing,
}: {
  detail: CreditDetail | null;
  loading: boolean;
  onClose: () => void;
  onRecompute: () => void;
  recomputing: boolean;
}) {
  if (!detail && !loading) return null;

  return (
    <div
      className="w-full shrink-0 lg:w-96"
    >
      <div
        className="pulso-card sticky top-6"
      >
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Detalhe do Credit Score
          </h3>
          <button
            onClick={onClose}
            className="rounded p-1 transition-colors"
            style={{ color: 'var(--text-muted)' }}
            aria-label="Fechar"
          >
            <X size={16} />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
              <Spinner />
              Carregando...
            </div>
          </div>
        ) : detail ? (
          <div className="space-y-5">
            {/* Rating + Score + PD header */}
            <div className="flex items-center gap-4">
              <RatingBadge rating={detail.rating} size="lg" />
              <div className="flex-1">
                {detail.provider_name && (
                  <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    {detail.provider_name}
                  </p>
                )}
                <div className="mt-1 flex items-baseline gap-3">
                  <div>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Score</span>
                    <p
                      className="text-2xl font-bold"
                      style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}
                    >
                      {formatDecimal(detail.composite_score, 1)}
                      <span className="text-sm font-normal" style={{ color: 'var(--text-muted)' }}>/100</span>
                    </p>
                  </div>
                  <div>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>PD</span>
                    <p
                      className="text-lg font-semibold"
                      style={{
                        color: detail.probability_of_default > 10 ? 'var(--danger)' : detail.probability_of_default > 5 ? 'var(--warning)' : 'var(--success)',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {formatPct(detail.probability_of_default)}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Factor breakdown */}
            <div>
              <h4
                className="mb-3 text-xs font-semibold uppercase tracking-wider"
                style={{ color: 'var(--text-muted)' }}
              >
                Fatores de Credito
              </h4>
              <div className="space-y-3">
                {detail.factors &&
                  (Object.keys(FACTOR_LABELS) as Array<keyof CreditFactors>).map((key) => (
                    <FactorBar
                      key={key}
                      factorKey={key}
                      value={detail.factors[key] ?? 0}
                    />
                  ))}
              </div>
            </div>

            {/* Recompute button */}
            <button
              onClick={onRecompute}
              disabled={recomputing}
              className="pulso-btn-primary flex w-full items-center justify-center gap-2"
            >
              <RefreshCw size={14} className={recomputing ? 'animate-spin' : ''} />
              {recomputing ? 'Recalculando...' : 'Recalcular'}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function CreditoPage() {
  // Filters
  const [stateFilter, setStateFilter] = useState('');
  const [ratingFilter, setRatingFilter] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Selected provider
  const [selectedProviderId, setSelectedProviderId] = useState<number | null>(null);

  // Distribution
  const { data: distribution, loading: distLoading, error: distError } = useApi<DistributionItem[]>(
    () => api.credit.distribution(),
    []
  );

  // Ranking
  const {
    data: ranking,
    loading: rankLoading,
    error: rankError,
    refetch: refetchRanking,
  } = useApi<RankingItem[]>(
    () =>
      api.credit.ranking({
        state: stateFilter || undefined,
        min_rating: ratingFilter || undefined,
        limit: 100,
      }),
    [stateFilter, ratingFilter]
  );

  // Credit detail (lazy)
  const {
    data: creditDetail,
    loading: detailLoading,
    error: detailError,
    execute: fetchDetail,
    reset: resetDetail,
  } = useLazyApi<CreditDetail, number>(
    useCallback((id: number) => api.credit.score(id), [])
  );

  // Recompute (lazy)
  const {
    loading: recomputing,
    execute: triggerRecompute,
  } = useLazyApi<any, number>(
    useCallback((id: number) => api.credit.compute(id), [])
  );

  const handleRowClick = (item: RankingItem) => {
    setSelectedProviderId(item.provider_id);
    fetchDetail(item.provider_id);
  };

  const handleCloseDetail = () => {
    setSelectedProviderId(null);
    resetDetail();
  };

  const handleRecompute = async () => {
    if (selectedProviderId == null) return;
    await triggerRecompute(selectedProviderId);
    // Refresh the detail and ranking after recompute
    fetchDetail(selectedProviderId);
    refetchRanking();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Page header */}
      <div>
        <h1
          className="flex items-center gap-3 text-2xl font-bold"
          style={{ color: 'var(--text-primary)' }}
        >
          <CreditCard size={28} style={{ color: 'var(--accent)' }} />
          Credit Scoring ISP
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Analise de credito e solvencia dos provedores de internet brasileiros
        </p>
      </div>

      {/* Errors */}
      {distError && <ErrorBanner message={`Erro na distribuicao: ${distError}`} />}
      {rankError && <ErrorBanner message={`Erro no ranking: ${rankError}`} />}
      {detailError && <ErrorBanner message={`Erro no detalhe: ${detailError}`} />}

      {/* Rating Distribution */}
      <div>
        <h2
          className="mb-3 text-sm font-semibold uppercase tracking-wider"
          style={{ color: 'var(--text-muted)' }}
        >
          Distribuicao de Ratings
        </h2>
        <DistributionCards data={distribution} loading={distLoading} />
      </div>

      {/* Filters */}
      <div className="pulso-card">
        <button
          onClick={() => setFiltersOpen((prev) => !prev)}
          className="flex w-full items-center justify-between"
        >
          <div className="flex items-center gap-2">
            <Filter size={16} style={{ color: 'var(--accent)' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              Filtros
            </span>
            {(stateFilter || ratingFilter) && (
              <span
                className="rounded px-1.5 py-0.5 text-[10px] font-bold"
                style={{ background: 'var(--accent)', color: '#fff' }}
              >
                {[stateFilter, ratingFilter].filter(Boolean).length}
              </span>
            )}
          </div>
          <ChevronDown
            size={16}
            style={{
              color: 'var(--text-muted)',
              transform: filtersOpen ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.2s',
            }}
          />
        </button>

        {filtersOpen && (
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <label
                className="mb-1 block text-xs font-medium"
                style={{ color: 'var(--text-secondary)' }}
              >
                Estado
              </label>
              <select
                className="pulso-input w-full"
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value)}
              >
                {BRAZILIAN_STATES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.value ? `${s.value} - ${s.label}` : s.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                className="mb-1 block text-xs font-medium"
                style={{ color: 'var(--text-secondary)' }}
              >
                Rating Minimo
              </label>
              <select
                className="pulso-input w-full"
                value={ratingFilter}
                onChange={(e) => setRatingFilter(e.target.value)}
              >
                {RATING_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <button
                onClick={() => {
                  setStateFilter('');
                  setRatingFilter('');
                }}
                className="text-sm font-medium"
                style={{ color: 'var(--accent)' }}
              >
                Limpar filtros
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Main content: table + detail panel */}
      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Ranking table */}
        <div className="flex-1 min-w-0">
          <h2
            className="mb-3 text-sm font-semibold uppercase tracking-wider"
            style={{ color: 'var(--text-muted)' }}
          >
            Ranking de Credito
            {ranking && (
              <span className="ml-2 font-normal normal-case" style={{ color: 'var(--text-muted)' }}>
                ({ranking.length} provedor{ranking.length !== 1 ? 'es' : ''})
              </span>
            )}
          </h2>

          <div
            className="overflow-hidden rounded-lg border"
            style={{ borderColor: 'var(--border)' }}
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ backgroundColor: 'var(--bg-subtle)' }}>
                    <th
                      className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      #
                    </th>
                    <th
                      className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      Provedor
                    </th>
                    <th
                      className="px-3 py-2.5 text-center text-xs font-semibold uppercase tracking-wider"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      Rating
                    </th>
                    <th
                      className="px-3 py-2.5 text-right text-xs font-semibold uppercase tracking-wider"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      Score
                    </th>
                    <th
                      className="px-3 py-2.5 text-right text-xs font-semibold uppercase tracking-wider"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      PD%
                    </th>
                    <th
                      className="px-3 py-2.5 text-right text-xs font-semibold uppercase tracking-wider"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      Assinantes
                    </th>
                    <th
                      className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      Estados
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rankLoading ? (
                    <tr>
                      <td colSpan={7} className="px-3 py-12 text-center">
                        <div className="flex items-center justify-center gap-2" style={{ color: 'var(--text-muted)' }}>
                          <Spinner />
                          Carregando ranking...
                        </div>
                      </td>
                    </tr>
                  ) : !ranking || ranking.length === 0 ? (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-3 py-12 text-center text-sm"
                        style={{ color: 'var(--text-muted)' }}
                      >
                        Nenhum provedor encontrado com os filtros selecionados.
                      </td>
                    </tr>
                  ) : (
                    ranking.map((item, index) => {
                      const isSelected = selectedProviderId === item.provider_id;
                      return (
                        <tr
                          key={item.provider_id}
                          onClick={() => handleRowClick(item)}
                          className="cursor-pointer transition-colors"
                          style={{
                            backgroundColor: isSelected
                              ? 'var(--accent-subtle)'
                              : index % 2 === 0
                                ? 'transparent'
                                : 'var(--bg-subtle)',
                            borderBottom: '1px solid var(--border)',
                          }}
                          onMouseEnter={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.backgroundColor = 'var(--bg-subtle)';
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.backgroundColor =
                                index % 2 === 0 ? 'transparent' : 'var(--bg-subtle)';
                            }
                          }}
                        >
                          <td
                            className="px-3 py-2.5 text-sm"
                            style={{ color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}
                          >
                            {index + 1}
                          </td>
                          <td className="px-3 py-2.5">
                            <span
                              className="text-sm font-medium"
                              style={{ color: 'var(--text-primary)' }}
                            >
                              {item.provider_name}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <RatingBadge rating={item.rating} />
                          </td>
                          <td
                            className="px-3 py-2.5 text-right text-sm font-medium"
                            style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}
                          >
                            {formatDecimal(item.score, 1)}
                          </td>
                          <td
                            className="px-3 py-2.5 text-right text-sm"
                            style={{
                              fontVariantNumeric: 'tabular-nums',
                              color:
                                (item.probability_of_default ?? 0) > 10
                                  ? 'var(--danger)'
                                  : (item.probability_of_default ?? 0) > 5
                                    ? 'var(--warning)'
                                    : 'var(--success)',
                            }}
                          >
                            {item.probability_of_default != null
                              ? formatPct(item.probability_of_default)
                              : '--'}
                          </td>
                          <td
                            className="px-3 py-2.5 text-right text-sm"
                            style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}
                          >
                            {formatCompact(item.total_subscribers)}
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="flex flex-wrap gap-1">
                              {(item.states ?? []).slice(0, 5).map((st) => (
                                <span
                                  key={st}
                                  className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                                  style={{
                                    backgroundColor: 'var(--bg-subtle)',
                                    color: 'var(--text-secondary)',
                                    border: '1px solid var(--border)',
                                  }}
                                >
                                  {st}
                                </span>
                              ))}
                              {(item.states ?? []).length > 5 && (
                                <span
                                  className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                                  style={{ color: 'var(--text-muted)' }}
                                >
                                  +{item.states.length - 5}
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Detail Panel */}
        {(selectedProviderId != null) && (
          <DetailPanel
            detail={creditDetail}
            loading={detailLoading}
            onClose={handleCloseDetail}
            onRecompute={handleRecompute}
            recomputing={recomputing}
          />
        )}
      </div>
    </div>
  );
}
