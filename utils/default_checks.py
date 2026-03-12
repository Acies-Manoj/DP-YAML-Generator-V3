"""
utils/default_checks.py
═══════════════════════════════════════════════════════════════════════════════
DETERMINISTIC DEFAULT QC CHECK GENERATOR
No LLM involved. Pure rule-based logic from schema + profiling data.

═══════════════════════════════════════════════════════════════════════════════
HOW WE ARRIVE AT DEFAULT CHECKS — COMPLETE LEARNING REFERENCE
═══════════════════════════════════════════════════════════════════════════════

The 7 rules below map directly to the 6 SodaCL check categories in DataOS.
Each rule has a clear trigger condition derived from Layer 1-5 of sf_utils.py.

──────────────────────────────────────────────────────────────────────────────
RULE 1 — Schema: Required columns (warn)
──────────────────────────────────────────────────────────────────────────────
  Source:   Layer 1 — INFORMATION_SCHEMA.COLUMNS
  Trigger:  Always — generated for every table
  Logic:    Every column found in INFORMATION_SCHEMA is added to the
            "when required column missing" list. This is a WARN (not fail)
            because missing columns in a source table are a schema drift
            issue, not a data issue. If Soda finds the column is gone, it
            warns the team rather than failing the pipeline.
  SodaCL:
    schema:
      name: "Ensure essential columns are present"
      warn:
        when required column missing: [COL1, COL2, ...]
      attributes:
        category: Schema

──────────────────────────────────────────────────────────────────────────────
RULE 2 — Schema: Data type validation (fail)
──────────────────────────────────────────────────────────────────────────────
  Source:   Layer 1 — DATA_TYPE from INFORMATION_SCHEMA, mapped via soda_type()
  Trigger:  Always — generated for every table
  Logic:    Each column's Snowflake type is mapped to the Soda type string
            (e.g. NUMBER → decimal, VARCHAR → string, TIMESTAMP_NTZ → timestamp).
            If the type changes unexpectedly (e.g. a number column becomes a
            string after a pipeline change), this check FAILS — blocking
            downstream consumers from getting bad data.
  SodaCL:
    schema:
      name: "Data types validation"
      fail:
        when wrong column type:
          COLUMN_NAME: soda_type
      attributes:
        category: Schema

──────────────────────────────────────────────────────────────────────────────
RULE 3 — Completeness: missing_count = 0
──────────────────────────────────────────────────────────────────────────────
  Source:   Layer 1 (IS_NULLABLE) + Layer 2 (is_pk)
  Trigger:  Column is NOT NULL in schema (IS_NULLABLE = NO)
            OR column is identified as a Primary Key
  Logic:    If a column is declared NOT NULL in Snowflake, missing values
            are a schema contract violation. PKs must never be null by
            definition. This check enforces that at data quality runtime.
            Note: if IS_NULLABLE fetch failed, this defaults to nullable=True
            (safe — no false positives). PK heuristic is applied as fallback.
  SodaCL:
    missing_count(COLUMN) = 0:
      name: "COLUMN should not have missing values"
      attributes:
        category: Completeness

──────────────────────────────────────────────────────────────────────────────
RULE 4 — Uniqueness: duplicate_count = 0
──────────────────────────────────────────────────────────────────────────────
  Source:   Layer 2 — SHOW PRIMARY KEYS (or heuristic)
  Trigger:  Column is identified as Primary Key (real or inferred)
  Logic:    Primary keys are unique by definition. If duplicates exist in a
            PK column, the data product is fundamentally broken — joins,
            aggregations, and downstream models will produce wrong results.
            This is the most important structural check for any table.
  SodaCL:
    duplicate_count(COLUMN) = 0:
      name: "COLUMN should not have duplicate values"
      attributes:
        category: Uniqueness

──────────────────────────────────────────────────────────────────────────────
RULE 5 — Freshness: freshness(col) < 7d
──────────────────────────────────────────────────────────────────────────────
  Source:   Layer 1 (DATA_TYPE is timestamp/date) + Layer 5 (name pattern)
  Trigger:  Column is a timestamp/date type AND name contains any of:
            created_at, updated_at, modified_at, last_modified, inserted_at,
            loaded_at, refreshed_at, timestamp, event_time, date_added,
            date_updated, ingested_at
  Logic:    If a table has a freshness column, data consumers depend on it
            being updated regularly. A 7-day threshold is the default
            (conservative for daily pipelines). This should be adjusted
            by the user based on their actual SLO (e.g. < 1d for real-time).
  SodaCL:
    freshness(COLUMN) < 7d:
      name: "COLUMN data should not be older than 7 days"
      attributes:
        category: Freshness

──────────────────────────────────────────────────────────────────────────────
RULE 6 — Validity: invalid_count = 0 with valid values (enum check)
──────────────────────────────────────────────────────────────────────────────
  Source:   Layer 4 (distinct_count) + Layer 3 (sample_values) + Layer 5 (flag)
  Trigger:  Column is a string type AND distinct_count < 20 (is_likely_enum)
            AND at least 1 sample value was collected
  Logic:    When a string column has very few distinct values, it is almost
            certainly a categorical/enum column (status, region, type, grade,
            etc.). The observed sample values become the valid values list.
            Any value outside this set is invalid data.
            ⚠️  Important: sample_values are from LIMIT 100 — if the table
            has more categories than appear in the first 100 rows, some valid
            values will be missing. User should review and add missing values.
  SodaCL:
    invalid_count(COLUMN) = 0:
      name: "COLUMN should contain only valid values"
      valid values: ["val1", "val2", ...]
      attributes:
        category: Validity

──────────────────────────────────────────────────────────────────────────────
RULE 7 — Accuracy: avg_length(col) > threshold
──────────────────────────────────────────────────────────────────────────────
  Source:   Layer 4 (avg_length from AVG(LENGTH(col)))
  Trigger:  Column is a string type AND avg_length was successfully computed
  Logic:    The observed average string length sets a lower bound. If the
            average drops to half the observed value, it likely signals
            data truncation, empty strings, or a pipeline issue that started
            producing shorter/corrupted values.
            Threshold = floor(observed_avg_length * 0.5), minimum 1.
  SodaCL:
    avg_length(COLUMN) > threshold:
      name: "Average length of COLUMN should be reasonable"
      attributes:
        category: Accuracy

═══════════════════════════════════════════════════════════════════════════════
CHECK DICT SCHEMA (returned by generate_default_checks)
═══════════════════════════════════════════════════════════════════════════════
{
    "col":      str | None,   # column name; None for table-level checks
    "category": str,          # Schema | Completeness | Uniqueness |
                              # Freshness | Validity | Accuracy
    "name":     str,          # human-readable check description
    "syntax":   str,          # SodaCL check key (the YAML mapping key)
    "body":     dict | None,  # sub-keys under the check (valid min, etc.)
    "source":   "default",    # always "default" — distinguishes from LLM
}
"""

