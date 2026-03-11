'use client';

import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import dynamic from 'next/dynamic';
import SidePanel from '@/components/layout/SidePanel';
import { useApi, useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatBRL, formatNumber, formatPct } from '@/lib/format';
import { Share2, Radio, DollarSign, BarChart3, MapPin, ChevronDown, AlertTriangle, Loader2 } from 'lucide-react';

const MapView = dynamic(() => import('@/components/map/MapView'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center" style={{ background: 'var(--bg-subtle)' }}>
      <div className="overflow-hidden absolute top-0 left-0 right-0" style={{ height: '2px' }}>
        <div className="pulso-progress-bar w-full" />
      </div>
    </div>
  ),
});

// Brazilian states for filter dropdown
const STATES = [
  '', 'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO',
  'MA', 'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR',
  'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
];

// Score to color: green (high opportunity) -> red (low)
function scoreToColor(score: number): [number, number, number, number] {
  const t = Math.max(0, Math.min(1, score / 100));
  // high = green, low = red
  const r = Math.round(239 - t * 205);
  const g = Math.round(68 + t * 129);
  const b = Math.round(68 - t * 34);
  return [r, g, b, 200];
}

function scoreLabel(score: number): string {
  if (score >= 80) return 'Excelente';
  if (score >= 60) return 'Bom';
  if (score >= 40) return 'Moderado';
  if (score >= 20) return 'Baixo';
  return 'Muito baixo';
}

function scoreBadgeColor(score: number): { bg: string; text: string } {
  if (score >= 80) return { bg: 'color-mix(in srgb, var(--success) 15%, transparent)', text: 'var(--success)' };
  if (score >= 60) return { bg: 'color-mix(in srgb, var(--accent) 15%, transparent)', text: 'var(--accent)' };
  if (score >= 40) return { bg: 'color-mix(in srgb, var(--warning) 15%, transparent)', text: 'var(--warning)' };
  return { bg: 'color-mix(in srgb, var(--danger) 15%, transparent)', text: 'var(--danger)' };
}

