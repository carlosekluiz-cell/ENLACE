"""
Seed data script for ENLACE platform.

Populates the database with realistic Brazilian telecommunications data:
- 27 Brazilian states (admin_level_1) with real IBGE codes
- 40+ municipalities (admin_level_2) with real coordinates and demographics
- Census tracts (5 per municipality: 3 urban, 2 rural)
- Census demographics with income bracket data
- 20 telecom providers (Big 4, regional, small ISPs)
- 12 months of broadband subscriber data per municipality
- Base stations with realistic technology/frequency configurations
- Colombia test data for multi-country validation

Usage:
    source /home/dev/enlace/.venv/bin/activate
    python data/scripts/seed_data.py

Idempotent: uses ON CONFLICT DO NOTHING where possible, and deletes
broadband/base station rows before re-inserting to allow safe re-runs.
"""

import psycopg2
import random
import json
import sys

DB_URL = "postgresql://enlace:enlace_dev_2026@localhost:5432/enlace"

random.seed(42)  # Reproducible results

# ---------------------------------------------------------------------------
# 1. Brazilian states — all 27 UFs with real IBGE codes
# ---------------------------------------------------------------------------
STATES = [
    ("11", "Rondônia", "RO"),
    ("12", "Acre", "AC"),
    ("13", "Amazonas", "AM"),
    ("14", "Roraima", "RR"),
    ("15", "Pará", "PA"),
    ("16", "Amapá", "AP"),
    ("17", "Tocantins", "TO"),
    ("21", "Maranhão", "MA"),
    ("22", "Piauí", "PI"),
    ("23", "Ceará", "CE"),
    ("24", "Rio Grande do Norte", "RN"),
    ("25", "Paraíba", "PB"),
    ("26", "Pernambuco", "PE"),
    ("27", "Alagoas", "AL"),
    ("28", "Sergipe", "SE"),
    ("29", "Bahia", "BA"),
    ("31", "Minas Gerais", "MG"),
    ("32", "Espírito Santo", "ES"),
    ("33", "Rio de Janeiro", "RJ"),
    ("35", "São Paulo", "SP"),
    ("41", "Paraná", "PR"),
    ("42", "Santa Catarina", "SC"),
    ("43", "Rio Grande do Sul", "RS"),
    ("50", "Mato Grosso do Sul", "MS"),
    ("51", "Mato Grosso", "MT"),
    ("52", "Goiás", "GO"),
    ("53", "Distrito Federal", "DF"),
]

