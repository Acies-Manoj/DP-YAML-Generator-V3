import streamlit as st

# ── TYPE CONSTANTS ─────────────────────────────────────────────────────────────
DIM_TYPES     = ["string", "number", "boolean", "time"]
MEASURE_TYPES = ["number", "count", "count_distinct", "sum", "avg", "min", "max", "string"]
JOIN_RELS     = ["many_to_one", "one_to_many", "one_to_one"]
LOG_LEVELS    = ["info", "debug", "warn", "error"]

STEP_LABELS = [
    "1. SQL Files",
    "2. Table YAMLs",
    "3. View YAMLs",
    "4. Repo Credential",
    "5. Lens Deployment",
    "6. User Groups",
    "7. Review & Download",
]

BUNDLE_KEYS_TO_CLEAR = [
    "bundle_tables", "bundle_table_idx", "bundle_views", "bundle_view_idx",
    "bundle_step", "bundle_lens_tags", "bundle_lens_secrets", "bundle_lens_sync_flags",
    "bundle_lens_name", "bundle_generated_lens_yaml", "bundle_lens_preview_mode",
    "bundle_user_groups", "bundle_user_groups_yaml", "bundle_user_groups_preview",
    "bundle_repo_cred_name", "bundle_repo_cred_desc", "bundle_repo_cred_owner",
    "bundle_repo_cred_username", "bundle_repo_cred_password",
    "bundle_repo_cred_version", "bundle_repo_cred_layer", "bundle_repo_cred_acl",
    "bundle_repo_cred_secret_type",
    "bundle_repo_cred_tags", "bundle_repo_cred_yaml", "bundle_repo_cred_preview",
    "bundle_lens_src_name", "bundle_lens_src_catalog", "bundle_lens_src_type",
    "bundle_lens_repo_url", "bundle_lens_repo_basedir",
    "bundle_lens_version", "bundle_lens_layer", "bundle_lens_compute",
]

BUNDLE_YAML_KEYS_PRESERVE = {
    "bundle_tables", "bundle_views",
    "bundle_lens_name", "bundle_generated_lens_yaml",
}


def new_table():
    return {
        "name": "", "db": "", "schema": "", "sql_input_mode": "manual",
        "generated_sql": "", "generated_table_yaml": "",
        "tbl_desc": "", "tbl_public": True,
        "dims": [], "measures": [], "joins": [], "segments": [],
        "sf_last_db": "", "sf_last_schema": "", "sf_last_table": "",
        "sf_schemas": [], "sf_tables": [],
        "sf_raw_columns": [], "sf_alias_preview": [], "sf_alias_confirmed": False,
        "upload_alias_preview": [], "upload_alias_confirmed": False,
        "manual_cols": [{"original": "", "alias": "", "cast_as": "", "mapped_type": "string", "include": True}],
        "sql_preview_mode": False,
        "tbl_preview_mode": False,
    }


def new_view():
    return {
        "name": "", "generated_view_yaml": "",
        "view_tags": [""], "view_metric_excludes": [""],
        "view_tables": [],
        "preview_mode": False,
    }


