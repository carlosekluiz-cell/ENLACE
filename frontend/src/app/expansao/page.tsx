'use client';

import { useState, useMemo, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import DataTable from '@/components/dashboard/DataTable';
import SimpleChart from '@/components/charts/SimpleChart';
import { useApi } from '@/hooks/useApi';
import { api, computeSatelliteAnalysis } from '@/lib/api';
import type { SatelliteComputeResult } from '@/lib/api';
import type { OpportunityScore, BaseStationPoint, MunicipalityFusion } from '@/lib/types';
import { TrendingUp, Target, BarChart3, X, AlertTriangle, Map as MapIcon, Radio, Satellite, Loader2, Building2, Landmark, FileText, Zap } from 'lucide-react';

const MapView = dynamic(() => import('@/components/map/MapView'), { ssr: false });

const columns = [
  {
    key: 'name',
    label: 'Município',
    sortable: true,
    render: (value: string, row: OpportunityScore) => (
      <div>
        <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{value}</span>
        <span className="ml-2 text-xs" style={{ color: 'var(--text-muted)' }}>{row.state_abbrev}</span>
      </div>
    ),
  },
  {
    key: 'composite_score',
    label: 'Pontuação',
    sortable: true,
    render: (value: number) => (
      <div className="flex items-center gap-2">
        <div className="h-2 w-16 overflow-hidden rounded-full" style={{ backgroundColor: 'var(--bg-subtle)' }}>
          <div
            className="h-full rounded-full"
            style={{ width: `${value ?? 0}%`, backgroundColor: 'var(--accent)' }}
          />
        </div>
        <span className="text-sm font-semibold" style={{ color: 'var(--accent)' }}>
          {(value ?? 0).toFixed(1)}
        </span>
      </div>
    ),
  },
  {
    key: 'population',
    label: 'População',
    sortable: true,
    render: (value: number) => (value ?? 0).toLocaleString('pt-BR'),
  },
  {
    key: 'households',
    label: 'Domicílios',
    sortable: true,
    render: (value: number) => (value ?? 0).toLocaleString('pt-BR'),
  },
  {
    key: 'confidence',
    label: 'Confiança',
    sortable: true,
    render: (value: number) => (
      <span
        style={{
          color:
            (value ?? 0) > 0.9
              ? 'var(--success)'
              : (value ?? 0) > 0.7
                ? 'var(--warning)'
                : 'var(--danger)',
        }}
      >
        {((value ?? 0) * 100).toFixed(0)}%
      </span>
    ),
  },
];

// Color scale: low scores are cool blue, high scores are warm orange/red
function scoreToColor(score: number): [number, number, number, number] {
  const t = Math.max(0, Math.min(1, (score - 60) / 20)); // normalize 60-80 to 0-1
  const r = Math.round(30 + t * 225);
  const g = Math.round(130 - t * 50);
  const b = Math.round(220 - t * 180);
  return [r, g, b, 200];
}

// Technology to color mapping for base stations
function techToColor(tech: string): [number, number, number, number] {
  switch (tech) {
    case '5G': return [0, 200, 120, 180];
    case '4G': return [50, 140, 255, 160];
    case '3G': return [180, 120, 50, 140];
    default:   return [128, 128, 128, 120];
  }
}

export default function OpportunitiesPage() {
  const [selectedRow, setSelectedRow] = useState<OpportunityScore | null>(null);
  const [showTowers, setShowTowers] = useState(true);
  const [deckLayers, setDeckLayers] = useState<{ ColumnLayer: any; ScatterplotLayer: any } | null>(null);
  const [satData, setSatData] = useState<SatelliteComputeResult | null>(null);
  const [satLoading, setSatLoading] = useState(false);
  const [satError, setSatError] = useState<string | null>(null);
  const [fusionData, setFusionData] = useState<MunicipalityFusion | null>(null);
  const [fusionLoading, setFusionLoading] = useState(false);

  const handleSatelliteAnalysis = useCallback(async (code: string) => {
    setSatLoading(true);
    setSatError(null);
    setSatData(null);
    try {
      const result = await computeSatelliteAnalysis(code);
      if (result.status === 'computing') {
        // Poll every 10s until ready
        const poll = setInterval(async () => {
          try {
            const r = await computeSatelliteAnalysis(code);
            if (r.status !== 'computing') {
              clearInterval(poll);
              setSatData(r);
              setSatLoading(false);
            }
          } catch { clearInterval(poll); setSatLoading(false); }
        }, 10000);
      } else {
        setSatData(result);
        setSatLoading(false);
      }
    } catch (e: any) {
      setSatError(e.message || 'Erro ao computar análise satelital');
      setSatLoading(false);
    }
  }, []);

  // Clear satellite data when switching rows + fetch fusion data
  useEffect(() => {
    setSatData(null);
    setSatError(null);
    setSatLoading(false);
    setFusionData(null);
    if (selectedRow?.municipality_id) {
      setFusionLoading(true);
      api.intelligence.fusion(selectedRow.municipality_id)
        .then(setFusionData)
        .catch(() => setFusionData(null))
        .finally(() => setFusionLoading(false));
    }
  }, [selectedRow?.municipality_code, selectedRow?.municipality_id]);

  const {
    data: opportunities,
    loading,
    error,
  } = useApi(() => api.opportunities.top({ limit: '5570', min_score: '0' }), []);

  const {
    data: baseStations,
    loading: loadingStations,
  } = useApi(() => api.opportunities.baseStations({ limit: '2000' }), []);

  // Dynamically import deck.gl layer classes (client-side only)
  useEffect(() => {
    import('@deck.gl/layers').then((mod) => {
      setDeckLayers({
        ColumnLayer: mod.ColumnLayer,
        ScatterplotLayer: mod.ScatterplotLayer,
      });
    }).catch(() => {
      // deck.gl not available; map will render without custom layers
    });
  }, []);

  const mapLayers = useMemo(() => {
    if (!deckLayers) return [];
    const { ColumnLayer, ScatterplotLayer } = deckLayers;
    const layers: any[] = [];

    // 3D column layer for opportunity scores
    if (opportunities && opportunities.length > 0) {
      const withCoords = opportunities.filter((o) => o.latitude != null && o.longitude != null);
      if (withCoords.length > 0) {
        layers.push(
          new ColumnLayer({
            id: 'opportunity-columns',
            data: withCoords,
            diskResolution: 12,
            radius: 15000,
            extruded: true,
            elevationScale: 1500,
            getPosition: (d: OpportunityScore) => [d.longitude!, d.latitude!],
            getFillColor: (d: OpportunityScore) => scoreToColor(d.composite_score ?? 0),
            getElevation: (d: OpportunityScore) => d.composite_score ?? 0,
            pickable: true,
            autoHighlight: true,
            highlightColor: [255, 255, 255, 100],
          })
        );
      }
    }

    // Base stations scatter layer
    if (showTowers && baseStations && baseStations.length > 0) {
      layers.push(
        new ScatterplotLayer({
          id: 'base-stations',
          data: baseStations,
          getPosition: (d: BaseStationPoint) => [d.longitude, d.latitude],
          getFillColor: (d: BaseStationPoint) => techToColor(d.technology),
          getRadius: 3000,
          radiusMinPixels: 2,
          radiusMaxPixels: 8,
          pickable: true,
          autoHighlight: true,
          highlightColor: [255, 255, 255, 150],
        })
      );
    }

    return layers;
  }, [deckLayers, opportunities, baseStations, showTowers]);

  const topScore =
    opportunities && opportunities.length > 0 && opportunities[0].composite_score != null
      ? opportunities[0].composite_score.toFixed(1)
      : '--';

  const topMunicipality =
    opportunities && opportunities.length > 0
      ? opportunities[0].name
      : undefined;

  const avgScore =
    opportunities && opportunities.length > 0
      ? (
          opportunities.reduce((s, o) => s + (o.composite_score ?? 0), 0) /
          opportunities.length
        ).toFixed(1)
      : '--';

  const municipalityCount =
    opportunities && opportunities.length > 0
      ? `${opportunities.length} municípios`
      : undefined;

  const totalPopulation =
    opportunities && opportunities.length > 0
      ? opportunities.reduce((s, o) => s + (o.population ?? 0), 0)
      : 0;

  const chartData =
    opportunities && opportunities.length > 0
      ? opportunities.slice(0, 10).map((o) => ({
          name: (o.name ?? '').substring(0, 12),
          score: o.composite_score ?? 0,
          demanda: o.sub_scores?.demand ?? 0,
        }))
      : [];

  return (
    <div className="space-y-6 p-6">
      {/* Error banner */}
      {error && (
        <div
          className="flex items-center gap-3 rounded-lg border px-4 py-3"
          style={{
            borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)',
            backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
          }}
        >
          <AlertTriangle size={18} className="shrink-0" style={{ color: 'var(--danger)' }} />
          <p className="text-sm" style={{ color: 'var(--danger)' }}>
            Erro ao carregar dados. Verifique sua conexão e tente novamente.
          </p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Maior Pontuação</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {loading ? 'Carregando...' : topScore}
              </p>
              {topMunicipality && (
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{topMunicipality}</p>
              )}
            </div>
            <TrendingUp size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Pontuação Média</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {loading ? 'Carregando...' : avgScore}
              </p>
              {municipalityCount && (
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{municipalityCount}</p>
              )}
            </div>
            <Target size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>População Total</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {loading ? 'Carregando...' : totalPopulation.toLocaleString('pt-BR')}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Habitantes nos municípios analisados</p>
            </div>
            <BarChart3 size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
      </div>

      {/* Chart */}
      <SimpleChart
        data={chartData}
        type="bar"
        xKey="name"
        yKeys={['score', 'demanda']}
        title="Top 10 Oportunidades: Score vs Demanda"
        height={250}
        loading={loading}
      />

      {/* 3D Map */}
      <div className="pulso-card overflow-hidden p-0">
        <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center gap-2">
            <MapIcon size={16} style={{ color: 'var(--accent)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Mapa 3D de Oportunidades
            </h2>
            {!loading && opportunities && (
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                {opportunities.filter((o) => o.latitude != null).length} municípios mapeados
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {/* Tower toggle */}
            <button
              onClick={() => setShowTowers((v) => !v)}
              className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-colors"
              style={{
                background: showTowers ? 'var(--accent-subtle)' : 'var(--bg-subtle)',
                color: showTowers ? 'var(--accent)' : 'var(--text-muted)',
                border: `1px solid ${showTowers ? 'var(--accent)' : 'var(--border)'}`,
              }}
              aria-label="Alternar torres base"
            >
              <Radio size={12} />
              Torres ({loadingStations ? '...' : (baseStations?.length ?? 0)})
            </button>
            {/* Legend */}
            <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-muted)' }}>
              <span className="flex items-center gap-1">
                <span className="inline-block h-3 w-3 rounded" style={{ background: 'rgb(30, 130, 220)' }} />
                Score baixo
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-3 w-3 rounded" style={{ background: 'rgb(255, 80, 40)' }} />
                Score alto
              </span>
              {showTowers && (
                <>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'rgb(0, 200, 120)' }} />
                    5G
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'rgb(50, 140, 255)' }} />
                    4G
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'rgb(180, 120, 50)' }} />
                    3G
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
        <MapView
          layers={mapLayers}
          className="h-[480px]"
          onMapClick={(info: any) => {
            if (info?.object && 'composite_score' in info.object) {
              setSelectedRow(info.object as OpportunityScore);
            }
          }}
        />
      </div>

      {/* Table */}
      <div className="flex gap-6">
        <div className="flex-1">
          <h2 className="mb-4 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
            Scoring de Oportunidades
          </h2>
          <DataTable
            columns={columns}
            data={opportunities || []}
            loading={loading}
            searchable
            searchKeys={['name', 'state_abbrev']}
            onRowClick={(row) => setSelectedRow(row)}
            emptyMessage="Nenhuma oportunidade encontrada"
          />
        </div>

        {/* Detail panel */}
        {selectedRow && (
          <div className="w-80 shrink-0">
            <div className="pulso-card sticky top-6">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  Detalhes
                </h3>
                <button
                  onClick={() => setSelectedRow(null)}
                  className="hover:opacity-80"
                  style={{ color: 'var(--text-secondary)' }}
                  aria-label="Fechar detalhes"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="space-y-3">
                <div>
                  <h4 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                    {selectedRow.name}
                  </h4>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {selectedRow.state_abbrev} - Cód. {selectedRow.municipality_code}
                  </p>
                </div>

                <div
                  className="rounded-lg p-3"
                  style={{ backgroundColor: 'var(--accent-subtle)' }}
                >
                  <p className="text-xs font-medium" style={{ color: 'var(--accent)' }}>Score Composto</p>
                  <p className="text-2xl font-bold" style={{ color: 'var(--accent)' }}>
                    {(selectedRow.composite_score ?? 0).toFixed(1)}
                  </p>
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    Confiança: {((selectedRow.confidence ?? 0) * 100).toFixed(0)}%
                  </p>
                </div>

                <div className="space-y-2">
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Sub-scores</p>
                  <SubScoreBar label="Demanda" value={selectedRow.sub_scores?.demand ?? 0} />
                  <SubScoreBar label="Concorrência" value={selectedRow.sub_scores?.competition ?? 0} />
                  <SubScoreBar label="Infraestrutura" value={selectedRow.sub_scores?.infrastructure ?? 0} />
                  <SubScoreBar label="Crescimento" value={selectedRow.sub_scores?.growth ?? 0} />
                </div>

                <div className="space-y-2 pt-2">
                  <DetailRow
                    label="População"
                    value={(selectedRow.population ?? 0).toLocaleString('pt-BR')}
                  />
                  <DetailRow
                    label="Domicílios"
                    value={(selectedRow.households ?? 0).toLocaleString('pt-BR')}
                  />
                </div>

                {/* Fusion Intelligence Sections */}
                {fusionLoading && (
                  <div className="flex items-center gap-2 py-2">
                    <Loader2 size={14} className="animate-spin" style={{ color: 'var(--accent)' }} />
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Carregando inteligência...</span>
                  </div>
                )}

                {fusionData && (
                  <>
                    {/* Infrastructure Gaps */}
                    <div className="space-y-2 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
                      <div className="flex items-center gap-2">
                        <Zap size={14} style={{ color: 'var(--accent)' }} />
                        <span className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Lacunas de Infraestrutura</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className="rounded px-2 py-0.5 text-[10px] font-bold"
                          style={{
                            backgroundColor: fusionData.infrastructure.has_fiber
                              ? 'color-mix(in srgb, var(--success) 15%, transparent)'
                              : 'color-mix(in srgb, var(--danger) 15%, transparent)',
                            color: fusionData.infrastructure.has_fiber ? 'var(--success)' : 'var(--danger)',
                          }}
                        >
                          Backhaul: {fusionData.infrastructure.backhaul || 'Nenhum'}
                        </span>
                      </div>
                      {fusionData.infrastructure.schools_offline > 0 && (
                        <DetailRow label="Escolas sem internet" value={`${fusionData.infrastructure.schools_offline} / ${fusionData.infrastructure.schools_total}`} />
                      )}
                      {fusionData.infrastructure.health_offline > 0 && (
                        <DetailRow label="Saúde sem internet" value={`${fusionData.infrastructure.health_offline} / ${fusionData.infrastructure.health_total}`} />
                      )}
                      {fusionData.infrastructure.building_density_km2 != null && (
                        <DetailRow label="Densidade" value={`${fusionData.infrastructure.building_density_km2.toFixed(0)} end./km²`} />
                      )}
                    </div>

                    {/* Economic Signals */}
                    <div className="space-y-2 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
                      <div className="flex items-center gap-2">
                        <TrendingUp size={14} style={{ color: 'var(--accent)' }} />
                        <span className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Sinais Econômicos</span>
                      </div>
                      {fusionData.economic.net_hires != null && (
                        <div className="flex items-center gap-1">
                          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Contratações:</span>
                          <span
                            className="text-xs font-semibold"
                            style={{ color: fusionData.economic.net_hires > 0 ? 'var(--success)' : fusionData.economic.net_hires < 0 ? 'var(--danger)' : 'var(--text-primary)' }}
                          >
                            {fusionData.economic.net_hires > 0 ? '+' : ''}{fusionData.economic.net_hires}
                          </span>
                        </div>
                      )}
                      {fusionData.economic.government_contracts_12m > 0 && (
                        <DetailRow label="Contratos gov. (12m)" value={`${fusionData.economic.government_contracts_12m} (R$ ${(fusionData.economic.contract_value_total_brl / 1000).toFixed(0)}K)`} />
                      )}
                      {fusionData.economic.bndes_loans_active > 0 && (
                        <DetailRow label="BNDES" value={`${fusionData.economic.bndes_loans_active} empréstimo(s)`} />
                      )}
                    </div>

                    {/* Regulatory Climate */}
                    <div className="space-y-2 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
                      <div className="flex items-center gap-2">
                        <Landmark size={14} style={{ color: 'var(--accent)' }} />
                        <span className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Clima Regulatório</span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        <BadgePill active={fusionData.regulatory.has_plano_diretor} label="Plano Diretor" />
                        <BadgePill active={fusionData.regulatory.has_building_code} label="Cod. Obras" />
                        <BadgePill active={fusionData.regulatory.has_zoning_law} label="Zoneamento" />
                      </div>
                      {fusionData.regulatory.recent_gazette_mentions > 0 && (
                        <DetailRow label="Menções em diário (6m)" value={String(fusionData.regulatory.recent_gazette_mentions)} />
                      )}
                      <div className="flex items-center gap-1">
                        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Risco:</span>
                        <span
                          className="rounded px-1.5 py-0.5 text-[10px] font-bold"
                          style={{
                            backgroundColor: fusionData.regulatory.regulatory_risk === 'low'
                              ? 'color-mix(in srgb, var(--success) 15%, transparent)'
                              : fusionData.regulatory.regulatory_risk === 'high'
                                ? 'color-mix(in srgb, var(--danger) 15%, transparent)'
                                : 'color-mix(in srgb, var(--warning) 15%, transparent)',
                            color: fusionData.regulatory.regulatory_risk === 'low'
                              ? 'var(--success)'
                              : fusionData.regulatory.regulatory_risk === 'high'
                                ? 'var(--danger)'
                                : 'var(--warning)',
                          }}
                        >
                          {fusionData.regulatory.regulatory_risk === 'low' ? 'BAIXO' : fusionData.regulatory.regulatory_risk === 'high' ? 'ALTO' : 'MÉDIO'}
                        </span>
                      </div>
                    </div>

                    {/* Recommendation */}
                    {fusionData.recommendation && (
                      <div
                        className="rounded-lg p-3 text-xs"
                        style={{
                          backgroundColor: fusionData.recommendation.startsWith('HIGH')
                            ? 'color-mix(in srgb, var(--success) 10%, transparent)'
                            : fusionData.recommendation.startsWith('MEDIUM')
                              ? 'color-mix(in srgb, var(--warning) 10%, transparent)'
                              : 'var(--bg-subtle)',
                          color: fusionData.recommendation.startsWith('HIGH')
                            ? 'var(--success)'
                            : fusionData.recommendation.startsWith('MEDIUM')
                              ? 'var(--warning)'
                              : 'var(--text-secondary)',
                        }}
                      >
                        <FileText size={12} className="mb-1 inline" /> {fusionData.recommendation}
                      </div>
                    )}
                  </>
                )}

                {/* Satellite Analysis Section */}
                <div className="space-y-2 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
                  <div className="flex items-center gap-2">
                    <Satellite size={14} style={{ color: 'var(--accent)' }} />
                    <span className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
                      Crescimento Urbano (Satélite)
                    </span>
                  </div>

                  {!satData && !satLoading && !satError && (
                    <button
                      className="pulso-btn-primary mt-2 w-full"
                      onClick={() => handleSatelliteAnalysis(selectedRow.municipality_code)}
                    >
                      <Satellite size={14} className="mr-1.5 inline" />
                      Analisar 10 Anos de Satélite
                    </button>
                  )}

                  {satLoading && (
                    <div className="flex flex-col items-center gap-2 rounded-lg p-4" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                      <Loader2 size={20} className="animate-spin" style={{ color: 'var(--accent)' }} />
                      <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>
                        Processando imagens Sentinel-2...
                        <br />
                        <span style={{ color: 'var(--text-muted)' }}>Isso pode levar até 5 minutos</span>
                      </p>
                    </div>
                  )}

                  {satError && (
                    <p className="text-xs" style={{ color: 'var(--danger)' }}>{satError}</p>
                  )}

                  {satData?.data && satData.data.length > 0 && (
                    <SatelliteGrowthPanel data={satData.data} />
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SubScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
        <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{value.toFixed(1)}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ backgroundColor: 'var(--bg-subtle)' }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${value}%`, backgroundColor: 'var(--accent)' }}
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

function BadgePill({ active, label }: { active: boolean; label: string }) {
  return (
    <span
      className="rounded-full px-2 py-0.5 text-[10px] font-medium"
      style={{
        backgroundColor: active
          ? 'color-mix(in srgb, var(--success) 15%, transparent)'
          : 'color-mix(in srgb, var(--border) 50%, transparent)',
        color: active ? 'var(--success)' : 'var(--text-muted)',
      }}
    >
      {active ? '\u2713' : '\u2717'} {label}
    </span>
  );
}

function SatelliteGrowthPanel({
  data,
}: {
  data: NonNullable<SatelliteComputeResult['data']>;
}) {
  const first = data[0];
  const last = data[data.length - 1];
  const builtFirst = first?.built_up_area_km2 ?? 0;
  const builtLast = last?.built_up_area_km2 ?? 0;
  const growthKm2 = builtLast - builtFirst;
  const growthPct = builtFirst > 0 ? ((builtLast - builtFirst) / builtFirst) * 100 : 0;
  const ndviFirst = first?.ndvi_mean ?? 0;
  const ndviLast = last?.ndvi_mean ?? 0;
  const ndviDelta = ndviFirst !== 0 ? ((ndviLast - ndviFirst) / Math.abs(ndviFirst)) * 100 : 0;
  const growing = growthPct > 0;

  return (
    <div className="space-y-3">
      {/* Summary */}
      <div className="rounded-lg p-3" style={{ backgroundColor: growing ? 'color-mix(in srgb, var(--success) 10%, transparent)' : 'var(--bg-subtle)' }}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Crescimento {first?.year}–{last?.year}
            </p>
            <p className="text-lg font-bold" style={{ color: growing ? 'var(--success)' : 'var(--text-primary)' }}>
              {growing ? '+' : ''}{growthPct.toFixed(1)}%
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Área urbana</p>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              {growing ? '+' : ''}{growthKm2.toFixed(1)} km²
            </p>
          </div>
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg p-2" style={{ backgroundColor: 'var(--bg-subtle)' }}>
          <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Área urbana atual</p>
          <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
            {builtLast.toFixed(0)} km²
          </p>
          <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
            {(last?.built_up_pct ?? 0).toFixed(1)}% do município
          </p>
        </div>
        <div className="rounded-lg p-2" style={{ backgroundColor: 'var(--bg-subtle)' }}>
          <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Vegetação (NDVI)</p>
          <p className="text-sm font-bold" style={{ color: ndviDelta < -5 ? 'var(--danger)' : 'var(--text-primary)' }}>
            {(ndviLast).toFixed(3)}
          </p>
          <p className="text-[10px]" style={{ color: ndviDelta < -5 ? 'var(--danger)' : 'var(--text-muted)' }}>
            {ndviDelta > 0 ? '+' : ''}{ndviDelta.toFixed(1)}% vs {first?.year}
          </p>
        </div>
      </div>

      {/* Mini timeline */}
      <div>
        <p className="mb-1 text-[10px] font-semibold" style={{ color: 'var(--text-muted)' }}>
          Área urbana por ano (km²)
        </p>
        <div className="flex items-end gap-[2px]" style={{ height: 50 }}>
          {data.map((d) => {
            const max = Math.max(...data.map((x) => x.built_up_area_km2 ?? 0));
            const h = max > 0 ? ((d.built_up_area_km2 ?? 0) / max) * 100 : 0;
            return (
              <div
                key={d.year}
                className="flex-1 rounded-t"
                style={{
                  height: `${Math.max(h, 4)}%`,
                  backgroundColor: 'var(--accent)',
                  opacity: 0.5 + (h / 200),
                }}
                title={`${d.year}: ${(d.built_up_area_km2 ?? 0).toFixed(1)} km²`}
              />
            );
          })}
        </div>
        <div className="mt-0.5 flex justify-between">
          <span className="text-[9px]" style={{ color: 'var(--text-muted)' }}>{first?.year}</span>
          <span className="text-[9px]" style={{ color: 'var(--text-muted)' }}>{last?.year}</span>
        </div>
      </div>
    </div>
  );
}
