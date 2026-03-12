import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.examples import EXAMPLE_BUNDLE, EXAMPLE_SPEC, EXAMPLE_DP_SCANNER, show_example
from utils.generators import generate_bundle_yaml, generate_spec_yaml, generate_dp_scanner_yaml
from utils.history import save_entry

st.set_page_config(page_title="CADP — DP Deployment", layout="wide")
from utils.ui_utils import load_global_css, render_sidebar, floating_docs
load_global_css()
render_sidebar()
floating_docs("bundle", "spec", "scanner")

st.markdown("""
<style>
.stButton>button { width: 100%; height: 45px; border-radius: 8px; font-size: 15px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# STATE INIT
# ─────────────────────────────────────────────────────────────────────────────
DP_KEYS_TO_CLEAR = [
    "dp_step", "dp_preview_mode",
    "dp_bundle_tags", "dp_bundle_qc_resources",
    "dp_spec_tags", "dp_spec_refs", "dp_spec_collaborators",
    "dp_spec_inputs", "dp_spec_outputs",
    "dp_scanner_tags", "dp_scanner_dag_tags", "dp_scanner_data_products",
    "dp_generated_bundle", "dp_generated_spec", "dp_generated_scanner",
    "dp_bundle_name",
]

for k, v in [
    ("dp_step",                  1),
    ("dp_entry_step",            1),
    ("dp_preview_mode",          False),
    ("dp_bundle_tags",           ["dataproduct"]),
    ("dp_bundle_qc_resources",   []),   # list of {file, workspace}
    ("dp_spec_tags",             [""]),
    ("dp_spec_refs",             [{"title": "Workspace Info", "href": "https://dataos.info/interfaces/cli/command_reference/#workspace"}]),
    ("dp_spec_collaborators",    [{"name": "", "description": "owner"}]),
    ("dp_spec_inputs",           [{"ref": ""}]),
    ("dp_spec_outputs",          [{"ref": ""}]),
    ("dp_scanner_tags",          ["scanner", "data-product"]),
    ("dp_scanner_dag_tags",      ["scanner2"]),
    ("dp_scanner_data_products", [""]),
]:
    if k not in st.session_state:
        st.session_state[k] = v

step = st.session_state.dp_step

# ─────────────────────────────────────────────────────────────────────────────
# NAV
# ─────────────────────────────────────────────────────────────────────────────
STEP_LABELS = ["1. Bundle", "2. Spec", "3. Scanner", "4. Review & Download"]
label = STEP_LABELS[step - 1] if step <= 4 else "Complete"
st.progress((step - 1) / 4, text=f"Step {step} of 4 — {label}")

_dp_origin = st.session_state.get("dp_origin", "specific")

def _dp_back():
    for k in DP_KEYS_TO_CLEAR:
        st.session_state.pop(k, None)
    if _dp_origin == "cadp_full":
        st.switch_page("pages/cadp_flow.py")
    else:
        st.session_state.home_screen = "specific"
        st.switch_page("app.py")

nav_l, _, nav_r = st.columns([1, 4, 1.5])
with nav_l:
    if step == 1:
        if st.button("← Back"):
            _dp_back()
    else:
        if not st.session_state.dp_preview_mode:
            if st.button("← Back"):
                if _dp_origin == "specific" and step == st.session_state.dp_entry_step:
                    _dp_back()
                else:
                    st.session_state.dp_step -= 1
                    st.rerun()
with nav_r:
    if st.button("✖ Cancel / Start Over"):
        for k in DP_KEYS_TO_CLEAR:
            st.session_state.pop(k, None)
        st.rerun()

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Auto-detect lens name & depot name from session state
# ─────────────────────────────────────────────────────────────────────────────
_lens_name = (
    st.session_state.get("cadp_lens_name", "")
    or st.session_state.get("bundle_lens_name", "")
    or st.session_state.get("lens_name_for_file", "")
).strip()

_depot_name = st.session_state.get("cadp_depot_name", "")

# ── Auto-seed QC resources from CADP QC step if list is empty ────────────────
_cadp_qc_name = st.session_state.get("cadp_qc_name", "").strip()
_cadp_qc_skipped = 3 in st.session_state.get("cadp_skipped_steps", set())

if (step == 1
        and not st.session_state.dp_bundle_qc_resources
        and _cadp_qc_name
        and not _cadp_qc_skipped):
    st.session_state.dp_bundle_qc_resources = [
        {"file": f"build/quality-checks/{_cadp_qc_name}.yml", "workspace": "public"}
    ]

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — BUNDLE
# ══════════════════════════════════════════════════════════════════════════════
if step == 1:

    if not st.session_state.dp_preview_mode:
        st.subheader("Step 1 — Bundle")
        show_example(st, "Bundle YAML", EXAMPLE_BUNDLE)
        st.caption(
            "The Bundle groups all resources for your data product. "
            "The Lens resource is always active. Add Quality Checks resources as needed."
        )

        # Info banners outside form
        if _cadp_qc_name and not _cadp_qc_skipped and st.session_state.dp_bundle_qc_resources:
            st.info(
                f"✅ First QC resource auto-filled from Quality Checks step — "
                f"**{_cadp_qc_name}.yml**"
            )
        elif _cadp_qc_skipped:
            st.warning("⚠️ Quality Checks was skipped — add QC resources manually if needed.")
        elif not _cadp_qc_name:
            st.caption("💡 Complete the Quality Checks step first to auto-fill the first QC resource.")

        with st.form("dp_bundle_form"):

            # ── Metadata ─────────────────────────────────────────────────────
            st.markdown("#### Metadata")
            bm1, bm2 = st.columns(2)
            with bm1:
                b_name = st.text_input(
                    "Bundle Name *",
                    placeholder="e.g. productaffinity-bundle",
                    help="Must be unique in DataOS. Do not use spaces.",
                )
                b_layer = st.text_input("Layer", value="user")
            with bm2:
                b_desc = st.text_area(
                    "Description *",
                    value=st.session_state.get("dp_bundle_desc", "Bundle resource for the data product"),
                    height=100,
                )

            # ── Tags ─────────────────────────────────────────────────────────
            _bth1, _bth2 = st.columns([5, 1])
            with _bth1: st.markdown("**Tags**")
            with _bth2:
                if st.form_submit_button("➕ Add", key="dp_add_btag"):
                    st.session_state.dp_bundle_tags.append("")
                    st.rerun()
            updated_bundle_tags = []
            for i, tag in enumerate(st.session_state.dp_bundle_tags):
                tc1, tc2 = st.columns([5, 1])
                with tc1:
                    val = st.text_input(f"Tag {i+1}", value=tag, key=f"dp_btag_{i}",
                                        placeholder="e.g. dataproduct", label_visibility="collapsed")
                    updated_bundle_tags.append(val)
                with tc2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"dp_rm_btag_{i}"):
                        st.session_state.dp_bundle_tags.pop(i)
                        st.rerun()

            st.divider()

            # ── Lens Resource ─────────────────────────────────────────────────
            st.markdown("#### Lens Resource")
            st.caption("This is always the first active resource in the bundle.")
            lc1, lc2 = st.columns(2)
            with lc1:
                b_lens_file = st.text_input(
                    "Lens File Path",
                    value="build/semantic-model/deployment.yml",
                    help="Relative path to the lens deployment YAML in your repo.",
                )
            with lc2:
                b_lens_ws = st.text_input("Lens Workspace", value="public")

            st.divider()

            # ── Quality Checks Resources ──────────────────────────────────────
            _qch1, _qch2 = st.columns([5, 1])
            with _qch1:
                st.markdown("#### Quality Checks Resources")
                st.caption("Each entry becomes an active resource in the bundle. Path is relative to your repo root.")
            with _qch2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("➕ Add QC", key="dp_add_qc"):
                    st.session_state.dp_bundle_qc_resources.append({"file": "", "workspace": "public"})
                    st.rerun()

            if not st.session_state.dp_bundle_qc_resources:
                st.info("No QC resources added yet — click ➕ Add QC to add one.")

            updated_qc_resources = []
            for i, qc in enumerate(st.session_state.dp_bundle_qc_resources):
                qc_cols = st.columns([4, 2, 0.7])
                with qc_cols[0]:
                    f_val = st.text_input(
                        f"File Path #{i+1}",
                        value=qc.get("file", ""),
                        key=f"dp_qc_file_{i}",
                        placeholder="e.g. build/quality-checks/soda-checks.yml",
                    )
                with qc_cols[1]:
                    w_val = st.text_input(
                        f"Workspace #{i+1}",
                        value=qc.get("workspace", "public"),
                        key=f"dp_qc_ws_{i}",
                    )
                with qc_cols[2]:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"dp_rm_qc_{i}"):
                        st.session_state.dp_bundle_qc_resources.pop(i)
                        st.rerun()
                updated_qc_resources.append({"file": f_val.strip(), "workspace": w_val.strip()})

            st.markdown(" ")
            submit1 = st.form_submit_button("Preview Bundle YAML →", use_container_width=True)

        # Persist outside form
        st.session_state.dp_bundle_tags         = updated_bundle_tags
        st.session_state.dp_bundle_qc_resources = updated_qc_resources

        if submit1:
            if not b_name.strip():
                st.error("Bundle Name is required.")
            elif not b_desc.strip():
                st.error("Description is required.")
            else:
                qc_list = [q for q in st.session_state.dp_bundle_qc_resources if q.get("file")]
                st.session_state.dp_bundle_name      = b_name.strip()
                st.session_state.dp_generated_bundle = generate_bundle_yaml({
                    "name":           b_name.strip(),
                    "description":    b_desc.strip(),
                    "tags":           [t for t in st.session_state.dp_bundle_tags if t.strip()],
                    "layer":          b_layer.strip() or "user",
                    "lens_file":      b_lens_file.strip(),
                    "lens_workspace": b_lens_ws.strip(),
                    "qc_resources":   qc_list,
                })
                save_entry("CADP", "bundle", f"{b_name.strip()}.yml", st.session_state.dp_generated_bundle, dp_name=b_name.strip())
                st.session_state.dp_preview_mode = True
                st.rerun()

    else:
        st.subheader("Step 1 — Bundle YAML Preview")
        st.code(st.session_state.dp_generated_bundle, language="yaml")
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("← Edit Bundle"):
                st.session_state.dp_preview_mode = False
                st.rerun()
        with pc2:
            if _dp_origin == "specific":
                bundle_fname = f"{st.session_state.get('dp_bundle_name', 'bundle')}.yml"
                st.download_button(
                    f"⬇ Download {bundle_fname}",
                    data=st.session_state.dp_generated_bundle,
                    file_name=bundle_fname,
                    mime="text/yaml",
                    use_container_width=True,
                    type="primary",
                )
            else:
                if st.button("Next: Spec →", use_container_width=True, type="primary"):
                    st.session_state.dp_preview_mode = False
                    st.session_state.dp_step = 2
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — SPEC
# ══════════════════════════════════════════════════════════════════════════════
elif step == 2:

    if not st.session_state.dp_preview_mode:
        st.subheader("Step 2 — Spec")
        show_example(st, "Spec YAML", EXAMPLE_SPEC)
        st.caption(
            "The Spec describes the data product — its metadata, ownership, inputs, outputs, and ports. "
            "The `resource` field automatically references the bundle name from Step 1."
        )

        bundle_name_saved = st.session_state.get("dp_bundle_name", "")
        if bundle_name_saved:
            st.info(f"Bundle reference: `bundle:v1beta:{bundle_name_saved}` (auto-filled from Step 1)")
        if _lens_name:
            st.info(f"Lens port reference: `lens:v1alpha:{_lens_name}:public` (auto-filled from Lens Deployment)")

        with st.form("dp_spec_form"):

            st.markdown("#### Metadata")
            sm1, sm2 = st.columns(2)
            with sm1:
                s_name = st.text_input(
                    "Spec Name *",
                    placeholder="e.g. productaffinity",
                    help="This name is used in the Scanner filter pattern — keep it short and unique.",
                )
                s_title = st.text_input("Title", placeholder="e.g. Product Affinity")
            with sm2:
                s_desc = st.text_area(
                    "Description *",
                    value=st.session_state.get("dp_spec_desc", "Data product spec"),
                    height=100,
                )

            _sth1, _sth2 = st.columns([5, 1])
            with _sth1: st.markdown("**Tags**")
            with _sth2:
                if st.form_submit_button("➕ Add", key="dp_add_stag"):
                    st.session_state.dp_spec_tags.append("")
                    st.rerun()
            updated_spec_tags = []
            for i, tag in enumerate(st.session_state.dp_spec_tags):
                stc1, stc2 = st.columns([5, 1])
                with stc1:
                    val = st.text_input(f"Tag {i+1}", value=tag, key=f"dp_stag_{i}",
                                        placeholder="e.g. DPDomain.Marketing", label_visibility="collapsed")
                    updated_spec_tags.append(val)
                with stc2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"dp_rm_stag_{i}"):
                        st.session_state.dp_spec_tags.pop(i)
                        st.rerun()

            st.divider()

            st.markdown("#### Meta URLs")
            st.caption("Optional source code and tracker links.")
            mu1, mu2 = st.columns(2)
            with mu1:
                s_source_url = st.text_input("sourceCodeUrl", placeholder="e.g. https://bitbucket.org/org/repo/src/main/")
            with mu2:
                s_tracker_url = st.text_input("trackerUrl", placeholder="e.g. https://jira.org/browse/DPRB-65")

            st.divider()

            _rh1, _rh2 = st.columns([5, 1])
            with _rh1: st.markdown("#### Refs")
            with _rh2:
                if st.form_submit_button("➕ Add", key="dp_add_sref"):
                    st.session_state.dp_spec_refs.append({"title": "", "href": ""})
                    st.rerun()
            st.caption("Reference links shown in the DataOS portal.")
            updated_spec_refs = []
            for i, ref in enumerate(st.session_state.dp_spec_refs):
                rc1, rc2, rc3 = st.columns([2, 3, 0.6])
                with rc1:
                    title = st.text_input("Title", value=ref.get("title", ""), key=f"dp_sref_title_{i}",
                                          placeholder="e.g. Workspace Info", label_visibility="collapsed")
                with rc2:
                    href = st.text_input("URL", value=ref.get("href", ""), key=f"dp_sref_href_{i}",
                                         placeholder="e.g. https://dataos.info/...", label_visibility="collapsed")
                with rc3:
                    if i > 0:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.form_submit_button("❌", key=f"dp_rm_sref_{i}"):
                            st.session_state.dp_spec_refs.pop(i)
                            st.rerun()
                updated_spec_refs.append({"title": title, "href": href})

            st.divider()

            _ch1, _ch2 = st.columns([5, 1])
            with _ch1: st.markdown("#### Collaborators")
            with _ch2:
                if st.form_submit_button("➕ Add", key="dp_add_scol"):
                    st.session_state.dp_spec_collaborators.append({"name": "", "description": "consumer"})
                    st.rerun()
            st.caption("List everyone involved — owner, developer, consumer.")
            ROLES = ["owner", "developer", "consumer"]
            updated_collaborators = []
            for i, col in enumerate(st.session_state.dp_spec_collaborators):
                cc1, cc2, cc3 = st.columns([3, 2, 0.6])
                with cc1:
                    name = st.text_input("Username", value=col.get("name", ""), key=f"dp_col_name_{i}",
                                         placeholder="e.g. manishagrawal", label_visibility="collapsed")
                with cc2:
                    desc = st.selectbox(
                        "Role", ROLES,
                        index=ROLES.index(col["description"]) if col.get("description") in ROLES else 2,
                        key=f"dp_col_role_{i}", label_visibility="collapsed",
                    )
                with cc3:
                    if i > 0:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.form_submit_button("❌", key=f"dp_rm_col_{i}"):
                            st.session_state.dp_spec_collaborators.pop(i)
                            st.rerun()
                updated_collaborators.append({"name": name, "description": desc})

            st.divider()

            _ih1, _ih2 = st.columns([5, 1])
            with _ih1: st.markdown("#### Input Datasets")
            with _ih2:
                if st.form_submit_button("➕ Add", key="dp_add_sinp"):
                    st.session_state.dp_spec_inputs.append({"ref": ""})
                    st.rerun()
            st.caption("Format: `dataset:icebase:<collection>:<table>`")
            for i, inp in enumerate(st.session_state.dp_spec_inputs):
                sic1, sic2 = st.columns([5, 1])
                with sic1:
                    st.session_state.dp_spec_inputs[i]["ref"] = st.text_input(
                        f"Input {i+1}", value=inp["ref"], key=f"dp_sinp_{i}",
                        placeholder="e.g. dataset:icebase:crm:customer_data",
                        label_visibility="collapsed",
                    )
                with sic2:
                    if i > 0:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.form_submit_button("❌", key=f"dp_rm_sinp_{i}"):
                            st.session_state.dp_spec_inputs.pop(i)
                            st.rerun()

            st.divider()

            _oh1, _oh2 = st.columns([5, 1])
            with _oh1: st.markdown("#### Output Datasets")
            with _oh2:
                if st.form_submit_button("➕ Add", key="dp_add_sout"):
                    st.session_state.dp_spec_outputs.append({"ref": ""})
                    st.rerun()
            st.caption("Format: `dataset:icebase:<collection>:<table>`")
            for i, out in enumerate(st.session_state.dp_spec_outputs):
                soc1, soc2 = st.columns([5, 1])
                with soc1:
                    st.session_state.dp_spec_outputs[i]["ref"] = st.text_input(
                        f"Output {i+1}", value=out["ref"], key=f"dp_sout_{i}",
                        placeholder="e.g. dataset:icebase:crm:product_affinity_matrix",
                        label_visibility="collapsed",
                    )
                with soc2:
                    if i > 0:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.form_submit_button("❌", key=f"dp_rm_sout_{i}"):
                            st.session_state.dp_spec_outputs.pop(i)
                            st.rerun()

            st.divider()

            st.markdown("#### Ports")
            st.caption("The Lens port is auto-filled from your Lens Deployment file.")
            sp1, sp2 = st.columns(2)
            with sp1:
                s_lens_name_field = st.text_input(
                    "Lens Name",
                    value=_lens_name,
                    placeholder="e.g. productaffinity",
                    help="Auto-filled from Lens Deployment if already completed.",
                )
            with sp2:
                s_lens_ws = st.text_input("Lens Workspace", value="public")

            st.markdown(" ")
            submit2 = st.form_submit_button("Preview Spec YAML →", use_container_width=True)

        st.session_state.dp_spec_tags          = updated_spec_tags
        st.session_state.dp_spec_refs          = updated_spec_refs
        st.session_state.dp_spec_collaborators = updated_collaborators

        if submit2:
            errors = []
            if not s_name.strip(): errors.append("Spec Name is required.")
            if not s_desc.strip(): errors.append("Description is required.")
            if errors:
                for e in errors: st.error(e)
            else:
                st.session_state.dp_spec_name = s_name.strip()
                st.session_state.dp_generated_spec = generate_spec_yaml({
                    "name":            s_name.strip(),
                    "description":     s_desc.strip(),
                    "tags":            [t for t in st.session_state.dp_spec_tags if t.strip()],
                    "refs":            st.session_state.dp_spec_refs,
                    "title":           s_title.strip(),
                    "source_code_url": s_source_url.strip(),
                    "tracker_url":     s_tracker_url.strip(),
                    "collaborators":   [c for c in st.session_state.dp_spec_collaborators if c.get("name", "").strip()],
                    "bundle_name":     st.session_state.get("dp_bundle_name", ""),
                    "inputs":          st.session_state.dp_spec_inputs,
                    "outputs":         st.session_state.dp_spec_outputs,
                    "lens_name":       s_lens_name_field.strip() or _lens_name,
                    "lens_workspace":  s_lens_ws.strip(),
                })
                save_entry("CADP", "spec", f"{s_name.strip()}.yml", st.session_state.dp_generated_spec, dp_name=s_name.strip())
                st.session_state.dp_scanner_data_products = [s_name.strip()]
                st.session_state.dp_preview_mode = True
                st.rerun()

    else:
        st.subheader("Step 2 — Spec YAML Preview")
        st.code(st.session_state.dp_generated_spec, language="yaml")
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("← Edit Spec"):
                st.session_state.dp_preview_mode = False
                st.rerun()
        with pc2:
            if _dp_origin == "specific":
                spec_fname = f"{st.session_state.get('dp_spec_name', 'spec')}.yml"
                st.download_button(
                    f"⬇ Download {spec_fname}",
                    data=st.session_state.dp_generated_spec,
                    file_name=spec_fname,
                    mime="text/yaml",
                    use_container_width=True,
                    type="primary",
                )
            else:
                if st.button("Next: Scanner →", use_container_width=True, type="primary"):
                    st.session_state.dp_preview_mode = False
                    st.session_state.dp_step = 3
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — SCANNER
# ══════════════════════════════════════════════════════════════════════════════
elif step == 3:

    if not st.session_state.dp_preview_mode:
        st.subheader("Step 3 — Scanner")
        show_example(st, "DP Scanner YAML", EXAMPLE_DP_SCANNER)
        st.caption(
            "The Scanner workflow crawls your data product and registers it in Metis. "
            "The filter pattern is pre-filled with the Spec name from Step 2."
        )

        spec_name_saved = st.session_state.get("dp_spec_name", "")
        if spec_name_saved:
            st.info(f"Scanner filter pre-filled from Spec name: `{spec_name_saved}`")

        with st.form("dp_scanner_form"):

            st.markdown("#### Metadata")
            scm1, scm2 = st.columns(2)
            with scm1:
                sc_name = st.text_input(
                    "Workflow Name *",
                    placeholder="e.g. scan-productaffinity",
                    help="Convention: scan-<product-name>",
                )
            with scm2:
                sc_desc = st.text_input("Description", value="The job scans data product from poros")

            _scth1, _scth2 = st.columns([5, 1])
            with _scth1: st.markdown("**Tags**")
            with _scth2:
                if st.form_submit_button("➕ Add", key="dp_add_scntag"):
                    st.session_state.dp_scanner_tags.append("")
                    st.rerun()
            updated_scanner_tags = []
            for i, tag in enumerate(st.session_state.dp_scanner_tags):
                sct1, sct2 = st.columns([5, 1])
                with sct1:
                    val = st.text_input(f"Tag {i+1}", value=tag, key=f"dp_scntag_{i}",
                                        label_visibility="collapsed")
                    updated_scanner_tags.append(val)
                with sct2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"dp_rm_scntag_{i}"):
                        st.session_state.dp_scanner_tags.pop(i)
                        st.rerun()

            st.divider()

            st.markdown("#### DAG")
            dg1, dg2 = st.columns(2)
            with dg1:
                sc_dag_name = st.text_input(
                    "DAG Name",
                    placeholder="e.g. scan-productaffinity-job",
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
                if st.form_submit_button("➕ Add", key="dp_add_scndtag"):
                    st.session_state.dp_scanner_dag_tags.append("")
                    st.rerun()
            updated_scanner_dag_tags = []
            for i, tag in enumerate(st.session_state.dp_scanner_dag_tags):
                sdct1, sdct2 = st.columns([5, 1])
                with sdct1:
                    val = st.text_input(f"DAG Tag {i+1}", value=tag, key=f"dp_scndtag_{i}",
                                        label_visibility="collapsed")
                    updated_scanner_dag_tags.append(val)
                with sdct2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"dp_rm_scndtag_{i}"):
                        st.session_state.dp_scanner_dag_tags.pop(i)
                        st.rerun()

            st.divider()

            _dpfh1, _dpfh2 = st.columns([5, 1])
            with _dpfh1: st.markdown("#### Data Product Filter Pattern")
            with _dpfh2:
                if st.form_submit_button("➕ Add", key="dp_add_dpfilter"):
                    st.session_state.dp_scanner_data_products.append("")
                    st.rerun()
            st.caption(
                "Pre-filled from the Spec name. "
                "Each entry becomes an item under `dataProductFilterPattern.includes`."
            )
            sc_mark_deleted = st.checkbox("markDeletedDataProducts", value=True)

            updated_dp_filters = []
            for i, dp in enumerate(st.session_state.dp_scanner_data_products):
                dpc1, dpc2 = st.columns([5, 1])
                with dpc1:
                    val = st.text_input(f"Include {i+1}", value=dp, key=f"dp_dpfilter_{i}",
                                        placeholder="e.g. productaffinity", label_visibility="collapsed")
                    updated_dp_filters.append(val)
                with dpc2:
                    if i > 0:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.form_submit_button("❌", key=f"dp_rm_dpfilter_{i}"):
                            st.session_state.dp_scanner_data_products.pop(i)
                            st.rerun()

            st.markdown(" ")
            submit3 = st.form_submit_button("Preview Scanner YAML →", use_container_width=True)

        st.session_state.dp_scanner_tags          = updated_scanner_tags
        st.session_state.dp_scanner_dag_tags      = updated_scanner_dag_tags
        st.session_state.dp_scanner_data_products = updated_dp_filters

        if submit3:
            if not sc_name.strip():
                st.error("Workflow Name is required.")
            else:
                st.session_state.dp_generated_scanner = generate_dp_scanner_yaml({
                    "name":              sc_name.strip(),
                    "description":       sc_desc.strip(),
                    "tags":              [t for t in st.session_state.dp_scanner_tags if t.strip()],
                    "dag_name":          sc_dag_name.strip(),
                    "dag_description":   sc_dag_desc.strip(),
                    "dag_tags":          [t for t in st.session_state.dp_scanner_dag_tags if t.strip()],
                    "stack":             sc_stack.strip(),
                    "compute":           sc_compute.strip(),
                    "mark_deleted":      sc_mark_deleted,
                    "data_products":     [dp for dp in st.session_state.dp_scanner_data_products if dp.strip()],
                })
                save_entry("CADP", "scanner", f"{sc_name.strip()}.yml", st.session_state.dp_generated_scanner, dp_name=sc_name.strip())
                st.session_state.dp_preview_mode = True
                st.rerun()

    else:
        st.subheader("Step 3 — Scanner YAML Preview")
        st.code(st.session_state.dp_generated_scanner, language="yaml")
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("← Edit Scanner"):
                st.session_state.dp_preview_mode = False
                st.rerun()
        with pc2:
            if _dp_origin == "specific":
                spec_name_for_file = st.session_state.get("dp_spec_name", "scanner")
                sc_fname = f"scan-{spec_name_for_file}.yml"
                st.download_button(
                    f"⬇ Download {sc_fname}",
                    data=st.session_state.dp_generated_scanner,
                    file_name=sc_fname,
                    mime="text/yaml",
                    use_container_width=True,
                    type="primary",
                )
            else:
                if st.button("Review All Files ✅", use_container_width=True, type="primary"):
                    st.session_state.dp_preview_mode = False
                    st.session_state.dp_step = 4
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — REVIEW & DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════
elif step == 4:
    st.subheader("Step 4 — Review All Files & Download")
    st.success("All 3 files generated. Review them below, then download individually or as a ZIP.")
    st.markdown(" ")

    bundle_name  = st.session_state.get("dp_bundle_name",  "bundle")
    spec_name    = st.session_state.get("dp_spec_name",    "spec")
    scanner_yaml = st.session_state.get("dp_generated_scanner", "")
    bundle_yaml  = st.session_state.get("dp_generated_bundle",  "")
    spec_yaml    = st.session_state.get("dp_generated_spec",    "")

    tab1, tab2, tab3 = st.tabs(["Bundle", "Spec", "Scanner"])

    with tab1:
        st.code(bundle_yaml, language="yaml")
        st.download_button(
            "⬇ Download Bundle YAML",
            data=bundle_yaml,
            file_name=f"{bundle_name}.yml",
            mime="text/yaml",
            use_container_width=True,
        )

    with tab2:
        st.code(spec_yaml, language="yaml")
        st.download_button(
            "⬇ Download Spec YAML",
            data=spec_yaml,
            file_name=f"{spec_name}.yml",
            mime="text/yaml",
            use_container_width=True,
        )

    with tab3:
        st.code(scanner_yaml, language="yaml")
        st.download_button(
            "⬇ Download Scanner YAML",
            data=scanner_yaml,
            file_name=f"scan-{spec_name}.yml",
            mime="text/yaml",
            use_container_width=True,
        )

    st.divider()

    import zipfile, io
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr(f"{bundle_name}.yml",   bundle_yaml)
        zf.writestr(f"{spec_name}.yml",      spec_yaml)
        zf.writestr(f"scan-{spec_name}.yml", scanner_yaml)
    zip_buf.seek(0)

    st.download_button(
        "⬇ Download All as ZIP",
        data=zip_buf,
        file_name=f"{spec_name}-dp-deployment.zip",
        mime="application/zip",
        use_container_width=True,
    )

    if _dp_origin == "cadp_full":
        st.divider()
        st.success("DP Deployment complete. Your CADP data product is fully generated.")
        if st.button("Back to CADP Flow", use_container_width=True, type="primary"):
            if "cadp_completed_steps" not in st.session_state:
                st.session_state.cadp_completed_steps = set()
            st.session_state.cadp_completed_steps.add(5)
            st.switch_page("pages/cadp_flow.py")