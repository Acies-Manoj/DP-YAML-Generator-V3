import streamlit as st
from utils.generators import generate_lens_yaml
from utils.history import save_entry
from utils.examples import EXAMPLE_LENS, show_example
from utils.ui_utils import inline_docs_banner

LOG_LEVELS = ["info", "debug", "warn", "error"]


def render_step5():
    if not st.session_state.bundle_lens_preview_mode:
        # Auto-fill first secret name from repo cred if it's still empty
        _cred_name = st.session_state.get("bundle_repo_cred_name", "")
        if _cred_name and st.session_state.bundle_lens_secrets:
            if not st.session_state.bundle_lens_secrets[0].get("name"):
                st.session_state.bundle_lens_secrets[0]["name"] = _cred_name
                # Clear widget cache so the text input re-reads the new value
                st.session_state.pop("b_secn_0", None)

        st.subheader("Step 5 — Lens Deployment")
        inline_docs_banner("lens")
        show_example(st, "Lens Deployment YAML", EXAMPLE_LENS)

        st.markdown("#### Basic Info")
        bl1, bl2 = st.columns(2)
        with bl1:
            b_lens_name = st.text_input("Name *", value=st.session_state.bundle_lens_name,
                key="b_lens_name", placeholder="e.g. customer-analytics-lens")
        with bl2:
            b_lens_desc = st.text_area("Description",
                value=st.session_state.get("bundle_lens_desc_saved", "Semantic model for the data product."),
                key="b_lens_desc",
                placeholder="e.g. Semantic model for customer analytics.", height=100)

        st.divider()

        # ── Tags ──────────────────────────────────────────────────────────
        _lth1, _lth2 = st.columns([5, 1])
        with _lth1: st.markdown("**Tags**")
        with _lth2:
            if st.button("➕ Add", key="b_add_ltag"):
                st.session_state.bundle_lens_tags.append(""); st.rerun()
        updated_lens_tags = []
        for i, tag in enumerate(st.session_state.bundle_lens_tags):
            ltc1, ltc2 = st.columns([5, 1])
            with ltc1:
                val = st.text_input(f"Tag {i+1}", value=tag, key=f"b_ltag_{i}", placeholder="lens")
                updated_lens_tags.append(val)
            with ltc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("X", key=f"b_rm_ltag_{i}"):
                    st.session_state.bundle_lens_tags.pop(i); st.rerun()
        st.session_state.bundle_lens_tags = updated_lens_tags

        st.divider()

        # ── Secrets ───────────────────────────────────────────────────────
        _lsh1, _lsh2 = st.columns([5, 1])
        with _lsh1: st.markdown("#### Secrets")
        with _lsh2:
            if st.button("➕ Add", key="b_add_lsec"):
                st.session_state.bundle_lens_secrets.append({"name": "", "allKeys": True}); st.rerun()
        for i, s in enumerate(st.session_state.bundle_lens_secrets):
            sc1, sc2, sc3 = st.columns([4, 2, 0.8])
            with sc1: st.session_state.bundle_lens_secrets[i]["name"]    = st.text_input("Secret Name", value=s["name"], key=f"b_secn_{i}", placeholder="e.g. customer-dp-github-cred")
            with sc2: st.session_state.bundle_lens_secrets[i]["allKeys"] = st.checkbox("allKeys", value=s.get("allKeys", True), key=f"b_secak_{i}")
            with sc3:
                st.markdown("<br><br>", unsafe_allow_html=True)
                if st.button("X", key=f"b_rm_sec_{i}"):
                    st.session_state.bundle_lens_secrets.pop(i); st.rerun()

        st.divider()

        # ── Source ────────────────────────────────────────────────────────
        st.markdown("#### Source")
        src1, src2 = st.columns(2)
        with src1: b_src_name    = st.text_input("Name",    value=st.session_state.bundle_lens_src_name,    key="b_src_name",    placeholder="e.g. miniature")
        with src2: b_src_catalog = st.text_input("Catalog", value=st.session_state.bundle_lens_src_catalog, key="b_src_catalog", placeholder="e.g. icebase")

        st.divider()

        # ── Repo ──────────────────────────────────────────────────────────
        st.markdown("#### Repo")
        b_repo_url     = st.text_input("URL",         value=st.session_state.bundle_lens_repo_url,     key="b_repo_url",     placeholder="e.g. https://github.com/org/CustomerAnalyticsDP")
        b_repo_basedir = st.text_input("lensBaseDir", value=st.session_state.bundle_lens_repo_basedir, key="b_repo_basedir", placeholder="e.g. CustomerAnalyticsDP/build/model")

        _lsfh1, _lsfh2 = st.columns([5, 1])
        with _lsfh1: st.markdown("**Sync Flags**")
        with _lsfh2:
            if st.button("➕ Add", key="b_add_lsf"):
                st.session_state.bundle_lens_sync_flags.append(""); st.rerun()
        updated_sync_flags = []
        for i, sf_flag in enumerate(st.session_state.bundle_lens_sync_flags):
            sfc1, sfc2 = st.columns([5, 1])
            with sfc1:
                val = st.text_input(f"Flag {i+1}", value=sf_flag, key=f"b_lsf_{i}", placeholder="--ref=main")
                updated_sync_flags.append(val)
            with sfc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("X", key=f"b_rm_lsf_{i}"):
                    st.session_state.bundle_lens_sync_flags.pop(i); st.rerun()
        st.session_state.bundle_lens_sync_flags = updated_sync_flags

        st.divider()

        # ── Advanced / Default Settings expander ──────────────────────────
        with st.expander("⚙️ Advanced / Default Settings", expanded=False):
            st.caption("These are pre-filled with standard defaults. Only change if you need custom values.")

            adv1, adv2, adv3, adv4 = st.columns(4)
            with adv1: b_lens_version = st.text_input("Version",      value=st.session_state.bundle_lens_version,  key="b_lens_version")
            with adv2: b_lens_layer   = st.text_input("Layer",        value=st.session_state.bundle_lens_layer,    key="b_lens_layer")
            with adv3: b_lens_compute = st.text_input("Compute",      value=st.session_state.bundle_lens_compute,  key="b_lens_compute")
            with adv4: b_src_type     = st.text_input("Source Type",  value=st.session_state.bundle_lens_src_type, key="b_src_type")

            st.markdown("**API**")
            a1, a2, a3, a4, a5, a6 = st.columns(6)
            with a1: b_api_rep  = st.number_input("Replicas", min_value=1, value=1,     key="b_api_rep")
            with a2: b_api_ll   = st.selectbox("Log Level", LOG_LEVELS, index=0,        key="b_api_ll")
            with a3: b_api_rcpu = st.text_input("Req CPU",  value="100m",               key="b_api_rcpu")
            with a4: b_api_rmem = st.text_input("Req Mem",  value="256Mi",              key="b_api_rmem")
            with a5: b_api_lcpu = st.text_input("Lim CPU",  value="500m",               key="b_api_lcpu")
            with a6: b_api_lmem = st.text_input("Lim Mem",  value="500Mi",              key="b_api_lmem")

            st.markdown("**Worker**")
            w1, w2, w3, w4, w5, w6 = st.columns(6)
            with w1: b_wkr_rep  = st.number_input("Replicas", min_value=1, value=1,     key="b_wkr_rep")
            with w2: b_wkr_ll   = st.selectbox("Log Level", LOG_LEVELS, index=1,        key="b_wkr_ll")
            with w3: b_wkr_rcpu = st.text_input("Req CPU",  value="100m",               key="b_wkr_rcpu")
            with w4: b_wkr_rmem = st.text_input("Req Mem",  value="256Mi",              key="b_wkr_rmem")
            with w5: b_wkr_lcpu = st.text_input("Lim CPU",  value="500m",               key="b_wkr_lcpu")
            with w6: b_wkr_lmem = st.text_input("Lim Mem",  value="500Mi",              key="b_wkr_lmem")

            st.markdown("**Router**")
            r1, r2, r3, r4, r5 = st.columns(5)
            with r1: b_rtr_ll   = st.selectbox("Log Level", LOG_LEVELS, index=0,        key="b_rtr_ll")
            with r2: b_rtr_rcpu = st.text_input("Req CPU",  value="100m",               key="b_rtr_rcpu")
            with r3: b_rtr_rmem = st.text_input("Req Mem",  value="256Mi",              key="b_rtr_rmem")
            with r4: b_rtr_lcpu = st.text_input("Lim CPU",  value="500m",               key="b_rtr_lcpu")
            with r5: b_rtr_lmem = st.text_input("Lim Mem",  value="500Mi",              key="b_rtr_lmem")

            st.markdown("**Metric**")
            b_met_ll = st.selectbox("Log Level", LOG_LEVELS, index=0, key="b_met_ll")

        # ── Preview at bottom ─────────────────────────────────────────────
        st.divider()
        if st.button("Preview Lens YAML ↓", key="b_lens_preview_bot", type="primary", use_container_width=True):
            st.session_state["b_lens_preview_clicked"] = True
            st.rerun()

        if st.session_state.pop("b_lens_preview_clicked", False):
            if not b_lens_name.strip():
                st.error("Lens Name is required.")
            else:
                lens_data = {
                    "name": b_lens_name.strip(), "version": b_lens_version.strip(), "layer": b_lens_layer.strip(),
                    "description": b_lens_desc.strip(), "compute": b_lens_compute.strip(),
                    "tags":    [t.strip() for t in st.session_state.bundle_lens_tags if t.strip()],
                    "secrets": st.session_state.bundle_lens_secrets,
                    "source":  {"type": b_src_type.strip(), "name": b_src_name.strip(), "catalog": b_src_catalog.strip()},
                    "repo":    {"url": b_repo_url.strip(), "lensBaseDir": b_repo_basedir.strip(),
                                "syncFlags": [f.strip() for f in st.session_state.bundle_lens_sync_flags if f.strip()]},
                    "api":    {"replicas": b_api_rep, "logLevel": b_api_ll, "req_cpu": b_api_rcpu, "req_mem": b_api_rmem, "lim_cpu": b_api_lcpu, "lim_mem": b_api_lmem},
                    "worker": {"replicas": b_wkr_rep, "logLevel": b_wkr_ll, "req_cpu": b_wkr_rcpu, "req_mem": b_wkr_rmem, "lim_cpu": b_wkr_lcpu, "lim_mem": b_wkr_lmem},
                    "router": {"logLevel": b_rtr_ll, "req_cpu": b_rtr_rcpu, "req_mem": b_rtr_rmem, "lim_cpu": b_rtr_lcpu, "lim_mem": b_rtr_lmem},
                    "metric": {"logLevel": b_met_ll},
                }
                st.session_state.bundle_generated_lens_yaml = generate_lens_yaml(lens_data)
                save_entry("CADP", "lens", f"{b_lens_name.strip()}.yml", st.session_state.bundle_generated_lens_yaml, dp_name=b_lens_name.strip())
                st.session_state.bundle_lens_name           = b_lens_name.strip()
                st.session_state.bundle_lens_desc_saved     = b_lens_desc.strip()
                st.session_state.bundle_lens_src_name       = b_src_name.strip()
                st.session_state.bundle_lens_src_catalog    = b_src_catalog.strip()
                st.session_state.bundle_lens_src_type       = b_src_type.strip()
                st.session_state.bundle_lens_repo_url       = b_repo_url.strip()
                st.session_state.bundle_lens_repo_basedir   = b_repo_basedir.strip()
                st.session_state.bundle_lens_version        = b_lens_version.strip()
                st.session_state.bundle_lens_layer          = b_lens_layer.strip()
                st.session_state.bundle_lens_compute        = b_lens_compute.strip()
                st.session_state.bundle_lens_preview_mode   = True
                st.rerun()

    else:
        st.subheader("Step 5 — Lens Deployment YAML Preview")
        st.code(st.session_state.bundle_generated_lens_yaml, language="yaml")
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("Edit Lens YAML"):
                st.session_state.bundle_lens_preview_mode = False
                st.rerun()
        with pc2:
            if st.button("Continue to User Groups", use_container_width=True, type="primary"):
                st.session_state.bundle_lens_preview_mode = False
                st.session_state.bundle_step = 6
                st.rerun()