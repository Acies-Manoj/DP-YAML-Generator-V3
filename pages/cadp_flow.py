import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.ui_utils import load_global_css, render_sidebar, app_footer
from utils.history import save_zip_entry

st.set_page_config(page_title="CADP — Full Data Product", layout="wide")
load_global_css()
render_sidebar()

# ─────────────────────────────────────────────────────────────────────────────
# STATE INIT
# ─────────────────────────────────────────────────────────────────────────────
STEPS = {
    1: {"label": "Depot",          "optional": True},
    2: {"label": "Semantic Model", "optional": False},
    3: {"label": "Quality Checks", "optional": True},
    4: {"label": "Flare Job",      "optional": True},
    5: {"label": "DP Deployment",  "optional": False},
}

if "cadp_completed_steps" not in st.session_state:
    st.session_state.cadp_completed_steps = set()
if "cadp_skipped_steps" not in st.session_state:
    st.session_state.cadp_skipped_steps = set()

completed = st.session_state.cadp_completed_steps
skipped   = st.session_state.cadp_skipped_steps

# ─────────────────────────────────────────────────────────────────────────────
# NAVIGATION HELPER
# ─────────────────────────────────────────────────────────────────────────────
def go_to_step(n):
    if n == 1:
        st.session_state["depot_origin"] = "cadp_full"
        st.switch_page("pages/6_Depot.py")
    elif n == 2:
        st.session_state["sm_mode"]   = "bundle"
        st.session_state["sm_origin"] = "cadp_full"
        st.session_state.pop("semantic_section", None)
        st.switch_page("pages/1_CADP.py")
    elif n == 3:
        st.session_state["cadp_qc_origin"] = "cadp_full"
        st.switch_page("pages/7_CADP_Quality_Checks.py")
    elif n == 4:
        st.session_state["flare_origin"] = "cadp_full"
        st.switch_page("pages/8_CADP_Flare.py")
    elif n == 5:
        st.session_state["dp_origin"] = "cadp_full"
        st.session_state.pop("dp_step", None)
        st.switch_page("pages/9_CADP_DP_Deployment.py")

def is_unlocked(n):
    return True  # All steps always accessible during testing

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("## CADP — Consumer-Aligned Data Product")
st.markdown(
    '<p style="color:#6b7280; font-size:13px; margin-top:-8px;">Complete all steps below to generate your full CADP package.</p>',
    unsafe_allow_html=True,
)

nav_l, _, nav_r = st.columns([1, 4, 1.5])
with nav_l:
    if st.button("← Back to Home"):
        st.session_state.home_screen = "full_dp"
        st.switch_page("app.py")
with nav_r:
    if st.button("Start Over"):
        for k in ["cadp_completed_steps", "cadp_skipped_steps",
                  "cadp_depot_name", "cadp_lens_name"]:
            st.session_state.pop(k, None)
        st.rerun()

st.divider()

done_count = len(completed) + len(skipped)
st.progress(done_count / 5, text=f"{done_count} of 5 steps done")
st.markdown(" ")

