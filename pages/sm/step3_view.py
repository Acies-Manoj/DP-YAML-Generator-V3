import streamlit as st
from utils.generators import generate_view_yaml
from sm.state import new_view
from utils.examples import EXAMPLE_VIEW_YAML, show_example
from utils.ui_utils import inline_docs_banner

_CRON_PRESETS = {
    "Every 15 minutes":     "*/15 * * * *",
    "Every 30 minutes":     "*/30 * * * *",
    "Every hour":           "0 * * * *",
    "Every 6 hours":        "0 */6 * * *",
    "Every day (midnight)": "0 0 * * *",
    "Custom":               None,
}


def render_step3():
    inline_docs_banner("views")
    tables = st.session_state.bundle_tables
    views  = st.session_state.bundle_views
    vidx   = st.session_state.bundle_view_idx

    views  = st.session_state.bundle_views
    tables = st.session_state.bundle_tables

    # All table names for dropdowns
    table_names = [tbl["name"] for tbl in tables if tbl.get("name")]

    if not table_names:
        st.warning("Please complete the Table YAML step for all tables before creating Views.")
        st.stop()

    # All fields per table for include multiselect
    def get_table_fields(tbl_name):
        tbl = next((t for t in tables if t["name"] == tbl_name), None)
        if not tbl: return []
        dims = [d["name"] for d in tbl.get("dims", []) if d.get("name")]
        measures = [m["name"] for m in tbl.get("measures", []) if m.get("name")]
        return [("Dimension", d) for d in dims] + [("Measure", m) for m in measures]

    st.subheader("Step 3 — View YAMLs")
    show_example(st, "View YAML", EXAMPLE_VIEW_YAML)
    st.caption("Views are optional. You can skip this step or add multiple views.")

    # Skip button
    vob1, vob2 = st.columns(2)
    with vob1:
        if st.button("Skip Views — Continue to Repo Credential", use_container_width=True):
            st.session_state.bundle_views = []
            st.session_state.bundle_view_idx = 0
            st.session_state.bundle_step = 4
            st.rerun()

    # ── Auto-initialise: always ensure at least one view exists ──────────────
    if not st.session_state.bundle_views:
        st.session_state.bundle_views.append(new_view())
        st.rerun()

    # Re-read after potential init above
    views = st.session_state.bundle_views

    # Guard: reset vidx if out of range
    if vidx >= len(views):
        st.session_state.bundle_view_idx = 0
        vidx = 0

    # View tabs if multiple views
    if len(views) > 1:
        vtabs = st.columns(len(views))
        for i, v in enumerate(views):
            with vtabs[i]:
                done_mark = "✅" if v.get("generated_view_yaml") else ""
                btn_type = "primary" if i == vidx else "secondary"
                if st.button(f"{v.get('name') or f'View {i+1}'} {done_mark}", key=f"view_tab_{i}", type=btn_type, use_container_width=True):
                    st.session_state.bundle_view_idx = i
                    st.rerun()
        st.divider()

    v = views[vidx]

    if not v.get("preview_mode"):

        vn_label = v.get("name") or f"View {vidx + 1}"
        st.markdown(f"**Editing: {vn_label}**")

        st.markdown("#### View Metadata")
        vvm1, vvm2 = st.columns(2)
        with vvm1:
            b_view_name   = st.text_input("View Name *", value=v.get("name",""), key=f"b_vname_{vidx}", placeholder="e.g. customer_lifetime_value")
            b_view_public = st.checkbox("Public", value=v.get("public", True), key=f"b_vpub_{vidx}")
        with vvm2:
            b_view_desc = st.text_area("Description", value=v.get("desc","View for the data product semantic model."),
                key=f"b_vdesc_{vidx}",
                placeholder="e.g. Measures total revenue per customer.", height=100)

        st.divider()
        st.markdown("#### Meta")
        b_view_title = st.text_input("Title", value=v.get("title",""), key=f"b_vtitle_{vidx}", placeholder="e.g. Customer Lifetime Value")

        # ── Tags ──────────────────────────────────────────────────────────────
        st.markdown("**Tags**")
        # Ensure view_tags is initialised
        if not v.get("view_tags"):
            views[vidx]["view_tags"] = [""]
        updated_view_tags = []
        for i, tag in enumerate(views[vidx]["view_tags"]):
            vtc1, vtc2 = st.columns([5, 1])
            with vtc1:
                val = st.text_input(f"Tag {i+1}", value=tag, key=f"b_vtag_{vidx}_{i}", placeholder="e.g. DPDomain.Retail")
                updated_view_tags.append(val)
            with vtc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("X", key=f"b_rm_vtag_{vidx}_{i}"):
                    views[vidx]["view_tags"].pop(i)
                    st.rerun()
        views[vidx]["view_tags"] = updated_view_tags

        if st.button("＋ Add Tag", key=f"v_add_tag_{vidx}"):
            views[vidx]["view_tags"].append("")
            st.rerun()

        st.divider()
        st.markdown("#### Metric")

        # Cron preset dropdown
        _saved_expr = v.get("metric_expr", "*/45 * * * *")
        _preset_match = next((k for k, val in _CRON_PRESETS.items() if val == _saved_expr), "Custom")
        _preset_opts  = list(_CRON_PRESETS.keys())

        vm1, vm2, vm3 = st.columns(3)
        with vm1:
            _sel_preset = st.selectbox(
                "Schedule Preset",
                _preset_opts,
                index=_preset_opts.index(_preset_match),
                key=f"b_vcron_preset_{vidx}",
                help="Pick a common schedule or choose Custom to write your own cron expression.")
            if _sel_preset != "Custom":
                _cron_value = _CRON_PRESETS[_sel_preset]
                st.session_state[f"b_vexpr_{vidx}"] = _cron_value
            else:
                _cron_value = _saved_expr
            b_metric_expr = st.text_input(
                "Cron Expression",
                value=_cron_value,
                key=f"b_vexpr_{vidx}",
                disabled=(_sel_preset != "Custom"),
                help="Auto-filled by preset above. Switch to Custom to edit manually.")
        with vm2:
            b_metric_tz  = st.text_input("Timezone", value=v.get("metric_tz","UTC"), key=f"b_vtz_{vidx}")
        with vm3:
            b_metric_win = st.text_input("Window", value=v.get("metric_win","day"), key=f"b_vwin_{vidx}")

        # ── Metric Excludes ───────────────────────────────────────────────────
        st.markdown("**Metric Excludes**")
        # Ensure view_metric_excludes is initialised
        if not v.get("view_metric_excludes"):
            views[vidx]["view_metric_excludes"] = [""]
        updated_view_excl = []
        for i, exc in enumerate(views[vidx]["view_metric_excludes"]):
            vec1, vec2 = st.columns([5, 1])
            with vec1:
                val = st.text_input(f"Exclude {i+1}", value=exc, key=f"b_vexc_{vidx}_{i}", placeholder="e.g. total_customers")
                updated_view_excl.append(val)
            with vec2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("X", key=f"b_rm_vexc_{vidx}_{i}"):
                    views[vidx]["view_metric_excludes"].pop(i)
                    st.rerun()
        views[vidx]["view_metric_excludes"] = updated_view_excl

        if st.button("＋ Add Metric Exclude", key=f"v_add_exc_{vidx}"):
            views[vidx]["view_metric_excludes"].append("")
            st.rerun()

        # ── Tables (Join Paths) ───────────────────────────────────────────────
        st.divider()
        st.markdown("#### Tables (Join Paths)")
        st.caption("Select tables from your SQL files. For each table, choose which fields to include.")

        # Ensure view_tables is initialised
        if not views[vidx].get("view_tables"):
            views[vidx]["view_tables"] = [{"join_path": table_names[0] if table_names else "", "prefix": True, "includes": []}]

        updated_view_tables = []
        for i, vt in enumerate(views[vidx]["view_tables"]):
            vt_col1, vt_col2, vt_col3 = st.columns([2, 1, 0.5])
            with vt_col1:
                sel_tbl = st.selectbox(
                    f"Table {i+1}",
                    table_names,
                    index=table_names.index(vt["join_path"]) if vt["join_path"] in table_names else 0,
                    key=f"vt_sel_{vidx}_{i}"
                )
            with vt_col2:
                vt_prefix = st.checkbox("Prefix", value=vt.get("prefix", True), key=f"vt_pre_{vidx}_{i}")
            with vt_col3:
                st.markdown("<br><br>", unsafe_allow_html=True)
                if i > 0 and st.button("X", key=f"vt_rm_{vidx}_{i}"):
                    views[vidx]["view_tables"].pop(i); st.rerun()

            # If user switched table, clear saved includes so stale fields don't carry over
            prev_includes = vt.get("includes", []) if vt.get("join_path") == sel_tbl else []

            fields = get_table_fields(sel_tbl)
            if fields:
                dim_fields  = [f for label, f in fields if label == "Dimension"]
                meas_fields = [f for label, f in fields if label == "Measure"]

                selected = []
                if dim_fields:
                    st.markdown("**Dimensions** (all unselected by default — select to include):")
                    dim_cols = st.columns(min(4, len(dim_fields)))
                    for fi, fname in enumerate(dim_fields):
                        checked = dim_cols[fi % 4].checkbox(fname, value=(fname in prev_includes), key=f"vt_dim_{vidx}_{i}_{sel_tbl}_{fi}")
                        if checked: selected.append(fname)
                if meas_fields:
                    st.markdown("**Measures**:")
                    meas_cols = st.columns(min(4, len(meas_fields)))
                    for fi, fname in enumerate(meas_fields):
                        checked = meas_cols[fi % 4].checkbox(fname, value=(fname in prev_includes), key=f"vt_meas_{vidx}_{i}_{sel_tbl}_{fi}")
                        if checked: selected.append(fname)

                updated_view_tables.append({"join_path": sel_tbl, "prefix": vt_prefix, "includes": selected})
            else:
                updated_view_tables.append({"join_path": sel_tbl, "prefix": vt_prefix, "includes": []})
            st.markdown("---")

        views[vidx]["view_tables"] = updated_view_tables

        if st.button("Add Another Table to View", key=f"v_add_tbl_{vidx}"):
            views[vidx]["view_tables"].append({"join_path": table_names[0] if table_names else "", "prefix": True, "includes": []})
            st.rerun()

        # ── Preview button ────────────────────────────────────────────────────
        st.divider()
        if st.button("Preview View YAML ↓", key=f"b_view_preview_bot_{vidx}", type="primary", use_container_width=True):
            st.session_state[f"b_view_preview_clicked_{vidx}"] = True
            st.rerun()

        if st.session_state.pop(f"b_view_preview_clicked_{vidx}", False):
            if not b_view_name.strip():
                st.error("View Name is required.")
            else:
                tables_data = []
                for vt in views[vidx]["view_tables"]:
                    if not vt.get("join_path"): continue
                    tables_data.append({
                        "join_path": vt["join_path"],
                        "prefix":    vt.get("prefix", True),
                        "includes":  vt.get("includes", []),
                    })
                view_data = {
                    "name": b_view_name.strip(), "description": b_view_desc.strip(), "public": b_view_public,
                    "meta": {
                        "title": b_view_title.strip(),
                        "tags":  [t.strip() for t in views[vidx]["view_tags"] if t.strip()],
                        "metric": {
                            "expression": b_metric_expr.strip(), "timezone": b_metric_tz.strip(),
                            "window": b_metric_win.strip(),
                            "excludes": [e.strip() for e in views[vidx]["view_metric_excludes"] if e.strip()],
                        }
                    },
                    "tables": tables_data,
                }
                views[vidx]["generated_view_yaml"] = generate_view_yaml(view_data)
                views[vidx]["name"]        = b_view_name.strip()
                views[vidx]["desc"]        = b_view_desc.strip()
                views[vidx]["title"]       = b_view_title.strip()
                views[vidx]["public"]      = b_view_public
                views[vidx]["metric_expr"] = b_metric_expr.strip()
                views[vidx]["metric_tz"]   = b_metric_tz.strip()
                views[vidx]["metric_win"]  = b_metric_win.strip()
                views[vidx]["preview_mode"] = True
                st.rerun()

    else:
        st.subheader(f"View YAML Preview — {v.get('name','view')}")
        st.code(v["generated_view_yaml"], language="yaml")
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            if st.button("Edit View"):
                views[vidx]["preview_mode"] = False
                st.rerun()
        with pc2:
            if st.button("Add Another View", use_container_width=True):
                st.session_state.bundle_views.append(new_view())
                st.session_state.bundle_view_idx = len(st.session_state.bundle_views) - 1
                st.rerun()
        with pc3:
            if st.button("Continue to Repo Credential", use_container_width=True, type="primary"):
                st.session_state.bundle_step = 4
                st.rerun()