"""
GTM Signal Engine - Synthetic Data Generator
=============================================
Generates realistic B2B SaaS usage data for a fictional workflow automation platform.
Loads data into BigQuery for signal detection and scoring.

Usage:
    pip install google-cloud-bigquery pandas faker pyarrow db-dtypes
    export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"
    python generate_data.py

Author: Utkarsh Kapoor
"""

import random
import os
from datetime import datetime, timedelta
from faker import Faker
import pandas as pd
from google.cloud import bigquery

# ============================================================
# CONFIGURATION - Change these to match your GCP project
# ============================================================
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "your-project-id")
BQ_DATASET = "gtm_signals"
BQ_TABLE = "usage_events"
FULL_TABLE_ID = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"

NUM_COMPANIES = 75
NUM_DAYS = 90
START_DATE = datetime(2026, 7, 28)  # 90 days back from ~Oct 26

fake = Faker()
Faker.seed(42)
random.seed(42)

# ============================================================
# COMPANY PROFILES - Each company gets a "behavior archetype"
# ============================================================
PLAN_TYPES = ["free", "starter", "pro", "enterprise"]
PLAN_MRR = {"free": 0, "starter": 99, "pro": 299, "enterprise": 799}
PLAN_SEAT_LIMITS = {"free": 5, "starter": 15, "pro": 50, "enterprise": 200}

# Available features in the fictional platform
FEATURES = [
    "workflow_builder", "scheduler", "api_connector", "webhook_handler",
    "error_logger", "dashboard_analytics", "team_collaboration",
    "version_control", "template_library", "ai_node", "conditional_logic",
    "loop_iterator", "database_connector", "email_node", "slack_integration",
    "crm_connector", "file_processor", "http_request", "code_node",
    "approval_workflow"
]

ARCHETYPES = {
    "steady_grower": {
        "description": "Gradually increasing usage, healthy adoption",
        "weight": 0.25,
        "dau_growth_per_day": 0.3,
        "feature_discovery_rate": 0.15,
        "api_base_multiplier": 1.0,
        "churn_risk": 0.0,
    },
    "power_user": {
        "description": "High usage from day one, uses many features",
        "weight": 0.15,
        "dau_growth_per_day": 0.1,
        "feature_discovery_rate": 0.25,
        "api_base_multiplier": 2.5,
        "churn_risk": 0.0,
    },
    "sudden_spike": {
        "description": "Normal usage then sudden jump (new team adopted it)",
        "weight": 0.15,
        "dau_growth_per_day": 0.05,
        "feature_discovery_rate": 0.08,
        "api_base_multiplier": 1.0,
        "churn_risk": 0.0,
        "spike_day_range": (45, 70),
        "spike_multiplier": (2.5, 4.0),
    },
    "seat_cruncher": {
        "description": "Rapidly filling up their seat allocation",
        "weight": 0.15,
        "dau_growth_per_day": 0.4,
        "feature_discovery_rate": 0.10,
        "api_base_multiplier": 1.2,
        "churn_risk": 0.0,
    },
    "dormant": {
        "description": "Signed up but barely uses the product",
        "weight": 0.15,
        "dau_growth_per_day": -0.05,
        "feature_discovery_rate": 0.02,
        "api_base_multiplier": 0.3,
        "churn_risk": 0.3,
    },
    "churning": {
        "description": "Was active, now declining rapidly",
        "weight": 0.10,
        "dau_growth_per_day": -0.3,
        "feature_discovery_rate": 0.0,
        "api_base_multiplier": 0.8,
        "churn_risk": 0.6,
    },
    "expansion_ready": {
        "description": "High usage + high seats + many features = ready to upgrade",
        "weight": 0.05,
        "dau_growth_per_day": 0.35,
        "feature_discovery_rate": 0.20,
        "api_base_multiplier": 2.0,
        "churn_risk": 0.0,
    },
}


def generate_company_name():
    """Generate a realistic startup/company name."""
    patterns = [
        lambda: f"{fake.last_name()} Technologies",
        lambda: f"{fake.last_name()} Solutions",
        lambda: f"{fake.company_suffix()} {fake.word().capitalize()}Labs",
        lambda: f"{''.join(random.choices('AEIOU', k=1))[0]}{fake.word().capitalize()}",
        lambda: f"{fake.word().capitalize()}{random.choice(['Stack', 'Sync', 'Flow', 'Base', 'Hub', 'Cloud', 'Ops'])}",
        lambda: f"{fake.word().capitalize()} {random.choice(['Digital', 'Systems', 'Analytics', 'AI', 'Tech'])}",
        lambda: f"{random.choice(['Nova', 'Peak', 'Core', 'Edge', 'Apex', 'Bolt', 'Nest'])}{fake.word().capitalize()}",
    ]
    return random.choice(patterns)()


