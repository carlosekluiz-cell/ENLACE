// ── ENLACE Audit Types ──
// Generated from actual pulso-agent --audit-csv JSON output.

export interface AuditResponse {
  audit_id: string;
  result: AuditResult;
}

export interface AuditResult {
  summary: AuditSummary;
  faults: Fault[];
  ghosts: Ghost[];
  capacity: CapacityEntry[];
  flapping: FlappingEntry[];
  weather_correlation: WeatherCorrelation[];
  reflectance: ReflectanceEntry[];
  optical_budget: OpticalBudgetEntry[];
  sfp_health: SfpHealth[];
  churn_risk: ChurnRisk[];
  tickets: Ticket[];
  diagnostics: Diagnostics;
  impact: Impact;
  onts: OntData[];
}

export interface AuditSummary {
  total_onts: number;
  total_readings: number;
  analysis_period_days: number;
  health_score: number;
  online: number;
  offline: number;
  avg_rx_dbm: number;
  worst_rx_dbm: number;
}

export interface Fault {
  fault_id?: string;
  fault_type?: string;
  severity?: string;
  affected_onts?: string[];
  description?: string;
}

export interface Ghost {
  ont_serial: string;
  port: string;
  rx_power_dbm: number;
  rx_power_variance: number;
  days_online: number;
  distance_m: number;
  estimated_monthly_revenue: number;
  eth_status: string;
}

export interface CapacityEntry {
  port: string;
  olt_id: string;
  active_onts: number;
  max_ports: number;
  utilisation_pct: number;
  splitter_type: string;
  alert_level: string;
  months_to_full: number | null;
  new_connections_per_month: number;
}

export interface FlappingEntry {
  ont_serial?: string;
  port?: string;
  flap_count?: number;
  period_hours?: number;
}

export interface WeatherCorrelation {
  port?: string;
  correlation?: number;
  weather_event?: string;
}

export interface ReflectanceEntry {
  ont_serial?: string;
  port?: string;
  reflectance_db?: number;
}

export interface OpticalBudgetEntry {
  ont_serial?: string;
  port?: string;
  margin_db?: number;
  budget_db?: number;
}

export interface SfpHealth {
  port: string;
  olt_id: string;
  ont_count: number;
  avg_rx_power_dbm: number;
  rx_trend_per_week: number;
  estimated_weeks_to_failure: number;
  severity: string;
  correlation: number;
  is_outlier_vs_siblings: boolean;
}

export interface ChurnRisk {
  ont_serial: string;
  current_rx_dbm: number;
  days_degrading: number;
  degradation_rate: number;
  churn_probability_90day: number;
  monthly_revenue_at_risk: number;
  micro_dropout_count: number;
  impact: string;
}

export interface Ticket {
  ticket_id: string;
  fault_type: string;
  priority: string;
  team: string;
  sla_days: number;
  affected_ont_count: number;
  affected_ont_serials: string[];
  evidence: string[];
  recommended_action: string;
  revenue_at_risk_annual: number;
  fix_cost_estimate: number;
  roi: number;
  generated_at: string;
}

export interface DiagnosticAlert {
  serial_number: string;
  pon_port: string;
  alert_type: string;
  severity: string;
  description: string;
  recommended_action: string;
  support_message: string;
}

export interface DiagnosticSummary {
  total_onts: number;
  online: number;
  offline: number;
  offline_rate_percent: number;
  avg_rx_power_dbm: number;
  worst_rx_power_dbm: number;
  critical_signal: number;
  low_signal: number;
}

export interface Diagnostics {
  olt_id: string;
  overall_health: string;
  timestamp: string;
  alerts: DiagnosticAlert[];
  capacity_warnings: unknown[];
  summary: DiagnosticSummary;
}

export interface Impact {
  fault_id: string;
  affected_onts: number;
  active_onts: number;
  impact_score: number;
  priority: string;
  time_sensitivity: string;
}

export interface OntData {
  ont_index: number;
  serial_number: string;
  pon_port: string;
  status: string;
  rx_power_dbm: number | null;
  tx_power_dbm: number | null;
  distance_meters: number;
  uptime_seconds: number | null;
  equipment_id: string | null;
  firmware_version: string | null;
  vendor_id: string | null;
  eth_speed_mbps: number | null;
  last_down_cause: string | null;
  in_octets: number | null;
  out_octets: number | null;
  extended: Record<string, unknown> | null;
}
