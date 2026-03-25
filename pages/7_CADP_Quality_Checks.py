"""
CADP Quality Checks
════════════════════
Quality checks page for the Consumer-Aligned Data Product flow.

Columns come entirely from bundle_tables (Table YAML step) — no Snowflake needed.
Every dim's name, type, primary_key, and description is already captured there.
The LLM automatically receives table + column descriptions from the Semantic Model.
"""

import streamlit as st
import json
import sys, os
import pandas as pd
import copy

from utils.qc_learning.qc_diff_engine import detect_new_rules
from utils.qc_learning.save_learning import save_reference_rules

@st.cache_data
def read_excel_cached(file):
    return pd.read_excel(file)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.ui_utils import load_global_css, section_header, app_footer
from utils.default_checks import generate_default_checks
from utils.llm_checks import call_llm
from utils.sf_utils import fetch_full_context, fetch_schema_overview
from utils.qc_yaml_generator import generate_qc_yaml
from utils.qc_config import PROVIDER, GROQ_DEFAULT_MODEL, OLLAMA_DEFAULT_MODEL

st.set_page_config(page_title="CADP — Quality Checks", page_icon="✅", layout="wide")
load_global_css()

# ─────────────────────────────────────────────────────────────────────────────
# SM type → Snowflake-style type (needed by default_checks is_string/is_timestamp)
# ─────────────────────────────────────────────────────────────────────────────
_SM_TO_SF = {
    "string":  "VARCHAR",
    "number":  "NUMBER",
    "boolean": "BOOLEAN",
    "time":    "TIMESTAMP_NTZ",
    "date":    "DATE",
}

def build_ctx_from_bundle_table(tbl: dict) -> dict:
    """
    Build a ctx dict from a bundle_table entry (Table YAML step).
    Matches the shape expected by generate_default_checks() and call_llm().

    All profiling fields (null_pct, sample_values, avg_length, etc.) are None/[]
    because we have no live Snowflake connection — default_checks handles this
    gracefully (those rules simply don't fire without profiling data).
    """
    cols = []
    for d in tbl.get("dims", []):
        name = d.get("name", "").strip()
        if not name:
            continue
        sm_type = d.get("type", "string")
        sf_type = _SM_TO_SF.get(sm_type, "VARCHAR")
        is_pk = d.get("primary_key", False) or name.lower().endswith("_id")

        desc = d.get("description", "").lower()
        col_lower = name.lower()

        is_enum = any(
            k in col_lower or k in desc
            for k in [
                "status","type","code","category","region",
                "segment","group","flag","level","class",
                "state","country","market","zone","area"
                ]
        )

        cols.append({
            "name": name,
            "sf_type": sf_type,
            "soda_type": sm_type,
            "nullable": not is_pk,
            "is_pk": is_pk,
            "is_fk": False,
            "is_pk_inferred": False,
            "char_max_len": None,

            "min_val": None,
            "max_val": None,
            "avg_val": None,
            "null_count": None,
            "null_pct": None,
            "distinct_count": None,

            # simulate profiling
            "avg_length": 10 if sm_type == "string" else None,
            "sample_values": [],

            "is_likely_enum": is_enum,

            "is_freshness_col": any(
                k in col_lower for k in [
                    "date","time","timestamp","period",
                    "created_at","updated_at","modified_at",
                    "loaded_at","ingested_at","refreshed_at"
                ]
            ),

            "description": d.get("description", "").strip(),
        })

    return {
        "table":             tbl.get("name", ""),
        "table_description": tbl.get("tbl_desc", "").strip(),
        "columns":           cols,
        "row_count":         None,
        "schema_overview":   {},
        "errors":            [],
    }

def merge_contexts(semantic_ctx, data_ctx):
    merged = copy.deepcopy(data_ctx)

    merged["table_description"] = semantic_ctx.get("table_description", "")

    sem_cols = {c["name"].lower(): c for c in semantic_ctx["columns"]}

    for col in merged["columns"]:
        name = col["name"]
        key = name.lower()

        if key in sem_cols:
            col["description"] = sem_cols[key].get("description", "")

            if sem_cols[key].get("is_likely_enum"):
                col["is_likely_enum"] = True

        # 🔥 ADD THIS BLOCK HERE (CORRECT PLACE)
        if col.get("distinct_count") and merged.get("row_count") and merged["row_count"] > 0:
            ratio = col["distinct_count"] / merged["row_count"]

            if ratio < 0.1 and col["distinct_count"] < 50:
                col["is_likely_enum"] = True

    return merged
# ─────────────────────────────────────────────────────────────────────────────
CATEGORIES = [
    ("Schema",       "🔷", "#1e3a5f", "#93c5fd"),
    ("Completeness", "🟢", "#14532d", "#86efac"),
    ("Uniqueness",   "🟣", "#3b0764", "#d8b4fe"),
    ("Freshness",    "🟡", "#78350f", "#fcd34d"),
    ("Validity",     "🩷", "#4a1d4a", "#f9a8d4"),
    ("Accuracy",     "🩵", "#134e4a", "#6ee7b7"),
]
CAT_NAMES = [c[0] for c in CATEGORIES]

