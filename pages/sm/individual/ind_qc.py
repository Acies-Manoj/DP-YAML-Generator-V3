"""
Individual Quality Checks Builder
═══════════════════════════════════
Standalone QC generator for the specific-file builder.
Uses live Snowflake connection — no Semantic Model / bundle_tables needed.
Identical behaviour to the SADP QC page but with ind_qc_* session keys
and a plain download button instead of a "Back to flow" button.
"""

import json
import streamlit as st

from utils.ui_utils import section_header
from utils.sf_utils import (
    connect, fetch_databases, fetch_schemas,
    fetch_tables, fetch_full_context, fetch_schema_overview,
)
from utils.default_checks import generate_default_checks
from utils.llm_checks import call_llm
from utils.qc_yaml_generator import generate_qc_yaml
from utils.history import save_entry
from utils.qc_config import PROVIDER, GROQ_DEFAULT_MODEL, OLLAMA_DEFAULT_MODEL

import pandas as pd

CATEGORIES = [
    ("Schema",       "🔷", "#1e3a5f", "#93c5fd"),
    ("Completeness", "🟢", "#14532d", "#86efac"),
    ("Uniqueness",   "🟣", "#3b0764", "#d8b4fe"),
    ("Freshness",    "🟡", "#78350f", "#fcd34d"),
    ("Validity",     "🩷", "#4a1d4a", "#f9a8d4"),
    ("Accuracy",     "🩵", "#134e4a", "#6ee7b7"),
]
CAT_NAMES = [c[0] for c in CATEGORIES]

_DEFAULTS = {
    "ind_qc_sf_conn": None, "ind_qc_sf_databases": [], "ind_qc_sf_last_db": "",
    "ind_qc_sf_schemas": [], "ind_qc_sf_last_schema": "", "ind_qc_sf_tables": [],
    "ind_qc_sf_last_table": "",
    "ind_qc_ctx": None, "ind_qc_default_checks": [], "ind_qc_llm_suggestions": [],
    "ind_qc_accepted_defaults": {}, "ind_qc_accepted_llm": {},
    "ind_qc_show_manual_form": False,
    "ind_qc_llm_done": False, "ind_qc_llm_error": None,
    "ind_qc_wf_name": "", "ind_qc_wf_desc": "", "ind_qc_wf_depot": "",
    "ind_qc_wf_workspace": "public", "ind_qc_wf_engine": "", "ind_qc_wf_cluster": "",
    "ind_qc_wf_tag_domain": "", "ind_qc_wf_tag_usecase": "",
    "ind_qc_wf_tag_tier": "Source Aligned",
    "ind_qc_wf_tag_region": "", "ind_qc_wf_tag_dataos": "", "ind_qc_wf_tag_custom": "",
    "ind_qc_last_yaml": None, "ind_qc_last_yaml_name": "",
}


def _manual_key():
    return f"ind_qc_manual_{st.session_state.get('ind_qc_sf_last_table', '')}"

def _acc_manual_key():
    return f"ind_qc_acc_manual_{st.session_state.get('ind_qc_sf_last_table', '')}"

def _reset_table():
    for k in ["ind_qc_ctx", "ind_qc_default_checks", "ind_qc_llm_suggestions",
              "ind_qc_accepted_defaults", "ind_qc_accepted_llm",
              "ind_qc_llm_done", "ind_qc_llm_error",
              "ind_qc_last_yaml", "ind_qc_last_yaml_name"]:
        st.session_state[k] = _DEFAULTS.get(k, None) or (
            [] if "checks" in k or "suggestions" in k
            else {} if "accepted" in k
            else None
        )

def _checks_by_cat(checks):
    out = {cat: [] for cat in CAT_NAMES}
    for i, chk in enumerate(checks):
        cat = chk.get("category", "Schema")
        if cat in out:
            out[cat].append((i, chk))
    return out

def _syntax_preview(chk):
    s    = chk.get("syntax", "")
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


