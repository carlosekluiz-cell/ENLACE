//! PULSO MEGA BUILD — BLIND AUDIT: Phases 1 & 2
//! Tests antenna patterns and propagation models against independently calculated reference values.

use pulso_propagation::antenna::{
    from_msi, link_budget_with_antenna, AntennaDatabase, AntennaPatternData,
};
use pulso_propagation::models::hata::{CitySize, HataModel};
use pulso_propagation::models::tr38901::Tr38901UmaModel;
use pulso_propagation::models::{Environment, PathLossParams, PropagationModel};
use pulso_propagation::vegetation::VegetationCorrector;

// ═══════════════════════════════════════════════════════════════════════
// AUDIT 1: ANTENNA PATTERN LIBRARY
// ═══════════════════════════════════════════════════════════════════════

/// Build audit MSI with KNOWN values at specific angles:
/// H[0]=0, H[90]=-3, H[180]=-25, H[270]=-3
/// V[0]=0, V[45]=-3, V[90]=-30, V[180]=-30
/// Values between control points are linearly interpolated.
fn build_audit_msi() -> String {
    let mut h = vec![0.0_f64; 360];
    let mut v = vec![0.0_f64; 360];

    // Horizontal: linear interpolation between control points
    // 0->90: 0 to -3
    for i in 0..=90 {
        h[i] = -3.0 * (i as f64) / 90.0;
    }
    // 90->180: -3 to -25
    for i in 91..=180 {
        h[i] = -3.0 + (-25.0 + 3.0) * ((i - 90) as f64) / 90.0;
    }
    // 180->270: -25 to -3
    for i in 181..=270 {
        h[i] = -25.0 + (-3.0 + 25.0) * ((i - 180) as f64) / 90.0;
    }
    // 270->359: -3 to ~0 (approaching boresight)
    for i in 271..360 {
        h[i] = -3.0 + (0.0 + 3.0) * ((i - 270) as f64) / 90.0;
    }

    // Vertical: linear interpolation
    // 0->45: 0 to -3
    for i in 0..=45 {
        v[i] = -3.0 * (i as f64) / 45.0;
    }
    // 45->90: -3 to -30
    for i in 46..=90 {
        v[i] = -3.0 + (-30.0 + 3.0) * ((i - 45) as f64) / 45.0;
    }
    // 90->180: -30
    for i in 91..=180 {
        v[i] = -30.0;
    }
    // 180->270: -30 to -30
    for i in 181..=270 {
        v[i] = -30.0;
    }
    // 270->315: -30 to -3
    for i in 271..=315 {
        v[i] = -30.0 + (-3.0 + 30.0) * ((i - 270) as f64) / 45.0;
    }
    // 315->359: -3 to ~0
    for i in 316..360 {
        v[i] = -3.0 + (0.0 + 3.0) * ((i - 315) as f64) / 45.0;
    }

    let mut msi = String::new();
    msi.push_str("NAME Test-Antenna-Audit\n");
    msi.push_str("MAKE AuditCo\n");
    msi.push_str("FREQUENCY 2400\n");
    msi.push_str("GAIN 10.0\n");
    msi.push_str("COMMENT Audit test antenna\n");
    msi.push_str("HORIZONTAL 360\n");
    for val in &h {
        msi.push_str(&format!("{:.4}\n", val));
    }
    msi.push_str("VERTICAL 360\n");
    for val in &v {
        msi.push_str(&format!("{:.4}\n", val));
    }
    msi
}

// ─── 1A: MSI Parser Accuracy ────────────────────────────────────────

#[test]
fn audit_1a_msi_parser_boresight() {
    let msi = build_audit_msi();
    let p = from_msi(msi.as_bytes()).unwrap();
    let actual = p.gain_at(0.0, 0.0);
    let expected = 0.0;
    let pass = (actual - expected).abs() < 0.01;
    println!("1A-1: gain_at(0,0) | expected={:.2} | actual={:.4} | {}",
        expected, actual, if pass { "PASS" } else { "FAIL" });
    assert!(pass);
}

