'use client';

import { useState, useCallback } from 'react';
import { useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import {
  FileText,
  Download,
  Clock,
  CheckCircle2,
  BarChart3,
  Map,
  Shield,
  Mountain,
} from 'lucide-react';
import { clsx } from 'clsx';
import type { ReportResult } from '@/lib/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ReportField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'select';
  placeholder?: string;
  options?: { value: string; label: string }[];
  required?: boolean;
}

interface ReportTypeConfig {
  id: 'market' | 'expansion' | 'compliance' | 'rural';
  name: string;
  description: string;
  icon: React.ReactNode;
  fields: ReportField[];
}

interface GeneratedReport {
  id: string;
  report_type: string;
  name: string;
  generated_at: string;
  content: Record<string, any>;
}

// ---------------------------------------------------------------------------
// Report type definitions (all labels in Portuguese)
// ---------------------------------------------------------------------------

const reportTypes: ReportTypeConfig[] = [
  {
    id: 'market',
    name: 'Analise de Mercado',
    description: 'Analise abrangente de mercado para uma regiao ou estado especifico.',
    icon: <BarChart3 size={20} style={{ color: 'var(--accent)' }} />,
    fields: [
      {
        key: 'municipality_id',
        label: 'Codigo IBGE do Municipio*',
        type: 'number',
        required: true,
        placeholder: 'ex: 3550308 (Sao Paulo)',
      },
      {
        key: 'provider_id',
        label: 'ID do Provedor',
        type: 'number',
        placeholder: 'Opcional',
      },
    ],
  },
  {
    id: 'expansion',
    name: 'Plano de Expansao',
    description: 'Planejamento de expansao de rede com pontuacao de oportunidades.',
    icon: <Map size={20} className="text-cyan-400" />,
    fields: [
      {
        key: 'municipality_id',
        label: 'Codigo IBGE do Municipio*',
        type: 'number',
        required: true,
        placeholder: 'ex: 3550308 (Sao Paulo)',
      },
    ],
  },
  {
    id: 'compliance',
    name: 'Relatorio de Conformidade',
    description: 'Status de conformidade regulatoria e avaliacao de riscos.',
    icon: <Shield size={20} style={{ color: 'var(--success)' }} />,
    fields: [
      {
        key: 'provider_name',
        label: 'Nome do Provedor*',
        type: 'text',
        required: true,
        placeholder: 'Nome do ISP',
      },
      {
        key: 'state_codes',
        label: 'Estados (separados por virgula)*',
        type: 'text',
        required: true,
        placeholder: 'ex: SP,RJ,MG',
      },
      {
        key: 'subscriber_count',
        label: 'Assinantes*',
        type: 'number',
        required: true,
        placeholder: '10000',
      },
      {
        key: 'revenue_monthly',
        label: 'Receita Mensal (R$)',
        type: 'number',
        placeholder: 'Opcional',
      },
    ],
  },
  {
    id: 'rural',
    name: 'Conectividade Rural',
    description: 'Analise de viabilidade e financiamento para implantacao rural.',
    icon: <Mountain size={20} className="text-amber-400" />,
    fields: [
      {
        key: 'community_lat',
        label: 'Latitude*',
        type: 'number',
        required: true,
        placeholder: '-12.9714',
      },
      {
        key: 'community_lon',
        label: 'Longitude*',
        type: 'number',
        required: true,
        placeholder: '-38.5124',
      },
      {
        key: 'population',
        label: 'Populacao*',
        type: 'number',
        required: true,
        placeholder: '2500',
      },
      {
        key: 'area_km2',
        label: 'Area (km2)*',
        type: 'number',
        required: true,
        placeholder: '150',
      },
    ],
  },
];

// ---------------------------------------------------------------------------
// API fetcher map
// ---------------------------------------------------------------------------

const apiFetchers: Record<
  ReportTypeConfig['id'],
  (params: Record<string, any>) => Promise<ReportResult>
