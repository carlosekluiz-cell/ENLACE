'use client';

import { useState, useMemo } from 'react';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import { formatNumber, formatDecimal } from '@/lib/format';
import { Gauge, ArrowUp, ArrowDown, Clock, Trophy, Filter } from 'lucide-react';

// Brazilian UF codes for the state filter dropdown
const UF_OPTIONS = [
  { value: '', label: 'Todos os estados' },
  { value: 'AC', label: 'AC' }, { value: 'AL', label: 'AL' }, { value: 'AM', label: 'AM' },
  { value: 'AP', label: 'AP' }, { value: 'BA', label: 'BA' }, { value: 'CE', label: 'CE' },
  { value: 'DF', label: 'DF' }, { value: 'ES', label: 'ES' }, { value: 'GO', label: 'GO' },
  { value: 'MA', label: 'MA' }, { value: 'MG', label: 'MG' }, { value: 'MS', label: 'MS' },
  { value: 'MT', label: 'MT' }, { value: 'PA', label: 'PA' }, { value: 'PB', label: 'PB' },
  { value: 'PE', label: 'PE' }, { value: 'PI', label: 'PI' }, { value: 'PR', label: 'PR' },
  { value: 'RJ', label: 'RJ' }, { value: 'RN', label: 'RN' }, { value: 'RO', label: 'RO' },
  { value: 'RR', label: 'RR' }, { value: 'RS', label: 'RS' }, { value: 'SC', label: 'SC' },
  { value: 'SE', label: 'SE' }, { value: 'SP', label: 'SP' }, { value: 'TO', label: 'TO' },
];

/** Convert kbps to Mbps, returning a formatted string with 1 decimal. */
function kbpsToMbps(kbps: number | null | undefined): string {
  if (kbps == null) return '--';
  return formatDecimal(kbps / 1000, 1);
}

/** Format latency in ms. */
function fmtLatency(ms: number | null | undefined): string {
  if (ms == null) return '--';
  return formatDecimal(ms, 1);
}

