import sys, os
import streamlit as st
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.ui_utils import load_global_css, render_sidebar

st.set_page_config(layout="wide")
load_global_css()
render_sidebar()


# ---------- Custom CSS ----------
st.markdown("""
<style>
.flow-card {
    padding: 25px;
    border-radius: 12px;
    background-color: #111827;
    color: white;
    height: 180px;
}
.flow-card h3 { margin-bottom: 10px; }
.flow-card p  { font-size: 14px; color: #9ca3af; }
.choice-card {
    padding: 30px;
    border-radius: 12px;
    background-color: #1f2937;
    color: white;
    text-align: center;
    height: 200px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.choice-card h3 { margin-bottom: 10px; font-size: 20px; }
.choice-card p  { font-size: 13px; color: #9ca3af; }
.stButton>button {
    width: 100%;
    height: 45px;
    border-radius: 8px;
    font-size: 15px;
}
.arrow { font-size: 36px; text-align: center; margin-top: 65px; }
</style>
""", unsafe_allow_html=True)

if st.session_state.get("sm_origin") == "cadp_full":
    st.title("Semantic Model — Step 2 of CADP")
else:
    st.title("Semantic Model")

if "sm_mode" not in st.session_state:
    st.session_state.sm_mode = None

# ── path setup so sm/ and utils/ are importable ───────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

# ── routing helpers ───────────────────────────────────────────────────────────
sm_origin = st.session_state.get("sm_origin", "specific")

BUNDLE_YAML_KEYS = {
    "bundle_generated_sql", "bundle_generated_table_yaml",
    "bundle_generated_view_yaml", "bundle_generated_lens_yaml",
    "bundle_tbl_name", "bundle_view_name", "bundle_lens_name",
}


def clear_bundle_state(keys_to_clear):
    keep = BUNDLE_YAML_KEYS if sm_origin == "cadp_full" else set()
    for k in keys_to_clear:
        if k not in keep:
            st.session_state.pop(k, None)


def back_from_sm():
    st.session_state.sm_mode = None
    st.session_state.pop("semantic_section", None)
    if sm_origin == "cadp_full":
        st.switch_page("pages/cadp_flow.py")
    else:
        st.session_state.home_screen = "specific"
        st.switch_page("app.py")


if st.session_state.sm_mode is None and st.session_state.get("semantic_section") is None:
    st.session_state.home_screen = "specific"
    st.switch_page("app.py")


# ══════════════════════════════════════════════════════════════════════════════
# BUNDLE MODE
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.sm_mode == "bundle":

    from sm.state import (
        init_bundle_state, BUNDLE_KEYS_TO_CLEAR, BUNDLE_YAML_KEYS_PRESERVE,
        STEP_LABELS,
    )
    from sm.step1_sql        import render_step1
    from sm.step2_table      import render_step2
    from sm.step3_view       import render_step3
    from sm.step4_repo_cred  import render_step4
    from sm.step5_lens       import render_step5
    from sm.step6_user_groups import render_step6
    from sm.step7_review     import render_step7

    init_bundle_state()

    step = st.session_state.bundle_step
    label = STEP_LABELS[step - 1] if step <= len(STEP_LABELS) else "Complete"
    st.progress((step - 1) / len(STEP_LABELS), text=f"Step {step} of {len(STEP_LABELS)} — {label}")

    nav_l, _, nav_r = st.columns([1, 4, 1.5])
    with nav_l:
        if step > 1:
            if st.button("← Back"):
                if step == 2:
                    st.session_state.bundle_table_idx = 0
                elif step == 3:
                    st.session_state.bundle_view_idx = 0
                st.session_state.bundle_step -= 1
                if step == 2:
                    completed = [t for t in st.session_state.bundle_tables if t.get("generated_sql")]
                    if completed:
                        st.session_state.bundle_tables    = completed
                        st.session_state.bundle_table_idx = len(completed) - 1
                st.rerun()
    with nav_r:
        if st.button("Cancel / Start Over"):
            for k in BUNDLE_KEYS_TO_CLEAR:
                st.session_state.pop(k, None)
            back_from_sm()

    st.divider()

    if   step == 1: render_step1()
    elif step == 2: render_step2()
    elif step == 3: render_step3()
    elif step == 4: render_step4()
    elif step == 5: render_step5()
    elif step == 6: render_step6()
    elif step == 7: render_step7(sm_origin, BUNDLE_YAML_KEYS_PRESERVE, BUNDLE_KEYS_TO_CLEAR, back_from_sm)


# ── guard — nothing further unless a section is selected ─────────────────────
section = st.session_state.get("semantic_section")
if not section or section == "sm_home":
    st.stop()

# Back button for individual section builders
if st.session_state.get("sm_mode") == "individual":
    if st.button("← Back to File List"):
        st.session_state.pop("semantic_section", None)
        st.session_state.home_screen = "specific"
        st.switch_page("app.py")
    st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# INDIVIDUAL SECTION BUILDERS
# ══════════════════════════════════════════════════════════════════════════════
from sm.individual.ind_sql        import render_ind_sql
from sm.individual.ind_table      import render_ind_table
from sm.individual.ind_view       import render_ind_view
from sm.individual.ind_lens       import render_ind_lens
from sm.individual.ind_qc         import render_ind_qc
from sm.individual.ind_user_groups import render_ind_user_groups
from sm.individual.ind_repo_cred  import render_ind_repo_cred

if   section == "sql":         render_ind_sql()
elif section == "table":       render_ind_table()
elif section == "view":        render_ind_view()
elif section == "lens":        render_ind_lens()
elif section == "qc":          render_ind_qc()
elif section == "user_groups": render_ind_user_groups()
elif section == "repo_cred":   render_ind_repo_cred()