// Tipos TypeScript correspondentes aos schemas do backend Pulso

export interface Municipality {
  id: number;
  code: string;
  name: string;
  state_abbrev?: string;
  country_code: string;
  population?: number;
  area_km2?: number;
  latitude?: number;
  longitude?: number;
}

export interface OpportunityScore {
  municipality_id: number;
  municipality_code: string;
  name: string;
  state_abbrev: string;
  composite_score: number;
  confidence: number;
  sub_scores: {
    demand: number;
    competition: number;
    infrastructure: number;
    growth: number;
  };
  area_km2: number | null;
  households: number;
  population: number;
  latitude: number | null;
  longitude: number | null;
}

export interface BaseStationPoint {
  id: number;
  latitude: number;
  longitude: number;
  technology: string;
  frequency_mhz: number | null;
  provider_name: string | null;
}

export interface MarketSummary {
  municipality_id: number;
  code?: string;
  name?: string;
  municipality_name?: string;
  state_abbrev: string;
  year_month?: string;
  total_subscribers: number;
  fiber_subscribers: number;
  provider_count: number;
  total_households?: number | null;
  total_population?: number | null;
  broadband_penetration_pct: number | null;
  fiber_share_pct: number | null;
  median_speed_mbps?: number;
  avg_arpu?: number;
}

export interface HeatmapFeatureCollection {
  type: 'FeatureCollection';
  features: HeatmapFeature[];
}

export interface HeatmapFeature {
  type: 'Feature';
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: {
    municipality_id: number;
    code: string;
    name: string;
    state_abbrev: string;
    metric: string;
    value: number | null;
    total_subscribers: number;
    provider_count: number;
  };
}

export interface ComplianceRegulation {
  id: string;
  name: string;
  agency: string;
  category: string;
  description: string;
  effective_date?: string;
  status: 'active' | 'pending' | 'revoked';
}

export interface ComplianceCheck {
  regulation_id: string;
  regulation_name: string;
  status: string;
  description: string;
  action_items: string[];
  deadline: string | null;
  estimated_cost_brl: number | null;
  priority: number;
  urgency: string;
}

export interface ComplianceStatus {
  provider_id: number | null;
  provider_name: string;
  state_codes: string[];
  subscriber_count: number;
  checks: ComplianceCheck[];
  overall_status?: string;
}

export interface Norma4Impact {
  state_code: string;
  icms_rate: number;
  monthly_revenue_brl: number;
  additional_monthly_tax_brl: number;
  additional_annual_tax_brl: number;
  pct_of_revenue: number;
  subscriber_count: number;
  arpu_brl: number;
  restructuring_options: {
    strategy: string;
    description: string;
    score: number;
    pros: string[];
    cons: string[];
    estimated_monthly_savings_brl: number;
    implementation_months: number;
  }[];
  recommended_action: string;
  days_until_deadline: number;
  readiness_score: number;
}

export interface LicensingCheck {
  subscriber_count: number;
  threshold: number;
  above_threshold: boolean;
  pct_of_threshold: number;
  requirements: string[];
  estimated_licensing_cost_brl: number;
  estimated_annual_cost_brl: number;
  urgency: string;
  subscribers_until_threshold: number;
  recommendation: string;
}

export interface ComplianceDeadline {
  regulation_id: string;
  name: string;
  deadline_date: string;
  description: string;
  urgency: string;
  days_remaining: number;
  milestone: boolean;
}

export interface RuralCommunity {
  name: string;
  latitude: number;
  longitude: number;
  population: number;
  area_km2: number;
  has_power: boolean;
}

