#!/usr/bin/env python3
"""Stream Anatel RNI measurement CSVs into rf_measurements.

Handles both published layouts:
  A) mapa_rni (medicoes_rni.csv): Numero_estação;Operador_estação;...;
     data_medida;ano;tipo_medicao_nome;latitude;longitude;Codigo_IBGE;
     valor_medio;Município;Estado
  B) 2016-2020: Responsável;...;Data da Medicao;Hora;Tipo de Medicao;
     Latitude;Longitude;Municipio;UF;Valor Medio;% do Limite;
     Número Estação;Operadora da Estação

Quirks handled: UTF-8 BOM, bare-\r line endings, decimal commas,
"N/I"/"N/A" placeholders. Rows are stored with e_field_vm + optional
station_number; frequency/measured_dbm stay NULL until the enrichment
join against the Anatel licensing registry (single-station or composite
multi-emitter attribution).

Usage: python3 scripts/ingest_rni.py <csv_path> [--source anatel-rni]
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2
import psycopg2.extras

from python.api.config import Settings

CHUNK = 10_000


def _f(value: str) -> float | None:
    if not value:
        return None
    value = value.strip().replace(",", ".")
    if not value or value.upper() in ("N/I", "N/A", "NAN", "-"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _norm(name: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return s.lower().strip().replace(" ", "_")


def iter_rows(path: str):
    """Yield dict rows from either layout, normalizing quirks."""
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    cols = {_norm(c): c for c in reader.fieldnames or []}

    def col(*cands):
        for cand in cands:
            if cand in cols:
                return cols[cand]
        return None

    lat_c = col("latitude")
    lon_c = col("longitude")
    val_c = col("valor_medio")
    sta_c = col("numero_estacao", "numero_estaco")
    date_c = col("data_medida", "data_da_medicao")
    tipo_c = col("tipo_medicao_nome", "tipo_de_medicao")
    uf_c = col("estado", "uf")
    mun_c = col("municipio")
    if not (lat_c and lon_c and val_c):
        raise SystemExit(f"colunas não reconhecidas: {list(cols)[:16]}")

    for row in reader:
        lat, lon, e_vm = _f(row.get(lat_c)), _f(row.get(lon_c)), _f(row.get(val_c))
        if lat is None or lon is None or e_vm is None or e_vm <= 0:
            continue
        if not (-34.5 <= lat <= 6.0 and -74.5 <= lon <= -28.5):
            continue
        station = (row.get(sta_c) or "").strip() if sta_c else ""
        if station.upper() in ("N/I", "N/A", ""):
            station = None
        date_raw = (row.get(date_c) or "").strip() if date_c else ""
        measured_at = None
        if date_raw:
            # dd/mm/yyyy -> ISO
            parts = date_raw.split("/")
            if len(parts) == 3 and len(parts[2]) == 4:
                measured_at = f"{parts[2]}-{parts[1]}-{parts[0]}"
        yield (
            lat,
            lon,
            e_vm,
            station,
            measured_at,
            (row.get(tipo_c) or "").strip() if tipo_c else "",
            (row.get(uf_c) or "").strip() if uf_c else "",
            (row.get(mun_c) or "").strip() if mun_c else "",
        )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("csv_path")
    p.add_argument("--source", default="anatel-rni")
    p.add_argument("--campaign", default=None)
    args = p.parse_args()
    campaign = args.campaign or Path(args.csv_path).name

    conn = psycopg2.connect(Settings().database_sync_url)
    cur = conn.cursor()
    total, t0 = 0, time.time()
    batch = []

    def flush():
        nonlocal total, batch
        if not batch:
            return
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO rf_measurements
            (lat, lon, e_field_vm, station_number, measured_at,
             frequency_mhz, measured_dbm, source, campaign, meta)
            VALUES %s
            """,
            batch,
            template="(%s,%s,%s,%s,%s,NULL,NULL,%s,%s,%s::jsonb)",
        )
        conn.commit()
        total += len(batch)
        batch = []
        print(f"  {total:>9,} rows  ({total / max(1, time.time() - t0):,.0f}/s)", flush=True)

    import json

    for lat, lon, e_vm, station, measured_at, tipo, uf, mun in iter_rows(args.csv_path):
        meta = json.dumps({"tipo": tipo, "uf": uf, "municipio": mun})
        batch.append((lat, lon, e_vm, station, measured_at, args.source, campaign, meta))
        if len(batch) >= CHUNK:
            flush()
    flush()
    cur.close()
    conn.close()
    print(f"DONE: {total:,} measurements from {args.csv_path} in {time.time() - t0:,.0f}s")


if __name__ == "__main__":
    main()
