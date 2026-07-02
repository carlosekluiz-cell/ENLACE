// SPDX-License-Identifier: Apache-2.0
// Fault Ticket Generator
//
// Auto-generates structured fault tickets from all detection module results.
// Each ticket includes priority, team classification, affected ONT count,
// evidence, revenue at risk, fix cost estimate, and ROI calculation.
//
// This is the final stage of the detection pipeline: raw telemetry →
// detection modules → structured tickets ready for the NOC/OSS system.
//
// HONESTY NOTE: every monetary figure on a ticket (revenue at risk, fix
// cost, ROI) is an ESTIMATE derived from configurable assumptions (ARPU,
// per-job cost constants, assumed churn probabilities) — none of it is
// measured. Fields are named `estimated_*` and each ticket carries an
// `assumptions` list echoing the constants used, so a NOC engineer can see
// exactly what the numbers rest on.
//
// Ticket IDs are derived from a generation timestamp plus a process-wide
// monotonic sequence, so IDs are unique and stable across detection cycles
// (they previously restarted at ENLACE-0001 every cycle).
//
// Team classification:
//   Passive    — cable, splice, splitter, connector work
//   Active     — OLT, SFP, configuration changes
//   Customer   — ONT, ethernet, premises wiring
//   Management — churn, capacity planning, ghost customers
//
// SLA targets:
//   P1 = 1 day, P2 = 5 days, P3 = 14 days, P4 = 30 days

use std::sync::atomic::{AtomicU64, Ordering};

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::reflectance::ReflectanceEvent;
use super::churn::ChurnRisk;
use super::fec_health::{FecConfidence, FecFinding, FecHypothesis};
use super::ghost::GhostCustomer;
use super::capacity::{SplitterCapacity, CapacityAlert};
use super::rogue::{RogueConfidence, RoguePortFinding};
use super::weather::{WeatherCorrelation, WeatherPattern};
use crate::predictions::laser_health::{LaserHealthPrediction, LaserHealthUrgency};

/// Process-wide monotonic ticket sequence. Combined with the generation
/// timestamp this makes IDs unique across cycles and across restarts.
static TICKET_SEQ: AtomicU64 = AtomicU64::new(1);

/// Minimum fit confidence (R² of the residual daily-mean fit) before a
/// ClassicAgeing laser prediction becomes a planned-maintenance ticket.
/// Lower-confidence ageing predictions stay in the laser_health report only
/// — an honest hypothesis is not yet a dispatch (same rule the FEC module
/// applies to its trend findings).
const LASER_AGEING_TICKET_MIN_CONFIDENCE: f32 = 0.8;

/// An ActivelyFailing laser whose fast-edge EOL ETA is inside this window
/// escalates from P2 to P1: the replacement has to happen before the laser
/// dies, and a 5-day SLA would eat most of the margin.
const LASER_FAILING_P1_ETA_DAYS: u32 = 30;

/// Produce a unique ticket id: ENLACE-{unix_ts}-{seq:04}.
fn next_ticket_id(generated_ts: i64) -> String {
    let seq = TICKET_SEQ.fetch_add(1, Ordering::Relaxed);
    format!("ENLACE-{}-{:04}", generated_ts, seq)
}

/// A structured fault ticket for NOC/OSS dispatch.
///
/// `estimated_*` fields are assumption-based estimates, not measurements;
/// the `assumptions` list echoes the constants they were computed from.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FaultTicket {
    pub ticket_id: String,
    pub generated_at: DateTime<Utc>,
    pub fault_type: TicketFaultType,
    pub priority: TicketPriority,
    pub team: TeamClassification,
    pub affected_ont_count: u32,
    pub affected_ont_serials: Vec<String>,
    pub evidence: Vec<String>,
    /// Estimated annual revenue at risk (assumption-based, not measured).
    pub estimated_revenue_at_risk_annual: f64,
    /// Estimated cost to fix (assumed per-job constant).
    pub fix_cost_estimate: f64,
    /// Estimated ROI = estimated revenue / estimated fix cost.
    pub estimated_roi: f64,
    /// The assumptions behind the estimates above, in human-readable form.
    pub assumptions: Vec<String>,
    pub recommended_action: String,
    pub sla_days: u32,
}

/// Fault type for ticket classification.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum TicketFaultType {
    FibreCut,
    SpliceDegradation,
    ReflectanceSource,
    ConnectorDirty,
    WaterIngress,
    ThermalIssue,
    EthernetIssue,
    GhostCustomer,
    CapacityWarning,
    ChurnRisk,
    /// Uncorrectable FEC codewords observed — customer already erroring.
    FecErrorFloor,
    /// Rising corrected-FEC trend (pre-FEC degradation).
    PreFecDegradation,
    /// Suspected rogue ONT (multi-victim upstream-integrity event).
    RogueOnt,
    /// Laser bias rising while tx power falls — APC out of headroom, the
    /// ONT laser is already failing.
    LaserFailing,
    /// Laser bias rising at flat tx power — classic ageing precursor;
    /// planned replacement inside the (heuristic) EOL ETA window.
    LaserAgeing,
}

impl std::fmt::Display for TicketFaultType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::FibreCut => write!(f, "Fibre Cut"),
            Self::SpliceDegradation => write!(f, "Splice Degradation"),
            Self::ReflectanceSource => write!(f, "Reflectance Source"),
            Self::ConnectorDirty => write!(f, "Dirty Connector"),
            Self::WaterIngress => write!(f, "Water Ingress"),
            Self::ThermalIssue => write!(f, "Thermal Issue"),
            Self::EthernetIssue => write!(f, "Ethernet Issue"),
            Self::GhostCustomer => write!(f, "Ghost Customer"),
            Self::CapacityWarning => write!(f, "Capacity Warning"),
            Self::ChurnRisk => write!(f, "Churn Risk"),
            Self::FecErrorFloor => write!(f, "FEC Error Floor Breached"),
            Self::PreFecDegradation => write!(f, "Pre-FEC Degradation"),
            Self::RogueOnt => write!(f, "Rogue ONT (suspected)"),
            Self::LaserFailing => write!(f, "Laser Failing (APC out of headroom)"),
            Self::LaserAgeing => write!(f, "Laser Ageing (planned replacement)"),
        }
    }
}

/// Ticket priority levels.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum TicketPriority {
    P1,
    P2,
    P3,
    P4,
}

