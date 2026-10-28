"""
GTM Signal Engine - Synthetic Data Generator v2
=================================================
Generates VARIED B2B SaaS usage data for a fictional workflow
automation platform. Unlike v1 (uniform patterns), v2 deliberately
creates companies with different usage archetypes so the scored_signals
view produces accounts across CRITICAL, HOT, and COLD tiers.

Possible scored outcomes with current SQL weights (40/35/25, 1.2x/1.3x):
  - All 3 signals:        (40+35+25) * 1.3 = 130 -> 100  CRITICAL
  - spike + seat_crunch:  (40+35) * 1.2    = 90          CRITICAL
  - spike + milestone:    (40+25) * 1.2    = 78          HOT
  - crunch + milestone:   (35+25) * 1.2    = 72          HOT
  - Single signal only:   max 40                         COLD
  - No signals:           0                              COLD

Usage:
    pip install pandas faker
    python generate_data_v2.py

    Then upload usage_events.csv to BigQuery Console manually.
    (pyarrow not needed, no programmatic upload)

Author: Utkarsh Kapoor
"""

import random
from datetime import datetime, timedelta
from faker import Faker
import pandas as pd

# ============================================================
# CONFIGURATION
# ============================================================
NUM_COMPANIES = 75
NUM_DAYS = 90
START_DATE = datetime(2026, 7, 28)

fake = Faker()
Faker.seed(42)
random.seed(42)

# Plan details
PLAN_MRR = {"free": 0, "starter": 99, "pro": 299, "enterprise": 799}
PLAN_SEAT_LIMITS = {"free": 5, "starter": 15, "pro": 50, "enterprise": 200}

FEATURES = [
    "workflow_builder", "scheduler", "api_connector", "webhook_handler",
    "error_logger", "dashboard_analytics", "team_collaboration",
    "version_control", "template_library", "ai_node", "conditional_logic",
    "loop_iterator", "database_connector", "email_node", "slack_integration",
    "crm_connector", "file_processor", "http_request", "code_node",
    "approval_workflow"
]

# ============================================================
# COMPANY ARCHETYPES - Deliberately varied
# ============================================================
# Each archetype is designed to trigger specific signal combos
# in the SQL scoring view, producing a realistic tier spread.

ARCHETYPES = {
    "triple_threat": {
        "description": "All 3 signals fire -> score 100, CRITICAL",
        "count": 5,
        "plan_weights": [0.0, 0.1, 0.4, 0.5],
        "seat_fill": (0.85, 0.98),
        "dau_spike": True,
        "spike_day_range": (60, 80),
        "feature_discovery_rate": 0.20,
        "base_features": 5,
    },
    "spike_and_crunch": {
        "description": "Usage spike + seat crunch -> score 90, CRITICAL",
        "count": 6,
        "plan_weights": [0.1, 0.3, 0.4, 0.2],
        "seat_fill": (0.83, 0.95),
        "dau_spike": True,
        "spike_day_range": (50, 75),
        "feature_discovery_rate": 0.05,
        "base_features": 3,
    },
    "spike_and_features": {
        "description": "Usage spike + feature milestone -> score 78, HOT",
        "count": 8,
        "plan_weights": [0.2, 0.3, 0.3, 0.2],
        "seat_fill": (0.30, 0.70),
        "dau_spike": True,
        "spike_day_range": (55, 80),
        "feature_discovery_rate": 0.18,
        "base_features": 4,
    },
    "crunch_and_features": {
        "description": "Seat crunch + feature milestone -> score 72, HOT",
        "count": 10,
        "plan_weights": [0.3, 0.3, 0.3, 0.1],
        "seat_fill": (0.82, 0.98),
        "dau_spike": False,
        "spike_day_range": None,
        "feature_discovery_rate": 0.15,
        "base_features": 5,
    },
    "spike_only": {
        "description": "Only usage spike -> score 40, COLD",
        "count": 8,
        "plan_weights": [0.3, 0.3, 0.3, 0.1],
        "seat_fill": (0.20, 0.60),
        "dau_spike": True,
        "spike_day_range": (60, 85),
        "feature_discovery_rate": 0.04,
        "base_features": 3,
    },
    "crunch_only": {
        "description": "Only seat crunch -> score 35, COLD",
        "count": 8,
        "plan_weights": [0.4, 0.3, 0.2, 0.1],
        "seat_fill": (0.85, 0.98),
        "dau_spike": False,
        "spike_day_range": None,
        "feature_discovery_rate": 0.03,
        "base_features": 2,
    },
    "features_only": {
        "description": "Only feature milestone -> score 25, COLD",
        "count": 8,
        "plan_weights": [0.2, 0.4, 0.3, 0.1],
        "seat_fill": (0.20, 0.55),
        "dau_spike": False,
        "spike_day_range": None,
        "feature_discovery_rate": 0.16,
        "base_features": 4,
    },
    "dormant": {
        "description": "No signals fire -> score 0, COLD",
        "count": 12,
        "plan_weights": [0.4, 0.3, 0.2, 0.1],
        "seat_fill": (0.10, 0.50),
        "dau_spike": False,
        "spike_day_range": None,
        "feature_discovery_rate": 0.02,
        "base_features": 2,
    },
    "churning": {
        "description": "Was active, now declining -> score 0, COLD",
        "count": 10,
        "plan_weights": [0.3, 0.3, 0.3, 0.1],
        "seat_fill": (0.30, 0.60),
        "dau_spike": False,
        "spike_day_range": None,
        "feature_discovery_rate": 0.0,
        "base_features": 4,
    },
}


