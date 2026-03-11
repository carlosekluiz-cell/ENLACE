'use client';

import { useState } from 'react';
import SimpleChart from '@/components/charts/SimpleChart';
import { useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type {
  CoverageRequest,
  CoverageResult,
  OptimizeRequest,
  LinkBudgetRequest,
} from '@/lib/types';
import {
  Antenna,
  Radio,
  Mountain,
  Zap,
  MapPin,
  Signal,
  Ruler,
  Maximize2,
  Send,
} from 'lucide-react';
import { clsx } from 'clsx';
import { formatDecimal } from '@/lib/format';

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

type TabKey = 'coverage' | 'optimize' | 'linkbudget' | 'terrain';

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'coverage', label: 'Cobertura RF', icon: <Signal size={16} /> },
  { key: 'optimize', label: 'Otimização de Torres', icon: <Antenna size={16} /> },
  { key: 'linkbudget', label: 'Link Budget', icon: <Radio size={16} /> },
  { key: 'terrain', label: 'Perfil de Terreno', icon: <Mountain size={16} /> },
];

const FREQ_OPTIONS = ['700', '850', '1800', '2100', '2600', '3500'];

// ---------------------------------------------------------------------------
// Inline stats card (replaces StatsCard)
// ---------------------------------------------------------------------------

