import streamlit as st
from utils.generators import generate_repo_cred_yaml
from utils.history import save_entry

_GIT_TYPES = ["github", "bitbucket", "gitlab", "azure-devops"]


def render_ind_repo_cred():
    # ── init state ────────────────────────────────────────────────────────────
    for k, v in [
        ("ind_rc_preview",  False),
        ("ind_rc_yaml",     ""),
        ("ind_rc_name",     ""),
        ("ind_rc_desc",     ""),
        ("ind_rc_owner",    ""),
        ("ind_rc_tags",     [""]),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

    if not st.session_state.ind_rc_preview:
        st.subheader("Repo Credential YAML")
        st.caption(
            "Generate the instance-secret credential file for your Git repo. "
            "This is a standalone file — its name will be referenced in Lens secrets."
        )

        st.markdown("#### Credential Info")
        rc1, rc2 = st.columns(2)
        with rc1:
            b_rc_name = st.text_input(
                "Credential Name *", value=st.session_state.ind_rc_name,
                key="ind_rc_name_input", placeholder="e.g. bitbucket-cred",
            )
            b_rc_git_type = st.selectbox("Git Provider", _GIT_TYPES, key="ind_rc_git_type")
            b_rc_owner = st.text_input(
                "Owner", value=st.session_state.ind_rc_owner,
                key="ind_rc_owner_input", placeholder="e.g. your-dataos-username",
            )
        with rc2:
            b_rc_desc = st.text_area(
                "Description", value=st.session_state.ind_rc_desc,
                key="ind_rc_desc_input",
                placeholder="e.g. GitHub read secrets for repos.", height=100,
            )

        st.divider()
        st.markdown("#### Git Credentials")
        st.caption("These will be stored as `GITSYNC_USERNAME` and `GITSYNC_PASSWORD` in the secret.")
        cred1, cred2 = st.columns(2)
        with cred1:
            b_rc_username = st.text_input(
                "Git Username", key="ind_rc_username", placeholder="e.g. your-git-username"
            )
        with cred2:
            b_rc_password = st.text_input(
                "Git Token / Password", key="ind_rc_password",
                type="password", placeholder="e.g. your-personal-access-token",
            )

        st.divider()
        _rth1, _rth2 = st.columns([5, 1])
        with _rth1:
            st.markdown("**Tags**")
        with _rth2:
            if st.button("➕ Add", key="ind_rc_add_tag"):
                st.session_state.ind_rc_tags.append("")
                st.rerun()

        _updated_rc_tags = []
        for i, tag in enumerate(st.session_state.ind_rc_tags):
            tc1, tc2 = st.columns([5, 1])
            with tc1:
                val = st.text_input(f"Tag {i+1}", value=tag, key=f"ind_rc_tag_{i}")
                _updated_rc_tags.append(val)
            with tc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("X", key=f"ind_rc_rm_tag_{i}"):
                    st.session_state.ind_rc_tags.pop(i)
                    st.rerun()
        st.session_state.ind_rc_tags = _updated_rc_tags

        with st.expander("Advanced / Default Settings", expanded=False):
            st.caption("Pre-filled with standard defaults. Change only if needed.")
            adv1, adv2, adv3 = st.columns(3)
            with adv1:
                b_rc_version = st.text_input("Version", value="v1", key="ind_rc_version")
            with adv2:
                b_rc_layer = st.text_input("Layer", value="user", key="ind_rc_layer")
            with adv3:
                b_rc_acl = st.text_input(
                    "ACL", value="r", key="ind_rc_acl",
                    help="r = read-only. Change to rw if write access is needed.",
                )
            b_rc_secret_type = st.text_input("Secret Type", value="key-value", key="ind_rc_secret_type")

        st.divider()
        if st.button("Preview Repo Credential YAML ↓", key="ind_rc_preview_btn",
                     type="primary", use_container_width=True):
            st.session_state["ind_rc_preview_clicked"] = True
            st.rerun()

        if st.session_state.pop("ind_rc_preview_clicked", False):
            if not b_rc_name.strip():
                st.error("Credential Name is required.")
            else:
                cred_data = {
                    "name":         b_rc_name.strip(),
                    "version":      st.session_state.get("ind_rc_version", "v1"),
                    "description":  b_rc_desc.strip(),
                    "owner":        b_rc_owner.strip(),
                    "layer":        st.session_state.get("ind_rc_layer", "user"),
                    "tags":         [t for t in st.session_state.ind_rc_tags if t.strip()],
                    "secret_type":  st.session_state.get("ind_rc_secret_type", "key-value"),
                    "acl":          st.session_state.get("ind_rc_acl", "r"),
                    "git_username": b_rc_username.strip(),
                    "git_password": b_rc_password.strip(),
                }
                st.session_state.ind_rc_yaml    = generate_repo_cred_yaml(cred_data)
                save_entry("Specific", "repo_cred", f"{b_rc_name.strip()}.yaml", st.session_state.ind_rc_yaml)
                st.session_state.ind_rc_name    = b_rc_name.strip()
                st.session_state.ind_rc_desc    = b_rc_desc.strip()
                st.session_state.ind_rc_owner   = b_rc_owner.strip()
                st.session_state.ind_rc_preview = True
                st.rerun()

    else:
        st.subheader("Repo Credential YAML Preview")
        st.code(st.session_state.ind_rc_yaml, language="yaml")
        st.info("Note the credential name — you will reference it in Lens secrets.")

        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("← Edit Repo Credential", key="ind_rc_edit"):
                st.session_state.ind_rc_preview = False
                st.rerun()
        with pc2:
            fname = f"{st.session_state.ind_rc_name or 'repo-cred'}.yaml"
            st.download_button(
                f"⬇️ Download {fname}",
                data=st.session_state.ind_rc_yaml,
                file_name=fname,
                mime="text/yaml",
                use_container_width=True,
                type="primary",
                key="ind_rc_dl",
            )