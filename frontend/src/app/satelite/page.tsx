'use client';

import { useState, useMemo, useEffect } from 'react';
import dynamic from 'next/dynamic';
import DataTable from '@/components/dashboard/DataTable';
import SimpleChart from '@/components/charts/SimpleChart';
import { useApi } from '@/hooks/useApi';
import { useLazyApi } from '@/hooks/useApi';
import {
  getSatelliteRanking,
  getSatelliteGrowth,
  getSatelliteIndices,
} from '@/lib/api';
import type {
  SatelliteGrowthRanking,
  SatelliteGrowthComparison,
  SatelliteYearData,
} from '@/lib/types';
import {
  Satellite,
  TrendingUp,
  BarChart3,
  X,
  AlertTriangle,
  Map as MapIcon,
  Leaf,
} from 'lucide-react';

const MapView = dynamic(() => import('@/components/map/MapView'), { ssr: false });

// Brazilian states for the filter dropdown
const BRAZILIAN_STATES = [
  { code: '', label: 'Todos os estados' },
  { code: 'AC', label: 'Acre' },
  { code: 'AL', label: 'Alagoas' },
  { code: 'AM', label: 'Amazonas' },
  { code: 'AP', label: 'Amapá' },
  { code: 'BA', label: 'Bahia' },
  { code: 'CE', label: 'Ceará' },
  { code: 'DF', label: 'Distrito Federal' },
  { code: 'ES', label: 'Espírito Santo' },
  { code: 'GO', label: 'Goiás' },
  { code: 'MA', label: 'Maranhão' },
  { code: 'MG', label: 'Minas Gerais' },
  { code: 'MS', label: 'Mato Grosso do Sul' },
  { code: 'MT', label: 'Mato Grosso' },
  { code: 'PA', label: 'Pará' },
  { code: 'PB', label: 'Paraíba' },
  { code: 'PE', label: 'Pernambuco' },
  { code: 'PI', label: 'Piauí' },
  { code: 'PR', label: 'Paraná' },
  { code: 'RJ', label: 'Rio de Janeiro' },
  { code: 'RN', label: 'Rio Grande do Norte' },
  { code: 'RO', label: 'Rondônia' },
  { code: 'RR', label: 'Roraima' },
  { code: 'RS', label: 'Rio Grande do Sul' },
  { code: 'SC', label: 'Santa Catarina' },
  { code: 'SE', label: 'Sergipe' },
  { code: 'SP', label: 'São Paulo' },
  { code: 'TO', label: 'Tocantins' },
];

// Color scale for built-up growth: low is cool blue, high is warm orange/red
function growthToColor(pct: number): [number, number, number, number] {
  const t = Math.max(0, Math.min(1, (pct + 2) / 8)); // normalize ~-2% to +6% range into 0-1
  const r = Math.round(30 + t * 225);
  const g = Math.round(180 - t * 100);
  const b = Math.round(200 - t * 170);
  return [r, g, b, 200];
}

