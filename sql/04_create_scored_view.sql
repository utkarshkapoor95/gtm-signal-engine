-- ============================================================
-- GTM Signal Engine: Scored Signals View
-- ============================================================
-- Creates a BigQuery VIEW that always shows the LATEST scored
-- signal per company. This is what the n8n workflow polls
-- every 4 hours.
--
-- The view uses ROW_NUMBER() to pick only the most recent day
-- per company, so n8n always gets one row per company with
-- their current score and tier.
--
-- IMPORTANT: Replace {PROJECT_ID} with your actual GCP project
-- ID before running this in BigQuery Console.
--
-- After creating this view, n8n queries:
--   SELECT * FROM `{PROJECT_ID}.gtm_signals.scored_signals`
--   WHERE signal_score >= 50
--   ORDER BY signal_score DESC
-- ============================================================

CREATE OR REPLACE VIEW `{PROJECT_ID}.gtm_signals.scored_signals` AS

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
        (dau_7d_avg > 0 AND daily_active_users > dau_7d_avg * 2) AS has_usage_spike,
        (seat_utilization_pct > 80) AS has_seat_crunch,
        (max_features_cumulative >= 10) AS has_feature_milestone,

        CASE
            WHEN dau_7d_avg > 0
            THEN ROUND(daily_active_users / dau_7d_avg, 2)
            ELSE 0
        END AS spike_ratio,

        (CASE WHEN dau_7d_avg > 0 AND daily_active_users > dau_7d_avg * 2 THEN 1 ELSE 0 END)
        + (CASE WHEN seat_utilization_pct > 80 THEN 1 ELSE 0 END)
        + (CASE WHEN max_features_cumulative >= 10 THEN 1 ELSE 0 END)
        AS signals_firing

    FROM rolling_metrics
),

scored AS (
    SELECT
        *,

        -- Base score
        (CASE WHEN has_usage_spike THEN 40 ELSE 0 END)
        + (CASE WHEN has_seat_crunch THEN 35 ELSE 0 END)
        + (CASE WHEN has_feature_milestone THEN 25 ELSE 0 END)
        AS base_score,

        -- Multiplier
        CASE
            WHEN (CASE WHEN dau_7d_avg > 0 AND daily_active_users > dau_7d_avg * 2 THEN 1 ELSE 0 END)
                 + (CASE WHEN seat_utilization_pct > 80 THEN 1 ELSE 0 END)
                 + (CASE WHEN max_features_cumulative >= 10 THEN 1 ELSE 0 END) >= 3 THEN 1.3
            WHEN (CASE WHEN dau_7d_avg > 0 AND daily_active_users > dau_7d_avg * 2 THEN 1 ELSE 0 END)
                 + (CASE WHEN seat_utilization_pct > 80 THEN 1 ELSE 0 END)
                 + (CASE WHEN max_features_cumulative >= 10 THEN 1 ELSE 0 END) = 2 THEN 1.2
            ELSE 1.0
        END AS multiplier,

        -- Signal type label
        CONCAT(
            CASE WHEN dau_7d_avg > 0 AND daily_active_users > dau_7d_avg * 2 THEN 'usage_spike' ELSE '' END,
            CASE WHEN (dau_7d_avg > 0 AND daily_active_users > dau_7d_avg * 2) AND seat_utilization_pct > 80 THEN ' + ' ELSE '' END,
            CASE WHEN seat_utilization_pct > 80 THEN 'seat_crunch' ELSE '' END,
            CASE WHEN ((dau_7d_avg > 0 AND daily_active_users > dau_7d_avg * 2) OR seat_utilization_pct > 80) AND max_features_cumulative >= 10 THEN ' + ' ELSE '' END,
            CASE WHEN max_features_cumulative >= 10 THEN 'feature_milestone' ELSE '' END
        ) AS signal_type

    FROM signal_flags
),

final_scored AS (
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
        seat_utilization_pct,
        max_features_cumulative,
        has_usage_spike,
        has_seat_crunch,
        has_feature_milestone,
        spike_ratio,
        signals_firing,
        signal_type,
        LEAST(100, CAST(ROUND(base_score * multiplier) AS INT64)) AS signal_score,
        CASE
            WHEN LEAST(100, CAST(ROUND(base_score * multiplier) AS INT64)) >= 85 THEN 'CRITICAL'
            WHEN LEAST(100, CAST(ROUND(base_score * multiplier) AS INT64)) >= 70 THEN 'HOT'
            WHEN LEAST(100, CAST(ROUND(base_score * multiplier) AS INT64)) >= 50 THEN 'WARM'
            ELSE 'COLD'
        END AS signal_tier,

        -- Pick only the most recent day per company
        ROW_NUMBER() OVER (
            PARTITION BY company_id
            ORDER BY event_date DESC
        ) AS row_num

    FROM scored
)

-- Return only the latest row per company
SELECT
    company_id,
    company_name,
    event_date AS last_signal_date,
    plan_type,
    mrr,
    signup_date,
    daily_active_users,
    features_used,
    api_calls,
    seats_purchased,
    seats_used,
    dau_7d_avg,
    seat_utilization_pct,
    max_features_cumulative,
    has_usage_spike,
    has_seat_crunch,
    has_feature_milestone,
    spike_ratio,
    signals_firing,
    signal_type,
    signal_score,
    signal_tier
FROM final_scored
WHERE row_num = 1;
