import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.ui_utils import load_global_css, app_footer

st.set_page_config(page_title="SADP — Full Data Product", layout="wide")
load_global_css()

# ─────────────────────────────────────────────────────────────────────────────
# STATE INIT
# ─────────────────────────────────────────────────────────────────────────────
STEPS = {
    1: {"label": "Depot",          "optional": False},
    2: {"label": "Quality Checks", "optional": False},
    3: {"label": "Bundle",         "optional": False},
    4: {"label": "Spec",           "optional": False},
    5: {"label": "Scanner",        "optional": False},
}

if "sadp_completed_steps" not in st.session_state:
    st.session_state.sadp_completed_steps = set()
if "sadp_skipped_steps" not in st.session_state:
    st.session_state.sadp_skipped_steps = set()

completed = st.session_state.sadp_completed_steps
skipped   = st.session_state.sadp_skipped_steps

# ─────────────────────────────────────────────────────────────────────────────
# NAVIGATION HELPER
# ─────────────────────────────────────────────────────────────────────────────
def go_to_step(n):
    if n == 1:
        st.session_state["depot_origin"] = "sadp_full"
        st.switch_page("pages/6_Depot.py")
    elif n == 2:
        st.session_state["sadp_qc_origin"] = "sadp_full"
        st.switch_page("pages/2_SADP_Quality_Checks.py")
    elif n == 3:
        st.session_state["sadp_origin"] = "sadp_full"
        st.switch_page("pages/3_SADP_Bundle.py")
    elif n == 4:
        st.session_state["sadp_origin"] = "sadp_full"
        st.switch_page("pages/4_SADP_Spec.py")
    elif n == 5:
        st.session_state["sadp_origin"] = "sadp_full"
        st.switch_page("pages/5_SADP_Scanner.py")

def is_unlocked(n):
    return True  # All steps always accessible during testing

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("## SADP — Source-Aligned Data Product")
st.markdown(
    '<p style="color:#6b7280; font-size:13px; margin-top:-8px;">Complete all steps below to generate your full SADP package.</p>',
    unsafe_allow_html=True,
)

nav_l, _, nav_r = st.columns([1, 4, 1.5])
with nav_l:
    if st.button("← Back to Home"):
        st.session_state.home_screen = "full_dp"
        st.switch_page("app.py")
with nav_r:
    if st.button("Start Over"):
        for k in ["sadp_completed_steps", "sadp_skipped_steps", "sadp_depot_name"]:
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
    elif n == min((s for s in STEPS if s not in completed and s not in skipped), default=n):
        card_cls, badge_cls, badge_txt = "current",  "b-current",  "Pending"
    else:
        card_cls, badge_cls, badge_txt = "pending",  "b-pending",  "Pending"

    opt_note  = " — optional" if is_optional else ""
    info_line = ""
    if n == 1 and st.session_state.get("sadp_depot_name"):
        info_line = f"<p>Depot: {st.session_state.sadp_depot_name}</p>"
    elif n == 2 and st.session_state.get("sadp_qc_name"):
        info_line = f"<p>Checks: {st.session_state.sadp_qc_name}</p>"

    col_card, col_btn = st.columns([4, 1.8])
    with col_card:
        check = "✓" if is_done else str(n)
        st.markdown(f"""
            <div class="step-card {card_cls}">
                <span class="step-num {card_cls}">{check}</span>
                <span style="font-size:14px; font-weight:600; color:#e5e7eb;">
                    Step {n} — {info['label']}{opt_note}
                </span>
                <span class="step-badge {badge_cls}">{badge_txt}</span>
                {info_line}
            </div>
        """, unsafe_allow_html=True)

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if is_done:
            if st.button("Edit", key=f"sadp_edit_{n}", use_container_width=True):
                go_to_step(n)
        elif is_skipped:
            if st.button("↩ Do it", key=f"sadp_doit_{n}", use_container_width=True):
                st.session_state.sadp_skipped_steps.discard(n)
                st.rerun()
        elif unlocked:
            if is_optional:
                btn_l, btn_r = st.columns(2)
                with btn_l:
                    if st.button("Start", key=f"sadp_start_{n}",
                                 type="primary", use_container_width=True):
                        go_to_step(n)
                with btn_r:
                    if st.button("Skip", key=f"sadp_skip_{n}",
                                 use_container_width=True):
                        st.session_state.sadp_skipped_steps.add(n)
                        st.rerun()
            else:
                if st.button("Start", key=f"sadp_start_{n}",
                             type="primary", use_container_width=True):
                    go_to_step(n)
        else:
            st.button("Locked", key=f"sadp_locked_{n}", disabled=True,
                      use_container_width=True)

    st.markdown(" ")

