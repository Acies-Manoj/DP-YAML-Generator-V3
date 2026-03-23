"""
description_ui.py — Streamlit UI for the Description Engine.

UI shows:
  - Provider label (read-only, from config)
  - Model dropdown
  - Profiling / cache toggles
  - Optional business context input
  - Generate All button with progress bar
  - Per-table editable description results
"""

import streamlit as st
from .description_generator import generate_descriptions, generate_descriptions_multi, clear_cache
from . import config


def get_available_models() -> list[str]:
    """Return the list of available models based on configured provider."""
    if config.PROVIDER == "groq":
        return config.GROQ_MODELS
    elif config.PROVIDER == "ollama":
        return config.OLLAMA_MODELS
    return []


def get_model_config(selected_model: str) -> dict:
    """
    Build model_config dict using provider + key from config.py
    and the model selected in the UI.

    Args:
        selected_model: Model name string chosen in the UI dropdown.

    Returns:
        model_config dict for passing to generate_descriptions().
    """
    if config.PROVIDER == "groq":
        return {
            "provider": "groq",
            "api_key":  config.GROQ_API_KEY,
            "model":    selected_model,
        }
    elif config.PROVIDER == "ollama":
        return {
            "provider": "ollama",
            "model":    selected_model,
            "base_url": config.OLLAMA_BASE_URL,
        }
    raise ValueError(f"Unknown provider in config.py: '{config.PROVIDER}'")


