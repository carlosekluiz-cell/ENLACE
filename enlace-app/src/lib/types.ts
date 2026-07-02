// ── Enlace Operations types ──
//
// Typed mirror of pulso-agent's serialized output. Field names are EXACT
// copies of the Rust structs (pulso-agent/src/audit.rs, fault/detector.rs,
// detection/*.rs) verified against a real `--audit-csv` run
// (src/demo/audit-demo.json). Do not "fix" names here — fix the agent.

// ── ONT status vocabulary (vendors/mod.rs OntStatus) ──
// Unknown is a first-class state: unrecognized vendor vocabulary or missing
// status. It is NOT an outage and must never be lumped with Offline.
export type OntStatus =
  | "Online"
  | "Offline"
  | "LowSignal"
  | "Dying"
  | "PowerFail"
  | "FiberCut"
  | "Unknown";

export const OFFLINE_STATUSES: OntStatus[] = ["Offline", "PowerFail", "FiberCut"];
export const ONLINE_STATUSES: OntStatus[] = ["Online", "LowSignal", "Dying"];

// ── Audit result (audit.rs) ──

export interface AuditResult {
  summary: AuditSummary;
  /** Present when the audit was fed from a CSV import; absent otherwise. */
  import_report?: ImportReportSummary;
  faults: FaultEvent[];
  ghosts: GhostCustomer[];
  capacity: CapacityEntry[];
  flapping: FlappingOnt[];
  weather_correlation: WeatherCorrelation[];
  reflectance: ReflectanceEvent[];
  optical_budget: OpticalBudgetEntry[];
  sfp_health: SfpHealth[];
  churn_risk: ChurnRisk[];
  tickets: Ticket[];
  diagnostics: Diagnostics;
  impact: Impact;
  onts: OntData[];
}

/** POST /audit and GET /audit/:id envelope from the agent's HTTP server. */
export interface AuditResponse {
  audit_id: string;
  result: AuditResult;
}

export interface AuditSummary {
  total_onts: number;
  total_readings: number;
  analysis_period_days: number;
  health_score: number;
  /** ONTs Online or LowSignal in the latest snapshot. */
  online: number;
  /** Offline/PowerFail/FiberCut. Unknown-status ONTs are NOT counted here. */
  offline: number;
  /** Status could not be determined. total_onts = online + offline + unknown. */
  unknown: number;
  avg_rx_dbm: number;
  worst_rx_dbm: number;
}

/** CSV import honesty counters (audit.rs ImportReportSummary). */
export interface ImportReportSummary {
  rows_ok: number;
  rows_skipped: number;
  /** Up to 5 sanitized skip messages (paths stripped server-side). */
  skip_samples: string[];
  /** Non-empty cells whose value could not be parsed (kept as null). */
  cells_unparsed: number;
  /** Rows whose status value was not recognized (imported as Unknown). */
  unknown_statuses: number;
  /** Distinct unrecognized status values seen (normalized, up to 10). */
  unknown_status_values: string[];
  /** True when the file had no timestamp column and rows were defaulted. */
  snapshot_mode: boolean;
  delimiter: string;
}

// ── Faults & incidents (fault/detector.rs) ──

export type FaultType = "FibreCut" | "PowerOutage" | "Mixed";

export interface AffectedOnt {
  serial_number: string;
  distance_meters: number | null;
  last_rx_dbm: number | null;
  /** True if this ONT sent a dying gasp (power failure evidence). */
  had_dying_gasp: boolean;
}

export interface FaultEvent {
  timestamp: string;
  pon_port: string;
  olt_id: string;
  severity: string;
  fault_type: FaultType;
  affected_onts: AffectedOnt[];
  detection_latency_seconds: number;
}

export type IncidentAction = "Open" | "Resolve";
export type IncidentScope = "Port" | "Olt";

/**
 * Incident lifecycle update (fault/detector.rs IncidentUpdate): emitted once
 * when an incident opens and once when it resolves. `incident_id` is the
 * stable dedup key ("{olt}:{port}:{opened_at}"). The FaultEvent fields are
 * #[serde(flatten)]ed into this object on the wire.
 */
export interface IncidentUpdate extends FaultEvent {
  action: IncidentAction;
  incident_id: string;
  scope: IncidentScope;
  opened_at: string;
  resolved_at: string | null;
  /** PON ports involved (single entry for port-scope incidents). */
  ports: string[];
}

