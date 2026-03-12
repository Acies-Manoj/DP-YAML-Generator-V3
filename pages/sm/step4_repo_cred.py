import streamlit as st
from utils.generators import generate_repo_cred_yaml

_GIT_TYPES = ["github", "bitbucket", "gitlab", "azure-devops"]


def render_step4():

    if not st.session_state.bundle_repo_cred_preview:
        st.subheader("Step 4 — Repo Credential YAML")
        st.caption("Generate the instance-secret credential file for your Git repo. This is a standalone file — its name will be referenced in the Lens secrets in the next step.")

        st.markdown("#### Credential Info")
        rc1, rc2 = st.columns(2)
        with rc1:
            b_rc_name = st.text_input("Credential Name *", value=st.session_state.bundle_repo_cred_name,
                key="b_rc_name", placeholder="e.g. bitbucket-cred")
            b_rc_git_type = st.selectbox("Git Provider", _GIT_TYPES, key="b_rc_git_type")
            b_rc_owner = st.text_input("Owner", value=st.session_state.bundle_repo_cred_owner,
                key="b_rc_owner", placeholder="e.g. your-dataos-username")
        with rc2:
            b_rc_desc = st.text_area("Description",
                value=st.session_state.bundle_repo_cred_desc,
                key="b_rc_desc",
                placeholder="e.g. GitHub read secrets for repos.", height=100)

        st.divider()
        st.markdown("#### Git Credentials")
        st.caption("These will be stored as `GITSYNC_USERNAME` and `GITSYNC_PASSWORD` in the secret.")
        cred1, cred2 = st.columns(2)
        with cred1:
            b_rc_username = st.text_input("Git Username",
                value=st.session_state.bundle_repo_cred_username,
                key="b_rc_username",
                placeholder="e.g. your-git-username")
        with cred2:
            b_rc_password = st.text_input("Git Token / Password",
                value=st.session_state.bundle_repo_cred_password,
                key="b_rc_password",
                type="password", placeholder="e.g. your-personal-access-token")

        st.divider()

        _rth1, _rth2 = st.columns([5, 1])
        with _rth1: st.markdown("**Tags**")
        with _rth2:
            if st.button("➕ Add", key="b_add_rc_tag"):
                st.session_state.bundle_repo_cred_tags.append(""); st.rerun()
        _updated_rc_tags = []
        for i, tag in enumerate(st.session_state.bundle_repo_cred_tags):
            tc1, tc2 = st.columns([5, 1])
            with tc1:
                val = st.text_input(f"Tag {i+1}", value=tag, key=f"b_rctag_{i}")
                _updated_rc_tags.append(val)
            with tc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("X", key=f"b_rm_rctag_{i}"):
                    st.session_state.bundle_repo_cred_tags.pop(i); st.rerun()
        st.session_state.bundle_repo_cred_tags = _updated_rc_tags

        with st.expander("⚙️ Advanced / Default Settings", expanded=False):
            st.caption("Pre-filled with standard defaults. Change only if needed.")
            adv1, adv2, adv3 = st.columns(3)
            with adv1: b_rc_version     = st.text_input("Version",     value=st.session_state.bundle_repo_cred_version,     key="b_rc_version")
            with adv2: b_rc_layer       = st.text_input("Layer",       value=st.session_state.bundle_repo_cred_layer,       key="b_rc_layer")
            with adv3: b_rc_acl         = st.text_input("ACL",         value=st.session_state.bundle_repo_cred_acl,         key="b_rc_acl",
                help="r = read-only. Change to rw if write access is needed.")
            b_rc_secret_type = st.text_input("Secret Type", value=st.session_state.bundle_repo_cred_secret_type, key="b_rc_secret_type")

        st.divider()
        if st.button("Preview Repo Credential YAML ↓", key="b_rc_preview_bot", type="primary", use_container_width=True):
            st.session_state["b_rc_preview_clicked"] = True
            st.rerun()

        if st.session_state.pop("b_rc_preview_clicked", False):
            if not b_rc_name.strip():
                st.error("Credential Name is required.")
            else:
                cred_data = {
                    "name":         b_rc_name.strip(),
                    "version":      b_rc_version.strip(),
                    "description":  b_rc_desc.strip(),
                    "owner":        b_rc_owner.strip(),
                    "layer":        b_rc_layer.strip(),
                    "tags":         [t for t in st.session_state.bundle_repo_cred_tags if t.strip()],
                    "secret_type":  b_rc_secret_type.strip(),
                    "acl":          b_rc_acl.strip(),
                    "git_username": b_rc_username.strip(),
                    "git_password": b_rc_password.strip(),
                }
                _generated_yaml = generate_repo_cred_yaml(cred_data)
                # ── Persist all fields to session state ───────────────────
                st.session_state.bundle_repo_cred_yaml        = _generated_yaml
                st.session_state.bundle_repo_cred_name        = b_rc_name.strip()
                st.session_state.bundle_repo_cred_desc        = b_rc_desc.strip()
                st.session_state.bundle_repo_cred_owner       = b_rc_owner.strip()
                st.session_state.bundle_repo_cred_username    = b_rc_username.strip()
                st.session_state.bundle_repo_cred_password    = b_rc_password.strip()
                st.session_state.bundle_repo_cred_version     = b_rc_version.strip()
                st.session_state.bundle_repo_cred_layer       = b_rc_layer.strip()
                st.session_state.bundle_repo_cred_acl         = b_rc_acl.strip()
                st.session_state.bundle_repo_cred_secret_type = b_rc_secret_type.strip()
                # Also store into the matching lens secret so cadp_flow.py
                # can include it in the full CADP ZIP under secrets/
                for sec in st.session_state.get("bundle_lens_secrets", []):
                    if sec.get("name", "").strip() == b_rc_name.strip():
                        sec["cred_yaml"] = _generated_yaml
                        break
                else:
                    # No matching secret found — store in first secret as fallback
                    if st.session_state.get("bundle_lens_secrets"):
                        st.session_state.bundle_lens_secrets[0]["cred_yaml"] = _generated_yaml
                st.session_state.bundle_repo_cred_preview = True
                st.rerun()

    else:
        st.subheader("Repo Credential YAML Preview")
        st.code(st.session_state.bundle_repo_cred_yaml, language="yaml")
        st.info("💡 Note the credential name — you will enter it in Lens secrets in the next step.")
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("Edit Repo Credential"):
                st.session_state.bundle_repo_cred_preview = False; st.rerun()
        with pc2:
            if st.button("Continue to Lens", use_container_width=True, type="primary"):
                st.session_state.bundle_repo_cred_preview = False
                st.session_state.bundle_step = 5; st.rerun()