def render_ind_qc():
    # ── init session state ────────────────────────────────────────────────────
    for k, v in _DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

    st.subheader("✅ Quality Checks")
    st.markdown(
        '<p style="color:#6b7280;font-size:13px;margin-top:-8px;">'
        'Connect to Snowflake, auto-generate checks, review LLM suggestions, and export YAML.'
        '</p>', unsafe_allow_html=True,
    )

    # Reset button
    if st.button("🔄 Start Over", key="ind_qc_reset"):
        for k, v in _DEFAULTS.items():
            st.session_state[k] = v
        st.rerun()

    model_label = GROQ_DEFAULT_MODEL if PROVIDER == "groq" else OLLAMA_DEFAULT_MODEL
    st.markdown(
        f'<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;'
        f'padding:8px 14px;font-size:12px;color:#6b7280;margin:8px 0;">'
        f'LLM Provider: <b style="color:#d1d5db">{PROVIDER.upper()}</b> &nbsp;|&nbsp; '
        f'Model: <b style="color:#d1d5db">{model_label}</b> &nbsp;|&nbsp; '
        f'Edit in <b style="color:#d1d5db">utils/qc_config.py</b></div>',
        unsafe_allow_html=True,
    )
    st.divider()

    # ── ① Snowflake Connection ────────────────────────────────────────────────
    section_header("🔗", "Snowflake Connection")

    # Reuse depot connection if available
    if st.session_state.ind_qc_sf_conn is None and st.session_state.get("sf_conn"):
        try:
            st.session_state.ind_qc_sf_conn      = st.session_state.sf_conn
            st.session_state.ind_qc_sf_databases = fetch_databases(st.session_state.ind_qc_sf_conn)
            st.success("✅ Reusing Snowflake connection from Depot step.")
        except Exception:
            st.session_state.ind_qc_sf_conn = None

    if st.session_state.ind_qc_sf_conn is None:
        with st.form("ind_qc_sf_form"):
            c1, c2 = st.columns(2)
            with c1:
                sf_acct = st.text_input("Account Identifier *", placeholder="abc12345.us-east-1.aws")
                sf_user = st.text_input("Username *", placeholder="john_doe")
            with c2:
                sf_pw   = st.text_input("Password *", type="password")
                sf_role = st.text_input("Role (optional)", placeholder="SYSADMIN")
                sf_wh   = st.text_input("Warehouse (optional)", placeholder="COMPUTE_WH")
            go = st.form_submit_button("Connect", use_container_width=True, type="primary")
        if go:
            if not sf_acct or not sf_user or not sf_pw:
                st.error("Account, username and password are required.")
            else:
                with st.spinner("Connecting..."):
                    try:
                        _conn = connect(sf_acct.strip(), sf_user.strip(), sf_pw,
                                        sf_role.strip(), sf_wh.strip())
                        st.session_state.ind_qc_sf_conn      = _conn
                        st.session_state.ind_qc_sf_databases = fetch_databases(_conn)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Connection failed: {e}")
        st.stop()

    hdr_c, disc_c = st.columns([8, 1])
    with hdr_c:
        st.success("✅ Connected to Snowflake")
    with disc_c:
        if st.button("Disconnect", key="ind_qc_disconnect"):
            for k, v in _DEFAULTS.items():
                st.session_state[k] = v
            st.rerun()

    # ── ② Table Selection ─────────────────────────────────────────────────────
    st.divider()
    section_header("🗄️", "Select Table")
    conn = st.session_state.ind_qc_sf_conn

    d1, d2, d3 = st.columns(3)
    with d1:
        db_opts = ["— select —"] + st.session_state.ind_qc_sf_databases
        db_idx  = db_opts.index(st.session_state.ind_qc_sf_last_db) if st.session_state.ind_qc_sf_last_db in db_opts else 0
        sel_db  = st.selectbox("Database", db_opts, index=db_idx, key="ind_qc_sel_db")
        if sel_db != "— select —" and sel_db != st.session_state.ind_qc_sf_last_db:
            st.session_state.ind_qc_sf_last_db     = sel_db
            st.session_state.ind_qc_sf_schemas     = fetch_schemas(conn, sel_db)
            st.session_state.ind_qc_sf_last_schema = ""
            st.session_state.ind_qc_sf_tables      = []
            st.session_state.ind_qc_sf_last_table  = ""
            _reset_table()
            st.rerun()

    with d2:
        sc_opts = ["— select —"] + st.session_state.ind_qc_sf_schemas
        sc_idx  = sc_opts.index(st.session_state.ind_qc_sf_last_schema) if st.session_state.ind_qc_sf_last_schema in sc_opts else 0
        sel_sc  = st.selectbox("Schema", sc_opts, index=sc_idx,
                               disabled=not st.session_state.ind_qc_sf_schemas, key="ind_qc_sel_sc")
        if sel_sc != "— select —" and sel_sc != st.session_state.ind_qc_sf_last_schema:
            st.session_state.ind_qc_sf_last_schema = sel_sc
            st.session_state.ind_qc_sf_tables      = fetch_tables(conn, st.session_state.ind_qc_sf_last_db, sel_sc)
            st.session_state.ind_qc_sf_last_table  = ""
            _reset_table()
            st.rerun()

    with d3:
        tb_opts = ["— select —"] + st.session_state.ind_qc_sf_tables
        tb_idx  = tb_opts.index(st.session_state.ind_qc_sf_last_table) if st.session_state.ind_qc_sf_last_table in tb_opts else 0
        sel_tb  = st.selectbox("Table", tb_opts, index=tb_idx,
                               disabled=not st.session_state.ind_qc_sf_tables, key="ind_qc_sel_tb")
        if sel_tb != "— select —" and sel_tb != st.session_state.ind_qc_sf_last_table:
            st.session_state.ind_qc_sf_last_table = sel_tb
            _reset_table()
            with st.spinner(f"Pulling schema & profiling for {sel_tb}..."):
                try:
                    _ctx = fetch_full_context(conn, st.session_state.ind_qc_sf_last_db,
                                              st.session_state.ind_qc_sf_last_schema, sel_tb)
                    _ctx["schema_overview"] = fetch_schema_overview(
                        conn, st.session_state.ind_qc_sf_last_db, st.session_state.ind_qc_sf_last_schema)
                    st.session_state.ind_qc_ctx = _ctx
                    _defs = generate_default_checks(_ctx)
                    for _chk in _defs:
                        _chk["_original"] = {
                            "name":   _chk.get("name"),
                            "syntax": _chk.get("syntax"),
                            "body":   json.dumps(_chk.get("body"), sort_keys=True),
                        }
                    st.session_state.ind_qc_default_checks    = _defs
                    st.session_state.ind_qc_accepted_defaults = {i: True for i in range(len(_defs))}
                    if _ctx["errors"]:
                        for err in _ctx["errors"]:
                            st.warning(f"⚠️ {err}")
                except Exception as e:
                    st.error(f"Failed to fetch table context: {e}")
            st.rerun()

    if not st.session_state.ind_qc_ctx:
        st.stop()

    # ── ③ Checks Review ───────────────────────────────────────────────────────
    ctx = st.session_state.ind_qc_ctx
    st.divider()
    section_header("🔍", f"Quality Checks — {ctx['table']}")

    ic, wc = st.columns([3, 3])
    with ic:
        st.caption(f"{len(ctx['columns'])} columns · ~{ctx['row_count'] or '?'} rows sampled")
    if ctx["errors"]:
        with wc:
            with st.expander(f"⚠️ {len(ctx['errors'])} data-pull warning(s)"):
                for e in ctx["errors"]:
                    st.caption(f"• {e}")

    with st.expander(" Upload Metadata for Advanced LLM Checks (optional)"):
        uploaded_meta = st.file_uploader(
            "Upload Excel with table & column descriptions",
            type=["xlsx"], key="ind_qc_meta_upload",
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

    # ── LLM controls ──────────────────────────────────────────────────────────
    llm_c1, llm_c2 = st.columns([4, 1])
    with llm_c1:
        llm_label = "Generate LLM Suggestions" if not st.session_state.ind_qc_llm_done else "🔄 Re-run LLM Suggestions"
        run_llm = st.button(llm_label, type="primary", use_container_width=True, key="ind_qc_run_llm")
    with llm_c2:
        if st.button("Clear LLM", use_container_width=True, key="ind_qc_clear_llm"):
            st.session_state.ind_qc_llm_suggestions = []
            st.session_state.ind_qc_accepted_llm    = {}
            st.session_state.ind_qc_llm_done        = False
            st.session_state.ind_qc_llm_error       = None
            st.rerun()

    if run_llm:
        with st.spinner("Calling LLM..."):
            try:
                ctx_for_llm = ctx.copy()
                ctx_for_llm["columns"] = [c.copy() for c in ctx.get("columns", [])]
                if semantic_metadata is not None:
                    tbl_rows = semantic_metadata[semantic_metadata["table_name"] == ctx["table"]]
                    if not tbl_rows.empty:
                        ctx_for_llm["table_description"] = tbl_rows.iloc[0]["table_description"]
                        col_desc = dict(zip(tbl_rows["column_name"], tbl_rows["column_description"]))
                        for col in ctx_for_llm["columns"]:
                            col["description"] = col_desc.get(col["name"], "")
                suggs = call_llm(ctx_for_llm, st.session_state.ind_qc_default_checks)
                for chk in suggs:
                    chk["_original"] = {
                        "name":   chk.get("name"),
                        "syntax": chk.get("syntax"),
                        "body":   json.dumps(chk.get("body"), sort_keys=True),
                    }
                st.session_state.ind_qc_llm_suggestions = suggs
                st.session_state.ind_qc_accepted_llm    = {i: False for i in range(len(suggs))}
                st.session_state.ind_qc_llm_done        = True
                st.session_state.ind_qc_llm_error       = None
            except Exception as e:
                st.session_state.ind_qc_llm_error = str(e)
        st.rerun()

    if st.session_state.ind_qc_llm_error:
        st.error(f"LLM error: {st.session_state.ind_qc_llm_error}")
        st.caption("Check your API key in utils/qc_config.py")
    if st.session_state.ind_qc_llm_done and st.session_state.ind_qc_llm_suggestions:
        st.success(f"✅ {len(st.session_state.ind_qc_llm_suggestions)} LLM suggestions ready — tick what you want to include.")

    # ── Category buckets ──────────────────────────────────────────────────────
    def_by_cat    = _checks_by_cat(st.session_state.ind_qc_default_checks)
    llm_by_cat    = _checks_by_cat(st.session_state.ind_qc_llm_suggestions)
    manual_key    = _manual_key()
    acc_man_key   = _acc_manual_key()
    manual_checks = st.session_state.get(manual_key, [])
    acc_manual    = st.session_state.get(acc_man_key, {})
    manual_by_cat = _checks_by_cat(manual_checks)

    for cat_name, icon, bg_color, text_color in CATEGORIES:
        def_items    = def_by_cat.get(cat_name, [])
        llm_items    = llm_by_cat.get(cat_name, [])
        manual_items = manual_by_cat.get(cat_name, [])
        if not def_items and not llm_items and not manual_items:
            continue
        total_checks   = len(def_items) + len(llm_items) + len(manual_items)
        accepted_count = (
            sum(1 for i, _ in def_items    if st.session_state.ind_qc_accepted_defaults.get(i, True)) +
            sum(1 for i, _ in llm_items    if st.session_state.ind_qc_accepted_llm.get(i, False)) +
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
                            st.code(_syntax_preview(chk), language="yaml")
                            if chk.get("body"):
                                st.json(chk["body"])
                            new_syn  = st.text_area("Edit SodaCL condition", value=chk["syntax"], key=f"ind_qc_def_syn_{idx}", height=60)
                            st.session_state.ind_qc_default_checks[idx]["syntax"] = new_syn
                            new_name = st.text_input("Check name", value=chk["name"], key=f"ind_qc_def_name_{idx}")
                            st.session_state.ind_qc_default_checks[idx]["name"] = new_name
                            if chk.get("body") and chk["syntax"] != "schema":
                                body_str = st.text_area("body", value=json.dumps(chk["body"], indent=2),
                                                        height=80, key=f"ind_qc_def_body_{idx}", label_visibility="collapsed")
                                try:
                                    st.session_state.ind_qc_default_checks[idx]["body"] = json.loads(body_str)
                                except Exception:
                                    st.caption("⚠️ Invalid JSON — original body preserved")
                            orig = chk.get("_original", {})
                            if new_name != orig.get("name") or new_syn != orig.get("syntax"):
                                st.markdown("<span style='color:#facc15;font-weight:600;'>✏️ Modified</span>", unsafe_allow_html=True)
                    with col_chk:
                        acc = st.checkbox("✓", value=st.session_state.ind_qc_accepted_defaults.get(idx, True),
                                          key=f"ind_qc_def_acc_{idx}", label_visibility="collapsed")
                        st.session_state.ind_qc_accepted_defaults[idx] = acc

            if llm_items:
                st.markdown('<span style="font-size:11px;color:#7c3aed;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">LLM Suggested</span>', unsafe_allow_html=True)
                for idx, chk in llm_items:
                    col_chk, col_acc = st.columns([0.5, 9.5])
                    with col_acc:
                        with st.expander(f"[LLM] {chk.get('col') or 'table-level'} — {chk.get('name','')[:80]}", expanded=False):
                            st.markdown('<span style="font-size:10px;font-weight:700;background:#3b0764;color:#d8b4fe;padding:1px 7px;border-radius:10px;">LLM SUGGESTION</span>', unsafe_allow_html=True)
                            if chk.get("reason"):
                                st.markdown(f'<div style="font-size:11px;color:#6b7280;font-style:italic;margin-top:4px;">💡 {chk["reason"]}</div>', unsafe_allow_html=True)
                            new_name = st.text_input("Check name", value=chk.get("name",""), key=f"ind_qc_llm_name_{idx}")
                            st.session_state.ind_qc_llm_suggestions[idx]["name"] = new_name
                            new_syn  = st.text_area("Edit SodaCL condition", value=chk.get("syntax",""),
                                                    key=f"ind_qc_llm_syn_{idx}", height=70)
                            st.session_state.ind_qc_llm_suggestions[idx]["syntax"] = new_syn
                            if chk.get("body"):
                                body_str = st.text_area("body", value=json.dumps(chk["body"], indent=2),
                                                        height=80, key=f"ind_qc_llm_body_{idx}", label_visibility="collapsed")
                                try:
                                    st.session_state.ind_qc_llm_suggestions[idx]["body"] = json.loads(body_str)
                                except Exception:
                                    st.caption("⚠️ Invalid JSON")
                    with col_chk:
                        acc = st.checkbox("✓", value=st.session_state.ind_qc_accepted_llm.get(idx, False),
                                          key=f"ind_qc_llm_acc_{idx}", label_visibility="collapsed")
                        st.session_state.ind_qc_accepted_llm[idx] = acc

            if manual_items:
                st.markdown('<span style="font-size:11px;color:#10b981;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Manual Checks</span>', unsafe_allow_html=True)
                for idx, chk in manual_items:
                    col_chk, col_acc = st.columns([0.5, 9.5])
                    with col_acc:
                        with st.expander(f"[MANUAL] {chk.get('col') or 'table-level'} — {chk['name'][:80]}", expanded=False):
                            st.markdown("<span style='color:#10b981;font-weight:700;'>🟢 MANUAL</span>", unsafe_allow_html=True)
                            new_name = st.text_input("Check name", value=chk["name"], key=f"ind_qc_man_name_{idx}")
                            manual_checks[idx]["name"] = new_name
                            new_syn  = st.text_area("Edit SodaCL condition", value=chk["syntax"],
                                                    key=f"ind_qc_man_syn_{idx}", height=70)
                            manual_checks[idx]["syntax"] = new_syn
                    with col_chk:
                        acc = st.checkbox("✓", value=acc_manual.get(idx, True),
                                          key=f"ind_qc_man_acc_{idx}", label_visibility="collapsed")
                        acc_manual[idx] = acc
            st.markdown("---")

    # ── Summary ───────────────────────────────────────────────────────────────
    acc_def_count = sum(1 for v in st.session_state.ind_qc_accepted_defaults.values() if v)
    acc_llm_count = sum(1 for v in st.session_state.ind_qc_accepted_llm.values() if v)
    acc_man_count = sum(1 for v in acc_manual.values() if v)
    total_acc     = acc_def_count + acc_llm_count + acc_man_count
    st.info(f"**{total_acc} checks** selected  ({acc_def_count} default · {acc_llm_count} LLM · {acc_man_count} manual)")

    if total_acc > 0:
        from io import BytesIO
        rows = []
        for i, chk in enumerate(st.session_state.ind_qc_default_checks):
            if st.session_state.ind_qc_accepted_defaults.get(i, True):
                rows.append({"check_name": chk["name"], "syntax": chk["syntax"],
                             "body": json.dumps(chk.get("body")), "category": chk["category"],
                             "column": chk.get("col"), "source": "default", "approved": "Yes"})
        for i, chk in enumerate(st.session_state.ind_qc_llm_suggestions):
            if st.session_state.ind_qc_accepted_llm.get(i, False):
                rows.append({"check_name": chk["name"], "syntax": chk["syntax"],
                             "body": json.dumps(chk.get("body")), "category": chk["category"],
                             "column": chk.get("col"), "source": "llm", "approved": "Yes"})
        for i, chk in enumerate(manual_checks):
            if acc_manual.get(i, True):
                rows.append({"check_name": chk["name"], "syntax": chk["syntax"],
                             "body": json.dumps(chk.get("body")), "category": chk["category"],
                             "column": chk.get("col"), "source": "manual", "approved": "Yes"})
        xls_buf = BytesIO()
        pd.DataFrame(rows).to_excel(xls_buf, index=False, engine="openpyxl")
        st.download_button("📥 Download Checks for Approval (Excel)", data=xls_buf.getvalue(),
                           file_name="ind_qc_checks.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True, key="ind_qc_dl_excel")

    if st.button("➕ Add Manual Check", use_container_width=True, key="ind_qc_add_manual"):
        st.session_state.ind_qc_show_manual_form = True

    if st.session_state.ind_qc_show_manual_form:
        table_cols = [c["name"] for c in ctx["columns"]]
        with st.form("ind_qc_manual_form"):
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
                    new_chk = {"name": m_name.strip(), "syntax": m_syntax.strip(),
                               "body": parsed_body, "category": m_category,
                               "col": m_column.strip() or None}
                    if manual_key not in st.session_state:
                        st.session_state[manual_key] = []
                    _idx = len(st.session_state[manual_key])
                    st.session_state[manual_key].append(new_chk)
                    if acc_man_key not in st.session_state:
                        st.session_state[acc_man_key] = {}
                    st.session_state[acc_man_key][_idx] = True
                    st.session_state.ind_qc_show_manual_form = False
                    st.rerun()

    st.divider()
    section_header("📤", "Upload Approved Checks (optional)")
    approved_file = st.file_uploader("Upload reviewed Excel file", type=["xlsx"], key="ind_qc_approved_upload")
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

    # ── ④ Workflow Metadata + Generate ────────────────────────────────────────
    st.divider()
    section_header("⚙️", "Workflow Metadata")

    with st.form("ind_qc_meta_form"):
        m1, m2 = st.columns(2)
        with m1:
            wf_name = st.text_input("Workflow Name *",
                value=st.session_state.ind_qc_wf_name or f"soda-{ctx['table'].lower()}-qc",
                placeholder="e.g. soda-sales-qc")
            wf_desc = st.text_area("Description",
                value=st.session_state.ind_qc_wf_desc or f"Quality checks for {ctx['table']}",
                height=80)
        with m2:
            wf_depot     = st.text_input("Depot Name *", value=st.session_state.ind_qc_wf_depot,
                                         placeholder="e.g. sfdataproductsnaaprod")
            wf_workspace = st.text_input("Workspace *", value=st.session_state.ind_qc_wf_workspace or "public")
        co1, co2 = st.columns(2)
        with co1:
            wf_engine  = st.text_input("Engine (optional)", value=st.session_state.ind_qc_wf_engine,
                                       placeholder="minerva")
        with co2:
            wf_cluster = st.text_input("Cluster (optional)", value=st.session_state.ind_qc_wf_cluster)
        st.markdown("**Tags**")
        t1, t2, t3 = st.columns(3)
        with t1:
            tag_domain  = st.text_input("DPDomain", value=st.session_state.ind_qc_wf_tag_domain, placeholder="Sales")
            tag_usecase = st.text_input("DPUsecase", value=st.session_state.ind_qc_wf_tag_usecase)
        with t2:
            tag_tier   = st.selectbox("DPTier", ["Source Aligned", "Consumer Aligned", "Derived"], index=0)
            tag_region = st.text_input("DPRegion", value=st.session_state.ind_qc_wf_tag_region)
        with t3:
            tag_dataos = st.text_input("Dataos tag", value=st.session_state.ind_qc_wf_tag_dataos)
            tag_custom = st.text_input("Custom project tag", value=st.session_state.ind_qc_wf_tag_custom)
        gen_btn = st.form_submit_button("⚡ Generate QC YAML", use_container_width=True, type="primary")

        if gen_btn:
            if not wf_name.strip():
                st.error("Workflow name is required.")
            elif not wf_depot.strip():
                st.error("Depot name is required.")
            elif not wf_workspace.strip():
                st.error("Workspace is required.")
            else:
                st.session_state.ind_qc_wf_name      = wf_name.strip()
                st.session_state.ind_qc_wf_desc      = wf_desc.strip()
                st.session_state.ind_qc_wf_depot     = wf_depot.strip()
                st.session_state.ind_qc_wf_workspace = wf_workspace.strip()
                st.session_state.ind_qc_wf_engine    = wf_engine.strip()
                st.session_state.ind_qc_wf_cluster   = wf_cluster.strip()
                st.session_state.ind_qc_wf_tag_domain  = tag_domain.strip()
                st.session_state.ind_qc_wf_tag_usecase = tag_usecase.strip()
                st.session_state.ind_qc_wf_tag_tier    = tag_tier
                st.session_state.ind_qc_wf_tag_region  = tag_region.strip()
                st.session_state.ind_qc_wf_tag_dataos  = tag_dataos.strip()
                st.session_state.ind_qc_wf_tag_custom  = tag_custom.strip()

                accepted = []
                if approved_from_excel is not None:
                    for _, row in approved_from_excel.iterrows():
                        try:
                            body = json.loads(row["body"]) if pd.notna(row["body"]) else None
                        except Exception:
                            body = None
                        accepted.append({"name": row["check_name"], "syntax": row["syntax"],
                                         "body": body, "category": row["category"], "col": row["column"]})
                else:
                    for i, chk in enumerate(st.session_state.ind_qc_default_checks):
                        if st.session_state.ind_qc_accepted_defaults.get(i, True):
                            accepted.append(chk)
                    for i, chk in enumerate(st.session_state.ind_qc_llm_suggestions):
                        if st.session_state.ind_qc_accepted_llm.get(i, False):
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

                db  = st.session_state.ind_qc_sf_last_db
                sch = st.session_state.ind_qc_sf_last_schema
                udl = f"dataos://{wf_depot.strip()}:{db}.{sch}/{ctx['table']}"
                try:
                    yaml_out = generate_qc_yaml(
                        metadata={"workflow_name": wf_name.strip(), "description": wf_desc.strip(), "tags": tags},
                        accepted_checks=accepted, dataset_udl=udl, workspace=wf_workspace.strip(),
                        engine=wf_engine.strip() or None, cluster=wf_cluster.strip() or None,
                    )
                    st.session_state.ind_qc_last_yaml      = yaml_out
                    st.session_state.ind_qc_last_yaml_name = f"{wf_name.strip()}.yaml"
                    save_entry("Specific", "quality_checks", f"{wf_name.strip()}.yaml", yaml_out)
                except Exception as e:
                    st.error(f"YAML generation failed: {e}")

    # ── ⑤ YAML Output ─────────────────────────────────────────────────────────
    if st.session_state.ind_qc_last_yaml:
        st.divider()
        section_header("📄", "Generated QC YAML")
        st.download_button(
            "⬇️ Download YAML",
            data=st.session_state.ind_qc_last_yaml,
            file_name=st.session_state.ind_qc_last_yaml_name or "quality-checks.yaml",
            mime="text/yaml",
            use_container_width=True,
            type="primary",
            key="ind_qc_dl_yaml",
        )
        st.code(st.session_state.ind_qc_last_yaml, language="yaml")