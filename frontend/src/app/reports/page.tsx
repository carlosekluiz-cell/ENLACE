'use client';

import { useState } from 'react';
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

interface ReportType {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  fields: ReportField[];
}

interface ReportField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'select';
  placeholder?: string;
  options?: { value: string; label: string }[];
  required?: boolean;
}

const reportTypes: ReportType[] = [
  {
    id: 'market',
    name: 'Market Analysis',
    description: 'Comprehensive market analysis for a specific region or state.',
    icon: <BarChart3 size={20} className="text-blue-400" />,
    fields: [
      {
        key: 'state',
        label: 'State',
        type: 'select',
        required: true,
        options: [
          { value: 'SP', label: 'Sao Paulo' },
          { value: 'RJ', label: 'Rio de Janeiro' },
          { value: 'MG', label: 'Minas Gerais' },
          { value: 'BA', label: 'Bahia' },
          { value: 'PR', label: 'Parana' },
          { value: 'RS', label: 'Rio Grande do Sul' },
          { value: 'CE', label: 'Ceara' },
          { value: 'PE', label: 'Pernambuco' },
        ],
      },
      { key: 'min_subscribers', label: 'Min Subscribers', type: 'number', placeholder: '1000' },
      { key: 'focus_area', label: 'Focus Area', type: 'text', placeholder: 'e.g., fiber expansion' },
    ],
  },
  {
    id: 'expansion',
    name: 'Expansion Plan',
    description: 'Network expansion planning with opportunity scoring.',
    icon: <Map size={20} className="text-cyan-400" />,
    fields: [
      { key: 'target_region', label: 'Target Region', type: 'text', required: true, placeholder: 'e.g., Interior SP' },
      { key: 'budget', label: 'Budget (BRL)', type: 'number', placeholder: '5000000' },
      { key: 'technology', label: 'Technology', type: 'select', options: [
        { value: 'ftth', label: 'FTTH' },
        { value: 'fwa', label: 'Fixed Wireless' },
        { value: 'hybrid', label: 'Hybrid' },
      ]},
      { key: 'timeline_months', label: 'Timeline (months)', type: 'number', placeholder: '12' },
    ],
  },
  {
    id: 'compliance',
    name: 'Compliance Report',
    description: 'Regulatory compliance status and risk assessment.',
    icon: <Shield size={20} className="text-green-400" />,
    fields: [
      { key: 'provider_name', label: 'Provider Name', type: 'text', required: true, placeholder: 'ISP Name' },
      { key: 'cnpj', label: 'CNPJ', type: 'text', placeholder: '00.000.000/0001-00' },
      {
        key: 'scope',
        label: 'Report Scope',
        type: 'select',
        options: [
          { value: 'full', label: 'Full Compliance' },
          { value: 'norma4', label: 'Norma No. 4 Only' },
          { value: 'quality', label: 'Quality of Service' },
        ],
      },
    ],
  },
  {
    id: 'rural',
    name: 'Rural Connectivity',
    description: 'Rural deployment feasibility and funding analysis.',
    icon: <Mountain size={20} className="text-amber-400" />,
    fields: [
      { key: 'region', label: 'Region', type: 'text', required: true, placeholder: 'e.g., Northern Amazon' },
      { key: 'population', label: 'Target Population', type: 'number', placeholder: '50000' },
      { key: 'include_solar', label: 'Include Solar Design', type: 'select', options: [
        { value: 'yes', label: 'Yes' },
        { value: 'no', label: 'No' },
      ]},
    ],
  },
];

interface GeneratedReport {
  type: string;
  name: string;
  timestamp: string;
  status: 'ready' | 'generating';
}

export default function ReportsPage() {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [generatedReports, setGeneratedReports] = useState<GeneratedReport[]>([]);
  const [generating, setGenerating] = useState(false);

  const selectedReport = reportTypes.find((r) => r.id === selectedType);

  const handleFieldChange = (key: string, value: string) => {
    setFormValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleGenerate = async () => {
    if (!selectedReport) return;

    setGenerating(true);

    // Simulate report generation
    await new Promise((resolve) => setTimeout(resolve, 2000));

    const newReport: GeneratedReport = {
      type: selectedReport.id,
      name: `${selectedReport.name} - ${new Date().toLocaleDateString('pt-BR')}`,
      timestamp: new Date().toISOString(),
      status: 'ready',
    };

    setGeneratedReports((prev) => [newReport, ...prev]);
    setGenerating(false);
    setSelectedType(null);
    setFormValues({});
  };

  return (
    <div className="space-y-6 p-6">
      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatsCard
          title="Reports Generated"
          value={generatedReports.length}
          icon={<FileText size={18} />}
          subtitle="This session"
        />
        <StatsCard
          title="Report Types"
          value={reportTypes.length}
          icon={<BarChart3 size={18} />}
          subtitle="Available"
        />
        <StatsCard
          title="Last Generated"
          value={
            generatedReports[0]
              ? new Date(generatedReports[0].timestamp).toLocaleTimeString('pt-BR')
              : 'None'
          }
          icon={<Clock size={18} />}
          subtitle="Most recent"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Report type selection */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-slate-200">
            Select Report Type
          </h2>

          {reportTypes.map((type) => (
            <button
              key={type.id}
              onClick={() => {
                setSelectedType(type.id);
                setFormValues({});
              }}
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

        {/* Report configuration */}
        <div className="lg:col-span-2">
          {selectedReport ? (
            <div className="enlace-card">
              <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
                {selectedReport.icon}
                Configure: {selectedReport.name}
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
                        <option value="">Select...</option>
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
                    {generating ? 'Generating...' : 'Generate Report'}
                  </button>
                  <button
                    onClick={() => {
                      setSelectedType(null);
                      setFormValues({});
                    }}
                    className="enlace-btn-secondary"
                  >
                    Cancel
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
                  Select a report type to configure and generate
                </p>
              </div>
            </div>
          )}

          {/* Generated reports history */}
          {generatedReports.length > 0 && (
            <div className="mt-6">
              <h2 className="mb-4 text-sm font-semibold text-slate-200">
                Generated Reports
              </h2>
              <div className="space-y-2">
                {generatedReports.map((report, idx) => (
                  <div
                    key={idx}
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
                          {new Date(report.timestamp).toLocaleString('pt-BR')}
                        </p>
                      </div>
                    </div>
                    <button className="enlace-btn-secondary flex items-center gap-1 px-3 py-1 text-xs">
                      <Download size={14} />
                      Download
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
