"""
utils/sf_utils.py — Snowflake connection + data pull for QC Generator.

HOW THE DEFAULT CHECK LOGIC FLOWS (for learning reference):
============================================================
fetch_full_context() pulls 5 layers of data from Snowflake:

  Layer 1 — INFORMATION_SCHEMA.COLUMNS
    → column name, native Snowflake data type, IS_NULLABLE (YES/NO),
      CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, ORDINAL_POSITION
    → IS_NULLABLE drives: Completeness checks (missing_count = 0)
    → DATA_TYPE drives: Schema checks (when wrong column type)
                        and which profiling aggregations to run

  Layer 2 — SHOW PRIMARY KEYS / SHOW IMPORTED KEYS
    → real PK columns drive: Completeness (must not be null)
                              Uniqueness (duplicate_count = 0)
    → if SHOW commands fail (permissions), heuristic patterns kick in:
      _PK_EXACT = {id, uuid, guid, pk}
      _PK_SUFFIXES = (_id, _key, _pk, _uuid, _guid)

  Layer 3 — SELECT * LIMIT 100  (sample query)
    → collects up to 5 unique non-null values per column
    → these become: valid values list for enum-like columns (Validity)
    → computed in Python — zero extra SQL

  Layer 4 — Single aggregation SQL (one query for whole table)
    → Numeric columns: MIN, MAX, AVG (cast to FLOAT), NULL count, DISTINCT count
      ⚠️  We use CAST("col" AS FLOAT) NOT TRY_TO_DOUBLE — TRY_TO_DOUBLE
          cannot accept NUMBER type as input in Snowflake.
    → String columns: AVG(LENGTH(col)), NULL count, DISTINCT count
    → These stats drive:
        - Accuracy checks: avg_length threshold = observed avg * 0.5
        - Validity (enum): distinct_count < 20 → flag is_likely_enum
        - Completeness: null_pct feeds LLM context for missing_percent suggestion

  Layer 5 — Derived flags (pure Python, no SQL)
    → is_likely_enum:   string + distinct_count < 20
                        → Validity: invalid_count(col) = 0 with valid values
    → is_freshness_col: timestamp type + name matches freshness patterns
                        → Freshness: freshness(col) < 7d

All of this feeds into default_checks.py which applies deterministic
rules to produce checks, then into llm_checks.py which sends the full
context + stats to the LLM for semantic suggestions.
"""

try:
    import snowflake.connector
    SF_AVAILABLE = True
except ImportError:
    SF_AVAILABLE = False

# ── Snowflake → Soda type mapping ────────────────────────────────────────────
# Source: DataOS production QC files + SodaCL documentation.
# Soda uses lowercase type strings in schema checks.
_SF_TO_SODA = {
    # Numeric — all map to integer or decimal depending on scale
    "NUMBER":           "decimal",
    "DECIMAL":          "decimal",
    "NUMERIC":          "decimal",
    "INT":              "integer",
    "INTEGER":          "integer",
    "BIGINT":           "integer",
    "SMALLINT":         "integer",
    "TINYINT":          "integer",
    "BYTEINT":          "integer",
    "FLOAT":            "double",
    "FLOAT4":           "double",
    "FLOAT8":           "double",
    "DOUBLE":           "double",
    "DOUBLE PRECISION": "double",
    "REAL":             "double",
    # String
    "VARCHAR":          "text",
    "CHAR":             "text",
    "CHARACTER":        "text",
    "STRING":           "text",
    "TEXT":             "text",
    "NVARCHAR":         "text",
    "NVARCHAR2":        "text",
    "NCHAR":            "text",
    # Boolean
    "BOOLEAN":          "boolean",
    # Date / Time
    "DATE":             "date",
    "DATETIME":         "timestamp",
    "TIME":             "time",
    "TIMESTAMP":        "timestamp",
    "TIMESTAMP_LTZ":    "timestamp",
    "TIMESTAMP_NTZ":    "timestamp",
    "TIMESTAMP_TZ":     "timestamp",
    # Semi-structured
    "VARIANT":          "variant",
    "OBJECT":           "object",
    "ARRAY":            "array",
    # Binary
    "BINARY":           "binary",
    "VARBINARY":        "binary",
}