// ── Detection modules (detection/*.rs) ──

export type GhostEthStatus = "NoLink";

export interface GhostCustomer {
  ont_serial: string;
  port: string;
  distance_m: number | null;
  rx_power_dbm: number;
  eth_status: GhostEthStatus;
  days_online: number;
  /** Assumed monthly revenue (= configured ARPU) — an assumption, not billing. */
  estimated_monthly_revenue: number;
}

export interface CapacityEntry {
  port: string;
  olt_id: string;
  active_onts: number;
  max_ports: number;
  utilisation_pct: number;
  splitter_type: string;
  /** True when the splitter ratio was assumed, not configured. */
  splitter_assumed: boolean;
  alert_level: string;
  months_to_full: number | null;
  new_connections_per_month: number;
}

export interface FlappingOnt {
  ont_serial: string;
  port: string;
  flap_count: number;
  flap_rate_per_hour: number;
  severity: string;
  first_flap: string;
  last_flap: string;
  cascade_risk: number;
  probable_cause: string;
  port_ont_count: number;
}

export interface WeatherCorrelation {
  ont_serials: string[];
  port: string;
  distance_range: [number, number];
  /** Suspected diurnal pattern — not confirmed by any weather feed. */
  pattern: string;
  correlation_strength: number;
  description: string;
}

export interface ReflectanceEvent {
  timestamp: string;
  port: string;
  affected_ont_count: number;
  affected_ont_serials: string[];
  suspect_ont_serial: string;
  suspect_ont_distance_m: number;
  suspect_tx_anomaly_dbm: number;
  confidence: number;
  events_correlated: number;
}

export interface OpticalBudgetEntry {
  ont_serial: string;
  port: string;
  distance_m: number;
  avg_rx_power_dbm: number;
  avg_tx_power_dbm: number;
  expected_rx_dbm: number;
  margin_db: number;
  excess_loss_db: number;
  excess_threshold_db: number;
  fibre_loss_db: number;
  connector_loss_db: number;
  splitter_loss_db: number;
  /** True when the splitter ratio behind the math was assumed. */
  splitter_assumed: boolean;
  budget_status: string;
  probable_issue: string | null;
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

/** The assumption set behind churn probabilities — echoed, never hidden. */
export interface ChurnAssumptions {
  baseline_probability: number;
  subtle_probability: number;
  noticeable_probability: number;
  severe_probability: number;
  micro_dropout_bonus: number;
  monthly_arpu: number;
}

export interface ChurnRisk {
  ont_serial: string;
  current_rx_dbm: number;
  days_degrading: number;
  degradation_rate: number;
  estimated_churn_probability_90day: number;
  estimated_annual_revenue_at_risk: number;
  micro_dropout_count: number;
  impact: string;
  assumptions: ChurnAssumptions;
}

// ── Tickets (detection/tickets.rs) ──

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
  /** The declared assumptions behind every estimated_* figure above. */
  assumptions: string[];
  generated_at: string;
}

/**
 * App-layer enrichment (NOT from the agent): geo comes from joining the
 * ISP's customer records. Absent geo renders as "no location data" — the app
 * never invents coordinates.
 */
export interface TicketGeo {
  lat: number;
  lon: number;
  label?: string;
}

export interface EnrichedTicket extends Ticket {
  geo?: TicketGeo;
}

// ── Diagnostics (diagnostics/mod.rs) ──

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

// ── Impact (detection/impact.rs) ──

export interface Impact {
  fault_id: string;
  affected_onts: number;
  active_onts: number;
  unknown_activity_onts: number;
  impact_score: number;
  priority: string;
  time_sensitivity: string;
}

// ── ONT snapshot rows (vendors/mod.rs OntData) ──

export interface OntData {
  ont_index: number;
  serial_number: string;
  pon_port: string;
  status: OntStatus;
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

// ── Live NOC feed envelope (/api/noc/summary) ──

export interface NocLiveSummary {
  available: true;
  index_pattern: string;
  doc_count: number;
  latest_timestamp: string | null;
  status_counts: Record<string, number>;
}

export interface NocLiveUnavailable {
  available: false;
  /** Honest reason: not configured, unreachable, query failed… */
  reason: string;
}

export type NocSummaryResponse = NocLiveSummary | NocLiveUnavailable;