impl std::fmt::Display for TicketPriority {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::P1 => write!(f, "P1 EMERGENCY"),
            Self::P2 => write!(f, "P2 HIGH"),
            Self::P3 => write!(f, "P3 MEDIUM"),
            Self::P4 => write!(f, "P4 LOW"),
        }
    }
}

/// Team responsible for resolving the fault.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum TeamClassification {
    /// Cable, splice, splitter, connector work.
    Passive,
    /// OLT, SFP, configuration changes.
    Active,
    /// ONT, ethernet, premises wiring.
    Customer,
    /// Churn, capacity planning, ghost customers.
    Management,
}

impl std::fmt::Display for TeamClassification {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Passive => write!(f, "Passive"),
            Self::Active => write!(f, "Active"),
            Self::Customer => write!(f, "Customer"),
            Self::Management => write!(f, "Management"),
        }
    }
}

/// Aggregated detection results from all detection modules.
pub struct DetectionResults {
    pub reflectance_events: Vec<ReflectanceEvent>,
    pub churn_risks: Vec<ChurnRisk>,
    pub ghost_customers: Vec<GhostCustomer>,
    pub splitter_capacity: Vec<SplitterCapacity>,
    pub weather_correlations: Vec<WeatherCorrelation>,
    pub fec_findings: Vec<FecFinding>,
    pub rogue_findings: Vec<RoguePortFinding>,
    pub laser_predictions: Vec<LaserHealthPrediction>,
}