export interface RuralDesign {
  backhaul_technology: string;
  backhaul_details: {
    provider: string;
    total_estimated_cost_brl: number;
    monthly_service_brl: number;
    capacity_mbps: number;
    latency_ms: number;
    rationale: string;
  };
  last_mile_technology: string;
  last_mile_details: {
    sites: number;
    cpes: number;
    subscribers: number;
    effective_radius_km: number;
    total_estimated_cost_brl: number;
    monthly_cost_brl: number;
    coverage_km2: number;
    rationale: string;
  };
  power_solution: string;
  power_details: {
    estimated_power_kw: number;
    battery_kwh: number;
    total_estimated_cost_brl: number;
    monthly_cost_brl: number;
    rationale: string;
  };
  equipment_list: {
    category: string;
    item: string;
    quantity: number;
    unit: string;
    unit_cost_brl: number;
    total_cost_brl: number;
  }[];
  estimated_capex_brl: number;
  estimated_monthly_opex_brl: number;
  coverage_estimate_km2: number;
  max_subscribers: number;
  design_notes: string[];
}

export interface FundingProgram {
  id: string;
  name: string;
  full_name: string;
  description: string;
  eligibility_criteria: string[];
  max_funding_brl: number;
  funding_type: string;
  application_url: string;
  deadline: string | null;
  notes: string;
}

export interface FundingMatch {
  matched_programs: FundingProgram[];
  total_available: number;
  eligibility_notes: string[];
}

export interface ReportResult {
  report_type: string;
  content: Record<string, any>;
  generated_at: string;
}

export interface ApiHealth {
  status: string;
  version?: string;
  timestamp?: string;
}

export interface Provider {
  id: number;
  name: string;
  cnpj?: string;
  type?: string;
  subscribers?: number;
}

// ---------------------------------------------------------------------------
// Auth types
// ---------------------------------------------------------------------------

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  tenant_id: string;
  role: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  organization: string;
  state_code?: string;
  country_code?: string;
}

export interface RegisterResponse {
  user_id: string;
  email: string;
  tenant_id: string;
  organization: string;
  access_token: string;
  token_type: string;
}

export interface UserProfile {
  user_id: string;
  email: string;
  full_name: string;
  tenant_id: string;
  role: 'admin' | 'manager' | 'analyst' | 'viewer';
  anonymous: boolean;
  is_active?: boolean;
  preferences?: UserPreferences;
  tenant?: Record<string, any> | null;
}

export interface UserPreferences {
  theme?: 'dark' | 'light' | 'system';
  language?: 'pt-BR' | 'en';
  notifications?: boolean;
}

export interface UpdateProfileRequest {
  full_name?: string;
  email?: string;
  preferences?: UserPreferences;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
  tenant_id: string;
  is_active: boolean;
  created_at?: string;
}

export interface CreateUserRequest {
  email: string;
  password: string;
  full_name: string;
  role: string;
  tenant_id?: string;
}

export interface PipelineRun {
  id: number;
  pipeline_name: string;
  started_at?: string;
  completed_at?: string;
  status: string;
  rows_processed?: number;
  rows_inserted?: number;
  error_message?: string;
}

export interface SSEEvent {
  type: string;
  data: Record<string, any>;
  timestamp: string;
}

export interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
  timestamp: Date;
}

// ---------------------------------------------------------------------------
// M&A types
// ---------------------------------------------------------------------------

export interface ValuationRequest {
  subscriber_count: number;
  fiber_pct: number;
  monthly_revenue_brl: number;
  ebitda_margin_pct: number;
  state_code: string;
  monthly_churn_pct: number;
  growth_rate_12m: number;
  net_debt_brl: number;
}

export interface ValuationResponse {
  subscriber_multiple: Record<string, any>;
  revenue_multiple: Record<string, any>;
  dcf: Record<string, any>;
  combined_range: { low_brl: number; mid_brl: number; high_brl: number };
}

export interface TargetsRequest {
  acquirer_states: string[];
  acquirer_subscribers: number;
  min_subs: number;
  max_subs: number;
}

export interface AcquisitionTarget {
  provider_id: number;
  provider_name: string;
  state_codes: string[];
  subscriber_count: number;
  fiber_pct: number;
  estimated_revenue_brl: number;
  valuation_subscriber: number;
  valuation_revenue: number;
  valuation_dcf: number;
  strategic_score: number;
  financial_score: number;
  integration_risk: string;
  synergy_estimate_brl: number;
  overall_score: number;
}

