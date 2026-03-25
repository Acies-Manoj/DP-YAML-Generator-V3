import io
import zipfile
import streamlit as st


def render_step7(sm_origin, BUNDLE_YAML_KEYS_PRESERVE, BUNDLE_KEYS_TO_CLEAR, back_from_sm):
    tables = st.session_state.bundle_tables
    views  = st.session_state.bundle_views
    lens   = st.session_state.bundle_lens_name

    tables = st.session_state.bundle_tables
    views  = st.session_state.bundle_views
    lens   = st.session_state.bundle_lens_name

    st.subheader("Step 7 — Review All Files & Download")
    st.success(f"Generated: {len(tables)} SQL file(s), {len(tables)} Table YAML(s), {len(views)} View YAML(s), 1 Lens YAML, 1 User Groups YAML, 1 Repo Credential YAML.")

    tab_sql, tab_tbl, tab_view, tab_lens, tab_ug, tab_cred = st.tabs(["SQL Files", "Table YAMLs", "View YAMLs", "Lens YAML", "User Groups", "Repo Credential"])

    with tab_sql:
        if len(tables) == 1:
            st.code(tables[0]["generated_sql"], language="sql")
            st.download_button("Download SQL", data=tables[0]["generated_sql"],
                file_name=f"{tables[0]['name']}.sql", mime="text/plain", use_container_width=True)
        else:
            sub_tabs = st.tabs([t["name"] for t in tables])
            for i, tbl in enumerate(tables):
                with sub_tabs[i]:
                    st.code(tbl["generated_sql"], language="sql")
                    st.download_button(f"Download {tbl['name']}.sql", data=tbl["generated_sql"],
                        file_name=f"{tbl['name']}.sql", mime="text/plain", use_container_width=True, key=f"dl_sql_{i}")

    with tab_tbl:
        if len(tables) == 1:
            st.code(tables[0]["generated_table_yaml"], language="yaml")
            st.download_button("Download Table YAML", data=tables[0]["generated_table_yaml"],
                file_name=f"{tables[0]['name']}.yml", mime="text/yaml", use_container_width=True)
        else:
            sub_tabs = st.tabs([t["name"] for t in tables])
            for i, tbl in enumerate(tables):
                with sub_tabs[i]:
                    st.code(tbl["generated_table_yaml"], language="yaml")
                    st.download_button(f"Download {tbl['name']}.yml", data=tbl["generated_table_yaml"],
                        file_name=f"{tbl['name']}.yml", mime="text/yaml", use_container_width=True, key=f"dl_tbl_{i}")

    with tab_view:
        if not views:
            st.info("No views generated.")
        elif len(views) == 1:
            st.code(views[0]["generated_view_yaml"], language="yaml")
            st.download_button("Download View YAML", data=views[0]["generated_view_yaml"],
                file_name=f"{views[0]['name']}.yml", mime="text/yaml", use_container_width=True)
        else:
            sub_tabs = st.tabs([v["name"] for v in views])
            for i, v in enumerate(views):
                with sub_tabs[i]:
                    st.code(v["generated_view_yaml"], language="yaml")
                    st.download_button(f"Download {v['name']}.yml", data=v["generated_view_yaml"],
                        file_name=f"{v['name']}.yml", mime="text/yaml", use_container_width=True, key=f"dl_view_{i}")

    with tab_lens:
        st.code(st.session_state.bundle_generated_lens_yaml, language="yaml")
        st.download_button("Download Lens YAML", data=st.session_state.bundle_generated_lens_yaml,
            file_name=f"{lens}.yml", mime="text/yaml", use_container_width=True)

    with tab_ug:
        if st.session_state.bundle_user_groups_yaml:
            st.code(st.session_state.bundle_user_groups_yaml, language="yaml")
            st.download_button("Download user_groups.yml", data=st.session_state.bundle_user_groups_yaml,
                file_name="user_groups.yml", mime="text/yaml", use_container_width=True)
        else:
            st.info("User Groups YAML not yet generated.")

    with tab_cred:
        if st.session_state.bundle_repo_cred_yaml:
            st.code(st.session_state.bundle_repo_cred_yaml, language="yaml")
            st.download_button("Download Repo Credential YAML",
                data=st.session_state.bundle_repo_cred_yaml,
                file_name=f"{st.session_state.bundle_repo_cred_name or 'repo-cred'}.yml",
                mime="text/yaml", use_container_width=True)
        else:
            st.info("Repo Credential YAML not yet generated.")

    st.divider()

    import zipfile, io
    zip_buf = io.BytesIO()
    _sm  = "build/semantic-model"
    _mdl = f"{_sm}/model"
    with zipfile.ZipFile(zip_buf, "w") as zf:
        # Lens YAML — lives as deployment.yml alongside model/
        zf.writestr(f"{_sm}/deployment.yml", st.session_state.bundle_generated_lens_yaml)
        for tbl in tables:
            # SQLs and table YAMLs — under model/sqls/ and model/tables/
            zf.writestr(f"{_mdl}/sqls/{tbl['name']}.sql",    tbl["generated_sql"])
            zf.writestr(f"{_mdl}/tables/{tbl['name']}.yml",  tbl["generated_table_yaml"])
        for v in views:
            if v.get("generated_view_yaml"):
                zf.writestr(f"{_mdl}/views/{v['name']}.yml", v["generated_view_yaml"])
        if st.session_state.bundle_user_groups_yaml:
            # user_groups uses .yml consistently
            zf.writestr(f"{_mdl}/user_groups.yml", st.session_state.bundle_user_groups_yaml)
        if st.session_state.bundle_repo_cred_yaml:
            cred_fname = st.session_state.bundle_repo_cred_name or "repo-cred"
            zf.writestr(f"secrets/{cred_fname}.yml", st.session_state.bundle_repo_cred_yaml)
    zip_buf.seek(0)

    st.download_button(
        "Download All as ZIP",
        data=zip_buf,
        file_name="semantic_model_bundle.zip",
        mime="application/zip",
        use_container_width=True,
    )

    if sm_origin == "cadp_full":
        st.session_state["cadp_lens_name"] = lens
        if "cadp_completed_steps" not in st.session_state:
            st.session_state.cadp_completed_steps = set()
        st.session_state.cadp_completed_steps.add(2)
        st.divider()
        st.success("Semantic Model complete. Return to the CADP flow to continue.")
        if st.button("Back to CADP Flow", use_container_width=True, type="primary"):
            keep = BUNDLE_YAML_KEYS_PRESERVE
            for k in BUNDLE_KEYS_TO_CLEAR:
                if k not in keep:
                    st.session_state.pop(k, None)
            st.switch_page("pages/cadp_flow.py")