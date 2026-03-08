-- Market summary per municipality — the most frequently queried view
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_market_summary AS
SELECT
    al2.id AS l2_id,
    al2.country_code,
    al2.code AS municipality_code,
    al2.name AS municipality_name,
    al1.abbrev AS state_abbrev,
    al2.centroid,
    -- Latest subscriber data
    latest.year_month,
    COALESCE(latest.total_subscribers, 0) AS total_subscribers,
    COALESCE(latest.fiber_subscribers, 0) AS fiber_subscribers,
    COALESCE(latest.provider_count, 0) AS provider_count,
    -- Demographics (aggregated from tracts)
    demos.total_households,
    demos.total_population,
    demos.avg_income,
    -- Computed metrics
    CASE WHEN demos.total_households > 0
         THEN ROUND(COALESCE(latest.total_subscribers, 0)::NUMERIC / demos.total_households * 100, 1)
         ELSE 0 END AS broadband_penetration_pct,
    CASE WHEN COALESCE(latest.total_subscribers, 0) > 0
         THEN ROUND(COALESCE(latest.fiber_subscribers, 0)::NUMERIC / latest.total_subscribers * 100, 1)
         ELSE 0 END AS fiber_share_pct
FROM admin_level_2 al2
JOIN admin_level_1 al1 ON al2.l1_id = al1.id
LEFT JOIN LATERAL (
    SELECT
        SUM(cd.total_households) AS total_households,
        SUM(cd.total_population) AS total_population,
        AVG((cd.income_data->>'avg_per_capita_brl')::NUMERIC) AS avg_income
    FROM census_tracts ct
    JOIN census_demographics cd ON cd.tract_id = ct.id
    WHERE ct.l2_id = al2.id
) demos ON TRUE
LEFT JOIN LATERAL (
    SELECT
        bs.year_month,
        SUM(bs.subscribers) AS total_subscribers,
        SUM(CASE WHEN bs.technology = 'fiber' THEN bs.subscribers ELSE 0 END) AS fiber_subscribers,
        COUNT(DISTINCT bs.provider_id) AS provider_count
    FROM broadband_subscribers bs
    WHERE bs.l2_id = al2.id
    AND bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers WHERE l2_id = al2.id)
    GROUP BY bs.year_month
) latest ON TRUE;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mvms_l2 ON mv_market_summary(l2_id);
CREATE INDEX IF NOT EXISTS idx_mvms_geom ON mv_market_summary USING GIST(centroid);
CREATE INDEX IF NOT EXISTS idx_mvms_country ON mv_market_summary(country_code);
