"""
description_generator.py — Main orchestrator for the Description Engine.

This is the ONLY file that other modules (CADP flow, YAML builders) import.
All internal logic is hidden behind generate_descriptions().

Usage:
    from utils.description_engine import generate_descriptions

    result = generate_descriptions(
        table_name="ORDERS",
        columns=extracted_columns,
        model_config={"provider": "groq", "api_key": "gsk_...", "model": "llama3-8b-8192"},
        conn=snowflake_conn,          # optional
        database="MY_DB",             # required if conn provided
        schema="MY_SCHEMA",           # required if conn provided
        use_profiling=False,
        use_cache=True,
    )

    # result shape:
    # {
    #   "table_description": "A table storing ...",
    #   "columns": [
    #     {"name": "ORDER_ID", "description": "Primary key uniquely identifying each order."},
    #     ...
    #   ]
    # }
"""

from .metadata_builder  import build_metadata
from .prompt_builder    import build_prompt
from .llm_client        import call_llm
from .cache             import DescriptionCache
from .profiler          import profile_table, get_pk_fk_info


_cache = DescriptionCache()


def generate_descriptions(
    table_name:    str,
    columns:       list[dict],
    model_config:  dict,
    conn=None,
    database:      str = "",
    schema:        str = "",
    use_profiling: bool = False,
    use_cache:     bool = True,
    user_context:  str = None,
) -> dict:
    """
    Generate table and column descriptions using an LLM.

    Args:
        table_name:    Name of the table (used in prompt + cache key).
        columns:       List of dicts from schema_extractor:
                       [{"name": str, "data_type": str, "is_nullable": bool}, ...]
        model_config:  LLM provider config dict.
                       Groq:   {"provider": "groq", "api_key": "gsk_...", "model": "llama3-8b-8192"}
                       Ollama: {"provider": "ollama", "model": "mistral", "base_url": "http://localhost:11434"}
        conn:          Optional active Snowflake connection (needed for profiling + real PK/FK).
        database:      Snowflake database name (required if conn is provided).
        schema:        Snowflake schema name (required if conn is provided).
        use_profiling: If True and conn is provided, run lightweight table profiling.
        use_cache:     If True, check/write file cache to avoid re-calling LLM.
        user_context:  Optional plain-text business context about the table/data.
                       When provided, injected into the LLM prompt to improve accuracy.
                       Useful when table names are cryptic (e.g. t_001, stg_xyz).
                       Pass None (default) to use standard column-name-only behaviour.

    Returns:
        Dict with:
        {
            "table_description": str,
            "columns": [{"name": str, "description": str}, ...]
        }

    Raises:
        ValueError:   If LLM returns invalid JSON after retries.
        RuntimeError: If LLM API call fails.
    """

    # ── Step 1: Check cache ───────────────────────────────────────────────────
    # Cache key includes user_context so context-specific calls never return
    # a stale context-free (or differently-contextualised) cached result.
    if use_cache:
        cached = _cache.get(table_name, columns, user_context=user_context)
        if cached:
            return cached

    # ── Step 2: Get real PK/FK from Snowflake if connection available ─────────
    real_pks, real_fks = [], []
    if conn and database and schema:
        try:
            constraints = get_pk_fk_info(conn, database, schema, table_name)
            real_pks    = constraints.get("pk_columns", [])
            real_fks    = constraints.get("fk_columns", [])
        except Exception:
            pass  # Fall back to heuristics silently

    # ── Step 3: Optional profiling ────────────────────────────────────────────
    profiling_data = {}
    if use_profiling and conn and database and schema:
        try:
            profiling_data = profile_table(conn, database, schema, table_name, columns)
        except Exception:
            pass  # Profiling is optional — never block description generation

    # ── Step 4: Build metadata object ────────────────────────────────────────
    metadata = build_metadata(
        table_name=table_name,
        columns=columns,
        real_pks=real_pks,
        real_fks=real_fks,
        profiling_data=profiling_data,
    )

    # ── Step 5: Build prompt ──────────────────────────────────────────────────
    prompt = build_prompt(metadata, user_context=user_context)

    # ── Step 6: Call LLM ──────────────────────────────────────────────────────
    result = call_llm(prompt, model_config)

    # ── Step 7: Save to cache ─────────────────────────────────────────────────
    if use_cache:
        _cache.set(table_name, columns, result, user_context=user_context)

    return result


def generate_descriptions_multi(
    tables:        list[dict],
    model_config:  dict,
    conn=None,
    database:      str = "",
    schema:        str = "",
    use_profiling: bool = False,
    use_cache:     bool = True,
    progress_cb=None,
    user_context:  str = None,
) -> dict:
    """
    Generate descriptions for multiple tables in one call.
    Useful for batch processing in CADP flow.

    Args:
        tables:       List of dicts: [{"name": str, "columns": [...]}, ...]
        progress_cb:  Optional callback(current, total, table_name) for Streamlit progress bar.
        user_context: Optional plain-text business context shared across all tables in this call.
                      Pass None to use standard column-name-only behaviour.

    Returns:
        Dict keyed by table name: {"TABLE_NAME": {description result}, ...}
    """
    results = {}
    total   = len(tables)

    for i, tbl in enumerate(tables):
        table_name = tbl["name"]
        columns    = tbl.get("columns", [])

        if progress_cb:
            progress_cb(i, total, table_name)

        try:
            results[table_name] = generate_descriptions(
                table_name=table_name,
                columns=columns,
                model_config=model_config,
                conn=conn,
                database=database,
                schema=schema,
                use_profiling=use_profiling,
                use_cache=use_cache,
                user_context=user_context,
            )
        except Exception as e:
            # On failure for one table, store error and continue with rest
            results[table_name] = {
                "table_description": f"[Description generation failed: {e}]",
                "columns": [
                    {"name": c.get("name", ""), "description": ""}
                    for c in columns
                ],
                "error": str(e),
            }

    if progress_cb:
        progress_cb(total, total, "done")

    return results


def clear_cache() -> int:
    """Clear all cached descriptions. Returns count of deleted entries."""
    return _cache.clear_all()