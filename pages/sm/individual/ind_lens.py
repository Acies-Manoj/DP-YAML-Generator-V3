import streamlit as st
from utils.generators import generate_lens_yaml
from utils.history import save_entry
from utils.examples import EXAMPLE_LENS, show_example
from utils.ui_utils import inline_docs_banner

LOG_LEVELS = ["info", "debug", "warn", "error"]


def render_ind_lens():
    st.subheader("Lens Deployment Builder")
    inline_docs_banner("lens") 

    for key, default in [
        ("lens_tags",       ["lens"]),
        ("lens_secrets",    [{"name": "", "allKeys": True}]),
        ("lens_sync_flags", ["--ref=main"]),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    ab1, ab2, ab3 = st.columns(3)
    with ab1:
        if st.button("➕ Add Tag"):     st.session_state.lens_tags.append(""); st.rerun()
    with ab2:
        if st.button("➕ Add Secret"):  st.session_state.lens_secrets.append({"name": "", "allKeys": True}); st.rerun()
    with ab3:
        if st.button("➕ Add Sync Flag"): st.session_state.lens_sync_flags.append(""); st.rerun()

    st.markdown(" ")

    with st.form("lens_form"):
        st.markdown("#### Basic Info")
        bl1, bl2 = st.columns(2)
        with bl1:
            lens_name    = st.text_input("Name *", placeholder="e.g. customer-analytics-lens")
            lens_layer   = st.text_input("Layer", value="user")
            lens_compute = st.text_input("Compute", value="runnable-default")
        with bl2:
            lens_desc = st.text_area("Description", placeholder="e.g. Semantic model for customer analytics data product.", height=120)

        st.markdown("**Tags**")
        updated_lens_tags = []
        for i, tag in enumerate(st.session_state.lens_tags):
            tc1, tc2 = st.columns([5, 1])
            with tc1:
                val = st.text_input(f"Tag {i+1}", value=tag, key=f"ltag_{i}", placeholder="e.g. lens")
                updated_lens_tags.append(val)
            with tc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("❌", key=f"rm_ltag_{i}"):
                    st.session_state.lens_tags.pop(i); st.rerun()

        st.divider()
        st.markdown("#### Secrets")
        for i, s in enumerate(st.session_state.lens_secrets):
            sc1, sc2, sc3 = st.columns([4, 2, 0.8])
            with sc1: st.session_state.lens_secrets[i]["name"]    = st.text_input("Secret Name", value=s["name"], key=f"sec_name_{i}", placeholder="e.g. customer-dp-github-cred")
            with sc2: st.session_state.lens_secrets[i]["allKeys"] = st.checkbox("allKeys", value=s.get("allKeys", True), key=f"sec_ak_{i}")
            with sc3:
                st.markdown("<br><br>", unsafe_allow_html=True)
                if st.form_submit_button("❌", key=f"rm_sec_{i}"):
                    st.session_state.lens_secrets.pop(i); st.rerun()

        st.divider()
        st.markdown("#### Source")
        src1, src2, src3 = st.columns(3)
        with src1: source_type    = st.text_input("Type",    value="minerva")
        with src2: source_name    = st.text_input("Name",    placeholder="e.g. miniature")
        with src3: source_catalog = st.text_input("Catalog", placeholder="e.g. icebase")

        st.divider()
        st.markdown("#### Repo")
        repo_url     = st.text_input("URL", placeholder="e.g. https://github.com/org/CustomerAnalyticsDP")
        repo_basedir = st.text_input("lensBaseDir", placeholder="e.g. CustomerAnalyticsDP/build/model")

        st.markdown("**Sync Flags**")
        updated_sync_flags = []
        for i, sf_flag in enumerate(st.session_state.lens_sync_flags):
            sfc1, sfc2 = st.columns([5, 1])
            with sfc1:
                val = st.text_input(f"Flag {i+1}", value=sf_flag, key=f"lsf_{i}", placeholder="e.g. --ref=main")
                updated_sync_flags.append(val)
            with sfc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("❌", key=f"rm_lsf_{i}"):
                    st.session_state.lens_sync_flags.pop(i); st.rerun()

        st.divider()
        st.markdown("#### API, Worker, Router & Metric")
        st.caption("Comments for envs and iris are auto-included in output. Fill resources below.")


        st.markdown("**API**")
        a1, a2, a3, a4, a5, a6 = st.columns(6)
        with a1: api_replicas = st.number_input("Replicas", min_value=1, value=1, key="api_rep")
        with a2: api_loglevel = st.selectbox("Log Level", LOG_LEVELS, index=0, key="api_ll")
        with a3: api_req_cpu  = st.text_input("Req CPU",  value="100m",  key="api_rcpu")
        with a4: api_req_mem  = st.text_input("Req Mem",  value="256Mi", key="api_rmem")
        with a5: api_lim_cpu  = st.text_input("Lim CPU",  value="500m",  key="api_lcpu")
        with a6: api_lim_mem  = st.text_input("Lim Mem",  value="500Mi", key="api_lmem")

        st.markdown("**Worker**")
        w1, w2, w3, w4, w5, w6 = st.columns(6)
        with w1: wkr_replicas = st.number_input("Replicas", min_value=1, value=1, key="wkr_rep")
        with w2: wkr_loglevel = st.selectbox("Log Level", LOG_LEVELS, index=1, key="wkr_ll")
        with w3: wkr_req_cpu  = st.text_input("Req CPU",  value="100m",  key="wkr_rcpu")
        with w4: wkr_req_mem  = st.text_input("Req Mem",  value="256Mi", key="wkr_rmem")
        with w5: wkr_lim_cpu  = st.text_input("Lim CPU",  value="500m",  key="wkr_lcpu")
        with w6: wkr_lim_mem  = st.text_input("Lim Mem",  value="500Mi", key="wkr_lmem")

        st.markdown("**Router**")
        r1, r2, r3, r4, r5 = st.columns(5)
        with r1: rtr_loglevel = st.selectbox("Log Level", LOG_LEVELS, index=0, key="rtr_ll")
        with r2: rtr_req_cpu  = st.text_input("Req CPU",  value="100m",  key="rtr_rcpu")
        with r3: rtr_req_mem  = st.text_input("Req Mem",  value="256Mi", key="rtr_rmem")
        with r4: rtr_lim_cpu  = st.text_input("Lim CPU",  value="500m",  key="rtr_lcpu")
        with r5: rtr_lim_mem  = st.text_input("Lim Mem",  value="500Mi", key="rtr_lmem")

        st.markdown("**Metric**")
        met_loglevel = st.selectbox("Log Level", LOG_LEVELS, index=0, key="met_ll")

        st.markdown(" ")
        generate_lens = st.form_submit_button("Generate Lens Deployment YAML", use_container_width=True)

    st.session_state.lens_tags       = updated_lens_tags
    st.session_state.lens_sync_flags = updated_sync_flags

    if generate_lens:
        if not lens_name.strip():
            st.error("Name is required.")
        else:
            lens_data = {
                "name": lens_name.strip(), "layer": lens_layer.strip(),
                "description": lens_desc.strip(), "compute": lens_compute.strip(),
                "tags":    [t.strip() for t in st.session_state.lens_tags if t.strip()],
                "secrets": st.session_state.lens_secrets,
                "source":  {"type": source_type.strip(), "name": source_name.strip(), "catalog": source_catalog.strip()},
                "repo":    {"url": repo_url.strip(), "lensBaseDir": repo_basedir.strip(),
                            "syncFlags": [f.strip() for f in st.session_state.lens_sync_flags if f.strip()]},
                "api":    {"replicas": api_replicas, "logLevel": api_loglevel, "req_cpu": api_req_cpu, "req_mem": api_req_mem, "lim_cpu": api_lim_cpu, "lim_mem": api_lim_mem},
                "worker": {"replicas": wkr_replicas, "logLevel": wkr_loglevel, "req_cpu": wkr_req_cpu, "req_mem": wkr_req_mem, "lim_cpu": wkr_lim_cpu, "lim_mem": wkr_lim_mem},
                "router": {"logLevel": rtr_loglevel, "req_cpu": rtr_req_cpu, "req_mem": rtr_req_mem, "lim_cpu": rtr_lim_cpu, "lim_mem": rtr_lim_mem},
                "metric": {"logLevel": met_loglevel},
            }
            st.session_state.generated_lens_yaml = generate_lens_yaml(lens_data)
            save_entry("Specific", "lens", f"{lens_name.strip()}.yml", st.session_state.generated_lens_yaml)
            st.session_state.lens_name_for_file  = lens_name.strip()

    if "generated_lens_yaml" in st.session_state:
        st.markdown("### Lens Deployment YAML Preview")
        st.code(st.session_state.generated_lens_yaml, language="yaml")
        st.download_button(
            "⬇ Download Lens Deployment YAML",
            data=st.session_state.generated_lens_yaml,
            file_name=f"{st.session_state.get('lens_name_for_file', 'lens')}.yml",
            mime="text/yaml",
            use_container_width=True,
        )