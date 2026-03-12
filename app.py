import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from utils.ui_utils import load_global_css, group_label, app_footer, floating_docs

st.set_page_config(page_title="DP YAML Generator", layout="wide")
load_global_css()

if "home_screen" not in st.session_state:
    st.session_state.home_screen = "home"


# ─────────────────────────────────────────────────────────────────────────────
# SCREEN 0 — Home
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.home_screen == "home":

    st.markdown("## DP YAML Generator")
    st.markdown(
        '<p style="color:#6b7280; font-size:14px; margin-top:-8px; margin-bottom:24px;">'
        'Generate YAML & SQL files for DataOS data products — fast, consistent, error-free.'
        '</p>',
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2, gap="large")

    with col_a:
        st.markdown("""
        <div class="choice-card accent-blue">
            <h3>Generate a Specific File</h3>
            <p>Pick any single file — Depot, Flare, Semantic Model, DP Deployment —
            fill in the details and download it instantly.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Open File Builder →", key="home_specific", use_container_width=True):
            st.session_state.home_screen = "specific"
            st.rerun()

    with col_b:
        st.markdown("""
        <div class="choice-card accent-green">
            <h3>Generate a Full Data Product</h3>
            <p>Walk through the complete step-by-step flow for a
            Source-Aligned (SADP) or Consumer-Aligned (CADP) data product.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Start Full Flow →", key="home_full", use_container_width=True):
            st.session_state.home_screen = "full_dp"
            st.rerun()

    app_footer()


# ─────────────────────────────────────────────────────────────────────────────
# SCREEN 1 — Specific File
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.home_screen == "specific":

    nav_l, _, nav_r = st.columns([1, 5, 1])
    with nav_l:
        if st.button("← Back", key="spec_back"):
            st.session_state.home_screen = "home"
            st.rerun()

    st.markdown("## File Builder")
    st.markdown(
        '<p style="color:#6b7280; font-size:13px; margin-top:-8px; margin-bottom:4px;">'
        'Each builder is standalone — select any file and fill in the details.'
        '</p>',
        unsafe_allow_html=True,
    )

    # ── Connection ────────────────────────────────────────────────────────────
    group_label("Connection", "dot-teal")
    g1c1, g1c2, g1c3, g1c4 = st.columns(4, gap="small")
    with g1c1:
        st.markdown("""<div class="flow-card teal">
            <h4>Instance Secret (Read)</h4>
            <p>Read-only credentials for a depot connection.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_secret_r", use_container_width=True):
            st.session_state["depot_origin"] = "specific"
            st.session_state["depot_specific_file"] = "secret_r"
            st.switch_page("pages/6_Depot.py")
    with g1c2:
        st.markdown("""<div class="flow-card teal">
            <h4>Instance Secret (R/W)</h4>
            <p>Read-write credentials for a depot connection.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_secret_rw", use_container_width=True):
            st.session_state["depot_origin"] = "specific"
            st.session_state["depot_specific_file"] = "secret_rw"
            st.switch_page("pages/6_Depot.py")
    with g1c3:
        st.markdown("""<div class="flow-card teal">
            <h4>Depot</h4>
            <p>Depot connection configuration for a data source.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_depot", use_container_width=True):
            st.session_state["depot_origin"] = "specific"
            st.session_state["depot_specific_file"] = "depot"
            st.switch_page("pages/6_Depot.py")
    with g1c4:
        st.markdown("""<div class="flow-card teal">
            <h4>Depot Scanner</h4>
            <p>Scanner workflow to catalog a depot in Metis.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_depot_scanner", use_container_width=True):
            st.session_state["depot_origin"] = "specific"
            st.session_state["depot_specific_file"] = "scanner"
            st.switch_page("pages/6_Depot.py")

    # ── Transformation ────────────────────────────────────────────────────────
    group_label("Transformation", "dot-orange")
    g2c1, g2c2, g2c3, g2c4 = st.columns(4, gap="small")
    with g2c1:
        st.markdown("""<div class="flow-card orange">
            <h4>Flare Job</h4>
            <p>Flare workflow for data ingestion and transformation.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_flare", use_container_width=True):
            st.session_state["flare_origin"] = "specific"
            st.switch_page("pages/8_CADP_Flare.py")

    # ── Semantic Model ────────────────────────────────────────────────────────
    group_label("Semantic Model", "dot-blue")
    g3c1, g3c2, g3c3, g3c4 = st.columns(4, gap="small")
    with g3c1:
        st.markdown("""<div class="flow-card blue">
            <h4>SQL File</h4>
            <p>SELECT query for a semantic model table.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_sql", use_container_width=True):
            st.session_state["sm_origin"] = "specific"
            st.session_state["sm_mode"] = "individual"
            st.session_state["semantic_section"] = "sql"
            st.switch_page("pages/1_CADP.py")
    with g3c2:
        st.markdown("""<div class="flow-card blue">
            <h4>Table YAML</h4>
            <p>Dimensions, measures, joins and segments.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_table", use_container_width=True):
            st.session_state["sm_origin"] = "specific"
            st.session_state["sm_mode"] = "individual"
            st.session_state["semantic_section"] = "table"
            st.switch_page("pages/1_CADP.py")
    with g3c3:
        st.markdown("""<div class="flow-card blue">
            <h4>View YAML</h4>
            <p>Views referencing semantic model tables.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_view", use_container_width=True):
            st.session_state["sm_origin"] = "specific"
            st.session_state["sm_mode"] = "individual"
            st.session_state["semantic_section"] = "view"
            st.switch_page("pages/1_CADP.py")
    with g3c4:
        st.markdown("""<div class="flow-card blue">
            <h4>Lens Deployment</h4>
            <p>Deployment configuration for Lens.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_lens", use_container_width=True):
            st.session_state["sm_origin"] = "specific"
            st.session_state["sm_mode"] = "individual"
            st.session_state["semantic_section"] = "lens"
            st.switch_page("pages/1_CADP.py")

    g3r2c1, g3r2c2, g3r2c3, g3r2c4 = st.columns(4, gap="small")
    with g3r2c1:
        st.markdown("""<div class="flow-card blue">
            <h4>User Groups</h4>
            <p>API access groups and user assignments for a semantic model.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_user_groups", use_container_width=True):
            st.session_state["sm_origin"] = "specific"
            st.session_state["sm_mode"] = "individual"
            st.session_state["semantic_section"] = "user_groups"
            st.switch_page("pages/1_CADP.py")
    with g3r2c2:
        st.markdown("""<div class="flow-card blue">
            <h4>Repo Credential</h4>
            <p>Instance secret for Git repo access (Lens gitsync).</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_repo_cred", use_container_width=True):
            st.session_state["sm_origin"] = "specific"
            st.session_state["sm_mode"] = "individual"
            st.session_state["semantic_section"] = "repo_cred"
            st.switch_page("pages/1_CADP.py")

    # ── DP Deployment ─────────────────────────────────────────────────────────
    group_label("DP Deployment", "dot-purple")
    g4c1, g4c2, g4c3, g4c4 = st.columns(4, gap="small")
    with g4c1:
        st.markdown("""<div class="flow-card purple">
            <h4>Bundle</h4>
            <p>Bundle configuration for a data product.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_bundle", use_container_width=True):
            st.session_state["dp_origin"]     = "specific"
            st.session_state["dp_step"]       = 1
            st.session_state["dp_entry_step"] = 1
            st.switch_page("pages/9_CADP_DP_Deployment.py")
    with g4c2:
        st.markdown("""<div class="flow-card purple">
            <h4>Spec</h4>
            <p>Specification file for a data product.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_spec", use_container_width=True):
            st.session_state["dp_origin"]     = "specific"
            st.session_state["dp_step"]       = 2
            st.session_state["dp_entry_step"] = 2
            st.switch_page("pages/9_CADP_DP_Deployment.py")
    with g4c3:
        st.markdown("""<div class="flow-card purple">
            <h4>DP Scanner</h4>
            <p>Scanner workflow to catalog a data product.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_dp_scanner", use_container_width=True):
            st.session_state["dp_origin"]     = "specific"
            st.session_state["dp_step"]       = 3
            st.session_state["dp_entry_step"] = 3
            st.switch_page("pages/9_CADP_DP_Deployment.py")

    # ── Quality Checks ────────────────────────────────────────────────────────
    group_label("Quality Checks", "dot-green")
    g5c1, g5c2, g5c3, g5c4 = st.columns(4, gap="small")
    with g5c1:
        st.markdown("""<div class="flow-card green">
            <h4>Quality Checks</h4>
            <p>Data quality rules and validation checks.</p>
        </div>""", unsafe_allow_html=True)
        if st.button("Open", key="spec_qc", use_container_width=True):
            st.session_state["sm_origin"] = "specific"
            st.session_state["sm_mode"] = "individual"
            st.session_state["semantic_section"] = "qc"
            st.switch_page("pages/1_CADP.py")

    app_footer()


# ─────────────────────────────────────────────────────────────────────────────
# SCREEN 2 — Full Data Product: SADP or CADP
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.home_screen == "full_dp":

    nav_l, _, nav_r = st.columns([1, 5, 1])
    with nav_l:
        if st.button("← Back", key="full_dp_back"):
            st.session_state.home_screen = "home"
            st.rerun()

    st.markdown("## Full Data Product")
    st.markdown(
        '<p style="color:#6b7280; font-size:13px; margin-top:-8px; margin-bottom:24px;">'
        'Walk through the complete step-by-step flow — all files generated and bundled into a ZIP.'
        '</p>',
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2, gap="large")

    with col_a:
        st.markdown("""
        <div class="choice-card accent-green">
            <h3>SADP — Source-Aligned</h3>
            <p>5 steps: Depot → Quality Checks → Bundle → Spec → Scanner.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Create SADP →", key="full_sadp", use_container_width=True):
            st.switch_page("pages/sadp_flow.py")

    with col_b:
        st.markdown("""
        <div class="choice-card accent-blue">
            <h3>CADP — Consumer-Aligned</h3>
            <p>5 steps: Depot → Semantic Model → Quality Checks → Flare Job → DP Deployment.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Create CADP →", key="full_cadp", use_container_width=True):
            st.switch_page("pages/cadp_flow.py")

    app_footer()
    floating_docs("dp_learn")