_QC_DEFAULTS = {
    "cadp_qc_sel_table": "",
    "cadp_qc_ctx": None, "cadp_qc_default_checks": [], "cadp_qc_llm_suggestions": [],
    "cadp_qc_accepted_defaults": {}, "cadp_qc_accepted_llm": {},
    "cadp_qc_show_manual_form": False,
    "cadp_qc_llm_done": False, "cadp_qc_llm_error": None, "cadp_qc_llm_sm_injected": False,
    "cadp_qc_wf_name": "", "cadp_qc_wf_desc": "", "cadp_qc_wf_depot": "",
    "cadp_qc_wf_workspace": "public", "cadp_qc_wf_engine": "", "cadp_qc_wf_cluster": "",
    "cadp_qc_wf_tag_domain": "", "cadp_qc_wf_tag_usecase": "",
    "cadp_qc_wf_tag_tier": "Consumer Aligned",
    "cadp_qc_wf_tag_region": "", "cadp_qc_wf_tag_dataos": "", "cadp_qc_wf_tag_custom": "",
    "cadp_qc_last_yaml": None, "cadp_qc_last_yaml_name": "",
}
# ── QC Progress Tracker ─────────────────────────────────────────────
if "cadp_qc_generated_tables" not in st.session_state:
    st.session_state.cadp_qc_generated_tables = set()

# Store all generated QC YAMLs (one per table)
if "cadp_qc_all_yaml" not in st.session_state:
    st.session_state.cadp_qc_all_yaml = {}

for k, v in _QC_DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def _manual_key():
    return f"cadp_qc_manual_{st.session_state.get('cadp_qc_sel_table', '')}"

def _accepted_manual_key():
    return f"cadp_qc_acc_manual_{st.session_state.get('cadp_qc_sel_table', '')}"

def reset_table_state():
    for k in ["cadp_qc_ctx", "cadp_qc_default_checks", "cadp_qc_llm_suggestions",
              "cadp_qc_accepted_defaults", "cadp_qc_accepted_llm",
              "cadp_qc_llm_done", "cadp_qc_llm_error", "cadp_qc_llm_sm_injected",
              "cadp_qc_last_yaml", "cadp_qc_last_yaml_name"]:
        st.session_state[k] = _QC_DEFAULTS.get(k, None) or (
            [] if "checks" in k or "suggestions" in k
            else {} if "accepted" in k
            else None
        )

def checks_by_category(checks):
    out = {cat: [] for cat in CAT_NAMES}
    for i, chk in enumerate(checks):
        cat = chk.get("category", "Schema")
        if cat in out:
            out[cat].append((i, chk))
    return out

def syntax_preview(chk):
    s = chk.get("syntax", "")
    body = chk.get("body") or {}
    if s == "schema":
        if "warn" in body:
            cols = body["warn"].get("when required column missing", [])
            snip = ", ".join(str(c) for c in cols[:4])
            more = f" ... +{len(cols)-4}" if len(cols) > 4 else ""
            return f"schema: warn when required column missing: [{snip}{more}]"
        if "fail" in body:
            n = len(body["fail"].get("when wrong column type", {}))
            return f"schema: fail when wrong column type: ({n} columns)"
    parts = [s]
    for k, v in body.items():
        parts.append(f"  {k}: {v}")
    return "\n".join(parts)

# ── Header + Nav ──────────────────────────────────────────────────────────────
st.markdown("## ✅ Quality Checks")
st.markdown(
    '<p style="color:#6b7280;font-size:13px;margin-top:-8px;">'
    'Columns and descriptions loaded from your Table YAML — no Snowflake needed. '
    'Generate checks, review LLM suggestions, and export YAML.'
    '</p>', unsafe_allow_html=True,
)
nav_l, _, nav_r = st.columns([1, 4, 1.5])
with nav_l:
    if st.button("← Back"):
        st.switch_page("pages/cadp_flow.py")
with nav_r:
    if st.button("🔄 Start Over"):
        for k in list(_QC_DEFAULTS.keys()):
            st.session_state[k] = _QC_DEFAULTS[k]
        st.rerun()

model_label = GROQ_DEFAULT_MODEL if PROVIDER == "groq" else OLLAMA_DEFAULT_MODEL
st.markdown(
    f'<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;'
    f'padding:8px 14px;font-size:12px;color:#6b7280;margin:8px 0;">'
    f'⚙️ LLM Provider: <b style="color:#d1d5db">{PROVIDER.upper()}</b> &nbsp;|&nbsp; '
    f'Model: <b style="color:#d1d5db">{model_label}</b> &nbsp;|&nbsp; '
    f'Edit in <b style="color:#d1d5db">utils/qc_config.py</b></div>',
    unsafe_allow_html=True,
)
st.divider()

