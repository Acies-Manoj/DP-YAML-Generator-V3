"""
profiler.py — Optional lightweight profiling of Snowflake tables.
Fetches sample values, distinct counts, and null percentages.
Also retrieves real PK/FK constraints from Snowflake metadata.

All functions are safe: failures are caught and skipped silently.
"""


def get_pk_fk_info(conn, database: str, schema: str, table: str) -> dict:
    """
    Retrieve real PK and FK column names from Snowflake using SHOW commands.

    Args:
        conn:     Active Snowflake connection.
        database: Database name.
        schema:   Schema name.
        table:    Table name.

    Returns:
        {"pk_columns": [...], "fk_columns": [...]}
    """
    pk_columns = []
    fk_columns = []

    try:
        cur = conn.cursor()
        # Primary keys
        cur.execute(f'SHOW PRIMARY KEYS IN TABLE "{database}"."{schema}"."{table}"')
        rows = cur.fetchall()
        # Column name is at index 4 in SHOW PRIMARY KEYS output
        pk_columns = [r[4] for r in rows if r[4]]
    except Exception:
        pass  # Table may not have PK defined

    try:
        cur = conn.cursor()
        # Foreign keys — SHOW IMPORTED KEYS returns FK columns at index 7
        cur.execute(f'SHOW IMPORTED KEYS IN TABLE "{database}"."{schema}"."{table}"')
        rows = cur.fetchall()
        fk_columns = [r[7] for r in rows if r[7]]
    except Exception:
        pass  # Table may not have FK defined

    return {"pk_columns": pk_columns, "fk_columns": fk_columns}


def profile_table(
    conn,
    database: str,
    schema: str,
    table: str,
    columns: list[dict],
    sample_limit: int = 100,
) -> dict:
    """
    Run lightweight profiling on a Snowflake table.
    Uses minimal queries to avoid performance impact.

    Args:
        conn:         Active Snowflake connection.
        database:     Database name.
        schema:       Schema name.
        table:        Table name.
        columns:      List of column dicts with 'name' key.
        sample_limit: Max rows to sample.

    Returns:
        Dict keyed by column name:
        {
            "col_name": {
                "sample_values":  [up to 5 unique non-null values],
                "distinct_count": int | None,
                "null_pct":       float | None,
            }
        }
    """
    result = {}
    if not columns:
        return result

    col_names = [c["name"] for c in columns]
    fq_table  = f'"{database}"."{schema}"."{table}"'

    # ── Step 1: Sample rows (single query) ───────────────────────────────────
    sample_data = {name: set() for name in col_names}
    try:
        quoted_cols = ", ".join(f'"{c}"' for c in col_names)
        cur = conn.cursor()
        cur.execute(f"SELECT {quoted_cols} FROM {fq_table} LIMIT {sample_limit}")
        rows = cur.fetchall()
        col_indices = {name: i for i, name in enumerate(col_names)}

        for row in rows:
            for name in col_names:
                val = row[col_indices[name]]
                if val is not None and len(sample_data[name]) < 5:
                    sample_data[name].add(str(val))
    except Exception:
        pass  # If sampling fails, continue without it

    # ── Step 2: Null % and distinct count (batch, max 5 cols to stay cheap) ──
    stats = {}
    try:
        # Only profile first 5 columns to keep query cost low
        probe_cols = col_names[:5]
        count_exprs = []
        for name in probe_cols:
            count_exprs.append(
                f'COUNT(DISTINCT "{name}") AS dist_{name.lower()}, '
                f'SUM(CASE WHEN "{name}" IS NULL THEN 1 ELSE 0 END) AS nulls_{name.lower()}'
            )
        expr_block = ", ".join(count_exprs)
        total_expr = f"COUNT(*) AS total_rows, {expr_block}"

        cur = conn.cursor()
        cur.execute(f"SELECT {total_expr} FROM {fq_table}")
        row = cur.fetchone()

        if row:
            total_rows = row[0] or 1
            idx = 1
            for name in probe_cols:
                distinct = row[idx]
                nulls    = row[idx + 1]
                stats[name] = {
                    "distinct_count": int(distinct) if distinct is not None else None,
                    "null_pct": round((nulls / total_rows) * 100, 1) if nulls is not None else None,
                }
                idx += 2
    except Exception:
        pass  # Stats query failed — not critical

    # ── Merge results ─────────────────────────────────────────────────────────
    for name in col_names:
        result[name] = {
            "sample_values":  list(sample_data.get(name, set())),
            "distinct_count": stats.get(name, {}).get("distinct_count"),
            "null_pct":       stats.get(name, {}).get("null_pct"),
        }

    return result
