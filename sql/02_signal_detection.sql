-- ============================================================
-- GTM Signal Engine: Signal Detection
-- ============================================================
-- Detects three types of expansion signals per company per day:
--
-- 1. USAGE SPIKE: Today's DAU or API calls > 2x the 7-day avg
--    Means: Something changed. A new team adopted, a big project
--    started, or a manager told everyone to use the tool.
--
-- 2. SEAT CRUNCH: seats_used / seats_purchased > 80%
--    Means: They're about to run out of licenses. The next
--    person who needs access forces a plan upgrade.
--
-- 3. FEATURE MILESTONE: Company has used 10+ distinct features
--    Means: They're deeply embedded. Unlikely to churn.
--    Good candidate for upsell to a higher plan.
--
-- Uses a CTE (Common Table Expression) to first calculate
-- rolling averages, then detect signals on top of them.
-- ============================================================

WITH rolling_metrics AS (
    -- Step 1: Calculate rolling averages (same as 01_rolling_averages.sql)
    SELECT
        company_id,
        company_name,
        event_date,
        plan_type,
        mrr,
        signup_date,
        daily_active_users,
        features_used,
        api_calls,
        seats_purchased,
        seats_used,

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

        MAX(features_used) OVER (
            PARTITION BY company_id
            ORDER BY event_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS max_features_cumulative,

        ROUND(SAFE_DIVIDE(seats_used, seats_purchased) * 100, 1) AS seat_utilization_pct

    FROM
        `{PROJECT_ID}.gtm_signals.usage_events`
)

-- Step 2: Detect signals
SELECT
    *,

    -- Signal 1: Usage Spike
    -- DAU today is more than 2x the 7-day rolling average
    CASE
        WHEN dau_7d_avg > 0
             AND daily_active_users > (dau_7d_avg * 2)
        THEN TRUE
        ELSE FALSE
    END AS signal_usage_spike,

    -- How big is the spike? (ratio of today vs average)
    CASE
        WHEN dau_7d_avg > 0
        THEN ROUND(daily_active_users / dau_7d_avg, 2)
        ELSE 0
    END AS spike_ratio,

    -- Signal 2: Seat Crunch
    -- More than 80% of purchased seats are being used
    CASE
        WHEN seat_utilization_pct > 80
        THEN TRUE
        ELSE FALSE
    END AS signal_seat_crunch,

    -- Signal 3: Feature Milestone
    -- Company has used 10+ distinct features cumulatively
    CASE
        WHEN max_features_cumulative >= 10
        THEN TRUE
        ELSE FALSE
    END AS signal_feature_milestone,

    -- Count how many signals are firing simultaneously
    (CASE WHEN dau_7d_avg > 0 AND daily_active_users > (dau_7d_avg * 2) THEN 1 ELSE 0 END)
    + (CASE WHEN SAFE_DIVIDE(seats_used, seats_purchased) * 100 > 80 THEN 1 ELSE 0 END)
    + (CASE WHEN max_features_cumulative >= 10 THEN 1 ELSE 0 END)
    AS signals_firing

FROM rolling_metrics
ORDER BY company_id, event_date;