# ── ① Table Picker — from bundle_tables (Table YAML) ─────────────────────────
section_header("🗂️", "Select Table from Semantic Model")

_bundle_tbls = [
    t for t in st.session_state.get("bundle_tables", [])
    if t.get("name", "").strip() and t.get("dims")
]

if not _bundle_tbls:
    st.error(
        "No tables found. Please complete **Step 2 — Table YAML** in the Semantic Model first."
    )
    st.stop()

_tbl_names = []
for t in _bundle_tbls:
    name = t["name"]
    if name in st.session_state.cadp_qc_generated_tables:
        name = f"✅ {name}"
    _tbl_names.append(name)
_saved = st.session_state.cadp_qc_sel_table
_clean_names = [n.replace("✅ ", "") for n in _tbl_names]

if _saved in _clean_names:
    _sel_idx = _clean_names.index(_saved)
else:
    # auto-pick first unprocessed table
    remaining = [t for t in _clean_names if t not in st.session_state.cadp_qc_generated_tables]
    _sel_idx = _clean_names.index(remaining[0]) if remaining else 0

_sel_name = st.selectbox("Table", _tbl_names, index=_sel_idx, key="cadp_qc_tbl_select")
_sel_name = _sel_name.replace("✅ ", "")

# Rebuild ctx whenever the selection changes
if _sel_name != st.session_state.cadp_qc_sel_table:
    st.session_state.cadp_qc_sel_table = _sel_name
    reset_table_state()

if not st.session_state.cadp_qc_ctx:
    _matched = next((t for t in _bundle_tbls if t["name"] == _sel_name), None)
    if _matched:
        # Try existing connections first
        conn = (
            st.session_state.get("sf_conn") or
            st.session_state.get("sadp_qc_sf_conn")
        )

        # If no connection yet, try to create one from Depot credentials
        if not conn:
            _acct = st.session_state.get("depot_account")
            _user = st.session_state.get("depot_username")
            _pw   = st.session_state.get("depot_password")
            _wh   = st.session_state.get("depot_warehouse", "")

            if _acct and _user and _pw:
                try:
                    from utils.sf_utils import connect
                    conn = connect(_acct, _user, _pw, warehouse=_wh)
                    st.session_state["sf_conn"] = conn
                except Exception as e:
                    st.warning(f"⚠️ Could not connect to Snowflake using Depot credentials: {e}")
                    conn = None

        if conn:
            try:
                db = (
                    st.session_state.get("selected_db") or
                    st.session_state.get("sadp_qc_sf_last_db") or
                    st.session_state.get("depot_database")
                )
                schema = (
                    st.session_state.get("selected_schema") or
                    st.session_state.get("sadp_qc_sf_last_schema")
                )

                # 🔥 Fetch real data profiling (SADP logic)
                data_ctx = fetch_full_context(conn, db, schema, _sel_name)
                if not data_ctx.get("row_count"):           
                    data_ctx["row_count"] = 100000  # fallback
                data_ctx["schema_overview"] = fetch_schema_overview(conn, db, schema)

                # 🔥 Build semantic context (CADP logic)
                semantic_ctx = build_ctx_from_bundle_table(_matched)

                # 🔥 Merge both
                _ctx = merge_contexts(semantic_ctx, data_ctx)

                st.success("🔥 QC Mode: Hybrid (Data + Semantic)")

            except Exception as e:
                st.warning(f"⚠️ Falling back to metadata-only: {e}")
                _ctx = build_ctx_from_bundle_table(_matched)

        else:
            _ctx = build_ctx_from_bundle_table(_matched)
        st.session_state.cadp_qc_ctx = _ctx
        _defs = generate_default_checks(_ctx)
        for _chk in _defs:
            _chk["_original"] = {
                "name":   _chk.get("name"),
                "syntax": _chk.get("syntax"),
                "body":   json.dumps(_chk.get("body"), sort_keys=True),
            }
        st.session_state.cadp_qc_default_checks    = _defs
        st.session_state.cadp_qc_accepted_defaults = {i: True for i in range(len(_defs))}
        st.session_state["generated_qc_checks"] = copy.deepcopy(_defs)

if not st.session_state.cadp_qc_ctx:
    st.stop()

ctx = st.session_state.cadp_qc_ctx
_n_cols = len(ctx["columns"])
_has_sm_desc = bool(
    ctx.get("table_description") or
    any(c.get("description", "").strip() for c in ctx["columns"])
)

st.info(
    f"✅ **{_sel_name}** — {_n_cols} columns loaded from Table YAML."
    + (" · Semantic Model descriptions available for LLM. ✨" if _has_sm_desc else "")
)
if st.session_state.get("sf_conn"):
    st.caption("🔍 Using Snowflake data for realistic QC generation")
else:
    st.caption("🧠 Using semantic model only (no data access)")
# ── QC Progress Display ─────────────────────────────────────────────
all_tables = [t["name"] for t in _bundle_tbls]
done_tables = st.session_state.cadp_qc_generated_tables
remaining_tables = [t for t in all_tables if t not in done_tables]