# Freshness column name patterns
_FRESHNESS_PATTERNS = (
    "created_at", "updated_at", "modified_at", "last_modified",
    "inserted_at", "loaded_at", "refreshed_at", "timestamp",
    "event_time", "date_added", "date_updated", "ingested_at",
)

# PK/FK heuristic patterns (used when SHOW PRIMARY KEYS is unavailable)
_PK_SUFFIXES = ("_id", "_key", "_pk", "_uuid", "_guid")
_PK_EXACT    = {"id", "uuid", "guid", "pk"}
_FK_SUFFIXES = ("_id", "_key", "_fk", "_ref")

# Type classification sets (using Snowflake base type names)
_NUMERIC_BASES = {
    "NUMBER", "DECIMAL", "NUMERIC", "INT", "INTEGER", "BIGINT",
    "SMALLINT", "TINYINT", "BYTEINT", "FLOAT", "FLOAT4", "FLOAT8",
    "DOUBLE", "DOUBLE PRECISION", "REAL",
}
_STRING_BASES = {
    "VARCHAR", "CHAR", "CHARACTER", "STRING", "TEXT",
    "NVARCHAR", "NVARCHAR2", "NCHAR",
}
_TS_BASES = {
    "DATE", "DATETIME", "TIME", "TIMESTAMP",
    "TIMESTAMP_LTZ", "TIMESTAMP_NTZ", "TIMESTAMP_TZ",
}


def soda_type(sf_type: str) -> str:
    """Map Snowflake native type to SodaCL type string."""
    base = sf_type.split("(")[0].strip().upper()
    return _SF_TO_SODA.get(base, "text")


def is_numeric(sf_type: str) -> bool:
    return sf_type.split("(")[0].strip().upper() in _NUMERIC_BASES


def is_string(sf_type: str) -> bool:
    return sf_type.split("(")[0].strip().upper() in _STRING_BASES


def is_timestamp(sf_type: str) -> bool:
    return sf_type.split("(")[0].strip().upper() in _TS_BASES


# ── Connection helpers ────────────────────────────────────────────────────────

def connect(account, user, password, role="", warehouse=""):
    if not SF_AVAILABLE:
        raise RuntimeError("snowflake-connector-python not installed.")
    kw = dict(account=account, user=user, password=password)
    if role:      kw["role"]      = role
    if warehouse: kw["warehouse"] = warehouse
    return snowflake.connector.connect(**kw)


def fetch_databases(conn):
    cur = conn.cursor()
    cur.execute("SHOW DATABASES")
    return [r[1] for r in cur.fetchall()]


def fetch_schemas(conn, database):
    cur = conn.cursor()
    cur.execute(f'SHOW SCHEMAS IN DATABASE "{database}"')
    return [r[1] for r in cur.fetchall() if r[1].upper() != "INFORMATION_SCHEMA"]


def fetch_tables(conn, database, schema):
    cur = conn.cursor()
    cur.execute(f'SHOW TABLES IN SCHEMA "{database}"."{schema}"')
    return [r[1] for r in cur.fetchall()]


# ── Full context fetch ────────────────────────────────────────────────────────

