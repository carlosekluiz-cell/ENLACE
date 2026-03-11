'use client';

import { useState, useCallback } from 'react';
import { useApi } from '@/hooks/useApi';
import { api } from '@/lib/api';
import {
  Bell,
  Plus,
  Trash2,
  Check,
  AlertTriangle,
  TrendingDown,
  Users,
  Shield,
  Activity,
  Settings,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AlertRule {
  id: number;
  name: string;
  rule_type: string;
  config: Record<string, any>;
  active: boolean;
  created_at?: string;
}

interface AlertEvent {
  id: number;
  rule_id?: number;
  rule_name?: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  message: string;
  acknowledged: boolean;
  created_at?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RULE_TYPE_LABELS: Record<string, string> = {
  subscriber_drop: 'Queda de assinantes',
  competitor_entry: 'Entrada de concorrente',
  regulatory_deadline: 'Prazo regulatorio',
  quality_degradation: 'Degradacao de qualidade',
  market_share_change: 'Mudanca de market share',
};

const RULE_TYPES = [
  'subscriber_drop',
  'competitor_entry',
  'regulatory_deadline',
  'quality_degradation',
  'market_share_change',
] as const;

const RULE_TYPE_ICON: Record<string, React.ReactNode> = {
  subscriber_drop: <TrendingDown size={14} />,
  competitor_entry: <Users size={14} />,
  regulatory_deadline: <Shield size={14} />,
  quality_degradation: <Activity size={14} />,
  market_share_change: <AlertTriangle size={14} />,
};

const SEVERITY_BADGE: Record<string, string> = {
  high: 'pulso-badge-red',
  medium: 'pulso-badge-yellow',
  low: 'pulso-badge-green',
};

const SEVERITY_LABEL: Record<string, string> = {
  high: 'Alto',
  medium: 'Medio',
  low: 'Baixo',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AlertasPage() {
  // ---- Form state for creating a new rule ----
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formType, setFormType] = useState<string>(RULE_TYPES[0]);
  const [formThreshold, setFormThreshold] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // ---- Action loading states ----
  const [evaluating, setEvaluating] = useState(false);
  const [acknowledgingId, setAcknowledgingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // ---- Data fetching ----
  const {
    data: events,
    loading: eventsLoading,
    error: eventsError,
    refetch: refetchEvents,
  } = useApi<AlertEvent[]>(() => api.alerts.events({ limit: 50 }), []);

  const {
    data: rules,
    loading: rulesLoading,
    error: rulesError,
    refetch: refetchRules,
  } = useApi<AlertRule[]>(() => api.alerts.rules(), []);

  const {
    data: countData,
    refetch: refetchCount,
  } = useApi<{ count: number }>(() => api.alerts.eventCount(true), []);

  // ---- Handlers ----
  const refetchAll = useCallback(() => {
    refetchEvents();
    refetchRules();
    refetchCount();
  }, [refetchEvents, refetchRules, refetchCount]);

  const handleEvaluate = async () => {
    setEvaluating(true);
    try {
      await api.alerts.evaluate();
      refetchAll();
    } catch {
      // Error handled silently
    } finally {
      setEvaluating(false);
    }
  };

  const handleAcknowledge = async (eventId: number) => {
    setAcknowledgingId(eventId);
    try {
      await api.alerts.acknowledge(eventId);
      refetchEvents();
      refetchCount();
    } catch {
      // Error handled silently
    } finally {
      setAcknowledgingId(null);
    }
  };

  const handleDeleteRule = async (ruleId: number) => {
    setDeletingId(ruleId);
    try {
      await api.alerts.deleteRule(ruleId);
      refetchRules();
    } catch {
      // Error handled silently
    } finally {
      setDeletingId(null);
    }
  };

  const handleCreateRule = async () => {
    if (!formName.trim()) return;
    setSubmitting(true);
    try {
      await api.alerts.createRule({
        name: formName.trim(),
        rule_type: formType,
        config: { threshold: parseFloat(formThreshold) || 0 },
        active: true,
      });
      setFormName('');
      setFormType(RULE_TYPES[0]);
      setFormThreshold('');
      setShowForm(false);
      refetchRules();
    } catch {
      // Error handled silently
    } finally {
      setSubmitting(false);
    }
  };

  // ---- Derived data ----
  const sortedEvents = events
    ? [...events].sort((a, b) => {
        const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
        const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
        return dateB - dateA;
      })
    : [];

  const unreadCount = countData?.count ?? 0;

  // ---- Loading state ----
  if (eventsLoading && rulesLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="mb-6 flex items-center gap-3">
          <Bell size={24} style={{ color: 'var(--accent)' }} />
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Alertas
          </h1>
        </div>
        <div className="overflow-hidden" style={{ height: '2px', borderRadius: '1px' }}>
          <div className="pulso-progress-bar w-full" />
        </div>
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3 space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="animate-pulse rounded-lg p-4"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '8px' }}
              >
                <div className="h-4 w-48 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                <div className="mt-2 h-3 w-72 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
              </div>
            ))}
          </div>
          <div className="lg:col-span-2 space-y-3">
            {[1, 2].map((i) => (
              <div
                key={i}
                className="animate-pulse rounded-lg p-4"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '8px' }}
              >
                <div className="h-4 w-36 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
                <div className="mt-2 h-3 w-24 rounded" style={{ backgroundColor: 'var(--bg-subtle)' }} />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bell size={24} style={{ color: 'var(--accent)' }} />
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Alertas
          </h1>
          {unreadCount > 0 && (
            <span
              className="flex items-center justify-center rounded-full text-xs font-bold"
              style={{
                width: '22px',
                height: '22px',
                backgroundColor: 'var(--danger)',
                color: '#fff',
              }}
            >
              {unreadCount}
            </span>
          )}
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* ============================================================ */}
        {/* LEFT COLUMN: Alert Events (60%) */}
        {/* ============================================================ */}
        <div className="lg:col-span-3 space-y-4">
          {/* Actions bar */}
          <div className="flex items-center justify-between">
            <h2
              className="flex items-center gap-2 text-sm font-semibold"
              style={{ color: 'var(--text-primary)' }}
            >
              <AlertTriangle size={16} style={{ color: 'var(--accent)' }} />
              Eventos de Alerta
            </h2>
            <button
              onClick={handleEvaluate}
              disabled={evaluating}
              className="pulso-btn-primary flex items-center gap-2 text-sm"
            >
              <Activity size={14} />
              {evaluating ? 'Avaliando...' : 'Avaliar Regras'}
            </button>
          </div>

          {/* Error state */}
          {eventsError && (
            <div
              className="rounded-lg p-3 text-sm"
              style={{
                backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                color: 'var(--danger)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
              }}
            >
              <span className="font-medium">Erro:</span> {eventsError}
            </div>
          )}

          {/* Empty state */}
          {!eventsLoading && sortedEvents.length === 0 && !eventsError && (
            <div
              className="flex flex-col items-center justify-center py-16 text-center"
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
              }}
            >
              <Bell size={40} style={{ color: 'var(--text-muted)', opacity: 0.4 }} />
              <p
                className="mt-3 text-sm font-medium"
                style={{ color: 'var(--text-muted)' }}
              >
                Nenhum alerta encontrado
              </p>
              <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Clique em &quot;Avaliar Regras&quot; para verificar suas regras configuradas.
              </p>
            </div>
          )}

          {/* Events list */}
          {sortedEvents.map((event) => (
            <div
              key={event.id}
              style={{
                background: 'var(--bg-surface)',
                border: `1px solid ${event.acknowledged ? 'var(--border)' : 'color-mix(in srgb, var(--accent) 30%, var(--border))'}`,
                borderRadius: '8px',
                opacity: event.acknowledged ? 0.75 : 1,
              }}
              className="p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className={SEVERITY_BADGE[event.severity] || 'pulso-badge-yellow'}>
                      {SEVERITY_LABEL[event.severity] || event.severity}
                    </span>
                    <h3
                      className="text-sm font-semibold truncate"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {event.title}
                    </h3>
                  </div>
                  <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
                    {event.message}
                  </p>
                  <div className="flex items-center gap-3 mt-2">
                    {event.created_at && (
                      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        {new Date(event.created_at).toLocaleString('pt-BR')}
                      </span>
                    )}
                    {event.rule_name && (
                      <span
                        className="text-xs rounded px-1.5 py-0.5"
                        style={{
                          backgroundColor: 'var(--bg-subtle)',
                          color: 'var(--text-muted)',
                        }}
                      >
                        {event.rule_name}
                      </span>
                    )}
                    {event.acknowledged && (
                      <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--success)' }}>
                        <Check size={10} />
                        Lido
                      </span>
                    )}
                  </div>
                </div>

                {/* Acknowledge button */}
                {!event.acknowledged && (
                  <button
                    onClick={() => handleAcknowledge(event.id)}
                    disabled={acknowledgingId === event.id}
                    className="flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-opacity hover:opacity-80"
                    style={{
                      backgroundColor: 'color-mix(in srgb, var(--success) 15%, transparent)',
                      color: 'var(--success)',
                      border: '1px solid color-mix(in srgb, var(--success) 30%, transparent)',
                    }}
                  >
                    <Check size={12} />
                    {acknowledgingId === event.id ? 'Marcando...' : 'Marcar como lido'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* ============================================================ */}
        {/* RIGHT COLUMN: Alert Rules (40%) */}
        {/* ============================================================ */}
        <div className="lg:col-span-2 space-y-4">
          {/* Rules header */}
          <div className="flex items-center justify-between">
            <h2
              className="flex items-center gap-2 text-sm font-semibold"
              style={{ color: 'var(--text-primary)' }}
            >
              <Settings size={16} style={{ color: 'var(--accent)' }} />
              Regras de Alerta
            </h2>
            <button
              onClick={() => setShowForm(!showForm)}
              className="pulso-btn-primary flex items-center gap-2 text-sm"
            >
              <Plus size={14} />
              Nova Regra
            </button>
          </div>

          {/* Create rule form */}
          {showForm && (
            <div
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--accent)',
                borderRadius: '8px',
              }}
              className="p-4 space-y-3"
            >
              <h3
                className="text-xs font-semibold uppercase"
                style={{ color: 'var(--text-secondary)' }}
              >
                Nova Regra
              </h3>

              <div>
                <label
                  className="mb-1 block text-xs"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Nome
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="Nome da regra"
                  className="pulso-input w-full"
                />
              </div>

              <div>
                <label
                  className="mb-1 block text-xs"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Tipo
                </label>
                <select
                  value={formType}
                  onChange={(e) => setFormType(e.target.value)}
                  className="pulso-input w-full"
                >
                  {RULE_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {RULE_TYPE_LABELS[t]}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  className="mb-1 block text-xs"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Threshold
                </label>
                <input
                  type="number"
                  value={formThreshold}
                  onChange={(e) => setFormThreshold(e.target.value)}
                  placeholder="Valor do threshold"
                  className="pulso-input w-full"
                />
              </div>

              <div className="flex gap-2 pt-1">
                <button
                  onClick={handleCreateRule}
                  disabled={submitting || !formName.trim()}
                  className="pulso-btn-primary flex-1 flex items-center justify-center gap-2 text-sm"
                >
                  <Plus size={14} />
                  {submitting ? 'Criando...' : 'Criar Regra'}
                </button>
                <button
                  onClick={() => setShowForm(false)}
                  className="flex-1 rounded-md py-2 text-sm font-medium transition-opacity hover:opacity-80"
                  style={{
                    backgroundColor: 'var(--bg-subtle)',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border)',
                  }}
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}

          {/* Rules error */}
          {rulesError && (
            <div
              className="rounded-lg p-3 text-sm"
              style={{
                backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                color: 'var(--danger)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
              }}
            >
              <span className="font-medium">Erro:</span> {rulesError}
            </div>
          )}

          {/* Rules empty state */}
          {!rulesLoading && rules && rules.length === 0 && !rulesError && (
            <div
              className="flex flex-col items-center justify-center py-12 text-center"
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
              }}
            >
              <Settings size={32} style={{ color: 'var(--text-muted)', opacity: 0.4 }} />
              <p className="mt-2 text-sm" style={{ color: 'var(--text-muted)' }}>
                Nenhuma regra configurada.
              </p>
              <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                Clique em &quot;Nova Regra&quot; para comecar.
              </p>
            </div>
          )}

          {/* Rules list */}
          {rules &&
            rules.map((rule) => (
              <div
                key={rule.id}
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  borderRadius: '8px',
                }}
                className="p-4"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h3
                        className="text-sm font-semibold truncate"
                        style={{ color: 'var(--text-primary)' }}
                      >
                        {rule.name}
                      </h3>
                      {/* Active indicator */}
                      <span
                        className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
                        style={{
                          backgroundColor: rule.active
                            ? 'color-mix(in srgb, var(--success) 15%, transparent)'
                            : 'color-mix(in srgb, var(--text-muted) 15%, transparent)',
                          color: rule.active ? 'var(--success)' : 'var(--text-muted)',
                        }}
                      >
                        <span
                          style={{
                            width: '6px',
                            height: '6px',
                            borderRadius: '50%',
                            backgroundColor: rule.active ? 'var(--success)' : 'var(--text-muted)',
                            display: 'inline-block',
                          }}
                        />
                        {rule.active ? 'Ativa' : 'Inativa'}
                      </span>
                    </div>

                    {/* Type badge */}
                    <div className="flex items-center gap-1.5 mt-1">
                      <span
                        className="flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium"
                        style={{
                          backgroundColor: 'var(--bg-subtle)',
                          color: 'var(--text-secondary)',
                          border: '1px solid var(--border)',
                        }}
                      >
                        {RULE_TYPE_ICON[rule.rule_type] || <AlertTriangle size={12} />}
                        {RULE_TYPE_LABELS[rule.rule_type] || rule.rule_type}
                      </span>
                    </div>

                    {/* Config details */}
                    {rule.config?.threshold != null && (
                      <p className="mt-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                        Threshold: {rule.config.threshold}
                      </p>
                    )}
                  </div>

                  {/* Delete button */}
                  <button
                    onClick={() => handleDeleteRule(rule.id)}
                    disabled={deletingId === rule.id}
                    className="rounded-md p-1.5 transition-opacity hover:opacity-80"
                    style={{
                      backgroundColor: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                      color: 'var(--danger)',
                    }}
                    title="Excluir regra"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