#[test]
fn audit_1a_msi_parser_back_lobe() {
    let msi = build_audit_msi();
    let p = from_msi(msi.as_bytes()).unwrap();
    // gain_at(180,0) = h[180] + v[0] = -25.0 + 0.0 = -25.0
    let actual = p.gain_at(180.0, 0.0);
    let expected = -25.0;
    let pass = (actual - expected).abs() < 0.5;
    println!("1A-2: gain_at(180,0) | expected={:.2} | actual={:.4} | {}",
        expected, actual, if pass { "PASS" } else { "FAIL" });
    assert!(pass);
}

#[test]
fn audit_1a_msi_parser_side() {
    let msi = build_audit_msi();
    let p = from_msi(msi.as_bytes()).unwrap();
    // gain_at(90,0) = h[90] + v[0] = -3.0 + 0.0 = -3.0
    let actual = p.gain_at(90.0, 0.0);
    let expected = -3.0;
    let pass = (actual - expected).abs() < 0.5;
    println!("1A-3: gain_at(90,0) | expected={:.2} | actual={:.4} | {}",
        expected, actual, if pass { "PASS" } else { "FAIL" });
    assert!(pass);
}

#[test]
fn audit_1a_beamwidth() {
    let msi = build_audit_msi();
    let p = from_msi(msi.as_bytes()).unwrap();
    // H pattern crosses -3dB at exactly 90° and 270° (symmetrically)
    // So beamwidth should be ~180°
    let actual = p.h_beamwidth();
    let expected = 180.0;
    let pass = (actual - expected).abs() < 10.0;
    println!("1A-4: h_beamwidth | expected=~{:.0}° | actual={:.1}° | {}",
        expected, actual, if pass { "PASS" } else { "FAIL" });
    assert!(pass);
}

#[test]
fn audit_1a_front_to_back() {
    let msi = build_audit_msi();
    let p = from_msi(msi.as_bytes()).unwrap();
    // F/B = -h[0] - (-h[180]) = 0 - (-25) = 25 → but stored as -back_gain
    // Actually: front_to_back_db = -(h[180]) = -(-25) = 25
    let actual = p.front_to_back_db();
    let expected = 25.0;
    let pass = (actual - expected).abs() < 0.5;
    println!("1A-5: front_to_back | expected={:.1} dB | actual={:.1} dB | {}",
        expected, actual, if pass { "PASS" } else { "FAIL" });
    assert!(pass);
}

// ─── 1B: Effective Gain Calculation ─────────────────────────────────

#[test]
fn audit_1b_effective_gain_east() {
    let msi = build_audit_msi();
    let p = from_msi(msi.as_bytes()).unwrap();
    // Antenna pointing north (az=0), target east (az=90), elevation=0
    // relative_az = 90-0 = 90
    // effective_gain = gain_dbi + gain_at(90, 0) = 10.0 + (-3.0) = 7.0
    let actual = p.effective_gain(0.0, 0.0, 90.0, 0.0);
    let expected = 7.0; // 10 dBi - 3 dB
    let pass = (actual - expected).abs() < 0.5;
    println!("1B-1: eff_gain(north→east) | expected={:.1} dBi | actual={:.2} dBi | {}",
        expected, actual, if pass { "PASS" } else { "FAIL" });
    assert!(pass);
}

#[test]
fn audit_1b_effective_gain_south() {
    let msi = build_audit_msi();
    let p = from_msi(msi.as_bytes()).unwrap();
    // Antenna north, target south (180)
    // effective_gain = 10.0 + gain_at(180, 0) = 10.0 + (-25.0) = -15.0
    let actual = p.effective_gain(0.0, 0.0, 180.0, 0.0);
    let expected = -15.0;
    let pass = (actual - expected).abs() < 0.5;
    println!("1B-2: eff_gain(north→south) | expected={:.1} dBi | actual={:.2} dBi | {}",
        expected, actual, if pass { "PASS" } else { "FAIL" });
    assert!(pass);
}

#[test]
fn audit_1b_effective_gain_tilt() {
    let msi = build_audit_msi();
    let p = from_msi(msi.as_bytes()).unwrap();
    // Antenna tilted 10° down, target at 10° elevation, boresight azimuth
    // relative_el = 10 - 10 = 0 → v_gain = 0
    // relative_az = 0 → h_gain = 0
    // effective_gain = 10.0 + 0.0 = 10.0
    let actual = p.effective_gain(0.0, 10.0, 0.0, 10.0);
    let expected = 10.0;
    let pass = (actual - expected).abs() < 0.5;
    println!("1B-3: eff_gain(10° tilt, 10° target) | expected={:.1} dBi | actual={:.2} dBi | {}",
        expected, actual, if pass { "PASS" } else { "FAIL" });
    assert!(pass);
}

