-- ============================================================
-- GTM Signal Engine: Rolling Averages
-- ============================================================
-- Calculates 7-day and 14-day rolling averages for each company
-- using SQL window functions. These averages become the baseline
-- against which we detect usage spikes.
--
-- Window function pattern:
--   AVG(column) OVER (
--     PARTITION BY company_id        -- calculate per company
--     ORDER BY event_date            -- in date order
--     ROWS BETWEEN 6 PRECEDING AND CURRENT ROW  -- last 7 days
--   )
-- ============================================================

SELECT
    company_id,
    company_name,
    event_date,
    plan_type,
    mrr,
    signup_date,

    -- Raw daily metrics
    daily_active_users,
    features_used,
    api_calls,
    seats_purchased,
    seats_used,

    -- 7-day rolling averages
    ROUND(AVG(daily_active_users) OVER (
        PARTITION BY company_id
        ORDER BY event_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 1) AS dau_7d_avg,

    ROUND(AVG(api_calls) OVER (
        PARTITION BY company_id
        ORDER BY event_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 1) AS api_calls_7d_avg,

    ROUND(AVG(features_used) OVER (
        PARTITION BY company_id
        ORDER BY event_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 1) AS features_7d_avg,

    -- 14-day rolling averages (for trend comparison)
    ROUND(AVG(daily_active_users) OVER (
        PARTITION BY company_id
        ORDER BY event_date
        ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
    ), 1) AS dau_14d_avg,

    ROUND(AVG(api_calls) OVER (
        PARTITION BY company_id
        ORDER BY event_date
        ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
    ), 1) AS api_calls_14d_avg,

    -- Max features ever used (cumulative, for milestone tracking)
    MAX(features_used) OVER (
        PARTITION BY company_id
        ORDER BY event_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS max_features_cumulative,

    -- Seat utilization percentage
    ROUND(SAFE_DIVIDE(seats_used, seats_purchased) * 100, 1) AS seat_utilization_pct

FROM
    `{PROJECT_ID}.gtm_signals.usage_events`
ORDER BY
    company_id, event_date;
