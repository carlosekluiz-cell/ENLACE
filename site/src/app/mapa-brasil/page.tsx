'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import Section from '@/components/ui/Section';
import { ArrowRight, Loader2, Map, Users, BarChart3, Activity, Play, Pause, Clock } from 'lucide-react';

/* =================================================================
   Types
   ================================================================= */

interface Municipality {
  lat: number;
  lng: number;
  uf: string;
  pop: number;
  subs: number;
  providers: number;
  hhi: number;
  penetration: number;
}

interface MapaMeta {
  total_municipalities: number;
  municipalities_with_data: number;
  total_subscribers: number;
  avg_penetration: number;
  periods_available: string[];
}

interface MapaResponse {
  municipalities: Municipality[];
  meta: MapaMeta;
}

// Historical types
interface HistMuniPoint {
  s: number;   // subscribers (blinded)
  p: number;   // providers
  h: number;   // hhi
  n: number;   // penetration
}

interface HistMunicipality {
  lat: number;
  lng: number;
  uf: string;
  pop: number;
  history: HistMuniPoint[];
}

interface HistPeriodStats {
  period: string;
  total_subs: number;
  avg_penetration: number;
  municipalities_with_data: number;
}

interface HistResponse {
  periods: string[];
  period_stats: HistPeriodStats[];
  municipalities: HistMunicipality[];
}

type ViewMode = 'penetration' | 'hhi' | 'providers';

/* =================================================================
   Constants
   ================================================================= */

const API_URL = 'https://api.pulso.network/api/v1/public/mapa';
const API_HIST_URL = 'https://api.pulso.network/api/v1/public/mapa/historico';

// Brazil bounding box (from real data: lat -33.69..4.71, lng -74.07..-32.41)
const BRAZIL_BOUNDS = {
  minLat: -34.0,
  maxLat: 5.5,
  minLng: -74.5,
  maxLng: -32.0,
};

// State → Region mapping for subtle regional tinting
const STATE_REGION: Record<string, string> = {
  AC: 'N', AM: 'N', AP: 'N', PA: 'N', RO: 'N', RR: 'N', TO: 'N',
  AL: 'NE', BA: 'NE', CE: 'NE', MA: 'NE', PB: 'NE', PE: 'NE', PI: 'NE', RN: 'NE', SE: 'NE',
  DF: 'CO', GO: 'CO', MS: 'CO', MT: 'CO',
  ES: 'SE', MG: 'SE', RJ: 'SE', SP: 'SE',
  PR: 'S', RS: 'S', SC: 'S',
};

/* =================================================================
   Color helpers
   ================================================================= */

function penetrationColor(pen: number): string {
  // 0=red, ~50=yellow, 100+=green
  if (pen <= 0) return 'rgba(220,38,38,0.7)';
  if (pen < 25) return 'rgba(239,68,68,0.7)';
  if (pen < 40) return 'rgba(245,158,11,0.7)';
  if (pen < 60) return 'rgba(234,179,8,0.7)';
  if (pen < 80) return 'rgba(132,204,22,0.7)';
  if (pen < 100) return 'rgba(34,197,94,0.7)';
  return 'rgba(16,185,129,0.8)';
}

function penetrationGlow(pen: number): string {
  if (pen <= 0) return 'rgba(220,38,38,0.15)';
  if (pen < 25) return 'rgba(239,68,68,0.12)';
  if (pen < 40) return 'rgba(245,158,11,0.12)';
  if (pen < 60) return 'rgba(234,179,8,0.12)';
  if (pen < 80) return 'rgba(132,204,22,0.12)';
  return 'rgba(34,197,94,0.15)';
}

function hhiColor(hhi: number): string {
  // Low HHI (competitive) = green, high HHI (concentrated) = red
  if (hhi < 1500) return 'rgba(34,197,94,0.7)';
  if (hhi < 2500) return 'rgba(132,204,22,0.7)';
  if (hhi < 4000) return 'rgba(234,179,8,0.7)';
  if (hhi < 6000) return 'rgba(245,158,11,0.7)';
  return 'rgba(239,68,68,0.7)';
}