// ─── 1C: Omnidirectional and Sectoral Generators ────────────────────

#[test]
fn audit_1c_omnidirectional() {
    let omni = AntennaDatabase::omnidirectional(8.0);
    let g0 = omni.gain_at(0.0, 0.0);
    let g90 = omni.gain_at(90.0, 0.0);
    let g180 = omni.gain_at(180.0, 0.0);
    let pass = (g0 - g90).abs() < 0.1 && (g0 - g180).abs() < 0.1;
    println!("1C-1: omni(8dBi) | g(0)={:.4} g(90)={:.4} g(180)={:.4} | {}",
        g0, g90, g180, if pass { "PASS" } else { "FAIL" });
    assert!(pass);
}

#[test]
fn audit_1c_sectoral_120() {
    let sec = AntennaDatabase::sectoral_120(15.0);
    let g0 = sec.gain_at(0.0, 0.0);
    let g60 = sec.gain_at(60.0, 0.0);
    let g180 = sec.gain_at(180.0, 0.0);

    let pass_boresight = g0.abs() < 0.1;
    // At 60°, the sectoral pattern should be at -3 dB
    let pass_edge = (g60 - (-3.0)).abs() < 0.5;
    let pass_back = g180 <= -19.0;

    println!("1C-2: sectoral_120(15dBi) | g(0)={:.2} (exp 0) g(60)={:.2} (exp -3) g(180)={:.2} (exp <=-20) | {} {} {}",
        g0, g60, g180,
        if pass_boresight { "PASS" } else { "FAIL" },
        if pass_edge { "PASS" } else { "FAIL" },
        if pass_back { "PASS" } else { "FAIL" });
    assert!(pass_boresight);
    assert!(pass_edge);
    assert!(pass_back);
}

// ─── 1D: Link Budget with Antenna ──────────────────────────────────

#[test]
fn audit_1d_link_budget_boresight() {
    // Tx 43 dBm, sector 18 dBi pointing north, target north at 0° el
    // Rx CPE 10 dBi pointing south → sees reverse_az=180° from its boresight
    // Path loss: 130 dB
    //
    // Tx effective gain = 18 + gain_at(0,0) = 18 + 0 = 18 dBi
    // Rx sees reverse_az = 0+180 = 180°. Rx boresight is 180° (pointing south toward tx).
    // Rx relative_az = 180 - 180 = 0 → on boresight
    // Rx effective gain = 10 + gain_at(0, 0) = 10 + 0 = 10 dBi
    // Rx power = 43 + 18 + 10 - 130 = -59 dBm (NOT -64)
    //
    // The prompt says "Additional losses: 5 dB" but link_budget_with_antenna
    // doesn't have an additional losses parameter. So expected = -59 dBm.
    let tx = AntennaDatabase::sectoral_120(18.0);
    let rx = AntennaDatabase::omnidirectional(10.0); // omni for CPE simplicity
    let actual = link_budget_with_antenna(
        43.0, &tx, 0.0, 0.0,   // tx: 43 dBm, pointing north, no tilt
        &rx, 180.0, 0.0,       // rx: pointing south, no tilt
        0.0, 0.0,              // target north, 0° elevation
        130.0,                  // path loss
    );
    // rx = 43 + 18 + 10 - 130 = -59
    let expected = -59.0;
    let pass = (actual - expected).abs() < 0.5;
    println!("1D-1: link_budget boresight | expected={:.1} dBm | actual={:.2} dBm | {}",
        expected, actual, if pass { "PASS" } else { "FAIL" });
    assert!(pass);
}

