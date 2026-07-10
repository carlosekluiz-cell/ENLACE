#!/usr/bin/env python3
"""Load the Anatel SMP station licensing export into Postgres.

Source: https://www.anatel.gov.br/dadosabertos/paineis_de_dados/
        outorga_e_licenciamento/estacoes_smp.zip  (Estacoes_SMP.csv)

One row per station-sector-carrier. Creates/refreshes `anatel_stations`
keyed for the calibration joins: by station number (tier 1) and by
location (tier 2 composite via GiST index).
"""

from __future__ import annotations

import csv
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2
import psycopg2.extras

from python.api.config import Settings

CHUNK = 20_000


def _f(v: str) -> float | None:
    if not v:
        return None
    v = v.strip().replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "data/uploads/Estacoes_SMP.csv"
    conn = psycopg2.connect(Settings().database_sync_url)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS anatel_stations (
            id BIGSERIAL PRIMARY KEY,
            station_number VARCHAR(30) NOT NULL,
            freq_tx_mhz DOUBLE PRECISION,
            bandwidth_mhz DOUBLE PRECISION,
            technology VARCHAR(30),
            generation VARCHAR(10),
            band VARCHAR(20),
            lat DOUBLE PRECISION NOT NULL,
            lon DOUBLE PRECISION NOT NULL,
            operator VARCHAR(120),
            uf VARCHAR(4),
            situacao VARCHAR(30),
            licensed_at DATE
        )
    """)
    cur.execute("TRUNCATE anatel_stations")
    conn.commit()

    text = Path(path).read_bytes().decode("utf-8-sig", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    cols = {c.strip(): c for c in reader.fieldnames or []}

    def col(name):
        for k, orig in cols.items():
            if name.lower() in k.lower():
                return orig
        return None

    c_sta = cols.get("Número Estação") or col("estação") or col("estacao")
    c_ftx = col("FreqTxMHz")
    c_bw = col("Banda_MHZ")
    c_tec = cols.get("Tecnologia")
    c_ger = col("Geracao") or col("Geração")
    c_faixa = col("Faixa Estacao") or col("Faixa Estação")
    c_lat = col("Latitude decimal")
    c_lon = col("Longitude decimal")
    c_op = col("Empresa Estacao") or col("Empresa Estação") or col("Entidade")
    c_uf = cols.get("UF")
    c_sit = col("Situacao") or col("Situação")
    c_lic = col("Data Licenciamento")

    total, t0, batch = 0, time.time(), []

    def flush():
        nonlocal total, batch
        if not batch:
            return
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO anatel_stations
               (station_number, freq_tx_mhz, bandwidth_mhz, technology,
                generation, band, lat, lon, operator, uf, situacao, licensed_at)
               VALUES %s""",
            batch,
        )
        conn.commit()
        total += len(batch)
        batch = []
        print(f"  {total:>9,} rows ({total / max(1, time.time() - t0):,.0f}/s)", flush=True)

    for row in reader:
        sta = (row.get(c_sta) or "").strip()
        lat, lon = _f(row.get(c_lat)), _f(row.get(c_lon))
        if not sta or lat is None or lon is None:
            continue
        if not (-34.5 <= lat <= 6.0 and -74.5 <= lon <= -28.5):
            continue
        lic_raw = (row.get(c_lic) or "").strip() if c_lic else ""
        licensed = None
        if lic_raw:
            p = lic_raw.split("/")
            if len(p) == 3 and len(p[2]) == 4:
                licensed = f"{p[2]}-{p[1]}-{p[0]}"
            elif len(lic_raw) == 10 and lic_raw[4] == "-":
                licensed = lic_raw
        batch.append(
            (
                sta,
                _f(row.get(c_ftx)) if c_ftx else None,
                _f(row.get(c_bw)) if c_bw else None,
                (row.get(c_tec) or "").strip()[:30] if c_tec else None,
                (row.get(c_ger) or "").strip()[:10] if c_ger else None,
                (row.get(c_faixa) or "").strip()[:20] if c_faixa else None,
                lat,
                lon,
                (row.get(c_op) or "").strip()[:120] if c_op else None,
                (row.get(c_uf) or "").strip()[:4] if c_uf else None,
                (row.get(c_sit) or "").strip()[:30] if c_sit else None,
                licensed,
            )
        )
        if len(batch) >= CHUNK:
            flush()
    flush()

    print("indexing…", flush=True)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ast_station ON anatel_stations (station_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ast_geo ON anatel_stations USING gist (ll_to_earth(lat, lon))")
    conn.commit()
    cur.close()
    conn.close()
    print(f"DONE: {total:,} station-carrier rows in {time.time() - t0:,.0f}s")


if __name__ == "__main__":
    main()
