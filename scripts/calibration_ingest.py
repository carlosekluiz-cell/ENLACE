#!/usr/bin/env python3
"""Load RF measurements into the calibration store.

Supports:
  1. Anatel EMF conformity CSVs ("Medições de campos eletromagnéticos")
     — E-field V/m converted to equivalent isotropic received power (dBm).
  2. Generic CSV with explicit column mapping.

Usage (from repo root):
  python3 scripts/calibration_ingest.py anatel-emf medidas.csv --campaign 2024
  python3 scripts/calibration_ingest.py generic drive_test.csv \
      --lat-col latitude --lon-col longitude --freq-col freq_mhz \
      --dbm-col rsrp --source drive-test-sp
  # then:  curl -X POST .../api/v1/design/calibration/run

Physics for EMF -> dBm (far-field, isotropic receive antenna):
  S [W/m^2] = E^2 / 377
  Pr [W]    = S * Aeff,  Aeff = lambda^2 / (4*pi)
  Pr [dBm]  = 10*log10(Pr) + 30
This makes Anatel conformity measurements comparable to predicted receive
power at the measurement point. Field readings without frequency are skipped.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from python.api.services.calibration import Measurement, record_measurements  # noqa: E402


def efield_to_dbm(e_vm: float, freq_mhz: float) -> float:
    """Convert an E-field measurement (V/m) to isotropic received power (dBm)."""
    if e_vm <= 0 or freq_mhz <= 0:
        raise ValueError("E-field and frequency must be positive")
    s = e_vm**2 / 377.0  # W/m^2
    wavelength = 299.792458 / freq_mhz  # m
    aeff = wavelength**2 / (4 * math.pi)
    pr_w = s * aeff
    return 10 * math.log10(pr_w) + 30


def _to_float(value: str) -> float | None:
    if value is None:
        return None
    value = value.strip().replace(",", ".")
    if not value or value.lower() in ("na", "nan", "-"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_anatel_emf(path: str, campaign: str | None) -> list[Measurement]:
    """Anatel EMF CSV: expects columns for lat/lon, frequency (MHz) and
    E-field (V/m); column names vary per release, so match loosely."""
    out = []
    with open(path, newline="", encoding="latin-1") as f:
        sample = f.read(4096)
        f.seek(0)
        # Anatel publishes CSVs and tab-separated TXTs interchangeably
        counts = {d: sample.count(d) for d in (";", "\t", ",")}
        delim = max(counts, key=counts.get)
        reader = csv.DictReader(f, delimiter=delim)
        cols = {c.lower().strip(): c for c in reader.fieldnames or []}

        def find(*cands):
            for cand in cands:
                for k, orig in cols.items():
                    if cand in k:
                        return orig
            return None

        lat_c = find("latitude", "lat")
        lon_c = find("longitude", "lon")
        freq_c = find("frequencia", "freq")
        e_c = find("campo", "v/m", "intensidade", "e_med", "valor")
        date_c = find("data")
        if not (lat_c and lon_c and e_c):
            raise SystemExit(
                f"Could not identify columns; found: {list(cols.keys())[:20]}"
            )
        for row in reader:
            lat, lon = _to_float(row.get(lat_c)), _to_float(row.get(lon_c))
            e_vm = _to_float(row.get(e_c))
            freq = _to_float(row.get(freq_c)) if freq_c else None
            if lat is None or lon is None or e_vm is None or not freq:
                continue
            try:
                dbm = efield_to_dbm(e_vm, freq)
            except ValueError:
                continue
            out.append(
                Measurement(
                    lat=lat,
                    lon=lon,
                    frequency_mhz=freq,
                    measured_dbm=round(dbm, 2),
                    source="anatel-emf",
                    campaign=campaign,
                    measured_at=(row.get(date_c) or None) if date_c else None,
                    meta={"e_field_vm": e_vm},
                )
            )
    return out


def load_generic(path: str, args) -> list[Measurement]:
    out = []
    with open(path, newline="", encoding=args.encoding) as f:
        reader = csv.DictReader(f, delimiter=args.delimiter)
        for row in reader:
            lat = _to_float(row.get(args.lat_col))
            lon = _to_float(row.get(args.lon_col))
            freq = _to_float(row.get(args.freq_col))
            dbm = _to_float(row.get(args.dbm_col))
            if None in (lat, lon, freq, dbm):
                continue
            out.append(
                Measurement(
                    lat=lat,
                    lon=lon,
                    frequency_mhz=freq,
                    measured_dbm=dbm,
                    tx_lat=_to_float(row.get(args.tx_lat_col)) if args.tx_lat_col else None,
                    tx_lon=_to_float(row.get(args.tx_lon_col)) if args.tx_lon_col else None,
                    tx_height_m=_to_float(row.get(args.tx_height_col)) if args.tx_height_col else None,
                    tx_power_dbm=_to_float(row.get(args.tx_power_col)) if args.tx_power_col else None,
                    source=args.source,
                    campaign=args.campaign,
                )
            )
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("anatel-emf", help="Anatel EMF conformity CSV")
    pa.add_argument("csv_path")
    pa.add_argument("--campaign", default=None)

    pg = sub.add_parser("generic", help="Generic CSV with column mapping")
    pg.add_argument("csv_path")
    pg.add_argument("--lat-col", required=True)
    pg.add_argument("--lon-col", required=True)
    pg.add_argument("--freq-col", required=True)
    pg.add_argument("--dbm-col", required=True)
    pg.add_argument("--tx-lat-col")
    pg.add_argument("--tx-lon-col")
    pg.add_argument("--tx-height-col")
    pg.add_argument("--tx-power-col")
    pg.add_argument("--source", default="generic-csv")
    pg.add_argument("--campaign", default=None)
    pg.add_argument("--delimiter", default=",")
    pg.add_argument("--encoding", default="utf-8")

    args = p.parse_args()
    if args.cmd == "anatel-emf":
        measurements = load_anatel_emf(args.csv_path, args.campaign)
    else:
        measurements = load_generic(args.csv_path, args)

    if not measurements:
        raise SystemExit("No valid measurements parsed — check column mapping.")
    stored = record_measurements(measurements)
    print(f"Stored {stored} measurements from {args.csv_path}")
    print("Next: POST /api/v1/design/calibration/run to score residuals.")


if __name__ == "__main__":
    main()
