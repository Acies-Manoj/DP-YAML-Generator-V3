import streamlit as st
from utils.generators import generate_view_yaml
from utils.history import save_entry
from utils.examples import EXAMPLE_VIEW_YAML, show_example
from utils.ui_utils import inline_docs_banner


def render_ind_view():
    st.subheader("View YAML Builder")
    inline_docs_banner("views")

    for key, default in [("view_tags",[""]), ("view_metric_excludes",[""]), ("view_tables",[])]:
        if key not in st.session_state:
            st.session_state[key] = default

    bc1, bc2, bc3 = st.columns(3)
    with bc1:
        if st.button("➕ Add Tag"): st.session_state.view_tags.append(""); st.rerun()
    with bc2:
        if st.button("➕ Add Metric Exclude"): st.session_state.view_metric_excludes.append(""); st.rerun()
    with bc3:
        if st.button("➕ Add Table (join path)"): st.session_state.view_tables.append({"join_path":"","prefix":True,"includes":""}); st.rerun()

    st.markdown(" ")

    with st.form("view_yaml_form"):
        st.markdown("#### View Metadata")
        vm1, vm2 = st.columns(2)
        with vm1:
            view_name   = st.text_input("View Name *", placeholder="e.g. customer_lifetime_value")
            view_public = st.checkbox("Public", value=True)
        with vm2:
            view_desc = st.text_area("Description", placeholder="e.g. Measures total revenue generated per customer over their lifetime.", height=100)

        st.divider()
        st.markdown("#### Meta")
        view_title = st.text_input("Title", placeholder="e.g. Customer Lifetime Value")

        st.markdown("**Tags**")
        st.caption("Format: DPDomain.Marketing  |  DPUsecase.Customer Segmentation  |  DPTier.Consumer Aligned")
        updated_tags = []
        for i, tag in enumerate(st.session_state.view_tags):
            tc1, tc2 = st.columns([5,1])
            with tc1:
                val = st.text_input(f"Tag {i+1}", value=tag, key=f"vtag_{i}", placeholder="e.g. DPDomain.Retail")
                updated_tags.append(val)
            with tc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("❌", key=f"rm_tag_{i}"):
                    st.session_state.view_tags.pop(i); st.rerun()

        st.divider()
        st.markdown("#### Metric")
        met1, met2, met3 = st.columns(3)
        with met1: metric_expr = st.text_input("Cron Expression", value="*/45  * * * *")
        with met2: metric_tz   = st.text_input("Timezone", value="UTC")
        with met3: metric_win  = st.text_input("Window", value="day")

        st.markdown("**Metric Excludes**")
        updated_excludes = []
        for i, exc in enumerate(st.session_state.view_metric_excludes):
            ec1, ec2 = st.columns([5,1])
            with ec1:
                val = st.text_input(f"Exclude {i+1}", value=exc, key=f"vexc_{i}", placeholder="e.g. total_customers")
                updated_excludes.append(val)
            with ec2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("❌", key=f"rm_exc_{i}"):
                    st.session_state.view_metric_excludes.pop(i); st.rerun()

        if st.session_state.view_tables:
            st.divider()
            st.markdown("#### Tables (Join Paths)")
            for i, t in enumerate(st.session_state.view_tables):
                tc1, tc2, tc3, tc4 = st.columns([2, 1, 5, 0.8])
                with tc1: st.session_state.view_tables[i]["join_path"] = st.text_input("Join Path", value=t["join_path"], key=f"vt_jp_{i}", placeholder="e.g. purchase")
                with tc2: st.session_state.view_tables[i]["prefix"]    = st.checkbox("Prefix", value=t.get("prefix", True), key=f"vt_pre_{i}")
                with tc3: st.session_state.view_tables[i]["includes"]  = st.text_area("Includes (one per line)", value=t.get("includes",""), key=f"vt_inc_{i}", height=120, placeholder="customer_id\npurchase_date")
                with tc4:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"rm_vt_{i}"):
                        st.session_state.view_tables.pop(i); st.rerun()
                st.markdown("---")

        st.markdown(" ")
        generate_view = st.form_submit_button("Generate View YAML", use_container_width=True)

    st.session_state.view_tags            = updated_tags
    st.session_state.view_metric_excludes = updated_excludes

    if generate_view:
        if not view_name.strip():
            st.error("View Name is required.")
        else:
            tables_data = []
            for t in st.session_state.view_tables:
                if not t.get("join_path","").strip(): continue
                inc_list = [ln.strip() for ln in t.get("includes","").splitlines() if ln.strip()]
                tables_data.append({"join_path": t["join_path"].strip(), "prefix": t.get("prefix", True), "includes": inc_list})
            view_data = {
                "name": view_name.strip(), "description": view_desc.strip(), "public": view_public,
                "meta": {
                    "title": view_title.strip(),
                    "tags":  [t.strip() for t in st.session_state.view_tags if t.strip()],
                    "metric": {
                        "expression": metric_expr.strip(), "timezone": metric_tz.strip(),
                        "window": metric_win.strip(),
                        "excludes": [e.strip() for e in st.session_state.view_metric_excludes if e.strip()],
                    }
                },
                "tables": tables_data,
            }
            st.session_state.generated_view_yaml = generate_view_yaml(view_data)
            save_entry("Specific", "view", f"{view_name.strip()}.yml", st.session_state.generated_view_yaml)
            st.session_state.view_name_for_file  = view_name.strip()

    if "generated_view_yaml" in st.session_state:
        st.markdown("### View YAML Preview")
        st.code(st.session_state.generated_view_yaml, language="yaml")
        st.download_button("⬇ Download View YAML", data=st.session_state.generated_view_yaml,
                           file_name=f"{st.session_state.get('view_name_for_file','view')}.yml",
                           mime="text/yaml", use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# LENS DEPLOYMENT BUILDER
# ─────────────────────────────────────────────────────────────────────────────