function hhiGlow(hhi: number): string {
  if (hhi < 1500) return 'rgba(34,197,94,0.15)';
  if (hhi < 2500) return 'rgba(132,204,22,0.12)';
  if (hhi < 4000) return 'rgba(234,179,8,0.12)';
  return 'rgba(239,68,68,0.12)';
}

function providerColor(count: number): string {
  if (count <= 5) return 'rgba(239,68,68,0.6)';
  if (count <= 15) return 'rgba(245,158,11,0.6)';
  if (count <= 30) return 'rgba(234,179,8,0.6)';
  if (count <= 60) return 'rgba(132,204,22,0.7)';
  if (count <= 150) return 'rgba(34,197,94,0.7)';
  return 'rgba(99,102,241,0.8)';
}

function providerGlow(count: number): string {
  if (count <= 5) return 'rgba(239,68,68,0.12)';
  if (count <= 15) return 'rgba(245,158,11,0.1)';
  if (count <= 60) return 'rgba(234,179,8,0.1)';
  return 'rgba(34,197,94,0.12)';
}

function getColor(m: Municipality, mode: ViewMode): string {
  switch (mode) {
    case 'penetration': return penetrationColor(m.penetration);
    case 'hhi': return hhiColor(m.hhi);
    case 'providers': return providerColor(m.providers);
  }
}

function getGlow(m: Municipality, mode: ViewMode): string {
  switch (mode) {
    case 'penetration': return penetrationGlow(m.penetration);
    case 'hhi': return hhiGlow(m.hhi);
    case 'providers': return providerGlow(m.providers);
  }
}

/* =================================================================
   Projection
   ================================================================= */

function project(
  lat: number,
  lng: number,
  w: number,
  h: number,
  padding: number = 20,
): { x: number; y: number } {
  const innerW = w - padding * 2;
  const innerH = h - padding * 2;
  const x =
    padding +
    ((lng - BRAZIL_BOUNDS.minLng) / (BRAZIL_BOUNDS.maxLng - BRAZIL_BOUNDS.minLng)) * innerW;
  const y =
    padding +
    ((BRAZIL_BOUNDS.maxLat - lat) / (BRAZIL_BOUNDS.maxLat - BRAZIL_BOUNDS.minLat)) * innerH;
  return { x, y };
}

/* =================================================================
   Format helpers
   ================================================================= */

function formatBigNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace('.0', '') + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K';
  return n.toLocaleString('pt-BR');
}

const MONTH_NAMES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

function formatPeriod(period: string): string {
  // "2023-01" → "Jan 2023"
  const [year, month] = period.split('-');
  return `${MONTH_NAMES[parseInt(month, 10) - 1]} ${year}`;
}

/* =================================================================
   Canvas renderer
   ================================================================= */