st.markdown(f"""
📊 **QC Progress**
- ✅ Completed: {len(done_tables)} / {len(all_tables)}
- ⏳ Remaining: {len(remaining_tables)}
""")

if remaining_tables:
    st.caption("Remaining tables: " + ", ".join(remaining_tables))

if len(done_tables) == len(all_tables):
    st.success("🎉 All QC files generated!")

# ── ② Checks Review ───────────────────────────────────────────────────────────
st.divider()
section_header("🔍", f"Quality Checks — {ctx['table']}")
st.caption(f"📊 {_n_cols} columns loaded from Semantic Model")

with st.expander("🧠 Upload Metadata to override/augment LLM context (optional)"):
    uploaded_meta = st.file_uploader(
        "Upload Excel with table & column descriptions",
        type=["xlsx"], key="cadp_qc_meta_upload",
    )
    semantic_metadata = None
    if uploaded_meta:
        try:
            df_meta = pd.read_excel(uploaded_meta)
            required = {"table_name", "table_description", "column_name", "column_description"}
            if not required.issubset(set(df_meta.columns)):
                st.error("Excel format invalid — required columns missing.")
            else:
                semantic_metadata = df_meta
                st.success(f"✅ {len(df_meta)} metadata rows loaded.")
        except Exception as e:
            st.error(f"Failed to read metadata: {e}")

st.markdown(" ")

# ── LLM controls ──────────────────────────────────────────────────────────────
_use_sm_desc = False
if _has_sm_desc:
    _use_sm_desc = st.toggle(
        "📝 Send Semantic Model descriptions to LLM",
        value=True,
        help="Table and column descriptions from your Semantic Model will be sent to the LLM "
             "for more accurate, domain-aware check suggestions. "
             "Turn off to let the LLM reason from column names and types only.",
    )

llm_c1, llm_c2 = st.columns([4, 1])
with llm_c1:
    llm_label = "✨ Generate LLM Suggestions" if not st.session_state.cadp_qc_llm_done else "🔄 Re-run LLM Suggestions"
    run_llm = st.button(llm_label, type="primary", use_container_width=True)
with llm_c2:
    if st.button("Clear LLM", use_container_width=True):
        st.session_state.cadp_qc_llm_suggestions = []
        st.session_state.cadp_qc_accepted_llm    = {}
        st.session_state.cadp_qc_llm_done        = False
        st.session_state.cadp_qc_llm_error       = None
        st.rerun()

if run_llm and not st.session_state.cadp_qc_llm_done:
    with st.spinner("Calling LLM..."):
        try:
            print("🚀 LLM button clicked — entering call block")
            ctx_for_llm = ctx.copy()
            ctx_for_llm["columns"] = [c.copy() for c in ctx["columns"]]

            _sm_injected = False

            if _has_sm_desc and _use_sm_desc:
                _sm_injected = True          # descriptions already in ctx
            elif _has_sm_desc and not _use_sm_desc:
                ctx_for_llm["table_description"] = ""
                for c in ctx_for_llm["columns"]:
                    c["description"] = ""

            # Optional Excel override
            if semantic_metadata is not None:
                tbl_rows = semantic_metadata[semantic_metadata["table_name"] == ctx["table"]]
                if not tbl_rows.empty:
                    ctx_for_llm["table_description"] = tbl_rows.iloc[0]["table_description"]
                    col_desc = dict(zip(tbl_rows["column_name"], tbl_rows["column_description"]))
                    for col in ctx_for_llm["columns"]:
                        col["description"] = col_desc.get(col["name"], "")
                    _sm_injected = True

            try:
                suggs = call_llm(ctx_for_llm, st.session_state.cadp_qc_default_checks)
            except RuntimeError as e:
                st.session_state.cadp_qc_llm_error = str(e)
                st.rerun()
            for chk in suggs:
                chk["_original"] = {
                    "name":   chk.get("name"),
                    "syntax": chk.get("syntax"),
                    "body":   json.dumps(chk.get("body"), sort_keys=True),
                }
            st.session_state.cadp_qc_llm_suggestions  = suggs
            generated_all = st.session_state.cadp_qc_default_checks + suggs
            st.session_state["generated_qc_checks"] = copy.deepcopy(generated_all)
            st.session_state.cadp_qc_accepted_llm     = {i: False for i in range(len(suggs))}
            st.session_state.cadp_qc_llm_done         = True
            st.session_state.cadp_qc_llm_error        = None
            st.session_state.cadp_qc_llm_sm_injected  = _sm_injected
        except Exception as e:
            st.session_state.cadp_qc_llm_error = str(e)
    st.rerun()

if st.session_state.cadp_qc_llm_error:
    st.error(f"LLM error: {st.session_state.cadp_qc_llm_error}")
    st.caption("Check your API key in utils/qc_config.py")