def render_description_panel(
    tables:     list[dict],
    conn=None,
    database:   str = "",
    schema:     str = "",
    key_prefix: str = "cadp_desc",
) -> dict:
    """
    Render the full description generation panel for the CADP Step 2 flow.

    Shows:
      - Provider label (read-only, from config)
      - Model dropdown (only UI input)
      - Profiling toggle
      - Generate All button with progress bar
      - Per-table editable description results

    Args:
        tables:     List of {"name": str, "columns": [...]} dicts built from bundle_tables.
        conn:       Optional active Snowflake connection for profiling + real PK/FK.
        database:   Snowflake database name.
        schema:     Snowflake schema name.
        key_prefix: Unique prefix for session state keys.

    Returns:
        Dict keyed by table name with description results, or {} if not yet generated.
        {
            "TABLE_NAME": {
                "table_description": str,
                "columns": [{"name": str, "description": str}, ...]
            },
            ...
        }
    """
    results_key = f"{key_prefix}_results"

    # ── Provider info (read-only) ─────────────────────────────────────────────
    provider_label = "Groq (Free Cloud API)" if config.PROVIDER == "groq" else "Ollama (Local)"
    st.caption(f"Provider: **{provider_label}** — configured in `utils/description_engine/config.py`")

    # ── Model selector (only UI input) ───────────────────────────────────────
    available_models = get_available_models()
    default_model = (
        config.DEFAULT_GROQ_MODEL
        if config.PROVIDER == "groq"
        else config.DEFAULT_OLLAMA_MODEL
    )
    default_idx = available_models.index(default_model) if default_model in available_models else 0

    selected_model = st.selectbox(
        "Model",
        options=available_models,
        index=default_idx,
        key=f"{key_prefix}_model",
        help="Select which model to use for generating descriptions.",
    )



    # ── Optional profiling toggle ─────────────────────────────────────────────
    use_profiling = st.toggle(
        "Enable column profiling (sample values, null % from Snowflake)",
        value=False,
        key=f"{key_prefix}_profiling",
        help="Adds richer context to descriptions but runs extra Snowflake queries.",
    )

    use_cache = st.toggle(
        "Cache results (skip LLM for already-generated tables)",
        value=True,
        key=f"{key_prefix}_cache",
    )

    st.divider()

    # ── Business Context (optional) ───────────────────────────────────────────
    _ctx_key = f"{key_prefix}_user_context"

    st.markdown(
        """
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
            <span style="font-size:15px;">💡</span>
            <span style="font-size:13px; font-weight:600; color:#d1d5db;">Business Context</span>
            <span style="font-size:10px; font-weight:600; color:#6b7280;
                         background:#1f2937; border:1px solid #374151;
                         padding:2px 8px; border-radius:999px;
                         text-transform:uppercase; letter-spacing:0.05em;">
                Optional
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "Tell the LLM what this data actually represents. "
        "Especially useful when the table name doesn't reflect the content "
        "— e.g. `t_001`, `stg_xyz`, `tmp_final_v3`."
    )

    user_context_input = st.text_area(
        label="business_context_hidden",
        label_visibility="collapsed",
        placeholder=(
            "e.g. This table contains daily B2B sales orders from our Salesforce CRM pipeline. "
            "Each row represents one order line item with pricing, region, and fulfillment status."
        ),
        key=_ctx_key,
        max_chars=400,
        height=90,
        help="Max 400 characters. Leave blank to use default LLM behaviour based on column names only.",
    )

    _ctx_value = (user_context_input or "").strip()

    # Character counter + quick-fill examples when empty
    if _ctx_value:
        st.caption(f"✅ Context active — {len(_ctx_value)}/400 characters")
    else:
        st.caption("No context provided — LLM will infer from column names and types only.")
        st.markdown(
            "<div style='font-size:11px; color:#4b5563; margin-top:4px; margin-bottom:4px;'>"
            "QUICK EXAMPLES — click to copy into the box above:"
            "</div>",
            unsafe_allow_html=True,
        )
        _examples = [
            "B2B orders from Salesforce CRM",
            "Daily snapshot of inventory levels",
            "User clickstream events from mobile app",
            "Financial transactions in USD",
        ]
        _ex_cols = st.columns(len(_examples))
        for _col, _ex in zip(_ex_cols, _examples):
            with _col:
                st.code(_ex, language=None)

    st.divider()

    # ── Generate All button ───────────────────────────────────────────────────
    _btn_label = (
        f"✨ Generate Descriptions for All {len(tables)} Table(s)"
        + (" · with context" if _ctx_value else "")
    )

    col_gen, col_clear = st.columns([3, 1])

    with col_gen:
        generate_clicked = st.button(
            _btn_label,
            key=f"{key_prefix}_gen_all",
            type="primary",
            use_container_width=True,
            help="Context will be sent to the LLM along with column metadata." if _ctx_value else None,
        )

    with col_clear:
        if st.button("🗑️ Clear Cache", key=f"{key_prefix}_clear", use_container_width=True):
            count = clear_cache()
            st.session_state.pop(results_key, None)
            st.success(f"Cleared {count} cached entries.")

    if generate_clicked:
        model_config  = get_model_config(selected_model)
        progress_bar  = st.progress(0)
        status_text   = st.empty()

        def _progress(current, total, table_name):
            if total > 0:
                progress_bar.progress(current / total)
            if table_name != "done":
                status_text.text(f"Generating: {table_name} ({current + 1}/{total})")
            else:
                status_text.text("✅ All done!")

        try:
            results = generate_descriptions_multi(
                tables=tables,
                model_config=model_config,
                conn=conn,
                database=database,
                schema=schema,
                use_profiling=use_profiling,
                use_cache=use_cache,
                progress_cb=_progress,
                user_context=_ctx_value or None,   # ← pass context; None = default behaviour
            )
            st.session_state[results_key] = results

            errors = [name for name, r in results.items() if r.get("error")]
            if errors:
                st.warning(f"Completed with errors on: {', '.join(errors)}. Check your API key or model.")
            else:
                _success_note = " (with your business context)" if _ctx_value else ""
                st.success(
                    f"Descriptions ready for {len(tables)} table(s){_success_note}. "
                    "Review and edit below, then click 'Auto-fill Descriptions'."
                )

        except Exception as e:
            if "api_key" in str(e).lower() or "authentication" in str(e).lower():
                st.error(
                    f"API key error: {e}\n\n"
                    "Open `utils/description_engine/config.py` and set your GROQ_API_KEY."
                )
            else:
                st.error(f"Generation failed: {e}")

    # ── Editable results per table ────────────────────────────────────────────
    results = st.session_state.get(results_key, {})

    if results:
        st.markdown("#### ✏️ Review & Edit Generated Descriptions")
        st.caption(
            "These descriptions will be auto-filled into the YAML. "
            "You can still override any field manually in the Table YAML form below."
        )

        edited_key = f"{key_prefix}_edited"
        if edited_key not in st.session_state:
            st.session_state[edited_key] = {}

        for tbl in tables:
            tbl_name = tbl["name"]
            tbl_result = results.get(tbl_name)
            if not tbl_result:
                continue

            with st.expander(f"📋 `{tbl_name}`", expanded=False):
                if tbl_result.get("error"):
                    st.error(f"Failed: {tbl_result['error']}")
                    continue

                # Editable table description
                edited_tbl_desc = st.text_area(
                    "Table Description",
                    value=tbl_result.get("table_description", ""),
                    key=f"{key_prefix}_td_{tbl_name}",
                    height=70,
                )

                # Editable column descriptions
                st.markdown("**Column Descriptions**")
                col_desc_map = {
                    c["name"]: c.get("description", "")
                    for c in tbl_result.get("columns", [])
                }

                edited_cols = []
                for col in tbl["columns"]:
                    col_name = col.get("name", "")
                    new_desc = st.text_input(
                        label=f"`{col_name}`",
                        value=col_desc_map.get(col_name, ""),
                        key=f"{key_prefix}_cd_{tbl_name}_{col_name}",
                    )
                    edited_cols.append({"name": col_name, "description": new_desc})

                # Save edits back to session state
                st.session_state[edited_key][tbl_name] = {
                    "table_description": edited_tbl_desc,
                    "columns":           edited_cols,
                }

        # Merge edits back into results
        for tbl_name, edits in st.session_state.get(edited_key, {}).items():
            if tbl_name in results:
                results[tbl_name].update(edits)
        st.session_state[results_key] = results

    return results