from utils.sf_utils import is_string, is_timestamp


def generate_default_checks(ctx: dict) -> list[dict]:
    """
    Generate deterministic SodaCL quality checks from Snowflake context.

    Args:
        ctx: result of fetch_full_context() from sf_utils.py

    Returns:
        List of check dicts ordered by category:
        Schema → Completeness → Uniqueness → Freshness → Validity → Accuracy
    """
    checks = []
    columns = ctx["columns"]

    # ── Rule 1: Schema — required columns present (warn) ─────────────────────
    col_names = [c["name"] for c in columns]
    checks.append({
        "col":      None,
        "category": "Schema",
        "name":     "Ensure essential columns are present",
        "syntax":   "schema",
        "body": {
            "warn": {
                "when required column missing": col_names
            }
        },
        "source": "default",
    })

    # ── Rule 2: Schema — data types validation (fail) ─────────────────────────
    type_map = {c["name"]: c["soda_type"] for c in columns}
    checks.append({
        "col":      None,
        "category": "Schema",
        "name":     "Data types validation — columns must match expected types",
        "syntax":   "schema",
        "body": {
            "fail": {
                "when wrong column type": type_map
            }
        },
        "source": "default",
    })

    # ── Rule 3: Completeness — missing_count = 0 for NOT NULL / PK ───────────
    for col in columns:
        if not col["nullable"] or col["is_pk"]:
            reason = "Primary Key" if col["is_pk"] else "NOT NULL constraint"
            checks.append({
                "col":      col["name"],
                "category": "Completeness",
                "name":     f"{col['name']} should not have missing values ({reason})",
                "syntax":   f"missing_count({col['name']}) = 0",
                "body":     None,
                "source":   "default",
            })

    # ── Rule 4: Uniqueness — duplicate_count = 0 for PK columns ──────────────
    for col in columns:
        if col["is_pk"]:
            pk_source = "heuristic" if col.get("is_pk_inferred") else "SHOW PRIMARY KEYS"
            checks.append({
                "col":      col["name"],
                "category": "Uniqueness",
                "name":     f"{col['name']} should not have duplicate values (PK via {pk_source})",
                "syntax":   f"duplicate_count({col['name']}) = 0",
                "body":     None,
                "source":   "default",
            })
            
    # ── Rule 5: Freshness — freshness(col) < 1d ─────────
    freshness_added = False

    for col in columns:

        col_name = col["name"].lower()

        if (
            not freshness_added and
            (
                col.get("is_freshness_col") or
                is_timestamp(col["sf_type"]) or
                any(k in col_name for k in ["date", "time", "timestamp", "period"])
            )
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

    # ── Rule 6: Validity — enum check for likely-enum string columns ──────────
    for col in columns:
        if col["is_likely_enum"] and col["sample_values"]:
            vals = [str(v) for v in col["sample_values"]]
            checks.append({
                "col":      col["name"],
                "category": "Validity",
                "name":     f"{col['name']} should contain only known valid values",
                "syntax":   f"invalid_count({col['name']}) = 0",
                "body":     {"valid values": vals},
                "source":   "default",
            })

    # ── Rule 7: Accuracy — avg_length threshold for string columns ────────────
    for col in columns:
        avg_len = col.get("avg_length")

        if is_string(col["sf_type"]) and avg_len is not None and avg_len > 0:
            threshold = max(1, round(float(avg_len) * 0.5))
            checks.append({
                "col":      col["name"],
                "category": "Accuracy",
                "name":     f"Average length of {col['name']} should be > {threshold} (50% of observed {round(float(avg_len), 1)})",
                "syntax":   f"avg_length({col['name']}) > {threshold}",
                "body":     None,
                "source":   "default",
            })

    return checks