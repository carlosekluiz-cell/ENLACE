'use client';

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import dynamic from 'next/dynamic';
import SidePanel from '@/components/layout/SidePanel';
import MapSearch from '@/components/map/MapSearch';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type { HeatmapFeatureCollection, MarketSummary, MunicipalityFusion } from '@/lib/types';
import {
  Users,
  Radio,
  Wifi,
  ChevronDown,
  Home,
  BarChart3,
  Layers,
  AlertTriangle,
  Landmark,
  TrendingUp,
} from 'lucide-react';

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

const DEFAULT_BBOX = '-73.99,-33.77,-34.79,5.27';

type MetricKey = 'penetration' | 'fiber_share' | 'subscribers';

const METRIC_OPTIONS: { value: MetricKey; label: string }[] = [
  { value: 'penetration', label: 'Penetração' },
  { value: 'fiber_share', label: '% Fibra' },
  { value: 'subscribers', label: 'Assinantes' },
];

function metricColor(normalized: number): [number, number, number, number] {
  const t = Math.max(0, Math.min(1, normalized));
  let r: number, g: number, b: number;
  if (t < 0.5) {
    const s = t / 0.5;
    r = 255;
    g = Math.round(s * 255);
    b = 0;
  } else {
    const s = (t - 0.5) / 0.5;
    r = Math.round((1 - s) * 255);
    g = Math.round((1 - s * 0.2) * 255);
    b = 0;
  }
  return [r, g, b, 200];
}

function normalize(val: number, min: number, max: number): number {
  if (max === min) return 0.5;
  return (val - min) / (max - min);
}

import { formatCompact as formatNumber } from '@/lib/format';