def pick_archetype():
    """Weighted random selection of a company behavior archetype."""
    archetypes = list(ARCHETYPES.keys())
    weights = [ARCHETYPES[a]["weight"] for a in archetypes]
    return random.choices(archetypes, weights=weights, k=1)[0]


def generate_company_profile(company_id):
    """Create a company with a plan, seat count, and behavior archetype."""
    archetype = pick_archetype()
    plan = random.choices(
        PLAN_TYPES,
        weights=[0.25, 0.30, 0.30, 0.15],
        k=1
    )[0]

    seat_limit = PLAN_SEAT_LIMITS[plan]
    seats_purchased = random.randint(
        max(3, seat_limit // 4),
        seat_limit
    )

    signup_offset = random.randint(30, 365)
    signup_date = START_DATE - timedelta(days=signup_offset)

    base_dau = random.randint(3, max(4, seats_purchased // 2))
    base_features = random.randint(2, 5)
    base_api_calls = random.randint(50, 500)

    return {
        "company_id": f"C{company_id:03d}",
        "company_name": generate_company_name(),
        "plan_type": plan,
        "mrr": PLAN_MRR[plan],
        "seats_purchased": seats_purchased,
        "signup_date": signup_date.strftime("%Y-%m-%d"),
        "archetype": archetype,
        "base_dau": base_dau,
        "base_features": base_features,
        "base_api_calls": base_api_calls,
    }


def generate_daily_events(company, day_index, total_days):
    """Generate one day of usage data for a company based on its archetype."""
    arch = ARCHETYPES[company["archetype"]]
    event_date = START_DATE + timedelta(days=day_index)
    progress = day_index / total_days  # 0.0 to 1.0

    # --- Daily Active Users ---
    growth = arch["dau_growth_per_day"] * day_index
    dau = company["base_dau"] + growth
    dau = max(1, int(dau + random.gauss(0, max(1, dau * 0.1))))

    # Handle sudden spike archetype
    if company["archetype"] == "sudden_spike":
        spike_start, spike_end = arch["spike_day_range"]
        if day_index >= spike_start:
            spike_mult = random.uniform(*arch["spike_multiplier"])
            dau = int(dau * spike_mult)

    # Handle churning: sharp decline after midpoint
    if company["archetype"] == "churning" and progress > 0.4:
        decline = (progress - 0.4) * 5
        dau = max(1, int(dau * max(0.1, 1 - decline)))

    # Cap DAU at seats purchased (can't have more users than seats)
    dau = min(dau, company["seats_purchased"])
    dau = max(1, dau)

    # --- Seats Used ---
    # Seats used trends toward DAU but can be slightly higher
    # (some users set up but don't log in daily)
    seats_used = min(
        company["seats_purchased"],
        max(dau, int(dau * random.uniform(1.0, 1.3)))
    )

    # Seat cruncher: push seats_used close to limit
    if company["archetype"] == "seat_cruncher":
        fill_rate = 0.5 + (progress * 0.5)
        seats_used = min(
            company["seats_purchased"],
            max(seats_used, int(company["seats_purchased"] * fill_rate))
        )

    # Expansion ready: also push seats high
    if company["archetype"] == "expansion_ready":
        seats_used = min(
            company["seats_purchased"],
            max(seats_used, int(company["seats_purchased"] * (0.6 + progress * 0.35)))
        )

    # --- Features Used ---
    feature_count = company["base_features"] + int(
        arch["feature_discovery_rate"] * day_index
    )
    feature_count = min(feature_count, len(FEATURES))
    feature_count = max(1, feature_count + random.randint(-1, 1))
    feature_count = min(feature_count, len(FEATURES))

    # --- API Calls ---
    api_base = company["base_api_calls"] * arch["api_base_multiplier"]
    api_calls = api_base + (api_base * 0.01 * day_index)
    api_calls = max(10, int(api_calls * random.uniform(0.7, 1.3)))

    # Spike in API calls mirrors DAU spike
    if company["archetype"] == "sudden_spike":
        spike_start = arch["spike_day_range"][0]
        if day_index >= spike_start:
            api_calls = int(api_calls * random.uniform(2.0, 3.5))

    # Dormant/churning: API calls drop
    if company["archetype"] in ("dormant", "churning") and progress > 0.3:
        api_calls = max(10, int(api_calls * max(0.1, 1 - progress)))

    # --- Weekend dip (realistic pattern) ---
    weekday = event_date.weekday()
    if weekday in (5, 6):  # Saturday, Sunday
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
    """Generate the complete synthetic dataset."""
    print(f"Generating data for {NUM_COMPANIES} companies over {NUM_DAYS} days...")

    companies = [generate_company_profile(i + 1) for i in range(NUM_COMPANIES)]

    all_events = []
    for company in companies:
        for day in range(NUM_DAYS):
            event = generate_daily_events(company, day, NUM_DAYS)
            all_events.append(event)

    df = pd.DataFrame(all_events)

    # Ensure correct data types
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df["signup_date"] = pd.to_datetime(df["signup_date"]).dt.date
    df["daily_active_users"] = df["daily_active_users"].astype(int)
    df["features_used"] = df["features_used"].astype(int)
    df["api_calls"] = df["api_calls"].astype(int)
    df["seats_purchased"] = df["seats_purchased"].astype(int)
    df["seats_used"] = df["seats_used"].astype(int)
    df["mrr"] = df["mrr"].astype(int)

    print(f"Generated {len(df)} total rows")
    print(f"\nArchetype distribution:")
    arch_counts = {}
    for c in companies:
        arch = c["archetype"]
        arch_counts[arch] = arch_counts.get(arch, 0) + 1
    for arch, count in sorted(arch_counts.items()):
        print(f"  {arch}: {count} companies")

    print(f"\nPlan distribution:")
    plan_counts = {}
    for c in companies:
        plan = c["plan_type"]
        plan_counts[plan] = plan_counts.get(plan, 0) + 1
    for plan, count in sorted(plan_counts.items()):
        print(f"  {plan}: {count} companies")

    print(f"\nSample rows:")
    print(df.head(3).to_string(index=False))

    return df, companies


def save_csv(df, filepath="usage_events.csv"):
    """Save data locally as CSV backup."""
    df.to_csv(filepath, index=False)
    print(f"\nCSV saved to: {filepath} ({len(df)} rows)")


def load_to_bigquery(df):
    """Load the DataFrame into BigQuery using a batch load job."""
    print(f"\nLoading data to BigQuery: {FULL_TABLE_ID}")

    if GCP_PROJECT_ID == "your-project-id":
        print("ERROR: Set GCP_PROJECT_ID environment variable first.")
        print("  export GCP_PROJECT_ID='your-actual-project-id'")
        return False

    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        print("ERROR: Set GOOGLE_APPLICATION_CREDENTIALS environment variable.")
        print("  export GOOGLE_APPLICATION_CREDENTIALS='path/to/key.json'")
        return False

    if not os.path.exists(creds_path):
        print(f"ERROR: Credentials file not found: {creds_path}")
        return False

    client = bigquery.Client(project=GCP_PROJECT_ID)

    # Create dataset if it doesn't exist
    dataset_ref = bigquery.DatasetReference(GCP_PROJECT_ID, BQ_DATASET)
    try:
        client.get_dataset(dataset_ref)
        print(f"Dataset '{BQ_DATASET}' already exists.")
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset)
        print(f"Created dataset '{BQ_DATASET}'.")

    # Define schema explicitly
    schema = [
        bigquery.SchemaField("company_id", "STRING"),
        bigquery.SchemaField("company_name", "STRING"),
        bigquery.SchemaField("event_date", "DATE"),
        bigquery.SchemaField("daily_active_users", "INTEGER"),
        bigquery.SchemaField("features_used", "INTEGER"),
        bigquery.SchemaField("api_calls", "INTEGER"),
        bigquery.SchemaField("seats_purchased", "INTEGER"),
        bigquery.SchemaField("seats_used", "INTEGER"),
        bigquery.SchemaField("plan_type", "STRING"),
        bigquery.SchemaField("mrr", "INTEGER"),
        bigquery.SchemaField("signup_date", "DATE"),
    ]

    # Configure the load job
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    # Load data using batch load job (works in BigQuery Sandbox)
    job = client.load_table_from_dataframe(
        df, FULL_TABLE_ID, job_config=job_config
    )
    job.result()  # Wait for completion

    table = client.get_table(FULL_TABLE_ID)
    print(f"Loaded {table.num_rows} rows to {FULL_TABLE_ID}")
    print("BigQuery load complete.")
    return True


def save_company_profiles(companies, filepath="company_profiles.csv"):
    """Save company profiles with archetypes for reference."""
    profiles_df = pd.DataFrame(companies)
    profiles_df.to_csv(filepath, index=False)
    print(f"Company profiles saved to: {filepath}")


if __name__ == "__main__":
    print("=" * 60)
    print("GTM SIGNAL ENGINE - Data Generator")
    print("=" * 60)

    # Generate data
    df, companies = generate_all_data()

    # Always save CSV as backup
    save_csv(df)
    save_company_profiles(companies)

    # Try to load to BigQuery
    print("\n" + "=" * 60)
    print("BIGQUERY UPLOAD")
    print("=" * 60)

    success = load_to_bigquery(df)

    if not success:
        print("\nBigQuery upload skipped. You can:")
        print("1. Set environment variables and run again, OR")
        print("2. Upload usage_events.csv manually via BigQuery Console:")
        print("   console.cloud.google.com > BigQuery > Create Table > Upload")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
