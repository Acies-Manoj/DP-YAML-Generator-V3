import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.history import save_entry
from utils.generators import generate_dp_scanner_yaml
from utils.examples import EXAMPLE_DP_SCANNER, show_example

st.set_page_config(page_title="SADP — Scanner", layout="wide")
from utils.ui_utils import load_global_css, render_sidebar, floating_docs
load_global_css()
render_sidebar()
floating_docs("scanner")

st.markdown("""
<style>
.stButton>button { width: 100%; height: 45px; border-radius: 8px; font-size: 15px; }
</style>
""", unsafe_allow_html=True)

SADP_SCANNER_KEYS = [
    "sadp_scanner_step", "sadp_scanner_preview_mode",
    "sadp_scanner_tags", "sadp_scanner_dag_tags",
    "sadp_scanner_data_products", "sadp_generated_scanner",
]

for k, v in [
    ("sadp_scanner_step",         1),
    ("sadp_scanner_preview_mode", False),
    ("sadp_scanner_tags",         ["scanner", "data-product"]),
    ("sadp_scanner_dag_tags",     ["scanner2"]),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# Pre-fill filter from spec name if coming from spec step
if "sadp_scanner_data_products" not in st.session_state:
    spec_name = st.session_state.get("sadp_spec_name", "")
    st.session_state.sadp_scanner_data_products = [spec_name] if spec_name else [""]

_origin    = st.session_state.get("sadp_origin", "specific")
_spec_name = st.session_state.get("sadp_spec_name", "")
step       = st.session_state.sadp_scanner_step

nav_l, _, nav_r = st.columns([1, 4, 1.5])
with nav_l:
    if step == 1:
        if st.button("← Back"):
            if _origin == "sadp_full":
                st.switch_page("pages/4_SADP_Spec.py")
            else:
                st.session_state.home_screen = "specific"
                st.switch_page("app.py")
    else:
        if not st.session_state.sadp_scanner_preview_mode:
            if st.button("← Back"):
                st.session_state.sadp_scanner_step -= 1
                st.rerun()
with nav_r:
    if st.button("✖ Cancel / Start Over"):
        for k in SADP_SCANNER_KEYS:
            st.session_state.pop(k, None)
        st.rerun()

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — SCANNER FORM
# ══════════════════════════════════════════════════════════════════════════════
if step == 1:
    if not st.session_state.sadp_scanner_preview_mode:

        st.subheader("Scanner")
        show_example(st, "DP Scanner YAML", EXAMPLE_DP_SCANNER)
        st.caption(
            "The Scanner workflow crawls your data product and registers it in Metis. "
            "The filter pattern is pre-filled with the Spec name from the previous step."
        )

        if _spec_name:
            st.info(f"Scanner filter pre-filled from Spec name: `{_spec_name}`")

        with st.form("sadp_scanner_form"):

            st.markdown("#### Metadata")
            scm1, scm2 = st.columns(2)
            with scm1:
                sc_name = st.text_input(
                    "Workflow Name *",
                    placeholder="e.g. scan-retail-sales",
                    help="Convention: scan-<product-name>",
                )
            with scm2:
                sc_desc = st.text_input(
                    "Description",
                    value="The job scans data product from poros",
                )

            _scth1, _scth2 = st.columns([5, 1])
            with _scth1: st.markdown("**Tags**")
            with _scth2:
                if st.form_submit_button("➕ Add", key="sadp_add_scntag"):
                    st.session_state.sadp_scanner_tags.append(""); st.rerun()
            updated_scanner_tags = []
            for i, tag in enumerate(st.session_state.sadp_scanner_tags):
                sct1, sct2 = st.columns([5, 1])
                with sct1:
                    val = st.text_input(f"Tag {i+1}", value=tag, key=f"sadp_scntag_{i}",
                                        label_visibility="collapsed")
                    updated_scanner_tags.append(val)
                with sct2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"sadp_rm_scntag_{i}"):
                        st.session_state.sadp_scanner_tags.pop(i); st.rerun()

            st.divider()

            st.markdown("#### DAG")
            dg1, dg2 = st.columns(2)
            with dg1:
                sc_dag_name = st.text_input(
                    "DAG Name",
                    placeholder="e.g. scan-retail-sales-job",
                    help="Leave blank to auto-derive: <workflow-name>-job",
                )
                sc_dag_desc = st.text_input(
                    "DAG Description",
                    value="The job scans data-product from poros and register data to metis",
                )
            with dg2:
                sc_stack   = st.text_input("Stack",   value="scanner:2.0")
                sc_compute = st.text_input("Compute", value="runnable-default")

            _sdth1, _sdth2 = st.columns([5, 1])
            with _sdth1: st.markdown("**DAG Tags**")
            with _sdth2:
                if st.form_submit_button("➕ Add", key="sadp_add_scndtag"):
                    st.session_state.sadp_scanner_dag_tags.append(""); st.rerun()
            updated_scanner_dag_tags = []
            for i, tag in enumerate(st.session_state.sadp_scanner_dag_tags):
                sdct1, sdct2 = st.columns([5, 1])
                with sdct1:
                    val = st.text_input(f"DAG Tag {i+1}", value=tag, key=f"sadp_scndtag_{i}",
                                        label_visibility="collapsed")
                    updated_scanner_dag_tags.append(val)
                with sdct2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"sadp_rm_scndtag_{i}"):
                        st.session_state.sadp_scanner_dag_tags.pop(i); st.rerun()

            st.divider()

            _dpfh1, _dpfh2 = st.columns([5, 1])
            with _dpfh1: st.markdown("#### Data Product Filter Pattern")
            with _dpfh2:
                if st.form_submit_button("➕ Add", key="sadp_add_dpfilter"):
                    st.session_state.sadp_scanner_data_products.append(""); st.rerun()
            st.caption("Pre-filled from the Spec name. Each entry becomes an item under `dataProductFilterPattern.includes`.")
            sc_mark_deleted = st.checkbox("markDeletedDataProducts", value=True)

            updated_dp_filters = []
            for i, dp in enumerate(st.session_state.sadp_scanner_data_products):
                dpc1, dpc2 = st.columns([5, 1])
                with dpc1:
                    val = st.text_input(f"Include {i+1}", value=dp, key=f"sadp_dpfilter_{i}",
                                        placeholder="e.g. retail-sales", label_visibility="collapsed")
                    updated_dp_filters.append(val)
                with dpc2:
                    if i > 0:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.form_submit_button("❌", key=f"sadp_rm_dpfilter_{i}"):
                            st.session_state.sadp_scanner_data_products.pop(i); st.rerun()

            st.markdown(" ")
            submit3 = st.form_submit_button("Preview Scanner YAML →", use_container_width=True)

        st.session_state.sadp_scanner_tags          = updated_scanner_tags
        st.session_state.sadp_scanner_dag_tags      = updated_scanner_dag_tags
        st.session_state.sadp_scanner_data_products = updated_dp_filters

        if submit3:
            if not sc_name.strip():
                st.error("Workflow Name is required.")
            else:
                st.session_state.sadp_generated_scanner = generate_dp_scanner_yaml({
                    "name":            sc_name.strip(),
                    "description":     sc_desc.strip(),
                    "tags":            [t for t in st.session_state.sadp_scanner_tags if t.strip()],
                    "dag_name":        sc_dag_name.strip(),
                    "dag_description": sc_dag_desc.strip(),
                    "dag_tags":        [t for t in st.session_state.sadp_scanner_dag_tags if t.strip()],
                    "stack":           sc_stack.strip(),
                    "compute":         sc_compute.strip(),
                    "mark_deleted":    sc_mark_deleted,
                    "data_products":   [dp for dp in st.session_state.sadp_scanner_data_products if dp.strip()],
                })
                save_entry("SADP", "scanner", f"{sc_name.strip()}.yml", st.session_state.sadp_generated_scanner, dp_name=sc_name.strip())
                st.session_state.sadp_scanner_preview_mode = True
                st.rerun()

    else:
        st.subheader("Scanner YAML Preview")
        st.code(st.session_state.sadp_generated_scanner, language="yaml")
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("← Edit Scanner"):
                st.session_state.sadp_scanner_preview_mode = False
                st.rerun()
        with pc2:
            if st.button("Review All Files ✅", use_container_width=True, type="primary"):
                st.session_state.sadp_scanner_preview_mode = False
                if _origin == "sadp_full":
                    if "sadp_completed_steps" not in st.session_state:
                        st.session_state.sadp_completed_steps = set()
                    st.session_state.sadp_completed_steps.add(5)
                st.session_state.sadp_scanner_step = 2
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — REVIEW & DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════
elif step == 2:
    bundle_name = st.session_state.get("sadp_bundle_name", "bundle")
    spec_name   = st.session_state.get("sadp_spec_name",   "spec")

    st.subheader("Review All Files & Download")
    st.success("All 3 files generated. Review below and download individually or as a ZIP.")
    st.markdown(" ")

    tab1, tab2, tab3 = st.tabs(["Bundle", "Spec", "Scanner"])
    with tab1:
        st.code(st.session_state.get("sadp_generated_bundle", ""), language="yaml")
        st.download_button("⬇ Download Bundle YAML",
                           data=st.session_state.get("sadp_generated_bundle", ""),
                           file_name=f"{bundle_name}.yml", mime="text/yaml", use_container_width=True)
    with tab2:
        st.code(st.session_state.get("sadp_generated_spec", ""), language="yaml")
        st.download_button("⬇ Download Spec YAML",
                           data=st.session_state.get("sadp_generated_spec", ""),
                           file_name=f"{spec_name}.yml", mime="text/yaml", use_container_width=True)
    with tab3:
        st.code(st.session_state.get("sadp_generated_scanner", ""), language="yaml")
        st.download_button("⬇ Download Scanner YAML",
                           data=st.session_state.get("sadp_generated_scanner", ""),
                           file_name=f"scan-{spec_name}.yml", mime="text/yaml", use_container_width=True)

    st.divider()

    import zipfile, io
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr(f"dp-deployment/{bundle_name}.yml",       st.session_state.get("sadp_generated_bundle", ""))
        zf.writestr(f"dp-deployment/{spec_name}.yml",         st.session_state.get("sadp_generated_spec", ""))
        zf.writestr(f"dp-deployment/scan-{spec_name}.yml",    st.session_state.get("sadp_generated_scanner", ""))
    zip_buf.seek(0)
    st.download_button("⬇ Download All as ZIP", data=zip_buf,
                       file_name=f"{spec_name}-sadp-deployment.zip",
                       mime="application/zip", use_container_width=True)

    if _origin == "sadp_full":
        st.divider()
        st.success("SADP Deployment complete. Your SADP data product is fully generated.")
        if st.button("Back to SADP Flow", use_container_width=True, type="primary"):
            st.switch_page("pages/sadp_flow.py")