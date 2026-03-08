'use client';

import { useState, useCallback } from 'react';
import StatsCard from '@/components/dashboard/StatsCard';
import { useLazyApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import {
  FileText,
  Download,
  Clock,
  CheckCircle2,
  Loader2,
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
    name: 'Análise de Mercado',
    description: 'Análise abrangente de mercado para uma região ou estado específico.',
    icon: <BarChart3 size={20} className="text-blue-400" />,
    fields: [
      {
        key: 'state',
        label: 'Estado',
        type: 'select',
        required: true,
        options: [
          { value: 'SP', label: 'São Paulo' },
          { value: 'RJ', label: 'Rio de Janeiro' },
          { value: 'MG', label: 'Minas Gerais' },
          { value: 'BA', label: 'Bahia' },
          { value: 'PR', label: 'Paraná' },
          { value: 'RS', label: 'Rio Grande do Sul' },
          { value: 'CE', label: 'Ceará' },
          { value: 'PE', label: 'Pernambuco' },
          { value: 'SC', label: 'Santa Catarina' },
          { value: 'GO', label: 'Goiás' },
          { value: 'DF', label: 'Distrito Federal' },
          { value: 'AM', label: 'Amazonas' },
          { value: 'PA', label: 'Pará' },
        ],
      },
      {
        key: 'min_subscribers',
        label: 'Assinantes Mín.',
        type: 'number',
        placeholder: '1000',
      },
      {
        key: 'focus_area',
        label: 'Área de Foco',
        type: 'text',
        placeholder: 'ex: expansão de fibra',
      },
    ],
  },
  {
    id: 'expansion',
    name: 'Plano de Expansão',
    description: 'Planejamento de expansão de rede com pontuação de oportunidades.',
    icon: <Map size={20} className="text-cyan-400" />,
    fields: [
      {
        key: 'target_region',
        label: 'Região Alvo',
        type: 'text',
        required: true,
        placeholder: 'ex: Interior de SP',
      },
      {
        key: 'budget',
        label: 'Orçamento (R$)',
        type: 'number',
        placeholder: '5000000',
      },
      {
        key: 'technology',
        label: 'Tecnologia',
        type: 'select',
        options: [
          { value: 'ftth', label: 'FTTH' },
          { value: 'fwa', label: 'Fixed Wireless' },
          { value: 'hybrid', label: 'Híbrido' },
        ],
      },
      {
        key: 'timeline_months',
        label: 'Prazo (meses)',
        type: 'number',
        placeholder: '12',
      },
    ],
  },
  {
    id: 'compliance',
    name: 'Relatório de Conformidade',
    description: 'Status de conformidade regulatória e avaliação de riscos.',
    icon: <Shield size={20} className="text-green-400" />,
    fields: [
      {
        key: 'provider_name',
        label: 'Nome do Provedor',
        type: 'text',
        required: true,
        placeholder: 'Nome do ISP',
      },
      {
        key: 'cnpj',
        label: 'CNPJ',
        type: 'text',
        placeholder: '00.000.000/0001-00',
      },
      {
        key: 'scope',
        label: 'Escopo do Relatório',
        type: 'select',
        options: [
          { value: 'full', label: 'Conformidade Completa' },
          { value: 'norma4', label: 'Apenas Norma nº 4' },
          { value: 'quality', label: 'Qualidade de Serviço' },
        ],
      },
    ],
  },
  {
    id: 'rural',
    name: 'Conectividade Rural',
    description: 'Análise de viabilidade e financiamento para implantação rural.',
    icon: <Mountain size={20} className="text-amber-400" />,
    fields: [
      {
        key: 'region',
        label: 'Região',
        type: 'text',
        required: true,
        placeholder: 'ex: Norte do Amazonas',
      },
      {
        key: 'population',
        label: 'População Alvo',
        type: 'number',
        placeholder: '50000',
      },
      {
        key: 'include_solar',
        label: 'Incluir Projeto Solar',
        type: 'select',
        options: [
          { value: 'yes', label: 'Sim' },
          { value: 'no', label: 'Não' },
        ],
      },
    ],
  },
];