# ─────────────────────────────────────────────────────────────────────────────
# STEP CARDS
# ─────────────────────────────────────────────────────────────────────────────
for n, info in STEPS.items():
    is_done     = n in completed
    is_skipped  = n in skipped
    is_optional = info["optional"]
    unlocked    = is_unlocked(n)

    if is_done:
        card_cls, badge_cls, badge_txt = "complete", "b-complete", "Complete"
    elif is_skipped:
        card_cls, badge_cls, badge_txt = "skipped",  "b-skipped",  "Skipped"
    elif not unlocked:
        card_cls, badge_cls, badge_txt = "locked",   "b-locked",   "Locked"
    elif is_optional:
        card_cls, badge_cls, badge_txt = "pending",  "b-pending",  "Optional"
    else:
        card_cls, badge_cls, badge_txt = "current",  "b-current",  "Pending"

    col_card, col_btn = st.columns([4, 1.8])
    with col_card:
        num_cls = card_cls  # reuse same class name for step-num color
        opt_note  = " — optional" if is_optional else ""
        info_line = ""
        if n == 1 and st.session_state.get("cadp_depot_name"):
            info_line = f"<p>Depot: {st.session_state.cadp_depot_name}</p>"
        elif n == 2 and st.session_state.get("cadp_lens_name"):
            info_line = f"<p>Lens: {st.session_state.cadp_lens_name}</p>"
        check = "✓" if is_done else str(n)
        st.markdown(f"""
            <div class="step-card {card_cls}">
                <span class="step-num {card_cls}">{check}</span>
                <span style="font-size:14px; font-weight:600; color:#111827;">
                    Step {n} — {info['label']}{opt_note}
                </span>
                <span class="step-badge {badge_cls}">{badge_txt}</span>
                {info_line}
            </div>
        """, unsafe_allow_html=True)

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if is_done:
            if st.button("Edit", key=f"edit_{n}", use_container_width=True):
                go_to_step(n)
        elif is_skipped:
            if st.button("↩ Do it", key=f"doit_{n}", use_container_width=True):
                st.session_state.cadp_skipped_steps.discard(n)
                st.rerun()
        elif unlocked:
            if is_optional:
                # Start + Skip side by side — no vertical gap
                btn_l, btn_r = st.columns(2)
                with btn_l:
                    if st.button("Start", key=f"start_{n}",
                                 type="primary", use_container_width=True):
                        go_to_step(n)
                with btn_r:
                    if st.button("Skip", key=f"skip_{n}",
                                 use_container_width=True):
                        st.session_state.cadp_skipped_steps.add(n)
                        st.rerun()
            else:
                if st.button("Start" if not is_done else "Edit",
                             key=f"start_{n}",
                             type="primary", use_container_width=True):
                    go_to_step(n)
        else:
            st.button("Locked", key=f"locked_{n}", disabled=True,
                      use_container_width=True)

    st.markdown(" ")

