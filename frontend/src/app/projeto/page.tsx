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
  FtthDesignRequest,
  FtthDesignResult,
  OpticalBudgetRequest,
  OpticalBudgetResult,
  ViabilityRequest,
  ViabilityResult,
} from '@/lib/types';
import {
  Cable,
  Antenna,
  Radio,
  Mountain,
  Zap,
  MapPin,
  Signal,
  Ruler,
  Maximize2,
  Send,
  DollarSign,
  TrendingUp,
  Users,
  BarChart3,
  CheckCircle,
  AlertTriangle,
  XCircle,
} from 'lucide-react';
import { clsx } from 'clsx';
import { formatDecimal, formatBRL, formatCompact, formatPct } from '@/lib/format';

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

type TabKey = 'ftth' | 'wireless' | 'linkbudget' | 'viability' | 'terrain';

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'ftth', label: 'Projeto FTTH', icon: <Cable size={16} /> },
  { key: 'wireless', label: 'Cobertura Wireless', icon: <Signal size={16} /> },
  { key: 'linkbudget', label: 'Link Budget', icon: <Radio size={16} /> },
  { key: 'viability', label: 'Viabilidade', icon: <DollarSign size={16} /> },
  { key: 'terrain', label: 'Perfil de Terreno', icon: <Mountain size={16} /> },
];

const FREQ_OPTIONS = ['700', '850', '1800', '2100', '2600', '3500'];

