-- Phase 1 enrichment: tier-1 near-station composite prediction, field domain.
--
-- For each measurement attributed to a licensed station (<=2 km away),
-- predict total E-field as the incoherent sum over the station's carrier
-- bands: S_band = EIRP_typ(band) * ceil(carriers/3) / (4*pi*d^2)  [W/m^2]
-- (free-space power density; at these ranges — 92% < 500 m — our engine's
-- band-dispatched models sit on the FSPL floor, so this matches the engine)
-- E_pred = sqrt(377 * sum S)                                     [V/m]
-- residual_db = 20*log10(E_meas / E_pred)                        [dB]
--
-- Documented assumptions (labeled in rf_residuals.model):
--  * Typical per-carrier EIRP by band (registry omits station power):
--    700/850/900: 60 dBm; 1800/2100: 61; 2300/2500: 62; 3500: 65; else 60.
--  * One of ~3 sectors faces the probe: effective carriers = ceil(n/3).
--  * Distance floored at 20 m (near-field/geocoding guard).

SET statement_timeout = 0;

DELETE FROM rf_residuals WHERE model = 'composite_v1';

WITH station_pos AS (
  SELECT station_number, avg(lat) AS lat, avg(lon) AS lon
  FROM anatel_stations GROUP BY station_number
),
station_bands AS (
  SELECT station_number, band, count(*) AS carriers
  FROM anatel_stations
  WHERE situacao IS DISTINCT FROM 'Cancelada'
  GROUP BY station_number, band
),
band_power AS (
  SELECT band, carriers,
         station_number,
         -- typical EIRP in watts
         (CASE
            WHEN band IN ('700','850','900') THEN 1000.0
            WHEN band IN ('1800','2100') THEN 1258.9
            WHEN band IN ('2300','2500') THEN 1584.9
            WHEN band = '3500' THEN 3162.3
            ELSE 1000.0
          END) * ceil(carriers / 3.0) AS eirp_w
  FROM station_bands
),
station_eirp AS (
  SELECT station_number, sum(eirp_w) AS total_eirp_w
  FROM band_power GROUP BY station_number
),
scored AS (
  SELECT m.id,
         greatest(earth_distance(ll_to_earth(m.lat, m.lon),
                                 ll_to_earth(p.lat, p.lon)), 20.0) AS d,
         se.total_eirp_w,
         m.e_field_vm
  FROM rf_measurements m
  JOIN station_pos p  ON p.station_number = m.station_number
  JOIN station_eirp se ON se.station_number = m.station_number
  WHERE m.station_number IS NOT NULL
    AND m.e_field_vm >= 0.05
    AND earth_distance(ll_to_earth(m.lat, m.lon),
                       ll_to_earth(p.lat, p.lon)) <= 2000
)
INSERT INTO rf_residuals
  (measurement_id, predicted_dbm, residual_db, model, environment, clutter, distance_m)
SELECT id,
       -- predicted field expressed in dB(V/m) stored in predicted_dbm slot
       20 * log(sqrt(377.0 * total_eirp_w / (4 * pi() * d * d))),
       20 * log(e_field_vm / sqrt(377.0 * total_eirp_w / (4 * pi() * d * d))),
       'composite_v1', NULL, NULL, d
FROM scored
ON CONFLICT (measurement_id) DO NOTHING;

ANALYZE rf_residuals;
SELECT count(*) AS residuals,
       round(avg(residual_db)::numeric, 2) AS bias_db,
       round(stddev(residual_db)::numeric, 2) AS sigma_db,
       round(sqrt(avg(residual_db * residual_db))::numeric, 2) AS rmse_db
FROM rf_residuals WHERE model = 'composite_v1';
