"""
utils/default_checks.py

Deterministic Default QC Generator
Generates relevant SodaCL quality checks based on schema + profiling context.
"""

from utils.sf_utils import is_string, is_timestamp


# ─────────────────────────────────────────────────────────────────────────────
# COLUMN TYPE DETECTION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def is_identifier(col_name: str) -> bool:
    """Detect identifier columns."""
    name = col_name.lower()

    patterns = [
        "id",
        "uuid",
        "guid",
        "key",
        "number",
        "code"
    ]

    return any(p in name for p in patterns)


def is_boolean_column(col) -> bool:
    """Detect boolean-like categorical columns."""
    vals = [str(v).lower() for v in col.get("sample_values", [])]

    boolean_sets = [
        {"yes", "no"},
        {"true", "false"},
        {"y", "n"},
        {"active", "inactive"},
        {"0", "1"}
    ]

    for b in boolean_sets:
        if set(vals).issubset(b):
            return True

    return False


def is_freshness_column(col_name: str) -> bool:
    """Detect ingestion/update timestamp columns."""
    name = col_name.lower()

    freshness_keywords = [
        "updated",
        "modified",
        "loaded",
        "ingested",
        "refreshed",
        "last_updated",
        "last_modified",
        "event_time",
        "event_timestamp"
    ]

    return any(k in name for k in freshness_keywords)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN QC GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_default_checks(ctx: dict) -> list[dict]:

    checks = []
    columns = ctx["columns"]
    row_count = ctx.get("row_count", 0)

    # ─────────────────────────────────────────────────────────────────
    # RULE 1 — Schema: Required Columns
    # ─────────────────────────────────────────────────────────────────

    col_names = [c["name"] for c in columns]

    checks.append({
        "col": None,
        "category": "Schema",
        "name": "Ensure essential columns are present",
        "syntax": "schema",
        "body": {
            "warn": {
                "when required column missing": col_names
            }
        },
        "source": "default",
    })

    # ─────────────────────────────────────────────────────────────────
    # RULE 2 — Schema: Data Type Validation
    # ─────────────────────────────────────────────────────────────────

    type_map = {c["name"]: c["soda_type"] for c in columns}

    checks.append({
        "col": None,
        "category": "Schema",
        "name": "Data types validation",
        "syntax": "schema",
        "body": {
            "fail": {
                "when wrong column type": type_map
            }
        },
        "source": "default",
    })

    # ─────────────────────────────────────────────────────────────────
    # RULE 3 — Completeness
    # ─────────────────────────────────────────────────────────────────

    for col in columns:

        if not col["nullable"] or col["is_pk"]:

            checks.append({
                "col": col["name"],
                "category": "Completeness",
                "name": f"{col['name']} should not have missing values",
                "syntax": f"missing_count({col['name']}) = 0",
                "body": None,
                "source": "default",
            })

    # ─────────────────────────────────────────────────────────────────
    # RULE 3B — Nullable categorical columns
    # ─────────────────────────────────────────────────────────────────

    for col in columns:

        if (
            col["nullable"]
            and col.get("is_likely_enum")
            and is_string(col["sf_type"])
        ):

            checks.append({
                "col": col["name"],
                "category": "Completeness",
                "name": f"{col['name']} should have less than 5% missing values",
                "syntax": f"missing_percent({col['name']}) < 5%",
                "body": None,
                "source": "default",
            })

    # ─────────────────────────────────────────────────────────────────
    # RULE 4 — Uniqueness (Primary Keys)
    # ─────────────────────────────────────────────────────────────────

    for col in columns:

        if col["is_pk"]:

            checks.append({
                "col": col["name"],
                "category": "Uniqueness",
                "name": f"{col['name']} should not contain duplicates",
                "syntax": f"duplicate_count({col['name']}) = 0",
                "body": None,
                "source": "default",
            })

    # ─────────────────────────────────────────────────────────────────
    # RULE 5 — Freshness
    # ─────────────────────────────────────────────────────────────────

    freshness_added = False

    for col in columns:

        if (
            not freshness_added
            and is_timestamp(col["sf_type"])
            and is_freshness_column(col["name"])
        ):

            checks.append({
                "col": col["name"],
                "category": "Freshness",
                "name": f"{col['name']} should be refreshed daily",
                "syntax": f"freshness({col['name']}) < 1d",
                "body": None,
                "source": "default",
            })

            freshness_added = True

    # ─────────────────────────────────────────────────────────────────
    # RULE 6 — Validity (Categorical / Boolean)
    # ─────────────────────────────────────────────────────────────────

    for col in columns:

        name = col["name"]

        # Skip identifiers
        if is_identifier(name):
            continue

        # Skip high-cardinality columns
        if col.get("distinct_count") and row_count:
            if col["distinct_count"] / row_count > 0.9:
                continue

        # Boolean detection
        if is_boolean_column(col):

            checks.append({
                "col": name,
                "category": "Validity",
                "name": f"{name} should contain valid boolean values",
                "syntax": f"invalid_count({name}) = 0",
                "body": {
                    "valid values": col["sample_values"]
                },
                "source": "default",
            })

            continue

        # Enum detection
        if (
            is_string(col["sf_type"])
            and col.get("is_likely_enum")
            and col.get("sample_values")
        ):

            vals = [str(v) for v in col["sample_values"]]

            checks.append({
                "col": name,
                "category": "Validity",
                "name": f"{name} should contain only known valid values",
                "syntax": f"invalid_count({name}) = 0",
                "body": {"valid values": vals},
                "source": "default",
            })

    # ─────────────────────────────────────────────────────────────────
    # RULE 7 — Accuracy (Descriptive Text)
    # ─────────────────────────────────────────────────────────────────

    for col in columns:

        name = col["name"]
        avg_len = col.get("avg_length")

        # Skip identifier columns
        if is_identifier(name):
            continue

        if (
            is_string(col["sf_type"])
            and avg_len
            and avg_len > 0
        ):

            threshold = max(1, round(avg_len * 0.5))

            checks.append({
                "col": name,
                "category": "Accuracy",
                "name": f"Average length of {name} should be > {threshold}",
                "syntax": f"avg_length({name}) > {threshold}",
                "body": None,
                "source": "default",
            })

    return checks