> = {
  market: (params) => api.reports.market(params),
  expansion: (params) => api.reports.expansion(params),
  compliance: (params) => api.reports.compliance(params),
  rural: (params) => api.reports.rural(params),
};

// ---------------------------------------------------------------------------
// Helper: download JSON content as a file
// ---------------------------------------------------------------------------

function downloadReportJson(report: GeneratedReport): void {
  const blob = new Blob([JSON.stringify(report.content, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `relatorio-${report.report_type}-${new Date().toISOString().split('T')[0]}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Helper: human-readable report type name (Portuguese)
// ---------------------------------------------------------------------------

const reportTypeNames: Record<string, string> = {
  market: 'Analise de Mercado',
  expansion: 'Plano de Expansao',
  compliance: 'Relatorio de Conformidade',
  rural: 'Conectividade Rural',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ReportsPage() {
  const [selectedType, setSelectedType] = useState<ReportTypeConfig['id'] | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [generatedReports, setGeneratedReports] = useState<GeneratedReport[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Lazy API hooks
  const marketApi = useLazyApi<ReportResult, Record<string, any>>(apiFetchers.market);
  const expansionApi = useLazyApi<ReportResult, Record<string, any>>(apiFetchers.expansion);
  const complianceApi = useLazyApi<ReportResult, Record<string, any>>(apiFetchers.compliance);
  const ruralApi = useLazyApi<ReportResult, Record<string, any>>(apiFetchers.rural);

  const apiHooks: Record<
    ReportTypeConfig['id'],
    typeof marketApi
  > = {
    market: marketApi,
    expansion: expansionApi,
    compliance: complianceApi,
    rural: ruralApi,
  };

  const selectedReport = reportTypes.find((r) => r.id === selectedType) ?? null;
  const generating = selectedType ? apiHooks[selectedType].loading : false;

  const handleFieldChange = useCallback((key: string, value: string) => {
    setFormValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleGenerate = useCallback(async () => {
    if (!selectedType || !selectedReport) return;

    setError(null);
    const hook = apiHooks[selectedType];

    const params: Record<string, any> = {};
    for (const field of selectedReport.fields) {
      const raw = formValues[field.key];
      if (raw === undefined || raw === '') continue;
      if (field.key === 'state_codes') {
        params[field.key] = raw.split(',').map((s: string) => s.trim()).filter(Boolean);
      } else if (field.type === 'number') {
        params[field.key] = Number(raw);
      } else {
        params[field.key] = raw;
      }
    }

    const result = await hook.execute(params);

    if (result) {
      const newReport: GeneratedReport = {
        id: `${selectedType}-${Date.now()}`,
        report_type: result.report_type,
        name: `${reportTypeNames[selectedType] ?? selectedType} - ${new Date(result.generated_at).toLocaleDateString('pt-BR')}`,
        generated_at: result.generated_at,
        content: result.content,
      };
      setGeneratedReports((prev) => [newReport, ...prev]);
      setSelectedType(null);
      setFormValues({});
    } else if (hook.error) {
      setError(hook.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedType, selectedReport, formValues]);

  const handleCancel = useCallback(() => {
    setSelectedType(null);
    setFormValues({});
    setError(null);
  }, []);

  const handleSelectType = useCallback((id: ReportTypeConfig['id']) => {
    setSelectedType(id);
    setFormValues({});
    setError(null);
  }, []);

  return (
    <div className="space-y-6 p-6">
      {/* Stats row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Relatorios Gerados</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{generatedReports.length}</p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Nesta sessao</p>
            </div>
            <FileText size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Tipos Disponiveis</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{reportTypes.length}</p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Disponiveis</p>
            </div>
            <BarChart3 size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Ultimo Gerado</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {generatedReports[0]
                  ? new Date(generatedReports[0].generated_at).toLocaleTimeString('pt-BR')
                  : 'Nenhum'}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Mais recente</p>
            </div>
            <Clock size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left panel -- report type buttons */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Selecionar Tipo de Relatorio
          </h2>

          {reportTypes.map((type) => (
            <button
              key={type.id}
              onClick={() => handleSelectType(type.id)}
              className="w-full rounded-lg border p-4 text-left transition-colors"
              style={{
                borderColor: selectedType === type.id ? 'var(--accent)' : 'var(--border)',
                backgroundColor: selectedType === type.id
                  ? 'color-mix(in srgb, var(--accent) 10%, transparent)'
                  : 'var(--bg-surface)',
              }}
            >
              <div className="flex items-center gap-3">
                {type.icon}
                <div>
                  <h3 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    {type.name}
                  </h3>
                  <p className="mt-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
                    {type.description}
                  </p>
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Right panel -- configuration + generated reports */}
        <div className="lg:col-span-2">
          {selectedReport ? (
            <div className="pulso-card">
              <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {selectedReport.icon}
                Configurar: {selectedReport.name}
              </h2>

              <div className="space-y-4">
                {selectedReport.fields.map((field) => (
                  <div key={field.key}>
                    <label className="mb-1 block text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {field.label}
                      {field.required && (
                        <span className="ml-1" style={{ color: 'var(--danger)' }}>*</span>
                      )}
                    </label>
                    {field.type === 'select' ? (
                      <select
                        value={formValues[field.key] || ''}
                        onChange={(e) =>
                          handleFieldChange(field.key, e.target.value)
                        }
                        className="pulso-input w-full"
                      >
                        <option value="">Selecionar...</option>
                        {field.options?.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type={field.type}
                        value={formValues[field.key] || ''}
                        onChange={(e) =>
                          handleFieldChange(field.key, e.target.value)
                        }
                        placeholder={field.placeholder}
                        className="pulso-input w-full"
                      />
                    )}
                  </div>
                ))}

                {/* Error message */}
                {error && (
                  <div
                    className="rounded-lg px-4 py-3 text-sm"
                    style={{
                      border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
                      backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                      color: 'var(--danger)',
                    }}
                  >
                    {error}
                  </div>
                )}

                {/* Action buttons */}
                <div className="flex gap-3 pt-2">
                  <button
                    onClick={handleGenerate}
                    disabled={generating}
                    className="pulso-btn-primary flex items-center gap-2"
                  >
                    <FileText size={16} />
                    {generating ? 'Gerando...' : 'Gerar Relatorio'}
                  </button>
                  <button
                    onClick={handleCancel}
                    disabled={generating}
                    className="pulso-btn-secondary"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div
              className="flex h-64 items-center justify-center rounded-lg border border-dashed"
              style={{
                borderColor: 'var(--border)',
                backgroundColor: 'color-mix(in srgb, var(--bg-surface) 50%, transparent)',
              }}
            >
              <div className="text-center">
                <FileText
                  size={40}
                  className="mx-auto mb-3"
                  style={{ color: 'var(--text-muted)' }}
                />
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  Selecione um tipo de relatorio para configurar e gerar
                </p>
              </div>
            </div>
          )}

          {/* Generated reports list */}
          {generatedReports.length > 0 && (
            <div className="mt-6">
              <h2 className="mb-4 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Relatorios Gerados
              </h2>
              <div className="space-y-2">
                {generatedReports.map((report) => (
                  <div
                    key={report.id}
                    className="flex items-center justify-between rounded-lg border px-4 py-3"
                    style={{
                      borderColor: 'var(--border)',
                      backgroundColor: 'var(--bg-surface)',
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <CheckCircle2
                        size={16}
                        style={{ color: 'var(--success)' }}
                      />
                      <div>
                        <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                          {report.name}
                        </p>
                        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                          {new Date(report.generated_at).toLocaleString('pt-BR')}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => downloadReportJson(report)}
                      className="pulso-btn-secondary flex items-center gap-1 px-3 py-1 text-xs"
                    >
                      <Download size={14} />
                      Baixar
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