/// Generate fault tickets from all detection results.
///
/// Converts each detection result into a structured ticket with priority,
/// team assignment, cost estimates, and ROI calculation. Tickets are
/// sorted by priority (P1 first) then by estimated revenue at risk
/// descending.
pub fn generate_fault_tickets(results: &DetectionResults, arpu: f64) -> Vec<FaultTicket> {
    let mut tickets = Vec::new();
    let generated_ts = Utc::now().timestamp();

    // REFLECTANCE → ReflectanceSource ticket.
    // Priority scales with detection confidence: a 0.3-confidence
    // correlation is not the same emergency as a 0.9 one.
    for event in &results.reflectance_events {
        let fix_cost = 100.0; // assumed ONT replacement cost
        let revenue = event.affected_ont_count as f64 * arpu * 12.0 * 0.35;
        let roi = if fix_cost > 0.0 { revenue / fix_cost } else { 0.0 };

        let (priority, sla_days) = if event.confidence >= 0.8 {
            (TicketPriority::P1, 1)
        } else if event.confidence >= 0.5 {
            (TicketPriority::P2, 5)
        } else {
            (TicketPriority::P3, 14)
        };

        tickets.push(FaultTicket {
            ticket_id: next_ticket_id(generated_ts),
            generated_at: Utc::now(),
            fault_type: TicketFaultType::ReflectanceSource,
            priority,
            team: TeamClassification::Customer,
            affected_ont_count: event.affected_ont_count,
            affected_ont_serials: event.affected_ont_serials.clone(),
            evidence: vec![
                format!("Suspect ONT: {} at {:.0}m", event.suspect_ont_serial, event.suspect_ont_distance_m),
                format!("Tx anomaly: +{:.2} dBm above baseline", event.suspect_tx_anomaly_dbm),
                format!("Confidence: {:.0}% ({} correlated events)", event.confidence * 100.0, event.events_correlated),
                format!("Port: {}", event.port),
            ],
            estimated_revenue_at_risk_annual: revenue,
            fix_cost_estimate: fix_cost,
            estimated_roi: roi,
            assumptions: vec![
                format!("Assumed monthly ARPU: {:.2}", arpu),
                "Assumed 35% of affected subscribers churn if unresolved".to_string(),
                format!("Assumed ONT replacement cost: {:.2}", fix_cost),
            ],
            recommended_action: format!(
                "Replace ONT {} or clean connector at {:.0}m on port {}",
                event.suspect_ont_serial, event.suspect_ont_distance_m, event.port
            ),
            sla_days,
        });
    }

    // CHURN RISKS → grouped into one management ticket
    if !results.churn_risks.is_empty() {
        let serials: Vec<String> = results.churn_risks.iter().map(|r| r.ont_serial.clone()).collect();
        let total_revenue: f64 = results
            .churn_risks
            .iter()
            .map(|r| r.estimated_annual_revenue_at_risk)
            .sum();
        let fix_cost = 150.0 * serials.len() as f64; // assumed truck roll per customer
        let roi = if fix_cost > 0.0 { total_revenue / fix_cost } else { 0.0 };

        let evidence: Vec<String> = results
            .churn_risks
            .iter()
            .take(5)
            .map(|r| {
                format!(
                    "{}: Rx {:.1} dBm, slope {:.3}/day, {:.0}% est. churn prob (assumed model)",
                    r.ont_serial, r.current_rx_dbm, r.degradation_rate,
                    r.estimated_churn_probability_90day * 100.0
                )
            })
            .collect();

        let mut assumptions = vec![
            format!("Assumed monthly ARPU: {:.2}", arpu),
            format!("Assumed truck roll cost per customer: {:.2}", 150.0),
        ];
        if let Some(first) = results.churn_risks.first() {
            let a = &first.assumptions;
            assumptions.push(format!(
                "Assumed churn probabilities (90d): baseline {:.0}%, subtle {:.0}%, \
                 noticeable {:.0}%, severe {:.0}%, +{:.0}% micro-dropout bonus",
                a.baseline_probability * 100.0,
                a.subtle_probability * 100.0,
                a.noticeable_probability * 100.0,
                a.severe_probability * 100.0,
                a.micro_dropout_bonus * 100.0,
            ));
        }

        tickets.push(FaultTicket {
            ticket_id: next_ticket_id(generated_ts),
            generated_at: Utc::now(),
            fault_type: TicketFaultType::ChurnRisk,
            priority: TicketPriority::P2,
            team: TeamClassification::Management,
            affected_ont_count: serials.len() as u32,
            affected_ont_serials: serials,
            evidence,
            estimated_revenue_at_risk_annual: total_revenue,
            fix_cost_estimate: fix_cost,
            estimated_roi: roi,
            assumptions,
            recommended_action: "Proactive maintenance: schedule truck rolls to inspect and repair \
                degrading connections before customers cancel".to_string(),
            sla_days: 5,
        });
    }

    // GHOST CUSTOMERS → management ticket
    if !results.ghost_customers.is_empty() {
        let serials: Vec<String> = results.ghost_customers.iter().map(|g| g.ont_serial.clone()).collect();
        let revenue = serials.len() as f64 * arpu * 12.0;
        // Assumed mix of phone calls (0) and site visits (150)
        let fix_cost = 75.0 * serials.len() as f64;
        let roi = if fix_cost > 0.0 { revenue / fix_cost } else { 0.0 };

        let evidence: Vec<String> = results
            .ghost_customers
            .iter()
            .take(5)
            .map(|g| {
                format!(
                    "{}: {} on port {}, {:.0} days online, Rx {:.1} dBm",
                    g.ont_serial, g.eth_status, g.port, g.days_online, g.rx_power_dbm
                )
            })
            .collect();

        tickets.push(FaultTicket {
            ticket_id: next_ticket_id(generated_ts),
            generated_at: Utc::now(),
            fault_type: TicketFaultType::GhostCustomer,
            priority: TicketPriority::P3,
            team: TeamClassification::Management,
            affected_ont_count: serials.len() as u32,
            affected_ont_serials: serials,
            evidence,
            estimated_revenue_at_risk_annual: revenue,
            fix_cost_estimate: fix_cost,
            estimated_roi: roi,
            assumptions: vec![
                format!("Assumed monthly ARPU: {:.2}", arpu),
                format!("Assumed contact/site-visit cost per customer: {:.2}", 75.0),
            ],
            recommended_action: "Contact customers to verify installation. Check ethernet \
                cable and router connection. Deprovision if customer has cancelled."
                .to_string(),
            sla_days: 14,
        });
    }

    // CAPACITY → ticket for Warning and Critical alerts only
    for cap in &results.splitter_capacity {
        match cap.alert_level {
            CapacityAlert::Ok | CapacityAlert::Watch => continue,
            _ => {}
        }

        let priority = match cap.alert_level {
            CapacityAlert::Critical => TicketPriority::P2,
            _ => TicketPriority::P3,
        };
        let sla = match priority {
            TicketPriority::P2 => 5,
            _ => 14,
        };

        let fix_cost = 800.0; // assumed new splitter + install
        let potential_new_customers = cap.max_ports.saturating_sub(cap.active_onts);
        let revenue = potential_new_customers as f64 * arpu * 12.0;
        let roi = if fix_cost > 0.0 { revenue / fix_cost } else { 0.0 };

        let splitter_evidence = if cap.splitter_assumed {
            format!(
                "Splitter: {} ASSUMED from ONT count — confirm ratio; utilisation may be off 2x \
                 ({}/{} ports used)",
                cap.splitter_type, cap.active_onts, cap.max_ports
            )
        } else {
            format!(
                "Splitter: {} ({}/{} ports used)",
                cap.splitter_type, cap.active_onts, cap.max_ports
            )
        };

        let mut assumptions = vec![
            format!("Assumed monthly ARPU: {:.2}", arpu),
            format!("Assumed splitter install cost: {:.2}", 800.0),
        ];
        if cap.splitter_assumed {
            assumptions.push(
                "Splitter ratio inferred from subscriber count (no topology data) — \
                 utilisation figures are advisory until confirmed"
                    .to_string(),
            );
        }

        tickets.push(FaultTicket {
            ticket_id: next_ticket_id(generated_ts),
            generated_at: Utc::now(),
            fault_type: TicketFaultType::CapacityWarning,
            priority,
            team: TeamClassification::Passive,
            affected_ont_count: cap.active_onts,
            affected_ont_serials: Vec::new(),
            evidence: vec![
                format!("Port: {} (OLT {})", cap.port, cap.olt_id),
                splitter_evidence,
                format!("Utilisation: {:.1}%", cap.utilisation_pct),
                format!("Growth: {:.1} new connections/month", cap.new_connections_per_month),
                match cap.months_to_full {
                    Some(m) => format!("Estimated full in {:.1} months", m),
                    None => "No growth trend detected".to_string(),
                },
            ],
            estimated_revenue_at_risk_annual: revenue,
            fix_cost_estimate: fix_cost,
            estimated_roi: roi,
            assumptions,
            recommended_action: format!(
                "Install additional splitter on port {} to increase capacity from {} to {} ports",
                cap.port, cap.max_ports, cap.max_ports * 2
            ),
            sla_days: sla,
        });
    }

    // WEATHER → WaterIngress or ThermalIssue tickets
    for wc in &results.weather_correlations {
        let (fault_type, fix_cost) = match wc.pattern {
            WeatherPattern::NighttimeCondensation | WeatherPattern::PeriodicRainIngress => {
                (TicketFaultType::WaterIngress, 150.0)
            }
            WeatherPattern::ThermalExpansion => {
                (TicketFaultType::ThermalIssue, 200.0)
            }
        };

        let revenue = wc.ont_serials.len() as f64 * arpu * 12.0 * 0.15;
        let roi = if fix_cost > 0.0 { revenue / fix_cost } else { 0.0 };

        tickets.push(FaultTicket {
            ticket_id: next_ticket_id(generated_ts),
            generated_at: Utc::now(),
            fault_type,
            priority: TicketPriority::P3,
            team: TeamClassification::Passive,
            affected_ont_count: wc.ont_serials.len() as u32,
            affected_ont_serials: wc.ont_serials.clone(),
            evidence: vec![
                format!(
                    "Pattern: {} (diurnal-pattern inference — no weather data feed)",
                    wc.pattern
                ),
                format!("Port: {}", wc.port),
                format!("Distance range: {}–{}m", wc.distance_range.0, wc.distance_range.1),
                format!("Correlation strength: {:.2}", wc.correlation_strength),
                wc.description.clone(),
            ],
            estimated_revenue_at_risk_annual: revenue,
            fix_cost_estimate: fix_cost,
            estimated_roi: roi,
            assumptions: vec![
                format!("Assumed monthly ARPU: {:.2}", arpu),
                "Assumed 15% of affected subscribers churn if unresolved".to_string(),
                format!("Assumed repair cost: {:.2}", fix_cost),
            ],
            recommended_action: match wc.pattern {
                WeatherPattern::NighttimeCondensation => format!(
                    "Inspect and reseal splice enclosure at {}–{}m on port {}",
                    wc.distance_range.0, wc.distance_range.1, wc.port
                ),
                WeatherPattern::PeriodicRainIngress => format!(
                    "Check cable joints and splice enclosures for water seals at {}–{}m on port {}",
                    wc.distance_range.0, wc.distance_range.1, wc.port
                ),
                WeatherPattern::ThermalExpansion => format!(
                    "Inspect aerial cable tension and expansion loops at {}–{}m on port {}",
                    wc.distance_range.0, wc.distance_range.1, wc.port
                ),
            },
            sla_days: 14,
        });
    }

    // FEC HEALTH → per-ONT tickets.
    //   ErrorFloorBreached  => P1 Customer (customer already erroring)
    //   DispersionOrReflection HIGH => P2 Passive (plant impairment rx
    //     power cannot see — the FEC trend is the only early warning)
    //   Attenuation HIGH => P3 Passive (optical-budget loss, also visible
    //     to the optical modules; lower urgency)
    // Lower-confidence trend findings stay in the fec_health report only —
    // an honest hypothesis is not yet a dispatch.
    for finding in &results.fec_findings {
        let (fault_type, priority, team, sla_days, action) = match (&finding.hypothesis, finding.confidence) {
            (FecHypothesis::ErrorFloorBreached, _) => (
                TicketFaultType::FecErrorFloor,
                TicketPriority::P1,
                TeamClassification::Customer,
                1,
                format!(
                    "Customer {} on port {} is already experiencing errored frames \
                     (uncorrectable FEC). Dispatch: inspect ONT optics, connectors and \
                     drop fibre now — do not wait for an rx-power alarm",
                    finding.serial_number, finding.pon_port
                ),
            ),
            (FecHypothesis::DispersionOrReflection, FecConfidence::High) => (
                TicketFaultType::PreFecDegradation,
                TicketPriority::P2,
                TeamClassification::Passive,
                5,
                format!(
                    "Inspect plant serving {} on port {} for a reflective/timing \
                     impairment (connector back-reflection, dispersion): corrected-FEC \
                     is rising while rx power is stable, so power monitoring will NOT \
                     catch this before the error floor",
                    finding.serial_number, finding.pon_port
                ),
            ),
            (FecHypothesis::Attenuation, FecConfidence::High) => (
                TicketFaultType::PreFecDegradation,
                TicketPriority::P3,
                TeamClassification::Passive,
                14,
                format!(
                    "Inspect drop/distribution fibre serving {} on port {} for \
                     progressive attenuation (bend, splice creep, dirty connector): \
                     corrected-FEC rising alongside falling rx power",
                    finding.serial_number, finding.pon_port
                ),
            ),
            _ => continue,
        };

        let fix_cost = 150.0; // assumed truck roll
        let revenue = arpu * 12.0 * 0.35;
        let roi = if fix_cost > 0.0 { revenue / fix_cost } else { 0.0 };

        let mut evidence = vec![finding.summary.clone()];
        evidence.push(format!(
            "Corrected-FEC rate: {:.0}/hour ({} normalization)",
            finding.corrected_rate_per_hour, finding.normalization
        ));
        if finding.uncorrected_total > 0 {
            evidence.push(format!(
                "Uncorrectable codewords in window: {}",
                finding.uncorrected_total
            ));
        }
        match finding.rx_trend_dbm_per_day {
            Some(t) => evidence.push(format!("Rx trend: {:+.3} dBm/day", t)),
            None => evidence.push("Rx trend: unavailable (insufficient rx samples)".to_string()),
        }
        evidence.push(format!("Confidence: {:?}", finding.confidence));

        tickets.push(FaultTicket {
            ticket_id: next_ticket_id(generated_ts),
            generated_at: Utc::now(),
            fault_type,
            priority,
            team,
            affected_ont_count: 1,
            affected_ont_serials: vec![finding.serial_number.clone()],
            evidence,
            estimated_revenue_at_risk_annual: revenue,
            fix_cost_estimate: fix_cost,
            estimated_roi: roi,
            assumptions: vec![
                format!("Assumed monthly ARPU: {:.2}", arpu),
                "Assumed 35% churn probability if unresolved".to_string(),
                format!("Assumed truck roll cost: {:.2}", fix_cost),
            ],
            recommended_action: action,
            sla_days,
        });
    }

    // ROGUE ONT → P2 ticket for HIGH-confidence findings only. The finding
    // is a hypothesis; the ticket action is the vendor-native confirmation
    // step, never "replace the candidate".
    for finding in &results.rogue_findings {
        if finding.confidence != RogueConfidence::High {
            continue;
        }

        let fix_cost = 200.0; // assumed maintenance-window diagnostic session
        let revenue = finding.victim_count as f64 * arpu * 12.0 * 0.35;
        let roi = if fix_cost > 0.0 { revenue / fix_cost } else { 0.0 };

        let mut evidence = finding.evidence.clone();
        for c in finding.candidates.iter().take(2) {
            for e in &c.evidence {
                evidence.push(format!("Candidate: {}", e));
            }
        }

        tickets.push(FaultTicket {
            ticket_id: next_ticket_id(generated_ts),
            generated_at: Utc::now(),
            fault_type: TicketFaultType::RogueOnt,
            priority: TicketPriority::P2,
            team: TeamClassification::Active,
            affected_ont_count: finding.victim_count,
            affected_ont_serials: finding
                .candidates
                .iter()
                .map(|c| c.serial_number.clone())
                .collect(),
            evidence,
            estimated_revenue_at_risk_annual: revenue,
            fix_cost_estimate: fix_cost,
            estimated_roi: roi,
            assumptions: vec![
                format!("Assumed monthly ARPU: {:.2}", arpu),
                "Assumed 35% of victim subscribers churn if unresolved".to_string(),
                format!("Assumed diagnostic session cost: {:.2}", fix_cost),
                "Candidate ranking is a passive hypothesis — vendor-native \
                 confirmation required before any hardware action"
                    .to_string(),
            ],
            recommended_action: finding.recommended_action.clone(),
            sla_days: 5,
        });
    }

    // LASER HEALTH → per-ONT tickets.
    //   ActivelyFailing => P2 Customer (P1 when the fast-edge EOL ETA is
    //     ≤ LASER_FAILING_P1_ETA_DAYS): bias rising AND tx power falling —
    //     the APC loop is out of headroom, the laser is already failing.
    //   ClassicAgeing with confidence >= 0.8 => P3 Customer planned
    //     maintenance, with the (heuristic) EOL ETA range in the evidence.
    //   ClassicAgeing below the confidence bar and BiasRiseOnly (tx trend
    //     unavailable — ageing vs failing cannot be distinguished) stay in
    //     the laser_health report only.
    for pred in &results.laser_predictions {
        let (fault_type, priority, sla_days, action) = match pred.urgency {
            LaserHealthUrgency::ActivelyFailing => {
                let (priority, sla_days) =
                    if pred.eta_days_to_eol_earliest <= LASER_FAILING_P1_ETA_DAYS {
                        (TicketPriority::P1, 1)
                    } else {
                        (TicketPriority::P2, 5)
                    };
                (
                    TicketFaultType::LaserFailing,
                    priority,
                    sla_days,
                    format!(
                        "Replace ONT {} on port {} urgently: bias current is rising \
                         while tx power falls — the APC loop is out of headroom and \
                         the laser is already failing. Do not wait for an rx-power \
                         alarm at the OLT",
                        pred.serial_number, pred.pon_port
                    ),
                )
            }
            LaserHealthUrgency::ClassicAgeing
                if pred.confidence >= LASER_AGEING_TICKET_MIN_CONFIDENCE =>
            {
                (
                    TicketFaultType::LaserAgeing,
                    TicketPriority::P3,
                    14,
                    format!(
                        "Schedule planned ONT replacement for {} on port {} inside \
                         the EOL ETA window ({}): bias current rising at flat tx \
                         power is the classic laser end-of-life precursor (APC \
                         compensating for threshold drift)",
                        pred.serial_number,
                        pred.pon_port,
                        eol_eta_text(pred)
                    ),
                )
            }
            _ => continue,
        };

        let fix_cost = 100.0; // assumed ONT replacement cost
        let revenue = arpu * 12.0 * 0.35;
        let roi = if fix_cost > 0.0 { revenue / fix_cost } else { 0.0 };

        let detrend_evidence = if pred.temperature_detrended {
            "Temperature detrending: bias~temperature residuals (thermal swings removed)"
                .to_string()
        } else {
            "Temperature detrending: 24h-mean fallback only (no temperature data — \
             multi-day weather swings NOT removed; weigh accordingly)"
                .to_string()
        };
        let tx_evidence = match pred.tx_power_stable {
            Some(true) => "Tx power: flat — APC still holding output constant".to_string(),
            Some(false) => "Tx power: falling — APC out of headroom".to_string(),
            None => "Tx power: trend unavailable (insufficient tx samples)".to_string(),
        };

        tickets.push(FaultTicket {
            ticket_id: next_ticket_id(generated_ts),
            generated_at: Utc::now(),
            fault_type,
            priority,
            team: TeamClassification::Customer,
            affected_ont_count: 1,
            affected_ont_serials: vec![pred.serial_number.clone()],
            evidence: vec![
                format!(
                    "Bias drift: +{:.2}%/month of median bias {:.1} mA (95% CI \
                     {:.2}–{:.2}%/month, R²={:.2})",
                    pred.drift_pct_per_month,
                    pred.median_bias_ma,
                    pred.drift_ci95_pct_per_month.0,
                    pred.drift_ci95_pct_per_month.1,
                    pred.confidence,
                ),
                detrend_evidence,
                tx_evidence,
                format!(
                    "EOL ETA (heuristic: bias at +50% over window-median baseline): {}",
                    eol_eta_text(pred)
                ),
            ],
            estimated_revenue_at_risk_annual: revenue,
            fix_cost_estimate: fix_cost,
            estimated_roi: roi,
            assumptions: vec![
                format!("Assumed monthly ARPU: {:.2}", arpu),
                "Assumed 35% churn probability if unresolved".to_string(),
                format!("Assumed ONT replacement cost: {:.2}", fix_cost),
                "EOL threshold (+50% bias over baseline) is a GR-468-style \
                 HEURISTIC, not a vendor spec — the ETA is a 95%-confidence \
                 range, never a point promise"
                    .to_string(),
            ],
            recommended_action: action,
            sla_days,
        });
    }

    // Sort by priority (P1 first) then by estimated revenue at risk descending
    tickets.sort_by(|a, b| {
        let pa = priority_rank(&a.priority);
        let pb = priority_rank(&b.priority);
        pa.cmp(&pb).then_with(|| {
            b.estimated_revenue_at_risk_annual
                .partial_cmp(&a.estimated_revenue_at_risk_annual)
                .unwrap_or(std::cmp::Ordering::Equal)
        })
    });

    tickets
}