export interface SellerPrepareRequest {
  provider_name: string;
  state_codes: string[];
  subscriber_count: number;
  fiber_pct: number;
  monthly_revenue_brl: number;
  ebitda_margin_pct: number;
  net_debt_brl: number;
}

export interface SellerReport {
  provider_name: string;
  subscriber_count: number;
  estimated_value_range: number[];
  valuation_methods: Record<string, any>;
  strengths: string[];
  weaknesses: string[];
  value_enhancement_opportunities: Record<string, any>[];
  preparation_checklist: Record<string, any>[];
  estimated_timeline_months: number;
}

export interface MnaMarketOverview {
  state: string;
  total_isps: number;
  total_subscribers: number;
  avg_valuation_per_sub: number;
  fiber_pct_avg: number;
  recent_transactions: Record<string, any>[];
}

// ---------------------------------------------------------------------------
// Design / RF types
// ---------------------------------------------------------------------------

export interface CoverageRequest {
  tower_lat: number;
  tower_lon: number;
  tower_height_m: number;
  frequency_mhz: number;
  tx_power_dbm: number;
  antenna_gain_dbi: number;
  radius_m: number;
  grid_resolution_m: number;
  apply_vegetation: boolean;
  country_code: string;
}

export interface CoverageResult {
  coverage_pct: number;
  coverage_area_km2: number;
  avg_signal_dbm: number;
  min_signal_dbm: number;
  max_signal_dbm: number;
  grid: { lat: number; lon: number; signal_dbm: number }[];
}

export interface OptimizeRequest {
  center_lat: number;
  center_lon: number;
  radius_m: number;
  coverage_target_pct: number;
  min_signal_dbm: number;
  max_towers: number;
  frequency_mhz: number;
  tx_power_dbm: number;
  antenna_gain_dbi: number;
  antenna_height_m: number;
}

export interface LinkBudgetRequest {
  frequency_ghz: number;
  distance_km: number;
  tx_power_dbm: number;
  tx_antenna_gain_dbi: number;
  rx_antenna_gain_dbi: number;
  rx_threshold_dbm: number;
  rain_rate_mmh: number;
}

// ---------------------------------------------------------------------------
// FTTH Design types
// ---------------------------------------------------------------------------

export interface FtthDesignRequest {
  lat: number;
  lon: number;
  radius_km: number;
  subscribers: number;
  technology: 'GPON' | 'XGS-PON';
  split_ratio: number;
  cascade_levels: number;
  deployment_type: 'aerial' | 'underground' | 'mixed';
  l2_id?: number;
}

export interface BomLineItem {
  category: string;
  item: string;
  unit: string;
  quantity: number;
  unit_cost_brl: number;
  total_cost_brl: number;
}

export interface FtthDesignResult {
  optical_budget: OpticalBudgetResult;
  splitter_cascade: {
    levels: number;
    stages: { level: number; location: string; ratio: number; loss_db: number; unit_cost_brl: number }[];
    total_split: number;
    total_loss_db: number;
    description: string;
  };
  olt_sizing: {
    technology: string;
    subscribers: number;
    split_ratio: number;
    pon_ports: number;
    boards: number;
    ports_per_board: number;
    chassis: number;
    total_bandwidth_down_gbps: number;
    total_bandwidth_up_gbps: number;
    bandwidth_per_sub_down_mbps: number;
    bandwidth_per_sub_up_mbps: number;
    olt_cost_brl: number;
  };
  coverage: Record<string, any>;
  bom: {
    items: BomLineItem[];
    subtotals: Record<string, number>;
    total_cost_brl: number;
  };
  summary: {
    technology: string;
    subscribers: number;
    split_ratio: number;
    deployment_type: string;
    total_capex_brl: number;
    capex_per_subscriber_brl: number;
    optical_margin_db: number;
    optical_viable: boolean;
    max_reach_km: number;
    trunk_km: number;
    distribution_km: number;
    drop_km: number;
  };
}

