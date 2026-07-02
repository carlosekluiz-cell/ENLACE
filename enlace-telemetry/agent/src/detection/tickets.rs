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
// Team classification:
//   Passive    — cable, splice, splitter, connector work
//   Active     — OLT, SFP, configuration changes
//   Customer   — ONT, ethernet, premises wiring
//   Management — churn, capacity planning, ghost customers
//
// SLA targets:
//   P1 = 1 day, P2 = 5 days, P3 = 14 days, P4 = 30 days

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::reflectance::ReflectanceEvent;
use super::churn::ChurnRisk;
use super::ghost::GhostCustomer;
use super::capacity::{SplitterCapacity, CapacityAlert};
use super::weather::{WeatherCorrelation, WeatherPattern};

/// A structured fault ticket for NOC/OSS dispatch.
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
    pub revenue_at_risk_annual: f64,
    pub fix_cost_estimate: f64,
    pub roi: f64,
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
}

/// Generate fault tickets from all detection results.
///
/// Converts each detection result into a structured ticket with priority,
/// team assignment, cost estimates, and ROI calculation. Tickets are
/// sorted by priority (P1 first) then by revenue at risk descending.
pub fn generate_fault_tickets(results: &DetectionResults, arpu: f64) -> Vec<FaultTicket> {
    let mut tickets = Vec::new();
    let mut ticket_num: u32 = 1;

    // REFLECTANCE → ReflectanceSource ticket
    for event in &results.reflectance_events {
        let fix_cost = 100.0; // ONT replacement
        let revenue = event.affected_ont_count as f64 * arpu * 12.0 * 0.35;
        let roi = if fix_cost > 0.0 { revenue / fix_cost } else { 0.0 };

        tickets.push(FaultTicket {
            ticket_id: format!("ENLACE-{:04}", ticket_num),
            generated_at: Utc::now(),
            fault_type: TicketFaultType::ReflectanceSource,
            priority: TicketPriority::P1,
            team: TeamClassification::Customer,
            affected_ont_count: event.affected_ont_count,
            affected_ont_serials: event.affected_ont_serials.clone(),
            evidence: vec![
                format!("Suspect ONT: {} at {:.0}m", event.suspect_ont_serial, event.suspect_ont_distance_m),
                format!("Tx anomaly: +{:.2} dBm above baseline", event.suspect_tx_anomaly_dbm),
                format!("Confidence: {:.0}% ({} correlated events)", event.confidence * 100.0, event.events_correlated),
                format!("Port: {}", event.port),
            ],
            revenue_at_risk_annual: revenue,
            fix_cost_estimate: fix_cost,
            roi,
            recommended_action: format!(
                "Replace ONT {} or clean connector at {:.0}m on port {}",
                event.suspect_ont_serial, event.suspect_ont_distance_m, event.port
            ),
            sla_days: 1,
        });
        ticket_num += 1;
    }

    // CHURN RISKS → grouped into one management ticket
    if !results.churn_risks.is_empty() {
        let serials: Vec<String> = results.churn_risks.iter().map(|r| r.ont_serial.clone()).collect();
        let total_revenue: f64 = results.churn_risks.iter().map(|r| r.monthly_revenue_at_risk).sum();
        let fix_cost = 150.0 * serials.len() as f64; // truck roll per customer
        let roi = if fix_cost > 0.0 { total_revenue / fix_cost } else { 0.0 };

        let evidence: Vec<String> = results
            .churn_risks
            .iter()
            .take(5)
            .map(|r| {
                format!(
                    "{}: Rx {:.1} dBm, slope {:.3}/day, {:.0}% churn prob",
                    r.ont_serial, r.current_rx_dbm, r.degradation_rate,
                    r.churn_probability_90day * 100.0
                )
            })
            .collect();

        tickets.push(FaultTicket {
            ticket_id: format!("ENLACE-{:04}", ticket_num),
            generated_at: Utc::now(),
            fault_type: TicketFaultType::ChurnRisk,
            priority: TicketPriority::P2,
            team: TeamClassification::Management,
            affected_ont_count: serials.len() as u32,
            affected_ont_serials: serials,
            evidence,
            revenue_at_risk_annual: total_revenue,
            fix_cost_estimate: fix_cost,
            roi,
            recommended_action: "Proactive maintenance: schedule truck rolls to inspect and repair \
                degrading connections before customers cancel".to_string(),
            sla_days: 5,
        });
        ticket_num += 1;
    }

    // GHOST CUSTOMERS → management ticket
    if !results.ghost_customers.is_empty() {
        let serials: Vec<String> = results.ghost_customers.iter().map(|g| g.ont_serial.clone()).collect();
        let revenue = serials.len() as f64 * arpu * 12.0;
        // Mix of phone calls (£0) and site visits (£150)
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
            ticket_id: format!("ENLACE-{:04}", ticket_num),
            generated_at: Utc::now(),
            fault_type: TicketFaultType::GhostCustomer,
            priority: TicketPriority::P3,
            team: TeamClassification::Management,
            affected_ont_count: serials.len() as u32,
            affected_ont_serials: serials,
            evidence,
            revenue_at_risk_annual: revenue,
            fix_cost_estimate: fix_cost,
            roi,
            recommended_action: "Contact customers to verify installation. Check ethernet \
                cable and router connection. Deprovision if customer has cancelled."
                .to_string(),
            sla_days: 14,
        });
        ticket_num += 1;
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

        let fix_cost = 800.0; // new splitter + install
        let potential_new_customers = cap.max_ports - cap.active_onts;
        let revenue = potential_new_customers as f64 * arpu * 12.0;
        let roi = if fix_cost > 0.0 { revenue / fix_cost } else { 0.0 };

        tickets.push(FaultTicket {
            ticket_id: format!("ENLACE-{:04}", ticket_num),
            generated_at: Utc::now(),
            fault_type: TicketFaultType::CapacityWarning,
            priority,
            team: TeamClassification::Passive,
            affected_ont_count: cap.active_onts,
            affected_ont_serials: Vec::new(),
            evidence: vec![
                format!("Port: {} (OLT {})", cap.port, cap.olt_id),
                format!("Splitter: {} ({}/{} ports used)", cap.splitter_type, cap.active_onts, cap.max_ports),
                format!("Utilisation: {:.1}%", cap.utilisation_pct),
                format!("Growth: {:.1} new connections/month", cap.new_connections_per_month),
                match cap.months_to_full {
                    Some(m) => format!("Estimated full in {:.1} months", m),
                    None => "No growth trend detected".to_string(),
                },
            ],
            revenue_at_risk_annual: revenue,
            fix_cost_estimate: fix_cost,
            roi,
            recommended_action: format!(
                "Install additional splitter on port {} to increase capacity from {} to {} ports",
                cap.port, cap.max_ports, cap.max_ports * 2
            ),
            sla_days: sla,
        });
        ticket_num += 1;
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
            ticket_id: format!("ENLACE-{:04}", ticket_num),
            generated_at: Utc::now(),
            fault_type,
            priority: TicketPriority::P3,
            team: TeamClassification::Passive,
            affected_ont_count: wc.ont_serials.len() as u32,
            affected_ont_serials: wc.ont_serials.clone(),
            evidence: vec![
                format!("Pattern: {}", wc.pattern),
                format!("Port: {}", wc.port),
                format!("Distance range: {}–{}m", wc.distance_range.0, wc.distance_range.1),
                format!("Correlation strength: {:.2}", wc.correlation_strength),
                wc.description.clone(),
            ],
            revenue_at_risk_annual: revenue,
            fix_cost_estimate: fix_cost,
            roi,
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
        ticket_num += 1;
    }

    // Sort by priority (P1 first) then by revenue at risk descending
    tickets.sort_by(|a, b| {
        let pa = priority_rank(&a.priority);
        let pb = priority_rank(&b.priority);
        pa.cmp(&pb).then_with(|| {
            b.revenue_at_risk_annual
                .partial_cmp(&a.revenue_at_risk_annual)
                .unwrap_or(std::cmp::Ordering::Equal)
        })
    });

    tickets
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
        "Revenue at Risk: £{:.0}/year",
        ticket.revenue_at_risk_annual
    ));
    lines.push(format!("Fix Cost: £{:.0}", ticket.fix_cost_estimate));
    lines.push(format!("ROI: {:.1}x", ticket.roi));
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
        }
    }

    #[test]
    fn test_ticket_from_reflectance() {
        let mut results = empty_results();
        results.reflectance_events.push(ReflectanceEvent {
            timestamp: Utc::now(),
            port: "0/1/0".to_string(),
            affected_ont_count: 7,
            affected_ont_serials: (0..7).map(|i| format!("ONT{:03}", i)).collect(),
            suspect_ont_serial: "ONT099".to_string(),
            suspect_ont_distance_m: 500.0,
            suspect_tx_anomaly_dbm: 0.8,
            confidence: 0.9,
            events_correlated: 3,
        });

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1);
        assert_eq!(tickets[0].fault_type, TicketFaultType::ReflectanceSource);
        assert_eq!(tickets[0].priority, TicketPriority::P1);
        assert_eq!(tickets[0].team, TeamClassification::Customer);
        assert_eq!(tickets[0].affected_ont_count, 7);
        assert_eq!(tickets[0].sla_days, 1);
        assert!(tickets[0].revenue_at_risk_annual > 0.0);
        assert!(tickets[0].roi > 0.0);
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
                churn_probability_90day: 0.15,
                monthly_revenue_at_risk: 89.90 * 0.15 * 12.0,
            });
        }

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1);
        assert_eq!(tickets[0].fault_type, TicketFaultType::ChurnRisk);
        assert_eq!(tickets[0].priority, TicketPriority::P2);
        assert_eq!(tickets[0].team, TeamClassification::Management);
        assert_eq!(tickets[0].affected_ont_count, 5);
        assert_eq!(tickets[0].sla_days, 5);
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
                rx_power_variance: 0.001,
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
            (tickets[0].revenue_at_risk_annual - expected_rev).abs() < 0.01,
            "Expected revenue {}, got {}",
            expected_rev,
            tickets[0].revenue_at_risk_annual
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
        });

        let tickets = generate_fault_tickets(&results, 89.90);
        assert_eq!(tickets.len(), 1);
        assert_eq!(tickets[0].fault_type, TicketFaultType::CapacityWarning);
        assert_eq!(tickets[0].priority, TicketPriority::P2);
        assert_eq!(tickets[0].team, TeamClassification::Passive);
        assert_eq!(tickets[0].sla_days, 5);
        assert!((tickets[0].fix_cost_estimate - 800.0).abs() < 0.01);
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

    #[test]
    fn test_ticket_format_text() {
        let ticket = FaultTicket {
            ticket_id: "ENLACE-0001".to_string(),
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
            revenue_at_risk_annual: 2700.0,
            fix_cost_estimate: 100.0,
            roi: 27.0,
            recommended_action: "Replace ONT099".to_string(),
            sla_days: 1,
        };

        let text = format_ticket_text(&ticket);
        assert!(text.contains("FAULT TICKET #ENLACE-0001"));
        assert!(text.contains("P1 EMERGENCY"));
        assert!(text.contains("Reflectance Source"));
        assert!(text.contains("Customer"));
        assert!(text.contains("7 ONTs"));
        assert!(text.contains("Suspect ONT: ONT099"));
        assert!(text.contains("2700/year"));
        assert!(text.contains("100"));
        assert!(text.contains("27.0x"));
        assert!(text.contains("Replace ONT099"));
        assert!(text.contains("1 days"));
    }
}