# ---------------------------------------------------------------------------
# 2. Municipalities — 45 real municipalities with IBGE codes and coordinates
#    (code, name, state_code, lat, lon, population, households)
# ---------------------------------------------------------------------------
MUNICIPALITIES = [
    # São Paulo (SP - 35)
    ("3550308", "São Paulo", "35", -23.5505, -46.6333, 12325232, 4110000),
    ("3509502", "Campinas", "35", -22.9099, -47.0626, 1223237, 407000),
    ("3518800", "Guarulhos", "35", -23.4628, -46.5333, 1392121, 464000),
    ("3543402", "Ribeirão Preto", "35", -21.1704, -47.8103, 711825, 237000),
    ("3552205", "Sorocaba", "35", -23.5015, -47.4526, 687357, 229000),
    ("3548500", "Santos", "35", -23.9608, -46.3336, 433656, 163000),
    ("3547809", "São Bernardo do Campo", "35", -23.6914, -46.5646, 844483, 281000),
    ("3534401", "Osasco", "35", -23.5325, -46.7917, 699944, 233000),
    # Rio de Janeiro (RJ - 33)
    ("3304557", "Rio de Janeiro", "33", -22.9068, -43.1729, 6748000, 2382000),
    ("3303302", "Niterói", "33", -22.8833, -43.1036, 515317, 189000),
    ("3301702", "Duque de Caxias", "33", -22.7856, -43.3117, 924624, 308000),
    ("3304904", "São Gonçalo", "33", -22.8269, -43.0634, 1091737, 363000),
    # Minas Gerais (MG - 31)
    ("3106200", "Belo Horizonte", "31", -19.9167, -43.9345, 2521564, 840000),
    ("3170206", "Uberlândia", "31", -18.9186, -48.2773, 699097, 233000),
    ("3136702", "Juiz de Fora", "31", -21.7642, -43.3503, 573285, 191000),
    ("3106705", "Betim", "31", -19.9678, -44.1983, 444784, 148000),
    # Paraná (PR - 41)
    ("4106902", "Curitiba", "41", -25.4284, -49.2733, 1963726, 717000),
    ("4113700", "Londrina", "41", -23.3045, -51.1696, 580870, 193000),
    ("4115200", "Maringá", "41", -23.4205, -51.9333, 436472, 145000),
    # Santa Catarina (SC - 42)
    ("4205407", "Florianópolis", "42", -27.5954, -48.5480, 508826, 195000),
    ("4209102", "Joinville", "42", -26.3045, -48.8487, 597658, 199000),
    ("4202404", "Blumenau", "42", -26.9194, -49.0661, 361855, 121000),
    # Rio Grande do Sul (RS - 43)
    ("4314902", "Porto Alegre", "43", -30.0346, -51.2177, 1492530, 538000),
    ("4305108", "Caxias do Sul", "43", -29.1681, -51.1794, 517451, 187000),
    # Bahia (BA - 29)
    ("2927408", "Salvador", "29", -12.9711, -38.5108, 2886698, 987000),
    ("2910800", "Feira de Santana", "29", -12.2669, -38.9666, 619609, 206000),
    ("2933307", "Vitória da Conquista", "29", -14.8619, -40.8444, 343230, 114000),
    # Ceará (CE - 23)
    ("2304400", "Fortaleza", "23", -3.7172, -38.5433, 2686612, 862000),
    ("2307304", "Juazeiro do Norte", "23", -7.2131, -39.3151, 278264, 92000),
    # Pernambuco (PE - 26)
    ("2611606", "Recife", "26", -8.0476, -34.8770, 1661681, 567000),
    ("2607901", "Jaboatão dos Guararapes", "26", -8.1130, -35.0156, 706867, 235000),
    # Pará (PA - 15)
    ("1501402", "Belém", "15", -1.4558, -48.5024, 1506420, 468000),
    ("1504208", "Marabá", "15", -5.3686, -49.1178, 283542, 94000),
    # Amazonas (AM - 13)
    ("1302603", "Manaus", "13", -3.1190, -60.0217, 2255903, 680000),
    # Goiás (GO - 52)
    ("5208707", "Goiânia", "52", -16.6869, -49.2648, 1555626, 555000),
    ("5201108", "Anápolis", "52", -16.3281, -48.9530, 391772, 130000),
    # Distrito Federal (DF - 53)
    ("5300108", "Brasília", "53", -15.7975, -47.8919, 3094325, 1030000),
    # Mato Grosso (MT - 51)
    ("5103403", "Cuiabá", "51", -15.5989, -56.0949, 618124, 206000),
    # Mato Grosso do Sul (MS - 50)
    ("5002704", "Campo Grande", "50", -20.4697, -54.6201, 906092, 302000),
    # Maranhão (MA - 21)
    ("2111300", "São Luís", "21", -2.5297, -44.2825, 1115932, 355000),
    # Piauí (PI - 22)
    ("2211001", "Teresina", "22", -5.0892, -42.8019, 871126, 274000),
    # Rio Grande do Norte (RN - 24)
    ("2408102", "Natal", "24", -5.7945, -35.2110, 896708, 299000),
    # Paraíba (PB - 25)
    ("2507507", "João Pessoa", "25", -7.1195, -34.8450, 817511, 272000),
    # Alagoas (AL - 27)
    ("2704302", "Maceió", "27", -9.6658, -35.7353, 1025360, 341000),
    # Sergipe (SE - 28)
    ("2800308", "Aracaju", "28", -10.9091, -37.0677, 664908, 221000),
    # Espírito Santo (ES - 32)
    ("3205309", "Vitória", "32", -20.3155, -40.3128, 365855, 131000),
    # Rondônia (RO - 11)
    ("1100205", "Porto Velho", "11", -8.7612, -63.9004, 548952, 183000),
    # Tocantins (TO - 17)
    ("1721000", "Palmas", "17", -10.1689, -48.3317, 306296, 102000),
    # Roraima (RR - 14)
    ("1400100", "Boa Vista", "14", 2.8235, -60.6753, 436591, 145000),
    # Amapá (AP - 16)
    ("1600303", "Macapá", "16", 0.0349, -51.0694, 512902, 155000),
    # Acre (AC - 12)
    ("1200401", "Rio Branco", "12", -9.9747, -67.8100, 419452, 140000),
]