# ─────────────────────────────────────────────────────────────────────────────
# ALL DONE — Full SADP Download
# ─────────────────────────────────────────────────────────────────────────────
mandatory_done = all(
    n in completed for n, info in STEPS.items() if not info["optional"]
)

if mandatory_done:
    st.success("All mandatory steps complete. Your SADP files are ready.")
    st.markdown(" ")

    import zipfile, io

    depot_name  = st.session_state.get("depot_base_name", "depot")
    bundle_name = st.session_state.get("sadp_bundle_name", "bundle")
    spec_name   = st.session_state.get("sadp_spec_name", "spec")

    files = {}

    # ── depot/snowflake/ ──────────────────────────────────────────────────────
    if st.session_state.get("depot_yaml_r"):
        files[f"depot/snowflake/{depot_name}-r.yml"]       = st.session_state.depot_yaml_r
    if st.session_state.get("depot_yaml_rw"):
        files[f"depot/snowflake/{depot_name}-rw.yml"]      = st.session_state.depot_yaml_rw
    if st.session_state.get("depot_yaml_depot"):
        files[f"depot/snowflake/{depot_name}-depot.yml"]   = st.session_state.depot_yaml_depot
    if st.session_state.get("depot_yaml_scanner"):
        files[f"depot/snowflake/{depot_name}-scanner.yml"] = st.session_state.depot_yaml_scanner

    # ── quality-checks/ — only if NOT skipped ────────────────────────────────
    if 2 not in skipped and st.session_state.get("sadp_qc_generated_yaml"):
        qc_name = st.session_state.get("sadp_qc_name", "quality-checks")
        files[f"quality-checks/{qc_name}.yml"] = st.session_state.sadp_qc_generated_yaml

    # ── dp-deployment/ ────────────────────────────────────────────────────────
    if st.session_state.get("sadp_generated_bundle"):
        files[f"dp-deployment/{bundle_name}.yml"]    = st.session_state.sadp_generated_bundle
    if st.session_state.get("sadp_generated_spec"):
        files[f"dp-deployment/{spec_name}.yml"]      = st.session_state.sadp_generated_spec
    if st.session_state.get("sadp_generated_scanner"):
        files[f"dp-deployment/scan-{spec_name}.yml"] = st.session_state.sadp_generated_scanner

    if files:
        st.markdown("**Files included in the SADP ZIP:**")
        for path in files:
            st.markdown(f"- `{path}`")
        st.markdown(" ")

        # ── Product name input ────────────────────────────────────────────────
        st.markdown("#### 📦 Name Your Data Product")
        st.caption("This will be used as the root folder name inside the ZIP.")
        dp_col1, dp_col2 = st.columns([3, 1])
        with dp_col1:
            sadp_dp_name = st.text_input(
                "Data Product Name",
                value=st.session_state.get("sadp_dp_name", spec_name or "my-data-product"),
                placeholder="e.g. sales-source-product",
                key="sadp_dp_name_input",
                label_visibility="collapsed",
            )
        with dp_col2:
            st.markdown("<br>", unsafe_allow_html=True)
            name_confirmed = st.button("✅ Confirm", key="sadp_confirm_dp_name", use_container_width=True)

        if name_confirmed and sadp_dp_name.strip():
            st.session_state["sadp_dp_name"] = sadp_dp_name.strip()
            st.rerun()

        confirmed_name = st.session_state.get("sadp_dp_name", "").strip()

        if confirmed_name:
            st.success(f"📁 Root folder: `{confirmed_name}/`")
            # Prefix all paths with the product name
            prefixed_files = {f"{confirmed_name}/{path}": content for path, content in files.items()}

            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                for path, content in prefixed_files.items():
                    zf.writestr(path, content)
            zip_buf.seek(0)

            st.download_button(
                label=f"⬇ Download Full SADP — {confirmed_name}.zip",
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

app_footer()