if st.session_state.cadp_qc_llm_done and st.session_state.cadp_qc_llm_suggestions:
    _note = " · enriched with Semantic Model descriptions ✨" if st.session_state.cadp_qc_llm_sm_injected else ""
    st.success(f"✅ {len(st.session_state.cadp_qc_llm_suggestions)} LLM suggestions ready{_note} — tick what you want to include.")

# ── Category buckets ──────────────────────────────────────────────────────────
def_by_cat    = checks_by_category(st.session_state.cadp_qc_default_checks)
llm_by_cat    = checks_by_category(st.session_state.cadp_qc_llm_suggestions)
manual_key    = _manual_key()
acc_man_key   = _accepted_manual_key()
manual_checks = st.session_state.get(manual_key, [])
acc_manual    = st.session_state.get(acc_man_key, {})
manual_by_cat = checks_by_category(manual_checks)

for cat_name, icon, bg_color, text_color in CATEGORIES:
    def_items    = def_by_cat.get(cat_name, [])
    llm_items    = llm_by_cat.get(cat_name, [])
    manual_items = manual_by_cat.get(cat_name, [])
    if not def_items and not llm_items and not manual_items:
        continue
    total_checks   = len(def_items) + len(llm_items) + len(manual_items)
    accepted_count = (
        sum(1 for i, _ in def_items    if st.session_state.cadp_qc_accepted_defaults.get(i, True)) +
        sum(1 for i, _ in llm_items    if st.session_state.cadp_qc_accepted_llm.get(i, False)) +
        sum(1 for i, _ in manual_items if acc_manual.get(i, True))
    )
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;padding:10px 16px;'
        f'border-radius:8px 8px 0 0;margin-top:18px;background:{bg_color};">'
        f'{icon} <span style="color:{text_color};font-weight:700;font-size:15px;">{cat_name}</span>'
        f'<span style="color:{text_color};opacity:0.7;font-size:12px;margin-left:8px;">'
        f'{accepted_count}/{total_checks} selected</span></div>', unsafe_allow_html=True,
    )
    with st.container():
        if def_items:
            st.markdown('<span style="font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Default Checks</span>', unsafe_allow_html=True)
            for idx, chk in def_items:
                col_chk, col_acc = st.columns([0.5, 9.5])
                with col_acc:
                    with st.expander(f"[DEFAULT] {chk['col'] or 'table-level'} — {chk['name'][:80]}", expanded=False):
                        st.markdown('<span style="font-size:10px;font-weight:700;background:#1e3a5f;color:#93c5fd;padding:1px 7px;border-radius:10px;">DEFAULT</span>', unsafe_allow_html=True)
                        st.code(syntax_preview(chk), language="yaml")
                        if chk.get("body"):
                            st.json(chk["body"])
                        new_syn  = st.text_area("Edit SodaCL condition", value=chk["syntax"], key=f"cadp_def_syn_{idx}", height=60)
                        st.session_state.cadp_qc_default_checks[idx]["syntax"] = new_syn
                        new_name = st.text_input("Check name", value=chk["name"], key=f"cadp_def_name_{idx}")
                        st.session_state.cadp_qc_default_checks[idx]["name"] = new_name
                        if chk.get("body") and chk["syntax"] != "schema":
                            body_str = st.text_area("body", value=json.dumps(chk["body"], indent=2), height=80, key=f"cadp_def_body_{idx}", label_visibility="collapsed")
                            try:
                                st.session_state.cadp_qc_default_checks[idx]["body"] = json.loads(body_str)
                            except Exception:
                                st.caption("⚠️ Invalid JSON — original body preserved")
                        orig = chk.get("_original", {})
                        if new_name != orig.get("name") or new_syn != orig.get("syntax"):
                            st.markdown("<span style='color:#facc15;font-weight:600;'>✏️ Modified</span>", unsafe_allow_html=True)
                with col_chk:
                    acc = st.checkbox("✓", value=st.session_state.cadp_qc_accepted_defaults.get(idx, True), key=f"cadp_def_acc_{idx}", label_visibility="collapsed")
                    st.session_state.cadp_qc_accepted_defaults[idx] = acc

        if llm_items:
            st.markdown('<span style="font-size:11px;color:#7c3aed;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">LLM Suggested</span>', unsafe_allow_html=True)
            for idx, chk in llm_items:
                col_chk, col_acc = st.columns([0.5, 9.5])
                with col_acc:
                    with st.expander(f"[LLM] {chk.get('col') or 'table-level'} — {chk.get('name','')[:80]}", expanded=False):
                        st.markdown('<span style="font-size:10px;font-weight:700;background:#3b0764;color:#d8b4fe;padding:1px 7px;border-radius:10px;">LLM SUGGESTION</span>', unsafe_allow_html=True)
                        if chk.get("reason"):
                            st.markdown(f'<div style="font-size:11px;color:#6b7280;font-style:italic;margin-top:4px;">💡 {chk["reason"]}</div>', unsafe_allow_html=True)
                        new_name = st.text_input("Check name", value=chk.get("name",""), key=f"cadp_llm_name_{idx}")
                        st.session_state.cadp_qc_llm_suggestions[idx]["name"] = new_name
                        new_syn  = st.text_area("Edit SodaCL condition", value=chk.get("syntax",""), key=f"cadp_llm_syn_{idx}", height=70)
                        st.session_state.cadp_qc_llm_suggestions[idx]["syntax"] = new_syn
                        if chk.get("body"):
                            body_str = st.text_area("body", value=json.dumps(chk["body"], indent=2), height=80, key=f"cadp_llm_body_{idx}", label_visibility="collapsed")
                            try:
                                st.session_state.cadp_qc_llm_suggestions[idx]["body"] = json.loads(body_str)
                            except Exception:
                                st.caption("⚠️ Invalid JSON")
                with col_chk:
                    acc = st.checkbox("✓", value=st.session_state.cadp_qc_accepted_llm.get(idx, False), key=f"cadp_llm_acc_{idx}", label_visibility="collapsed")
                    st.session_state.cadp_qc_accepted_llm[idx] = acc

        if manual_items:
            st.markdown('<span style="font-size:11px;color:#10b981;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Manual Checks</span>', unsafe_allow_html=True)
            for idx, chk in manual_items:
                col_chk, col_acc = st.columns([0.5, 9.5])
                with col_acc:
                    with st.expander(f"[MANUAL] {chk.get('col') or 'table-level'} — {chk['name'][:80]}", expanded=False):
                        st.markdown("<span style='color:#10b981;font-weight:700;'>🟢 MANUAL</span>", unsafe_allow_html=True)
                        new_name = st.text_input("Check name", value=chk["name"], key=f"cadp_man_name_{idx}")
                        manual_checks[idx]["name"] = new_name
                        new_syn  = st.text_area("Edit SodaCL condition", value=chk["syntax"], key=f"cadp_man_syn_{idx}", height=70)
                        manual_checks[idx]["syntax"] = new_syn
                with col_chk:
                    acc = st.checkbox("✓", value=acc_manual.get(idx, True), key=f"cadp_man_acc_{idx}", label_visibility="collapsed")
                    acc_manual[idx] = acc
        st.markdown("---")

