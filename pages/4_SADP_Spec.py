import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.history import save_entry
from utils.generators import generate_sadp_spec_yaml
from utils.examples import EXAMPLE_SPEC, show_example

st.set_page_config(page_title="SADP — Spec", layout="wide")
from utils.ui_utils import load_global_css, render_sidebar, floating_docs
load_global_css()
render_sidebar()
floating_docs("spec")

st.markdown("""
<style>
.stButton>button { width: 100%; height: 45px; border-radius: 8px; font-size: 15px; }
</style>
""", unsafe_allow_html=True)

SADP_SPEC_KEYS = [
    "sadp_spec_preview_mode", "sadp_spec_tags", "sadp_spec_refs",
    "sadp_spec_collaborators", "sadp_spec_inputs", "sadp_spec_outputs",
    "sadp_spec_name", "sadp_generated_spec",
]

for k, v in [
    ("sadp_spec_preview_mode",  False),
    ("sadp_spec_tags",          [""]),
    ("sadp_spec_refs",          [{"title": "Workspace Info", "href": "https://dataos.info/interfaces/cli/command_reference/#workspace"}]),
    ("sadp_spec_collaborators", [{"name": "", "description": "owner"}]),
    ("sadp_spec_inputs",        [{"ref": ""}]),
    ("sadp_spec_outputs",       [{"ref": ""}]),
]:
    if k not in st.session_state:
        st.session_state[k] = v

_origin = st.session_state.get("sadp_origin", "specific")
_bundle_name = st.session_state.get("sadp_bundle_name", "")

nav_l, _, nav_r = st.columns([1, 4, 1.5])
with nav_l:
    if st.button("← Back"):
        if _origin == "sadp_full":
            st.switch_page("pages/3_SADP_Bundle.py")
        else:
            st.session_state.home_screen = "specific"
            st.switch_page("app.py")
with nav_r:
    if st.button("✖ Cancel / Start Over"):
        for k in SADP_SPEC_KEYS:
            st.session_state.pop(k, None)
        st.rerun()

st.divider()