export default function CompartilhamentoPage() {
  const [stateFilter, setStateFilter] = useState('');
  const [stateDropdownOpen, setStateDropdownOpen] = useState(false);
  const [selectedTower, setSelectedTower] = useState<any | null>(null);
  const deckRef = useRef<{ ScatterplotLayer: any } | null>(null);
  const [deckReady, setDeckReady] = useState(false);

  // Dynamic deck.gl import
  useEffect(() => {
    import('@deck.gl/layers').then((mod) => {
      deckRef.current = { ScatterplotLayer: mod.ScatterplotLayer };
      setDeckReady(true);
    });
  }, []);

  // Fetch opportunities
  const {
    data: opportunities,
    loading: loadingOpportunities,
    error: errorOpportunities,
  } = useApi<any[]>(
    () => api.colocation.opportunities({
      state: stateFilter || undefined,
      min_score: 50,
      limit: 200,
    }),
    [stateFilter]
  );

  // Fetch summary stats
  const {
    data: summary,
    loading: loadingSummary,
  } = useApi<any>(
    () => api.colocation.summary({ state: stateFilter || undefined }),
    [stateFilter]
  );

  // Lazy fetch for tower analysis detail
  const {
    data: analysisData,
    loading: analysisLoading,
    execute: fetchAnalysis,
    reset: resetAnalysis,
  } = useLazyApi<any, number>((id) => api.colocation.analysis(id));

  // When a tower is selected, fetch its detailed analysis
  useEffect(() => {
    if (selectedTower?.id) {
      fetchAnalysis(selectedTower.id);
    } else {
      resetAnalysis();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTower?.id]);

  // Map click handler
  const handleMapClick = useCallback((info: any) => {
    if (info?.object) {
      setSelectedTower(info.object);
    }
  }, []);

  // Build map layers
  const mapLayers = useMemo(() => {
    if (!deckReady || !deckRef.current || !opportunities?.length) return [];
    const { ScatterplotLayer } = deckRef.current;

    const withCoords = opportunities.filter(
      (d: any) => d.latitude != null && d.longitude != null
    );

    if (!withCoords.length) return [];

    return [
      new ScatterplotLayer({
        id: 'colocation-towers',
        data: withCoords,
        getPosition: (d: any) => [d.longitude, d.latitude],
        getFillColor: (d: any) => scoreToColor(d.colocation_score ?? d.score ?? 0),
        getRadius: 5000,
        radiusMinPixels: 4,
        radiusMaxPixels: 14,
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 150],
      }),
    ];
  }, [deckReady, opportunities]);

  // Derived stats from summary
  const totalTowers = summary?.total_towers ?? summary?.total ?? '--';
  const avgScore = summary?.avg_score ?? summary?.average_score ?? null;
  const totalSavings = summary?.total_savings ?? summary?.savings_potential ?? null;

  const isLoading = loadingOpportunities || loadingSummary;

  return (
    <div className="relative flex h-[calc(100vh-56px)] flex-col">
      {/* Loading progress bar */}
      {isLoading && (
        <div className="overflow-hidden absolute top-0 left-0 right-0 z-20" style={{ height: '2px' }}>
          <div className="pulso-progress-bar w-full" />
        </div>
      )}

      {/* Error banner */}
      {errorOpportunities && (
        <div
          className="mx-4 mt-2 flex items-center gap-3 rounded-lg border px-4 py-3"
          style={{
            borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)',
            backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
          }}
        >
          <AlertTriangle size={18} className="shrink-0" style={{ color: 'var(--danger)' }} />
          <p className="text-sm" style={{ color: 'var(--danger)' }}>
            Erro ao carregar dados de compartilhamento. Verifique sua conexão e tente novamente.
          </p>
        </div>
      )}

      {/* Full-screen map */}
      <div className="relative flex-1">
        <MapView
          className="h-full w-full"
          layers={mapLayers}
          onMapClick={handleMapClick}
        />

        {/* Summary stats overlay — top-left */}
        <div className="absolute left-4 top-4 z-10 flex flex-col gap-2" style={{ maxWidth: '280px' }}>
          {/* Title card */}
          <div
            className="rounded-lg p-3"
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            }}
          >
            <div className="flex items-center gap-2 mb-3">
              <Share2 size={16} style={{ color: 'var(--accent)' }} />
              <h1 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Compartilhamento de Torres
              </h1>
            </div>

            {/* State filter */}
            <div className="relative mb-3">
              <button
                onClick={() => setStateDropdownOpen(!stateDropdownOpen)}
                className="flex w-full items-center justify-between rounded-md px-3 py-1.5 text-xs"
                style={{
                  background: 'var(--bg-subtle)',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border)',
                }}
              >
                <span>{stateFilter || 'Todos os estados'}</span>
                <ChevronDown size={14} />
              </button>
              {stateDropdownOpen && (
                <div
                  className="absolute left-0 right-0 top-full mt-1 z-50 max-h-48 overflow-y-auto rounded-md py-1"
                  style={{
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border)',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
                  }}
                >
                  {STATES.map((s) => (
                    <button
                      key={s || '__all'}
                      onClick={() => {
                        setStateFilter(s);
                        setStateDropdownOpen(false);
                      }}
                      className="block w-full px-3 py-1.5 text-left text-xs transition-colors hover:opacity-80"
                      style={{
                        color: s === stateFilter ? 'var(--accent)' : 'var(--text-secondary)',
                        background: s === stateFilter ? 'var(--accent-subtle)' : 'transparent',
                      }}
                    >
                      {s || 'Todos os estados'}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Stats grid */}
            <div className="space-y-2">
              <StatRow
                icon={<Radio size={14} style={{ color: 'var(--accent)' }} />}
                label="Torres analisadas"
                value={isLoading ? '...' : formatNumber(typeof totalTowers === 'number' ? totalTowers : null)}
              />
              <StatRow
                icon={<BarChart3 size={14} style={{ color: 'var(--accent)' }} />}
                label="Score m\u00e9dio"
                value={isLoading ? '...' : avgScore != null ? avgScore.toFixed(1) : '--'}
              />
              <StatRow
                icon={<DollarSign size={14} style={{ color: 'var(--success)' }} />}
                label="Economia potencial"
                value={isLoading ? '...' : formatBRL(totalSavings)}
              />
            </div>
          </div>

          {/* Legend */}
          <div
            className="rounded-lg px-3 py-2"
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            }}
          >
            <p className="mb-1.5 text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
              Score de compartilhamento
            </p>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-2 rounded-full" style={{
                background: 'linear-gradient(to right, rgb(239,68,68), rgb(234,179,8), rgb(34,197,94))',
              }} />
            </div>
            <div className="flex justify-between mt-0.5">
              <span className="text-[9px]" style={{ color: 'var(--text-muted)' }}>Baixo</span>
              <span className="text-[9px]" style={{ color: 'var(--text-muted)' }}>Alto</span>
            </div>
          </div>

          {/* Count badge */}
          {!isLoading && opportunities && (
            <div
              className="rounded-lg px-3 py-1.5 text-center text-xs"
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                color: 'var(--text-muted)',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              }}
            >
              <MapPin size={12} className="inline mr-1" style={{ color: 'var(--accent)' }} />
              {opportunities.length} oportunidades no mapa
            </div>
          )}
        </div>
      </div>

      {/* Side Panel for tower details */}
      <SidePanel
        open={!!selectedTower}
        onClose={() => setSelectedTower(null)}
        title={selectedTower?.name || selectedTower?.station_name || 'Torre'}
        subtitle={selectedTower?.operator || selectedTower?.provider_name || ''}
      >
        {analysisLoading && (
          <div className="flex flex-col items-center gap-3 py-8">
            <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent)' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Carregando an\u00e1lise...</p>
          </div>
        )}

        {!analysisLoading && selectedTower && (
          <div className="space-y-4">
            {/* Colocation score */}
            <div
              className="rounded-lg p-4"
              style={{
                backgroundColor: scoreBadgeColor(
                  analysisData?.colocation_score ?? selectedTower?.colocation_score ?? selectedTower?.score ?? 0
                ).bg,
              }}
            >
              <p className="text-xs font-medium" style={{
                color: scoreBadgeColor(
                  analysisData?.colocation_score ?? selectedTower?.colocation_score ?? selectedTower?.score ?? 0
                ).text,
              }}>
                Score de Compartilhamento
              </p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-3xl font-bold" style={{
                  color: scoreBadgeColor(
                    analysisData?.colocation_score ?? selectedTower?.colocation_score ?? selectedTower?.score ?? 0
                  ).text,
                }}>
                  {(analysisData?.colocation_score ?? selectedTower?.colocation_score ?? selectedTower?.score ?? 0).toFixed(1)}
                </span>
                <span className="text-xs font-medium" style={{
                  color: scoreBadgeColor(
                    analysisData?.colocation_score ?? selectedTower?.colocation_score ?? selectedTower?.score ?? 0
                  ).text,
                }}>
                  / 100 &mdash; {scoreLabel(analysisData?.colocation_score ?? selectedTower?.colocation_score ?? selectedTower?.score ?? 0)}
                </span>
              </div>
            </div>

            {/* Sub-scores */}
            {(analysisData?.sub_scores || selectedTower?.sub_scores) && (
              <div className="space-y-2">
                <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Sub-scores</p>
                <SubScoreBar
                  label="Demanda n\u00e3o atendida"
                  value={(analysisData?.sub_scores ?? selectedTower?.sub_scores)?.underserved ?? 0}
                />
                <SubScoreBar
                  label="Densidade"
                  value={(analysisData?.sub_scores ?? selectedTower?.sub_scores)?.density ?? 0}
                />
                <SubScoreBar
                  label="Lacuna de cobertura"
                  value={(analysisData?.sub_scores ?? selectedTower?.sub_scores)?.gap ?? 0}
                />
                <SubScoreBar
                  label="Espectro"
                  value={(analysisData?.sub_scores ?? selectedTower?.sub_scores)?.spectrum ?? 0}
                />
              </div>
            )}

            {/* CAPEX Savings */}
            {(analysisData?.capex_savings ?? analysisData?.estimated_savings ?? selectedTower?.capex_savings ?? selectedTower?.estimated_savings) != null && (
              <div
                className="rounded-lg p-3"
                style={{ backgroundColor: 'color-mix(in srgb, var(--success) 10%, transparent)' }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <DollarSign size={14} style={{ color: 'var(--success)' }} />
                  <span className="text-xs font-semibold" style={{ color: 'var(--success)' }}>
                    Economia estimada (CAPEX)
                  </span>
                </div>
                <p className="text-xl font-bold" style={{ color: 'var(--success)' }}>
                  {formatBRL(
                    analysisData?.capex_savings ?? analysisData?.estimated_savings ??
                    selectedTower?.capex_savings ?? selectedTower?.estimated_savings
                  )}
                </p>
              </div>
            )}

            {/* Tower info */}
            <div className="space-y-2">
              <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Informa\u00e7\u00f5es da torre</p>
              <DetailRow
                label="Operador"
                value={analysisData?.operator ?? selectedTower?.operator ?? selectedTower?.provider_name ?? '--'}
              />
              <DetailRow
                label="Tecnologia"
                value={analysisData?.technology ?? selectedTower?.technology ?? '--'}
              />
              <DetailRow
                label="Latitude"
                value={(selectedTower?.latitude ?? analysisData?.latitude)?.toFixed(5) ?? '--'}
              />
              <DetailRow
                label="Longitude"
                value={(selectedTower?.longitude ?? analysisData?.longitude)?.toFixed(5) ?? '--'}
              />
              {(analysisData?.height_m ?? selectedTower?.height_m) != null && (
                <DetailRow
                  label="Altura"
                  value={`${analysisData?.height_m ?? selectedTower?.height_m}m`}
                />
              )}
              {(analysisData?.municipality ?? selectedTower?.municipality) && (
                <DetailRow
                  label="Munic\u00edpio"
                  value={analysisData?.municipality ?? selectedTower?.municipality ?? '--'}
                />
              )}
            </div>

            {/* Nearby towers */}
            {analysisData?.nearby_towers && analysisData.nearby_towers.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
                  Torres pr\u00f3ximas ({analysisData.nearby_towers.length})
                </p>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {analysisData.nearby_towers.map((tower: any, idx: number) => (
                    <div
                      key={tower.id ?? idx}
                      className="flex items-center justify-between rounded-md px-3 py-2 text-xs"
                      style={{ backgroundColor: 'var(--bg-subtle)' }}
                    >
                      <div>
                        <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
                          {tower.operator ?? tower.provider_name ?? `Torre ${idx + 1}`}
                        </span>
                        {tower.distance_km != null && (
                          <span className="ml-2" style={{ color: 'var(--text-muted)' }}>
                            {tower.distance_km.toFixed(1)} km
                          </span>
                        )}
                      </div>
                      {tower.technology && (
                        <span
                          className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                          style={{
                            backgroundColor: 'var(--accent-subtle)',
                            color: 'var(--accent)',
                          }}
                        >
                          {tower.technology}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Provider diversity */}
            {analysisData?.provider_diversity && analysisData.provider_diversity.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
                  Diversidade de provedores
                </p>
                <div className="space-y-1">
                  {analysisData.provider_diversity.map((provider: any, idx: number) => (
                    <div
                      key={provider.name ?? idx}
                      className="flex items-center justify-between rounded-md px-3 py-2 text-xs"
                      style={{ backgroundColor: 'var(--bg-subtle)' }}
                    >
                      <span style={{ color: 'var(--text-primary)' }}>
                        {provider.name ?? provider.provider_name ?? `Provedor ${idx + 1}`}
                      </span>
                      <span className="font-medium" style={{ color: 'var(--accent)' }}>
                        {provider.share != null ? formatPct(provider.share) : provider.count ?? '--'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Providers on tower (alternative field name) */}
            {analysisData?.providers && analysisData.providers.length > 0 && !analysisData.provider_diversity && (
              <div className="space-y-2">
                <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
                  Provedores na torre
                </p>
                <div className="flex flex-wrap gap-1">
                  {analysisData.providers.map((name: string, idx: number) => (
                    <span
                      key={idx}
                      className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                      style={{
                        backgroundColor: 'var(--accent-subtle)',
                        color: 'var(--accent)',
                      }}
                    >
                      {name}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </SidePanel>
    </div>
  );
}

// ── Helper components ──────────────────────────────────────────────────────

function StatRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2">
      {icon}
      <div className="flex-1 flex items-center justify-between">
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
        <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{value}</span>
      </div>
    </div>
  );
}

function SubScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
        <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
          {value.toFixed(1)}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ backgroundColor: 'var(--bg-subtle)' }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${Math.min(value, 100)}%`, backgroundColor: 'var(--accent)' }}
        />
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="flex items-center justify-between rounded-lg px-3 py-2"
      style={{ backgroundColor: 'var(--bg-subtle)' }}
    >
      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{value}</span>
    </div>
  );
}
