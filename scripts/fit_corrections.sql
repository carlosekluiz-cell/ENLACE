-- Phase 2 calibration: fit per-environment log-distance correction curves
-- on an 80% split and persist the held-out (20%) evaluation.
-- Rerunnable: refits from the current rf_residuals contents.

SET statement_timeout = 0;

CREATE TABLE IF NOT EXISTS rf_correction_curves (
  environment VARCHAR(20) PRIMARY KEY,
  a DOUBLE PRECISION NOT NULL,
  b DOUBLE PRECISION NOT NULL,
  n BIGINT NOT NULL,
  fitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS rf_calibration_eval (
  environment VARCHAR(20) PRIMARY KEY,
  n_test BIGINT NOT NULL,
  rmse_before DOUBLE PRECISION NOT NULL,
  rmse_after DOUBLE PRECISION NOT NULL,
  sigma_after DOUBLE PRECISION NOT NULL,
  evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

TRUNCATE rf_correction_curves;
INSERT INTO rf_correction_curves (environment, a, b, n)
SELECT COALESCE(environment,'unknown'),
       regr_intercept(residual_db, log(distance_m)),
       regr_slope(residual_db, log(distance_m)),
       count(*)
FROM rf_residuals
WHERE model='composite_v1' AND distance_m > 0 AND measurement_id % 5 <> 0
GROUP BY 1;

TRUNCATE rf_calibration_eval;
INSERT INTO rf_calibration_eval
  (environment, n_test, rmse_before, rmse_after, sigma_after)
SELECT COALESCE(r.environment,'unknown'),
       count(*),
       sqrt(avg(r.residual_db^2)),
       sqrt(avg((r.residual_db - (c.a + c.b*log(r.distance_m)))^2)),
       stddev(r.residual_db - (c.a + c.b*log(r.distance_m)))
FROM rf_residuals r
JOIN rf_correction_curves c ON c.environment = COALESCE(r.environment,'unknown')
WHERE r.model='composite_v1' AND r.distance_m > 0 AND r.measurement_id % 5 = 0
GROUP BY 1;

SELECT e.environment, e.n_test,
       round(e.rmse_before::numeric,2) AS rmse_before,
       round(e.rmse_after::numeric,2) AS rmse_after
FROM rf_calibration_eval e ORDER BY e.n_test DESC;