# ─────────────────────────────────────────────────────────────────────────────
# ALL DONE — Full CADP Download
# ─────────────────────────────────────────────────────────────────────────────
mandatory_done = all(
    n in completed for n, info in STEPS.items() if not info["optional"]
)
if mandatory_done:
    st.success("All mandatory steps complete. Your CADP data product files are ready.")
    st.markdown(" ")

    # ── Collect all generated files from session state ────────────────────────
    import zipfile, io

    depot_name  = st.session_state.get("depot_base_name", "depot")
    lens_name   = st.session_state.get("bundle_lens_name", st.session_state.get("cadp_lens_name", "lens"))
    bundle_name = st.session_state.get("dp_bundle_name", "bundle")
    spec_name   = st.session_state.get("dp_spec_name", "spec")
    flare_name  = st.session_state.get("flare_job_name_for_file", "flare-job")

    files = {}

    # ── depot/snowflake/ — 4 depot files ─────────────────────────────────────
    if st.session_state.get("depot_yaml_r"):
        files[f"depot/snowflake/{depot_name}-r.yml"]       = st.session_state.depot_yaml_r
    if st.session_state.get("depot_yaml_rw"):
        files[f"depot/snowflake/{depot_name}-rw.yml"]      = st.session_state.depot_yaml_rw
    if st.session_state.get("depot_yaml_depot"):
        files[f"depot/snowflake/{depot_name}-depot.yml"]   = st.session_state.depot_yaml_depot
    if st.session_state.get("depot_yaml_scanner"):
        files[f"depot/snowflake/{depot_name}-scanner.yml"] = st.session_state.depot_yaml_scanner

    # ── build/semantic-model/ — lens as deployment.yml (sits alongside model/)
    # ── build/semantic-model/model/ — sqls, tables, views, user_groups.yml
    bundle_tables = st.session_state.get("bundle_tables", [])
    bundle_views  = st.session_state.get("bundle_views", [])
    _sm  = "build/semantic-model"
    _mdl = f"{_sm}/model"
    if st.session_state.get("bundle_generated_lens_yaml"):
        files[f"{_sm}/deployment.yml"]               = st.session_state.bundle_generated_lens_yaml
    for tbl in bundle_tables:
        if tbl.get("generated_sql"):
            files[f"{_mdl}/sqls/{tbl['name']}.sql"]   = tbl["generated_sql"]
        if tbl.get("generated_table_yaml"):
            files[f"{_mdl}/tables/{tbl['name']}.yml"] = tbl["generated_table_yaml"]
    for v in bundle_views:
        if v.get("generated_view_yaml"):
            files[f"{_mdl}/views/{v['name']}.yml"]    = v["generated_view_yaml"]
    if st.session_state.get("bundle_user_groups_yaml"):
        files[f"{_mdl}/user_groups.yml"]             = st.session_state.bundle_user_groups_yaml

    # ── dp-deployment/ — bundle, spec, scanner ───────────────────────────────
    if st.session_state.get("dp_generated_bundle"):
        files[f"dp-deployment/{bundle_name}.yml"]        = st.session_state.dp_generated_bundle
    if st.session_state.get("dp_generated_spec"):
        files[f"dp-deployment/{spec_name}.yml"]          = st.session_state.dp_generated_spec
    if st.session_state.get("dp_generated_scanner"):
        files[f"dp-deployment/scan-{spec_name}.yml"]     = st.session_state.dp_generated_scanner

    # ── secrets/ — cred file(s), one per lens secret ────────────────────────
    for sec in st.session_state.get("bundle_lens_secrets", []):
        sec_name = sec.get("name", "").strip()
        if sec_name and sec.get("cred_yaml"):
            files[f"secrets/{sec_name}.yml"] = sec["cred_yaml"]

    # ── secrets/ — repo credential (git sync secret for Lens) ────────────────
    if st.session_state.get("bundle_repo_cred_yaml") and st.session_state.get("bundle_repo_cred_name"):
        rc_name = st.session_state.bundle_repo_cred_name.strip()
        files[f"secrets/{rc_name}.yml"] = st.session_state.bundle_repo_cred_yaml

    # ── Quality Checks (optional) ─────────────────────────────────────────────
    if 3 in completed and st.session_state.get("cadp_qc_generated_yaml"):
        qc_name = st.session_state.get("cadp_qc_name", "quality-checks")
        files[f"quality-checks/{qc_name}.yml"] = st.session_state.cadp_qc_generated_yaml

    # ── Flare (optional) ─────────────────────────────────────────────────────
    if 4 in completed and st.session_state.get("flare_generated_yaml"):
        files[f"flare/{flare_name}.yml"] = st.session_state.flare_generated_yaml

    # ── Summary of what will be in the ZIP ───────────────────────────────────
    if files:
        st.markdown("**Files included in the full CADP ZIP:**")
        for path in files:
            st.markdown(f"- `{path}`")
        st.markdown(" ")

        # ── Product name input ────────────────────────────────────────────────
        st.markdown("#### 📦 Name Your Data Product")
        st.caption("This will be used as the root folder name inside the ZIP.")
        dp_col1, dp_col2 = st.columns([3, 1])
        with dp_col1:
            cadp_dp_name = st.text_input(
                "Data Product Name",
                value=st.session_state.get("cadp_dp_name", spec_name or "my-data-product"),
                placeholder="e.g. sales-consumer-product",
                key="cadp_dp_name_input",
                label_visibility="collapsed",
            )
        with dp_col2:
            st.markdown("<br>", unsafe_allow_html=True)
            name_confirmed = st.button("✅ Confirm", key="cadp_confirm_dp_name", use_container_width=True)

        if name_confirmed and cadp_dp_name.strip():
            st.session_state["cadp_dp_name"] = cadp_dp_name.strip()
            st.rerun()

        confirmed_name = st.session_state.get("cadp_dp_name", "").strip()

        if confirmed_name:
            st.success(f"📁 Root folder: `{confirmed_name}/`")
            # Prefix all paths with the product name
            prefixed_files = {f"{confirmed_name}/{path}": content for path, content in files.items()}

            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                for path, content in prefixed_files.items():
                    zf.writestr(path, content)
            zip_buf.seek(0)
            save_zip_entry("CADP", "zip_cadp", f"{confirmed_name}.zip", prefixed_files, dp_name=confirmed_name)

            st.download_button(
                label=f"⬇ Download Full CADP — {confirmed_name}.zip",
                data=zip_buf,
                file_name=f"{confirmed_name}.zip",
                mime="application/zip",
                use_container_width=True,
                type="primary",
            )
        else:
            st.info("Enter and confirm a Data Product name above to enable download.")
    else:
        st.info("Complete the steps above to generate files for download.")