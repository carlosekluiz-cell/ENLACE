// ── ENLACE Audit Types ──
// Mirrors the actual pulso-agent --audit-csv / POST /audit JSON output.
// Regenerated 2026-07-02 against the current engine (528 passing tests).

export interface AuditResponse {
  audit_id: string;
  result: AuditResult;
}

export interface AuditResult {
  summary: AuditSummary;
  import_report?: ImportReport;
  faults: Fault[];
  ghosts: Ghost[];
  capacity: CapacityEntry[];
  flapping: FlappingEntry[];
  weather_correlation: WeatherCorrelation[];
  reflectance: ReflectanceEntry[];
  optical_budget: OpticalBudgetEntry[];
  sfp_health: SfpHealth[];
  fec_health?: FecHealth;
  laser_health?: LaserHealth;
  rogue?: RoguePortFinding[];
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
  unknown?: number;
  avg_rx_dbm: number;
  worst_rx_dbm: number;
}

// Import honesty report: what the CSV importer accepted, skipped, and
// could not parse — emitted with every audit.
export interface ImportReport {
  rows_ok: number;
  rows_skipped: number;
  skip_samples: string[];
  cells_unparsed: number;
  unknown_statuses: number;
  unknown_status_values: string[];
  snapshot_mode: boolean;
  delimiter: string;
}

export interface AffectedOnt {
  serial_number: string;
  distance_meters: number | null;
  had_dying_gasp: boolean;
  last_rx_dbm: number | null;
}

export interface Fault {
  fault_type?: string;
  severity?: string;
  olt_id?: string;
  pon_port?: string;
  affected_onts?: AffectedOnt[];
  detection_latency_seconds?: number;
  timestamp?: string;
}

export interface Ghost {
  ont_serial: string;
  port: string;
  distance_m: number | null;
  rx_power_dbm: number;
  eth_status: string;
  days_online: number;
  // Assumed monthly revenue (= configured ARPU) — an assumption echoed
  // for context, not a measured value.
  estimated_monthly_revenue: number;
}

export interface CapacityEntry {
  port: string;
  olt_id: string;
  active_onts: number;
  max_ports: number;
  utilisation_pct: number;
  splitter_type: string;
  splitter_assumed?: boolean;
  alert_level: string;
  months_to_full: number | null;
  new_connections_per_month: number;
}

export interface FlappingEntry {
  ont_serial?: string;
  port?: string;
  flap_count?: number;
  flap_rate_per_hour?: number;
  severity?: string;
  cascade_risk?: number;
  probable_cause?: string;
  port_ont_count?: number;
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
  confidence?: number;
}

export interface OpticalBudgetEntry {
  ont_serial: string;
  port: string;
  budget_status: string;
  avg_rx_power_dbm?: number;
  avg_tx_power_dbm?: number;
  expected_rx_dbm?: number;
  excess_loss_db?: number;
  excess_threshold_db?: number;
  margin_db?: number;
  distance_m?: number;
  fibre_loss_db?: number;
  connector_loss_db?: number;
  splitter_loss_db?: number;
  splitter_assumed?: boolean;
  probable_issue?: string | null;
}

export interface SfpHealth {
  port: string;
  olt_id: string;
  ont_count: number;
  avg_rx_power_dbm: number;
  rx_trend_per_week: number;
  estimated_weeks_to_failure: number | null;
  severity: string;
  correlation: number;
  is_outlier_vs_siblings: boolean;
}

// Pre-FEC health analysis. Coverage is reported honestly: ONTs without
// FEC counters are not assessed, and the report says so.
export interface FecHealth {
  coverage_note: string;
  findings: FecFinding[];
  onts_with_fec_data: number;
  total_onts: number;
}

export interface FecFinding {
  ont_serial?: string;
  port?: string;
  severity?: string;
  diagnosis?: string;
  evidence?: string[];
}

// Laser end-of-life prediction from bias-current drift, temperature-
// detrended. Coverage counters make gating explicit.
export interface LaserHealth {
  coverage: LaserCoverage;
  predictions: LaserPrediction[];
}

export interface LaserCoverage {
  onts_total: number;
  onts_with_bias: number;
  onts_analyzed: number;
  onts_flagged: number;
  onts_gated_out: number;
  onts_temperature_detrended: number;
}

export interface LaserPrediction {
  ont_serial?: string;
  port?: string;
  classification?: string;
  estimated_days_to_failure?: number | null;
  evidence?: string[];
}

// Passive rogue-ONT detection: multi-victim upstream-corruption scoring.
export interface RoguePortFinding {
  olt: string;
  pon_port: string;
  victim_count: number;
  window_start: string;
  window_end: string;
  evidence: string[];
  candidates: RogueCandidate[];
  confidence: string;
  recommended_action: string;
}

export interface RogueCandidate {
  serial_number: string;
  score: number;
  evidence: string[];
}

export interface ChurnRisk {
  ont_serial: string;
  current_rx_dbm: number;
  days_degrading: number;
  degradation_rate: number;
  estimated_churn_probability_90day: number;
  estimated_annual_revenue_at_risk: number;
  impact: string;
  micro_dropout_count: number;
  // Every £-figure carries its assumptions inline.
  assumptions?: Record<string, number>;
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
  estimated_revenue_at_risk_annual: number;
  fix_cost_estimate: number;
  estimated_roi: number;
  assumptions?: string[];
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
  unknown_activity_onts?: number;
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
  distance_meters: number | null;
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
