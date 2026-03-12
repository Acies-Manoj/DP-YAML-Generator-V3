import streamlit as st
from utils.generators import generate_user_groups_yaml
from utils.ui_utils import inline_docs_banner

_UG_SCOPES = ["meta", "data", "graphql", "jobs", "source"]


def render_step6():

    if not st.session_state.bundle_user_groups_preview:
        st.subheader("Step 6 — User Groups YAML")
        inline_docs_banner("user_groups") 
        st.caption("Define user groups for your semantic model. Each group controls API access and which users are included. This file will be placed at `semanticmodel/model/user_groups.yaml`.")

        # Add group button
        _ugh1, _ugh2 = st.columns([5, 1])
        with _ugh1: st.markdown("#### User Groups")
        with _ugh2:
            if st.button("➕ Add Group", key="b_add_ug"):
                st.session_state.bundle_user_groups.append(
                    {"name": "", "api_scopes": list(_UG_SCOPES), "includes": [""]}
                ); st.rerun()

        for gi, grp in enumerate(st.session_state.bundle_user_groups):
            with st.expander(f"Group: {grp['name'] or f'Group {gi+1}'}", expanded=True):
                gc1, gc2 = st.columns([3, 1])
                with gc1:
                    st.session_state.bundle_user_groups[gi]["name"] = st.text_input(
                        "Group Name", value=grp["name"],
                        key=f"ug_name_{gi}", placeholder="e.g. default, usa, india")
                with gc2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if len(st.session_state.bundle_user_groups) > 1:
                        if st.button("🗑️ Remove", key=f"ug_rm_{gi}"):
                            st.session_state.bundle_user_groups.pop(gi); st.rerun()

                st.markdown("**API Scopes**")
                _saved_scopes = grp.get("api_scopes", list(_UG_SCOPES))
                _scope_cols = st.columns(len(_UG_SCOPES))
                _sel_scopes = []
                for si, scope in enumerate(_UG_SCOPES):
                    checked = _scope_cols[si].checkbox(scope, value=(scope in _saved_scopes), key=f"ug_scope_{gi}_{si}")
                    if checked: _sel_scopes.append(scope)
                st.session_state.bundle_user_groups[gi]["api_scopes"] = _sel_scopes

                st.markdown("**Includes**")
                _is_wildcard = grp.get("includes") == ["*"] or grp.get("includes") == "*"
                _wildcard = st.checkbox(
                    'Include everyone (`"*"`)',
                    value=_is_wildcard,
                    key=f"ug_wild_{gi}",
                    help='Check this for the default group to include all users.')
                if _wildcard:
                    st.session_state.bundle_user_groups[gi]["includes"] = ["*"]
                    st.caption('includes: "*"  — all users allowed')
                else:
                    # Per-user ID list
                    _inc_list = grp.get("includes", [""])
                    if _inc_list == ["*"]: _inc_list = [""]
                    _inh1, _inh2 = st.columns([5, 1])
                    with _inh2:
                        if st.button("➕", key=f"ug_add_inc_{gi}"):
                            st.session_state.bundle_user_groups[gi]["includes"].append(""); st.rerun()
                    _updated_inc = []
                    for ii, uid in enumerate(_inc_list):
                        ic1, ic2 = st.columns([5, 1])
                        with ic1:
                            val = st.text_input(f"User ID {ii+1}", value=uid, key=f"ug_inc_{gi}_{ii}",
                                placeholder="e.g. users:id:johndoe")
                            _updated_inc.append(val)
                        with ic2:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if len(_inc_list) > 1 and st.button("X", key=f"ug_rm_inc_{gi}_{ii}"):
                                st.session_state.bundle_user_groups[gi]["includes"].pop(ii); st.rerun()
                    st.session_state.bundle_user_groups[gi]["includes"] = _updated_inc

        st.divider()
        if st.button("Preview User Groups YAML ↓", key="b_ug_preview_bot", type="primary", use_container_width=True):
            st.session_state["b_ug_preview_clicked"] = True
            st.rerun()

        if st.session_state.pop("b_ug_preview_clicked", False):
            st.session_state.bundle_user_groups_yaml = generate_user_groups_yaml(
                st.session_state.bundle_user_groups)
            st.session_state.bundle_user_groups_preview = True
            st.rerun()

    else:
        st.subheader("User Groups YAML Preview")
        st.code(st.session_state.bundle_user_groups_yaml, language="yaml")
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("Edit User Groups"):
                st.session_state.bundle_user_groups_preview = False; st.rerun()
        with pc2:
            if st.button("Continue to Review", use_container_width=True, type="primary"):
                st.session_state.bundle_user_groups_preview = False
                st.session_state.bundle_step = 7; st.rerun()