function drawMap(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  municipalities: Municipality[],
  mode: ViewMode,
  hoveredIdx: number | null,
  prevMunicipalities?: Municipality[] | null,
) {
  ctx.clearRect(0, 0, w, h);

  // Dark background gradient
  const bgGrad = ctx.createRadialGradient(w * 0.55, h * 0.45, 0, w * 0.55, h * 0.45, w * 0.7);
  bgGrad.addColorStop(0, '#1a1614');
  bgGrad.addColorStop(1, '#0c0a09');
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, w, h);

  // Subtle grid lines
  ctx.strokeStyle = 'rgba(255,255,255,0.02)';
  ctx.lineWidth = 0.5;
  for (let i = 0; i < w; i += 60) {
    ctx.beginPath();
    ctx.moveTo(i, 0);
    ctx.lineTo(i, h);
    ctx.stroke();
  }
  for (let j = 0; j < h; j += 60) {
    ctx.beginPath();
    ctx.moveTo(0, j);
    ctx.lineTo(w, j);
    ctx.stroke();
  }

  // Determine padding based on canvas size
  const padding = Math.max(20, Math.min(w, h) * 0.04);

  // Draw municipalities — smaller dots first, then larger ones on top
  const indexed = municipalities.map((m, i) => ({ m, i }));
  indexed.sort((a, b) => a.m.subs - b.m.subs);

  for (const { m, i } of indexed) {
    const { x, y } = project(m.lat, m.lng, w, h, padding);

    // Dot size: log scale based on subscribers, min 1px, max ~12px
    const logSubs = m.subs > 0 ? Math.log10(m.subs) : 0;
    // logSubs range: ~2 (100) to ~6.7 (4.7M)
    const radius = Math.max(0.8, Math.min(12, (logSubs - 1.5) * 1.8));

    const isHovered = hoveredIdx === i;

    // Delta glow when comparing to previous period
    if (prevMunicipalities && i < prevMunicipalities.length) {
      const prevSubs = prevMunicipalities[i].subs;
      const delta = m.subs - prevSubs;
      if (Math.abs(delta) > 50 && radius > 1.5) {
        const deltaGlow = delta > 0
          ? 'rgba(34,197,94,0.25)'
          : 'rgba(239,68,68,0.25)';
        ctx.beginPath();
        ctx.arc(x, y, radius + 8, 0, Math.PI * 2);
        ctx.fillStyle = deltaGlow;
        ctx.fill();
      }
    }

    // Glow for larger municipalities
    if (radius > 2.5 || isHovered) {
      const glowRadius = isHovered ? radius + 12 : radius + 6;
      const glowColor = isHovered
        ? 'rgba(99,102,241,0.25)'
        : getGlow(m, mode);
      ctx.beginPath();
      ctx.arc(x, y, glowRadius, 0, Math.PI * 2);
      ctx.fillStyle = glowColor;
      ctx.fill();
    }

    // Main dot
    ctx.beginPath();
    ctx.arc(x, y, isHovered ? radius + 2 : radius, 0, Math.PI * 2);
    ctx.fillStyle = isHovered ? 'rgba(129,140,248,0.95)' : getColor(m, mode);
    ctx.fill();

    // Bright center for large cities
    if (radius > 4) {
      ctx.beginPath();
      ctx.arc(x, y, radius * 0.4, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,0.3)';
      ctx.fill();
    }
  }

  // Hovered tooltip
  if (hoveredIdx !== null && hoveredIdx >= 0 && hoveredIdx < municipalities.length) {
    const m = municipalities[hoveredIdx];
    const { x, y } = project(m.lat, m.lng, w, h, padding);

    const tooltipLines = [
      `${m.uf} - Pop: ${formatBigNumber(m.pop)}`,
      `Assinantes: ${formatBigNumber(m.subs)}`,
      mode === 'penetration'
        ? `Penetracao: ${m.penetration.toFixed(1)}%`
        : mode === 'hhi'
          ? `HHI: ${m.hhi.toLocaleString('pt-BR')}`
          : `Provedores: ${m.providers}`,
    ];

    ctx.font = '11px "JetBrains Mono", monospace';
    const maxTextW = Math.max(...tooltipLines.map((l) => ctx.measureText(l).width));
    const tipW = maxTextW + 20;
    const tipH = tooltipLines.length * 18 + 14;

    let tipX = x + 12;
    let tipY = y - tipH - 8;
    if (tipX + tipW > w - 10) tipX = x - tipW - 12;
    if (tipY < 10) tipY = y + 12;

    // Tooltip background
    ctx.fillStyle = 'rgba(28,25,23,0.95)';
    ctx.fillRect(tipX, tipY, tipW, tipH);
    ctx.strokeStyle = 'rgba(99,102,241,0.4)';
    ctx.lineWidth = 1;
    ctx.strokeRect(tipX, tipY, tipW, tipH);

    // Tooltip text
    ctx.fillStyle = '#d6d3d1';
    tooltipLines.forEach((line, li) => {
      ctx.fillText(line, tipX + 10, tipY + 18 + li * 18);
    });
  }
}

/* =================================================================
   Legend component
   ================================================================= */

