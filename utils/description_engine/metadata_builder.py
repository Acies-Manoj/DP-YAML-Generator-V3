"""
metadata_builder.py — Builds a structured metadata object from raw schema data.
This isolates schema logic from LLM prompt logic.
Supports real PK/FK data from Snowflake if available, with name-based heuristics as fallback.
"""

# Patterns that suggest a column is a primary or foreign key
_PK_PATTERNS = ("_id", "_key", "_code", "_pk", "_uuid", "_guid")
_FK_PATTERNS = ("_id", "_fk", "_ref", "_key")
_EXACT_PK    = {"id", "uuid", "guid", "pk"}


def _likely_pk(col_name: str) -> bool:
    """Heuristic: column name suggests it is a primary key."""
    name = col_name.lower()
    return name in _EXACT_PK or name.startswith("id_") or any(name.endswith(p) for p in _PK_PATTERNS)


def _likely_fk(col_name: str, is_pk: bool) -> bool:
    """Heuristic: column name suggests it is a foreign key (only if not already PK)."""
    if is_pk:
        return False
    name = col_name.lower()
    return any(name.endswith(p) for p in _FK_PATTERNS)


def build_metadata(
    table_name: str,
    columns: list[dict],
    real_pks: list[str] | None = None,
    real_fks: list[str] | None = None,
    profiling_data: dict | None = None,
) -> dict:
    """
    Build structured metadata object for LLM consumption.

    Args:
        table_name:     Name of the table.
        columns:        List of column dicts with keys: name, data_type, is_nullable.
        real_pks:       Optional list of real PK column names from Snowflake SHOW PRIMARY KEYS.
        real_fks:       Optional list of real FK column names from Snowflake SHOW IMPORTED KEYS.
        profiling_data: Optional dict from profiler.py keyed by column name.

    Returns:
        Structured dict ready to pass into prompt_builder.
    """
    real_pks = [p.upper() for p in (real_pks or [])]
    real_fks = [f.upper() for f in (real_fks or [])]
    profiling_data = profiling_data or {}

    built_columns = []
    for col in columns:
        name       = col.get("name", "")
        data_type  = col.get("data_type", "UNKNOWN")
        nullable   = col.get("is_nullable", True)

        # Use real constraint data if available, else fall back to heuristics
        if real_pks or real_fks:
            is_pk = name.upper() in real_pks
            is_fk = name.upper() in real_fks
        else:
            is_pk = _likely_pk(name)
            is_fk = _likely_fk(name, is_pk)

        # Merge profiling data if available
        prof = profiling_data.get(name, {})

        built_columns.append({
            "name":           name,
            "data_type":      data_type,
            "nullable":       nullable,
            "is_pk":          is_pk,
            "is_fk":          is_fk,
            "sample_values":  prof.get("sample_values", []),
            "distinct_count": prof.get("distinct_count", None),
            "null_pct":       prof.get("null_pct", None),
        })

    return {
        "table_name": table_name,
        "columns":    built_columns,
    }
