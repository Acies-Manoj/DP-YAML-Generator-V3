import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.examples import (
    EXAMPLE_SECRET_R, EXAMPLE_SECRET_RW, EXAMPLE_DEPOT, EXAMPLE_SCANNER,
    show_example,
)
from utils.history import save_entry, save_zip_entry
from utils.depot_generators import (
    generate_secret_r_yaml,
    generate_secret_rw_yaml,
    generate_depot_yaml,
    generate_scanner_yaml,
)

st.set_page_config(page_title="Depot Builder", layout="wide")
from utils.ui_utils import load_global_css, render_sidebar, floating_docs
load_global_css()
render_sidebar()
floating_docs("depot")

st.markdown("""
<style>
.stButton>button {
    width: 100%;
    height: 45px;
    border-radius: 8px;
    font-size: 15px;
}
.info-pill {
    display: inline-block;
    background-color: #1f2937;
    color: #9ca3af;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 13px;
    margin: 2px 4px 2px 0;

}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# BACK NAVIGATION
# ─────────────────────────────────────────────────────────────────────────────
origin = st.session_state.get("depot_origin", "cadp")

# ─────────────────────────────────────────────────────────────────────────────
# STATE INITIALISATION
# ─────────────────────────────────────────────────────────────────────────────
DEPOT_KEYS_TO_CLEAR = [
    "depot_step", "depot_source",
    "depot_base_name", "depot_username", "depot_password",
    "depot_layer_secret", "depot_desc_r", "depot_desc_rw",
    "depot_description", "depot_tags", "depot_warehouse",
    "depot_url", "depot_database", "depot_account",
    "depot_layer_depot", "depot_external",
    "depot_workflow_name", "depot_wf_description", "depot_dag_description",
    "depot_scanner_tags", "depot_schemas",
    "depot_stack", "depot_compute", "depot_run_as_user",
    "depot_include_tables", "depot_include_views",
    "depot_yaml_r", "depot_yaml_rw", "depot_yaml_depot", "depot_yaml_scanner",
]

DEPOT_CRED_KEYS = {"depot_username", "depot_password", "depot_account", "depot_warehouse", "depot_url", "depot_database"}
DEPOT_YAML_KEYS = {"depot_yaml_r", "depot_yaml_rw", "depot_yaml_depot", "depot_yaml_scanner", "depot_base_name"}

def clear_depot_state(keep_creds=False):
    keep = set()
    if keep_creds:
        keep |= DEPOT_CRED_KEYS | DEPOT_YAML_KEYS
    for k in DEPOT_KEYS_TO_CLEAR:
        if k in keep:
            continue
        st.session_state.pop(k, None)

for k, v in [
    ("depot_step",           0),
    ("depot_source",         None),
    ("depot_tags",           ["snowflake depot", "user data"]),
    ("depot_scanner_tags",   ["snowflake-scanner"]),
    ("depot_schemas",        [""]),
]:
    if k not in st.session_state:
        st.session_state[k] = v

step = st.session_state.depot_step
source = st.session_state.get("depot_source")
specific_file = st.session_state.get("depot_specific_file")

STEP_LABELS = [
    "1. Credentials & Naming",
    "2. Depot Configuration",
    "3. Scanner Configuration",
    "4. Review & Download",
]

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
source_label = f" — {source}" if source else ""
st.title(f"Depot Builder{source_label}")

if step > 0:
    label = STEP_LABELS[step - 1] if step <= 4 else "Complete"
    st.progress((step - 1) / 4, text=f"Step {step} of 4 — {label}")

def _back_to_origin():
    keep = origin in ("cadp_full", "sadp_full")
    clear_depot_state(keep_creds=keep)
    if origin == "sadp_full":
        st.switch_page("pages/sadp_flow.py")
    elif origin == "cadp_full":
        st.switch_page("pages/cadp_flow.py")
    elif origin == "sadp":
        st.switch_page("app.py")
    elif origin == "specific":
        st.switch_page("app.py")
    else:
        st.switch_page("pages/1_CADP.py")

nav_l, _, nav_r = st.columns([1, 4, 1.5])
with nav_l:
    if step == 0:
        if st.button("← Back"):
            _back_to_origin()
    elif step == 1:
        if st.button("← Back"):
            st.session_state.depot_step = 0
            st.rerun()
    elif step > 1:
        if st.button("← Back"):
            st.session_state.depot_step -= 1
            st.rerun()
with nav_r:
    if st.button("✖ Cancel / Start Over"):
        _back_to_origin()

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# INDIVIDUAL MODE
# ══════════════════════════════════════════════════════════════════════════════
if origin == "specific" and specific_file:

    FILE_LABELS = {
        "secret_r":  "Instance Secret (Read)",
        "secret_rw": "Instance Secret (Read-Write)",
        "depot":     "Depot",
        "scanner":   "Depot Scanner",
    }
    st.subheader(FILE_LABELS.get(specific_file, specific_file))

    # ── Individual: Secret R ──────────────────────────────────────────────────
    if specific_file == "secret_r":
        show_example(st, "Instance Secret R", EXAMPLE_SECRET_R)
        with st.expander("⚙️ Advanced Options"):
            adv1, adv2 = st.columns(2)
            with adv1:
                st.text_input("Layer", value="user", key="ind_r_layer")
            with adv2:
                st.text_input("Description", placeholder="Auto-generated if blank", key="ind_r_desc")
        with st.form("ind_secret_r_form"):
            st.markdown("#### Credentials")
            c1, c2 = st.columns(2)
            with c1:
                base_name = st.text_input("Secret Name *", placeholder="e.g. depot-name-r",
                    help="Convention: {depot-name}-r")
            with c2:
                username = st.text_input("Username *", placeholder="e.g. snowflake_user")
            password = st.text_input("Password *", type="password")
            st.markdown(" ")
            sub = st.form_submit_button("Generate YAML", use_container_width=True)
        if sub:
            if not base_name.strip():
                st.error("Secret Name is required.")
            elif not username.strip() or not password.strip():
                st.error("Username and Password are required.")
            else:
                layer = st.session_state.get("ind_r_layer", "user") or "user"
                desc  = st.session_state.get("ind_r_desc", "")
                yaml_out = generate_secret_r_yaml({
                    "name": base_name.strip(), "layer": layer.strip(),
                    "username": username.strip(), "password": password,
                    "desc_r": desc.strip() or f"read instance-secret for {base_name.strip()} snowflake depot",
                    "desc_rw": "",
                })
                st.code(yaml_out, language="yaml")
                save_entry("Specific", "secret_r", f"{base_name.strip()}.yml", yaml_out)
                st.download_button("Download YAML", data=yaml_out,
                    file_name=f"{base_name.strip()}.yml", mime="text/yaml",
                    use_container_width=True)

    # ── Individual: Secret RW ─────────────────────────────────────────────────
    elif specific_file == "secret_rw":
        show_example(st, "Instance Secret RW", EXAMPLE_SECRET_RW)
        with st.expander("⚙️ Advanced Options"):
            adv1, adv2 = st.columns(2)
            with adv1:
                st.text_input("Layer", value="user", key="ind_rw_layer")
            with adv2:
                st.text_input("Description", placeholder="Auto-generated if blank", key="ind_rw_desc")
        with st.form("ind_secret_rw_form"):
            st.markdown("#### Credentials")
            c1, c2 = st.columns(2)
            with c1:
                base_name = st.text_input("Secret Name *", placeholder="e.g. depot-name-rw",
                    help="Convention: {depot-name}-rw")
            with c2:
                username = st.text_input("Username *", placeholder="e.g. snowflake_user")
            password = st.text_input("Password *", type="password")
            st.markdown(" ")
            sub = st.form_submit_button("Generate YAML", use_container_width=True)
        if sub:
            if not base_name.strip():
                st.error("Secret Name is required.")
            elif not username.strip() or not password.strip():
                st.error("Username and Password are required.")
            else:
                layer = st.session_state.get("ind_rw_layer", "user") or "user"
                desc  = st.session_state.get("ind_rw_desc", "")
                yaml_out = generate_secret_rw_yaml({
                    "name": base_name.strip(), "layer": layer.strip(),
                    "username": username.strip(), "password": password,
                    "desc_r": "",
                    "desc_rw": desc.strip() or f"read-write instance-secret for {base_name.strip()} snowflake depot",
                })
                st.code(yaml_out, language="yaml")
                save_entry("Specific", "secret_rw", f"{base_name.strip()}.yml", yaml_out)
                st.download_button("Download YAML", data=yaml_out,
                    file_name=f"{base_name.strip()}.yml", mime="text/yaml",
                    use_container_width=True)

    # ── Individual: Depot ─────────────────────────────────────────────────────
    elif specific_file == "depot":
        show_example(st, "Depot YAML", EXAMPLE_DEPOT)

        if "depot_tags" not in st.session_state:
            st.session_state.depot_tags = ["snowflake depot", "user data"]

        with st.expander("⚙️ Advanced Options"):
            adv1, adv2 = st.columns(2)
            with adv1:
                st.text_input("Layer", value="user", key="ind_dep_layer")
            with adv2:
                st.checkbox("External", value=True, key="ind_dep_external",
                    help="Always true for Snowflake.")

        with st.form("ind_depot_form"):
            st.markdown("#### Metadata")
            m1, m2 = st.columns(2)
            with m1:
                dep_name = st.text_input("Depot Name *", placeholder="e.g. sampleobs")
            with m2:
                description = st.text_input("Description *",
                    value="Depot to fetch data from Snowflake datasource")

            st.markdown("#### Tags")
            _th1, _th2 = st.columns([5, 1])
            with _th2:
                if st.form_submit_button("➕ Add", key="ind_depot_add_tag"):
                    st.session_state.depot_tags.append(""); st.rerun()
            updated_tags = []
            for i, tag in enumerate(st.session_state.depot_tags):
                tc1, tc2 = st.columns([5, 1])
                with tc1:
                    val = st.text_input(f"Tag {i+1}", value=tag, key=f"ind_dtag_{i}",
                        placeholder="e.g. snowflake depot", label_visibility="collapsed")
                    updated_tags.append(val)
                with tc2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"ind_rm_dtag_{i}"):
                        st.session_state.depot_tags.pop(i); st.rerun()

            st.divider()
            st.markdown("#### Secrets")
            st.caption("Enter the base name — `-r` and `-rw` suffixes are added automatically.")
            secret_base = st.text_input("Secret Base Name *", placeholder="e.g. sampleobs")

            st.divider()
            st.markdown("#### Snowflake Connection")
            sf1, sf2 = st.columns(2)
            with sf1:
                warehouse = st.text_input("Warehouse *", placeholder="e.g. COMPUTE_WH")
                url = st.text_input("URL *", placeholder="e.g. myorg.snowflakecomputing.com")
            with sf2:
                database = st.text_input("Database *", placeholder="e.g. PROD_DB")
                account = st.text_input("Account *", placeholder="e.g. myorg-myaccount")
            st.markdown(" ")
            sub = st.form_submit_button("Generate YAML", use_container_width=True)

        st.session_state.depot_tags = updated_tags

        if sub:
            errors = []
            if not dep_name.strip(): errors.append("Depot Name is required.")
            if not description.strip(): errors.append("Description is required.")
            if not secret_base.strip(): errors.append("Secret Base Name is required.")
            if not warehouse.strip(): errors.append("Warehouse is required.")
            if not url.strip(): errors.append("URL is required.")
            if not database.strip(): errors.append("Database is required.")
            if not account.strip(): errors.append("Account is required.")
            if errors:
                for e in errors: st.error(e)
            else:
                layer    = st.session_state.get("ind_dep_layer", "user") or "user"
                external = st.session_state.get("ind_dep_external", True)
                yaml_out = generate_depot_yaml({
                    "name": dep_name.strip(),
                    "description": description.strip(),
                    "tags": [t for t in updated_tags if t.strip()],
                    "layer": layer.strip(),
                    "external": external,
                    "warehouse": warehouse.strip(),
                    "url": url.strip(),
                    "database": database.strip(),
                    "account": account.strip(),
                    "secret_base": secret_base.strip(),
                })
                st.code(yaml_out, language="yaml")
                save_entry("Specific", "depot", f"{dep_name.strip()}-depot.yml", yaml_out)
                st.download_button("Download YAML", data=yaml_out,
                    file_name=f"{dep_name.strip()}-depot.yml", mime="text/yaml",
                    use_container_width=True)

    # ── Individual: Scanner ───────────────────────────────────────────────────
    elif specific_file == "scanner":
        show_example(st, "Scanner YAML", EXAMPLE_SCANNER)

        if "depot_scanner_tags" not in st.session_state:
            st.session_state.depot_scanner_tags = ["snowflake-scanner"]
        if "depot_schemas" not in st.session_state:
            st.session_state.depot_schemas = [""]

        with st.expander("⚙️ Advanced Options"):
            adv1, adv2 = st.columns(2)
            with adv1:
                st.text_input("Workflow Description",
                    value="Workflow to scan Snowflake database tables and register metadata in Metis.",
                    key="ind_sc_wf_desc")
                st.text_input("Stack", value="scanner:2.0", key="ind_sc_stack")
                st.text_input("Compute", value="runnable-default", key="ind_sc_compute")
            with adv2:
                st.text_input("DAG Description",
                    value="Scans schemas from Snowflake database and registers metadata to Metis.",
                    key="ind_sc_dag_desc")
                st.text_input("Run As User", value="metis", key="ind_sc_run_as")
            inc1, inc2 = st.columns(2)
            with inc1: st.checkbox("Include Tables", value=True, key="ind_sc_inc_tables")
            with inc2: st.checkbox("Include Views",  value=True, key="ind_sc_inc_views")

        with st.form("ind_scanner_form"):
            st.markdown("#### Workflow Identity")
            w1, w2 = st.columns(2)
            with w1:
                workflow_name = st.text_input("Workflow Name *",
                    placeholder="e.g. scan-sampleobs",
                    help="Convention: scan-{depot-name}")
                depot_ref = st.text_input("Depot Name *",
                    placeholder="e.g. sampleobs")

            st.markdown("#### Scanner Tags")
            _scth1, _scth2 = st.columns([5, 1])
            with _scth2:
                if st.form_submit_button("➕ Add", key="ind_add_stag"):
                    st.session_state.depot_scanner_tags.append(""); st.rerun()
            updated_scanner_tags = []
            for i, tag in enumerate(st.session_state.depot_scanner_tags):
                stc1, stc2 = st.columns([5, 1])
                with stc1:
                    val = st.text_input(f"Tag {i+1}", value=tag, key=f"ind_stag_{i}",
                        label_visibility="collapsed")
                    updated_scanner_tags.append(val)
                with stc2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"ind_rm_stag_{i}"):
                        st.session_state.depot_scanner_tags.pop(i); st.rerun()

            st.divider()
            st.markdown("#### Schema Filter")
            st.caption("Enter schema names to include — `^...$` anchors are added automatically.")
            _sch1, _sch2 = st.columns([5, 1])
            with _sch2:
                if st.form_submit_button("➕ Add", key="ind_add_schema"):
                    st.session_state.depot_schemas.append(""); st.rerun()
            updated_schemas = []
            for i, schema in enumerate(st.session_state.depot_schemas):
                sc1, sc2 = st.columns([5, 1])
                with sc1:
                    val = st.text_input(f"Schema {i+1}", value=schema, key=f"ind_schema_{i}",
                        placeholder="e.g. SAMPLE_MANOJ", label_visibility="collapsed")
                    updated_schemas.append(val)
                with sc2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("❌", key=f"ind_rm_schema_{i}"):
                        st.session_state.depot_schemas.pop(i); st.rerun()

            filled = [s.strip() for s in updated_schemas if s.strip()]
            if filled:
                st.caption("Will render as: " + "  |  ".join(f"`^{s}$`" for s in filled))

            st.markdown(" ")
            sub = st.form_submit_button("Generate YAML", use_container_width=True)

        st.session_state.depot_scanner_tags = updated_scanner_tags
        st.session_state.depot_schemas = updated_schemas

        if sub:
            if not workflow_name.strip():
                st.error("Workflow Name is required.")
            elif not depot_ref.strip():
                st.error("Depot Name is required.")
            else:
                yaml_out = generate_scanner_yaml({
                    "workflow_name":   workflow_name.strip(),
                    "description":     st.session_state.get("ind_sc_wf_desc", ""),
                    "dag_description": st.session_state.get("ind_sc_dag_desc", ""),
                    "tags":            [t for t in updated_scanner_tags if t.strip()],
                    "depot_name":      depot_ref.strip(),
                    "schemas":         [s for s in updated_schemas if s.strip()],
                    "stack":           st.session_state.get("ind_sc_stack", "scanner:2.0") or "scanner:2.0",
                    "compute":         st.session_state.get("ind_sc_compute", "runnable-default") or "runnable-default",
                    "run_as_user":     st.session_state.get("ind_sc_run_as", "metis") or "metis",
                    "include_tables":  st.session_state.get("ind_sc_inc_tables", True),
                    "include_views":   st.session_state.get("ind_sc_inc_views", True),
                })
                st.code(yaml_out, language="yaml")
                save_entry("Specific", "scanner", f"{workflow_name.strip()}.yml", yaml_out)
                st.download_button("Download YAML", data=yaml_out,
                    file_name=f"{workflow_name.strip()}.yml", mime="text/yaml",
                    use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 0 — SOURCE SELECTION
# ══════════════════════════════════════════════════════════════════════════════
elif step == 0:
    st.subheader("Select a Source System")
    st.caption("Choose the source you want to connect to DataOS. Each source has its own depot template.")
    st.markdown(" ")

    SOURCES = [
        {"key": "Snowflake",  "desc": "Cloud data warehouse by Snowflake Inc.", "available": True},
        {"key": "PostgreSQL", "desc": "Open-source relational database.",        "available": False},
    ]
    for row_start in range(0, len(SOURCES), 4):
        cols = st.columns(4)
        for col, src in zip(cols, SOURCES[row_start:row_start + 4]):
            with col:
                st.markdown(f"""
                    <div style="padding:20px;border-radius:12px;background-color:#111827;
                                color:white;height:140px;margin-bottom:8px;">
                        <h4 style="margin:0 0 6px 0">{src['key']}</h4>
                        <p style="font-size:13px;color:#9ca3af;margin:0">{src['desc']}</p>
                    </div>
                """, unsafe_allow_html=True)
                if src["available"]:
                    if st.button(f"Select {src['key']}", use_container_width=True, key=f"src_{src['key']}"):
                        st.session_state.depot_source = src["key"]
                        st.session_state.depot_step   = 1
                        st.rerun()
                else:
                    st.button("Coming Soon", use_container_width=True,
                              key=f"src_{src['key']}", disabled=True)
        st.markdown(" ")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — CREDENTIALS & NAMING
# ══════════════════════════════════════════════════════════════════════════════
elif step == 1:
    st.subheader("Step 1 — Credentials & Naming")
    c_ex1, c_ex2 = st.columns([1, 1])
    with c_ex1:
        show_example(st, "Instance Secret R", EXAMPLE_SECRET_R)
    with c_ex2:
        show_example(st, "Instance Secret RW", EXAMPLE_SECRET_RW)
    st.caption(
        "The name you enter will be the depot name. "
        "Secrets will be named `{name}-r` and `{name}-rw`."
    )
    st.markdown(" ")

    # Advanced options — outside form so expander works
    with st.expander("⚙️ Advanced Options"):
        adv1, adv2 = st.columns(2)
        with adv1:
            st.text_input("Layer", value=st.session_state.get("depot_layer_secret", "user"),
                key="s1_adv_layer")
        with adv2:
            base_preview = st.session_state.get("depot_base_name", "{name}")
            st.text_input("Secret R Description",
                value=st.session_state.get("depot_desc_r", f"read instance-secret for {base_preview} snowflake depot"),
                key="s1_adv_desc_r")
            st.text_input("Secret RW Description",
                value=st.session_state.get("depot_desc_rw", f"read-write instance-secret for {base_preview} snowflake depot"),
                key="s1_adv_desc_rw")

    with st.form("depot_step1_form"):
        st.markdown("#### Secret Names")
        c1, c2 = st.columns(2)
        with c1:
            base_name = st.text_input(
                "Instance Secret Name *",
                value=st.session_state.get("depot_base_name", ""),
                placeholder="e.g. depot-name",
                help="Depot name — secrets get -r and -rw suffixes.",
            )
        with c2:
            username = st.text_input(
                "Username *",
                value=st.session_state.get("depot_username", ""),
                placeholder="e.g. snowflake_user",
            )

        password = st.text_input(
            "Password *",
            value=st.session_state.get("depot_password", ""),
            type="password",
            placeholder="Snowflake password",
        )

        st.markdown(" ")
        submit1 = st.form_submit_button("Next →", use_container_width=True)

    if submit1:
        if not base_name.strip():
            st.error("Base Name is required.")
        elif not username.strip():
            st.error("Username is required.")
        elif not password.strip():
            st.error("Password is required.")
        else:
            layer   = st.session_state.get("s1_adv_layer", "user") or "user"
            desc_r  = st.session_state.get("s1_adv_desc_r", "") or f"read instance-secret for {base_name.strip()} snowflake depot"
            desc_rw = st.session_state.get("s1_adv_desc_rw", "") or f"read-write instance-secret for {base_name.strip()} snowflake depot"

            st.session_state.depot_base_name    = base_name.strip()
            st.session_state.depot_layer_secret = layer
            st.session_state.depot_username     = username.strip()
            st.session_state.depot_password     = password
            st.session_state.depot_desc_r       = desc_r
            st.session_state.depot_desc_rw      = desc_rw

            payload = {
                "name":     base_name.strip(),
                "layer":    layer,
                "username": username.strip(),
                "password": password,
                "desc_r":   desc_r,
                "desc_rw":  desc_rw,
            }
            st.session_state.depot_yaml_r  = generate_secret_r_yaml(payload)
            st.session_state.depot_yaml_rw = generate_secret_rw_yaml(payload)
            st.session_state.depot_step    = 2
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — DEPOT CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
elif step == 2:
    name = st.session_state.depot_base_name

    st.subheader("Step 2 — Depot Configuration")
    show_example(st, "Depot YAML", EXAMPLE_DEPOT)
    st.caption("Configure the Snowflake connection. Secret references are auto-filled from Step 1.")
    st.markdown(" ")

    st.markdown("**Secret references (auto-filled from Step 1)**")
    st.markdown(
        f'<span class="info-pill">Secret R → <strong>{name}-r</strong></span>'
        f'<span class="info-pill">Secret RW → <strong>{name}-rw</strong></span>',
        unsafe_allow_html=True,
    )
    st.markdown(" ")

    # Advanced options — outside form
    with st.expander("⚙️ Advanced Options"):
        adv1, adv2, adv3 = st.columns(3)
        with adv1:
            st.text_input("Version", value=st.session_state.get("depot_version", "v2alpha"), key="s2_adv_version")
            st.text_input("Type", value=st.session_state.get("depot_type", "depot"), key="s2_adv_type")
        with adv2:
            st.text_input("Layer", value=st.session_state.get("depot_layer_depot", "user"), key="s2_adv_layer")
        with adv3:
            st.checkbox("External", value=st.session_state.get("depot_external", True), key="s2_adv_external", help="Always true for Snowflake.")

    # Tag management outside form
    tag_col1, tag_col2 = st.columns([6, 1])
    with tag_col1:
        st.markdown("**Tags** — click ➕ to add")
    with tag_col2:
        if st.button("➕ Tag", key="depot_add_tag"):
            st.session_state.depot_tags.append("")
            st.rerun()

    with st.form("depot_step2_form"):
        st.markdown("#### Metadata")
        description = st.text_input(
            "Description *",
            value=st.session_state.get("depot_description", "Depot to fetch data from Snowflake datasource"),
            placeholder="e.g. Depot to fetch data from Snowflake datasource",
        )

        st.markdown("**Tags**")
        updated_tags = []
        for i, tag in enumerate(st.session_state.depot_tags):
            tc1, tc2 = st.columns([5, 1])
            with tc1:
                val = st.text_input(
                    f"Tag {i+1}", value=tag, key=f"depot_tag_{i}",
                    placeholder="e.g. snowflake depot", label_visibility="collapsed",
                )
                updated_tags.append(val)
            with tc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("❌", key=f"depot_rm_tag_{i}"):
                    st.session_state.depot_tags.pop(i)
                    st.rerun()

        st.divider()
        st.markdown("#### ❄️ Snowflake Connection")
        sf1, sf2 = st.columns(2)
        with sf1:
            warehouse = st.text_input("Warehouse *",
                value=st.session_state.get("depot_warehouse", ""), placeholder="e.g. COMPUTE_WH")
            url = st.text_input("URL *",
                value=st.session_state.get("depot_url", ""),
                placeholder="e.g. myorg.snowflakecomputing.com")
        with sf2:
            database = st.text_input("Database *",
                value=st.session_state.get("depot_database", ""), placeholder="e.g. PROD_DB")
            account = st.text_input("Account *",
                value=st.session_state.get("depot_account", ""), placeholder="e.g. myorg-myaccount")

        st.markdown(" ")
        submit2 = st.form_submit_button("Next →", use_container_width=True)

    st.session_state.depot_tags = updated_tags

    if submit2:
        errors = []
        if not description.strip(): errors.append("Description is required.")
        if not warehouse.strip():   errors.append("Warehouse is required.")
        if not url.strip():         errors.append("URL is required.")
        if not database.strip():    errors.append("Database is required.")
        if not account.strip():     errors.append("Account is required.")
        if errors:
            for e in errors: st.error(e)
        else:
            layer_depot = st.session_state.get("s2_adv_layer", "user") or "user"
            external    = st.session_state.get("s2_adv_external", True)
            version     = st.session_state.get("s2_adv_version", "v2alpha") or "v2alpha"
            dtype       = st.session_state.get("s2_adv_type", "depot") or "depot"

            st.session_state.depot_description  = description.strip()
            st.session_state.depot_layer_depot  = layer_depot
            st.session_state.depot_external     = external
            st.session_state.depot_version      = version
            st.session_state.depot_type         = dtype
            st.session_state.depot_warehouse    = warehouse.strip()
            st.session_state.depot_url          = url.strip()
            st.session_state.depot_database     = database.strip()
            st.session_state.depot_account      = account.strip()

            st.session_state.depot_yaml_depot = generate_depot_yaml({
                "name":        name,
                "version":     version,
                "type":        dtype,
                "description": description.strip(),
                "tags":        [t for t in updated_tags if t.strip()],
                "layer":       layer_depot,
                "external":    external,
                "warehouse":   warehouse.strip(),
                "url":         url.strip(),
                "database":    database.strip(),
                "account":     account.strip(),
            })
            st.session_state.depot_step = 3
            st.rerun()
            st.session_state.depot_step = 3
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — SCANNER CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
elif step == 3:
    name = st.session_state.depot_base_name

    st.subheader("🔍 Step 3 — Scanner Configuration")
    show_example(st, "Scanner YAML", EXAMPLE_SCANNER)
    st.caption("Configure the metadata scanner workflow for this Snowflake depot.")
    st.markdown(" ")

    st.markdown("**Depot reference (auto-filled)**")
    st.markdown(
        f'<span class="info-pill">dataos://<strong>{name}</strong></span>',
        unsafe_allow_html=True,
    )
    st.markdown(" ")

    # Advanced options — outside form
    with st.expander("⚙️ Advanced Options"):
        adv1, adv2, adv3 = st.columns(3)
        with adv1:
            st.text_input("Version", value=st.session_state.get("scanner_version", "v1"), key="s3_adv_version")
            st.text_input("Type", value=st.session_state.get("scanner_type", "workflow"), key="s3_adv_type")
            st.text_input("Stack", value=st.session_state.get("depot_stack", "scanner:2.0"), key="s3_adv_stack")
            st.text_input("Compute", value=st.session_state.get("depot_compute", "runnable-default"), key="s3_adv_compute")
        with adv2:
            st.text_input("Workflow Description",
                value=st.session_state.get("depot_wf_description", "Workflow to scan Snowflake database tables and register metadata in Metis."),
                key="s3_adv_wf_desc")
            st.text_input("DAG Step Description",
                value=st.session_state.get("depot_dag_description", "Scans schemas from Snowflake database and registers metadata to Metis."),
                key="s3_adv_dag_desc")
        with adv3:
            st.text_input("Run As User", value=st.session_state.get("depot_run_as_user", "metis"), key="s3_adv_run_as")
        inc1, inc2 = st.columns(2)
        with inc1:
            st.checkbox("Include Tables", value=st.session_state.get("depot_include_tables", True), key="s3_adv_inc_tables")
        with inc2:
            st.checkbox("Include Views", value=st.session_state.get("depot_include_views", True), key="s3_adv_inc_views")

    # Add / remove buttons outside form
    btn1, btn2 = st.columns(2)
    with btn1:
        if st.button("➕ Scanner Tag", key="depot_add_stag"):
            st.session_state.depot_scanner_tags.append("")
            st.rerun()
    with btn2:
        if st.button("➕ Schema", key="depot_add_schema"):
            st.session_state.depot_schemas.append("")
            st.rerun()

    with st.form("depot_step3_form"):
        st.markdown("#### Workflow Identity")
        default_wf_name = f"{name}-snowflake-scanner"
        workflow_name = st.text_input(
            "Workflow Name *",
            value=st.session_state.get("depot_workflow_name", default_wf_name),
        )

        st.markdown("**Scanner Tags**")
        updated_scanner_tags = []
        for i, tag in enumerate(st.session_state.depot_scanner_tags):
            stc1, stc2 = st.columns([5, 1])
            with stc1:
                val = st.text_input(
                    f"STag {i+1}", value=tag, key=f"depot_stag_{i}",
                    placeholder="e.g. snowflake-scanner", label_visibility="collapsed",
                )
                updated_scanner_tags.append(val)
            with stc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("❌", key=f"depot_rm_stag_{i}"):
                    st.session_state.depot_scanner_tags.pop(i)
                    st.rerun()

        st.divider()
        st.markdown("#### Schema Filter")
        st.caption("Enter schema names to include — `^...$` anchors are added automatically.")
        updated_schemas = []
        for i, schema in enumerate(st.session_state.depot_schemas):
            sc1, sc2 = st.columns([5, 1])
            with sc1:
                val = st.text_input(
                    f"Schema {i+1}", value=schema, key=f"depot_schema_{i}",
                    placeholder="e.g. SAMPLE_MANOJ", label_visibility="collapsed",
                )
                updated_schemas.append(val)
            with sc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("❌", key=f"depot_rm_schema_{i}"):
                    st.session_state.depot_schemas.pop(i)
                    st.rerun()

        filled = [s.strip() for s in updated_schemas if s.strip()]
        if filled:
            st.caption("Will render as: " + "  |  ".join(f"`^{s}$`" for s in filled))

        st.markdown(" ")
        submit3 = st.form_submit_button("Next →", use_container_width=True)

    st.session_state.depot_scanner_tags = updated_scanner_tags
    st.session_state.depot_schemas      = updated_schemas

    if submit3:
        if not workflow_name.strip():
            st.error("Workflow Name is required.")
        else:
            wf_desc  = st.session_state.get("s3_adv_wf_desc",  "Workflow to scan Snowflake database tables and register metadata in Metis.")
            dag_desc = st.session_state.get("s3_adv_dag_desc", "Scans schemas from Snowflake database and registers metadata to Metis.")
            stack    = st.session_state.get("s3_adv_stack",    "scanner:2.0") or "scanner:2.0"
            compute  = st.session_state.get("s3_adv_compute",  "runnable-default") or "runnable-default"
            run_as   = st.session_state.get("s3_adv_run_as",   "metis") or "metis"
            version  = st.session_state.get("s3_adv_version",  "v1") or "v1"
            dtype    = st.session_state.get("s3_adv_type",     "workflow") or "workflow"
            inc_tbl  = st.session_state.get("s3_adv_inc_tables", True)
            inc_vw   = st.session_state.get("s3_adv_inc_views",  True)

            st.session_state.depot_workflow_name   = workflow_name.strip()
            st.session_state.depot_wf_description  = wf_desc
            st.session_state.depot_dag_description = dag_desc
            st.session_state.depot_stack           = stack
            st.session_state.depot_compute         = compute
            st.session_state.depot_run_as_user     = run_as
            st.session_state.scanner_version       = version
            st.session_state.scanner_type          = dtype
            st.session_state.depot_include_tables  = inc_tbl
            st.session_state.depot_include_views   = inc_vw

            st.session_state.depot_yaml_scanner = generate_scanner_yaml({
                "workflow_name":   workflow_name.strip(),
                "version":         version,
                "type":            dtype,
                "description":     wf_desc,
                "dag_description": dag_desc,
                "tags":            [t for t in updated_scanner_tags if t.strip()],
                "depot_name":      name,
                "schemas":         [s for s in updated_schemas if s.strip()],
                "stack":           stack,
                "compute":         compute,
                "run_as_user":     run_as,
                "include_tables":  inc_tbl,
                "include_views":   inc_vw,
            })
            st.session_state.depot_step = 4
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — REVIEW & DOWNLOAD ALL
# ══════════════════════════════════════════════════════════════════════════════
elif step == 4:
    name = st.session_state.depot_base_name

    st.subheader("Step 4 — Review All Files & Download")
    st.success(f"All 4 files generated for depot **{name}**. Review and download below.")
    st.markdown(" ")

    yaml_r       = st.session_state.get("depot_yaml_r", "")
    yaml_rw      = st.session_state.get("depot_yaml_rw", "")
    yaml_depot   = st.session_state.get("depot_yaml_depot", "")
    yaml_scanner = st.session_state.get("depot_yaml_scanner", "")

    tab1, tab2, tab3, tab4 = st.tabs(["Secret R", "Secret RW", "Depot", "Scanner"])

    with tab1:
        st.markdown(f"**`{name}-r.yml`**")
        st.code(yaml_r, language="yaml")
        st.download_button("⬇ Download Secret R", data=yaml_r,
            file_name=f"{name}-r.yml", mime="text/yaml", use_container_width=True)

    with tab2:
        st.markdown(f"**`{name}-rw.yml`**")
        st.code(yaml_rw, language="yaml")
        st.download_button("⬇ Download Secret RW", data=yaml_rw,
            file_name=f"{name}-rw.yml", mime="text/yaml", use_container_width=True)

    with tab3:
        st.markdown(f"**`{name}-depot.yml`**")
        st.code(yaml_depot, language="yaml")
        st.download_button("⬇ Download Depot", data=yaml_depot,
            file_name=f"{name}-depot.yml", mime="text/yaml", use_container_width=True)

    with tab4:
        st.markdown(f"**`{name}-scanner.yml`**")
        st.code(yaml_scanner, language="yaml")
        st.download_button("⬇ Download Scanner", data=yaml_scanner,
            file_name=f"{name}-scanner.yml", mime="text/yaml", use_container_width=True)

    st.divider()

    import zipfile, io
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr(f"{name}-depot/{name}-r.yml",       yaml_r)
        zf.writestr(f"{name}-depot/{name}-rw.yml",      yaml_rw)
        zf.writestr(f"{name}-depot/{name}-depot.yml",   yaml_depot)
        zf.writestr(f"{name}-depot/{name}-scanner.yml", yaml_scanner)
    zip_buf.seek(0)
    save_zip_entry("Specific", "zip_depot", f"{name}-depot.zip", {
    f"{name}-depot/{name}-r.yml":       yaml_r,
    f"{name}-depot/{name}-rw.yml":      yaml_rw,
    f"{name}-depot/{name}-depot.yml":   yaml_depot,
    f"{name}-depot/{name}-scanner.yml": yaml_scanner,
    })
    st.download_button(
        f"Download All as ZIP  ({name}-depot.zip)",
        data=zip_buf, file_name=f"{name}-depot.zip",
        mime="application/zip", use_container_width=True,
    )

    st.markdown(" ")

    if origin == "cadp_full":
        st.session_state["cadp_depot_name"] = name
        if "cadp_completed_steps" not in st.session_state:
            st.session_state.cadp_completed_steps = set()
        st.session_state.cadp_completed_steps.add(1)
        st.divider()
        st.success("Depot files ready. Return to the CADP flow to continue.")
        if st.button("Back to CADP Flow →", use_container_width=True, type="primary"):
            clear_depot_state(keep_creds=True)
            st.switch_page("pages/cadp_flow.py")

    elif origin == "sadp_full":
        st.session_state["sadp_depot_name"] = name
        if "sadp_completed_steps" not in st.session_state:
            st.session_state.sadp_completed_steps = set()
        st.session_state.sadp_completed_steps.add(1)
        st.divider()
        st.success("Depot files ready. Return to the SADP flow to continue.")
        if st.button("Back to SADP Flow →", use_container_width=True, type="primary"):
            clear_depot_state(keep_creds=True)
            st.switch_page("pages/sadp_flow.py")

    elif origin == "specific":
        if st.button("← Back to File List"):
            clear_depot_state()
            st.session_state.home_screen = "specific"
            st.switch_page("app.py")
    else:
        if st.button("← Back to Home"):
            clear_depot_state()
            st.switch_page("app.py")