function Legend({ mode }: { mode: ViewMode }) {
  if (mode === 'penetration') {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-on-dark-muted)' }}>
          Penetracao
        </span>
        {[
          { color: 'rgba(220,38,38,0.8)', label: '0%' },
          { color: 'rgba(245,158,11,0.8)', label: '25%' },
          { color: 'rgba(234,179,8,0.8)', label: '50%' },
          { color: 'rgba(132,204,22,0.8)', label: '75%' },
          { color: 'rgba(34,197,94,0.8)', label: '100%+' },
        ].map((item) => (
          <span key={item.label} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5"
              style={{ background: item.color, borderRadius: '50%' }}
            />
            <span className="font-mono text-[10px]" style={{ color: 'var(--text-on-dark-muted)' }}>
              {item.label}
            </span>
          </span>
        ))}
      </div>
    );
  }

  if (mode === 'hhi') {
    return (
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-on-dark-muted)' }}>
          HHI (concentracao)
        </span>
        {[
          { color: 'rgba(34,197,94,0.8)', label: '<1500' },
          { color: 'rgba(132,204,22,0.8)', label: '1500-2500' },
          { color: 'rgba(234,179,8,0.8)', label: '2500-4000' },
          { color: 'rgba(245,158,11,0.8)', label: '4000-6000' },
          { color: 'rgba(239,68,68,0.8)', label: '>6000' },
        ].map((item) => (
          <span key={item.label} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5"
              style={{ background: item.color, borderRadius: '50%' }}
            />
            <span className="font-mono text-[10px]" style={{ color: 'var(--text-on-dark-muted)' }}>
              {item.label}
            </span>
          </span>
        ))}
      </div>
    );
  }

  // providers
  return (
    <div className="flex items-center gap-3 flex-wrap">
      <span className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-on-dark-muted)' }}>
        Provedores ativos
      </span>
      {[
        { color: 'rgba(239,68,68,0.7)', label: '1-5' },
        { color: 'rgba(245,158,11,0.7)', label: '6-15' },
        { color: 'rgba(234,179,8,0.7)', label: '16-30' },
        { color: 'rgba(132,204,22,0.8)', label: '31-60' },
        { color: 'rgba(34,197,94,0.8)', label: '61-150' },
        { color: 'rgba(99,102,241,0.8)', label: '150+' },
      ].map((item) => (
        <span key={item.label} className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5"
            style={{ background: item.color, borderRadius: '50%' }}
          />
          <span className="font-mono text-[10px]" style={{ color: 'var(--text-on-dark-muted)' }}>
            {item.label}
          </span>
        </span>
      ))}
    </div>
  );
}

/* =================================================================
   Main Page Component
   ================================================================= */