// ---------------------------------------------------------------------------
// API fetcher map — connects each report type to api.reports.*
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
  market: 'Análise de Mercado',
  expansion: 'Plano de Expansão',
  compliance: 'Relatório de Conformidade',
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

  // Lazy API hooks — one per report type
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

    // Build params — convert number fields from string to number
    const params: Record<string, any> = {};
    for (const field of selectedReport.fields) {
      const raw = formValues[field.key];
      if (raw === undefined || raw === '') continue;
      if (field.type === 'number') {
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

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6 p-6">
      {/* Stats row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatsCard
          title="Relatórios Gerados"
          value={generatedReports.length}
          icon={<FileText size={18} />}
          subtitle="Nesta sessão"
        />
        <StatsCard
          title="Tipos Disponíveis"
          value={reportTypes.length}
          icon={<BarChart3 size={18} />}
          subtitle="Disponíveis"
        />
        <StatsCard
          title="Último Gerado"
          value={
            generatedReports[0]
              ? new Date(generatedReports[0].generated_at).toLocaleTimeString('pt-BR')
              : 'Nenhum'
          }
          icon={<Clock size={18} />}
          subtitle="Mais recente"
        />
      </div>

      {/* Main content: left = type selection, right = config form */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left panel — report type buttons */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-slate-200">
            Selecionar Tipo de Relatório
          </h2>

          {reportTypes.map((type) => (
            <button
              key={type.id}
              onClick={() => handleSelectType(type.id)}
              className={clsx(
                'w-full rounded-lg border p-4 text-left transition-colors',
                selectedType === type.id
                  ? 'border-blue-500 bg-blue-600/10'
                  : 'border-slate-700 bg-slate-800 hover:border-slate-600'
              )}
            >
              <div className="flex items-center gap-3">
                {type.icon}
                <div>
                  <h3 className="text-sm font-medium text-slate-200">
                    {type.name}
                  </h3>
                  <p className="mt-0.5 text-xs text-slate-400">
                    {type.description}
                  </p>
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Right panel — configuration + generated reports */}
        <div className="lg:col-span-2">
          {selectedReport ? (
            <div className="enlace-card">
              <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
                {selectedReport.icon}
                Configurar: {selectedReport.name}
              </h2>

              <div className="space-y-4">
                {selectedReport.fields.map((field) => (
                  <div key={field.key}>
                    <label className="mb-1 block text-xs text-slate-400">
                      {field.label}
                      {field.required && (
                        <span className="ml-1 text-red-400">*</span>
                      )}
                    </label>
                    {field.type === 'select' ? (
                      <select
                        value={formValues[field.key] || ''}
                        onChange={(e) =>
                          handleFieldChange(field.key, e.target.value)
                        }
                        className="enlace-input w-full"
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
                        className="enlace-input w-full"
                      />
                    )}
                  </div>
                ))}

                {/* Error message */}
                {error && (
                  <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
                    {error}
                  </div>
                )}

                {/* Action buttons */}
                <div className="flex gap-3 pt-2">
                  <button
                    onClick={handleGenerate}
                    disabled={generating}
                    className="enlace-btn-primary flex items-center gap-2"
                  >
                    {generating ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <FileText size={16} />
                    )}
                    {generating ? 'Gerando...' : 'Gerar Relatório'}
                  </button>
                  <button
                    onClick={handleCancel}
                    disabled={generating}
                    className="enlace-btn-secondary"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-slate-700 bg-slate-800/50">
              <div className="text-center">
                <FileText
                  size={40}
                  className="mx-auto mb-3 text-slate-600"
                />
                <p className="text-sm text-slate-400">
                  Selecione um tipo de relatório para configurar e gerar
                </p>
              </div>
            </div>
          )}

          {/* Generated reports list */}
          {generatedReports.length > 0 && (
            <div className="mt-6">
              <h2 className="mb-4 text-sm font-semibold text-slate-200">
                Relatórios Gerados
              </h2>
              <div className="space-y-2">
                {generatedReports.map((report) => (
                  <div
                    key={report.id}
                    className="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-800 px-4 py-3"
                  >
                    <div className="flex items-center gap-3">
                      <CheckCircle2
                        size={16}
                        className="text-green-400"
                      />
                      <div>
                        <p className="text-sm font-medium text-slate-200">
                          {report.name}
                        </p>
                        <p className="text-xs text-slate-500">
                          {new Date(report.generated_at).toLocaleString('pt-BR')}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => downloadReportJson(report)}
                      className="enlace-btn-secondary flex items-center gap-1 px-3 py-1 text-xs"
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