function StatBox({
  title,
  value,
  icon,
  subtitle,
  loading,
}: {
  title: string;
  value: string;
  icon?: React.ReactNode;
  subtitle?: string;
  loading?: boolean;
}) {
  return (
    <div className="pulso-card">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>{title}</p>
          <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            {loading ? 'Carregando...' : value}
          </p>
          {subtitle && <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{subtitle}</p>}
        </div>
        {icon && <div>{icon}</div>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function DesignPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('coverage');

  // -- Tab 1: Cobertura RF
  const [covLat, setCovLat] = useState('-15.7939');
  const [covLon, setCovLon] = useState('-47.8828');
  const [covHeight, setCovHeight] = useState('30');
  const [covFreq, setCovFreq] = useState('700');
  const [covPower, setCovPower] = useState('43');
  const [covGain, setCovGain] = useState('15');
  const [covRadius, setCovRadius] = useState('5000');
  const [covResolution, setCovResolution] = useState('50');
  const [covVegetation, setCovVegetation] = useState(true);

  const {
    data: coverageData,
    loading: coverageLoading,
    error: coverageError,
    execute: executeCoverage,
  } = useLazyApi<CoverageResult, CoverageRequest>((params) =>
    api.design.coverage(params)
  );

  const handleCoverage = () => {
    const params: CoverageRequest = {
      tower_lat: parseFloat(covLat),
      tower_lon: parseFloat(covLon),
      tower_height_m: parseFloat(covHeight),
      frequency_mhz: parseInt(covFreq, 10),
      tx_power_dbm: parseFloat(covPower),
      antenna_gain_dbi: parseFloat(covGain),
      radius_m: parseFloat(covRadius),
      grid_resolution_m: parseFloat(covResolution),
      apply_vegetation: covVegetation,
      country_code: 'BRA',
    };
    executeCoverage(params);
  };

  // -- Tab 2: Otimização de Torres
  const [optLat, setOptLat] = useState('-15.7939');
  const [optLon, setOptLon] = useState('-47.8828');
  const [optRadius, setOptRadius] = useState('5000');
  const [optTarget, setOptTarget] = useState('95');
  const [optMinSignal, setOptMinSignal] = useState('-95');
  const [optMaxTowers, setOptMaxTowers] = useState('20');
  const [optFreq, setOptFreq] = useState('700');
  const [optPower, setOptPower] = useState('43');
  const [optGain, setOptGain] = useState('15');
  const [optAntennaHeight, setOptAntennaHeight] = useState('30');

  const {
    data: optimizeData,
    loading: optimizeLoading,
    error: optimizeError,
    execute: executeOptimize,
  } = useLazyApi<any, OptimizeRequest>((params) =>
    api.design.optimize(params)
  );

  const handleOptimize = () => {
    const params: OptimizeRequest = {
      center_lat: parseFloat(optLat),
      center_lon: parseFloat(optLon),
      radius_m: parseFloat(optRadius),
      coverage_target_pct: parseFloat(optTarget),
      min_signal_dbm: parseFloat(optMinSignal),
      max_towers: parseInt(optMaxTowers, 10),
      frequency_mhz: parseInt(optFreq, 10),
      tx_power_dbm: parseFloat(optPower),
      antenna_gain_dbi: parseFloat(optGain),
      antenna_height_m: parseFloat(optAntennaHeight),
    };
    executeOptimize(params);
  };

  // -- Tab 3: Link Budget
  const [lbFreq, setLbFreq] = useState('18');
  const [lbDist, setLbDist] = useState('10');
  const [lbPower, setLbPower] = useState('20');
  const [lbTxGain, setLbTxGain] = useState('38');
  const [lbRxGain, setLbRxGain] = useState('38');
  const [lbThreshold, setLbThreshold] = useState('-70');
  const [lbRain, setLbRain] = useState('145');

  const {
    data: linkData,
    loading: linkLoading,
    error: linkError,
    execute: executeLink,
  } = useLazyApi<any, LinkBudgetRequest>((params) =>
    api.design.linkBudget(params)
  );

  const handleLinkBudget = () => {
    const params: LinkBudgetRequest = {
      frequency_ghz: parseFloat(lbFreq),
      distance_km: parseFloat(lbDist),
      tx_power_dbm: parseFloat(lbPower),
      tx_antenna_gain_dbi: parseFloat(lbTxGain),
      rx_antenna_gain_dbi: parseFloat(lbRxGain),
      rx_threshold_dbm: parseFloat(lbThreshold),
      rain_rate_mmh: parseFloat(lbRain),
    };
    executeLink(params);
  };

  // -- Tab 4: Perfil de Terreno
  const [tpStartLat, setTpStartLat] = useState('-15.7939');
  const [tpStartLon, setTpStartLon] = useState('-47.8828');
  const [tpEndLat, setTpEndLat] = useState('-15.8200');
  const [tpEndLon, setTpEndLon] = useState('-47.9100');
  const [tpStep, setTpStep] = useState('30');

  const {
    data: terrainData,
    loading: terrainLoading,
    error: terrainError,
    execute: executeTerrain,
  } = useLazyApi<any, { startLat: number; startLon: number; endLat: number; endLon: number; stepM: number }>(
    (p) => api.design.terrainProfile(p.startLat, p.startLon, p.endLat, p.endLon, p.stepM)
  );

  const handleTerrain = () => {
    executeTerrain({
      startLat: parseFloat(tpStartLat),
      startLon: parseFloat(tpStartLon),
      endLat: parseFloat(tpEndLat),
      endLon: parseFloat(tpEndLon),
      stepM: parseFloat(tpStep),
    });
  };

  // -- Helpers
  const fmtNum = (v: number | null | undefined, decimals = 1) =>
    formatDecimal(v, decimals);

  // Build terrain chart data
  const terrainChartData: { name: string; elevação: number }[] = [];
  if (terrainData?.points) {
    const profile = terrainData.points as { distance_m: number; elevation_m: number }[];
    for (const pt of profile) {
      terrainChartData.push({
        name: `${(pt.distance_m / 1000).toFixed(1)} km`,
        elevação: pt.elevation_m,
      });
    }
  }

  // -- Render

  return (
    <div className="space-y-6 p-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Projeto de Cobertura RF
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Simulação de cobertura, otimização de torres, link budget e perfil de terreno
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg p-1" style={{ backgroundColor: 'var(--bg-subtle)' }}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors"
            style={{
              backgroundColor: activeTab === tab.key ? 'var(--accent)' : 'transparent',
              color: activeTab === tab.key ? '#fff' : 'var(--text-secondary)',
            }}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB 1 -- Cobertura RF */}
      {activeTab === 'coverage' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Form panel */}
          <div className="pulso-card lg:col-span-1">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Signal size={16} style={{ color: 'var(--accent)' }} />
              Parâmetros de Cobertura
            </h2>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Latitude da Torre</label>
                  <input type="number" step="0.0001" value={covLat} onChange={(e) => setCovLat(e.target.value)} className="pulso-input w-full" />
                </div>
                <div>
                  <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Longitude da Torre</label>
                  <input type="number" step="0.0001" value={covLon} onChange={(e) => setCovLon(e.target.value)} className="pulso-input w-full" />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Altura da Torre (m)</label>
                <input type="number" value={covHeight} onChange={(e) => setCovHeight(e.target.value)} className="pulso-input w-full" />
              </div>

              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Frequência (MHz)</label>
                <select value={covFreq} onChange={(e) => setCovFreq(e.target.value)} className="pulso-input w-full">
                  {FREQ_OPTIONS.map((f) => (<option key={f} value={f}>{f} MHz</option>))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Potência TX (dBm)</label>
                  <input type="number" value={covPower} onChange={(e) => setCovPower(e.target.value)} className="pulso-input w-full" />
                </div>
                <div>
                  <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Ganho da Antena (dBi)</label>
                  <input type="number" value={covGain} onChange={(e) => setCovGain(e.target.value)} className="pulso-input w-full" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Raio (m)</label>
                  <input type="number" value={covRadius} onChange={(e) => setCovRadius(e.target.value)} className="pulso-input w-full" />
                </div>
                <div>
                  <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Resolução (m)</label>
                  <input type="number" value={covResolution} onChange={(e) => setCovResolution(e.target.value)} className="pulso-input w-full" />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <label className="relative inline-flex cursor-pointer items-center">
                  <input type="checkbox" checked={covVegetation} onChange={(e) => setCovVegetation(e.target.checked)} className="peer sr-only" />
                  <div className="h-5 w-9 rounded-full after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:after:translate-x-full" style={{ backgroundColor: covVegetation ? 'var(--accent)' : 'var(--bg-subtle)' }} />
                </label>
                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Correção de Vegetação</span>
              </div>

              <button
                onClick={handleCoverage}
                disabled={coverageLoading}
                className={clsx('pulso-btn-primary flex w-full items-center justify-center gap-2', coverageLoading && 'cursor-wait opacity-70')}
              >
                <Send size={16} />
                {coverageLoading ? 'Calculando...' : 'Calcular Cobertura'}
              </button>

              {coverageError && (
                <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)', color: 'var(--danger)' }}>
                  <span className="font-medium">Erro:</span> {coverageError}
                </div>
              )}
            </div>
          </div>

          {/* Results panel */}
          <div className="space-y-4 lg:col-span-2">
            {!coverageData && !coverageLoading && (
              <div className="pulso-card flex items-center justify-center py-16 text-sm" style={{ color: 'var(--text-muted)' }}>
                Defina os parâmetros e clique em &quot;Calcular Cobertura&quot; para visualizar os resultados.
              </div>
            )}

            {coverageLoading && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (<StatBox key={i} title="" value="" loading />))}
              </div>
            )}

            {coverageData && (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <StatBox title="Cobertura" value={`${fmtNum(coverageData.coverage_pct)}%`} icon={<Signal size={18} style={{ color: 'var(--accent)' }} />} subtitle="Percentual coberto" />
                  <StatBox title="Área de Cobertura" value={`${fmtNum(coverageData.coverage_area_km2, 2)} km2`} icon={<Maximize2 size={18} style={{ color: 'var(--success)' }} />} subtitle="Área total" />
                  <StatBox title="Sinal Médio" value={`${fmtNum(coverageData.avg_signal_dbm)} dBm`} icon={<Radio size={18} className="text-cyan-400" />} subtitle="Média na área" />
                  <StatBox title="Sinal Mínimo" value={`${fmtNum(coverageData.min_signal_dbm)} dBm`} icon={<Zap size={18} style={{ color: 'var(--warning)' }} />} subtitle="Pior caso" />
                </div>

                {/* Grid points summary */}
                <div className="pulso-card">
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    <MapPin size={16} style={{ color: 'var(--accent)' }} />
                    Grade de Cobertura
                  </h3>
                  <div className="space-y-3">
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                      <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                        <p className="text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Pontos da Grade</p>
                        <p className="mt-1 text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{(coverageData.grid?.length ?? 0).toLocaleString('pt-BR')}</p>
                      </div>
                      <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                        <p className="text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Sinal Máximo</p>
                        <p className="mt-1 text-lg font-bold" style={{ color: 'var(--success)' }}>{fmtNum(coverageData.max_signal_dbm)} dBm</p>
                      </div>
                      <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                        <p className="text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Resolução da Grade</p>
                        <p className="mt-1 text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{covResolution} m</p>
                      </div>
                    </div>

                    {/* Signal distribution summary */}
                    {(coverageData.grid?.length ?? 0) > 0 && (
                      <div className="rounded-lg p-4" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                        <p className="mb-2 text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Distribuição do Sinal</p>
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                          {[
                            { label: 'Excelente (> -65 dBm)', count: (coverageData.grid ?? []).filter(p => p.signal_dbm > -65).length, color: 'var(--success)' },
                            { label: 'Bom (-65 a -75 dBm)', count: (coverageData.grid ?? []).filter(p => p.signal_dbm <= -65 && p.signal_dbm > -75).length, color: 'var(--accent)' },
                            { label: 'Regular (-75 a -85 dBm)', count: (coverageData.grid ?? []).filter(p => p.signal_dbm <= -75 && p.signal_dbm > -85).length, color: 'var(--warning)' },
                            { label: 'Fraco (< -85 dBm)', count: (coverageData.grid ?? []).filter(p => p.signal_dbm <= -85).length, color: 'var(--danger)' },
                          ].map((band) => (
                            <div key={band.label} className="text-center">
                              <p className="text-lg font-bold" style={{ color: band.color }}>{band.count.toLocaleString('pt-BR')}</p>
                              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{band.label}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* TAB 2 -- Otimização de Torres */}
      {activeTab === 'optimize' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="pulso-card lg:col-span-1">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Antenna size={16} style={{ color: 'var(--accent)' }} />
              Parâmetros de Otimização
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Latitude Central</label><input type="number" step="0.0001" value={optLat} onChange={(e) => setOptLat(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Longitude Central</label><input type="number" step="0.0001" value={optLon} onChange={(e) => setOptLon(e.target.value)} className="pulso-input w-full" /></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Raio (m)</label><input type="number" value={optRadius} onChange={(e) => setOptRadius(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Cobertura Alvo (%)</label><input type="number" value={optTarget} onChange={(e) => setOptTarget(e.target.value)} className="pulso-input w-full" /></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Sinal Mínimo (dBm)</label><input type="number" value={optMinSignal} onChange={(e) => setOptMinSignal(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Max. Torres</label><input type="number" value={optMaxTowers} onChange={(e) => setOptMaxTowers(e.target.value)} className="pulso-input w-full" /></div>
              </div>
              <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Frequência (MHz)</label><input type="number" value={optFreq} onChange={(e) => setOptFreq(e.target.value)} className="pulso-input w-full" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Potência TX (dBm)</label><input type="number" value={optPower} onChange={(e) => setOptPower(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Ganho da Antena (dBi)</label><input type="number" value={optGain} onChange={(e) => setOptGain(e.target.value)} className="pulso-input w-full" /></div>
              </div>
              <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Altura da Antena (m)</label><input type="number" value={optAntennaHeight} onChange={(e) => setOptAntennaHeight(e.target.value)} className="pulso-input w-full" /></div>

              <button onClick={handleOptimize} disabled={optimizeLoading} className={clsx('pulso-btn-primary flex w-full items-center justify-center gap-2', optimizeLoading && 'cursor-wait opacity-70')}>
                <Antenna size={16} />
                {optimizeLoading ? 'Otimizando...' : 'Otimizar Posicionamento'}
              </button>

              {optimizeError && (
                <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)', color: 'var(--danger)' }}>
                  <span className="font-medium">Erro:</span> {optimizeError}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-4 lg:col-span-2">
            {!optimizeData && !optimizeLoading && (
              <div className="pulso-card flex items-center justify-center py-16 text-sm" style={{ color: 'var(--text-muted)' }}>
                Defina os parâmetros e clique em &quot;Otimizar Posicionamento&quot; para visualizar os resultados.
              </div>
            )}

            {optimizeLoading && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (<StatBox key={i} title="" value="" loading />))}
              </div>
            )}

            {optimizeData && (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <StatBox title="Torres Necessárias" value={String(optimizeData.tower_count ?? optimizeData.towers?.length ?? '---')} icon={<Antenna size={18} style={{ color: 'var(--accent)' }} />} subtitle="Posições otimizadas" />
                  <StatBox title="Cobertura Alcançada" value={optimizeData.coverage_achieved_pct != null ? `${fmtNum(optimizeData.coverage_achieved_pct)}%` : '---'} icon={<Signal size={18} style={{ color: 'var(--success)' }} />} subtitle={`Meta: ${optTarget}%`} />
                  <StatBox title="Área Coberta" value={optimizeData.coverage_area_km2 != null ? `${fmtNum(optimizeData.coverage_area_km2, 2)} km2` : '---'} icon={<Maximize2 size={18} className="text-cyan-400" />} subtitle="Estimativa" />
                  <StatBox title="CAPEX Estimado" value={optimizeData.estimated_capex_brl != null ? `R$ ${(optimizeData.estimated_capex_brl / 1000).toFixed(0)}k` : '---'} icon={<Zap size={18} style={{ color: 'var(--warning)' }} />} subtitle="Investimento total" />
                </div>

                {optimizeData.towers && optimizeData.towers.length > 0 && (
                  <div className="pulso-card">
                    <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                      <MapPin size={16} style={{ color: 'var(--accent)' }} />
                      Posições das Torres
                    </h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-xs uppercase" style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                            <th className="pb-2 pr-4 font-medium">#</th>
                            <th className="pb-2 pr-4 font-medium">Latitude</th>
                            <th className="pb-2 pr-4 font-medium">Longitude</th>
                            <th className="pb-2 pr-4 font-medium">Altura (m)</th>
                            <th className="pb-2 font-medium">Cobertura (%)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {optimizeData.towers.map((tower: any, idx: number) => (
                            <tr key={idx} style={{ borderBottom: '1px solid color-mix(in srgb, var(--border) 50%, transparent)', color: 'var(--text-secondary)' }}>
                              <td className="py-2 pr-4 font-medium" style={{ color: 'var(--text-primary)' }}>{idx + 1}</td>
                              <td className="py-2 pr-4">{tower.lat?.toFixed(4) ?? tower.latitude?.toFixed(4) ?? '---'}</td>
                              <td className="py-2 pr-4">{tower.lon?.toFixed(4) ?? tower.longitude?.toFixed(4) ?? '---'}</td>
                              <td className="py-2 pr-4">{tower.height_m ?? tower.antenna_height_m ?? optAntennaHeight}</td>
                              <td className="py-2">{tower.coverage_pct != null ? <span className="font-semibold" style={{ color: 'var(--success)' }}>{fmtNum(tower.coverage_pct)}%</span> : '---'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {optimizeData.notes && optimizeData.notes.length > 0 && (
                  <div className="pulso-card">
                    <h3 className="mb-2 text-xs font-semibold uppercase" style={{ color: 'var(--text-secondary)' }}>Observações</h3>
                    <ul className="space-y-1">
                      {optimizeData.notes.map((note: string, idx: number) => (
                        <li key={idx} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                          <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ backgroundColor: 'var(--accent)' }} />
                          {note}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* TAB 3 -- Link Budget */}
      {activeTab === 'linkbudget' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="pulso-card lg:col-span-1">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Radio size={16} style={{ color: 'var(--accent)' }} />
              Parâmetros do Link Budget
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Frequência (GHz)</label><input type="number" value={lbFreq} onChange={(e) => setLbFreq(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Distância (km)</label><input type="number" value={lbDist} onChange={(e) => setLbDist(e.target.value)} className="pulso-input w-full" /></div>
              </div>
              <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Potência TX (dBm)</label><input type="number" value={lbPower} onChange={(e) => setLbPower(e.target.value)} className="pulso-input w-full" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Ganho Antena TX (dBi)</label><input type="number" value={lbTxGain} onChange={(e) => setLbTxGain(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Ganho Antena RX (dBi)</label><input type="number" value={lbRxGain} onChange={(e) => setLbRxGain(e.target.value)} className="pulso-input w-full" /></div>
              </div>
              <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Limiar RX (dBm)</label><input type="number" value={lbThreshold} onChange={(e) => setLbThreshold(e.target.value)} className="pulso-input w-full" /></div>
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Taxa de Chuva (mm/h)</label>
                <input type="number" value={lbRain} onChange={(e) => setLbRain(e.target.value)} className="pulso-input w-full" />
                <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Padrão tropical Brasil</p>
              </div>

              <button onClick={handleLinkBudget} disabled={linkLoading} className={clsx('pulso-btn-primary flex w-full items-center justify-center gap-2', linkLoading && 'cursor-wait opacity-70')}>
                <Ruler size={16} />
                {linkLoading ? 'Calculando...' : 'Calcular Link Budget'}
              </button>

              {linkError && (
                <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)', color: 'var(--danger)' }}>
                  <span className="font-medium">Erro:</span> {linkError}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-4 lg:col-span-2">
            {!linkData && !linkLoading && (
              <div className="pulso-card flex items-center justify-center py-16 text-sm" style={{ color: 'var(--text-muted)' }}>
                Defina os parâmetros e clique em &quot;Calcular Link Budget&quot; para visualizar os resultados.
              </div>
            )}

            {linkLoading && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {[1, 2, 3, 4, 5, 6].map((i) => (<StatBox key={i} title="" value="" loading />))}
              </div>
            )}

            {linkData && (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <StatBox title="EIRP" value={linkData.eirp_dbm != null ? `${fmtNum(linkData.eirp_dbm)} dBm` : '---'} icon={<Zap size={18} style={{ color: 'var(--accent)' }} />} subtitle="Potência efetiva irradiada" />
                  <StatBox title="Perda no Espaço Livre" value={linkData.free_space_loss_db != null ? `${fmtNum(linkData.free_space_loss_db)} dB` : '---'} icon={<Ruler size={18} className="text-cyan-400" />} subtitle="FSL" />
                  <StatBox title="Atenuação por Chuva" value={linkData.rain_attenuation_db != null ? `${fmtNum(linkData.rain_attenuation_db)} dB` : '---'} icon={<Mountain size={18} style={{ color: 'var(--warning)' }} />} subtitle={`${lbRain} mm/h`} />
                  <StatBox title="Sinal Recebido" value={linkData.received_power_dbm != null ? `${fmtNum(linkData.received_power_dbm)} dBm` : '---'} icon={<Signal size={18} style={{ color: 'var(--success)' }} />} subtitle="Nível no receptor" />
                  <StatBox title="Margem de Desvanecimento" value={linkData.fade_margin_db != null ? `${fmtNum(linkData.fade_margin_db)} dB` : '---'} icon={<Radio size={18} style={{ color: linkData.fade_margin_db != null && linkData.fade_margin_db > 0 ? 'var(--success)' : 'var(--danger)' }} />} subtitle={linkData.fade_margin_db != null ? (linkData.fade_margin_db > 0 ? 'Link viável' : 'Link inviável') : ''} />
                  <StatBox title="Disponibilidade" value={linkData.availability_pct != null ? `${fmtNum(linkData.availability_pct, 4)}%` : '---'} icon={<Maximize2 size={18} className="text-purple-400" />} subtitle="Estimativa anual" />
                </div>

                <div className="pulso-card">
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    <Radio size={16} style={{ color: 'var(--accent)' }} />
                    Detalhamento do Link
                  </h3>
                  <div className="space-y-2">
                    {[
                      { label: 'Frequência', value: `${lbFreq} GHz` },
                      { label: 'Distância', value: `${lbDist} km` },
                      { label: 'Potência TX', value: `${lbPower} dBm` },
                      { label: 'Ganho Antena TX', value: `${lbTxGain} dBi` },
                      { label: 'Ganho Antena RX', value: `${lbRxGain} dBi` },
                      { label: 'EIRP', value: linkData.eirp_dbm != null ? `${fmtNum(linkData.eirp_dbm)} dBm` : '---' },
                      { label: 'Perda no Espaço Livre (FSL)', value: linkData.free_space_loss_db != null ? `${fmtNum(linkData.free_space_loss_db)} dB` : '---' },
                      { label: 'Atenuação por Chuva', value: linkData.rain_attenuation_db != null ? `${fmtNum(linkData.rain_attenuation_db)} dB` : '---' },
                      { label: 'Perdas Totais', value: linkData.total_loss_db != null ? `${fmtNum(linkData.total_loss_db)} dB` : '---' },
                      { label: 'Sinal Recebido', value: linkData.received_power_dbm != null ? `${fmtNum(linkData.received_power_dbm)} dBm` : '---' },
                      { label: 'Limiar RX', value: `${lbThreshold} dBm` },
                      { label: 'Margem de Desvanecimento', value: linkData.fade_margin_db != null ? `${fmtNum(linkData.fade_margin_db)} dB` : '---', highlight: true },
                      { label: 'Disponibilidade', value: linkData.availability_pct != null ? `${fmtNum(linkData.availability_pct, 4)}%` : '---', highlight: true },
                    ].map((row) => (
                      <div key={row.label} className={clsx('flex justify-between text-sm', row.highlight ? 'pt-2' : '')} style={row.highlight ? { borderTop: '1px solid var(--border)' } : undefined}>
                        <span style={{ color: row.highlight ? 'var(--text-secondary)' : 'var(--text-secondary)' }}>{row.label}</span>
                        <span className="font-semibold" style={{ color: row.highlight ? 'var(--accent)' : 'var(--text-primary)' }}>{row.value}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pulso-card flex items-center justify-between">
                  <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Status do Enlace</span>
                  {linkData.fade_margin_db != null ? (
                    linkData.fade_margin_db > 0 ? (
                      <span className="pulso-badge-green flex items-center gap-1">
                        <Signal size={14} />
                        Enlace Viável - Margem de {fmtNum(linkData.fade_margin_db)} dB
                      </span>
                    ) : (
                      <span className="pulso-badge-red flex items-center gap-1">
                        <Zap size={14} />
                        Enlace Inviável - Margem insuficiente
                      </span>
                    )
                  ) : (
                    <span className="text-sm" style={{ color: 'var(--text-muted)' }}>---</span>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* TAB 4 -- Perfil de Terreno */}
      {activeTab === 'terrain' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="pulso-card lg:col-span-1">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Mountain size={16} style={{ color: 'var(--accent)' }} />
              Parâmetros do Perfil
            </h2>
            <div className="space-y-4">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Ponto de Início</p>
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Latitude Início</label><input type="number" step="0.0001" value={tpStartLat} onChange={(e) => setTpStartLat(e.target.value)} className="pulso-input w-full" /></div>
                  <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Longitude Início</label><input type="number" step="0.0001" value={tpStartLon} onChange={(e) => setTpStartLon(e.target.value)} className="pulso-input w-full" /></div>
                </div>
              </div>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Ponto Final</p>
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Latitude Fim</label><input type="number" step="0.0001" value={tpEndLat} onChange={(e) => setTpEndLat(e.target.value)} className="pulso-input w-full" /></div>
                  <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Longitude Fim</label><input type="number" step="0.0001" value={tpEndLon} onChange={(e) => setTpEndLon(e.target.value)} className="pulso-input w-full" /></div>
                </div>
              </div>
              <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Passo (m)</label><input type="number" value={tpStep} onChange={(e) => setTpStep(e.target.value)} className="pulso-input w-full" /></div>

              <button onClick={handleTerrain} disabled={terrainLoading} className={clsx('pulso-btn-primary flex w-full items-center justify-center gap-2', terrainLoading && 'cursor-wait opacity-70')}>
                <Mountain size={16} />
                {terrainLoading ? 'Calculando...' : 'Extrair Perfil'}
              </button>

              {terrainError && (
                <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)', color: 'var(--danger)' }}>
                  <span className="font-medium">Erro:</span> {terrainError}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-4 lg:col-span-2">
            {!terrainData && !terrainLoading && (
              <div className="pulso-card flex items-center justify-center py-16 text-sm" style={{ color: 'var(--text-muted)' }}>
                Defina os pontos de início e fim e clique em &quot;Extrair Perfil&quot; para visualizar o terreno.
              </div>
            )}

            {terrainLoading && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  {[1, 2, 3].map((i) => (<StatBox key={i} title="" value="" loading />))}
                </div>
                <SimpleChart data={[]} type="line" title="Perfil de Elevação" loading height={300} />
              </div>
            )}

            {terrainData && (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <StatBox title="Distância Total" value={terrainData.total_distance_m != null ? `${fmtNum(terrainData.total_distance_m / 1000, 2)} km` : '---'} icon={<Ruler size={18} style={{ color: 'var(--accent)' }} />} subtitle="Entre os pontos" />
                  <StatBox title="Elevação Máxima" value={terrainData.max_elevation_m != null ? `${fmtNum(terrainData.max_elevation_m, 0)} m` : '---'} icon={<Mountain size={18} style={{ color: 'var(--success)' }} />} subtitle="Ponto mais alto" />
                  <StatBox title="Elevação Mínima" value={terrainData.min_elevation_m != null ? `${fmtNum(terrainData.min_elevation_m, 0)} m` : '---'} icon={<MapPin size={18} style={{ color: 'var(--warning)' }} />} subtitle="Ponto mais baixo" />
                  <StatBox title="Pontos Amostrados" value={terrainData.points?.length?.toLocaleString('pt-BR') ?? '---'} icon={<Maximize2 size={18} className="text-cyan-400" />} subtitle={`Passo: ${tpStep} m`} />
                </div>

                {terrainChartData.length > 0 && (
                  <SimpleChart data={terrainChartData} type="line" xKey="name" yKey="elevação" title="Perfil de Elevação (m)" height={350} />
                )}

                {terrainData.points && terrainData.points.length > 1 && (
                  <div className="pulso-card">
                    <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                      <Mountain size={16} style={{ color: 'var(--accent)' }} />
                      Resumo do Terreno
                    </h3>
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                      {(() => {
                        const elevations = terrainData.points.map((p: any) => p.elevation_m);
                        const maxElev = Math.max(...elevations);
                        const minElev = Math.min(...elevations);
                        const avgElev = elevations.reduce((a: number, b: number) => a + b, 0) / elevations.length;
                        const startElev = elevations[0];
                        const endElev = elevations[elevations.length - 1];
                        return (
                          <>
                            <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                              <p className="text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Desnivel Total</p>
                              <p className="mt-1 text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{fmtNum(maxElev - minElev, 0)} m</p>
                            </div>
                            <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                              <p className="text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Elevação Média</p>
                              <p className="mt-1 text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{fmtNum(avgElev, 0)} m</p>
                            </div>
                            <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                              <p className="text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Diferença Início/Fim</p>
                              <p className="mt-1 text-lg font-bold" style={{ color: endElev >= startElev ? 'var(--success)' : 'var(--danger)' }}>
                                {endElev >= startElev ? '+' : ''}{fmtNum(endElev - startElev, 0)} m
                              </p>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