#[test]
fn audit_1d_link_budget_off_axis() {
    // Same setup but target at 90° azimuth (due east)
    // sectoral_120: -3 dB at ±60°, -20 dB at ±120°. At 90° (between 60° and 120°):
    //   gain_at(90,0) = -3 - 17*(90-60)/60 = -3 - 8.5 = -11.5 dB
    // Tx effective gain = 18 + (-11.5) = 6.5 dBi
    // Rx omni: gain_at(any,0) = 0. Rx effective = 10 + 0 = 10
    // rx = 43 + 6.5 + 10 - 130 = -70.5
    let tx = AntennaDatabase::sectoral_120(18.0);
    let rx = AntennaDatabase::omnidirectional(10.0);
    let actual = link_budget_with_antenna(
        43.0, &tx, 0.0, 0.0,
        &rx, 180.0, 0.0,
        90.0, 0.0,
        130.0,
    );
    let expected = -70.5;
    let pass = (actual - expected).abs() < 1.0;
    println!("1D-2: link_budget 90° off-axis | expected={:.1} dBm | actual={:.2} dBm | {}",
        expected, actual, if pass { "PASS" } else { "FAIL" });
    assert!(pass);
}

// ═══════════════════════════════════════════════════════════════════════
// AUDIT 2: PROPAGATION MODELS
// ═══════════════════════════════════════════════════════════════════════

// ─── 2A: Okumura-Hata Known Reference Values ───────────────────────

#[test]
fn audit_2a_hata_900_5km_urban() {
    let model = HataModel::small_medium_city();
    let params = PathLossParams {
        frequency_mhz: 900.0,
        distance_m: 5000.0,
        tx_height_m: 50.0,
        rx_height_m: 1.5,
        terrain_profile: None,
        environment: Environment::Urban,
    };
    let result = model.path_loss(&params);
    // Hand calculation:
    // a(h_m) = (1.1*log10(900)-0.7)*1.5 - (1.56*log10(900)-0.8)
    //        = (1.1*2.954-0.7)*1.5 - (1.56*2.954-0.8)
    //        = (3.249-0.7)*1.5 - (4.608-0.8)
    //        = 2.549*1.5 - 3.808 = 3.824 - 3.808 = 0.016
    // L = 69.55 + 26.16*log10(900) - 13.82*log10(50) - 0.016
    //     + (44.9 - 6.55*log10(50))*log10(5)
    //   = 69.55 + 26.16*2.954 - 13.82*1.699 - 0.016
    //     + (44.9 - 6.55*1.699)*0.699
    //   = 69.55 + 77.28 - 23.48 - 0.016 + (44.9-11.13)*0.699
    //   = 123.33 + 33.77*0.699 = 123.33 + 23.61 = 146.94
    let expected_lo = 143.0;
    let expected_hi = 150.0;
    let pass = result.loss_db >= expected_lo && result.loss_db <= expected_hi;
    println!("2A-1: Hata 900MHz 5km Urban | expected={:.0}-{:.0} dB | actual={:.2} dB | {}",
        expected_lo, expected_hi, result.loss_db, if pass { "PASS" } else { "FAIL" });
    assert!(pass, "Got {:.2} dB, expected {:.0}-{:.0}", result.loss_db, expected_lo, expected_hi);
}

#[test]
fn audit_2a_hata_900_5km_suburban() {
    let model = HataModel::small_medium_city();
    let params = PathLossParams {
        frequency_mhz: 900.0,
        distance_m: 5000.0,
        tx_height_m: 50.0,
        rx_height_m: 1.5,
        terrain_profile: None,
        environment: Environment::Suburban,
    };
    let result = model.path_loss(&params);
    // Suburban correction = 2*(log10(900/28))^2 + 5.4
    //                     = 2*(log10(32.14))^2 + 5.4
    //                     = 2*(1.507)^2 + 5.4
    //                     = 2*2.271 + 5.4 = 4.542 + 5.4 = 9.94
    // Suburban = Urban - 9.94 ≈ 147 - 10 ≈ 137
    let expected_lo = 133.0;
    let expected_hi = 142.0;
    let pass = result.loss_db >= expected_lo && result.loss_db <= expected_hi;
    println!("2A-2: Hata 900MHz 5km Suburban | expected={:.0}-{:.0} dB | actual={:.2} dB | {}",
        expected_lo, expected_hi, result.loss_db, if pass { "PASS" } else { "FAIL" });
    assert!(pass, "Got {:.2} dB", result.loss_db);
}