def generate_company_name():
    """Generate a realistic startup/company name."""
    patterns = [
        lambda: f"{fake.last_name()} Technologies",
        lambda: f"{fake.last_name()} Solutions",
        lambda: f"{fake.word().capitalize()}{random.choice(['Stack', 'Sync', 'Flow', 'Base', 'Hub', 'Cloud', 'Ops'])}",
        lambda: f"{random.choice(['Nova', 'Peak', 'Core', 'Edge', 'Apex', 'Bolt', 'Nest'])}{fake.word().capitalize()}",
        lambda: f"{fake.word().capitalize()} {random.choice(['Digital', 'Systems', 'Analytics', 'AI', 'Tech'])}",
    ]
    return random.choice(patterns)()


def generate_daily_events(company, day_index, total_days):
    """Generate one day of usage data."""
    arch = company["archetype_config"]
    event_date = START_DATE + timedelta(days=day_index)
    progress = day_index / total_days

    # --- Daily Active Users ---
    base_dau = company["base_dau"]
    growth = 0.15 * day_index  # gentle growth
    dau = base_dau + growth
    dau = max(1, int(dau + random.gauss(0, max(1, dau * 0.1))))

    # Handle spike archetype
    if arch["dau_spike"] and arch["spike_day_range"]:
        spike_start, spike_end = arch["spike_day_range"]
        if day_index >= spike_start:
            spike_mult = random.uniform(2.5, 4.0)
            dau = int(dau * spike_mult)

    # Handle churning: sharp decline after midpoint
    if company["archetype"] == "churning" and progress > 0.4:
        decline = (progress - 0.4) * 4
        dau = max(1, int(dau * max(0.1, 1 - decline)))

    # Cap DAU at seats purchased
    dau = min(dau, company["seats_purchased"])
    dau = max(1, dau)

    # --- Seats Used ---
    seat_min, seat_max = arch["seat_fill"]
    fill_rate = seat_min + (progress * (seat_max - seat_min))
    seats_used = min(
        company["seats_purchased"],
        max(dau, int(company["seats_purchased"] * fill_rate))
    )

    # --- Features Used ---
    feature_count = arch["base_features"] + int(
        arch["feature_discovery_rate"] * day_index
    )
    feature_count = min(feature_count, len(FEATURES))
    feature_count = max(1, feature_count + random.randint(-1, 1))

    # --- API Calls ---
    api_calls = max(10, int(
        company["base_api_calls"] * (1 + 0.01 * day_index) *
        random.uniform(0.7, 1.3)
    ))

    # Spike in API calls mirrors DAU spike
    if arch["dau_spike"] and arch["spike_day_range"]:
        spike_start = arch["spike_day_range"][0]
        if day_index >= spike_start:
            api_calls = int(api_calls * random.uniform(2.0, 3.0))

    # Weekend dip
    weekday = event_date.weekday()
    if weekday in (5, 6):
        dau = max(1, int(dau * random.uniform(0.3, 0.6)))
        api_calls = max(10, int(api_calls * random.uniform(0.2, 0.5)))

    return {
        "company_id": company["company_id"],
        "company_name": company["company_name"],
        "event_date": event_date.strftime("%Y-%m-%d"),
        "daily_active_users": dau,
        "features_used": feature_count,
        "api_calls": api_calls,
        "seats_purchased": company["seats_purchased"],
        "seats_used": seats_used,
        "plan_type": company["plan_type"],
        "mrr": company["mrr"],
        "signup_date": company["signup_date"],
    }