export interface OpticalBudgetRequest {
  fiber_km: number;
  splices: number;
  connectors: number;
  splitter_ratios: number[];
  technology: 'GPON' | 'XGS-PON';
}

export interface OpticalBudgetResult {
  technology: string;
  pon_class: string;
  budget_db: number;
  wavelength: string;
  losses: {
    fiber_db: number;
    splice_db: number;
    connector_db: number;
    splitter_db: number;
  };
  total_loss_db: number;
  margin_db: number;
  viable: boolean;
  max_distance_km: number;
  total_split_ratio: number;
  fiber_km: number;
  splices: number;
  connectors: number;
  splitter_ratios: number[];
}

export interface ViabilityRequest {
  l2_id: number;
  technology: 'FTTH' | 'FWA' | 'Hibrido';
  subscribers: number;
  arpu: number;
  capex_override?: number;
}

export interface ViabilityScenario {
  label: string;
  target_pct: number;
  months_to_target: number;
  max_subscribers: number;
  payback_months: number | null;
  npv_brl: number;
  irr_pct: number | null;
  monthly_revenue_at_target_brl: number;
  monthly_opex_at_target_brl: number;
  cashflow: { month: number; subscribers: number; revenue_brl: number; opex_brl: number; net_brl: number; cumulative_brl: number }[];
}

export interface ViabilityResult {
  technology: string;
  subscribers: number;
  arpu_brl: number;
  capex: { total_brl: number; per_subscriber_brl: number };
  opex_per_subscriber_brl: number;
  scenarios: {
    optimistic: ViabilityScenario;
    realistic: ViabilityScenario;
    conservative: ViabilityScenario;
  };
  market_context: {
    total_subscribers: number;
    providers: number;
    hhi: number;
    leader_name: string | null;
    leader_share_pct: number;
    fiber_pct: number;
    growth_trend: string;
  };
  recommendation: {
    status: 'viable' | 'marginal' | 'not_viable';
    label: string;
    reason: string;
  };
  discount_rate_annual_pct: number;
}

// ---------------------------------------------------------------------------
// Network Health types
// ---------------------------------------------------------------------------

export interface WeatherRisk {
  municipality_id: number;
  municipality_name: string;
  overall_risk_score: number;
  precipitation_risk: string;
  wind_risk: string;
  temperature_risk: string;
  details: Record<string, any>;
}

export interface MaintenancePriority {
  municipality_id: number;
  municipality_name: string;
  priority_score: number;
  weather_risk_score: number;
  infrastructure_age_score: number;
  quality_trend_score: number;
  revenue_risk_score: number;
  competitive_pressure_score: number;
  recommended_action: string;
  timing: string;
  details: Record<string, any>;
}

export interface NavItem {
  label: string;
  href: string;
  icon: string;
}

// ---------------------------------------------------------------------------
// Intelligence Fusion types
// ---------------------------------------------------------------------------

export interface MunicipalityFusion {
  municipality_id: number;
  name: string;
  state: string;
  population: number | null;
  opportunity: {
    score: number;
    rank: number;
    sub_scores: {
      demand: number;
      competition: number;
      infrastructure: number;
      growth: number;
      social: number | null;
    };
    details: Record<string, any>;
  } | null;
  infrastructure: {
    backhaul: string;
    has_fiber: boolean;
    schools_offline: number;
    schools_total: number;
    health_offline: number;
    health_total: number;
    building_density_km2: number | null;
  };
  economic: {
    formal_jobs: number | null;
    telecom_jobs: number | null;
    net_hires: number | null;
    avg_salary_brl: number | null;
    government_contracts_12m: number;
    contract_value_total_brl: number;
    bndes_loans_active: number;
    bndes_total_brl: number;
  };
  regulatory: {
    has_plano_diretor: boolean;
    has_building_code: boolean;
    has_zoning_law: boolean;
    has_digital_governance: boolean;
    recent_gazette_mentions: number;
    mention_types: string[];
    regulatory_risk: string;
  };
  competition: {
    provider_count: number;
    hhi: number | null;
    leader_market_share: number | null;
    growth_trend: string | null;
    threat_level: string | null;
    avg_quality_score: number | null;
    fiber_share_pct: number | null;
  };
  safety: {
    risk_score: number | null;
    homicide_rate: number | null;
  };
  recommendation: string;
}