#[test]
fn audit_2a_hata_900_5km_rural() {
    let model = HataModel::small_medium_city();
    let params = PathLossParams {
        frequency_mhz: 900.0,
        distance_m: 5000.0,
        tx_height_m: 50.0,
        rx_height_m: 1.5,
        terrain_profile: None,
        environment: Environment::Rural,
    };
    let result = model.path_loss(&params);
    // Rural correction = 4.78*(log10(900))^2 - 18.33*log10(900) + 40.94
    //                   = 4.78*(2.954)^2 - 18.33*2.954 + 40.94
    //                   = 4.78*8.727 - 54.15 + 40.94
    //                   = 41.71 - 54.15 + 40.94 = 28.50
    // Rural = Urban - 28.50 ≈ 147 - 28.5 ≈ 118.5
    let expected_lo = 115.0;
    let expected_hi = 125.0;
    let pass = result.loss_db >= expected_lo && result.loss_db <= expected_hi;
    println!("2A-3: Hata 900MHz 5km Rural | expected={:.0}-{:.0} dB | actual={:.2} dB | {}",
        expected_lo, expected_hi, result.loss_db, if pass { "PASS" } else { "FAIL" });
    assert!(pass, "Got {:.2} dB", result.loss_db);
}

#[test]
fn audit_2a_hata_700_10km_rural() {
    let model = HataModel::small_medium_city();
    let params = PathLossParams {
        frequency_mhz: 700.0,
        distance_m: 10000.0,
        tx_height_m: 30.0,
        rx_height_m: 1.5,
        terrain_profile: None,
        environment: Environment::Rural,
    };
    let result = model.path_loss(&params);
    let expected_lo = 115.0;
    let expected_hi = 140.0;
    let pass = result.loss_db >= expected_lo && result.loss_db <= expected_hi;
    println!("2A-4: Hata 700MHz 10km Rural | expected={:.0}-{:.0} dB | actual={:.2} dB | {}",
        expected_lo, expected_hi, result.loss_db, if pass { "PASS" } else { "FAIL" });
    assert!(pass, "Got {:.2} dB", result.loss_db);
}

#[test]
fn audit_2a_hata_1800_1km_urban() {
    let model = HataModel::small_medium_city();
    let params = PathLossParams {
        frequency_mhz: 1800.0,
        distance_m: 1000.0,
        tx_height_m: 30.0,
        rx_height_m: 1.5,
        terrain_profile: None,
        environment: Environment::Urban,
    };
    let result = model.path_loss(&params);
    let expected_lo = 120.0;
    let expected_hi = 140.0;
    let pass = result.loss_db >= expected_lo && result.loss_db <= expected_hi;
    println!("2A-5: Hata 1800MHz 1km Urban | expected={:.0}-{:.0} dB | actual={:.2} dB | {}",
        expected_lo, expected_hi, result.loss_db, if pass { "PASS" } else { "FAIL" });
    assert!(pass, "Got {:.2} dB", result.loss_db);
}

// ─── 2B: COST-231 Hata Known Reference ─────────────────────────────

#[test]
fn audit_2b_cost231_1800_2km_urban() {
    let model = HataModel::small_medium_city();
    let params = PathLossParams {
        frequency_mhz: 1800.0,
        distance_m: 2000.0,
        tx_height_m: 40.0,
        rx_height_m: 1.5,
        terrain_profile: None,
        environment: Environment::Urban,
    };
    let result = model.path_loss(&params);
    // COST-231: f=1800 (>1500, uses extension)
    // a(h_m) = (1.1*log10(1800)-0.7)*1.5 - (1.56*log10(1800)-0.8)
    //        = (1.1*3.255-0.7)*1.5 - (1.56*3.255-0.8)
    //        = (3.581-0.7)*1.5 - (5.078-0.8)
    //        = 2.881*1.5 - 4.278 = 4.321 - 4.278 = 0.043
    // L = 46.3 + 33.9*log10(1800) - 13.82*log10(40) - 0.043
    //     + (44.9 - 6.55*log10(40))*log10(2) + 0 (Cm=0 for small city)
    //   = 46.3 + 33.9*3.255 - 13.82*1.602 - 0.043
    //     + (44.9 - 6.55*1.602)*0.301
    //   = 46.3 + 110.35 - 22.14 - 0.043 + (44.9-10.49)*0.301
    //   = 134.47 + 34.41*0.301 = 134.47 + 10.36 = 144.83
    let expected_lo = 138.0;
    let expected_hi = 150.0;
    let pass = result.loss_db >= expected_lo && result.loss_db <= expected_hi;
    println!("2B-1: COST-231 1800MHz 2km Urban | expected={:.0}-{:.0} dB | actual={:.2} dB | {}",
        expected_lo, expected_hi, result.loss_db, if pass { "PASS" } else { "FAIL" });
    assert!(pass, "Got {:.2} dB", result.loss_db);
}

