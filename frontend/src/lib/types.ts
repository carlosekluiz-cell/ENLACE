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