/// The EOL ETA range as human text: "120–300 days (95% confidence)" or
/// "120+ days (slow edge of confidence band is flat)".
fn eol_eta_text(pred: &LaserHealthPrediction) -> String {
    match pred.eta_days_to_eol_latest {
        Some(late) => format!(
            "{}–{} days (95% confidence)",
            pred.eta_days_to_eol_earliest, late
        ),
        None => format!(
            "{}+ days (slow edge of confidence band is flat)",
            pred.eta_days_to_eol_earliest
        ),
    }
}

/// Map priority to a numeric rank for sorting (lower = higher priority).
fn priority_rank(p: &TicketPriority) -> u8 {
    match p {
        TicketPriority::P1 => 1,
        TicketPriority::P2 => 2,
        TicketPriority::P3 => 3,
        TicketPriority::P4 => 4,
    }
}

/// Format a fault ticket as human-readable text.
pub fn format_ticket_text(ticket: &FaultTicket) -> String {
    let priority_label = match ticket.priority {
        TicketPriority::P1 => "P1 EMERGENCY",
        TicketPriority::P2 => "P2 HIGH",
        TicketPriority::P3 => "P3 MEDIUM",
        TicketPriority::P4 => "P4 LOW",
    };

    let mut lines = Vec::new();
    lines.push(format!(
        "FAULT TICKET #{} -- Auto-generated",
        ticket.ticket_id
    ));
    lines.push(format!("Priority: {}", priority_label));
    lines.push(format!("Type: {}", ticket.fault_type));
    lines.push(format!("Team: {}", ticket.team));
    lines.push(format!("Affected: {} ONTs", ticket.affected_ont_count));

    lines.push("Evidence:".to_string());
    for e in &ticket.evidence {
        lines.push(format!("  - {}", e));
    }

    lines.push(format!(
        "Est. Revenue at Risk (assumption-based): £{:.0}/year",
        ticket.estimated_revenue_at_risk_annual
    ));
    lines.push(format!("Est. Fix Cost: £{:.0}", ticket.fix_cost_estimate));
    lines.push(format!("Est. ROI: {:.1}x", ticket.estimated_roi));
    if !ticket.assumptions.is_empty() {
        lines.push("Assumptions (estimates, not measurements):".to_string());
        for a in &ticket.assumptions {
            lines.push(format!("  - {}", a));
        }
    }
    lines.push(format!("Action: {}", ticket.recommended_action));
    lines.push(format!("SLA: {} days", ticket.sla_days));

    lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::detection::churn::ChurnImpact;
    use crate::detection::ghost::GhostEthStatus;

    fn empty_results() -> DetectionResults {
        DetectionResults {
            reflectance_events: Vec::new(),
            churn_risks: Vec::new(),
            ghost_customers: Vec::new(),
            splitter_capacity: Vec::new(),
            weather_correlations: Vec::new(),
            fec_findings: Vec::new(),
            rogue_findings: Vec::new(),
            laser_predictions: Vec::new(),
        }
    }

    fn make_laser_prediction(
        urgency: LaserHealthUrgency,
        confidence: f32,
        eta_earliest: u32,
    ) -> LaserHealthPrediction {
        LaserHealthPrediction {
            serial_number: "LSR-001".to_string(),
            pon_port: "OLT01/0/1/0".to_string(),
            median_bias_ma: 20.0,
            drift_pct_per_month: 3.2,
            drift_ci95_pct_per_month: (2.4, 4.0),
            temperature_detrended: true,
            tx_power_stable: match urgency {
                LaserHealthUrgency::ActivelyFailing => Some(false),
                LaserHealthUrgency::ClassicAgeing => Some(true),
                LaserHealthUrgency::BiasRiseOnly => None,
            },
            urgency,
            eta_days_to_eol_earliest: eta_earliest,
            eta_days_to_eol_latest: Some(eta_earliest * 3),
            confidence,
            message: "test laser message".to_string(),
        }
    }

    fn make_reflectance_event(confidence: f64) -> ReflectanceEvent {
        ReflectanceEvent {
            timestamp: Utc::now(),
            port: "0/1/0".to_string(),
            affected_ont_count: 7,
            affected_ont_serials: (0..7).map(|i| format!("ONT{:03}", i)).collect(),
            suspect_ont_serial: "ONT099".to_string(),
            suspect_ont_distance_m: 500.0,
            suspect_tx_anomaly_dbm: 0.8,
            confidence,
            events_correlated: 3,
        }
    }

    #[test]
    fn test_ticket_from_reflectance() {
        let mut results = empty_results();
        results.reflectance_events.push(make_reflectance_event(0.9));

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1);
        assert_eq!(tickets[0].fault_type, TicketFaultType::ReflectanceSource);
        assert_eq!(tickets[0].priority, TicketPriority::P1);
        assert_eq!(tickets[0].team, TeamClassification::Customer);
        assert_eq!(tickets[0].affected_ont_count, 7);
        assert_eq!(tickets[0].sla_days, 1);
        assert!(tickets[0].estimated_revenue_at_risk_annual > 0.0);
        assert!(tickets[0].estimated_roi > 0.0);
        assert!(!tickets[0].assumptions.is_empty(), "ticket must echo its assumptions");
    }

    #[test]
    fn test_ticket_reflectance_priority_scales_with_confidence() {
        // 0.3 confidence is not a P1 emergency.
        let mut results = empty_results();
        results.reflectance_events.push(make_reflectance_event(0.3));
        results.reflectance_events.push(make_reflectance_event(0.6));
        results.reflectance_events.push(make_reflectance_event(0.9));

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 3);
        let priorities: Vec<&TicketPriority> = tickets.iter().map(|t| &t.priority).collect();
        assert!(priorities.contains(&&TicketPriority::P1), "0.9 confidence -> P1");
        assert!(priorities.contains(&&TicketPriority::P2), "0.6 confidence -> P2");
        assert!(priorities.contains(&&TicketPriority::P3), "0.3 confidence -> P3");
    }

    #[test]
    fn test_ticket_ids_unique_across_cycles() {
        // IDs must not restart at ENLACE-0001 every detection cycle.
        let mut results = empty_results();
        results.reflectance_events.push(make_reflectance_event(0.9));
        results.reflectance_events.push(make_reflectance_event(0.9));

        let cycle1 = generate_fault_tickets(&results, 89.90);
        let cycle2 = generate_fault_tickets(&results, 89.90);

        let mut all_ids: Vec<&String> = cycle1
            .iter()
            .chain(cycle2.iter())
            .map(|t| &t.ticket_id)
            .collect();
        let total = all_ids.len();
        all_ids.sort();
        all_ids.dedup();
        assert_eq!(
            all_ids.len(),
            total,
            "ticket IDs must be unique across cycles: {:?}",
            all_ids
        );
        for id in &all_ids {
            assert!(id.starts_with("ENLACE-"), "id format: {}", id);
        }
    }

    fn default_churn_assumptions() -> crate::detection::churn::ChurnAssumptions {
        crate::detection::churn::ChurnAssumptions::with_arpu(89.90)
    }

    #[test]
    fn test_ticket_from_churn_group() {
        let mut results = empty_results();
        for i in 0..5 {
            results.churn_risks.push(ChurnRisk {
                ont_serial: format!("CHURN{:03}", i),
                current_rx_dbm: -23.0,
                degradation_rate: -0.04,
                days_degrading: 30,
                micro_dropout_count: 3,
                impact: ChurnImpact::Noticeable,
                estimated_churn_probability_90day: 0.15,
                estimated_annual_revenue_at_risk: 89.90 * 0.15 * 12.0,
                assumptions: default_churn_assumptions(),
            });
        }

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1);
        assert_eq!(tickets[0].fault_type, TicketFaultType::ChurnRisk);
        assert_eq!(tickets[0].priority, TicketPriority::P2);
        assert_eq!(tickets[0].team, TeamClassification::Management);
        assert_eq!(tickets[0].affected_ont_count, 5);
        assert_eq!(tickets[0].sla_days, 5);
        assert!(
            tickets[0].assumptions.iter().any(|a| a.contains("churn probabilities")),
            "churn ticket must echo the assumed probability model: {:?}",
            tickets[0].assumptions
        );
    }

    #[test]
    fn test_ticket_from_ghost_customers() {
        let mut results = empty_results();
        for i in 0..3 {
            results.ghost_customers.push(GhostCustomer {
                ont_serial: format!("GHOST{:03}", i),
                port: "0/1/0".to_string(),
                distance_m: Some(500),
                rx_power_dbm: -20.0,
                eth_status: GhostEthStatus::NoLink,
                days_online: 45.0,
                estimated_monthly_revenue: 89.90,
            });
        }

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1);
        assert_eq!(tickets[0].fault_type, TicketFaultType::GhostCustomer);
        assert_eq!(tickets[0].priority, TicketPriority::P3);
        assert_eq!(tickets[0].team, TeamClassification::Management);
        assert_eq!(tickets[0].affected_ont_count, 3);
        assert_eq!(tickets[0].sla_days, 14);
        // Revenue = 3 * 89.90 * 12
        let expected_rev = 3.0 * 89.90 * 12.0;
        assert!(
            (tickets[0].estimated_revenue_at_risk_annual - expected_rev).abs() < 0.01,
            "Expected revenue {}, got {}",
            expected_rev,
            tickets[0].estimated_revenue_at_risk_annual
        );
    }

    #[test]
    fn test_ticket_from_capacity_warning() {
        let mut results = empty_results();
        results.splitter_capacity.push(SplitterCapacity {
            port: "0/2/0".to_string(),
            olt_id: "0".to_string(),
            splitter_type: "1:32".to_string(),
            max_ports: 32,
            active_onts: 30,
            utilisation_pct: 93.75,
            new_connections_per_month: 2.0,
            months_to_full: Some(1.0),
            alert_level: CapacityAlert::Critical,
            splitter_assumed: true,
        });

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1);
        assert_eq!(tickets[0].fault_type, TicketFaultType::CapacityWarning);
        assert_eq!(tickets[0].priority, TicketPriority::P2);
        assert_eq!(tickets[0].team, TeamClassification::Passive);
        assert_eq!(tickets[0].sla_days, 5);
        assert!((tickets[0].fix_cost_estimate - 800.0).abs() < 0.01);
        assert!(
            tickets[0].evidence.iter().any(|e| e.contains("ASSUMED")),
            "assumed splitter ratio must be visible in the evidence: {:?}",
            tickets[0].evidence
        );
    }

    #[test]
    fn test_ticket_from_weather_event() {
        let mut results = empty_results();
        results.weather_correlations.push(WeatherCorrelation {
            ont_serials: vec!["W001".into(), "W002".into(), "W003".into(), "W004".into()],
            port: "0/3/0".to_string(),
            distance_range: (800, 850),
            pattern: WeatherPattern::PeriodicRainIngress,
            correlation_strength: 0.7,
            description: "Rain ingress detected".to_string(),
        });

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1);
        assert_eq!(tickets[0].fault_type, TicketFaultType::WaterIngress);
        assert_eq!(tickets[0].priority, TicketPriority::P3);
        assert_eq!(tickets[0].team, TeamClassification::Passive);
        assert_eq!(tickets[0].affected_ont_count, 4);
        assert_eq!(tickets[0].sla_days, 14);
        assert!((tickets[0].fix_cost_estimate - 150.0).abs() < 0.01);
    }

    fn make_fec_finding(
        hypothesis: crate::detection::fec_health::FecHypothesis,
        confidence: crate::detection::fec_health::FecConfidence,
        uncorrected: u64,
    ) -> crate::detection::fec_health::FecFinding {
        crate::detection::fec_health::FecFinding {
            serial_number: "FEC-001".to_string(),
            pon_port: "OLT01/0/1/0".to_string(),
            window_start: Utc::now() - chrono::Duration::days(7),
            window_end: Utc::now(),
            corrected_rate_per_hour: 2500.0,
            corrected_per_gbyte: None,
            normalization: "time".to_string(),
            uncorrected_total: uncorrected,
            rx_trend_dbm_per_day: Some(0.001),
            hypothesis,
            confidence,
            summary: "test summary".to_string(),
        }
    }

    #[test]
    fn test_ticket_error_floor_breached_is_p1_customer() {
        let mut results = empty_results();
        results.fec_findings.push(make_fec_finding(
            crate::detection::fec_health::FecHypothesis::ErrorFloorBreached,
            crate::detection::fec_health::FecConfidence::Medium,
            42,
        ));

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1);
        assert_eq!(tickets[0].fault_type, TicketFaultType::FecErrorFloor);
        assert_eq!(tickets[0].priority, TicketPriority::P1, "customer already erroring => P1");
        assert_eq!(tickets[0].team, TeamClassification::Customer);
        assert_eq!(tickets[0].sla_days, 1);
        assert_eq!(tickets[0].affected_ont_serials, vec!["FEC-001".to_string()]);
        assert!(tickets[0].evidence.iter().any(|e| e.contains("Uncorrectable")));
    }

    #[test]
    fn test_ticket_dispersion_high_is_p2_passive_low_conf_suppressed() {
        let mut results = empty_results();
        results.fec_findings.push(make_fec_finding(
            crate::detection::fec_health::FecHypothesis::DispersionOrReflection,
            crate::detection::fec_health::FecConfidence::High,
            0,
        ));
        results.fec_findings.push(make_fec_finding(
            crate::detection::fec_health::FecHypothesis::DispersionOrReflection,
            crate::detection::fec_health::FecConfidence::Low,
            0,
        ));

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1, "only HIGH-confidence dispersion becomes a ticket");
        assert_eq!(tickets[0].fault_type, TicketFaultType::PreFecDegradation);
        assert_eq!(tickets[0].priority, TicketPriority::P2);
        assert_eq!(tickets[0].team, TeamClassification::Passive);
        assert!(tickets[0].recommended_action.contains("rx power is stable"));
    }

    fn make_rogue_finding(
        confidence: crate::detection::rogue::RogueConfidence,
    ) -> crate::detection::rogue::RoguePortFinding {
        crate::detection::rogue::RoguePortFinding {
            olt: "OLT01".to_string(),
            pon_port: "OLT01/0/1/0".to_string(),
            victim_count: 4,
            window_start: Utc::now() - chrono::Duration::days(3),
            window_end: Utc::now(),
            evidence: vec!["4 ONTs suffering".to_string()],
            candidates: vec![crate::detection::rogue::RogueCandidate {
                serial_number: "ROGUE-1".to_string(),
                score: 4.0,
                evidence: vec!["tx anomaly".to_string(), "bias anomaly".to_string()],
            }],
            confidence,
            recommended_action:
                "confirm via OLT rogue-ONU detection / port-level bisection during a \
                 maintenance window"
                    .to_string(),
        }
    }

    #[test]
    fn test_ticket_rogue_high_is_p2_with_confirmation_action() {
        let mut results = empty_results();
        results.rogue_findings.push(make_rogue_finding(
            crate::detection::rogue::RogueConfidence::High,
        ));
        results.rogue_findings.push(make_rogue_finding(
            crate::detection::rogue::RogueConfidence::Medium,
        ));

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1, "only HIGH-confidence rogue findings become tickets");
        assert_eq!(tickets[0].fault_type, TicketFaultType::RogueOnt);
        assert_eq!(tickets[0].priority, TicketPriority::P2);
        assert_eq!(tickets[0].team, TeamClassification::Active);
        assert_eq!(tickets[0].affected_ont_count, 4);
        assert!(
            tickets[0].recommended_action.contains("rogue-ONU detection"),
            "ticket must carry the vendor-native confirmation step"
        );
        assert!(
            tickets[0].assumptions.iter().any(|a| a.contains("hypothesis")),
            "rogue ticket must state the candidate ranking is a hypothesis"
        );
        assert!(tickets[0].evidence.iter().any(|e| e.contains("Candidate:")));
    }

    #[test]
    fn test_ticket_laser_actively_failing_is_urgent_customer() {
        let mut results = empty_results();
        results.laser_predictions.push(make_laser_prediction(
            LaserHealthUrgency::ActivelyFailing,
            0.7, // ActivelyFailing tickets regardless of the ageing bar
            200,
        ));

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1);
        assert_eq!(tickets[0].fault_type, TicketFaultType::LaserFailing);
        assert_eq!(tickets[0].priority, TicketPriority::P2, "distant ETA => P2 urgent");
        assert_eq!(tickets[0].team, TeamClassification::Customer);
        assert_eq!(tickets[0].sla_days, 5);
        assert_eq!(tickets[0].affected_ont_serials, vec!["LSR-001".to_string()]);
        assert!(
            tickets[0].recommended_action.contains("out of headroom"),
            "action must explain the failing signature: {}",
            tickets[0].recommended_action
        );
        assert!(
            tickets[0].assumptions.iter().any(|a| a.contains("HEURISTIC")),
            "EOL threshold must be labelled a heuristic: {:?}",
            tickets[0].assumptions
        );
    }

    #[test]
    fn test_ticket_laser_failing_escalates_to_p1_on_short_eta() {
        let mut results = empty_results();
        results.laser_predictions.push(make_laser_prediction(
            LaserHealthUrgency::ActivelyFailing,
            0.9,
            21, // fast edge inside the 30-day escalation window
        ));

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1);
        assert_eq!(tickets[0].priority, TicketPriority::P1);
        assert_eq!(tickets[0].sla_days, 1);
    }

    #[test]
    fn test_ticket_laser_classic_ageing_high_conf_is_p3_with_eta_range() {
        let mut results = empty_results();
        results.laser_predictions.push(make_laser_prediction(
            LaserHealthUrgency::ClassicAgeing,
            0.92,
            150,
        ));

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1);
        assert_eq!(tickets[0].fault_type, TicketFaultType::LaserAgeing);
        assert_eq!(tickets[0].priority, TicketPriority::P3, "planned maintenance => P3");
        assert_eq!(tickets[0].team, TeamClassification::Customer);
        assert_eq!(tickets[0].sla_days, 14);
        assert!(
            tickets[0].evidence.iter().any(|e| e.contains("150–450 days")),
            "ETA range must be in the evidence: {:?}",
            tickets[0].evidence
        );
        assert!(
            tickets[0].evidence.iter().any(|e| e.contains("heuristic")),
            "EOL evidence must be labelled heuristic: {:?}",
            tickets[0].evidence
        );
    }

    #[test]
    fn test_ticket_laser_low_conf_ageing_and_bias_rise_only_suppressed() {
        let mut results = empty_results();
        // ClassicAgeing below the 0.8 confidence bar: report-only.
        results.laser_predictions.push(make_laser_prediction(
            LaserHealthUrgency::ClassicAgeing,
            0.65,
            150,
        ));
        // BiasRiseOnly (ageing vs failing indistinguishable): report-only.
        results.laser_predictions.push(make_laser_prediction(
            LaserHealthUrgency::BiasRiseOnly,
            0.95,
            150,
        ));

        let tickets = generate_fault_tickets(&results, 89.90);
        assert!(
            tickets.is_empty(),
            "low-confidence ageing / unclassified bias rise must not dispatch: {:?}",
            tickets.iter().map(|t| &t.fault_type).collect::<Vec<_>>()
        );
    }

    #[test]
    fn test_ticket_format_text() {
        let ticket = FaultTicket {
            ticket_id: "ENLACE-1770000000-0001".to_string(),
            generated_at: Utc::now(),
            fault_type: TicketFaultType::ReflectanceSource,
            priority: TicketPriority::P1,
            team: TeamClassification::Customer,
            affected_ont_count: 7,
            affected_ont_serials: vec!["ONT001".into(), "ONT002".into()],
            evidence: vec![
                "Suspect ONT: ONT099 at 500m".to_string(),
                "Tx anomaly: +0.80 dBm".to_string(),
            ],
            estimated_revenue_at_risk_annual: 2700.0,
            fix_cost_estimate: 100.0,
            estimated_roi: 27.0,
            assumptions: vec!["Assumed monthly ARPU: 89.90".to_string()],
            recommended_action: "Replace ONT099".to_string(),
            sla_days: 1,
        };

        let text = format_ticket_text(&ticket);
        assert!(text.contains("FAULT TICKET #ENLACE-1770000000-0001"));
        assert!(text.contains("P1 EMERGENCY"));
        assert!(text.contains("Reflectance Source"));
        assert!(text.contains("Customer"));
        assert!(text.contains("7 ONTs"));
        assert!(text.contains("Suspect ONT: ONT099"));
        assert!(text.contains("2700/year"));
        assert!(text.contains("Est. Revenue at Risk (assumption-based)"));
        assert!(text.contains("100"));
        assert!(text.contains("27.0x"));
        assert!(text.contains("Assumed monthly ARPU"));
        assert!(text.contains("Replace ONT099"));
        assert!(text.contains("1 days"));
    }
}