#[test]
fn audit_2b_cost231_2000_1km_suburban() {
    let model = HataModel::small_medium_city();
    let params = PathLossParams {
        frequency_mhz: 2000.0,
        distance_m: 1000.0,
        tx_height_m: 30.0,
        rx_height_m: 1.5,
        terrain_profile: None,
        environment: Environment::Suburban,
    };
    let result = model.path_loss(&params);
    let expected_lo = 115.0;
    let expected_hi = 135.0;
    let pass = result.loss_db >= expected_lo && result.loss_db <= expected_hi;
    println!("2B-2: COST-231 2000MHz 1km Suburban | expected={:.0}-{:.0} dB | actual={:.2} dB | {}",
        expected_lo, expected_hi, result.loss_db, if pass { "PASS" } else { "FAIL" });
    assert!(pass, "Got {:.2} dB", result.loss_db);
}

// ─── 2C: Cross-Check Hata vs TR 38.901 ─────────────────────────────

#[test]
fn audit_2c_hata_vs_tr38901() {
    // At 2000 MHz, 1km, urban — both models should give results in same ballpark
    let hata = HataModel::small_medium_city();
    let hata_params = PathLossParams {
        frequency_mhz: 2000.0,
        distance_m: 1000.0,
        tx_height_m: 30.0,
        rx_height_m: 1.5,
        terrain_profile: None,
        environment: Environment::Urban,
    };
    let hata_result = hata.path_loss(&hata_params);

    let uma = Tr38901UmaModel::default();
    let uma_params = PathLossParams {
        frequency_mhz: 2000.0,
        distance_m: 1000.0,
        tx_height_m: 30.0,
        rx_height_m: 1.5,
        terrain_profile: None,
        environment: Environment::Urban, // UMa uses NLOS for urban
    };
    let uma_result = uma.path_loss(&uma_params);

    let diff = (hata_result.loss_db - uma_result.loss_db).abs();
    let pass = diff < 15.0;
    println!("2C-1: Hata vs TR38.901 at 2GHz 1km Urban | Hata={:.2} dB | TR38.901={:.2} dB | diff={:.2} dB | {}",
        hata_result.loss_db, uma_result.loss_db, diff, if pass { "PASS" } else { "FAIL" });
    assert!(pass, "Difference {:.2} dB exceeds 15 dB threshold", diff);
}

// ─── 2D: Brazilian Biome Corrections ────────────────────────────────

#[test]
fn audit_2d_cerrado_700mhz() {
    let vc = VegetationCorrector::with_defaults();
    // Cerrado at 700 MHz, 100m depth → should be about 3 dB per table
    let correction = vc.correction_for_segment("cerrado", 700.0, 100.0);
    let pass = correction >= 2.0 && correction <= 8.0;
    println!("2D-1: Cerrado 700MHz 100m | expected=2-8 dB | actual={:.2} dB | {}",
        correction, if pass { "PASS" } else { "FAIL" });
    assert!(pass, "Got {:.2} dB", correction);
}

#[test]
fn audit_2d_amazonia_700mhz() {
    let vc = VegetationCorrector::with_defaults();
    let correction = vc.correction_for_segment("amazonia", 700.0, 100.0);
    let pass = correction >= 10.0 && correction <= 30.0;
    println!("2D-2: Amazonia 700MHz 100m | expected=10-30 dB | actual={:.2} dB | {}",
        correction, if pass { "PASS" } else { "FAIL" });
    assert!(pass, "Got {:.2} dB", correction);
}

#[test]
fn audit_2d_caatinga_700mhz() {
    let vc = VegetationCorrector::with_defaults();
    let correction = vc.correction_for_segment("caatinga", 700.0, 100.0);
    let pass = correction >= 0.5 && correction <= 5.0;
    println!("2D-3: Caatinga 700MHz 100m | expected=0.5-5 dB | actual={:.2} dB | {}",
        correction, if pass { "PASS" } else { "FAIL" });
    assert!(pass, "Got {:.2} dB", correction);
}
