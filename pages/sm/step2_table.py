import streamlit as st
from utils.generators import generate_table_yaml
from sm.state import new_view
from utils.examples import EXAMPLE_TABLE_YAML, show_example
from utils.ui_utils import inline_docs_banner
from utils.llm_measures import suggest_measures
from utils.llm_segments import suggest_segments

DIM_TYPES     = ["string", "number", "boolean", "time"]
MEASURE_TYPES = ["number", "count", "count_distinct", "sum", "avg", "min", "max", "string"]
JOIN_RELS     = ["many_to_one", "one_to_many", "one_to_one"]


def render_step2():
    inline_docs_banner("lens", "segments")
    tables   = st.session_state.bundle_tables
    tidx     = st.session_state.bundle_table_idx
    t        = tables[tidx]
    n_tables = len(tables)


    # ── Table selector sidebar ────────────────────────────────────────────
    st.markdown(f"**Table YAML — {tidx + 1} of {n_tables}: `{t['name']}`**")
    if n_tables > 1:
        tab_cols = st.columns(n_tables)
        for i, tbl in enumerate(tables):
            with tab_cols[i]:
                done_mark = "✅" if tbl.get("generated_table_yaml") else ""
                btn_type = "primary" if i == tidx else "secondary"
                if st.button(f"{tbl['name']} {done_mark}", key=f"tbl_tab_{i}", type=btn_type, use_container_width=True):
                    st.session_state.bundle_table_idx = i
                    st.rerun()
    st.divider()

    if not t.get("tbl_preview_mode"):
        st.subheader(f"Step 2 — Table YAML: {t['name']}")
        show_example(st, "Table YAML", EXAMPLE_TABLE_YAML)
        if t["sql_input_mode"] == "snowflake":
            st.info(f"{len(t['dims'])} dimensions pre-filled from Snowflake — aliases used as names, types auto-mapped.")
        else:
            st.info(f"Dimensions pre-filled from {len(t['dims'])} SQL columns. Set types, mark primary keys, add measures/joins/segments as needed.")

        # ── AI Description Generation ──────────────────────────────
        _results_key = f"ai_desc_{tidx}_results"

        with st.expander("✨ Generate AI Descriptions (optional)", expanded=False):
            from utils.description_engine.description_ui import render_description_panel
            _ai_tables = [{
                "name": t["name"],
                "columns": [
                    {"name": d["name"], "data_type": d.get("type", "string")}
                    for d in t["dims"]
                ]
            }]
            _ai_results = render_description_panel(
                tables=_ai_tables,
                conn=st.session_state.get("sf_shared_conn"),
                database=t.get("db", ""),
                schema=t.get("schema", ""),
                key_prefix=f"ai_desc_{tidx}",
            )
            if _ai_results and t["name"] in _ai_results:
                st.session_state[_results_key] = _ai_results
                if st.button("✨ Auto-fill Descriptions", key=f"ai_apply_btn_{tidx}", type="primary"):
                    _data = _ai_results[t["name"]]
                    # Write table description directly into session state
                    _tbl_desc = _data.get("table_description", "")
                    if _tbl_desc:
                        tables[tidx]["tbl_desc"] = _tbl_desc
                        # Directly set widget state so it re-renders with new value
                        st.session_state[f"b_tbl_desc_{tidx}"] = _tbl_desc
                    # Write each column description directly into dims
                    _col_descs = {
                        c["name"].lower(): c["description"]
                        for c in _data.get("columns", [])
                    }
                    for j, dim in enumerate(tables[tidx]["dims"]):
                        _desc = _col_descs.get(dim["name"].lower(), "")
                        if _desc:
                            tables[tidx]["dims"][j]["description"] = _desc
                            # Directly set widget state so it re-renders with new value
                            st.session_state[f"b_dd_{tidx}_{j}"] = _desc
                    st.rerun()

        st.markdown("#### Table Metadata")
        tm1, tm2 = st.columns(2)
        with tm1:
            st.text_input("Table Name", value=t["name"], disabled=True)
            b_tbl_private = st.checkbox(
                "Set as Private (public: false)",
                value=not t.get("tbl_public", True),
                key=f"b_tbl_priv_{tidx}",
                help="Leave unchecked — DataOS treats tables as public by default. Only check to explicitly set public: false.",
            )
            b_tbl_public = not b_tbl_private
        with tm2:
            b_tbl_desc = st.text_area("Description", value=t.get("tbl_desc", ""),
                key=f"b_tbl_desc_{tidx}",
                placeholder="e.g. Contains customer data.", height=100)

        st.divider()

        # Dimensions section in one expander
        _dim_count  = len(t["dims"])
        _pk_names   = [d["name"] for d in t["dims"] if d.get("primary_key")]
        _pk_hint    = f" · PK: {', '.join(_pk_names)}" if _pk_names else ""
        _priv_count = sum(1 for d in t["dims"] if not d.get("public", True))
        _priv_hint  = f" · {_priv_count} private" if _priv_count else ""
        _dim_label  = f"Dimensions ({_dim_count}){_pk_hint}{_priv_hint}"

        with st.expander(_dim_label, expanded=True):
            st.caption("Pre-filled from SQL columns. Rename, retype, mark PKs, or set individual dimensions as private.")
            # ── Primary key requirement note ───────────────────────────────
            _has_pk = any(d.get("primary_key") for d in t["dims"])
            if not _has_pk:
                st.markdown(
                    '<div style="background:#fffbeb;border:1px solid #fcd34d;border-left:3px solid #f59e0b;'
                    'border-radius:6px;padding:8px 14px;margin:6px 0 10px 0;font-size:13px;color:#92400e;">'
                    '⚠️ <b>At least one dimension must be marked as Primary Key (PK)</b> — '
                    'Lens requires a primary key on every table to function correctly.'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="background:#f0fdf4;border:1px solid #86efac;border-left:3px solid #16a34a;'
                    f'border-radius:6px;padding:6px 14px;margin:6px 0 10px 0;font-size:13px;color:#15803d;">'
                    f'✅ Primary key set: <b>{", ".join(d["name"] for d in t["dims"] if d.get("primary_key"))}</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            hh1, hh2, hh3, hh4, hh5 = st.columns([2, 2, 1.5, 1, 3])
            hh1.markdown("**Name**"); hh2.markdown("**Column**")
            hh3.markdown("**Type**"); hh4.markdown("**Flags**"); hh5.markdown("**Description**")
            st.markdown("---")
            for i, d in enumerate(t["dims"]):
                dc1, dc2, dc3, dc4, dc5 = st.columns([2, 2, 1.5, 1, 3])
                with dc1:
                    new_name = st.text_input("Name", value=d["name"], key=f"b_dn_{tidx}_{i}",
                                             label_visibility="collapsed")
                    tables[tidx]["dims"][i]["name"] = new_name
                with dc2:
                    st.text_input("Column", value=d["column"], key=f"b_dc_{tidx}_{i}",
                                  disabled=True, label_visibility="collapsed")
                with dc3:
                    tables[tidx]["dims"][i]["type"] = st.selectbox(
                        "Type", DIM_TYPES,
                        index=DIM_TYPES.index(d["type"]) if d["type"] in DIM_TYPES else 0,
                        key=f"b_dt_{tidx}_{i}", label_visibility="collapsed")
                with dc4:
                    tables[tidx]["dims"][i]["primary_key"] = st.checkbox(
                        "PK", value=d.get("primary_key", False), key=f"b_dpk_{tidx}_{i}")
                    _is_private = st.checkbox(
                        "Private",
                        value=not d.get("public", True),
                        key=f"b_dpriv_{tidx}_{i}",
                        help="Only check to set public: false. Leave unchecked for default (public).",
                    )
                    tables[tidx]["dims"][i]["public"] = not _is_private
                with dc5:
                    tables[tidx]["dims"][i]["description"] = st.text_input(
                        "Description", value=d.get("description", ""),
                        key=f"b_dd_{tidx}_{i}",
                        placeholder="e.g. Unique customer identifier.",
                        label_visibility="collapsed")
                st.markdown("---")

        # ── MEASURES ──────────────────────────────────────────────────────
        st.divider()
        _mh1, _mh2, _mh3 = st.columns([4, 1.4, 1])
        with _mh1:
            st.markdown("#### Measures")
        with _mh2:
            _suggest_key = f"b_suggest_meas_{tidx}"
            if st.button("✨ Suggest", key=_suggest_key, use_container_width=True,
                         help="Use AI to suggest measures based on your table columns"):
                with st.spinner("Thinking…"):
                    try:
                        _suggestions = suggest_measures(
                            table_name  = t["name"],
                            dimensions  = t["dims"],
                            table_desc  = t.get("tbl_desc", ""),
                        )
                        st.session_state[f"b_meas_suggestions_{tidx}"] = _suggestions
                    except Exception as _e:
                        st.session_state[f"b_meas_suggestions_{tidx}"] = []
                        st.error(f"Suggestion failed: {_e}")
                st.rerun()
        with _mh3:
            if st.button("➕ Add", key=f"b_add_meas_{tidx}", use_container_width=True):
                tables[tidx]["measures"].append({"name": "", "sql": "", "type": "number", "description": ""}); st.rerun()

        # ── AI Measure Suggestion Cards ────────────────────────────────────
        _suggestions = st.session_state.get(f"b_meas_suggestions_{tidx}", [])
        if _suggestions:
            st.markdown(
                "<div style='background:#0f2237;border:1px solid #1e40af;"
                "border-radius:10px;padding:14px 16px 10px 16px;margin-bottom:12px;'>"
                "<p style='color:#93c5fd;font-weight:700;font-size:13px;margin:0 0 10px 0;'>"
                "✨ AI Suggestions — click Accept to add, or Dismiss to remove</p>",
                unsafe_allow_html=True,
            )
            _to_remove = []
            for _si, _sug in enumerate(_suggestions):
                _sc1, _sc2, _sc3, _sc4 = st.columns([2.5, 3.5, 2.5, 1.2])
                with _sc1:
                    st.markdown(f"**`{_sug['name']}`**")
                    st.caption(f"Type: `{_sug['type']}`")
                with _sc2:
                    st.code(_sug["sql"], language=None)
                with _sc3:
                    st.caption(_sug.get("description", ""))
                with _sc4:
                    _acc_col, _dis_col = st.columns(2)
                    with _acc_col:
                        if st.button("✅", key=f"b_sug_acc_{tidx}_{_si}",
                                     help="Accept this measure", use_container_width=True):
                            tables[tidx]["measures"].append({
                                "name":        _sug["name"],
                                "sql":         _sug["sql"],
                                "type":        _sug["type"],
                                "description": _sug.get("description", ""),
                                "_agg_func":   "Custom",
                                "_agg_dim":    "",
                            })
                            _to_remove.append(_si)
                    with _dis_col:
                        if st.button("✕", key=f"b_sug_dis_{tidx}_{_si}",
                                     help="Dismiss", use_container_width=True):
                            _to_remove.append(_si)
                st.markdown("<hr style='border-color:#1e3a5f;margin:6px 0;'>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            if _to_remove:
                _new_sug = [s for i, s in enumerate(_suggestions) if i not in _to_remove]
                st.session_state[f"b_meas_suggestions_{tidx}"] = _new_sug
                st.rerun()

        if t["measures"]:
            _dim_names   = [d["name"] for d in t["dims"] if d.get("name")]
            _AGG_FUNCS   = ["SUM", "COUNT", "COUNT_DISTINCT", "AVG", "MIN", "MAX", "Custom"]
            _AGG_TO_TYPE = {
                "SUM": "sum", "COUNT": "count", "COUNT_DISTINCT": "count_distinct",
                "AVG": "avg", "MIN": "min", "MAX": "max", "Custom": "number",
            }
            for i, m in enumerate(t["measures"]):
                ms1, ms2, ms3, ms4 = st.columns([2.5, 3.5, 2.5, 0.8])
                with ms1:
                    tables[tidx]["measures"][i]["name"] = st.text_input(
                        "Measure Name", value=m.get("name", ""),
                        key=f"b_mn_{tidx}_{i}", placeholder="e.g. total_revenue")

                with ms2:
                    st.caption("SQL Builder")
                    _prev_func = m.get("_agg_func", "SUM")
                    _prev_dim  = m.get("_agg_dim", _dim_names[0] if _dim_names else "")
                    _agg_col1, _agg_col2 = st.columns(2)
                    with _agg_col1:
                        _sel_func = st.selectbox(
                            "Function", _AGG_FUNCS,
                            index=_AGG_FUNCS.index(_prev_func) if _prev_func in _AGG_FUNCS else 0,
                            key=f"b_magg_{tidx}_{i}", label_visibility="collapsed")

                    with _agg_col2:
                        if _sel_func == "Custom":
                            # Custom: free text input
                            _custom_sql = st.text_input(
                                "Custom SQL", value=m.get("sql", ""),
                                key=f"b_mcust_{tidx}_{i}",
                                placeholder="e.g. SUM({revenue}) / COUNT({orders})",
                                label_visibility="collapsed")
                            _sel_dim = ""
                            _built_sql = _custom_sql
                        else:
                            # Non-custom: dimension dropdown
                            _dim_opts = _dim_names if _dim_names else ["—"]
                            _sel_dim  = st.selectbox(
                                "Dimension", _dim_opts,
                                index=_dim_opts.index(_prev_dim) if _prev_dim in _dim_opts else 0,
                                key=f"b_mdim_{tidx}_{i}", label_visibility="collapsed")
                            _custom_sql = None
                            if _sel_func == "COUNT_DISTINCT":
                                _built_sql = f"COUNT(DISTINCT {{{_sel_dim}}})"
                            else:
                                _built_sql = f"{_sel_func}({{{_sel_dim}}})"
                            st.caption(f"→ `{_built_sql}`")

                    tables[tidx]["measures"][i]["sql"]       = _built_sql
                    tables[tidx]["measures"][i]["_agg_func"] = _sel_func
                    tables[tidx]["measures"][i]["_agg_dim"]  = _sel_dim

                with ms3:
                    _auto_type = _AGG_TO_TYPE.get(_sel_func, "number")
                    _cur_type  = m.get("type", _auto_type)
                    tables[tidx]["measures"][i]["type"] = st.selectbox(
                        "Type", MEASURE_TYPES,
                        index=MEASURE_TYPES.index(_cur_type) if _cur_type in MEASURE_TYPES else 0,
                        key=f"b_mt_{tidx}_{i}")
                    tables[tidx]["measures"][i]["description"] = st.text_input(
                        "Description", value=m.get("description", ""),
                        key=f"b_md_{tidx}_{i}", placeholder="e.g. Total revenue across all orders")
                with ms4:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.button("✕", key=f"b_rm_meas_{tidx}_{i}"):
                        tables[tidx]["measures"].pop(i); st.rerun()
                st.markdown("---")

        # ── JOINS ─────────────────────────────────────────────────────────
        st.divider()
        _jh1, _jh2 = st.columns([5, 1])
        with _jh1:
            st.markdown("#### Joins")
        with _jh2:
            if st.button("➕ Add", key=f"b_add_join_{tidx}"):
                tables[tidx]["joins"].append({"name": "", "relationship": "many_to_one", "sql": ""}); st.rerun()

        if t["joins"]:
            _other_tables  = [tbl for tbl in st.session_state.bundle_tables
                              if tbl["name"] and tbl["name"] != t["name"]]
            _other_names   = [tbl["name"] for tbl in _other_tables]
            _cur_dim_names = [d["name"] for d in t["dims"] if d.get("name")]

            for i, j in enumerate(t["joins"]):
                jc1, jc2, jc3, jc4 = st.columns([2, 2.5, 4, 0.8])
                with jc1:
                    _jname_opts = _other_names if _other_names else ["(add more tables)"]
                    _jname_idx  = _jname_opts.index(j["name"]) if j["name"] in _jname_opts else 0
                    _sel_join_name = st.selectbox(
                        "Join Table", _jname_opts, index=_jname_idx,
                        key=f"b_jn_{tidx}_{i}")
                    tables[tidx]["joins"][i]["name"] = _sel_join_name

                    tables[tidx]["joins"][i]["relationship"] = st.selectbox(
                        "Relationship", JOIN_RELS,
                        index=JOIN_RELS.index(j["relationship"]) if j["relationship"] in JOIN_RELS else 0,
                        key=f"b_jr_{tidx}_{i}")

                with jc2:
                    st.caption("Column mapping")
                    _join_tbl_obj   = next((tbl for tbl in _other_tables
                                            if tbl["name"] == _sel_join_name), None)
                    _join_dim_names = ([d["name"] for d in _join_tbl_obj.get("dims", [])
                                        if d.get("name")] if _join_tbl_obj else [])
                    _left_opts  = _cur_dim_names  if _cur_dim_names  else ["—"]
                    _right_opts = _join_dim_names if _join_dim_names else ["—"]
                    _prev_left  = j.get("_sql_left",  _left_opts[0])
                    _prev_right = j.get("_sql_right", _right_opts[0])
                    _left_col = st.selectbox(
                        f"{t['name']}", _left_opts,
                        index=_left_opts.index(_prev_left) if _prev_left in _left_opts else 0,
                        key=f"b_jleft_{tidx}_{i}")
                    _right_col = st.selectbox(
                        f"{_sel_join_name}", _right_opts,
                        index=_right_opts.index(_prev_right) if _prev_right in _right_opts else 0,
                        key=f"b_jright_{tidx}_{i}")
                    tables[tidx]["joins"][i]["_sql_left"]  = _left_col
                    tables[tidx]["joins"][i]["_sql_right"] = _right_col

                with jc3:
                    _auto_sql  = f"{{{t['name']}.{_left_col}}} = {{{_sel_join_name}.{_right_col}}}"
                    _prev_auto = j.get("_last_auto_sql", "")
                    _cur_sql   = j.get("sql", "") or _auto_sql
                    if _cur_sql == _prev_auto:
                        _cur_sql = _auto_sql
                    tables[tidx]["joins"][i]["_last_auto_sql"] = _auto_sql
                    st.markdown("<br>", unsafe_allow_html=True)
                    tables[tidx]["joins"][i]["sql"] = st.text_input(
                        "SQL (editable)", value=_cur_sql,
                        key=f"b_js_{tidx}_{i}",
                        help="Auto-built from dropdowns above. Edit freely if needed.")
                with jc4:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.button("✕", key=f"b_rm_join_{tidx}_{i}"):
                        tables[tidx]["joins"].pop(i); st.rerun()
                st.markdown("---")

        # ── SEGMENTS ──────────────────────────────────────────────────────
        st.divider()
        _sh1, _sh2, _sh3 = st.columns([4, 1.4, 1])
        with _sh1:
            st.markdown("#### Segments")
        with _sh2:
            if st.button("✨ Suggest", key=f"b_suggest_seg_{tidx}", use_container_width=True,
                         help="Use AI to suggest segments based on your table columns"):
                with st.spinner("Thinking…"):
                    try:
                        _seg_suggestions = suggest_segments(
                            table_name = t["name"],
                            dimensions = t["dims"],
                            table_desc = t.get("tbl_desc", ""),
                        )
                        st.session_state[f"b_seg_suggestions_{tidx}"] = _seg_suggestions
                    except Exception as _e:
                        st.session_state[f"b_seg_suggestions_{tidx}"] = []
                        st.error(f"Suggestion failed: {_e}")
                st.rerun()
        with _sh3:
            if st.button("➕ Add", key=f"b_add_seg_{tidx}", use_container_width=True):
                tables[tidx]["segments"].append({"name": "", "sql": "", "description": "", "includes": "", "excludes": ""}); st.rerun()

        # ── AI Segment Suggestion Cards ────────────────────────────────────
        _seg_suggestions = st.session_state.get(f"b_seg_suggestions_{tidx}", [])
        if _seg_suggestions:
            st.markdown(
                "<div style='background:#0f2237;border:1px solid #1e40af;"
                "border-radius:10px;padding:14px 16px 10px 16px;margin-bottom:12px;'>"
                "<p style='color:#93c5fd;font-weight:700;font-size:13px;margin:0 0 10px 0;'>"
                "✨ AI Suggestions — click Accept to add, or Dismiss to remove</p>",
                unsafe_allow_html=True,
            )
            _seg_to_remove = []
            for _si, _sug in enumerate(_seg_suggestions):
                _sc1, _sc2, _sc3, _sc4 = st.columns([2, 3.5, 3, 1.2])
                with _sc1:
                    st.markdown(f"**`{_sug['name']}`**")
                with _sc2:
                    st.code(_sug["sql"], language=None)
                with _sc3:
                    st.caption(_sug.get("description", ""))
                with _sc4:
                    _acc_col, _dis_col = st.columns(2)
                    with _acc_col:
                        if st.button("✅", key=f"b_seg_acc_{tidx}_{_si}",
                                     help="Accept this segment", use_container_width=True):
                            tables[tidx]["segments"].append({
                                "name":        _sug["name"],
                                "sql":         _sug["sql"],
                                "description": _sug.get("description", ""),
                                "includes":    "",
                                "excludes":    "",
                            })
                            _seg_to_remove.append(_si)
                    with _dis_col:
                        if st.button("✕", key=f"b_seg_dis_{tidx}_{_si}",
                                     help="Dismiss", use_container_width=True):
                            _seg_to_remove.append(_si)
                st.markdown("<hr style='border-color:#1e3a5f;margin:6px 0;'>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            if _seg_to_remove:
                _new_seg = [s for i, s in enumerate(_seg_suggestions) if i not in _seg_to_remove]
                st.session_state[f"b_seg_suggestions_{tidx}"] = _new_seg
                st.rerun()

        if t["segments"]:
            for i, s in enumerate(t["segments"]):
                sc1, sc2, sc3 = st.columns([3, 3, 0.8])
                with sc1:
                    tables[tidx]["segments"][i]["name"] = st.text_input("Name", value=s["name"], key=f"b_sn_{tidx}_{i}", placeholder="e.g. high_value")
                    tables[tidx]["segments"][i]["sql"]  = st.text_input("SQL",  value=s["sql"],  key=f"b_ss_{tidx}_{i}", placeholder="{lifetime_value} > 1000")
                with sc2:
                    tables[tidx]["segments"][i]["description"] = st.text_input("Description", value=s["description"], key=f"b_sd_{tidx}_{i}")
                    sg1, sg2 = st.columns(2)
                    with sg1: tables[tidx]["segments"][i]["includes"] = st.text_input("Includes", value=s.get("includes", ""), key=f"b_sinc_{tidx}_{i}")
                    with sg2: tables[tidx]["segments"][i]["excludes"] = st.text_input("Excludes", value=s.get("excludes", ""), key=f"b_sexc_{tidx}_{i}")
                with sc3:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.button("✕", key=f"b_rm_seg_{tidx}_{i}"):
                        tables[tidx]["segments"].pop(i); st.rerun()
                st.markdown("---")

        # ── PREVIEW BUTTON AT BOTTOM ──────────────────────────────────────
        st.divider()
        _has_pk_final = any(d.get("primary_key") for d in t["dims"])
        if not _has_pk_final:
            st.error(
                "⚠️ Cannot generate Table YAML — no primary key set. "
                "Go to the Dimensions section above and check **PK** on at least one column.",
                icon=None,
            )
        if st.button("Preview Table YAML ↓", key=f"b_preview_bot_{tidx}", type="primary",
                     use_container_width=True, disabled=not _has_pk_final):
            st.session_state[f"b_preview_bot_clicked_{tidx}"] = True
            st.rerun()

        if st.session_state.pop(f"b_preview_bot_clicked_{tidx}", False):
            tables[tidx]["tbl_desc"]  = b_tbl_desc.strip()
            tables[tidx]["tbl_public"] = b_tbl_public
            segments_data = []
            for s in t["segments"]:
                if not s.get("name","").strip(): continue
                segments_data.append({
                    "name": s["name"], "sql": s["sql"], "description": s.get("description",""),
                    "includes": [g.strip() for g in s.get("includes","").split(",") if g.strip()],
                    "excludes": [g.strip() for g in s.get("excludes","").split(",") if g.strip()],
                })
            tables[tidx]["generated_table_yaml"] = generate_table_yaml({
                "name": t["name"],
                "description": b_tbl_desc.strip(),
                "public": b_tbl_public,
                "joins":      t["joins"],
                "dimensions": t["dims"],
                "measures":   t["measures"],
                "segments":   segments_data,
            })
            tables[tidx]["tbl_preview_mode"] = True
            st.rerun()

    else:
        st.subheader(f"Table YAML Preview — {t['name']}")
        st.code(t["generated_table_yaml"], language="yaml")
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("Edit Table YAML"):
                tables[tidx]["tbl_preview_mode"] = False
                st.rerun()
        with pc2:
            all_tbl_done = all(tbl.get("generated_table_yaml") for tbl in st.session_state.bundle_tables)
            next_undone = next((i for i, tbl in enumerate(tables) if not tbl.get("generated_table_yaml")), None)

            if next_undone is not None:
                if st.button(f"Next Table: {tables[next_undone]['name']}", use_container_width=True, type="primary"):
                    st.session_state.bundle_table_idx = next_undone
                    st.rerun()
            elif all_tbl_done:
                if st.button("Continue to View YAML", use_container_width=True, type="primary"):
                    st.session_state.bundle_view_idx = 0
                    if not st.session_state.bundle_views:
                        st.session_state.bundle_views = [new_view()]
                    st.session_state.bundle_step = 3
                    st.rerun()