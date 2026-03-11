'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { fetchReportDownload, api } from '@/lib/api';
import {
  FileText,
  Download,
  Clock,
  CheckCircle2,
  BarChart3,
  Map,
  Shield,
  Mountain,
  Loader2,
  MapPin,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ReportField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'municipality';
  placeholder?: string;
  options?: { value: string; label: string }[];
  required?: boolean;
}

interface MunicipalityResult {
  id: number;
  code: string;
  name: string;
  state_abbrev: string;
}

interface ReportTypeConfig {
  id: 'market' | 'expansion' | 'compliance' | 'rural';
  name: string;
  description: string;
  icon: React.ReactNode;
  apiPath: string;
  fields: ReportField[];
}

interface GeneratedReport {
  id: string;
  type: string;
  name: string;
  generated_at: string;
  blob: Blob;
  filename: string;
}

// ---------------------------------------------------------------------------
// Report type definitions
// ---------------------------------------------------------------------------

const reportTypes: ReportTypeConfig[] = [
  {
    id: 'market',
    name: 'Análise de Mercado',
    description: 'Análise abrangente de mercado para uma região ou estado específico.',
    icon: <BarChart3 size={20} style={{ color: 'var(--accent)' }} />,
    apiPath: '/api/v1/reports/market',
    fields: [
      {
        key: 'municipality_id',
        label: 'Município',
        type: 'municipality',
        required: true,
        placeholder: 'Digite o nome da cidade...',
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
    name: 'Plano de Expansão',
    description: 'Planejamento de expansão de rede com pontuação de oportunidades.',
    icon: <Map size={20} className="text-cyan-400" />,
    apiPath: '/api/v1/reports/expansion',
    fields: [
      {
        key: 'municipality_id',
        label: 'Município',
        type: 'municipality',
        required: true,
        placeholder: 'Digite o nome da cidade...',
      },
    ],
  },
  {
    id: 'compliance',
    name: 'Relatório de Conformidade',
    description: 'Status de conformidade regulatória e avaliação de riscos.',
    icon: <Shield size={20} style={{ color: 'var(--success)' }} />,
    apiPath: '/api/v1/reports/compliance',
    fields: [
      {
        key: 'provider_name',
        label: 'Nome do Provedor',
        type: 'text',
        required: true,
        placeholder: 'Nome do ISP',
      },
      {
        key: 'state_codes',
        label: 'Estados (separados por vírgula)',
        type: 'text',
        required: true,
        placeholder: 'ex: SP,RJ,MG',
      },
      {
        key: 'subscriber_count',
        label: 'Assinantes',
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
    description: 'Análise de viabilidade e financiamento para implantação rural.',
    icon: <Mountain size={20} className="text-amber-400" />,
    apiPath: '/api/v1/reports/rural',
    fields: [
      {
        key: 'community_lat',
        label: 'Latitude',
        type: 'number',
        required: true,
        placeholder: '-12.9714',
      },
      {
        key: 'community_lon',
        label: 'Longitude',
        type: 'number',
        required: true,
        placeholder: '-38.5124',
      },
      {
        key: 'population',
        label: 'População',
        type: 'number',
        required: true,
        placeholder: '2500',
      },
      {
        key: 'area_km2',
        label: 'Área (km²)',
        type: 'number',
        required: true,
        placeholder: '150',
      },
    ],
  },
];

// ---------------------------------------------------------------------------
// Helper: trigger browser download
// ---------------------------------------------------------------------------

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Municipality autocomplete field
// ---------------------------------------------------------------------------

function MunicipalityField({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (code: string, display: string) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MunicipalityResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [displayValue, setDisplayValue] = useState('');
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleInput = (text: string) => {
    setQuery(text);
    setDisplayValue(text);
    // Clear the selected code if user types again
    if (value) onChange('', '');

    clearTimeout(timerRef.current);
    if (text.length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    timerRef.current = setTimeout(async () => {
      try {
        const data = await api.geo.search(text, 8);
        setResults(data as MunicipalityResult[]);
        setOpen(data.length > 0);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);
  };

  const handleSelect = (m: MunicipalityResult) => {
    const display = `${m.name} — ${m.state_abbrev}`;
    setDisplayValue(display);
    setQuery(display);
    onChange(m.code, display);
    setOpen(false);
  };

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <MapPin
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2"
          style={{ color: 'var(--text-muted)' }}
        />
        <input
          type="text"
          value={displayValue}
          onChange={(e) => handleInput(e.target.value)}
          placeholder={placeholder}
          className="pulso-input w-full pl-9"
        />
        {loading && (
          <Loader2
            size={14}
            className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin"
            style={{ color: 'var(--text-muted)' }}
          />
        )}
      </div>

      {open && results.length > 0 && (
        <div
          className="absolute z-50 mt-1 max-h-48 w-full overflow-y-auto rounded-lg border shadow-lg"
          style={{
            borderColor: 'var(--border)',
            backgroundColor: 'var(--bg-surface)',
          }}
        >
          {results.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => handleSelect(m)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-white/5"
              style={{ color: 'var(--text-primary)' }}
            >
              <MapPin size={12} style={{ color: 'var(--accent)' }} />
              <span>{m.name}</span>
              <span className="ml-auto text-xs" style={{ color: 'var(--text-muted)' }}>
                {m.state_abbrev} — {m.code}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ReportsPage() {
  const [selectedType, setSelectedType] = useState<ReportTypeConfig['id'] | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [generatedReports, setGeneratedReports] = useState<GeneratedReport[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const selectedReport = reportTypes.find((r) => r.id === selectedType) ?? null;

  const handleFieldChange = useCallback((key: string, value: string) => {
    setFormValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleGenerate = useCallback(async () => {
    if (!selectedType || !selectedReport) return;

    // Validate required fields
    for (const field of selectedReport.fields) {
      if (field.required && !formValues[field.key]?.trim()) {
        setError(`Campo obrigatório: ${field.label}`);
        return;
      }
    }

    setError(null);
    setGenerating(true);

    try {
      const params: Record<string, any> = {};
      for (const field of selectedReport.fields) {
        const raw = formValues[field.key];
        if (raw === undefined || raw === '') continue;
        if (field.key === 'state_codes') {
          params[field.key] = raw.split(',').map((s) => s.trim()).filter(Boolean);
        } else if (field.type === 'number' || field.type === 'municipality') {
          params[field.key] = Number(raw);
        } else {
          params[field.key] = raw;
        }
      }

      const { blob, filename } = await fetchReportDownload(selectedReport.apiPath, params);

      // Auto-download
      triggerDownload(blob, filename);

      // Track in session
      const newReport: GeneratedReport = {
        id: `${selectedType}-${Date.now()}`,
        type: selectedReport.name,
        name: filename,
        generated_at: new Date().toISOString(),
        blob,
        filename,
      };
      setGeneratedReports((prev) => [newReport, ...prev]);
      setSelectedType(null);
      setFormValues({});
    } catch (e: any) {
      setError(e.message || 'Erro ao gerar relatório');
    } finally {
      setGenerating(false);
    }
  }, [selectedType, selectedReport, formValues]);

  const handleCancel = useCallback(() => {
    setSelectedType(null);
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
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Relatórios Gerados</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{generatedReports.length}</p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Nesta sessão</p>
            </div>
            <FileText size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Tipos Disponíveis</p>
              <p className="mt-1 text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{reportTypes.length}</p>
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Disponíveis</p>
            </div>
            <BarChart3 size={18} style={{ color: 'var(--accent)' }} />
          </div>
        </div>
        <div className="pulso-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Último Gerado</p>
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
            Selecionar Tipo de Relatório
          </h2>

          {reportTypes.map((type) => (
            <button
              key={type.id}
              onClick={() => {
                setSelectedType(type.id);
                setFormValues({});
                setError(null);
              }}
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
                    {field.type === 'municipality' ? (
                      <MunicipalityField
                        value={formValues[field.key] || ''}
                        onChange={(code) => handleFieldChange(field.key, code)}
                        placeholder={field.placeholder}
                      />
                    ) : (
                      <input
                        type={field.type === 'number' ? 'text' : field.type}
                        inputMode={field.type === 'number' ? 'numeric' : undefined}
                        value={formValues[field.key] || ''}
                        onChange={(e) => handleFieldChange(field.key, e.target.value)}
                        placeholder={field.placeholder}
                        className="pulso-input w-full"
                      />
                    )}
                  </div>
                ))}

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

                <div className="flex gap-3 pt-2">
                  <button
                    onClick={handleGenerate}
                    disabled={generating}
                    className="pulso-btn-primary flex items-center gap-2"
                  >
                    {generating ? (
                      <>
                        <Loader2 size={16} className="animate-spin" />
                        Gerando...
                      </>
                    ) : (
                      <>
                        <FileText size={16} />
                        Gerar Relatório
                      </>
                    )}
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
                <FileText size={40} className="mx-auto mb-3" style={{ color: 'var(--text-muted)' }} />
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  Selecione um tipo de relatório para configurar e gerar
                </p>
              </div>
            </div>
          )}

          {/* Generated reports list */}
          {generatedReports.length > 0 && (
            <div className="mt-6">
              <h2 className="mb-4 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Relatórios Gerados
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
                      <CheckCircle2 size={16} style={{ color: 'var(--success)' }} />
                      <div>
                        <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                          {report.type}
                        </p>
                        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                          {report.filename} — {new Date(report.generated_at).toLocaleString('pt-BR')}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => triggerDownload(report.blob, report.filename)}
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