export interface FundingEligibility {
  municipality_id: number;
  municipality_name: string;
  state: string;
  population: number;
  programs: {
    program: string;
    description: string;
    eligible: boolean;
    reason: string;
    estimated_value_brl: number | null;
    requirements: string[];
  }[];
  total_eligible: number;
  total_estimated_brl: number;
}

export interface GazetteAlert {
  id: number;
  date: string | null;
  municipality: string;
  state: string;
  type: string;
  excerpt: string | null;
  keywords: string[];
  url: string | null;
  opportunity_score: number;
  demand_score: number | null;
  days_ago: number | null;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Satellite Intelligence
// ═══════════════════════════════════════════════════════════════════════════════

export interface SatelliteYearData {
  year: number;
  mean_ndvi: number | null;
  ndvi_std: number | null;
  mean_ndbi: number | null;
  built_up_area_km2: number | null;
  built_up_pct: number | null;
  mean_mndwi: number | null;
  water_area_km2: number | null;
  mean_bsi: number | null;
  bare_soil_area_km2: number | null;
  built_up_change_km2: number | null;
  built_up_change_pct: number | null;
  ndvi_change_pct: number | null;
  scenes_used: number | null;
}

export interface SatelliteGrowthComparison {
  municipality_code: string;
  municipality_name: string;
  satellite_growth: Array<{
    year: number;
    built_up_area_km2: number | null;
    built_up_pct: number | null;
    built_up_change_pct: number | null;
    mean_ndvi: number | null;
  }>;
  ibge_growth: Array<{
    year: number;
    population: number | null;
  }>;
  correlation_summary: {
    avg_annual_built_up_change_pct: number;
    ibge_population: number | null;
    area_km2: number | null;
  };
}

export interface SatelliteGrowthRanking {
  municipality_code: string;
  municipality_name: string;
  population: number | null;
  latitude: number | null;
  longitude: number | null;
  avg_built_up_change_pct: number | null;
  latest_built_up_area_km2: number | null;
  avg_ndvi: number | null;
}

// ---------------------------------------------------------------------------
// UK Topology types
// ---------------------------------------------------------------------------

export interface UkTopologyNode {
  building: string;
  lat: number;
  lon: number;
  dwelling_count: number;
  splitter: string;
  cable_type: string;
  distance_from_previous_m: number;
  distance_from_aux_m: number;
  roof_linked: boolean;
  optical_budget: {
    total_loss_db: number;
    rx_power_dbm: number;
    margin_db: number;
    pass: boolean;
  };
}

export interface UkTopologyBranch {
  name: string;
  nodes: UkTopologyNode[];
  total_distance_m: number;
  building_count: number;
}

export interface UkTopologyResult {
  project_id: string;
  postcode: string;
  premises: number;
  buildings: number;
  aux_joint: { lat: number; lon: number };
  branches: UkTopologyBranch[];
  bom: {
    cable_12f_m: number;
    cable_24f_m: number;
    cable_48f_m: number;
    cable_144f_m: number;
    total_cable_m: number;
    splitter_32way: number;
    splitter_64way: number;
    pbo_count: number;
    splice_closures: number;
    total_splices: number;
    cable_segments: number;
  };
  cost: {
    total_capex_gbp: number;
    capex_per_premises_gbp: number;
    annual_pia_rental_gbp: number;
  };
}

export interface UkTopologyComparison {
  buildings: Array<{
    name: string;
    generated_splitter: string;
    reference_splitter: string;
    match: boolean;
  }>;
  overall_match_pct: number;
  pbo_detection: { found: number; expected: number };
  reference_source: string;
}
