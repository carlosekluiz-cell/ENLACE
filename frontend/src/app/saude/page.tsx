'use client';

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import dynamic from 'next/dynamic';
import SidePanel from '@/components/layout/SidePanel';
import { useApi, useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type { HeatmapFeatureCollection, WeatherRisk, MaintenancePriority } from '@/lib/types';
import { Activity, CloudRain, AlertTriangle, Thermometer, Wrench, ChevronDown, Layers, Wind, Droplets, School, Building2, Shield } from 'lucide-react';
import type { MunicipalityFusion } from '@/lib/types';

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

type LayerType = 'weather_risk' | 'quality';

const LAYER_OPTIONS: { value: LayerType; label: string }[] = [
  { value: 'weather_risk', label: 'Risco climático' },
  { value: 'quality', label: 'Qualidade da rede' },
];

function riskColor(risk: number): [number, number, number, number] {
  if (risk < 0.3) return [34, 197, 94, 180];
  if (risk < 0.6) return [234, 179, 8, 180];
  return [239, 68, 68, 180];
}

function riskLabel(level: string): string {
  switch (level) {
    case 'low': return 'baixo';
    case 'moderate': return 'médio';
    case 'high': return 'alto';
    default: return level;
  }
}

function riskBadgeClass(level: string): string {
  switch (level) {
    case 'low': return 'pulso-badge-green';
    case 'moderate': return 'pulso-badge-yellow';
    case 'high': return 'pulso-badge-red';
    default: return 'pulso-badge-yellow';
  }
}

function timingLabel(timing: string): string {
  switch (timing) {
    case 'within_7_days': return 'Próximos 7 dias';
    case 'within_30_days': return 'Próximos 30 dias';
    case 'within_90_days': return 'Próximos 90 dias';
    default: return timing;
  }
}

export default function SaudePage() {
  const [layer, setLayer] = useState<LayerType>('weather_risk');
  const [layerDropdownOpen, setLayerDropdownOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedName, setSelectedName] = useState<string>('');
  const deckRef = useRef<{ ScatterplotLayer: any } | null>(null);
  const [deckReady, setDeckReady] = useState(false);

  useEffect(() => {
    import('@deck.gl/layers').then((mod) => {
      deckRef.current = { ScatterplotLayer: mod.ScatterplotLayer };
      setDeckReady(true);
    });
  }, []);

  const { data: heatmapData, loading } = useApi<HeatmapFeatureCollection>(
    () => api.market.heatmap(DEFAULT_BBOX, 'penetration'),
    []
  );

  const {
    data: weatherData,
    loading: weatherLoading,
    execute: fetchWeather,
    reset: resetWeather,
  } = useLazyApi<WeatherRisk, number>((id) => api.networkHealth.weatherRisk(id));

  const {
    data: maintenanceData,
    loading: maintenanceLoading,
    execute: fetchMaintenance,
  } = useLazyApi<MaintenancePriority[], number>((id) => api.networkHealth.maintenancePriorities(id));

  const {
    data: fusionData,
    loading: fusionLoading,
  } = useApi<MunicipalityFusion | null>(
    () => {
      if (selectedId == null) return Promise.resolve(null);
      return api.intelligence.fusion(selectedId);
    },
    [selectedId]
  );

  // Fetch health data when a municipality is selected
  useEffect(() => {
    if (selectedId != null) {
      fetchWeather(selectedId);
      fetchMaintenance(1); // provider_id=1 as default context
    }
  }, [selectedId, fetchWeather, fetchMaintenance]);

  // Find the maintenance priority for the selected municipality
  const selectedMaintenance = useMemo(() => {
    if (!maintenanceData || selectedId == null) return null;
    return maintenanceData.find((m) => m.municipality_id === selectedId) || maintenanceData[0] || null;
  }, [maintenanceData, selectedId]);

  const layers = useMemo(() => {
    if (!heatmapData?.features?.length || !deckRef.current) return [];
    const { ScatterplotLayer } = deckRef.current;
    return [
      new ScatterplotLayer({
        id: 'health-layer',
        data: heatmapData.features,
        getPosition: (d: any) => d.geometry.coordinates,
        getRadius: 6000,
        getFillColor: (d: any) => {
          const val = d.properties.value || 0;
          return riskColor(layer === 'weather_risk' ? 1 - val / 100 : val / 100);
        },
        pickable: true,
        radiusMinPixels: 3,
        radiusMaxPixels: 20,
        updateTriggers: { getFillColor: [layer] },
      }),
    ];
  }, [heatmapData, layer, deckReady]);

  const handleMapClick = useCallback((info: any) => {
    if (info?.object?.properties?.municipality_id) {
      setSelectedId(info.object.properties.municipality_id);
      setSelectedName(info.object.properties.name || '');
    }
  }, []);

  const handleClose = useCallback(() => {
    setSelectedId(null);
    setSelectedName('');
    resetWeather();
  }, [resetWeather]);

  const panelLoading = weatherLoading || maintenanceLoading;

  return (
    <div className="relative h-full w-full">
      {loading && (
        <div className="absolute top-0 left-0 right-0 z-20 overflow-hidden" style={{ height: '2px' }}>
          <div className="pulso-progress-bar w-full" />
        </div>
      )}

      <MapView className="h-full w-full" layers={layers} onMapClick={handleMapClick} />

      {/* Layer selector */}
      <div className="absolute right-4 top-40 z-10">
        <div className="relative">
          <button
            onClick={() => setLayerDropdownOpen((prev) => !prev)}
            className="flex items-center gap-2 rounded-md px-3 py-2 text-sm"
            style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
          >
            <Layers size={14} />
            {LAYER_OPTIONS.find((o) => o.value === layer)?.label}
            <ChevronDown size={12} />
          </button>

          {layerDropdownOpen && (
            <div className="absolute right-0 mt-1 w-48 rounded-md py-1" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
              {LAYER_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => { setLayer(opt.value); setLayerDropdownOpen(false); }}
                  className="w-full px-3 py-2 text-left text-sm"
                  style={{ color: opt.value === layer ? 'var(--accent)' : 'var(--text-primary)', background: opt.value === layer ? 'var(--accent-subtle)' : 'transparent' }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* SidePanel */}
      <SidePanel
        open={selectedId != null}
        onClose={handleClose}
        title="Saúde da Rede"
        subtitle={selectedName || 'Análise regional'}
      >
        <div className="space-y-5">
          {panelLoading && (
            <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-current" style={{ borderTopColor: 'transparent' }} />
              Carregando dados...
            </div>
          )}

          {/* Weather risk from real API */}
          {weatherData && (
            <div>
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                <CloudRain size={14} /> Risco Climático
              </h4>
              <div className="space-y-2">
                <div className="flex items-center justify-between py-1.5" style={{ borderBottom: '1px solid var(--border)' }}>
                  <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Score geral</span>
                  <span className="text-sm font-medium" style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                    {(weatherData.overall_risk_score ?? 0).toFixed(0)} / 100
                  </span>
                </div>
                <div className="flex items-center justify-between py-1.5" style={{ borderBottom: '1px solid var(--border)' }}>
                  <span className="flex items-center gap-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    <Droplets size={12} /> Precipitação
                  </span>
                  <span className={riskBadgeClass(weatherData.precipitation_risk)}>
                    {riskLabel(weatherData.precipitation_risk)}
                  </span>
                </div>
                <div className="flex items-center justify-between py-1.5" style={{ borderBottom: '1px solid var(--border)' }}>
                  <span className="flex items-center gap-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    <Wind size={12} /> Vento
                  </span>
                  <span className={riskBadgeClass(weatherData.wind_risk)}>
                    {riskLabel(weatherData.wind_risk)}
                  </span>
                </div>
                <div className="flex items-center justify-between py-1.5" style={{ borderBottom: '1px solid var(--border)' }}>
                  <span className="flex items-center gap-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    <Thermometer size={12} /> Temperatura
                  </span>
                  <span className={riskBadgeClass(weatherData.temperature_risk)}>
                    {riskLabel(weatherData.temperature_risk)}
                  </span>
                </div>
                {weatherData.details?.pattern_description && (
                  <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                    {weatherData.details.pattern_description}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Maintenance priority from real API */}
          {selectedMaintenance && (
            <div>
              <h4 className="text-sm font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                <Wrench size={14} /> Prioridade de Manutenção
              </h4>
              <div className="space-y-2">
                <KeyValue
                  icon={<Activity size={14} />}
                  label="Score de prioridade"
                  value={`${(selectedMaintenance.priority_score ?? 0).toFixed(1)} / 100`}
                />
                <KeyValue
                  icon={<CloudRain size={14} />}
                  label="Risco climático"
                  value={`${(selectedMaintenance.weather_risk_score ?? 0).toFixed(0)}`}
                />
                <KeyValue
                  icon={<Activity size={14} />}
                  label="Tendência de qualidade"
                  value={`${(selectedMaintenance.quality_trend_score ?? 0).toFixed(0)}`}
                />
                <KeyValue
                  icon={<AlertTriangle size={14} />}
                  label="Prazo"
                  value={timingLabel(selectedMaintenance.timing)}
                />
              </div>
            </div>
          )}

          {/* Recommended action from real API */}
          {selectedMaintenance?.recommended_action && (
            <div>
              <h4 className="text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>Ação Recomendada</h4>
              <p className="text-sm" style={{ color: 'var(--text-primary)' }}>
                {selectedMaintenance.recommended_action}
              </p>
            </div>
          )}

          {/* Fusion: infrastructure gaps & competition quality */}
          {fusionLoading && (
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Carregando inteligência...</p>
          )}
          {fusionData && (
            <div>
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                <Shield size={14} /> Indicadores de Infraestrutura
              </h4>
              <div className="space-y-2">
                <KeyValue
                  icon={<School size={14} />}
                  label="Escolas sem internet"
                  value={`${fusionData.infrastructure.schools_offline} / ${fusionData.infrastructure.schools_total}`}
                />
                <KeyValue
                  icon={<Building2 size={14} />}
                  label="Unidades de saúde offline"
                  value={`${fusionData.infrastructure.health_offline} / ${fusionData.infrastructure.health_total}`}
                />
                {fusionData.competition.avg_quality_score != null && (
                  <KeyValue
                    icon={<Activity size={14} />}
                    label="Qualidade média da rede"
                    value={`${(fusionData.competition.avg_quality_score ?? 0).toFixed(1)} / 100`}
                  />
                )}
                {fusionData.safety.risk_score != null && (
                  <KeyValue
                    icon={<AlertTriangle size={14} />}
                    label="Risco de segurança"
                    value={`${(fusionData.safety.risk_score ?? 0).toFixed(0)} / 100`}
                  />
                )}
              </div>
            </div>
          )}

          {/* Empty state */}
          {!panelLoading && !fusionLoading && !weatherData && !selectedMaintenance && !fusionData && (
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              Sem dados disponíveis para este município.
            </p>
          )}
        </div>
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
