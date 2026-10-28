-- ============================================================
-- GTM Signal Engine: Composite Scoring
-- ============================================================
-- Combines all three signals into a single 0-100 score per
-- company per day. The score tells a sales rep how "hot"
-- this account is for expansion/upsell.
--
-- Scoring weights (opinionated):
--   Usage Spike:      40 points (highest - urgency drives action)
--   Seat Crunch:      35 points (they'll be blocked without buying)
--   Feature Milestone: 25 points (strong but less urgent)
--
-- Multi-signal multiplier:
--   2 signals firing: score x 1.2
--   3 signals firing: score x 1.3
--   Capped at 100
--
-- Signal type label combines all active signals into a readable
-- string like "usage_spike + seat_crunch" for CRM display.
-- ============================================================

WITH rolling_metrics AS (
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
),

signal_flags AS (
    SELECT
        *,

        -- Individual signal flags (TRUE/FALSE)
        (dau_7d_avg > 0 AND daily_active_users > dau_7d_avg * 2) AS has_usage_spike,
        (seat_utilization_pct > 80) AS has_seat_crunch,
        (max_features_cumulative >= 10) AS has_feature_milestone,

        -- Spike ratio for display
        CASE
            WHEN dau_7d_avg > 0
            THEN ROUND(daily_active_users / dau_7d_avg, 2)
            ELSE 0
        END AS spike_ratio,

        -- Count of signals firing
        (CASE WHEN dau_7d_avg > 0 AND daily_active_users > dau_7d_avg * 2 THEN 1 ELSE 0 END)
        + (CASE WHEN seat_utilization_pct > 80 THEN 1 ELSE 0 END)
        + (CASE WHEN max_features_cumulative >= 10 THEN 1 ELSE 0 END)
        AS signals_firing

    FROM rolling_metrics
),

raw_scores AS (
    SELECT
        *,

        -- Base score from individual signals (weighted)
        (CASE WHEN has_usage_spike THEN 40 ELSE 0 END)
        + (CASE WHEN has_seat_crunch THEN 35 ELSE 0 END)
        + (CASE WHEN has_feature_milestone THEN 25 ELSE 0 END)
        AS base_score,

        -- Multi-signal multiplier
        CASE
            WHEN signals_firing >= 3 THEN 1.3
            WHEN signals_firing = 2 THEN 1.2
            ELSE 1.0
        END AS multiplier,

        -- Signal type label (for CRM and alerts)
        CONCAT(
            CASE WHEN dau_7d_avg > 0 AND daily_active_users > dau_7d_avg * 2 THEN 'usage_spike' ELSE '' END,
            CASE WHEN (dau_7d_avg > 0 AND daily_active_users > dau_7d_avg * 2) AND seat_utilization_pct > 80 THEN ' + ' ELSE '' END,
            CASE WHEN seat_utilization_pct > 80 THEN 'seat_crunch' ELSE '' END,
            CASE WHEN ((dau_7d_avg > 0 AND daily_active_users > dau_7d_avg * 2) OR seat_utilization_pct > 80) AND max_features_cumulative >= 10 THEN ' + ' ELSE '' END,
            CASE WHEN max_features_cumulative >= 10 THEN 'feature_milestone' ELSE '' END
        ) AS signal_type

    FROM signal_flags
)

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
    dau_7d_avg,
    api_calls_7d_avg,
    seat_utilization_pct,
    max_features_cumulative,
    has_usage_spike,
    has_seat_crunch,
    has_feature_milestone,
    spike_ratio,
    signals_firing,
    base_score,
    multiplier,
    signal_type,

    -- Final composite score (capped at 100)
    LEAST(100, CAST(ROUND(base_score * multiplier) AS INT64)) AS signal_score,

    -- Tier classification
    CASE
        WHEN LEAST(100, CAST(ROUND(base_score * multiplier) AS INT64)) >= 85 THEN 'CRITICAL'
        WHEN LEAST(100, CAST(ROUND(base_score * multiplier) AS INT64)) >= 70 THEN 'HOT'
        WHEN LEAST(100, CAST(ROUND(base_score * multiplier) AS INT64)) >= 50 THEN 'WARM'
        ELSE 'COLD'
    END AS signal_tier

FROM raw_scores
ORDER BY company_id, event_date;