# ---------------------------------------------------------------------------
# 3. Providers — 20 telecom providers with real/realistic data
# ---------------------------------------------------------------------------
PROVIDERS = [
    # Big 4
    ("Claro S.A.", "claro", "40.432.544/0001-47", "PGP", ["SCM", "SMP", "SeAC"]),
    ("Telefônica Brasil S.A. (Vivo)", "vivo", "02.558.157/0001-62", "PGP", ["SCM", "SMP", "SeAC"]),
    ("Oi S.A.", "oi", "76.535.764/0001-43", "PGP", ["SCM", "SMP", "SeAC"]),
    ("TIM S.A.", "tim", "04.206.050/0001-80", "PGP", ["SCM", "SMP"]),
    # Regional
    ("Algar Telecom S.A.", "algar telecom", "71.208.516/0001-74", "PMP", ["SCM", "SMP"]),
    ("Brisanet Serviços de Telecomunicações S.A.", "brisanet", "04.601.397/0001-28", "PMP", ["SCM"]),
    ("Desktop - Sigmanet Comunicação Multimídia Ltda.", "desktop", "08.250.407/0001-34", "PMP", ["SCM"]),
    ("Unifique Telecomunicações S.A.", "unifique", "02.255.187/0001-08", "PMP", ["SCM"]),
    ("Copel Telecomunicações S.A.", "copel telecom", "04.368.865/0001-66", "PMP", ["SCM"]),
    ("Sercomtel S.A. Telecomunicações", "sercomtel", "78.825.236/0001-09", "PMP", ["SCM"]),
    ("Sumicity Telecomunicações S.A.", "sumicity", "11.089.765/0001-02", "PMP", ["SCM"]),
    ("Americanet S.A.", "americanet", "02.093.552/0001-44", "PMP", ["SCM"]),
    ("Mob Serviços de Telecomunicações S.A.", "mob telecom", "22.160.527/0001-01", "PMP", ["SCM"]),
    ("Ligga Telecomunicações S.A.", "ligga", "01.738.945/0001-50", "PMP", ["SCM"]),
    # Small ISPs (fictional but realistic)
    ("NetConnect Telecomunicações Ltda.", "netconnect", "31.456.789/0001-01", "PPP", ["SCM"]),
    ("FibraMax Internet Ltda.", "fibramax", "32.567.890/0001-02", "PPP", ["SCM"]),
    ("VelozNet Provedor de Internet Ltda.", "veloznet", "33.678.901/0001-03", "PPP", ["SCM"]),
    ("TurboLink Telecomunicações Ltda.", "turbolink", "34.789.012/0001-04", "PPP", ["SCM"]),
    ("CerradoNet Serviços de Internet Ltda.", "cerradonet", "35.890.123/0001-05", "PPP", ["SCM"]),
    ("Pantanal Telecom Ltda.", "pantanal telecom", "36.901.234/0001-06", "PPP", ["SCM"]),
]

# Frequency/technology combos for base stations
BS_CONFIGS = [
    ("4G", 700, 10),
    ("4G", 850, 10),
    ("4G", 1800, 20),
    ("4G", 2100, 20),
    ("4G", 2600, 20),
    ("5G", 3500, 100),
    ("5G", 2300, 40),
    ("3G", 850, 5),
    ("3G", 2100, 5),
]