// Table columns for the ranking table
const columns = [
  {
    key: 'municipality_name',
    label: 'Município',
    sortable: true,
    render: (value: string, row: SatelliteGrowthRanking) => (
      <div>
        <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{value}</span>
        {(row as any).state_code && (
          <span className="ml-2 text-xs" style={{ color: 'var(--text-muted)' }}>{(row as any).state_code}</span>
        )}
      </div>
    ),
  },
  {
    key: 'avg_built_up_change_pct',
    label: 'Crescimento Urbano',
    sortable: true,
    render: (value: number | null, row: SatelliteGrowthRanking) => {
      const pct = (row as any).avg_metric ?? value ?? 0;
      const absVal = Math.abs(pct);
      const barWidth = Math.min(absVal * 10, 100);
      return (
        <div className="flex items-center gap-2">
          <div className="h-2 w-16 overflow-hidden rounded-full" style={{ backgroundColor: 'var(--bg-subtle)' }}>
            <div
              className="h-full rounded-full"
              style={{
                width: `${barWidth}%`,
                backgroundColor: pct >= 0 ? 'var(--success)' : 'var(--danger)',
              }}
            />
          </div>
          <span
            className="text-sm font-semibold"
            style={{ color: pct >= 0 ? 'var(--success)' : 'var(--danger)' }}
          >
            {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
          </span>
        </div>
      );
    },
  },
  {
    key: 'latest_built_up_area_km2',
    label: 'Área Construída',
    sortable: true,
    render: (_value: number | null, row: SatelliteGrowthRanking) => {
      const area = (row as any).area_km2 ?? _value;
      return area != null ? `${area.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} km2` : '-';
    },
  },
  {
    key: 'avg_ndvi',
    label: 'NDVI Médio',
    sortable: true,
    render: (value: number | null) => (
      <span style={{ color: 'var(--success)' }}>
        {value != null ? value.toFixed(3) : '-'}
      </span>
    ),
  },
  {
    key: 'population',
    label: 'População',
    sortable: true,
    render: (value: number | null) => value != null ? value.toLocaleString('pt-BR') : '-',
  },
];

export default function SatellitePage() {
  const [stateFilter, setStateFilter] = useState('');
  const [selectedRow, setSelectedRow] = useState<SatelliteGrowthRanking | null>(null);
  const [deckLayers, setDeckLayers] = useState<{ ColumnLayer: any; ScatterplotLayer: any } | null>(null);

  // Fetch ranking data (re-fetch when state filter changes)
  const {
    data: ranking,
    loading,
    error,
  } = useApi(
    () => getSatelliteRanking(stateFilter || undefined),
    [stateFilter],
  );

  // Lazy fetch for municipality detail
  const {
    data: growthData,
    loading: loadingGrowth,
    execute: fetchGrowth,
    reset: resetGrowth,
  } = useLazyApi<SatelliteGrowthComparison, string>(
    (code) => getSatelliteGrowth(code),
  );

  const {
    data: indicesData,
    loading: loadingIndices,
    execute: fetchIndices,
    reset: resetIndices,
  } = useLazyApi<SatelliteYearData[], string>(
    (code) => getSatelliteIndices(code),
  );

  // When a row is selected, fetch detail data
  const handleRowClick = (row: SatelliteGrowthRanking) => {
    setSelectedRow(row);
    fetchGrowth(row.municipality_code);
    fetchIndices(row.municipality_code);
  };

  const handleCloseDetail = () => {
    setSelectedRow(null);
    resetGrowth();
    resetIndices();
  };

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

  // Build map layers from ranking data
  const mapLayers = useMemo(() => {
    if (!deckLayers) return [];
    const { ColumnLayer } = deckLayers;
    const layers: any[] = [];

    if (ranking && ranking.length > 0) {
      const withCoords = ranking.filter(
        (r) => r.latitude != null && r.longitude != null,
      );
      if (withCoords.length > 0) {
        layers.push(
          new ColumnLayer({
            id: 'satellite-growth-columns',
            data: withCoords,
            diskResolution: 12,
            radius: 15000,
            extruded: true,
            elevationScale: 3000,
            getPosition: (d: SatelliteGrowthRanking) => [d.longitude!, d.latitude!],
            getFillColor: (d: SatelliteGrowthRanking) =>
              growthToColor((d as any).avg_metric ?? d.avg_built_up_change_pct ?? 0),
            getElevation: (d: SatelliteGrowthRanking) =>
              Math.max(0, ((d as any).avg_metric ?? d.avg_built_up_change_pct ?? 0) * 10),
            pickable: true,
            autoHighlight: true,
            highlightColor: [255, 255, 255, 100],
          }),
        );
      }
    }

    return layers;
  }, [deckLayers, ranking]);

  // Summary stats
  const topGrowth =
    ranking && ranking.length > 0
      ? ((ranking[0] as any).avg_metric ?? ranking[0].avg_built_up_change_pct)
      : null;
  const topMunicipality =
    ranking && ranking.length > 0 ? ranking[0].municipality_name : undefined;
  const avgGrowth =
    ranking && ranking.length > 0
      ? ranking.reduce(
          (s, r) => s + ((r as any).avg_metric ?? r.avg_built_up_change_pct ?? 0),
          0,
        ) / ranking.length
      : null;
  const totalPopulation =
    ranking && ranking.length > 0
      ? ranking.reduce((s, r) => s + (r.population ?? 0), 0)
      : 0;

  // Growth comparison chart data
  const growthChartData = useMemo(() => {
    if (!growthData) return [];
    const satMap = new Map(
      growthData.satellite_growth.map((d) => [d.year, d.built_up_area_km2]),
    );
    const ibgeMap = new Map(
      growthData.ibge_growth.map((d) => [d.year, d.population]),
    );
    const allYears = Array.from(
      new Set([
        ...growthData.satellite_growth.map((d) => d.year),
        ...growthData.ibge_growth.map((d) => d.year),
      ]),
    ).sort();
    return allYears.map((year) => ({
      name: String(year),
      area_construida: satMap.get(year) ?? null,
      população: ibgeMap.get(year) ?? null,
    }));
  }, [growthData]);

  // Satellite índices chart data
  const indicesChartData = useMemo(() => {
    if (!indicesData) return [];
    return indicesData.map((d) => ({
      name: String(d.year),
      NDVI: d.mean_ndvi ?? 0,
      NDBI: d.mean_ndbi ?? 0,
      MNDWI: d.mean_mndwi ?? 0,
      BSI: d.mean_bsi ?? 0,
    }));
  }, [indicesData]);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <Satellite size={24} style={{ color: 'var(--accent)' }} />
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
              Inteligência Satelital
            </h1>
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Análise de crescimento urbano baseada em imagens Sentinel-2 com cruzamento de dados IBGE
            </p>
          </div>
        </div>
      </div>

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
            Erro ao carregar dados satelitais. Verifique sua conexão e tente novamente.
          </p>
        </div>
      )}

      {/* State filter */}
      <div className="flex items-center gap-3">
        <label
          htmlFor="state-filter"
          className="text-sm font-medium"
          style={{ color: 'var(--text-secondary)' }}
        >
          Filtrar por estado:
        </label>
        <select
          id="state-filter"
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
          className="pulso-input w-56"
        >
          {BRAZILIAN_STATES.map((st) => (
            <option key={st.code} value={st.code}>
              {st.label}
            </option>
          ))}
        </select>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                Maior Crescimento
              </p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {loading
                  ? 'Carregando...'
                  : topGrowth != null
                    ? `${topGrowth >= 0 ? '+' : ''}${topGrowth.toFixed(2)}%`
                    : '--'}
              </p>
              {topMunicipality && (
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {topMunicipality}
                </p>
              )}
            </div>
            <TrendingUp size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                Crescimento Médio
              </p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {loading
                  ? 'Carregando...'
                  : avgGrowth != null
                    ? `${avgGrowth >= 0 ? '+' : ''}${avgGrowth.toFixed(2)}%`
                    : '--'}
              </p>
              {ranking && ranking.length > 0 && (
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {ranking.length} municípios analisados
                </p>
              )}
            </div>
            <BarChart3 size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                População Total
              </p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {loading ? 'Carregando...' : totalPopulation.toLocaleString('pt-BR')}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Habitantes nos municípios analisados
              </p>
            </div>
            <Leaf size={18} style={{ color: 'var(--success)' }} />
          </div>
        </div>
      </div>

      {/* Map with satellite growth */}
      <div className="pulso-card overflow-hidden p-0">
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-2">
            <MapIcon size={16} style={{ color: 'var(--accent)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Mapa de Crescimento Urbano Satelital
            </h2>
            {!loading && ranking && (
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                {ranking.filter((r) => r.latitude != null).length} municípios mapeados
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-muted)' }}>
            <span className="flex items-center gap-1">
              <span
                className="inline-block h-3 w-3 rounded"
                style={{ background: 'rgb(30, 180, 200)' }}
              />
              Baixo crescimento
            </span>
            <span className="flex items-center gap-1">
              <span
                className="inline-block h-3 w-3 rounded"
                style={{ background: 'rgb(255, 80, 30)' }}
              />
              Alto crescimento
            </span>
          </div>
        </div>
        <MapView
          layers={mapLayers}
          className="h-[480px]"
          onMapClick={(info: any) => {
            if (info?.object && 'municipality_code' in info.object) {
              handleRowClick(info.object as SatelliteGrowthRanking);
            }
          }}
        />
      </div>

      {/* Table + Detail panel */}
      <div className="flex gap-6">
        <div className="flex-1">
          <h2 className="mb-4 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
            Ranking de Crescimento Urbano
          </h2>
          <DataTable
            columns={columns}
            data={ranking || []}
            loading={loading}
            searchable
            searchKeys={['municipality_name']}
            onRowClick={handleRowClick}
            emptyMessage="Índices satelitais ainda não foram computados para esta região. Os dados Sentinel-2 serão processados em breve."
          />
        </div>

        {/* Municipality Detail Panel */}
        {selectedRow && (
          <div className="w-96 shrink-0">
            <div className="pulso-card sticky top-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  Detalhes do Município
                </h3>
                <button
                  onClick={handleCloseDetail}
                  className="hover:opacity-80"
                  style={{ color: 'var(--text-secondary)' }}
                  aria-label="Fechar detalhes"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Municipality header */}
              <div>
                <h4 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                  {selectedRow.municipality_name}
                </h4>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  Cod. {selectedRow.municipality_code}
                </p>
              </div>

              {/* Comparison card */}
              {growthData && (
                <div
                  className="rounded-lg p-3"
                  style={{ backgroundColor: 'var(--accent-subtle)' }}
                >
                  <p className="text-xs font-medium" style={{ color: 'var(--accent)' }}>
                    Comparativo Satélite vs IBGE
                  </p>
                  <p className="mt-1 text-sm font-semibold" style={{ color: 'var(--accent)' }}>
                    Satélite: {growthData.correlation_summary.avg_annual_built_up_change_pct != null
                      ? `${growthData.correlation_summary.avg_annual_built_up_change_pct >= 0 ? '+' : ''}${growthData.correlation_summary.avg_annual_built_up_change_pct.toFixed(2)}% área construída`
                      : 'Sem dados'}
                  </p>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    IBGE: {growthData.correlation_summary.ibge_population != null
                      ? `${growthData.correlation_summary.ibge_population.toLocaleString('pt-BR')} habitantes`
                      : 'Sem dados'}
                  </p>
                </div>
              )}
              {loadingGrowth && (
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Carregando comparativo...</p>
              )}

              {/* Growth comparison chart */}
              {growthChartData.length > 0 && (
                <SimpleChart
                  data={growthChartData}
                  type="line"
                  xKey="name"
                  yKeys={['area_construida', 'população']}
                  title="Área Construída vs População"
                  height={200}
                  loading={loadingGrowth}
                />
              )}

              {/* Satellite índices chart */}
              {indicesChartData.length > 0 && (
                <SimpleChart
                  data={indicesChartData}
                  type="line"
                  xKey="name"
                  yKeys={['NDVI', 'NDBI', 'MNDWI', 'BSI']}
                  title="Índices Satelitais ao Longo do Tempo"
                  height={200}
                  loading={loadingIndices}
                />
              )}
              {loadingIndices && !indicesChartData.length && (
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Carregando índices...</p>
              )}

              {/* Detail stats */}
              <div className="space-y-2 pt-2">
                <DetailRow
                  label="População"
                  value={
                    selectedRow.population != null
                      ? selectedRow.population.toLocaleString('pt-BR')
                      : '-'
                  }
                />
                <DetailRow
                  label="Área do Município"
                  value={
                    (selectedRow as any).area_km2 != null
                      ? `${(selectedRow as any).area_km2.toLocaleString('pt-BR')} km2`
                      : '-'
                  }
                />
                <DetailRow
                  label="Crescimento Médio"
                  value={
                    ((selectedRow as any).avg_metric ?? selectedRow.avg_built_up_change_pct) != null
                      ? `${(((selectedRow as any).avg_metric ?? selectedRow.avg_built_up_change_pct) as number).toFixed(2)}%`
                      : '-'
                  }
                />
              </div>
            </div>
          </div>
        )}
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