def generate_all_data():
    """Generate the complete synthetic dataset with varied archetypes."""
    print(f"Generating varied data for {NUM_COMPANIES} companies over {NUM_DAYS} days...")

    plans = ["free", "starter", "pro", "enterprise"]
    companies = []
    used_names = set()
    company_idx = 1

    for arch_name, arch_config in ARCHETYPES.items():
        for _ in range(arch_config["count"]):
            # Generate unique name
            name = generate_company_name()
            while name in used_names:
                name = generate_company_name()
            used_names.add(name)

            # Pick plan based on archetype weights
            plan = random.choices(plans, weights=arch_config["plan_weights"], k=1)[0]
            seat_limit = PLAN_SEAT_LIMITS[plan]
            seats_purchased = random.randint(max(3, seat_limit // 3), seat_limit)

            signup_offset = random.randint(30, 365)
            signup_date = START_DATE - timedelta(days=signup_offset)

            companies.append({
                "company_id": f"C{company_idx:03d}",
                "company_name": name,
                "plan_type": plan,
                "mrr": PLAN_MRR[plan],
                "seats_purchased": seats_purchased,
                "signup_date": signup_date.strftime("%Y-%m-%d"),
                "archetype": arch_name,
                "archetype_config": arch_config,
                "base_dau": random.randint(2, max(3, seats_purchased // 3)),
                "base_api_calls": random.randint(50, 500),
            })
            company_idx += 1

    # Generate daily events
    all_events = []
    for company in companies:
        for day in range(NUM_DAYS):
            event = generate_daily_events(company, day, NUM_DAYS)
            all_events.append(event)

    df = pd.DataFrame(all_events)
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df["signup_date"] = pd.to_datetime(df["signup_date"]).dt.date
    for col in ["daily_active_users", "features_used", "api_calls",
                "seats_purchased", "seats_used", "mrr"]:
        df[col] = df[col].astype(int)

    print(f"Generated {len(df)} total rows")
    print(f"\nArchetype distribution:")
    for arch_name, arch_config in ARCHETYPES.items():
        print(f"  {arch_name}: {arch_config['count']} companies -> {arch_config['description']}")

    print(f"\nExpected tier distribution after SQL scoring:")
    critical = sum(v["count"] for k, v in ARCHETYPES.items()
                   if k in ("triple_threat", "spike_and_crunch"))
    hot = sum(v["count"] for k, v in ARCHETYPES.items()
              if k in ("spike_and_features", "crunch_and_features"))
    cold = NUM_COMPANIES - critical - hot
    print(f"  CRITICAL (85+): ~{critical} accounts")
    print(f"  HOT (70-84):    ~{hot} accounts")
    print(f"  COLD (<50):     ~{cold} accounts")

    return df, companies


def save_csv(df, filepath="usage_events_v2.csv"):
    """Save data locally as CSV."""
    df.to_csv(filepath, index=False)
    print(f"\nCSV saved to: {filepath} ({len(df)} rows)")
    print(f"\nNext steps:")
    print(f"  1. Go to BigQuery Console: console.cloud.google.com/bigquery")
    print(f"  2. Click your dataset: gtm_signals")
    print(f"  3. Click usage_events table > Delete Table (old data)")
    print(f"  4. Create Table > Upload > Select {filepath}")
    print(f"  5. Table name: usage_events")
    print(f"  6. Auto detect schema: ON")
    print(f"  7. Write disposition: WRITE_TRUNCATE")
    print(f"  8. The scored_signals view auto-recalculates")


if __name__ == "__main__":
    print("=" * 60)
    print("GTM SIGNAL ENGINE - Data Generator v2 (Varied)")
    print("=" * 60)
    df, companies = generate_all_data()
    save_csv(df)
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