def main():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("=" * 60)
        print("ENLACE Seed Data Script")
        print("=" * 60)

        # ------------------------------------------------------------------
        # Step 1: Insert Brazilian states
        # ------------------------------------------------------------------
        print("\n[1/8] Inserting 27 Brazilian states...")
        for code, name, abbrev in STATES:
            cur.execute(
                """
                INSERT INTO admin_level_1 (country_code, code, name, abbrev)
                VALUES ('BR', %s, %s, %s)
                ON CONFLICT (country_code, code) DO NOTHING
                """,
                (code, name, abbrev),
            )
        conn.commit()
        cur.execute("SELECT count(*) FROM admin_level_1 WHERE country_code='BR'")
        print(f"   -> {cur.fetchone()[0]} states in database")

        # ------------------------------------------------------------------
        # Step 2: Insert municipalities
        # ------------------------------------------------------------------
        print("\n[2/8] Inserting municipalities...")

        # Build state code -> l1 id mapping
        cur.execute("SELECT id, code FROM admin_level_1 WHERE country_code='BR'")
        state_map = {row[1].strip(): row[0] for row in cur.fetchall()}

        for code, name, state_code, lat, lon, pop, hh in MUNICIPALITIES:
            l1_id = state_map.get(state_code)
            if l1_id is None:
                print(f"   WARNING: state code {state_code} not found for {name}")
                continue
            cur.execute(
                """
                INSERT INTO admin_level_2 (country_code, l1_id, code, name, centroid)
                VALUES ('BR', %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                ON CONFLICT (country_code, code) DO NOTHING
                """,
                (l1_id, code, name, lon, lat),
            )
        conn.commit()
        cur.execute("SELECT count(*) FROM admin_level_2 WHERE country_code='BR'")
        print(f"   -> {cur.fetchone()[0]} municipalities in database")

        # ------------------------------------------------------------------
        # Step 3: Insert census tracts
        # ------------------------------------------------------------------
        print("\n[3/8] Inserting census tracts...")

        # Build municipality data lookup
        cur.execute("SELECT id, code FROM admin_level_2 WHERE country_code='BR'")
        muni_db_rows = {row[1].strip(): row[0] for row in cur.fetchall()}

        # Build municipality info dict: code -> (pop, hh, lat, lon)
        muni_info = {}
        for code, name, state_code, lat, lon, pop, hh in MUNICIPALITIES:
            muni_info[code] = (pop, hh, lat, lon, name)

        tract_count = 0
        for muni_code, l2_id in muni_db_rows.items():
            info = muni_info.get(muni_code)
            if info is None:
                continue
            pop, hh, lat, lon, mname = info

            for i in range(5):
                # Generate 15-digit tract code: municipality code (7) + sequential (8)
                tract_code = f"{muni_code}{(i + 1):08d}"

                # 3 urban (situation 1), 2 rural (situation 2)
                situation = "1" if i < 3 else "2"
                tract_type = "urban" if i < 3 else "rural"

                # Small offset for tract centroid
                t_lat = lat + random.uniform(-0.02, 0.02)
                t_lon = lon + random.uniform(-0.02, 0.02)

                cur.execute(
                    """
                    INSERT INTO census_tracts
                        (country_code, l2_id, code, situation, tract_type,
                         centroid)
                    VALUES ('BR', %s, %s, %s, %s,
                            ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                    ON CONFLICT (country_code, code) DO NOTHING
                    """,
                    (l2_id, tract_code, situation, tract_type, t_lon, t_lat),
                )
                tract_count += 1

        conn.commit()
        cur.execute("SELECT count(*) FROM census_tracts WHERE country_code='BR'")
        print(f"   -> {cur.fetchone()[0]} census tracts in database")

        # ------------------------------------------------------------------
        # Step 4: Insert census demographics
        # ------------------------------------------------------------------
        print("\n[4/8] Inserting census demographics...")

        cur.execute(
            """
            SELECT ct.id, ct.code, ct.l2_id, ct.situation
            FROM census_tracts ct
            WHERE ct.country_code = 'BR'
            """
        )
        tract_rows = cur.fetchall()

        # Group tracts by municipality
        tracts_by_muni = {}
        for tid, tcode, l2_id, situation in tract_rows:
            muni_code = tcode[:7]
            if muni_code not in tracts_by_muni:
                tracts_by_muni[muni_code] = []
            tracts_by_muni[muni_code].append((tid, tcode, situation))

        demo_count = 0
        for muni_code, tracts in tracts_by_muni.items():
            info = muni_info.get(muni_code)
            if info is None:
                continue
            total_pop, total_hh, _, _, _ = info

            # Distribute population among tracts with some variance
            n = len(tracts)
            weights = [random.uniform(0.8, 1.2) for _ in range(n)]
            total_w = sum(weights)

            for idx, (tid, tcode, situation) in enumerate(tracts):
                frac = weights[idx] / total_w
                t_pop = max(100, int(total_pop * frac))
                t_hh = max(30, int(total_hh * frac))
                t_occ = int(t_hh * random.uniform(0.88, 0.96))
                avg_res = round(t_pop / max(t_hh, 1), 2)
                avg_res = min(avg_res, 9.99)  # fits numeric(4,2)

                # Income data — urban tracts richer on average
                if situation and situation.strip() == "1":
                    avg_income = random.uniform(1800, 5000)
                else:
                    avg_income = random.uniform(800, 2200)
                median_income = avg_income * random.uniform(0.65, 0.85)

                # Income brackets (must sum to ~100%)
                if avg_income > 3000:
                    brackets = {
                        "below_half_min_wage": round(random.uniform(3, 8), 1),
                        "half_to_one_min_wage": round(random.uniform(8, 15), 1),
                        "one_to_two_min_wage": round(random.uniform(18, 28), 1),
                        "two_to_five_min_wage": round(random.uniform(25, 35), 1),
                        "five_to_ten_min_wage": round(random.uniform(12, 20), 1),
                        "above_ten_min_wage": round(random.uniform(5, 15), 1),
                    }
                elif avg_income > 1500:
                    brackets = {
                        "below_half_min_wage": round(random.uniform(8, 18), 1),
                        "half_to_one_min_wage": round(random.uniform(15, 25), 1),
                        "one_to_two_min_wage": round(random.uniform(25, 35), 1),
                        "two_to_five_min_wage": round(random.uniform(15, 25), 1),
                        "five_to_ten_min_wage": round(random.uniform(3, 10), 1),
                        "above_ten_min_wage": round(random.uniform(1, 5), 1),
                    }
                else:
                    brackets = {
                        "below_half_min_wage": round(random.uniform(18, 35), 1),
                        "half_to_one_min_wage": round(random.uniform(22, 35), 1),
                        "one_to_two_min_wage": round(random.uniform(18, 28), 1),
                        "two_to_five_min_wage": round(random.uniform(5, 15), 1),
                        "five_to_ten_min_wage": round(random.uniform(1, 5), 1),
                        "above_ten_min_wage": round(random.uniform(0.5, 2), 1),
                    }

                income_data = {
                    "avg_per_capita_brl": round(avg_income, 2),
                    "median_per_capita_brl": round(median_income, 2),
                    **brackets,
                }

                cur.execute(
                    """
                    INSERT INTO census_demographics
                        (tract_id, census_year, total_population,
                         total_households, occupied_households,
                         avg_residents_per_household, income_data)
                    VALUES (%s, 2022, %s, %s, %s, %s, %s)
                    ON CONFLICT (tract_id, census_year) DO NOTHING
                    """,
                    (
                        tid,
                        t_pop,
                        t_hh,
                        t_occ,
                        avg_res,
                        json.dumps(income_data),
                    ),
                )
                demo_count += 1

        conn.commit()
        cur.execute("SELECT count(*) FROM census_demographics")
        print(f"   -> {cur.fetchone()[0]} demographic records in database")

        # ------------------------------------------------------------------
        # Step 5: Insert providers
        # ------------------------------------------------------------------
        print("\n[5/8] Inserting 20 telecom providers...")

        for name, name_norm, cnpj, classification, services in PROVIDERS:
            # Check if provider already exists by national_id (CNPJ)
            cur.execute(
                "SELECT id FROM providers "
                "WHERE country_code='BR' AND national_id = %s",
                (cnpj,),
            )
            if cur.fetchone() is not None:
                continue
            cur.execute(
                """
                INSERT INTO providers
                    (country_code, name, name_normalized, national_id,
                     classification, services, status, first_seen_date)
                VALUES ('BR', %s, %s, %s, %s, %s, 'active', '2020-01-01')
                """,
                (name, name_norm, cnpj, classification, json.dumps(services)),
            )
        conn.commit()
        cur.execute("SELECT count(*) FROM providers WHERE country_code='BR'")
        print(f"   -> {cur.fetchone()[0]} providers in database")

        # ------------------------------------------------------------------
        # Step 6: Broadband subscribers
        # ------------------------------------------------------------------
        print("\n[6/8] Inserting broadband subscriber data (12 months)...")

        # Clear existing to allow re-runs (no natural unique constraint)
        cur.execute("DELETE FROM broadband_subscribers")
        conn.commit()

        cur.execute("SELECT id FROM providers WHERE country_code='BR'")
        provider_ids = [r[0] for r in cur.fetchall()]

        cur.execute("SELECT id, code FROM admin_level_2 WHERE country_code='BR'")
        muni_rows = cur.fetchall()

        technologies = ["fiber", "cable", "dsl", "wireless"]
        months = [f"2025-{m:02d}" for m in range(1, 13)]

        sub_row_count = 0
        for l2_id, muni_code in muni_rows:
            info = muni_info.get(muni_code.strip())
            if info is None:
                continue
            pop, total_hh, _, _, _ = info

            # Each municipality gets 2-6 providers
            n_providers = random.randint(2, min(6, len(provider_ids)))
            chosen_providers = random.sample(provider_ids, n_providers)

            # Budget: total subscribers across all providers must not exceed
            # total_hh. Allocate a household penetration rate (40-85%).
            penetration = random.uniform(0.40, 0.85)
            max_subs = int(total_hh * penetration)

            # Divide among providers with random weights
            prov_weights = [random.uniform(0.5, 2.0) for _ in range(n_providers)]
            total_w = sum(prov_weights)
            prov_allocs = [
                max(50, int(max_subs * w / total_w)) for w in prov_weights
            ]
            # Clamp total
            while sum(prov_allocs) > max_subs:
                idx = random.randint(0, n_providers - 1)
                if prov_allocs[idx] > 100:
                    prov_allocs[idx] -= 50

            for p_idx, prov_id in enumerate(chosen_providers):
                base_subs = prov_allocs[p_idx]
                tech = random.choice(technologies)

                for ym in months:
                    # Slight monthly growth (0.2% - 1.5% per month)
                    month_num = int(ym.split("-")[1])
                    growth = 1 + (month_num - 1) * random.uniform(0.002, 0.015)
                    subs = max(50, int(base_subs * growth))

                    cur.execute(
                        """
                        INSERT INTO broadband_subscribers
                            (provider_id, l2_id, year_month, technology,
                             subscribers)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (prov_id, l2_id, ym, tech, subs),
                    )
                    sub_row_count += 1

        conn.commit()
        cur.execute("SELECT count(*) FROM broadband_subscribers")
        print(f"   -> {cur.fetchone()[0]} subscriber rows in database")

        # ------------------------------------------------------------------
        # Step 7: Base stations (first 20 municipalities)
        # ------------------------------------------------------------------
        print("\n[7/8] Inserting base stations...")

        # Clear existing to allow re-runs
        cur.execute("DELETE FROM base_stations")
        conn.commit()

        # Use top 5 providers (Big 4 + Algar) for base stations
        cur.execute(
            """
            SELECT id FROM providers
            WHERE country_code='BR'
            ORDER BY id
            LIMIT 5
            """
        )
        bs_provider_ids = [r[0] for r in cur.fetchall()]

        # First 20 municipalities
        first_20_munis = MUNICIPALITIES[:20]
        bs_count = 0
        station_seq = 1

        for code, name, state_code, lat, lon, pop, hh in first_20_munis:
            l2_id = muni_db_rows.get(code)
            if l2_id is None:
                continue

            # Number of stations proportional to population
            if pop > 5000000:
                n_stations = 15
            elif pop > 1000000:
                n_stations = 10
            elif pop > 500000:
                n_stations = 7
            else:
                n_stations = random.randint(3, 5)

            for _ in range(n_stations):
                prov_id = random.choice(bs_provider_ids)
                tech, freq, bw = random.choice(BS_CONFIGS)
                s_lat = lat + random.uniform(-0.05, 0.05)
                s_lon = lon + random.uniform(-0.05, 0.05)
                station_id = f"BS-{station_seq:06d}"
                station_seq += 1

                antenna_h = random.uniform(15, 60)
                azimuth = random.choice([0, 60, 120, 180, 240, 300])
                mech_tilt = random.uniform(0, 8)
                power = random.uniform(10, 60)

                cur.execute(
                    """
                    INSERT INTO base_stations
                        (country_code, provider_id, station_id,
                         geom, latitude, longitude,
                         technology, frequency_mhz, bandwidth_mhz,
                         antenna_height_m, azimuth_degrees,
                         mechanical_tilt, power_watts,
                         authorization_date, status)
                    VALUES ('BR', %s, %s,
                            ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                            %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            '2023-01-15', 'active')
                    """,
                    (
                        prov_id,
                        station_id,
                        s_lon,
                        s_lat,
                        s_lat,
                        s_lon,
                        tech,
                        freq,
                        bw,
                        round(antenna_h, 1),
                        azimuth,
                        round(mech_tilt, 1),
                        round(power, 1),
                    ),
                )
                bs_count += 1

        conn.commit()
        cur.execute("SELECT count(*) FROM base_stations")
        print(f"   -> {cur.fetchone()[0]} base stations in database")

        # ------------------------------------------------------------------
        # Step 8: Colombia test data
        # ------------------------------------------------------------------
        print("\n[8/8] Inserting Colombia test data...")

        cur.execute(
            """
            INSERT INTO countries
                (code, name, name_local, currency_code, language_code,
                 regulator_name, regulator_url, national_crs, timezone)
            VALUES ('CO', 'Colombia', 'Colombia', 'COP', 'es-CO',
                    'CRC', 'https://www.crcom.gov.co', 3116,
                    'America/Bogota')
            ON CONFLICT (code) DO NOTHING
            """
        )

        cur.execute(
            """
            INSERT INTO admin_level_1 (country_code, code, name, abbrev)
            VALUES ('CO', '11', 'Bogotá D.C.', 'DC')
            ON CONFLICT (country_code, code) DO NOTHING
            RETURNING id
            """
        )
        row = cur.fetchone()
        if row:
            co_l1_id = row[0]
        else:
            cur.execute(
                "SELECT id FROM admin_level_1 "
                "WHERE country_code='CO' AND code='11'"
            )
            co_l1_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO admin_level_2
                (country_code, l1_id, code, name,
                 centroid)
            VALUES ('CO', %s, '11001', 'Bogotá',
                    ST_SetSRID(ST_MakePoint(-74.0721, 4.7110), 4326))
            ON CONFLICT (country_code, code) DO NOTHING
            """,
            (co_l1_id,),
        )
        conn.commit()

        cur.execute(
            "SELECT count(*) FROM admin_level_1 WHERE country_code='CO'"
        )
        print(f"   -> {cur.fetchone()[0]} Colombia admin_level_1 records")
        cur.execute(
            "SELECT count(*) FROM admin_level_2 WHERE country_code='CO'"
        )
        print(f"   -> {cur.fetchone()[0]} Colombia admin_level_2 records")

        # ------------------------------------------------------------------
        # Verification
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        cur.execute(
            """
            SELECT 'states' as t, count(*) FROM admin_level_1
                WHERE country_code='BR'
            UNION ALL
            SELECT 'municipalities', count(*) FROM admin_level_2
                WHERE country_code='BR'
            UNION ALL
            SELECT 'tracts', count(*) FROM census_tracts
                WHERE country_code='BR'
            UNION ALL
            SELECT 'demographics', count(*) FROM census_demographics
            UNION ALL
            SELECT 'providers', count(*) FROM providers
                WHERE country_code='BR'
            UNION ALL
            SELECT 'subscriber_rows', count(*) FROM broadband_subscribers
            UNION ALL
            SELECT 'base_stations', count(*) FROM base_stations
            UNION ALL
            SELECT 'colombia_l1', count(*) FROM admin_level_1
                WHERE country_code='CO'
            """
        )
        results = cur.fetchall()
        for label, count in results:
            label = label.strip()
            print(f"   {label:20s} {count:>8,d}")

        # Sanity check: subscribers <= households per municipality
        cur.execute(
            """
            WITH muni_subs AS (
                SELECT l2_id, year_month,
                       SUM(subscribers) as total_subs
                FROM broadband_subscribers
                GROUP BY l2_id, year_month
            ),
            muni_hh AS (
                SELECT ct.l2_id,
                       SUM(cd.total_households) as total_hh
                FROM census_tracts ct
                JOIN census_demographics cd ON cd.tract_id = ct.id
                GROUP BY ct.l2_id
            )
            SELECT count(*)
            FROM muni_subs ms
            JOIN muni_hh mh ON ms.l2_id = mh.l2_id
            WHERE ms.total_subs > mh.total_hh
            """
        )
        violations = cur.fetchone()[0]
        if violations > 0:
            print(
                f"\n   WARNING: {violations} month-municipality combos "
                "have subscribers > households"
            )
        else:
            print("\n   OK: No municipality exceeds household count")

        print("\nSeed data complete!")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}", file=sys.stderr)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