export default function VelocidadePage() {
  const [stateFilter, setStateFilter] = useState('');

  const {
    data: ranking,
    loading,
    error,
  } = useApi(
    () => api.speedtest.ranking({ state: stateFilter || undefined, limit: 100 }),
    [stateFilter],
  );

  // Compute aggregate stats from the ranking data
  const stats = useMemo(() => {
    if (!ranking || ranking.length === 0) {
      return { avgDownload: null, avgUpload: null, avgLatency: null, totalTests: 0 };
    }

    let sumDown = 0;
    let sumUp = 0;
    let sumLat = 0;
    let countDown = 0;
    let countUp = 0;
    let countLat = 0;
    let totalTests = 0;

    for (const r of ranking) {
      if (r.avg_download_kbps != null) { sumDown += r.avg_download_kbps; countDown++; }
      if (r.avg_upload_kbps != null) { sumUp += r.avg_upload_kbps; countUp++; }
      if (r.avg_latency_ms != null) { sumLat += r.avg_latency_ms; countLat++; }
      if (r.tests != null) totalTests += r.tests;
    }

    return {
      avgDownload: countDown > 0 ? sumDown / countDown : null,
      avgUpload: countUp > 0 ? sumUp / countUp : null,
      avgLatency: countLat > 0 ? sumLat / countLat : null,
      totalTests,
    };
  }, [ranking]);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Velocidade da Banda Larga
          </h1>
          <p className="mt-1 text-sm" style={{ color: 'var(--text-muted)' }}>
            Ranking de velocidade por municipio com base em testes reais de banda larga.
          </p>
        </div>

        {/* State filter */}
        <div className="flex items-center gap-2">
          <Filter size={16} style={{ color: 'var(--text-muted)' }} />
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="rounded-md px-3 py-2 text-sm"
            style={{
              background: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border)',
            }}
          >
            {UF_OPTIONS.map((uf) => (
              <option key={uf.value} value={uf.value}>
                {uf.label}
              </option>
            ))}
          </select>
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
          <Gauge size={18} className="shrink-0" style={{ color: 'var(--danger)' }} />
          <p className="text-sm" style={{ color: 'var(--danger)' }}>
            Erro ao carregar dados de velocidade. Verifique sua conexao e tente novamente.
          </p>
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {/* Avg Download */}
        <div
          className="rounded-lg p-4"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                Download Medio
              </p>
              <p
                className="mt-1 text-2xl font-bold"
                style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}
              >
                {loading ? 'Carregando...' : kbpsToMbps(stats.avgDownload)}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Mbps</p>
            </div>
            <ArrowDown size={20} style={{ color: 'var(--accent)' }} />
          </div>
        </div>

        {/* Avg Upload */}
        <div
          className="rounded-lg p-4"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                Upload Medio
              </p>
              <p
                className="mt-1 text-2xl font-bold"
                style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}
              >
                {loading ? 'Carregando...' : kbpsToMbps(stats.avgUpload)}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Mbps</p>
            </div>
            <ArrowUp size={20} style={{ color: 'var(--accent)' }} />
          </div>
        </div>

        {/* Avg Latency */}
        <div
          className="rounded-lg p-4"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                Latencia Media
              </p>
              <p
                className="mt-1 text-2xl font-bold"
                style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}
              >
                {loading ? 'Carregando...' : fmtLatency(stats.avgLatency)}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>ms</p>
            </div>
            <Clock size={20} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
      </div>

      {/* Ranking Table */}
      <div
        className="overflow-hidden rounded-lg"
        style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
      >
        {/* Table header bar */}
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-2">
            <Trophy size={16} style={{ color: 'var(--accent)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Ranking de Velocidade
            </h2>
            {!loading && ranking && (
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                {ranking.length} municipios
                {stats.totalTests > 0 && ` \u00b7 ${formatNumber(stats.totalTests)} testes`}
              </span>
            )}
          </div>
          {stateFilter && (
            <span
              className="rounded-full px-2 py-0.5 text-xs font-medium"
              style={{
                backgroundColor: 'var(--accent-subtle)',
                color: 'var(--accent)',
              }}
            >
              {stateFilter}
            </span>
          )}
        </div>

        {/* Loading skeleton */}
        {loading && (
          <div className="space-y-0">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="flex items-center gap-4 px-4 py-3"
                style={{
                  backgroundColor: i % 2 === 0 ? 'var(--bg-surface)' : 'var(--bg-subtle)',
                }}
              >
                <div
                  className="h-4 w-6 animate-pulse rounded"
                  style={{ backgroundColor: 'var(--border)' }}
                />
                <div
                  className="h-4 flex-1 animate-pulse rounded"
                  style={{ backgroundColor: 'var(--border)' }}
                />
                <div
                  className="h-4 w-16 animate-pulse rounded"
                  style={{ backgroundColor: 'var(--border)' }}
                />
                <div
                  className="h-4 w-16 animate-pulse rounded"
                  style={{ backgroundColor: 'var(--border)' }}
                />
                <div
                  className="h-4 w-16 animate-pulse rounded"
                  style={{ backgroundColor: 'var(--border)' }}
                />
              </div>
            ))}
          </div>
        )}

        {/* Table */}
        {!loading && ranking && ranking.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  style={{
                    borderBottom: '1px solid var(--border)',
                    backgroundColor: 'var(--bg-subtle)',
                  }}
                >
                  <th
                    className="px-4 py-2.5 text-left text-xs font-semibold"
                    style={{ color: 'var(--text-muted)', width: '50px' }}
                  >
                    #
                  </th>
                  <th
                    className="px-4 py-2.5 text-left text-xs font-semibold"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    Municipio
                  </th>
                  <th
                    className="px-4 py-2.5 text-left text-xs font-semibold"
                    style={{ color: 'var(--text-muted)', width: '60px' }}
                  >
                    UF
                  </th>
                  <th
                    className="px-4 py-2.5 text-right text-xs font-semibold"
                    style={{ color: 'var(--text-muted)', width: '120px' }}
                  >
                    <span className="flex items-center justify-end gap-1">
                      <ArrowDown size={12} />
                      Download
                    </span>
                  </th>
                  <th
                    className="px-4 py-2.5 text-right text-xs font-semibold"
                    style={{ color: 'var(--text-muted)', width: '120px' }}
                  >
                    <span className="flex items-center justify-end gap-1">
                      <ArrowUp size={12} />
                      Upload
                    </span>
                  </th>
                  <th
                    className="px-4 py-2.5 text-right text-xs font-semibold"
                    style={{ color: 'var(--text-muted)', width: '100px' }}
                  >
                    <span className="flex items-center justify-end gap-1">
                      <Clock size={12} />
                      Latencia
                    </span>
                  </th>
                  <th
                    className="px-4 py-2.5 text-right text-xs font-semibold"
                    style={{ color: 'var(--text-muted)', width: '90px' }}
                  >
                    Testes
                  </th>
                </tr>
              </thead>
              <tbody>
                {ranking.map((row: any, idx: number) => (
                  <tr
                    key={row.municipality_id ?? idx}
                    style={{
                      backgroundColor: idx % 2 === 0 ? 'var(--bg-surface)' : 'var(--bg-subtle)',
                      borderBottom: '1px solid var(--border)',
                    }}
                  >
                    {/* Position */}
                    <td className="px-4 py-2.5">
                      <span
                        className="text-xs font-bold"
                        style={{
                          color:
                            idx < 3 ? 'var(--accent)' : 'var(--text-muted)',
                        }}
                      >
                        {idx + 1}
                      </span>
                    </td>

                    {/* Municipality name */}
                    <td className="px-4 py-2.5">
                      <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
                        {row.name || row.municipality_name || '--'}
                      </span>
                    </td>

                    {/* State */}
                    <td className="px-4 py-2.5">
                      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        {row.state_abbrev || row.state || '--'}
                      </span>
                    </td>

                    {/* Download Mbps */}
                    <td
                      className="px-4 py-2.5 text-right"
                      style={{ fontVariantNumeric: 'tabular-nums' }}
                    >
                      <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                        {kbpsToMbps(row.avg_download_kbps)}
                      </span>
                      <span className="ml-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                        Mbps
                      </span>
                    </td>

                    {/* Upload Mbps */}
                    <td
                      className="px-4 py-2.5 text-right"
                      style={{ fontVariantNumeric: 'tabular-nums' }}
                    >
                      <span className="font-medium" style={{ color: 'var(--text-secondary)' }}>
                        {kbpsToMbps(row.avg_upload_kbps)}
                      </span>
                      <span className="ml-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                        Mbps
                      </span>
                    </td>

                    {/* Latency ms */}
                    <td
                      className="px-4 py-2.5 text-right"
                      style={{ fontVariantNumeric: 'tabular-nums' }}
                    >
                      <span
                        className="font-medium"
                        style={{
                          color:
                            row.avg_latency_ms != null && row.avg_latency_ms < 20
                              ? 'var(--success)'
                              : row.avg_latency_ms != null && row.avg_latency_ms > 50
                                ? 'var(--danger)'
                                : 'var(--text-secondary)',
                        }}
                      >
                        {fmtLatency(row.avg_latency_ms)}
                      </span>
                      <span className="ml-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                        ms
                      </span>
                    </td>

                    {/* Tests count */}
                    <td
                      className="px-4 py-2.5 text-right"
                      style={{ fontVariantNumeric: 'tabular-nums' }}
                    >
                      <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
                        {row.tests != null ? formatNumber(row.tests) : '--'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Empty state */}
        {!loading && ranking && ranking.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 py-16">
            <Gauge size={32} style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              Nenhum dado de velocidade encontrado
              {stateFilter ? ` para ${stateFilter}` : ''}.
            </p>
          </div>
        )}

        {/* No data loaded yet and no error */}
        {!loading && !ranking && !error && (
          <div className="flex flex-col items-center justify-center gap-3 py-16">
            <Gauge size={32} style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              Nenhum dado de velocidade disponivel.
            </p>
          </div>
        )}
      </div>

      {/* Source attribution */}
      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
        Fonte: Dados de testes de velocidade agregados por municipio. Velocidades exibidas em Mbps (download/upload) e latencia em ms.
      </p>
    </div>
  );
}
