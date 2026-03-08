'use client';

import { useState, useMemo, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { ScatterplotLayer } from 'deck.gl';
import StatsCard from '@/components/dashboard/StatsCard';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type { HeatmapFeatureCollection, MarketSummary } from '@/lib/types';
import {
  MapPin,
  Users,
  Radio,
  Wifi,
  X,
  ChevronDown,
  Loader2,
  AlertCircle,
  Home,
  BarChart3,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Dynamic import for MapView (avoid SSR issues with WebGL)
// ---------------------------------------------------------------------------
const MapView = dynamic(() => import('@/components/map/MapView'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center rounded-lg bg-slate-800 border border-slate-700">
      <div className="text-center">
        <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        <p className="text-sm text-slate-400">Carregando mapa...</p>
      </div>
    </div>
  ),
});

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const DEFAULT_BBOX = '-73.99,-33.77,-34.79,5.27';

type MetricKey = 'penetration' | 'fiber_share' | 'subscribers';

const METRIC_OPTIONS: { value: MetricKey; label: string }[] = [
  { value: 'penetration', label: 'Penetracao' },
  { value: 'fiber_share', label: '% Fibra' },
  { value: 'subscribers', label: 'Assinantes' },
];

// ---------------------------------------------------------------------------
// Color helpers  (red/orange -> yellow -> green gradient)
// ---------------------------------------------------------------------------

/** Return an RGBA color based on a 0-1 normalized value.
 *  Low = red/orange, medium = yellow, high = green. */
function metricColor(normalized: number): [number, number, number, number] {
  const t = Math.max(0, Math.min(1, normalized));
  let r: number, g: number, b: number;
  if (t < 0.5) {
    // red (1,0,0) -> yellow (1,1,0)
    const s = t / 0.5;
    r = 255;
    g = Math.round(s * 255);
    b = 0;
  } else {
    // yellow (1,1,0) -> green (0,0.8,0)
    const s = (t - 0.5) / 0.5;
    r = Math.round((1 - s) * 255);
    g = Math.round((1 - s * 0.2) * 255); // 255 -> 204
    b = 0;
  }
  return [r, g, b, 200];
}

/** Normalize a value between min and max to 0-1 range. */
function normalize(val: number, min: number, max: number): number {
  if (max === min) return 0.5;
  return (val - min) / (max - min);
}

// ---------------------------------------------------------------------------
// Stats computation
// ---------------------------------------------------------------------------
interface ComputedStats {
  municipios: number;
  totalAssinantes: number;
  provedores: number;
  penetracaoMedia: number;
}

function computeStats(
  data: HeatmapFeatureCollection | null,
  metric: MetricKey
): ComputedStats {
  if (!data || !data.features || data.features.length === 0) {
    return { municipios: 0, totalAssinantes: 0, provedores: 0, penetracaoMedia: 0 };
  }

  const features = data.features;
  const municipios = features.length;

  const totalAssinantes = features.reduce(
    (sum, f) => sum + (f.properties.total_subscribers || 0),
    0
  );

  const provedores = features.reduce(
    (max, f) => Math.max(max, f.properties.provider_count || 0),
    0
  );

  // Average value when metric is penetration
  let penetracaoMedia = 0;
  if (metric === 'penetration') {
    const validFeatures = features.filter(
      (f) => f.properties.value != null
    );
    if (validFeatures.length > 0) {
      penetracaoMedia =
        validFeatures.reduce((sum, f) => sum + (f.properties.value ?? 0), 0) /
        validFeatures.length;
    }
  } else {
    // For other metrics, still compute average of value field as an indicator
    const validFeatures = features.filter(
      (f) => f.properties.value != null
    );
    if (validFeatures.length > 0) {
      penetracaoMedia =
        validFeatures.reduce((sum, f) => sum + (f.properties.value ?? 0), 0) /
        validFeatures.length;
    }
  }

  return { municipios, totalAssinantes, provedores, penetracaoMedia };
}

// ---------------------------------------------------------------------------
// Format helpers
// ---------------------------------------------------------------------------
function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString('pt-BR');
}

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------
export default function MapPage() {
  const [metric, setMetric] = useState<MetricKey>('penetration');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [selectedMunicipalityId, setSelectedMunicipalityId] = useState<number | null>(null);

  // ------ Fetch heatmap data from real API ----------------------------------
  const {
    data: heatmapData,
    loading: heatmapLoading,
    error: heatmapError,
  } = useApi<HeatmapFeatureCollection>(
    () => api.market.heatmap(DEFAULT_BBOX, metric),
    [metric]
  );

  // ------ Fetch municipality detail when selected ---------------------------
  const {
    data: municipalityDetail,
    loading: detailLoading,
    error: detailError,
  } = useApi<MarketSummary | null>(
    () => {
      if (selectedMunicipalityId == null) return Promise.resolve(null);
      return api.market.summary(selectedMunicipalityId);
    },
    [selectedMunicipalityId]
  );

  // ------ Computed stats from heatmap data ----------------------------------
  const stats = useMemo(() => computeStats(heatmapData, metric), [heatmapData, metric]);

  // ------ Build deck.gl layer -----------------------------------------------
  const layers = useMemo(() => {
    if (!heatmapData || !heatmapData.features || heatmapData.features.length === 0) {
      return [];
    }

    const features = heatmapData.features;
    const values = features
      .map((f) => f.properties.value)
      .filter((v): v is number => v != null);

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
        updateTriggers: {
          getFillColor: [metric, minVal, maxVal],
        },
      }),
    ];
  }, [heatmapData, metric]);

  // ------ Map click handler -------------------------------------------------
  const handleMapClick = useCallback((info: any) => {
    if (info?.object?.properties?.municipality_id) {
      setSelectedMunicipalityId(info.object.properties.municipality_id);
    }
  }, []);

  // ------ Close side panel --------------------------------------------------
  const handleClosePanel = useCallback(() => {
    setSelectedMunicipalityId(null);
  }, []);

  // ------ Metric selector handler -------------------------------------------
  const handleMetricChange = useCallback((newMetric: MetricKey) => {
    setMetric(newMetric);
    setDropdownOpen(false);
  }, []);

  // ------ Determine API connection status -----------------------------------
  const isApiConnected = !!heatmapData && !heatmapError;

  // ------ Metric label for display ------------------------------------------
  const currentMetricLabel =
    METRIC_OPTIONS.find((m) => m.value === metric)?.label ?? metric;

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      {/* ── Header: Metric selector ──────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <h1 className="text-lg font-semibold text-slate-100">
          Mapa de Cobertura
        </h1>

        {/* Metric dropdown */}
        <div className="relative">
          <button
            onClick={() => setDropdownOpen((prev) => !prev)}
            className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-200 hover:bg-slate-700 transition-colors"
          >
            <BarChart3 size={16} className="text-blue-400" />
            <span className="text-slate-400">Metrica:</span>
            <span className="font-medium">{currentMetricLabel}</span>
            <ChevronDown
              size={14}
              className={`text-slate-400 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`}
            />
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 z-50 mt-1 w-48 rounded-lg border border-slate-700 bg-slate-800 py-1 shadow-xl">
              {METRIC_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleMetricChange(opt.value)}
                  className={`w-full px-4 py-2 text-left text-sm transition-colors ${
                    opt.value === metric
                      ? 'bg-blue-500/10 text-blue-400'
                      : 'text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Stats bar ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-4 px-4 py-2 md:grid-cols-4">
        <StatsCard
          title="Municipios"
          value={formatNumber(stats.municipios)}
          icon={<MapPin size={18} />}
          subtitle="Total rastreados"
          loading={heatmapLoading}
        />
        <StatsCard
          title="Total Assinantes"
          value={formatNumber(stats.totalAssinantes)}
          icon={<Users size={18} />}
          subtitle="Banda larga"
          loading={heatmapLoading}
        />
        <StatsCard
          title="Provedores"
          value={formatNumber(stats.provedores)}
          icon={<Radio size={18} />}
          subtitle="ISPs ativos"
          loading={heatmapLoading}
        />
        <StatsCard
          title="Penetracao Media"
          value={`${stats.penetracaoMedia.toFixed(1)}%`}
          icon={<Wifi size={18} />}
          subtitle="Banda larga"
          loading={heatmapLoading}
        />
      </div>

      {/* ── Map + Side panel ─────────────────────────────────────────── */}
      <div className="flex flex-1 gap-4 px-4 pb-4">
        {/* Map area */}
        <div className="flex flex-1 flex-col">
          {heatmapError && (
            <div className="mb-2 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-400">
              <AlertCircle size={16} />
              <span>Erro ao carregar dados: {heatmapError}</span>
            </div>
          )}

          <div className="flex-1">
            <MapView
              className="h-full"
              layers={layers}
              onMapClick={handleMapClick}
            />
          </div>

          {/* Legend + API status */}
          <div className="mt-2 flex items-center justify-between">
            {/* Color legend */}
            <div className="flex items-center gap-3 text-xs text-slate-400">
              <span>Baixo</span>
              <div className="flex h-3 w-32 overflow-hidden rounded">
                <div className="flex-1 bg-red-500" />
                <div className="flex-1 bg-orange-500" />
                <div className="flex-1 bg-yellow-500" />
                <div className="flex-1 bg-lime-500" />
                <div className="flex-1 bg-green-500" />
              </div>
              <span>Alto</span>
              <span className="ml-2 text-slate-500">({currentMetricLabel})</span>
            </div>

            {/* API status indicator */}
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span
                className={`h-2 w-2 rounded-full ${isApiConnected ? 'bg-green-500' : 'bg-yellow-500'}`}
              />
              {isApiConnected ? 'API Conectada' : 'Modo Demo'}
            </div>
          </div>
        </div>

        {/* ── Side panel: municipality details ───────────────────────── */}
        {selectedMunicipalityId != null && (
          <div className="w-80 shrink-0 overflow-y-auto rounded-lg border border-slate-700 bg-slate-800">
            {/* Panel header */}
            <div className="flex items-center justify-between border-b border-slate-700 p-4">
              <h2 className="text-sm font-semibold text-slate-200">
                Detalhes do Municipio
              </h2>
              <button
                onClick={handleClosePanel}
                className="rounded p-1 text-slate-400 hover:bg-slate-700 hover:text-slate-200 transition-colors"
                aria-label="Fechar painel"
              >
                <X size={16} />
              </button>
            </div>

            {/* Panel body */}
            <div className="space-y-4 p-4">
              {detailLoading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 size={24} className="animate-spin text-blue-400" />
                  <span className="ml-2 text-sm text-slate-400">
                    Carregando...
                  </span>
                </div>
              )}

              {detailError && (
                <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
                  <AlertCircle size={16} className="mb-1 inline" />{' '}
                  Erro ao carregar detalhes
                </div>
              )}

              {municipalityDetail && !detailLoading && (
                <>
                  {/* Municipality name */}
                  <div>
                    <h3 className="text-lg font-bold text-slate-100">
                      {municipalityDetail.name ||
                        municipalityDetail.municipality_name ||
                        'N/A'}
                    </h3>
                    <p className="text-sm text-slate-400">
                      {municipalityDetail.state_abbrev}
                      {municipalityDetail.year_month &&
                        ` - ${municipalityDetail.year_month}`}
                    </p>
                  </div>

                  {/* Data grid */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg bg-slate-900 p-3">
                      <div className="flex items-center gap-1.5">
                        <Users size={12} className="text-slate-500" />
                        <p className="text-xs text-slate-500">Populacao</p>
                      </div>
                      <p className="mt-1 text-sm font-semibold text-slate-200">
                        {municipalityDetail.total_population != null
                          ? municipalityDetail.total_population.toLocaleString('pt-BR')
                          : 'N/A'}
                      </p>
                    </div>

                    <div className="rounded-lg bg-slate-900 p-3">
                      <div className="flex items-center gap-1.5">
                        <Home size={12} className="text-slate-500" />
                        <p className="text-xs text-slate-500">Domicilios</p>
                      </div>
                      <p className="mt-1 text-sm font-semibold text-slate-200">
                        {municipalityDetail.total_households != null
                          ? municipalityDetail.total_households.toLocaleString('pt-BR')
                          : 'N/A'}
                      </p>
                    </div>

                    <div className="rounded-lg bg-slate-900 p-3">
                      <div className="flex items-center gap-1.5">
                        <Users size={12} className="text-slate-500" />
                        <p className="text-xs text-slate-500">Assinantes</p>
                      </div>
                      <p className="mt-1 text-sm font-semibold text-slate-200">
                        {municipalityDetail.total_subscribers.toLocaleString('pt-BR')}
                      </p>
                    </div>

                    <div className="rounded-lg bg-slate-900 p-3">
                      <div className="flex items-center gap-1.5">
                        <Wifi size={12} className="text-slate-500" />
                        <p className="text-xs text-slate-500">Fibra</p>
                      </div>
                      <p className="mt-1 text-sm font-semibold text-slate-200">
                        {municipalityDetail.fiber_subscribers.toLocaleString('pt-BR')}
                      </p>
                    </div>

                    <div className="rounded-lg bg-slate-900 p-3">
                      <div className="flex items-center gap-1.5">
                        <BarChart3 size={12} className="text-slate-500" />
                        <p className="text-xs text-slate-500">Penetracao</p>
                      </div>
                      <p className="mt-1 text-sm font-semibold text-slate-200">
                        {municipalityDetail.broadband_penetration_pct != null
                          ? `${municipalityDetail.broadband_penetration_pct.toFixed(1)}%`
                          : 'N/A'}
                      </p>
                    </div>

                    <div className="rounded-lg bg-slate-900 p-3">
                      <div className="flex items-center gap-1.5">
                        <BarChart3 size={12} className="text-slate-500" />
                        <p className="text-xs text-slate-500">% Fibra</p>
                      </div>
                      <p className="mt-1 text-sm font-semibold text-slate-200">
                        {municipalityDetail.fiber_share_pct != null
                          ? `${municipalityDetail.fiber_share_pct.toFixed(1)}%`
                          : 'N/A'}
                      </p>
                    </div>

                    <div className="rounded-lg bg-slate-900 p-3 col-span-2">
                      <div className="flex items-center gap-1.5">
                        <Radio size={12} className="text-slate-500" />
                        <p className="text-xs text-slate-500">Provedores</p>
                      </div>
                      <p className="mt-1 text-sm font-semibold text-slate-200">
                        {municipalityDetail.provider_count}
                      </p>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