export default function MapaBrasilPage() {
  const [data, setData] = useState<MapaResponse | null>(null);
  const [histData, setHistData] = useState<HistResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<ViewMode>('penetration');
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const [periodIdx, setPeriodIdx] = useState<number>(-1); // -1 = latest (default/no history loaded)
  const [isPlaying, setIsPlaying] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const animFrameRef = useRef<number>(0);
  const playIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch base data + historical data in parallel
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [baseRes, histRes] = await Promise.all([
          fetch(API_URL),
          fetch(API_HIST_URL),
        ]);
        if (!baseRes.ok) throw new Error('Erro ao carregar dados');
        const baseJson: MapaResponse = await baseRes.json();

        if (!cancelled) {
          setData(baseJson);
          setLoading(false);
        }

        if (histRes.ok) {
          const histJson: HistResponse = await histRes.json();
          if (!cancelled && histJson.periods?.length > 0) {
            setHistData(histJson);
            setPeriodIdx(histJson.periods.length - 1); // start at latest
          }
        }
      } catch {
        if (!cancelled) {
          setError('Nao foi possivel carregar os dados do mapa.');
          setLoading(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Build municipalities for current period from historical data
  const currentMunis: Municipality[] | null = (() => {
    if (!histData || periodIdx < 0) return null;
    return histData.municipalities.map(m => {
      const h = m.history[periodIdx] || { s: 0, p: 0, h: 0, n: 0 };
      return {
        lat: m.lat,
        lng: m.lng,
        uf: m.uf,
        pop: m.pop,
        subs: h.s,
        providers: h.p,
        hhi: h.h,
        penetration: h.n,
      };
    });
  })();

  const prevMunis: Municipality[] | null = (() => {
    if (!histData || periodIdx <= 0) return null;
    return histData.municipalities.map(m => {
      const h = m.history[periodIdx - 1] || { s: 0, p: 0, h: 0, n: 0 };
      return {
        lat: m.lat,
        lng: m.lng,
        uf: m.uf,
        pop: m.pop,
        subs: h.s,
        providers: h.p,
        hhi: h.h,
        penetration: h.n,
      };
    });
  })();

  // Use historical data when available, otherwise fall back to base data
  const displayMunis = currentMunis || data?.municipalities || [];

  // Canvas drawing
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || displayMunis.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    drawMap(ctx, rect.width, rect.height, displayMunis, mode, hoveredIdx, prevMunis);
  }, [displayMunis, mode, hoveredIdx, prevMunis]);

  // Auto-play
  useEffect(() => {
    if (isPlaying && histData) {
      playIntervalRef.current = setInterval(() => {
        setPeriodIdx(prev => {
          const next = prev + 1;
          if (next >= histData.periods.length) {
            setIsPlaying(false);
            return histData.periods.length - 1;
          }
          return next;
        });
      }, 400);
    }
    return () => {
      if (playIntervalRef.current) clearInterval(playIntervalRef.current);
    };
  }, [isPlaying, histData]);

  useEffect(() => {
    render();

    const handleResize = () => {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = requestAnimationFrame(render);
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animFrameRef.current);
    };
  }, [render]);

  // Mouse hover — find closest municipality
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (displayMunis.length === 0 || !canvasRef.current) return;

      const rect = canvasRef.current.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const w = rect.width;
      const h = rect.height;
      const padding = Math.max(20, Math.min(w, h) * 0.04);

      let closest = -1;
      let minDist = 20; // 20px snap radius

      for (let i = 0; i < displayMunis.length; i++) {
        const m = displayMunis[i];
        const { x, y } = project(m.lat, m.lng, w, h, padding);
        const dist = Math.hypot(mx - x, my - y);
        if (dist < minDist) {
          minDist = dist;
          closest = i;
        }
      }

      setHoveredIdx(closest >= 0 ? closest : null);
    },
    [displayMunis],
  );

  const handleMouseLeave = useCallback(() => {
    setHoveredIdx(null);
  }, []);

  // Period label
  const currentPeriod = histData && periodIdx >= 0 ? histData.periods[periodIdx] : null;
  const periodLabel = currentPeriod
    ? formatPeriod(currentPeriod)
    : 'Ultimo periodo';

  // Derived stats — dynamic from historical data if available
  const meta = data?.meta;
  const histStats = histData && periodIdx >= 0 ? histData.period_stats[periodIdx] : null;
  const firstStats = histData ? histData.period_stats[0] : null;

  const totalSubsCurrent = histStats?.total_subs ?? meta?.total_subscribers ?? 0;
  const totalSubsLabel = formatBigNumber(totalSubsCurrent) + '+';
  const avgPenCurrent = histStats?.avg_penetration ?? meta?.avg_penetration ?? 0;
  const avgPenLabel = avgPenCurrent.toFixed(1) + '%';
  const munisWithDataCurrent = histStats?.municipalities_with_data ?? meta?.municipalities_with_data ?? 0;
  const periodsLabel = histData ? histData.periods.length.toString() : (meta ? meta.periods_available.length.toString() : '--');
  const munisLabel = meta ? meta.total_municipalities.toLocaleString('pt-BR') : '--';
  const munisWithDataLabel = munisWithDataCurrent.toLocaleString('pt-BR');

  // Delta labels (comparing to first period)
  const showDelta = histData && firstStats && histStats && periodIdx > 0;
  const subsDelta = showDelta ? totalSubsCurrent - firstStats!.total_subs : 0;
  const penDelta = showDelta ? avgPenCurrent - firstStats!.avg_penetration : 0;
  const munisDelta = showDelta ? munisWithDataCurrent - firstStats!.municipalities_with_data : 0;

  const VIEW_MODES: { key: ViewMode; label: string }[] = [
    { key: 'penetration', label: 'Penetracao' },
    { key: 'hhi', label: 'Concentracao (HHI)' },
    { key: 'providers', label: 'Provedores' },
  ];

  return (
    <>
      {/* ---- Hero ---- */}
      <section
        className="relative overflow-hidden -mt-14 grain"
        style={{ background: 'var(--bg-dark)' }}
      >
        <div className="relative z-10 mx-auto max-w-6xl px-4 pt-32 pb-12 md:pt-40 md:pb-16">
          {/* Tag */}
          <div
            className="mb-6 inline-flex items-center gap-2 font-mono text-xs tracking-wider uppercase"
            style={{ color: 'var(--accent-hover)' }}
          >
            <span className="inline-block h-px w-8" style={{ background: 'var(--accent)' }} />
            Dados reais, anonimizados
          </div>

          {/* Headline */}
          <h1
            className="font-serif text-4xl font-bold tracking-tight md:text-5xl lg:text-6xl max-w-4xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.05 }}
          >
            Dados reais.{' '}
            <br className="hidden md:block" />
            Cobertura nacional.
          </h1>

          <p
            className="mt-6 max-w-xl text-base leading-relaxed md:text-lg"
            style={{ color: 'var(--text-on-dark-secondary)' }}
          >
            {meta
              ? `${formatBigNumber(meta.total_subscribers)}+ registros de assinantes em ${meta.total_municipalities.toLocaleString('pt-BR')} municipios.`
              : '54M+ registros de assinantes em 5.572 municipios.'}{' '}
            Visualize a inteligencia telecom do Pulso — sem filtro, sem simulacao.
          </p>

          {/* Social proof */}
          <div
            className="mt-8 flex flex-wrap items-center gap-4 font-mono text-xs"
            style={{ color: 'var(--text-on-dark-muted)' }}
          >
            <span className="flex items-center gap-2">
              <span className="inline-block h-2 w-2" style={{ background: 'var(--success)', borderRadius: '50%' }} />
              Fontes: Anatel STEL, IBGE
            </span>
            <span style={{ color: 'var(--border-dark-strong)' }}>|</span>
            <span>{histData ? histData.periods.length : (meta ? meta.periods_available.length : 37)} periodos disponiveis</span>
            <span style={{ color: 'var(--border-dark-strong)' }}>|</span>
            <span>Atualizado mensalmente</span>
          </div>
        </div>
      </section>

      {/* ---- Map Section ---- */}
      <section style={{ background: 'var(--bg-dark)' }}>
        {/* Toggle controls */}
        <div
          className="mx-auto max-w-6xl px-4 pb-4"
          style={{ borderBottom: '1px solid var(--border-dark)' }}
        >
          <div className="flex flex-wrap items-center gap-2">
            {VIEW_MODES.map((vm) => (
              <button
                key={vm.key}
                onClick={() => setMode(vm.key)}
                className="px-4 py-2 text-xs font-semibold transition-all"
                style={{
                  background: mode === vm.key ? 'var(--accent)' : 'transparent',
                  color: mode === vm.key ? '#fff' : 'var(--text-on-dark-muted)',
                  border: mode === vm.key
                    ? '1px solid var(--accent)'
                    : '1px solid var(--border-dark-strong)',
                }}
              >
                {vm.label}
              </button>
            ))}
            <div className="flex-1" />
            <Legend mode={mode} />
          </div>
        </div>

        {/* Time Machine slider */}
        {histData && histData.periods.length > 1 && (
          <div className="mx-auto max-w-6xl px-4 py-3" style={{ borderBottom: '1px solid var(--border-dark)' }}>
            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  if (isPlaying) {
                    setIsPlaying(false);
                  } else {
                    if (periodIdx >= histData.periods.length - 1) setPeriodIdx(0);
                    setIsPlaying(true);
                  }
                }}
                className="flex items-center justify-center shrink-0 transition-colors"
                style={{
                  width: 32,
                  height: 32,
                  border: '1px solid var(--border-dark-strong)',
                  background: isPlaying ? 'var(--accent)' : 'transparent',
                  color: isPlaying ? '#fff' : 'var(--text-on-dark-muted)',
                }}
              >
                {isPlaying ? <Pause size={14} /> : <Play size={14} />}
              </button>
              <Clock size={12} style={{ color: 'var(--text-on-dark-muted)', flexShrink: 0 }} />
              <input
                type="range"
                min={0}
                max={histData.periods.length - 1}
                value={periodIdx}
                onChange={(e) => {
                  setIsPlaying(false);
                  setPeriodIdx(parseInt(e.target.value, 10));
                }}
                className="flex-1 h-1.5 appearance-none cursor-pointer"
                style={{
                  background: `linear-gradient(to right, var(--accent) ${(periodIdx / (histData.periods.length - 1)) * 100}%, rgba(255,255,255,0.15) ${(periodIdx / (histData.periods.length - 1)) * 100}%)`,
                  borderRadius: 4,
                  accentColor: 'var(--accent)',
                }}
              />
              <span
                className="font-mono text-sm font-bold tabular-nums shrink-0"
                style={{ color: 'var(--accent-hover)', minWidth: 80, textAlign: 'right' }}
              >
                {periodLabel}
              </span>
            </div>
          </div>
        )}

        {/* Canvas */}
        <div
          ref={containerRef}
          className="relative mx-auto max-w-6xl px-4"
          style={{ minHeight: '500px' }}
        >
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center z-20">
              <div className="flex flex-col items-center gap-4">
                <Loader2
                  size={32}
                  className="animate-spin"
                  style={{ color: 'var(--accent-hover)' }}
                />
                <span className="font-mono text-xs" style={{ color: 'var(--text-on-dark-muted)' }}>
                  Carregando 5.572 municipios...
                </span>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center z-20">
              <div className="text-center p-8">
                <p className="text-base font-semibold" style={{ color: 'var(--text-on-dark)' }}>
                  {error}
                </p>
                <p className="mt-2 text-sm" style={{ color: 'var(--text-on-dark-muted)' }}>
                  Verifique sua conexao e recarregue a pagina.
                </p>
              </div>
            </div>
          )}

          <canvas
            ref={canvasRef}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            style={{
              width: '100%',
              height: 'min(70vh, 700px)',
              cursor: hoveredIdx !== null ? 'crosshair' : 'default',
              display: 'block',
            }}
          />
        </div>

        {/* Source line */}
        <div className="mx-auto max-w-6xl px-4 py-3">
          <p className="font-mono text-[10px]" style={{ color: 'var(--text-on-dark-muted)' }}>
            Cada ponto = 1 municipio. Tamanho proporcional ao numero de assinantes (escala logaritmica).
            Nomes de municipios e provedores omitidos. Dados Anatel STEL.
          </p>
        </div>
      </section>

      {/* ---- Stats Bar ---- */}
      <section style={{ background: 'var(--bg-dark-surface)' }}>
        <div className="mx-auto max-w-6xl px-4">
          <div
            className="grid grid-cols-2 gap-0 md:grid-cols-5"
            style={{ borderTop: '1px solid var(--border-dark-strong)' }}
          >
            {[
              {
                icon: Map,
                value: munisLabel,
                label: 'Municipios mapeados',
                delta: null as string | null,
              },
              {
                icon: Map,
                value: munisWithDataLabel,
                label: 'Com dados de assinantes',
                delta: showDelta && munisDelta !== 0 ? `${munisDelta > 0 ? '+' : ''}${munisDelta.toLocaleString('pt-BR')}` : null,
              },
              {
                icon: Users,
                value: totalSubsLabel,
                label: 'Registros de assinantes',
                delta: showDelta && subsDelta !== 0 ? `${subsDelta > 0 ? '+' : ''}${formatBigNumber(subsDelta)}` : null,
              },
              {
                icon: Activity,
                value: avgPenLabel,
                label: 'Penetracao media',
                delta: showDelta && penDelta !== 0 ? `${penDelta > 0 ? '+' : ''}${penDelta.toFixed(1)}pp` : null,
              },
              {
                icon: BarChart3,
                value: periodsLabel,
                label: 'Periodos disponiveis',
                delta: null,
              },
            ].map((stat) => {
              const Icon = stat.icon;
              return (
                <div
                  key={stat.label}
                  className="py-7 pr-6"
                  style={{ borderBottom: '1px solid var(--border-dark)' }}
                >
                  <div className="flex items-center gap-1.5 mb-2" style={{ color: 'var(--text-on-dark-muted)' }}>
                    <Icon size={12} />
                    <span className="text-[10px] uppercase tracking-wider">{stat.label}</span>
                  </div>
                  <div
                    className="font-mono text-2xl font-bold tabular-nums"
                    style={{ color: 'var(--accent-hover)' }}
                  >
                    {stat.value}
                  </div>
                  {stat.delta && (
                    <div
                      className="mt-1 font-mono text-xs font-semibold"
                      style={{ color: stat.delta.startsWith('+') ? '#22c55e' : '#ef4444' }}
                    >
                      {stat.delta} vs Jan 2023
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ---- What this proves ---- */}
      <Section background="dark" grain>
        <div className="mb-4 font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--accent-hover)' }}>
          O que este mapa prova
        </div>
        <h2
          className="font-serif text-3xl font-bold tracking-tight md:text-4xl max-w-2xl"
          style={{ color: 'var(--text-on-dark)', lineHeight: 1.1 }}
        >
          Dados reais, em todos os cantos do Brasil.{' '}
          <span style={{ color: 'var(--text-on-dark-muted)' }}>Nao simulacao.</span>
        </h2>

        <div
          className="mt-14 grid grid-cols-1 gap-0 md:grid-cols-3"
          style={{ border: '1px solid var(--border-dark-strong)' }}
        >
          {[
            {
              number: '01',
              title: 'Cobertura completa',
              description:
                'Cada municipio brasileiro esta representado. De Sao Paulo com 805 provedores a comunidades rurais com 3. Nenhuma simulacao — cada ponto e real.',
            },
            {
              number: '02',
              title: 'Inteligencia competitiva',
              description:
                'HHI, penetracao, contagem de provedores — tudo calculado a partir de dados oficiais da Anatel. 37 periodos de serie historica para analise de tendencia.',
            },
            {
              number: '03',
              title: 'Anonimizado, mas real',
              description:
                'Nomes de provedores e numeros exatos foram omitidos. Na plataforma completa, voce desbloqueia tudo: nomes, ranking, market share e 28 modulos de analise.',
            },
          ].map((step) => (
            <div
              key={step.number}
              className="p-8"
              style={{
                borderRight: '1px solid var(--border-dark)',
                background: 'var(--bg-dark-surface)',
              }}
            >
              <div className="font-mono text-3xl font-bold" style={{ color: 'var(--accent-hover)' }}>
                {step.number}
              </div>
              <h3 className="mt-3 text-lg font-semibold" style={{ color: 'var(--text-on-dark)' }}>
                {step.title}
              </h3>
              <p
                className="mt-3 text-sm leading-relaxed"
                style={{ color: 'var(--text-on-dark-secondary)' }}
              >
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* ---- CTA ---- */}
      <Section background="dark-surface">
        <div className="text-center max-w-2xl mx-auto">
          <h2
            className="font-serif text-3xl font-bold tracking-tight md:text-4xl"
            style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}
          >
            Quer ver os nomes, os numeros exatos,{' '}
            <span style={{ color: 'var(--text-on-dark-muted)' }}>
              e os 28 modulos de analise?
            </span>
          </h2>
          <p
            className="mt-5 text-base leading-relaxed"
            style={{ color: 'var(--text-on-dark-secondary)' }}
          >
            Desbloqueie a plataforma completa: nomes de provedores, market share exato,
            M&A, conformidade, projeto RF, satelite e mais 22 modulos.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link href="/precos" className="pulso-btn-dark inline-flex items-center gap-2">
              Entrar na lista de espera <ArrowRight size={14} />
            </Link>
            <Link href="/precos" className="pulso-btn-ghost">
              Ver planos
            </Link>
          </div>
          <p className="mt-5 font-mono text-xs" style={{ color: 'var(--text-on-dark-muted)' }}>
            Plano gratuito permanente. Sem cartao de credito.
          </p>
        </div>
      </Section>
    </>
  );
}