export default function MapDashboard() {
  const [metric, setMetric] = useState<MetricKey>('penetration');
  const [layerDropdownOpen, setLayerDropdownOpen] = useState(false);
  const [selectedMunicipalityId, setSelectedMunicipalityId] = useState<number | null>(null);
  const [flyTo, setFlyTo] = useState<{ latitude: number; longitude: number; zoom?: number } | null>(null);
  const deckRef = useRef<{ ScatterplotLayer: any } | null>(null);
  const [deckReady, setDeckReady] = useState(false);

  useEffect(() => {
    import('@deck.gl/layers').then((mod) => {
      deckRef.current = { ScatterplotLayer: mod.ScatterplotLayer };
      setDeckReady(true);
    });
  }, []);

  const {
    data: heatmapData,
    loading: heatmapLoading,
  } = useApi<HeatmapFeatureCollection>(
    () => api.market.heatmap(DEFAULT_BBOX, metric),
    [metric]
  );

  const {
    data: municipalityDetail,
    loading: detailLoading,
  } = useApi<MarketSummary | null>(
    () => {
      if (selectedMunicipalityId == null) return Promise.resolve(null);
      return api.market.summary(selectedMunicipalityId);
    },
    [selectedMunicipalityId]
  );

  const {
    data: fusionData,
    loading: fusionLoading,
  } = useApi<MunicipalityFusion | null>(
    () => {
      if (selectedMunicipalityId == null) return Promise.resolve(null);
      return api.intelligence.fusion(selectedMunicipalityId);
    },
    [selectedMunicipalityId]
  );

  const layers = useMemo(() => {
    if (!heatmapData?.features?.length || !deckRef.current) return [];
    const { ScatterplotLayer } = deckRef.current;

    const features = heatmapData.features;
    const values = features.map((f) => f.properties.value).filter((v): v is number => v != null);
    const minVal = values.length > 0 ? Math.min(...values) : 0;
    const maxVal = values.length > 0 ? Math.max(...values) : 1;

    return [
      new ScatterplotLayer({
        id: 'heatmap-layer',
        data: features,
        getPosition: (d: any) => d.geometry.coordinates,
        getRadius: 6000,
        getFillColor: (d: any) => {
          const val = d.properties.value;
          if (val == null) return [128, 128, 128, 150] as [number, number, number, number];
          return metricColor(normalize(val, minVal, maxVal));
        },
        pickable: true,
        radiusMinPixels: 3,
        radiusMaxPixels: 20,
        updateTriggers: { getFillColor: [metric, minVal, maxVal] },
      }),
    ];
  }, [heatmapData, metric, deckReady]);

  const handleMapClick = useCallback((info: any) => {
    if (info?.object?.properties?.municipality_id) {
      setSelectedMunicipalityId(info.object.properties.municipality_id);
    }
  }, []);

  const currentMetricLabel = METRIC_OPTIONS.find((m) => m.value === metric)?.label ?? metric;

  return (
    <div className="relative h-full w-full overflow-hidden">
      {/* Loading progress bar */}
      {heatmapLoading && (
        <div className="absolute top-0 left-0 right-0 z-20 overflow-hidden" style={{ height: '2px' }}>
          <div className="pulso-progress-bar w-full" />
        </div>
      )}

      {/* Map fills entire area */}
      <MapView
        className="h-full w-full"
        layers={layers}
        onMapClick={handleMapClick}
        flyTo={flyTo}
      />

      {/* Search overlay top-center */}
      <MapSearch
        onSelect={(m) => setFlyTo({ latitude: m.lat, longitude: m.lng, zoom: 11 })}
      />

      {/* Layer selector top-right (below map controls) */}
      <div className="absolute right-4 top-40 z-10">
        <div className="relative">
          <button
            onClick={() => setLayerDropdownOpen((prev) => !prev)}
            className="flex items-center gap-2 rounded-md px-3 py-2 text-sm"
            style={{
              background: 'var(--bg-surface)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            <Layers size={14} />
            {currentMetricLabel}
            <ChevronDown size={12} className={layerDropdownOpen ? 'rotate-180' : ''} />
          </button>

          {layerDropdownOpen && (
            <div
              className="absolute right-0 mt-1 w-44 rounded-md py-1"
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              }}
            >
              {METRIC_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => { setMetric(opt.value); setLayerDropdownOpen(false); }}
                  className="w-full px-3 py-2 text-left text-sm"
                  style={{
                    color: opt.value === metric ? 'var(--accent)' : 'var(--text-primary)',
                    background: opt.value === metric ? 'var(--accent-subtle)' : 'transparent',
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Attribution bottom-left */}
      <div
        className="absolute bottom-2 left-2 z-10 rounded px-2 py-1 text-xs"
        style={{ color: 'var(--text-muted)', background: 'var(--bg-surface)', opacity: 0.8 }}
      >
        Fonte: Anatel Banda Larga / IBGE 2024 / Pulso Network
      </div>

      {/* Municipality detail SidePanel */}
      <SidePanel
        open={selectedMunicipalityId != null}
        onClose={() => setSelectedMunicipalityId(null)}
        title={municipalityDetail?.name || municipalityDetail?.municipality_name || 'Município'}
        subtitle={municipalityDetail?.state_abbrev}
      >
        {detailLoading ? (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Carregando...</p>
        ) : municipalityDetail ? (
          <div className="space-y-4">
            {/* Key values */}
            <div className="space-y-3">
              <KeyValue icon={<Users size={14} />} label="População" value={municipalityDetail.total_population != null ? municipalityDetail.total_population.toLocaleString('pt-BR') : 'N/A'} />
              <KeyValue icon={<Home size={14} />} label="Domicílios" value={municipalityDetail.total_households != null ? municipalityDetail.total_households.toLocaleString('pt-BR') : 'N/A'} />
              <KeyValue icon={<Users size={14} />} label="Assinantes" value={formatNumber(municipalityDetail.total_subscribers)} />
              <KeyValue icon={<Wifi size={14} />} label="Fibra" value={formatNumber(municipalityDetail.fiber_subscribers)} />
              <KeyValue icon={<BarChart3 size={14} />} label="Penetração" value={municipalityDetail.broadband_penetration_pct != null ? `${municipalityDetail.broadband_penetration_pct.toFixed(1)}%` : 'N/A'} />
              <KeyValue icon={<BarChart3 size={14} />} label="% Fibra" value={municipalityDetail.fiber_share_pct != null ? `${municipalityDetail.fiber_share_pct.toFixed(1)}%` : 'N/A'} />
              <KeyValue icon={<Radio size={14} />} label="Provedores" value={String(municipalityDetail.provider_count)} />
            </div>

            {/* Fusion intelligence badges */}
            {fusionLoading && (
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Carregando inteligência...</p>
            )}
            {fusionData && (
              <div className="space-y-3 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
                {/* Opportunity score */}
                {fusionData.opportunity && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Oportunidade</span>
                    <span
                      className="rounded px-2 py-0.5 text-xs font-bold"
                      style={{
                        backgroundColor: fusionData.opportunity.score >= 75
                          ? 'color-mix(in srgb, var(--success) 15%, transparent)'
                          : fusionData.opportunity.score >= 50
                            ? 'color-mix(in srgb, var(--warning) 15%, transparent)'
                            : 'var(--bg-subtle)',
                        color: fusionData.opportunity.score >= 75 ? 'var(--success)' : fusionData.opportunity.score >= 50 ? 'var(--warning)' : 'var(--text-muted)',
                      }}
                    >
                      {(fusionData.opportunity.score ?? 0).toFixed(1)} (#{fusionData.opportunity.rank})
                    </span>
                  </div>
                )}

                {/* Infrastructure gap severity */}
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                    <AlertTriangle size={12} /> Infra
                  </span>
                  <span
                    className="rounded px-2 py-0.5 text-[10px] font-bold"
                    style={{
                      backgroundColor: !fusionData.infrastructure.has_fiber
                        ? 'color-mix(in srgb, var(--danger) 15%, transparent)'
                        : fusionData.infrastructure.schools_offline > 5
                          ? 'color-mix(in srgb, var(--warning) 15%, transparent)'
                          : 'color-mix(in srgb, var(--success) 15%, transparent)',
                      color: !fusionData.infrastructure.has_fiber
                        ? 'var(--danger)'
                        : fusionData.infrastructure.schools_offline > 5
                          ? 'var(--warning)'
                          : 'var(--success)',
                    }}
                  >
                    {!fusionData.infrastructure.has_fiber ? 'CRÍTICO' : fusionData.infrastructure.schools_offline > 5 ? 'MODERADO' : 'OK'}
                  </span>
                </div>

                {/* Government investment */}
                {(fusionData.economic.government_contracts_12m > 0 || fusionData.economic.bndes_loans_active > 0) && (
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                      <Landmark size={12} /> Gov
                    </span>
                    <span className="text-xs font-medium" style={{ color: 'var(--success)' }}>
                      {fusionData.economic.government_contracts_12m > 0 && `${fusionData.economic.government_contracts_12m} contrato(s)`}
                      {fusionData.economic.government_contracts_12m > 0 && fusionData.economic.bndes_loans_active > 0 && ' + '}
                      {fusionData.economic.bndes_loans_active > 0 && `${fusionData.economic.bndes_loans_active} BNDES`}
                    </span>
                  </div>
                )}

                {/* Recommendation */}
                {fusionData.recommendation && (
                  <p
                    className="rounded-lg p-2 text-[10px]"
                    style={{
                      backgroundColor: fusionData.recommendation.startsWith('HIGH')
                        ? 'color-mix(in srgb, var(--success) 10%, transparent)'
                        : 'var(--bg-subtle)',
                      color: fusionData.recommendation.startsWith('HIGH')
                        ? 'var(--success)'
                        : 'var(--text-muted)',
                    }}
                  >
                    {fusionData.recommendation}
                  </p>
                )}
              </div>
            )}
          </div>
        ) : null}
      </SidePanel>
    </div>
  );
}

function KeyValue({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1" style={{ borderBottom: '1px solid var(--border)' }}>
      <div className="flex items-center gap-2">
        <span style={{ color: 'var(--text-muted)' }}>{icon}</span>
        <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</span>
      </div>
      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  );
}
