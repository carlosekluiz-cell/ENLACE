'use client';

import { useState } from 'react';
import DataTable from '@/components/dashboard/DataTable';
import SimpleChart from '@/components/charts/SimpleChart';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import type { OpportunityScore } from '@/lib/types';
import { TrendingUp, Target, BarChart3, X, AlertTriangle } from 'lucide-react';

const columns = [
  {
    key: 'name',
    label: 'Municipio',
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
    label: 'Pontuacao',
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
    label: 'Populacao',
    sortable: true,
    render: (value: number) => (value ?? 0).toLocaleString('pt-BR'),
  },
  {
    key: 'households',
    label: 'Domicilios',
    sortable: true,
    render: (value: number) => (value ?? 0).toLocaleString('pt-BR'),
  },
  {
    key: 'confidence',
    label: 'Confianca',
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

export default function OpportunitiesPage() {
  const [selectedRow, setSelectedRow] = useState<OpportunityScore | null>(null);

  const {
    data: opportunities,
    loading,
    error,
  } = useApi(() => api.opportunities.top({ limit: '50' }), []);

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
      ? `${opportunities.length} municipios`
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
            Erro ao carregar dados. Verifique sua conexao e tente novamente.
          </p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Maior Pontuacao</p>
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
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Pontuacao Media</p>
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
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Populacao Total</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {loading ? 'Carregando...' : totalPopulation.toLocaleString('pt-BR')}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Habitantes nos municipios analisados</p>
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
                    {selectedRow.state_abbrev} - Cod. {selectedRow.municipality_code}
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
                    Confianca: {((selectedRow.confidence ?? 0) * 100).toFixed(0)}%
                  </p>
                </div>

                <div className="space-y-2">
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Sub-scores</p>
                  <SubScoreBar label="Demanda" value={selectedRow.sub_scores?.demand ?? 0} />
                  <SubScoreBar label="Concorrencia" value={selectedRow.sub_scores?.competition ?? 0} />
                  <SubScoreBar label="Infraestrutura" value={selectedRow.sub_scores?.infrastructure ?? 0} />
                  <SubScoreBar label="Crescimento" value={selectedRow.sub_scores?.growth ?? 0} />
                </div>

                <div className="space-y-2 pt-2">
                  <DetailRow
                    label="Populacao"
                    value={(selectedRow.population ?? 0).toLocaleString('pt-BR')}
                  />
                  <DetailRow
                    label="Domicilios"
                    value={(selectedRow.households ?? 0).toLocaleString('pt-BR')}
                  />
                </div>

                <button className="pulso-btn-primary mt-4 w-full">
                  Ver Analise Completa
                </button>
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