def init_bundle_state():
    if "bundle_tables" not in st.session_state:
        st.session_state.bundle_tables = [new_table()]
    if "bundle_table_idx" not in st.session_state:
        st.session_state.bundle_table_idx = 0
    if "sf_shared_conn"      not in st.session_state: st.session_state.sf_shared_conn      = None
    if "sf_shared_account"   not in st.session_state: st.session_state.sf_shared_account   = ""
    if "sf_shared_user"      not in st.session_state: st.session_state.sf_shared_user      = ""
    if "sf_shared_databases" not in st.session_state: st.session_state.sf_shared_databases = []
    if "bundle_views" not in st.session_state:
        st.session_state.bundle_views = []
    if "bundle_view_idx"  not in st.session_state: st.session_state.bundle_view_idx  = 0
    if "bundle_step"      not in st.session_state: st.session_state.bundle_step      = 1
    if "bundle_lens_tags"       not in st.session_state: st.session_state.bundle_lens_tags       = ["lens"]
    if "bundle_lens_secrets"    not in st.session_state: st.session_state.bundle_lens_secrets    = [{"name": "", "allKeys": True}]
    if "bundle_lens_sync_flags" not in st.session_state: st.session_state.bundle_lens_sync_flags = ["--ref=main"]
    if "bundle_lens_name"       not in st.session_state: st.session_state.bundle_lens_name       = ""
    if "bundle_generated_lens_yaml"  not in st.session_state: st.session_state.bundle_generated_lens_yaml  = ""
    if "bundle_lens_preview_mode"    not in st.session_state: st.session_state.bundle_lens_preview_mode    = False
    if "bundle_user_groups" not in st.session_state:
        st.session_state.bundle_user_groups = [
            {"name": "default", "api_scopes": ["meta", "data", "graphql", "jobs", "source"], "includes": ["*"]}
        ]
    if "bundle_user_groups_yaml"    not in st.session_state: st.session_state.bundle_user_groups_yaml    = ""
    if "bundle_user_groups_preview" not in st.session_state: st.session_state.bundle_user_groups_preview = False
    if "bundle_repo_cred_name"        not in st.session_state: st.session_state.bundle_repo_cred_name        = ""
    if "bundle_repo_cred_desc"        not in st.session_state: st.session_state.bundle_repo_cred_desc        = "Git read secrets for repos."
    if "bundle_repo_cred_owner"       not in st.session_state: st.session_state.bundle_repo_cred_owner       = ""
    if "bundle_repo_cred_username"    not in st.session_state: st.session_state.bundle_repo_cred_username    = ""
    if "bundle_repo_cred_password"    not in st.session_state: st.session_state.bundle_repo_cred_password    = ""
    if "bundle_repo_cred_version"     not in st.session_state: st.session_state.bundle_repo_cred_version     = "v1"
    if "bundle_repo_cred_layer"       not in st.session_state: st.session_state.bundle_repo_cred_layer       = "user"
    if "bundle_repo_cred_acl"         not in st.session_state: st.session_state.bundle_repo_cred_acl         = "r"
    if "bundle_repo_cred_secret_type" not in st.session_state: st.session_state.bundle_repo_cred_secret_type = "key-value"
    if "bundle_repo_cred_tags"  not in st.session_state:
        st.session_state.bundle_repo_cred_tags = [
            "dataos:type:resource", "dataos:type:cluster-resource",
            "dataos:resource:instance-secret", "dataos:layer:user",
        ]
    if "bundle_repo_cred_yaml"    not in st.session_state: st.session_state.bundle_repo_cred_yaml    = ""
    if "bundle_repo_cred_preview" not in st.session_state: st.session_state.bundle_repo_cred_preview = False
    # ── Lens source / repo fields ─────────────────────────────────────────────
    if "bundle_lens_src_name"    not in st.session_state: st.session_state.bundle_lens_src_name    = ""
    if "bundle_lens_src_catalog" not in st.session_state: st.session_state.bundle_lens_src_catalog = ""
    if "bundle_lens_src_type"    not in st.session_state: st.session_state.bundle_lens_src_type    = "minerva"
    if "bundle_lens_repo_url"    not in st.session_state: st.session_state.bundle_lens_repo_url    = ""
    if "bundle_lens_repo_basedir" not in st.session_state: st.session_state.bundle_lens_repo_basedir = ""
    if "bundle_lens_version"     not in st.session_state: st.session_state.bundle_lens_version     = "v1alpha"
    if "bundle_lens_layer"       not in st.session_state: st.session_state.bundle_lens_layer       = "user"
    if "bundle_lens_compute"     not in st.session_state: st.session_state.bundle_lens_compute     = "runnable-default"