// ---------------------------------------------------------------------------
// Stat card
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
  const [activeTab, setActiveTab] = useState<TabKey>('ftth');

  // ═══════════════════════════════════════════════════════════════════════════
  // Tab 1: Projeto FTTH (NEW)
  // ═══════════════════════════════════════════════════════════════════════════

  const [ftthLat, setFtthLat] = useState('-15.7939');
  const [ftthLon, setFtthLon] = useState('-47.8828');
  const [ftthRadius, setFtthRadius] = useState('3');
  const [ftthSubs, setFtthSubs] = useState('1000');
  const [ftthTech, setFtthTech] = useState<'GPON' | 'XGS-PON'>('GPON');
  const [ftthSplit, setFtthSplit] = useState('32');
  const [ftthCascade, setFtthCascade] = useState('2');
  const [ftthDeploy, setFtthDeploy] = useState<'aerial' | 'underground' | 'mixed'>('aerial');

  const {
    data: ftthData,
    loading: ftthLoading,
    error: ftthError,
    execute: executeFtth,
  } = useLazyApi<FtthDesignResult, FtthDesignRequest>((params) =>
    api.design.ftthDesign(params)
  );

  const handleFtth = () => {
    executeFtth({
      lat: parseFloat(ftthLat),
      lon: parseFloat(ftthLon),
      radius_km: parseFloat(ftthRadius),
      subscribers: parseInt(ftthSubs, 10),
      technology: ftthTech,
      split_ratio: parseInt(ftthSplit, 10),
      cascade_levels: parseInt(ftthCascade, 10),
      deployment_type: ftthDeploy,
    });
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // Tab 2: Cobertura Wireless (merged coverage + optimization)
  // ═══════════════════════════════════════════════════════════════════════════

  const [covLat, setCovLat] = useState('-15.7939');
  const [covLon, setCovLon] = useState('-47.8828');
  const [covHeight, setCovHeight] = useState('30');
  const [covFreq, setCovFreq] = useState('700');
  const [covPower, setCovPower] = useState('43');
  const [covGain, setCovGain] = useState('15');
  const [covRadius, setCovRadius] = useState('5000');
  const [covResolution, setCovResolution] = useState('50');
  const [covVegetation, setCovVegetation] = useState(true);
  const [showOptimize, setShowOptimize] = useState(false);
  const [optMaxTowers, setOptMaxTowers] = useState('20');
  const [optTarget, setOptTarget] = useState('95');
  const [optMinSignal, setOptMinSignal] = useState('-95');

  const {
    data: coverageData,
    loading: coverageLoading,
    error: coverageError,
    execute: executeCoverage,
  } = useLazyApi<CoverageResult, CoverageRequest>((params) =>
    api.design.coverage(params)
  );

  const handleCoverage = () => {
    executeCoverage({
      tower_lat: parseFloat(covLat),
      tower_lon: parseFloat(covLon),
      tower_height_m: parseFloat(covHeight),
      frequency_mhz: parseInt(covFreq, 10),
      tx_power_dbm: parseFloat(covPower),
      antenna_gain_dbi: parseFloat(covGain),
      radius_m: parseFloat(covRadius),
      grid_resolution_m: parseFloat(covResolution),
      apply_vegetation: covVegetation,
      country_code: typeof window !== 'undefined' ? (localStorage.getItem('pulso_country') || 'BR') : 'BR',
    });
  };

  const {
    data: optimizeData,
    loading: optimizeLoading,
    error: optimizeError,
    execute: executeOptimize,
  } = useLazyApi<any, OptimizeRequest>((params) =>
    api.design.optimize(params)
  );

  const handleOptimize = () => {
    executeOptimize({
      center_lat: parseFloat(covLat),
      center_lon: parseFloat(covLon),
      radius_m: parseFloat(covRadius),
      coverage_target_pct: parseFloat(optTarget),
      min_signal_dbm: parseFloat(optMinSignal),
      max_towers: parseInt(optMaxTowers, 10),
      frequency_mhz: parseInt(covFreq, 10),
      tx_power_dbm: parseFloat(covPower),
      antenna_gain_dbi: parseFloat(covGain),
      antenna_height_m: parseFloat(covHeight),
    });
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // Tab 3: Link Budget (dual: microwave + optical)
  // ═══════════════════════════════════════════════════════════════════════════

  const [lbMode, setLbMode] = useState<'microwave' | 'optical'>('microwave');

  // Microwave state
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
    executeLink({
      frequency_ghz: parseFloat(lbFreq),
      distance_km: parseFloat(lbDist),
      tx_power_dbm: parseFloat(lbPower),
      tx_antenna_gain_dbi: parseFloat(lbTxGain),
      rx_antenna_gain_dbi: parseFloat(lbRxGain),
      rx_threshold_dbm: parseFloat(lbThreshold),
      rain_rate_mmh: parseFloat(lbRain),
    });
  };

  // Optical state
  const [obFiber, setObFiber] = useState('5');
  const [obSplices, setObSplices] = useState('3');
  const [obConnectors, setObConnectors] = useState('4');
  const [obSplit1, setObSplit1] = useState('4');
  const [obSplit2, setObSplit2] = useState('8');
  const [obTech, setObTech] = useState<'GPON' | 'XGS-PON'>('GPON');

  const {
    data: opticalData,
    loading: opticalLoading,
    error: opticalError,
    execute: executeOptical,
  } = useLazyApi<OpticalBudgetResult, OpticalBudgetRequest>((params) =>
    api.design.opticalBudget(params)
  );

  const handleOpticalBudget = () => {
    const ratios = [parseInt(obSplit1, 10)];
    if (parseInt(obSplit2, 10) > 0) ratios.push(parseInt(obSplit2, 10));
    executeOptical({
      fiber_km: parseFloat(obFiber),
      splices: parseInt(obSplices, 10),
      connectors: parseInt(obConnectors, 10),
      splitter_ratios: ratios,
      technology: obTech,
    });
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // Tab 4: Viabilidade (NEW)
  // ═══════════════════════════════════════════════════════════════════════════

  const [viaMuniSearch, setViaMuniSearch] = useState('');
  const [viaMuniId, setViaMuniId] = useState<number | null>(null);
  const [viaMuniName, setViaMuniName] = useState('');
  const [viaTech, setViaTech] = useState<'FTTH' | 'FWA' | 'Hibrido'>('FTTH');
  const [viaSubs, setViaSubs] = useState('1000');
  const [viaArpu, setViaArpu] = useState('89.90');
  const [muniResults, setMuniResults] = useState<{ id: number; name: string; state_abbrev: string }[]>([]);
  const [showMuniDropdown, setShowMuniDropdown] = useState(false);

  const {
    data: viaData,
    loading: viaLoading,
    error: viaError,
    execute: executeVia,
  } = useLazyApi<ViabilityResult, ViabilityRequest>((params) =>
    api.design.viability(params)
  );

  const searchMunicipalities = async (q: string) => {
    setViaMuniSearch(q);
    if (q.length < 2) { setMuniResults([]); setShowMuniDropdown(false); return; }
    try {
      const results = await api.geo.search(q, 10);
      setMuniResults(results);
      setShowMuniDropdown(true);
    } catch { setMuniResults([]); }
  };

  const selectMuni = (m: { id: number; name: string; state_abbrev: string }) => {
    setViaMuniId(m.id);
    setViaMuniName(`${m.name} - ${m.state_abbrev}`);
    setViaMuniSearch(`${m.name} - ${m.state_abbrev}`);
    setShowMuniDropdown(false);
  };

  const handleViability = () => {
    if (!viaMuniId) return;
    executeVia({
      l2_id: viaMuniId,
      technology: viaTech,
      subscribers: parseInt(viaSubs, 10),
      arpu: parseFloat(viaArpu),
    });
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // Tab 5: Perfil de Terreno (unchanged logic)
  // ═══════════════════════════════════════════════════════════════════════════

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

  // Helpers
  const fmtNum = (v: number | null | undefined, decimals = 1) => formatDecimal(v, decimals);

  const terrainChartData: { name: string; elevação: number }[] = [];
  if (terrainData?.points) {
    for (const pt of terrainData.points as { distance_m: number; elevation_m: number }[]) {
      terrainChartData.push({ name: `${(pt.distance_m / 1000).toFixed(1)} km`, elevação: pt.elevation_m });
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Render
  // ═══════════════════════════════════════════════════════════════════════════

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Projeto de Rede
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Projeto FTTH, cobertura wireless, link budget, viabilidade econômica e perfil de terreno
        </p>
      </div>

      {/* Engineering disclaimer */}
      <div className="flex items-start gap-3 rounded-lg border px-4 py-3" style={{ borderColor: 'var(--warning, #f59e0b)', backgroundColor: 'rgba(245,158,11,0.06)' }}>
        <AlertTriangle size={18} className="mt-0.5 shrink-0" style={{ color: 'var(--warning, #f59e0b)' }} />
        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          <strong style={{ color: 'var(--text-primary)' }}>Ferramenta de apoio à decisão.</strong>{' '}
          Os cálculos e estimativas apresentados são referências técnicas para planejamento preliminar.
          Projetos de telecomunicações devem ser elaborados e assinados por engenheiro habilitado com registro
          ativo no CREA, conforme Lei 5.194/66 e Resolução CONFEA 218/73. A Pulso Network não se responsabiliza
          pelo uso dos resultados sem validação por profissional competente.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-1 rounded-lg p-1" style={{ backgroundColor: 'var(--bg-subtle)' }}>
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

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 1 — Projeto FTTH
          ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'ftth' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="pulso-card lg:col-span-1">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Cable size={16} style={{ color: 'var(--accent)' }} />
              Parâmetros FTTH
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Latitude OLT</label><input type="number" step="0.0001" value={ftthLat} onChange={(e) => setFtthLat(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Longitude OLT</label><input type="number" step="0.0001" value={ftthLon} onChange={(e) => setFtthLon(e.target.value)} className="pulso-input w-full" /></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Raio (km)</label><input type="number" step="0.5" value={ftthRadius} onChange={(e) => setFtthRadius(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Assinantes</label><input type="number" value={ftthSubs} onChange={(e) => setFtthSubs(e.target.value)} className="pulso-input w-full" /></div>
              </div>
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Tecnologia PON</label>
                <div className="flex gap-2">
                  {(['GPON', 'XGS-PON'] as const).map((t) => (
                    <button key={t} onClick={() => setFtthTech(t)} className={clsx('flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors', ftthTech === t ? 'text-white' : '')} style={{ backgroundColor: ftthTech === t ? 'var(--accent)' : 'var(--bg-subtle)', color: ftthTech === t ? '#fff' : 'var(--text-secondary)' }}>{t}</button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Split Ratio</label>
                  <select value={ftthSplit} onChange={(e) => setFtthSplit(e.target.value)} className="pulso-input w-full">
                    {['16', '32', '64'].map((s) => (<option key={s} value={s}>1:{s}</option>))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Cascata</label>
                  <select value={ftthCascade} onChange={(e) => setFtthCascade(e.target.value)} className="pulso-input w-full">
                    <option value="1">1 nível</option>
                    <option value="2">2 níveis</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Implantação</label>
                <select value={ftthDeploy} onChange={(e) => setFtthDeploy(e.target.value as any)} className="pulso-input w-full">
                  <option value="aerial">Aérea</option>
                  <option value="underground">Subterrânea</option>
                  <option value="mixed">Mista</option>
                </select>
              </div>

              <button onClick={handleFtth} disabled={ftthLoading} className={clsx('pulso-btn-primary flex w-full items-center justify-center gap-2', ftthLoading && 'cursor-wait opacity-70')}>
                <Send size={16} />
                {ftthLoading ? 'Projetando...' : 'Projetar Rede FTTH'}
              </button>

              {ftthError && (
                <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)', color: 'var(--danger)' }}>
                  <span className="font-medium">Erro:</span> {ftthError}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-4 lg:col-span-2">
            {!ftthData && !ftthLoading && (
              <div className="pulso-card flex items-center justify-center py-16 text-sm" style={{ color: 'var(--text-muted)' }}>
                Defina os parâmetros e clique em &quot;Projetar Rede FTTH&quot; para gerar o projeto.
              </div>
            )}

            {ftthLoading && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (<StatBox key={i} title="" value="" loading />))}
              </div>
            )}

            {ftthData && (
              <>
                {/* Summary stats */}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <StatBox title="CAPEX Total" value={formatBRL(ftthData.summary.total_capex_brl)} icon={<DollarSign size={18} style={{ color: 'var(--accent)' }} />} subtitle="Investimento total" />
                  <StatBox title="Custo/Assinante" value={formatBRL(ftthData.summary.capex_per_subscriber_brl)} icon={<Users size={18} style={{ color: 'var(--success)' }} />} subtitle="CAPEX por sub" />
                  <StatBox title="Margem Óptica" value={`${fmtNum(ftthData.summary.optical_margin_db)} dB`} icon={<Signal size={18} style={{ color: ftthData.summary.optical_viable ? 'var(--success)' : 'var(--danger)' }} />} subtitle={ftthData.summary.optical_viable ? 'Link viável' : 'Margem insuficiente'} />
                  <StatBox title="Assinantes" value={formatCompact(ftthData.summary.subscribers)} icon={<Cable size={18} className="text-cyan-400" />} subtitle={`${ftthData.summary.technology} 1:${ftthData.summary.split_ratio}`} />
                </div>

                {/* Optical budget bar */}
                <div className="pulso-card">
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    <Signal size={16} style={{ color: 'var(--accent)' }} />
                    Orçamento Óptico
                  </h3>
                  <div className="space-y-2">
                    {Object.entries(ftthData.optical_budget.losses).map(([key, val]) => {
                      const labels: Record<string, string> = { fiber_db: 'Fibra', splice_db: 'Emendas', connector_db: 'Conectores', splitter_db: 'Splitters' };
                      const pct = ((val as number) / ftthData.optical_budget.budget_db) * 100;
                      return (
                        <div key={key}>
                          <div className="flex justify-between text-xs" style={{ color: 'var(--text-secondary)' }}>
                            <span>{labels[key] || key}</span>
                            <span>{fmtNum(val as number, 2)} dB</span>
                          </div>
                          <div className="mt-1 h-2 w-full overflow-hidden rounded-full" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                            <div className="h-full rounded-full" style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: 'var(--accent)' }} />
                          </div>
                        </div>
                      );
                    })}
                    <div className="mt-2 flex justify-between text-xs font-semibold" style={{ borderTop: '1px solid var(--border)', paddingTop: '8px' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Total: {fmtNum(ftthData.optical_budget.total_loss_db, 2)} dB / {ftthData.optical_budget.budget_db} dB</span>
                      <span style={{ color: ftthData.optical_budget.viable ? 'var(--success)' : 'var(--danger)' }}>Margem: {fmtNum(ftthData.optical_budget.margin_db, 2)} dB</span>
                    </div>
                  </div>
                </div>

                {/* Splitter cascade + OLT sizing side by side */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="pulso-card">
                    <h3 className="mb-3 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Cascata de Splitters</h3>
                    <p className="mb-3 text-xs" style={{ color: 'var(--text-muted)' }}>{ftthData.splitter_cascade.description}</p>
                    <div className="space-y-2">
                      {ftthData.splitter_cascade.stages.map((s) => (
                        <div key={s.level} className="flex items-center justify-between rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                          <div>
                            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Nível {s.level}: 1:{s.ratio}</p>
                            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{s.location} — {s.loss_db} dB</p>
                          </div>
                          <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>{formatBRL(s.unit_cost_brl)}/un</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="pulso-card">
                    <h3 className="mb-3 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Dimensionamento OLT</h3>
                    <div className="space-y-2 text-sm">
                      {[
                        { label: 'Portas PON', value: String(ftthData.olt_sizing.pon_ports) },
                        { label: 'Placas', value: `${ftthData.olt_sizing.boards} × ${ftthData.olt_sizing.ports_per_board} portas` },
                        { label: 'Chassis', value: String(ftthData.olt_sizing.chassis) },
                        { label: 'BW Down', value: `${ftthData.olt_sizing.total_bandwidth_down_gbps} Gbps` },
                        { label: 'BW/Assinante', value: `${fmtNum(ftthData.olt_sizing.bandwidth_per_sub_down_mbps, 0)} Mbps` },
                        { label: 'Custo OLT', value: formatBRL(ftthData.olt_sizing.olt_cost_brl) },
                      ].map((r) => (
                        <div key={r.label} className="flex justify-between">
                          <span style={{ color: 'var(--text-secondary)' }}>{r.label}</span>
                          <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{r.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* BOM table */}
                <div className="pulso-card">
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    <BarChart3 size={16} style={{ color: 'var(--accent)' }} />
                    Bill of Materials (BOM)
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs uppercase" style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                          <th className="pb-2 pr-4 font-medium">Categoria</th>
                          <th className="pb-2 pr-4 font-medium">Item</th>
                          <th className="pb-2 pr-4 font-medium text-right">Qtd</th>
                          <th className="pb-2 pr-4 font-medium text-right">Unit.</th>
                          <th className="pb-2 font-medium text-right">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ftthData.bom.items.map((item, idx) => (
                          <tr key={idx} style={{ borderBottom: '1px solid color-mix(in srgb, var(--border) 50%, transparent)', color: 'var(--text-secondary)' }}>
                            <td className="py-2 pr-4 text-xs">{item.category}</td>
                            <td className="py-2 pr-4" style={{ color: 'var(--text-primary)' }}>{item.item}</td>
                            <td className="py-2 pr-4 text-right">{typeof item.quantity === 'number' && item.quantity % 1 !== 0 ? fmtNum(item.quantity, 2) : item.quantity} {item.unit}</td>
                            <td className="py-2 pr-4 text-right">{formatBRL(item.unit_cost_brl)}</td>
                            <td className="py-2 text-right font-medium" style={{ color: 'var(--text-primary)' }}>{formatBRL(item.total_cost_brl)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr style={{ borderTop: '2px solid var(--border)' }}>
                          <td colSpan={4} className="py-2 text-right font-semibold" style={{ color: 'var(--text-primary)' }}>TOTAL</td>
                          <td className="py-2 text-right text-base font-bold" style={{ color: 'var(--accent)' }}>{formatBRL(ftthData.bom.total_cost_brl)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 2 — Cobertura Wireless (merged coverage + optimization)
          ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'wireless' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="pulso-card lg:col-span-1">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Signal size={16} style={{ color: 'var(--accent)' }} />
              Parâmetros de Cobertura
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Latitude da Torre</label><input type="number" step="0.0001" value={covLat} onChange={(e) => setCovLat(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Longitude da Torre</label><input type="number" step="0.0001" value={covLon} onChange={(e) => setCovLon(e.target.value)} className="pulso-input w-full" /></div>
              </div>
              <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Altura da Torre (m)</label><input type="number" value={covHeight} onChange={(e) => setCovHeight(e.target.value)} className="pulso-input w-full" /></div>
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Frequência (MHz)</label>
                <select value={covFreq} onChange={(e) => setCovFreq(e.target.value)} className="pulso-input w-full">
                  {FREQ_OPTIONS.map((f) => (<option key={f} value={f}>{f} MHz</option>))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Potência TX (dBm)</label><input type="number" value={covPower} onChange={(e) => setCovPower(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Ganho Antena (dBi)</label><input type="number" value={covGain} onChange={(e) => setCovGain(e.target.value)} className="pulso-input w-full" /></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Raio (m)</label><input type="number" value={covRadius} onChange={(e) => setCovRadius(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Resolução (m)</label><input type="number" value={covResolution} onChange={(e) => setCovResolution(e.target.value)} className="pulso-input w-full" /></div>
              </div>
              <div className="flex items-center gap-3">
                <label className="relative inline-flex cursor-pointer items-center">
                  <input type="checkbox" checked={covVegetation} onChange={(e) => setCovVegetation(e.target.checked)} className="peer sr-only" />
                  <div className="h-5 w-9 rounded-full after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:after:translate-x-full" style={{ backgroundColor: covVegetation ? 'var(--accent)' : 'var(--bg-subtle)' }} />
                </label>
                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Correção de Vegetação</span>
              </div>

              <button onClick={handleCoverage} disabled={coverageLoading} className={clsx('pulso-btn-primary flex w-full items-center justify-center gap-2', coverageLoading && 'cursor-wait opacity-70')}>
                <Send size={16} />
                {coverageLoading ? 'Calculando...' : 'Calcular Cobertura'}
              </button>

              {/* Optimization toggle */}
              <button onClick={() => setShowOptimize(!showOptimize)} className="flex w-full items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors" style={{ backgroundColor: 'var(--bg-subtle)', color: 'var(--text-secondary)' }}>
                <Antenna size={14} />
                {showOptimize ? 'Ocultar Otimização' : 'Otimização de Torres'}
              </button>

              {showOptimize && (
                <div className="space-y-3 rounded-lg p-3" style={{ backgroundColor: 'var(--bg-subtle)' }}>
                  <div className="grid grid-cols-3 gap-2">
                    <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Meta (%)</label><input type="number" value={optTarget} onChange={(e) => setOptTarget(e.target.value)} className="pulso-input w-full" /></div>
                    <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Min dBm</label><input type="number" value={optMinSignal} onChange={(e) => setOptMinSignal(e.target.value)} className="pulso-input w-full" /></div>
                    <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Max Torres</label><input type="number" value={optMaxTowers} onChange={(e) => setOptMaxTowers(e.target.value)} className="pulso-input w-full" /></div>
                  </div>
                  <button onClick={handleOptimize} disabled={optimizeLoading} className={clsx('pulso-btn-primary flex w-full items-center justify-center gap-2 text-sm', optimizeLoading && 'cursor-wait opacity-70')}>
                    <Antenna size={14} />
                    {optimizeLoading ? 'Otimizando...' : 'Otimizar Posicionamento'}
                  </button>
                </div>
              )}

              {(coverageError || optimizeError) && (
                <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)', color: 'var(--danger)' }}>
                  <span className="font-medium">Erro:</span> {coverageError || optimizeError}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-4 lg:col-span-2">
            {!coverageData && !coverageLoading && !optimizeData && !optimizeLoading && (
              <div className="pulso-card flex items-center justify-center py-16 text-sm" style={{ color: 'var(--text-muted)' }}>
                Defina os parâmetros e clique em &quot;Calcular Cobertura&quot; para visualizar os resultados.
              </div>
            )}

            {(coverageLoading || optimizeLoading) && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (<StatBox key={i} title="" value="" loading />))}
              </div>
            )}

            {coverageData && (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <StatBox title="Cobertura" value={`${fmtNum(coverageData.coverage_pct)}%`} icon={<Signal size={18} style={{ color: 'var(--accent)' }} />} subtitle="Percentual coberto" />
                  <StatBox title="Área Coberta" value={`${fmtNum(coverageData.coverage_area_km2, 2)} km²`} icon={<Maximize2 size={18} style={{ color: 'var(--success)' }} />} subtitle="Área total" />
                  <StatBox title="Sinal Médio" value={`${fmtNum(coverageData.avg_signal_dbm)} dBm`} icon={<Radio size={18} className="text-cyan-400" />} subtitle="Média na área" />
                  <StatBox title="Sinal Mínimo" value={`${fmtNum(coverageData.min_signal_dbm)} dBm`} icon={<Zap size={18} style={{ color: 'var(--warning)' }} />} subtitle="Pior caso" />
                </div>

                {(coverageData.grid?.length ?? 0) > 0 && (
                  <div className="pulso-card">
                    <p className="mb-2 text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Distribuição do Sinal</p>
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                      {[
                        { label: 'Excelente (> -65)', count: (coverageData.grid ?? []).filter(p => p.signal_dbm > -65).length, color: 'var(--success)' },
                        { label: 'Bom (-65 a -75)', count: (coverageData.grid ?? []).filter(p => p.signal_dbm <= -65 && p.signal_dbm > -75).length, color: 'var(--accent)' },
                        { label: 'Regular (-75 a -85)', count: (coverageData.grid ?? []).filter(p => p.signal_dbm <= -75 && p.signal_dbm > -85).length, color: 'var(--warning)' },
                        { label: 'Fraco (< -85)', count: (coverageData.grid ?? []).filter(p => p.signal_dbm <= -85).length, color: 'var(--danger)' },
                      ].map((band) => (
                        <div key={band.label} className="text-center">
                          <p className="text-lg font-bold" style={{ color: band.color }}>{band.count.toLocaleString('pt-BR')}</p>
                          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{band.label}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {optimizeData && (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <StatBox title="Torres" value={String(optimizeData.tower_count ?? optimizeData.towers?.length ?? '---')} icon={<Antenna size={18} style={{ color: 'var(--accent)' }} />} subtitle="Posições otimizadas" />
                  <StatBox title="Cobertura" value={optimizeData.coverage_achieved_pct != null ? `${fmtNum(optimizeData.coverage_achieved_pct)}%` : '---'} icon={<Signal size={18} style={{ color: 'var(--success)' }} />} subtitle={`Meta: ${optTarget}%`} />
                  <StatBox title="Área" value={optimizeData.coverage_area_km2 != null ? `${fmtNum(optimizeData.coverage_area_km2, 2)} km²` : '---'} icon={<Maximize2 size={18} className="text-cyan-400" />} />
                  <StatBox title="CAPEX" value={optimizeData.estimated_capex_brl != null ? `R$ ${(optimizeData.estimated_capex_brl / 1000).toFixed(0)}k` : '---'} icon={<DollarSign size={18} style={{ color: 'var(--warning)' }} />} />
                </div>

                {optimizeData.towers && optimizeData.towers.length > 0 && (
                  <div className="pulso-card">
                    <h3 className="mb-3 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Posições das Torres</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-xs uppercase" style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                            <th className="pb-2 pr-4 font-medium">#</th>
                            <th className="pb-2 pr-4 font-medium">Lat</th>
                            <th className="pb-2 pr-4 font-medium">Lon</th>
                            <th className="pb-2 font-medium">Cobertura</th>
                          </tr>
                        </thead>
                        <tbody>
                          {optimizeData.towers.map((tower: any, idx: number) => (
                            <tr key={idx} style={{ borderBottom: '1px solid color-mix(in srgb, var(--border) 50%, transparent)', color: 'var(--text-secondary)' }}>
                              <td className="py-2 pr-4 font-medium" style={{ color: 'var(--text-primary)' }}>{idx + 1}</td>
                              <td className="py-2 pr-4">{(tower.lat ?? tower.latitude)?.toFixed(4) ?? '---'}</td>
                              <td className="py-2 pr-4">{(tower.lon ?? tower.longitude)?.toFixed(4) ?? '---'}</td>
                              <td className="py-2">{tower.coverage_pct != null ? <span className="font-semibold" style={{ color: 'var(--success)' }}>{fmtNum(tower.coverage_pct)}%</span> : '---'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 3 — Link Budget (dual: microwave + optical)
          ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'linkbudget' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="pulso-card lg:col-span-1">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <Radio size={16} style={{ color: 'var(--accent)' }} />
              Link Budget
            </h2>

            {/* Mode toggle */}
            <div className="mb-4 flex gap-2">
              {([['microwave', 'Microondas'], ['optical', 'Fibra Óptica']] as const).map(([key, label]) => (
                <button key={key} onClick={() => setLbMode(key)} className={clsx('flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors')} style={{ backgroundColor: lbMode === key ? 'var(--accent)' : 'var(--bg-subtle)', color: lbMode === key ? '#fff' : 'var(--text-secondary)' }}>{label}</button>
              ))}
            </div>

            {lbMode === 'microwave' ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Frequência (GHz)</label><input type="number" value={lbFreq} onChange={(e) => setLbFreq(e.target.value)} className="pulso-input w-full" /></div>
                  <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Distância (km)</label><input type="number" value={lbDist} onChange={(e) => setLbDist(e.target.value)} className="pulso-input w-full" /></div>
                </div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Potência TX (dBm)</label><input type="number" value={lbPower} onChange={(e) => setLbPower(e.target.value)} className="pulso-input w-full" /></div>
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Ganho TX (dBi)</label><input type="number" value={lbTxGain} onChange={(e) => setLbTxGain(e.target.value)} className="pulso-input w-full" /></div>
                  <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Ganho RX (dBi)</label><input type="number" value={lbRxGain} onChange={(e) => setLbRxGain(e.target.value)} className="pulso-input w-full" /></div>
                </div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Limiar RX (dBm)</label><input type="number" value={lbThreshold} onChange={(e) => setLbThreshold(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Taxa de Chuva (mm/h)</label><input type="number" value={lbRain} onChange={(e) => setLbRain(e.target.value)} className="pulso-input w-full" /><p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Padrão tropical Brasil</p></div>
                <button onClick={handleLinkBudget} disabled={linkLoading} className={clsx('pulso-btn-primary flex w-full items-center justify-center gap-2', linkLoading && 'cursor-wait opacity-70')}>
                  <Ruler size={16} />
                  {linkLoading ? 'Calculando...' : 'Calcular Link Budget'}
                </button>
                {linkError && <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)', color: 'var(--danger)' }}><span className="font-medium">Erro:</span> {linkError}</div>}
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Distância fibra (km)</label><input type="number" step="0.1" value={obFiber} onChange={(e) => setObFiber(e.target.value)} className="pulso-input w-full" /></div>
                  <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Emendas</label><input type="number" value={obSplices} onChange={(e) => setObSplices(e.target.value)} className="pulso-input w-full" /></div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Conectores</label><input type="number" value={obConnectors} onChange={(e) => setObConnectors(e.target.value)} className="pulso-input w-full" /></div>
                  <div>
                    <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Tecnologia</label>
                    <select value={obTech} onChange={(e) => setObTech(e.target.value as any)} className="pulso-input w-full">
                      <option value="GPON">GPON</option>
                      <option value="XGS-PON">XGS-PON</option>
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Splitter 1 (ratio)</label>
                    <select value={obSplit1} onChange={(e) => setObSplit1(e.target.value)} className="pulso-input w-full">
                      {['2', '4', '8', '16', '32', '64'].map((s) => (<option key={s} value={s}>1:{s}</option>))}
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Splitter 2 (0=nenhum)</label>
                    <select value={obSplit2} onChange={(e) => setObSplit2(e.target.value)} className="pulso-input w-full">
                      <option value="0">Nenhum</option>
                      {['2', '4', '8', '16', '32'].map((s) => (<option key={s} value={s}>1:{s}</option>))}
                    </select>
                  </div>
                </div>
                <button onClick={handleOpticalBudget} disabled={opticalLoading} className={clsx('pulso-btn-primary flex w-full items-center justify-center gap-2', opticalLoading && 'cursor-wait opacity-70')}>
                  <Cable size={16} />
                  {opticalLoading ? 'Calculando...' : 'Calcular Orçamento Óptico'}
                </button>
                {opticalError && <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)', color: 'var(--danger)' }}><span className="font-medium">Erro:</span> {opticalError}</div>}
              </div>
            )}
          </div>

          <div className="space-y-4 lg:col-span-2">
            {lbMode === 'microwave' && !linkData && !linkLoading && (
              <div className="pulso-card flex items-center justify-center py-16 text-sm" style={{ color: 'var(--text-muted)' }}>
                Defina os parâmetros e clique em &quot;Calcular Link Budget&quot; para visualizar os resultados.
              </div>
            )}

            {lbMode === 'optical' && !opticalData && !opticalLoading && (
              <div className="pulso-card flex items-center justify-center py-16 text-sm" style={{ color: 'var(--text-muted)' }}>
                Defina os parâmetros e clique em &quot;Calcular Orçamento Óptico&quot; para visualizar os resultados.
              </div>
            )}

            {(linkLoading || opticalLoading) && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {[1, 2, 3].map((i) => (<StatBox key={i} title="" value="" loading />))}
              </div>
            )}

            {/* Microwave results */}
            {lbMode === 'microwave' && linkData && (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <StatBox title="EIRP" value={linkData.eirp_dbm != null ? `${fmtNum(linkData.eirp_dbm)} dBm` : '---'} icon={<Zap size={18} style={{ color: 'var(--accent)' }} />} subtitle="Potência efetiva" />
                  <StatBox title="FSL" value={linkData.free_space_loss_db != null ? `${fmtNum(linkData.free_space_loss_db)} dB` : '---'} icon={<Ruler size={18} className="text-cyan-400" />} subtitle="Espaço livre" />
                  <StatBox title="Atenuação Chuva" value={linkData.rain_attenuation_db != null ? `${fmtNum(linkData.rain_attenuation_db)} dB` : '---'} icon={<Mountain size={18} style={{ color: 'var(--warning)' }} />} subtitle={`${lbRain} mm/h`} />
                  <StatBox title="Sinal Recebido" value={linkData.received_power_dbm != null ? `${fmtNum(linkData.received_power_dbm)} dBm` : '---'} icon={<Signal size={18} style={{ color: 'var(--success)' }} />} subtitle="No receptor" />
                  <StatBox title="Margem" value={linkData.fade_margin_db != null ? `${fmtNum(linkData.fade_margin_db)} dB` : '---'} icon={<Radio size={18} style={{ color: linkData.fade_margin_db > 0 ? 'var(--success)' : 'var(--danger)' }} />} subtitle={linkData.fade_margin_db > 0 ? 'Link viável' : 'Link inviável'} />
                  <StatBox title="Disponibilidade" value={linkData.availability_pct != null ? `${fmtNum(linkData.availability_pct, 4)}%` : '---'} icon={<Maximize2 size={18} className="text-purple-400" />} subtitle="Estimativa anual" />
                </div>
                <div className="pulso-card flex items-center justify-between">
                  <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Status do Enlace</span>
                  {linkData.fade_margin_db != null ? (
                    linkData.fade_margin_db > 0 ? (
                      <span className="pulso-badge-green flex items-center gap-1"><CheckCircle size={14} /> Viável — Margem {fmtNum(linkData.fade_margin_db)} dB</span>
                    ) : (
                      <span className="pulso-badge-red flex items-center gap-1"><XCircle size={14} /> Inviável</span>
                    )
                  ) : <span className="text-sm" style={{ color: 'var(--text-muted)' }}>---</span>}
                </div>
              </>
            )}

            {/* Optical results */}
            {lbMode === 'optical' && opticalData && (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <StatBox title="Perda Total" value={`${fmtNum(opticalData.total_loss_db, 2)} dB`} icon={<Cable size={18} style={{ color: 'var(--accent)' }} />} subtitle={`Budget: ${opticalData.budget_db} dB`} />
                  <StatBox title="Margem Óptica" value={`${fmtNum(opticalData.margin_db, 2)} dB`} icon={<Signal size={18} style={{ color: opticalData.viable ? 'var(--success)' : 'var(--danger)' }} />} subtitle={opticalData.viable ? 'Link viável' : 'Margem insuficiente'} />
                  <StatBox title="Alcance Máximo" value={`${fmtNum(opticalData.max_distance_km)} km`} icon={<Ruler size={18} className="text-cyan-400" />} subtitle={`Split 1:${opticalData.total_split_ratio}`} />
                </div>

                <div className="pulso-card">
                  <h3 className="mb-3 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Detalhamento de Perdas</h3>
                  <div className="space-y-2">
                    {[
                      { label: 'Fibra', value: `${fmtNum(opticalData.losses.fiber_db, 2)} dB`, detail: `${opticalData.fiber_km} km` },
                      { label: 'Emendas', value: `${fmtNum(opticalData.losses.splice_db, 2)} dB`, detail: `${opticalData.splices} × 0.1 dB` },
                      { label: 'Conectores', value: `${fmtNum(opticalData.losses.connector_db, 2)} dB`, detail: `${opticalData.connectors} × 0.5 dB` },
                      { label: 'Splitters', value: `${fmtNum(opticalData.losses.splitter_db, 2)} dB`, detail: `1:${opticalData.total_split_ratio}` },
                    ].map((r) => (
                      <div key={r.label} className="flex items-center justify-between text-sm">
                        <span style={{ color: 'var(--text-secondary)' }}>{r.label} <span className="text-xs" style={{ color: 'var(--text-muted)' }}>({r.detail})</span></span>
                        <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{r.value}</span>
                      </div>
                    ))}
                    <div className="flex justify-between text-sm font-semibold" style={{ borderTop: '1px solid var(--border)', paddingTop: '8px' }}>
                      <span style={{ color: 'var(--text-primary)' }}>Total</span>
                      <span style={{ color: 'var(--accent)' }}>{fmtNum(opticalData.total_loss_db, 2)} dB</span>
                    </div>
                  </div>
                </div>

                <div className="pulso-card flex items-center justify-between">
                  <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Status do Enlace Óptico</span>
                  {opticalData.viable ? (
                    <span className="pulso-badge-green flex items-center gap-1"><CheckCircle size={14} /> Viável — Margem {fmtNum(opticalData.margin_db, 2)} dB</span>
                  ) : (
                    <span className="pulso-badge-red flex items-center gap-1"><XCircle size={14} /> Margem insuficiente ({fmtNum(opticalData.margin_db, 2)} dB)</span>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 4 — Viabilidade (NEW)
          ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'viability' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="pulso-card lg:col-span-1">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              <DollarSign size={16} style={{ color: 'var(--accent)' }} />
              Análise de Viabilidade
            </h2>
            <div className="space-y-4">
              <div className="relative">
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Município</label>
                <input
                  type="text"
                  value={viaMuniSearch}
                  onChange={(e) => searchMunicipalities(e.target.value)}
                  onFocus={() => muniResults.length > 0 && setShowMuniDropdown(true)}
                  placeholder="Buscar município..."
                  className="pulso-input w-full"
                />
                {showMuniDropdown && muniResults.length > 0 && (
                  <div className="absolute z-10 mt-1 max-h-48 w-full overflow-y-auto rounded-lg shadow-lg" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                    {muniResults.map((m) => (
                      <button key={m.id} onClick={() => selectMuni(m)} className="block w-full px-3 py-2 text-left text-sm hover:opacity-80" style={{ color: 'var(--text-primary)' }}>
                        {m.name} <span style={{ color: 'var(--text-muted)' }}>— {m.state_abbrev}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Tecnologia</label>
                <div className="flex gap-2">
                  {(['FTTH', 'FWA', 'Hibrido'] as const).map((t) => (
                    <button key={t} onClick={() => setViaTech(t)} className="flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors" style={{ backgroundColor: viaTech === t ? 'var(--accent)' : 'var(--bg-subtle)', color: viaTech === t ? '#fff' : 'var(--text-secondary)' }}>{t === 'Hibrido' ? 'Híbrido' : t}</button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>Assinantes</label><input type="number" value={viaSubs} onChange={(e) => setViaSubs(e.target.value)} className="pulso-input w-full" /></div>
                <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>ARPU (R$/mês)</label><input type="number" step="0.01" value={viaArpu} onChange={(e) => setViaArpu(e.target.value)} className="pulso-input w-full" /></div>
              </div>

              <button onClick={handleViability} disabled={viaLoading || !viaMuniId} className={clsx('pulso-btn-primary flex w-full items-center justify-center gap-2', (viaLoading || !viaMuniId) && 'cursor-wait opacity-70')}>
                <TrendingUp size={16} />
                {viaLoading ? 'Analisando...' : 'Analisar Viabilidade'}
              </button>

              {!viaMuniId && viaMuniSearch.length > 0 && (
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Selecione um município da lista.</p>
              )}

              {viaError && (
                <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)', color: 'var(--danger)' }}>
                  <span className="font-medium">Erro:</span> {viaError}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-4 lg:col-span-2">
            {!viaData && !viaLoading && (
              <div className="pulso-card flex items-center justify-center py-16 text-sm" style={{ color: 'var(--text-muted)' }}>
                Selecione um município e clique em &quot;Analisar Viabilidade&quot; para gerar a análise econômica.
              </div>
            )}

            {viaLoading && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (<StatBox key={i} title="" value="" loading />))}
              </div>
            )}

            {viaData && (
              <>
                {/* Recommendation badge */}
                <div className="pulso-card flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Recomendação</p>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{viaData.recommendation.reason}</p>
                  </div>
                  <span className={clsx('flex items-center gap-1 rounded-full px-3 py-1 text-sm font-semibold', viaData.recommendation.status === 'viable' && 'pulso-badge-green', viaData.recommendation.status === 'marginal' && 'pulso-badge-yellow', viaData.recommendation.status === 'not_viable' && 'pulso-badge-red')}>
                    {viaData.recommendation.status === 'viable' && <CheckCircle size={14} />}
                    {viaData.recommendation.status === 'marginal' && <AlertTriangle size={14} />}
                    {viaData.recommendation.status === 'not_viable' && <XCircle size={14} />}
                    {viaData.recommendation.label}
                  </span>
                </div>

                {/* Market context */}
                <div className="pulso-card">
                  <h3 className="mb-3 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Contexto de Mercado</h3>
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    <div className="text-center">
                      <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{formatCompact(viaData.market_context.total_subscribers)}</p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Assinantes</p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{viaData.market_context.providers}</p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Provedores</p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{formatCompact(viaData.market_context.hhi)}</p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>HHI</p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{formatPct(viaData.market_context.fiber_pct)}</p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Fibra %</p>
                    </div>
                  </div>
                  {viaData.market_context.leader_name && (
                    <p className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                      Líder: {viaData.market_context.leader_name} ({formatPct(viaData.market_context.leader_share_pct)}) — Tendência: {viaData.market_context.growth_trend}
                    </p>
                  )}
                </div>

                {/* CAPEX breakdown */}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <StatBox title="CAPEX Total" value={formatBRL(viaData.capex.total_brl)} icon={<DollarSign size={18} style={{ color: 'var(--accent)' }} />} subtitle={`${formatBRL(viaData.capex.per_subscriber_brl)}/assinante`} />
                  <StatBox title="OPEX/Assinante" value={`${formatBRL(viaData.opex_per_subscriber_brl)}/mês`} icon={<TrendingUp size={18} style={{ color: 'var(--warning)' }} />} subtitle={viaData.technology} />
                  <StatBox title="ARPU" value={`${formatBRL(viaData.arpu_brl)}/mês`} icon={<Users size={18} style={{ color: 'var(--success)' }} />} subtitle={`${viaData.subscribers} assinantes`} />
                </div>

                {/* 3-scenario comparison table */}
                <div className="pulso-card">
                  <h3 className="mb-3 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Comparativo de Cenários (60 meses)</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs uppercase" style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                          <th className="pb-2 pr-4 font-medium">Cenário</th>
                          <th className="pb-2 pr-4 font-medium text-right">Assinantes</th>
                          <th className="pb-2 pr-4 font-medium text-right">Payback</th>
                          <th className="pb-2 pr-4 font-medium text-right">NPV</th>
                          <th className="pb-2 font-medium text-right">TIR</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(['optimistic', 'realistic', 'conservative'] as const).map((key) => {
                          const s = viaData.scenarios[key];
                          return (
                            <tr key={key} style={{ borderBottom: '1px solid color-mix(in srgb, var(--border) 50%, transparent)' }}>
                              <td className="py-2 pr-4 font-medium" style={{ color: 'var(--text-primary)' }}>{s.label}</td>
                              <td className="py-2 pr-4 text-right" style={{ color: 'var(--text-secondary)' }}>{s.max_subscribers.toLocaleString('pt-BR')} ({formatPct(s.target_pct * 100, 0)})</td>
                              <td className="py-2 pr-4 text-right">
                                <span style={{ color: s.payback_months && s.payback_months <= 24 ? 'var(--success)' : s.payback_months && s.payback_months <= 48 ? 'var(--warning)' : 'var(--danger)' }}>
                                  {s.payback_months ? `${s.payback_months} meses` : '> 60 meses'}
                                </span>
                              </td>
                              <td className="py-2 pr-4 text-right font-medium" style={{ color: s.npv_brl >= 0 ? 'var(--success)' : 'var(--danger)' }}>{formatBRL(s.npv_brl)}</td>
                              <td className="py-2 text-right font-medium" style={{ color: 'var(--text-primary)' }}>{s.irr_pct != null ? `${fmtNum(s.irr_pct)}%` : '---'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <p className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>Taxa de desconto: {viaData.discount_rate_annual_pct}% a.a.</p>
                </div>

                {/* Cashflow chart — realistic scenario */}
                {viaData.scenarios.realistic.cashflow.length > 0 && (
                  <SimpleChart
                    data={viaData.scenarios.realistic.cashflow.filter((_, i) => i % 3 === 0).map((c) => ({
                      name: `M${c.month}`,
                      acumulado: Math.round(c.cumulative_brl / 1000),
                      receita: Math.round(c.revenue_brl / 1000),
                    }))}
                    type="line"
                    xKey="name"
                    yKey="acumulado"
                    title="Fluxo de Caixa Acumulado — Cenário Realista (R$ mil)"
                    height={300}
                  />
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 5 — Perfil de Terreno (unchanged)
          ══════════════════════════════════════════════════════════════════════ */}
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
                              <p className="text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Desnível Total</p>
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
