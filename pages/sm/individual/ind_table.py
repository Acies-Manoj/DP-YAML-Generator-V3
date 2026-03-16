import streamlit as st
from utils.generators import generate_table_yaml
from utils.history import save_entry
from utils.examples import EXAMPLE_TABLE_YAML, show_example
from utils.ui_utils import inline_docs_banner
from utils.llm_measures import suggest_measures
from utils.llm_segments import suggest_segments

DIM_TYPES     = ["string", "number", "boolean", "time"]
MEASURE_TYPES = ["number", "count", "count_distinct", "sum", "avg", "min", "max", "string"]
JOIN_RELS     = ["many_to_one", "one_to_many", "one_to_one"]


def render_ind_table():

    st.subheader("Table YAML Builder")
    inline_docs_banner("lens", "segments")

    for key, default in [
        ("tbl_dimensions", []),
        ("tbl_measures",   []),
        ("tbl_joins",      []),
        ("tbl_segments",   []),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default


    btn_c1, btn_c2, btn_c3, btn_c4, btn_c5, btn_c6 = st.columns(6)
    with btn_c1:
        if st.button("➕ Add Dimension"):
            st.session_state.tbl_dimensions.append(
                {"name": "", "type": "string", "column": "", "description": "", "primary_key": False, "public": False})
            st.rerun()
    with btn_c2:
        if st.button("➕ Add Measure"):
            st.session_state.tbl_measures.append({"name": "", "sql": "", "type": "number", "description": ""})
            st.rerun()
    with btn_c3:
        if st.button("✨ Suggest Measures", help="Use AI to suggest measures from your columns"):
            _dims = st.session_state.get("tbl_dimensions", [])
            if not any(d.get("name") or d.get("column") for d in _dims):
                st.warning("Add at least one dimension first so the AI has columns to work with.")
            else:
                with st.spinner("Thinking…"):
                    try:
                        _sug = suggest_measures(
                            table_name = st.session_state.get("_ind_tbl_name_hint", ""),
                            dimensions = _dims,
                            table_desc = "",
                        )
                        st.session_state["ind_tbl_meas_suggestions"] = _sug
                    except Exception as _e:
                        st.session_state["ind_tbl_meas_suggestions"] = []
                        st.error(f"Suggestion failed: {_e}")
                st.rerun()
    with btn_c4:
        if st.button("✨ Suggest Segments", help="Use AI to suggest segments from your columns"):
            _dims = st.session_state.get("tbl_dimensions", [])
            if not any(d.get("name") or d.get("column") for d in _dims):
                st.warning("Add at least one dimension first so the AI has columns to work with.")
            else:
                with st.spinner("Thinking…"):
                    try:
                        _seg_sug = suggest_segments(
                            table_name = st.session_state.get("_ind_tbl_name_hint", ""),
                            dimensions = _dims,
                            table_desc = "",
                        )
                        st.session_state["ind_tbl_seg_suggestions"] = _seg_sug
                    except Exception as _e:
                        st.session_state["ind_tbl_seg_suggestions"] = []
                        st.error(f"Suggestion failed: {_e}")
                st.rerun()
    with btn_c5:
        if st.button("➕ Add Join"):
            st.session_state.tbl_joins.append({"name": "", "relationship": "many_to_one", "sql": ""})
            st.rerun()
    with btn_c6:
        if st.button("➕ Add Segment"):
            st.session_state.tbl_segments.append({"name": "", "sql": "", "description": "", "includes": "", "excludes": ""})
            st.rerun()

    # ── AI Measure Suggestion Cards (outside form) ─────────────────────────
    _ind_suggestions = st.session_state.get("ind_tbl_meas_suggestions", [])
    if _ind_suggestions:
        st.markdown(
            "<div style='background:#0f2237;border:1px solid #1e40af;"
            "border-radius:10px;padding:14px 16px 10px 16px;margin:10px 0 12px 0;'>"
            "<p style='color:#93c5fd;font-weight:700;font-size:13px;margin:0 0 10px 0;'>"
            "✨ Measure Suggestions — click ✅ to add to your measures list</p>",
            unsafe_allow_html=True,
        )
        _to_remove = []
        for _si, _sug in enumerate(_ind_suggestions):
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
                    if st.button("✅", key=f"ind_sug_acc_{_si}", help="Accept", use_container_width=True):
                        st.session_state.tbl_measures.append({
                            "name":        _sug["name"],
                            "sql":         _sug["sql"],
                            "type":        _sug["type"],
                            "description": _sug.get("description", ""),
                        })
                        _to_remove.append(_si)
                with _dis_col:
                    if st.button("✕", key=f"ind_sug_dis_{_si}", help="Dismiss", use_container_width=True):
                        _to_remove.append(_si)
            st.markdown("<hr style='border-color:#1e3a5f;margin:6px 0;'>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        if _to_remove:
            st.session_state["ind_tbl_meas_suggestions"] = [
                s for i, s in enumerate(_ind_suggestions) if i not in _to_remove
            ]
            st.rerun()

    # ── AI Segment Suggestion Cards (outside form) ─────────────────────────
    _ind_seg_suggestions = st.session_state.get("ind_tbl_seg_suggestions", [])
    if _ind_seg_suggestions:
        st.markdown(
            "<div style='background:#0f1f0f;border:1px solid #166534;"
            "border-radius:10px;padding:14px 16px 10px 16px;margin:10px 0 12px 0;'>"
            "<p style='color:#86efac;font-weight:700;font-size:13px;margin:0 0 10px 0;'>"
            "✨ Segment Suggestions — click ✅ to add to your segments list</p>",
            unsafe_allow_html=True,
        )
        _seg_to_remove = []
        for _si, _sug in enumerate(_ind_seg_suggestions):
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
                    if st.button("✅", key=f"ind_seg_acc_{_si}", help="Accept", use_container_width=True):
                        st.session_state.tbl_segments.append({
                            "name":        _sug["name"],
                            "sql":         _sug["sql"],
                            "description": _sug.get("description", ""),
                            "includes":    "",
                            "excludes":    "",
                        })
                        _seg_to_remove.append(_si)
                with _dis_col:
                    if st.button("✕", key=f"ind_seg_dis_{_si}", help="Dismiss", use_container_width=True):
                        _seg_to_remove.append(_si)
            st.markdown("<hr style='border-color:#14532d;margin:6px 0;'>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        if _seg_to_remove:
            st.session_state["ind_tbl_seg_suggestions"] = [
                s for i, s in enumerate(_ind_seg_suggestions) if i not in _seg_to_remove
            ]
            st.rerun()

    st.markdown(" ")

    with st.form("table_yaml_form"):
        st.markdown("#### Table Metadata")
        mc1, mc2 = st.columns(2)
        with mc1:
            tbl_name   = st.text_input("Table Name *", placeholder="e.g. customer",
                                       value=st.session_state.get("_ind_tbl_name_hint", ""))
            # Persist name so the Suggest button (outside the form) can read it
            st.session_state["_ind_tbl_name_hint"] = tbl_name
            tbl_public = st.checkbox("Public", value=True)
        with mc2:
            tbl_desc = st.text_area("Description", placeholder="e.g. Contains customer demographic and transaction data.", height=100)

        if st.session_state.tbl_joins:
            st.divider()
            st.markdown("#### Joins")
            for i, j in enumerate(st.session_state.tbl_joins):
                jc1, jc2, jc3, jc4 = st.columns([2.5, 2, 4, 0.8])
                with jc1: st.session_state.tbl_joins[i]["name"] = st.text_input("Join Name", value=j["name"], key=f"j_name_{i}", placeholder="e.g. branch")
                with jc2: st.session_state.tbl_joins[i]["relationship"] = st.selectbox("Relationship", JOIN_RELS, index=JOIN_RELS.index(j["relationship"]) if j["relationship"] in JOIN_RELS else 0, key=f"j_rel_{i}")
                with jc3: st.session_state.tbl_joins[i]["sql"] = st.text_input("SQL", value=j["sql"], key=f"j_sql_{i}", placeholder="{TABLE.BRANCH} = {branch.OFFICE_NAME}")
                with jc4:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"rm_join_{i}"):
                        st.session_state.tbl_joins.pop(i); st.rerun()

        if st.session_state.tbl_dimensions:
            st.divider()
            st.markdown("#### Dimensions")
            for i, d in enumerate(st.session_state.tbl_dimensions):
                dc1, dc2, dc3, dc4 = st.columns([2.5, 2, 3.5, 0.8])
                with dc1:
                    st.session_state.tbl_dimensions[i]["name"]   = st.text_input("Name",   value=d["name"],   key=f"d_name_{i}", placeholder="e.g. customer_id")
                    st.session_state.tbl_dimensions[i]["column"] = st.text_input("Column", value=d["column"], key=f"d_col_{i}",  placeholder="e.g. customer_id")
                with dc2:
                    st.session_state.tbl_dimensions[i]["type"]        = st.selectbox("Type", DIM_TYPES, index=DIM_TYPES.index(d["type"]) if d["type"] in DIM_TYPES else 0, key=f"d_type_{i}")
                    st.session_state.tbl_dimensions[i]["primary_key"] = st.checkbox("Primary Key", value=d["primary_key"], key=f"d_pk_{i}")
                    st.session_state.tbl_dimensions[i]["public"]      = st.checkbox("Public",      value=d["public"],      key=f"d_pub_{i}")
                with dc3:
                    st.session_state.tbl_dimensions[i]["description"] = st.text_area("Description", value=d["description"], key=f"d_desc_{i}", height=120)
                with dc4:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"rm_dim_{i}"):
                        st.session_state.tbl_dimensions.pop(i); st.rerun()
                st.markdown("---")

        if st.session_state.tbl_measures:
            st.divider()
            st.markdown("#### Measures")
            for i, m in enumerate(st.session_state.tbl_measures):
                ms1, ms2, ms3, ms4 = st.columns([2.5, 2, 3.5, 0.8])
                with ms1:
                    st.session_state.tbl_measures[i]["name"] = st.text_input("Name", value=m["name"], key=f"m_name_{i}", placeholder="e.g. total_customers")
                    st.session_state.tbl_measures[i]["sql"]  = st.text_input("SQL Expression", value=m["sql"], key=f"m_sql_{i}", placeholder="COUNT(DISTINCT {customer_id})")
                with ms2:
                    st.session_state.tbl_measures[i]["type"] = st.selectbox("Type", MEASURE_TYPES, index=MEASURE_TYPES.index(m["type"]) if m["type"] in MEASURE_TYPES else 0, key=f"m_type_{i}")
                with ms3:
                    st.session_state.tbl_measures[i]["description"] = st.text_area("Description", value=m["description"], key=f"m_desc_{i}", height=100)
                with ms4:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"rm_meas_{i}"):
                        st.session_state.tbl_measures.pop(i); st.rerun()
                st.markdown("---")

        if st.session_state.tbl_segments:
            st.divider()
            st.markdown("#### Segments")
            for i, s in enumerate(st.session_state.tbl_segments):
                sc1, sc2, sc3 = st.columns([3, 3, 0.8])
                with sc1:
                    st.session_state.tbl_segments[i]["name"] = st.text_input("Segment Name", value=s["name"], key=f"s_name_{i}", placeholder="e.g. high_value_customers")
                    st.session_state.tbl_segments[i]["sql"]  = st.text_input("SQL Filter",   value=s["sql"],  key=f"s_sql_{i}",  placeholder="e.g. {customer.lifetime_value} > 1000")
                with sc2:
                    st.session_state.tbl_segments[i]["description"] = st.text_input("Description", value=s["description"], key=f"s_desc_{i}", placeholder="e.g. Filters customers with high lifetime value.")
                    st.markdown("**User Groups (meta > secure)**")
                    sg1, sg2 = st.columns(2)
                    with sg1: st.session_state.tbl_segments[i]["includes"] = st.text_input("Includes (comma-separated)", value=s.get("includes", ""), key=f"s_inc_{i}", placeholder="india, us")
                    with sg2: st.session_state.tbl_segments[i]["excludes"] = st.text_input("Excludes (comma-separated)", value=s.get("excludes", ""), key=f"s_exc_{i}", placeholder="default")
                with sc3:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"rm_seg_{i}"):
                        st.session_state.tbl_segments.pop(i); st.rerun()
                st.markdown("---")

        st.markdown(" ")
        generate_yaml = st.form_submit_button("Generate Table YAML", use_container_width=True)

    if generate_yaml:
        if not tbl_name.strip():
            st.error("Table Name is required.")
        else:
            segments_data = []
            for s in st.session_state.tbl_segments:
                if not s.get("name", "").strip(): continue
                segments_data.append({
                    "name": s["name"], "sql": s["sql"], "description": s.get("description", ""),
                    "includes": [g.strip() for g in s.get("includes", "").split(",") if g.strip()],
                    "excludes": [g.strip() for g in s.get("excludes", "").split(",") if g.strip()],
                })
            table_data = {
                "name": tbl_name.strip(), "description": tbl_desc.strip(), "public": tbl_public,
                "joins": st.session_state.tbl_joins, "dimensions": st.session_state.tbl_dimensions,
                "measures": st.session_state.tbl_measures, "segments": segments_data,
            }
            st.session_state.generated_table_yaml = generate_table_yaml(table_data)
            save_entry("Specific", "table", f"{tbl_name.strip()}.yml", st.session_state.generated_table_yaml)
            st.session_state.tbl_name_for_file    = tbl_name.strip()

    if "generated_table_yaml" in st.session_state:
        st.markdown("### Table YAML Preview")
        st.code(st.session_state.generated_table_yaml, language="yaml")
        st.download_button(
            label="⬇ Download Table YAML",
            data=st.session_state.generated_table_yaml,
            file_name=f"{st.session_state.get('tbl_name_for_file', 'table')}.yml",
            mime="text/yaml",
            use_container_width=True
        )


# ─────────────────────────────────────────────────────────────────────────────
# VIEW YAML BUILDER
# ─────────────────────────────────────────────────────────────────────────────