if not st.session_state.sadp_spec_preview_mode:

    st.subheader("Spec")
    show_example(st, "Spec YAML", EXAMPLE_SPEC)
    st.caption(
        "The Spec describes the data product — its metadata, ownership, inputs, and outputs. "
        "The `resource` field automatically references the bundle name from the previous step."
    )

    if _bundle_name:
        st.info(f"Bundle reference: `bundle:v1beta:{_bundle_name}` (auto-filled from Bundle step)")

    with st.form("sadp_spec_form"):

        st.markdown("#### Metadata")
        sm1, sm2 = st.columns(2)
        with sm1:
            s_name = st.text_input(
                "Spec Name *",
                placeholder="e.g. retail-sales",
                help="Short unique name. Also used in the Scanner filter pattern.",
            )
            s_title = st.text_input("Title", placeholder="e.g. Retail Sales")
        with sm2:
            s_desc = st.text_area(
                "Description *",
                value=st.session_state.get("sadp_spec_desc", "Data product spec"),
                height=100,
            )

        _sth1, _sth2 = st.columns([5, 1])
        with _sth1: st.markdown("**Tags**")
        with _sth2:
            if st.form_submit_button("➕ Add", key="sadp_add_stag"):
                st.session_state.sadp_spec_tags.append(""); st.rerun()
        updated_spec_tags = []
        for i, tag in enumerate(st.session_state.sadp_spec_tags):
            stc1, stc2 = st.columns([5, 1])
            with stc1:
                val = st.text_input(f"Tag {i+1}", value=tag, key=f"sadp_stag_{i}",
                                    placeholder="e.g. DPDomain.Sales", label_visibility="collapsed")
                updated_spec_tags.append(val)
            with stc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("❌", key=f"sadp_rm_stag_{i}"):
                    st.session_state.sadp_spec_tags.pop(i); st.rerun()

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
            if st.form_submit_button("➕ Add", key="sadp_add_sref"):
                st.session_state.sadp_spec_refs.append({"title": "", "href": ""}); st.rerun()
        st.caption("Reference links shown in the DataOS portal.")
        updated_spec_refs = []
        for i, ref in enumerate(st.session_state.sadp_spec_refs):
            rc1, rc2, rc3 = st.columns([2, 3, 0.6])
            with rc1:
                title = st.text_input("Title", value=ref.get("title", ""), key=f"sadp_sref_title_{i}",
                                      placeholder="e.g. Workspace Info", label_visibility="collapsed")
            with rc2:
                href = st.text_input("URL", value=ref.get("href", ""), key=f"sadp_sref_href_{i}",
                                     placeholder="e.g. https://dataos.info/...", label_visibility="collapsed")
            with rc3:
                if i > 0:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"sadp_rm_sref_{i}"):
                        st.session_state.sadp_spec_refs.pop(i); st.rerun()
            updated_spec_refs.append({"title": title, "href": href})

        st.divider()

        _ch1, _ch2 = st.columns([5, 1])
        with _ch1: st.markdown("#### Collaborators")
        with _ch2:
            if st.form_submit_button("➕ Add", key="sadp_add_scol"):
                st.session_state.sadp_spec_collaborators.append({"name": "", "description": "consumer"}); st.rerun()
        st.caption("List everyone involved — owner, developer, consumer.")
        ROLES = ["owner", "developer", "consumer"]
        updated_collaborators = []
        for i, col in enumerate(st.session_state.sadp_spec_collaborators):
            cc1, cc2, cc3 = st.columns([3, 2, 0.6])
            with cc1:
                name = st.text_input("Username", value=col.get("name", ""), key=f"sadp_col_name_{i}",
                                     placeholder="e.g. manishagrawal", label_visibility="collapsed")
            with cc2:
                desc = st.selectbox(
                    "Role", ROLES,
                    index=ROLES.index(col["description"]) if col.get("description") in ROLES else 2,
                    key=f"sadp_col_role_{i}", label_visibility="collapsed",
                )
            with cc3:
                if i > 0:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"sadp_rm_col_{i}"):
                        st.session_state.sadp_spec_collaborators.pop(i); st.rerun()
            updated_collaborators.append({"name": name, "description": desc})

        st.divider()

        _ih1, _ih2 = st.columns([5, 1])
        with _ih1: st.markdown("#### Input Datasets")
        with _ih2:
            if st.form_submit_button("➕ Add", key="sadp_add_sinp"):
                st.session_state.sadp_spec_inputs.append({"ref": ""}); st.rerun()
        st.caption("Pre-filled from Bundle step — edit if needed. Format: `dataset:icebase:<collection>:<table>`")
        for i, inp in enumerate(st.session_state.sadp_spec_inputs):
            sic1, sic2 = st.columns([5, 1])
            with sic1:
                st.session_state.sadp_spec_inputs[i]["ref"] = st.text_input(
                    f"Input {i+1}", value=inp["ref"], key=f"sadp_sinp_{i}",
                    placeholder="e.g. dataset:icebase:crm:customer_data",
                    label_visibility="collapsed",
                )
            with sic2:
                if i > 0:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"sadp_rm_sinp_{i}"):
                        st.session_state.sadp_spec_inputs.pop(i); st.rerun()

        st.divider()

        _oh1, _oh2 = st.columns([5, 1])
        with _oh1: st.markdown("#### Output Datasets")
        with _oh2:
            if st.form_submit_button("➕ Add", key="sadp_add_sout"):
                st.session_state.sadp_spec_outputs.append({"ref": ""}); st.rerun()
        st.caption("Pre-filled from Bundle step — edit if needed. Format: `dataset:icebase:<collection>:<table>`")
        for i, out in enumerate(st.session_state.sadp_spec_outputs):
            soc1, soc2 = st.columns([5, 1])
            with soc1:
                st.session_state.sadp_spec_outputs[i]["ref"] = st.text_input(
                    f"Output {i+1}", value=out["ref"], key=f"sadp_sout_{i}",
                    placeholder="e.g. dataset:icebase:crm:product_affinity_matrix",
                    label_visibility="collapsed",
                )
            with soc2:
                if i > 0:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"sadp_rm_sout_{i}"):
                        st.session_state.sadp_spec_outputs.pop(i); st.rerun()

        st.markdown(" ")
        submit2 = st.form_submit_button("Preview Spec YAML →", use_container_width=True)

    st.session_state.sadp_spec_tags          = updated_spec_tags
    st.session_state.sadp_spec_refs          = updated_spec_refs
    st.session_state.sadp_spec_collaborators = updated_collaborators

    if submit2:
        errors = []
        if not s_name.strip():
            errors.append("Spec Name is required.")
        if not s_desc.strip():
            errors.append("Description is required.")
        if errors:
            for e in errors:
                st.error(e)
        else:
            st.session_state.sadp_spec_name = s_name.strip()
            st.session_state.sadp_generated_spec = generate_sadp_spec_yaml({
                "name":            s_name.strip(),
                "description":     s_desc.strip(),
                "tags":            [t for t in st.session_state.sadp_spec_tags if t.strip()],
                "refs":            st.session_state.sadp_spec_refs,
                "title":           s_title.strip(),
                "source_code_url": s_source_url.strip(),
                "tracker_url":     s_tracker_url.strip(),
                "collaborators":   [c for c in st.session_state.sadp_spec_collaborators if c.get("name", "").strip()],
                "bundle_name":     _bundle_name,
                "inputs":          st.session_state.sadp_spec_inputs,
                "outputs":         st.session_state.sadp_spec_outputs,
            })
            save_entry("SADP", "spec", f"{s_name.strip()}.yml", st.session_state.sadp_generated_spec, dp_name=s_name.strip())
            st.session_state.sadp_scanner_data_products = [s_name.strip()]
            st.session_state.sadp_spec_preview_mode = True
            st.rerun()

else:
    st.subheader("Spec YAML Preview")
    st.code(st.session_state.sadp_generated_spec, language="yaml")
    pc1, pc2 = st.columns(2)
    with pc1:
        if st.button("← Edit Spec"):
            st.session_state.sadp_spec_preview_mode = False
            st.rerun()
    with pc2:
        if st.button("Continue to Scanner →", use_container_width=True, type="primary"):
            st.session_state.sadp_spec_preview_mode = False
            if _origin == "sadp_full":
                if "sadp_completed_steps" not in st.session_state:
                    st.session_state.sadp_completed_steps = set()
                st.session_state.sadp_completed_steps.add(4)
            st.switch_page("pages/5_SADP_Scanner.py")