def fetch_full_context(conn, database, schema, table, max_cols=40):
    """
    Pull all data needed for QC generation for one table.
    See module docstring for full explanation of each layer.

    Returns dict:
    {
        "table":      str,
        "columns":    list of column dicts (see below),
        "row_count":  int | None,
        "errors":     list of non-fatal warning strings,
    }

    Each column dict contains:
        name, sf_type, soda_type, nullable, char_max_len,
        is_pk, is_fk, is_pk_inferred,
        min_val, max_val, avg_val,
        null_count, null_pct, distinct_count,
        avg_length,          (strings only)
        sample_values,       (up to 5 unique non-null values)
        is_likely_enum,      (string + distinct_count < 20)
        is_freshness_col,    (timestamp + name pattern match)
    """
    result = {"table": table, "columns": [], "row_count": None, "errors": []}
    fq  = f'"{database}"."{schema}"."{table}"'
    cur = conn.cursor()

    # ── Layer 1: INFORMATION_SCHEMA.COLUMNS ──────────────────────────────────
    try:
        cur.execute(f"""
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                ORDINAL_POSITION
            FROM "{database}".INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = '{schema}'
              AND TABLE_NAME   = '{table}'
            ORDER BY ORDINAL_POSITION
        """)
        schema_rows = cur.fetchall()
    except Exception as e:
        result["errors"].append(f"Schema fetch failed: {e}")
        return result

    col_map = {}
    for row in schema_rows:
        cn, dt, nullable, char_len, num_prec, _ = row
        col_map[cn] = {
            "name":          cn,
            "sf_type":       dt,
            "soda_type":     soda_type(dt),
            "nullable":      (nullable or "YES").upper() == "YES",
            "char_max_len":  char_len,
            "is_pk":         False,
            "is_fk":         False,
            "is_pk_inferred": False,
            # Profiling — filled in Layer 4
            "min_val":       None,
            "max_val":       None,
            "avg_val":       None,
            "null_count":    None,
            "null_pct":      None,
            "distinct_count": None,
            "avg_length":    None,
            # Samples — filled in Layer 3
            "sample_values": [],
            # Derived flags — filled in Layer 5
            "is_likely_enum":   False,
            "is_freshness_col": False,
        }

    if not col_map:
        result["errors"].append("No columns found in INFORMATION_SCHEMA.")
        return result

    # ── Layer 2: PK / FK constraints ─────────────────────────────────────────
    real_pks: set = set()
    real_fks: set = set()

    try:
        cur.execute(f"SHOW PRIMARY KEYS IN TABLE {fq}")
        for r in cur.fetchall():
            real_pks.add(r[4])   # column_name is at index 4
    except Exception as e:
        result["errors"].append(f"SHOW PRIMARY KEYS unavailable — heuristic used: {e}")

    try:
        cur.execute(f"SHOW IMPORTED KEYS IN TABLE {fq}")
        for r in cur.fetchall():
            real_fks.add(r[7])   # fk_column_name is at index 7
    except Exception as e:
        result["errors"].append(f"SHOW IMPORTED KEYS unavailable — heuristic used: {e}")

    # Apply real constraints or fall back to name heuristics
    for cn, col in col_map.items():
        nl = cn.lower()
        if real_pks:
            # Real constraints available
            col["is_pk"] = cn in real_pks
            col["is_fk"] = cn in real_fks
        else:
            # Heuristic: column name pattern matching
            pk = (nl in _PK_EXACT or any(nl.endswith(s) for s in _PK_SUFFIXES))
            col["is_pk"]           = pk
            col["is_fk"]           = not pk and any(nl.endswith(s) for s in _FK_SUFFIXES)
            col["is_pk_inferred"]  = True

    # ── Layer 3: Sample query (LIMIT 100) ────────────────────────────────────
    all_cols  = list(col_map.keys())
    prof_cols = all_cols[:max_cols]          # cap at max_cols
    q_cols    = ", ".join(f'"{c}"' for c in prof_cols)

    try:
        cur.execute(f"SELECT {q_cols} FROM {fq} LIMIT 100")
        sample_rows = cur.fetchall()

        seen: dict = {c: set() for c in prof_cols}
        for row in sample_rows:
            for i, cn in enumerate(prof_cols):
                v = row[i]
                sv = v
                if sv is not None and len(seen[cn]) < 5 and sv not in seen[cn]:
                    seen[cn].add(sv)
                    col_map[cn]["sample_values"].append(v)

    except Exception as e:
        result["errors"].append(f"Sample query failed: {e}")

    # ── Layer 4: Aggregation profiling ───────────────────────────────────────
    # ⚠️  FIX: Snowflake does NOT allow TRY_TO_DOUBLE(NUMBER_COL).
    #     Use CAST("col" AS FLOAT) for AVG on numeric columns.
    #     For non-numeric types that slip through, we wrap with TRY_TO_NUMBER.
    #
    num_cols = [c for c in prof_cols if is_numeric(col_map[c]["sf_type"])]
    str_cols = [c for c in prof_cols if is_string(col_map[c]["sf_type"])]

    try:
        agg_parts = ["COUNT(*) AS __rows__"]

        # Numeric: MIN, MAX, AVG (cast to FLOAT avoids TRY_TO_DOUBLE issue),
        #          null count, distinct count
        for c in num_cols:
            s  = c.lower().replace(" ", "_")
            qc = f'"{c}"'
            agg_parts += [
                f"MIN({qc})                    AS __min_{s}__",
                f"MAX({qc})                    AS __max_{s}__",
                f"AVG(CAST({qc} AS FLOAT))     AS __avg_{s}__",
                f"SUM(CASE WHEN {qc} IS NULL THEN 1 ELSE 0 END) AS __null_{s}__",
                f"COUNT(DISTINCT {qc})         AS __dist_{s}__",
            ]

        # String: avg length, null count, distinct count
        for c in str_cols:
            s  = c.lower().replace(" ", "_")
            qc = f'"{c}"'
            agg_parts += [
                f"AVG(LENGTH({qc}))            AS __avgl_{s}__",
                f"SUM(CASE WHEN {qc} IS NULL THEN 1 ELSE 0 END) AS __null_{s}__",
                f"COUNT(DISTINCT {qc})         AS __dist_{s}__",
            ]

        if len(agg_parts) > 1:   # more than just COUNT(*)
            sql = f"SELECT {', '.join(agg_parts)} FROM {fq}"
            cur.execute(sql)
            agg_row = cur.fetchone()
            hdrs    = [d[0].lower() for d in cur.description]
            ad      = dict(zip(hdrs, agg_row))

            total = int(ad.get("__rows__") or 0)
            result["row_count"] = total

            for c in num_cols:
                s = c.lower().replace(" ", "_")
                col_map[c]["min_val"]       = ad.get(f"__min_{s}__")
                col_map[c]["max_val"]       = ad.get(f"__max_{s}__")
                raw_avg                     = ad.get(f"__avg_{s}__")
                col_map[c]["avg_val"]       = float(raw_avg) if raw_avg is not None else None
                nc                          = int(ad.get(f"__null_{s}__") or 0)
                col_map[c]["null_count"]    = nc
                col_map[c]["null_pct"]      = round(nc / total * 100, 2) if total else None
                col_map[c]["distinct_count"]= ad.get(f"__dist_{s}__")

            for c in str_cols:
                s = c.lower().replace(" ", "_")
                raw_avgl                    = ad.get(f"__avgl_{s}__")
                col_map[c]["avg_length"]    = float(raw_avgl) if raw_avgl is not None else None
                nc                          = int(ad.get(f"__null_{s}__") or 0)
                col_map[c]["null_count"]    = nc
                col_map[c]["null_pct"]      = round(nc / total * 100, 2) if total else None
                col_map[c]["distinct_count"]= ad.get(f"__dist_{s}__")

    except Exception as e:
        result["errors"].append(f"Profiling failed: {e}")

    # ── Layer 5: Derived flags (pure Python) ─────────────────────────────────
    for cn, col in col_map.items():
        nl = cn.lower()

        # is_likely_enum: string column with very few distinct values
        # → signals that valid values check makes sense
        dc = col.get("distinct_count")
        if is_string(col["sf_type"]) and dc is not None and int(dc) < 20:
            col["is_likely_enum"] = True

        # is_freshness_col: timestamp/date column whose name suggests
        # it tracks when a record was created or last updated
        if is_timestamp(col["sf_type"]):
            if any(pat in nl for pat in _FRESHNESS_PATTERNS):
                col["is_freshness_col"] = True

    result["columns"] = list(col_map.values())
    return result


def fetch_schema_overview(conn, db, schema):
    """
    Returns lightweight metadata for all tables in the schema.
    Only table + column names (no profiling).
    """

    cursor = conn.cursor()

    # Get tables
    cursor.execute(f"""
    SELECT table_name
    FROM "{db}".information_schema.tables
    WHERE table_schema = '{schema}'
    """)

    tables = [r[0] for r in cursor.fetchall()]
    schema_map = {}

    # Get columns per table
    for table in tables:
        cursor.execute(f"""
            SELECT column_name, data_type
            FROM "{db}".information_schema.columns
            WHERE table_schema = '{schema}'
            AND table_name = '{table}'
        """)

        cols = cursor.fetchall()

        schema_map[table] = [
            {"name": c[0], "type": c[1]}
            for c in cols
        ]

    return schema_map