# ── Summary ───────────────────────────────────────────────────────────────────
acc_def_count = sum(1 for v in st.session_state.cadp_qc_accepted_defaults.values() if v)
acc_llm_count = sum(1 for v in st.session_state.cadp_qc_accepted_llm.values() if v)
acc_man_count = sum(1 for v in acc_manual.values() if v)
total_acc     = acc_def_count + acc_llm_count + acc_man_count
st.info(f"**{total_acc} checks** selected  ({acc_def_count} default · {acc_llm_count} LLM · {acc_man_count} manual)")

if total_acc > 0:
    from io import BytesIO
    rows = []
    for i, chk in enumerate(st.session_state.cadp_qc_default_checks):
        if st.session_state.cadp_qc_accepted_defaults.get(i, True):
            rows.append({"check_name": chk["name"], "syntax": chk["syntax"], "body": json.dumps(chk.get("body")), "category": chk["category"], "column": chk.get("col"), "source": "default", "approved": "Yes"})
    for i, chk in enumerate(st.session_state.cadp_qc_llm_suggestions):
        if st.session_state.cadp_qc_accepted_llm.get(i, False):
            rows.append({"check_name": chk["name"], "syntax": chk["syntax"], "body": json.dumps(chk.get("body")), "category": chk["category"], "column": chk.get("col"), "source": "llm", "approved": "Yes"})
    for i, chk in enumerate(manual_checks):
        if acc_manual.get(i, True):
            rows.append({"check_name": chk["name"], "syntax": chk["syntax"], "body": json.dumps(chk.get("body")), "category": chk["category"], "column": chk.get("col"), "source": "manual", "approved": "Yes"})
    xls_buf = BytesIO()
    pd.DataFrame(rows).to_excel(xls_buf, index=False, engine="openpyxl")
    st.download_button("📥 Download Checks for Approval (Excel)", data=xls_buf.getvalue(), file_name="cadp_qc_checks.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

st.divider()
section_header("🧠", "Learn from Edited QC Excel")

uploaded_learning = st.file_uploader(
    "Upload edited QC Excel to improve future QC suggestions",
    type=["xlsx"],
    key="cadp_learning_upload"
)

if uploaded_learning and "learning_done" not in st.session_state:
    df_learning = read_excel_cached(uploaded_learning)
    required_cols = {"check_name", "syntax", "body", "category", "column"}
    if not required_cols.issubset(set(df_learning.columns)):
        st.error("Invalid QC Excel format.")
    else:
        generated_checks = st.session_state.get("generated_qc_checks")
        if not generated_checks:
            st.warning("Generate QC checks first before uploading edited Excel.")
        else:
            learned_rules = detect_new_rules(generated_checks, df_learning)
            if learned_rules:
                count = save_reference_rules(learned_rules)
                st.success(f"🧠 Learned {count} new QC rule(s) from your edits")
            else:
                st.info("No new rules detected")
        st.session_state["learning_done"] = True

if st.button("➕ Add Manual Check", use_container_width=True):
    st.session_state.cadp_qc_show_manual_form = True

if st.session_state.cadp_qc_show_manual_form:
    table_cols = [c["name"] for c in ctx["columns"]]
    with st.form("cadp_manual_form"):
        c1, c2 = st.columns(2)
        with c1:
            m_name     = st.text_input("Check Name *")
            m_category = st.selectbox("Category", CAT_NAMES)
            m_column   = st.selectbox("Column (optional)", [""] + table_cols)
        with c2:
            m_syntax = st.text_input("SodaCL Syntax *", placeholder="e.g. missing_count(COL) = 0")
        m_body_str = st.text_area("Body JSON (optional)", value="", height=80)
        if st.form_submit_button("Add Check", type="primary"):
            if not m_name.strip() or not m_syntax.strip():
                st.error("Name and syntax are required.")
            else:
                try:
                    parsed_body = json.loads(m_body_str) if m_body_str.strip() else None
                except Exception:
                    parsed_body = None
                new_chk = {"name": m_name.strip(), "syntax": m_syntax.strip(), "body": parsed_body, "category": m_category, "col": m_column.strip() or None}
                if manual_key not in st.session_state:
                    st.session_state[manual_key] = []
                idx = len(st.session_state[manual_key])
                st.session_state[manual_key].append(new_chk)
                if acc_man_key not in st.session_state:
                    st.session_state[acc_man_key] = {}
                st.session_state[acc_man_key][idx] = True
                st.session_state.cadp_qc_show_manual_form = False
                st.rerun()

st.divider()
section_header("📤", "Upload Approved Checks (optional)")
approved_file = st.file_uploader("Upload reviewed Excel file", type=["xlsx"], key="cadp_approved_upload")
approved_from_excel = None
if approved_file:
    try:
        df_app = pd.read_excel(approved_file)
        req = {"check_name", "syntax", "body", "category", "column", "approved"}
        if not req.issubset(set(df_app.columns)):
            st.error("Invalid Excel format.")
        else:
            approved_from_excel = df_app[df_app["approved"].str.lower() == "yes"]
            st.success(f"{len(approved_from_excel)} approved checks loaded from Excel.")
    except Exception as e:
        st.error(f"Failed to read Excel: {e}")

# ── ③ Workflow Metadata + Generate ────────────────────────────────────────────
st.divider()
section_header(" ", "Workflow Metadata")

with st.form("cadp_meta_form"):
    m1, m2 = st.columns(2)
    with m1:
        wf_name = st.text_input("Workflow Name *", value=st.session_state.cadp_qc_wf_name or f"soda-{ctx['table'].lower()}-qc", placeholder="e.g. soda-customer-qc")
        wf_desc = st.text_area("Description", value=st.session_state.cadp_qc_wf_desc or f"Quality checks for {ctx['table']}", height=80)
    with m2:
        wf_depot     = st.text_input("Depot Name *", value=st.session_state.cadp_qc_wf_depot, placeholder="e.g. sfdataproductsnaaprod")
        wf_workspace = st.text_input("Workspace *", value=st.session_state.cadp_qc_wf_workspace or "public")
    co1, co2 = st.columns(2)
    with co1:
        wf_engine  = st.text_input("Engine (optional)", value=st.session_state.cadp_qc_wf_engine, placeholder="minerva")
    with co2:
        wf_cluster = st.text_input("Cluster (optional)", value=st.session_state.cadp_qc_wf_cluster)
    st.markdown("**Tags**")
    t1, t2, t3 = st.columns(3)
    with t1:
        tag_domain  = st.text_input("DPDomain", value=st.session_state.cadp_qc_wf_tag_domain, placeholder="Sales")
        tag_usecase = st.text_input("DPUsecase", value=st.session_state.cadp_qc_wf_tag_usecase)
    with t2:
        tag_tier   = st.selectbox("DPTier", ["Consumer Aligned", "Source Aligned", "Derived"], index=0)
        tag_region = st.text_input("DPRegion", value=st.session_state.cadp_qc_wf_tag_region)
    with t3:
        tag_dataos = st.text_input("Dataos tag", value=st.session_state.cadp_qc_wf_tag_dataos)
        tag_custom = st.text_input("Custom project tag", value=st.session_state.cadp_qc_wf_tag_custom)
    gen_btn = st.form_submit_button("Generate QC YAML", use_container_width=True, type="primary")
    if gen_btn:
        if not wf_name.strip():
            st.error("Workflow name is required.")
        elif not wf_depot.strip():
            st.error("Depot name is required.")
        elif not wf_workspace.strip():
            st.error("Workspace is required.")
        else:
            st.session_state.cadp_qc_wf_name      = wf_name.strip()
            st.session_state.cadp_qc_wf_desc      = wf_desc.strip()
            st.session_state.cadp_qc_wf_depot     = wf_depot.strip()
            st.session_state.cadp_qc_wf_workspace = wf_workspace.strip()
            st.session_state.cadp_qc_wf_engine    = wf_engine.strip()
            st.session_state.cadp_qc_wf_cluster   = wf_cluster.strip()
            st.session_state.cadp_qc_wf_tag_domain  = tag_domain.strip()
            st.session_state.cadp_qc_wf_tag_usecase = tag_usecase.strip()
            st.session_state.cadp_qc_wf_tag_tier    = tag_tier
            st.session_state.cadp_qc_wf_tag_region  = tag_region.strip()
            st.session_state.cadp_qc_wf_tag_dataos  = tag_dataos.strip()
            st.session_state.cadp_qc_wf_tag_custom  = tag_custom.strip()
            accepted = []
            if approved_from_excel is not None:
                for _, row in approved_from_excel.iterrows():
                    try:
                        body = json.loads(row["body"]) if pd.notna(row["body"]) else None
                    except Exception:
                        body = None
                    accepted.append({"name": row["check_name"], "syntax": row["syntax"], "body": body, "category": row["category"], "col": row["column"]})
            else:
                for i, chk in enumerate(st.session_state.cadp_qc_default_checks):
                    if st.session_state.cadp_qc_accepted_defaults.get(i, True):
                        accepted.append(chk)
                for i, chk in enumerate(st.session_state.cadp_qc_llm_suggestions):
                    if st.session_state.cadp_qc_accepted_llm.get(i, False):
                        accepted.append(chk)
                for i, chk in enumerate(manual_checks):
                    if acc_manual.get(i, True):
                        accepted.append(chk)
            tags = ["workflow", "soda-checks"]
            if tag_domain:  tags.append(f"DPDomain.{tag_domain}")
            if tag_usecase: tags.append(f"DPUsecase.{tag_usecase}")
            if tag_tier:    tags.append(f"DPTier.{tag_tier}")
            if tag_region:  tags.append(f"DPRegion.{tag_region}")
            if tag_dataos:  tags.append(f"Dataos.{tag_dataos}")
            if tag_custom:  tags.append(tag_custom)
            # UDL: depot + table name (no DB/schema since we're not using Snowflake directly)
            udl = f"dataos://{wf_depot.strip()}/{ctx['table']}"
            try:
                yaml_out = generate_qc_yaml(
                    metadata={"workflow_name": wf_name.strip(), "description": wf_desc.strip(), "tags": tags},
                    accepted_checks=accepted, dataset_udl=udl, workspace=wf_workspace.strip(),
                    engine=wf_engine.strip() or None, cluster=wf_cluster.strip() or None,
                )
                file_name = f"soda-{ctx['table'].lower()}-qc.yml"

                # store per table
                st.session_state.cadp_qc_all_yaml[ctx["table"]] = {
                    "content": yaml_out,
                    "file_name": file_name
                }

                # keep last one for preview
                st.session_state.cadp_qc_last_yaml = yaml_out
                st.session_state.cadp_qc_last_yaml_name = file_name
                # Track completed table
                st.session_state.cadp_qc_generated_tables.add(ctx["table"])
                st.success(f"✅ QC generated for table: {ctx['table']}")
            except Exception as e:
                st.error(f"YAML generation failed: {e}")

# ── ④ YAML Output ─────────────────────────────────────────────────────────────
if st.session_state.cadp_qc_last_yaml:
    st.divider()
    section_header("📄", "Generated QC YAML")
    dl_col, next_col, back_col = st.columns([2, 2, 2])
    with dl_col:
        st.download_button("⬇️ Download YAML", data=st.session_state.cadp_qc_last_yaml,
            file_name=st.session_state.cadp_qc_last_yaml_name or "cadp-qc.yaml",
            mime="text/yaml", use_container_width=True, type="primary")
    with next_col:
        done = st.session_state.cadp_qc_generated_tables
        remaining = [t for t in all_tables if t not in done]

        if st.button(
            "➡️ Generate QC for Another Table",
            use_container_width=True,
            disabled=len(remaining) == 0
        ):
            all_tables = [t["name"] for t in _bundle_tbls]
            done = st.session_state.cadp_qc_generated_tables

            # find next remaining table
            next_table = next((t for t in all_tables if t not in done), None)

            if next_table:
                st.session_state.cadp_qc_sel_table = next_table

            reset_table_state()
            st.rerun()
    with back_col:
        if st.button("✅ Complete & Back to CADP Flow →", use_container_width=True):
            if "cadp_completed_steps" not in st.session_state:
                st.session_state.cadp_completed_steps = set()
            st.session_state.cadp_completed_steps.add(3)
            st.switch_page("pages/cadp_flow.py")
    st.code(st.session_state.cadp_qc_last_yaml, language="yaml")

app_footer()