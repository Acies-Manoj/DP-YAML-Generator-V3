import streamlit as st
from utils.snowflake_utils import sf_connect, sf_fetch_databases, sf_fetch_schemas, sf_fetch_tables, sf_fetch_columns
from utils.sql_parser import parse_ddl, parse_sql_file
from utils.examples import EXAMPLE_SQL, show_example


def render_ind_sql():
    # NOTE: 'section' is guaranteed to be "sql" by the caller in 1_CADP.py.
    # The redundant `if section == "sql":` check was removed — 'section' is
    # not in scope here and caused a NameError.

    st.subheader("SQL Builder")

    # Init state
    for k, v in [
        ("ind_sql_mode",              "manual"),
        ("ind_sql_columns",           [""]),
        ("ind_sf_conn",               None),
        ("ind_sf_databases",          []),
        ("ind_sf_schemas",            []),
        ("ind_sf_tables",             []),
        ("ind_sf_alias_preview",      []),
        ("ind_sf_alias_confirmed",    False),
        ("ind_upload_alias_preview",  []),
        ("ind_upload_confirmed",      False),
        ("ind_preview_mode",          False),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

    DIM_TYPES = ["string", "number", "boolean", "time"]

    import re as _re
    def _valid(n): return bool(_re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', n))

    if not st.session_state.ind_preview_mode:

        # ── 3-way toggle ──────────────────────────────────────────────────────
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            if st.button("Enter Manually", use_container_width=True,
                type="primary" if st.session_state.ind_sql_mode == "manual" else "secondary"):
                st.session_state.ind_sql_mode = "manual"
                st.session_state.ind_sf_alias_confirmed = False
                st.session_state.ind_upload_confirmed   = False
                st.rerun()
        with tc2:
            if st.button("Connect to Snowflake", use_container_width=True,
                type="primary" if st.session_state.ind_sql_mode == "snowflake" else "secondary"):
                st.session_state.ind_sql_mode = "snowflake"
                st.session_state.ind_upload_confirmed = False
                st.rerun()
        with tc3:
            if st.button("Paste DDL", use_container_width=True,
                type="primary" if st.session_state.ind_sql_mode == "upload" else "secondary"):
                st.session_state.ind_sql_mode = "upload"
                st.session_state.ind_sf_alias_confirmed = False
                st.rerun()

        st.markdown(" ")

        # ══════════════════════════════════════════════════════════════════════
        # MANUAL
        # ══════════════════════════════════════════════════════════════════════
        if st.session_state.ind_sql_mode == "manual":

            if st.button("➕ Add Column", key="ind_add_col"):
                st.session_state.ind_sql_columns.append(""); st.rerun()

            with st.form("sql_form"):
                sc1, sc2, sc3 = st.columns(3)
                with sc1: db_name     = st.text_input("Database Name", placeholder="e.g. icebase")
                with sc2: schema_name = st.text_input("Schema Name",   placeholder="e.g. retail")
                with sc3: table_name  = st.text_input("Table Name *",  placeholder="e.g. customer")
                st.markdown("### Columns")
                updated_columns = []
                for i, col in enumerate(st.session_state.ind_sql_columns):
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        val = st.text_input(f"Column {i+1}", value=col, key=f"sql_col_{i}", placeholder="e.g. customer_id")
                        updated_columns.append(val)
                    with c2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.form_submit_button("❌", key=f"sql_rm_{i}"):
                            st.session_state.ind_sql_columns.pop(i); st.rerun()
                generate = st.form_submit_button("Preview SQL →", use_container_width=True)

            st.session_state.ind_sql_columns = updated_columns

            if generate:
                final_cols = [c.strip() for c in st.session_state.ind_sql_columns if c.strip()]
                if not db_name or not schema_name or not table_name:
                    st.error("Please fill Database, Schema, and Table name.")
                elif not final_cols:
                    st.error("Please add at least one column.")
                else:
                    col_str = ",\n    ".join(final_cols)
                    st.session_state.generated_sql = f"SELECT\n    {col_str}\nFROM {db_name}.{schema_name}.{table_name};"
                    st.session_state.ind_preview_mode = True
                    st.rerun()

        # ══════════════════════════════════════════════════════════════════════
        # SNOWFLAKE
        # ══════════════════════════════════════════════════════════════════════
        elif st.session_state.ind_sql_mode == "snowflake":

            if st.session_state.ind_sf_conn is None:
                st.markdown("#### Snowflake Credentials")

                # ── Pre-fill from Depot if available ─────────────────────────
                _depot_account   = st.session_state.get("depot_account", "")
                _depot_user      = st.session_state.get("depot_username", "")
                _depot_password  = st.session_state.get("depot_password", "")
                _depot_warehouse = st.session_state.get("depot_warehouse", "")

                if _depot_account or _depot_user:
                    st.info("✅ Credentials pre-filled from your Depot configuration. Click Connect to proceed.")
                else:
                    st.caption("Credentials held in memory only — never stored.")
                    _missing = []
                    if not _depot_account:   _missing.append("Account Identifier")
                    if not _depot_user:      _missing.append("Username")
                    if not _depot_password:  _missing.append("Password")
                    if not _depot_warehouse: _missing.append("Warehouse")
                    if _missing:
                        st.warning(
                            "The following fields were not filled in the Depot step and must be entered manually here: **"
                            + "**, **".join(_missing)
                            + "**. To avoid re-entering these, go back and complete the Depot first."
                        )

                with st.form("ind_sf_creds_form"):
                    cr1, cr2 = st.columns(2)
                    with cr1:
                        sf_account   = st.text_input("Account Identifier *", value=_depot_account, placeholder="e.g. abc12345.us-east-1.aws")
                        sf_user      = st.text_input("Username *", value=_depot_user)
                    with cr2:
                        sf_password  = st.text_input("Password *", value=_depot_password, type="password")
                        sf_role      = st.text_input("Role (optional)")
                        sf_warehouse = st.text_input("Warehouse (optional)", value=_depot_warehouse)
                    connect_btn = st.form_submit_button("Connect", use_container_width=True)

                if connect_btn:
                    if not sf_account or not sf_user or not sf_password:
                        st.error("Account, username and password are required.")
                    else:
                        with st.spinner("Connecting..."):
                            try:
                                conn = sf_connect(sf_account.strip(), sf_user.strip(), sf_password, sf_role, sf_warehouse)
                                st.session_state.ind_sf_conn = conn
                                st.session_state.ind_sf_databases = sf_fetch_databases(conn)
                                st.success("✅ Connected!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Connection failed: {e}")

            elif not st.session_state.ind_sf_alias_confirmed:
                conn = st.session_state.ind_sf_conn
                st.success("✅ Connected to Snowflake")
                if st.button("Disconnect", key="ind_sf_disconnect"):
                    for k in ["ind_sf_conn","ind_sf_databases","ind_sf_schemas","ind_sf_tables","ind_sf_alias_preview"]:
                        st.session_state[k] = [] if k != "ind_sf_conn" else None
                    st.rerun()

                st.markdown("#### Select Database → Schema → Table")
                dd1, dd2, dd3 = st.columns(3)

                with dd1:
                    sel_db = st.selectbox("Database", ["— select —"] + st.session_state.ind_sf_databases, key="ind_sf_sel_db")
                    if sel_db != "— select —" and sel_db != st.session_state.get("ind_sf_last_db"):
                        st.session_state.ind_sf_last_db = sel_db
                        st.session_state.ind_sf_schemas = sf_fetch_schemas(conn, sel_db)
                        st.session_state.ind_sf_tables = []
                        st.session_state.ind_sf_alias_preview = []
                        st.rerun()

                with dd2:
                    sel_schema = st.selectbox("Schema", ["— select —"] + st.session_state.ind_sf_schemas,
                                              key="ind_sf_sel_schema", disabled=not st.session_state.ind_sf_schemas)
                    if sel_schema != "— select —" and sel_schema != st.session_state.get("ind_sf_last_schema"):
                        st.session_state.ind_sf_last_schema = sel_schema
                        st.session_state.ind_sf_tables = sf_fetch_tables(conn, st.session_state.get("ind_sf_last_db",""), sel_schema)
                        st.session_state.ind_sf_alias_preview = []
                        st.rerun()

                with dd3:
                    sel_table = st.selectbox("Table", ["— select —"] + st.session_state.ind_sf_tables,
                                             key="ind_sf_sel_table", disabled=not st.session_state.ind_sf_tables)
                    if sel_table != "— select —" and sel_table != st.session_state.get("ind_sf_last_table"):
                        st.session_state.ind_sf_last_table = sel_table
                        raw_cols = sf_fetch_columns(conn, st.session_state.get("ind_sf_last_db",""),
                                                    st.session_state.get("ind_sf_last_schema",""), sel_table)
                        st.session_state.ind_sf_alias_preview = [
                            {"original": c["original"], "snowflake_type": c["snowflake_type"],
                             "mapped_type": c["mapped_type"], "alias": c["original"].lower(), "include": True}
                            for c in raw_cols
                        ]
                        st.rerun()

                if st.session_state.ind_sf_alias_preview:
                    st.divider()
                    st.markdown("#### Preview & Configure Columns")
                    preview = st.session_state.ind_sf_alias_preview
                    h1,h2,h3,h4,h5 = st.columns([2.5,2,2,2,0.7])
                    h1.markdown("**Original**"); h2.markdown("**SF Type**")
                    h3.markdown("**Alias**");    h4.markdown("**YAML Type**"); h5.markdown("**Inc**")
                    st.markdown("---")
                    aliases_seen = {}; has_errors = False
                    for i, col in enumerate(preview):
                        c1,c2,c3,c4,c5 = st.columns([2.5,2,2,2,0.7])
                        with c1: st.code(col["original"], language=None)
                        with c2: st.caption(col["snowflake_type"])
                        with c3:
                            a = st.text_input("a", value=col["alias"], key=f"ind_sf_alias_{i}", label_visibility="collapsed")
                            preview[i]["alias"] = a
                            if a:
                                if not _valid(a): st.error("⚠ Invalid"); has_errors = True
                                elif a in aliases_seen: st.error("⚠ Duplicate"); has_errors = True
                                else: aliases_seen[a] = True
                        with c4:
                            t = st.selectbox("t", DIM_TYPES,
                                             index=DIM_TYPES.index(col["mapped_type"]) if col["mapped_type"] in DIM_TYPES else 0,
                                             key=f"ind_sf_type_{i}", label_visibility="collapsed")
                            preview[i]["mapped_type"] = t
                        with c5:
                            inc = st.checkbox("i", value=col["include"], key=f"ind_sf_inc_{i}", label_visibility="collapsed")
                            preview[i]["include"] = inc
                    st.session_state.ind_sf_alias_preview = preview
                    included = [c for c in preview if c["include"]]
                    st.markdown(f"**{len(included)} of {len(preview)} columns selected**")

                    if has_errors: st.warning("Fix errors before confirming.")
                    elif not included: st.warning("Select at least one column.")
                    else:
                        if st.button("✅ Confirm & Generate SQL →", use_container_width=True, type="primary"):
                            sf_db  = st.session_state.get("ind_sf_last_db","")
                            sf_sch = st.session_state.get("ind_sf_last_schema","")
                            sf_tbl = st.session_state.get("ind_sf_last_table","")
                            col_lines = [
                                f'{c["original"]} AS {c["alias"]}' if c["alias"].lower() != c["original"].lower() else c["original"]
                                for c in included
                            ]
                            col_str = ",\n    ".join(col_lines)
                            st.session_state.generated_sql = f"SELECT\n    {col_str}\nFROM {sf_db}.{sf_sch}.{sf_tbl};"
                            st.session_state.ind_sf_alias_confirmed = True
                            st.session_state.ind_preview_mode = True
                            st.rerun()

        # ══════════════════════════════════════════════════════════════════════
        # PASTE DDL
        # ══════════════════════════════════════════════════════════════════════
        elif st.session_state.ind_sql_mode == "upload":

            if not st.session_state.ind_upload_confirmed:
                st.markdown("#### Paste your CREATE TABLE DDL")
                st.caption("Paste a Snowflake `CREATE [OR REPLACE] TABLE` statement. We'll extract the table name, columns, and data types automatically.")

                ddl_input = st.text_area(
                    "DDL Statement",
                    height=220,
                    placeholder="CREATE OR REPLACE TABLE DB.SCHEMA.TABLE_NAME (\n\tCOLUMN_ONE VARCHAR(16777216),\n\tCOLUMN_TWO NUMBER(38,0),\n\t...\n);",
                    key="ind_ddl_input",
                    label_visibility="collapsed",
                )

                parse_btn = st.button("Parse DDL", use_container_width=True, type="primary", key="ind_parse_ddl")

                if parse_btn and ddl_input.strip():
                    parsed = parse_ddl(ddl_input)
                    if parsed["columns"]:
                        st.session_state.ind_upload_alias_preview = [
                            {
                                "original":      c["original"],
                                "alias":         c["alias"],
                                "snowflake_type": c["snowflake_type"],
                                "mapped_type":   c["mapped_type"],
                                "include":       True,
                            }
                            for c in parsed["columns"]
                        ]
                        st.session_state["ind_parsed_db"]     = parsed["db"]
                        st.session_state["ind_parsed_schema"] = parsed["schema"]
                        st.session_state["ind_parsed_table"]  = parsed["table"]
                        st.rerun()
                    else:
                        st.error("Could not parse columns. Make sure it's a valid CREATE TABLE statement.")

                if st.session_state.ind_upload_alias_preview:
                    parsed_db    = st.session_state.get("ind_parsed_db", "")
                    parsed_sch   = st.session_state.get("ind_parsed_schema", "")
                    parsed_table = st.session_state.get("ind_parsed_table", "")

                    up1, up2, up3 = st.columns(3)
                    with up1: up_db     = st.text_input("Database",   value=parsed_db,    key="ind_up_db",     placeholder="e.g. icebase")
                    with up2: up_schema = st.text_input("Schema",     value=parsed_sch,   key="ind_up_schema", placeholder="e.g. retail")
                    with up3: up_table  = st.text_input("Table Name", value=parsed_table, key="ind_up_table",  placeholder="e.g. customer")

                    st.divider()
                    st.markdown("#### Preview & Configure Columns")
                    st.caption("Column names and Snowflake types auto-filled from your DDL. Set aliases and override YAML types as needed.")

                    preview = st.session_state.ind_upload_alias_preview
                    h1, h2, h3, h4, h5 = st.columns([2.5, 2, 2, 2, 0.7])
                    h1.markdown("**Original**"); h2.markdown("**SF Type**")
                    h3.markdown("**Alias**");    h4.markdown("**YAML Type**"); h5.markdown("**Inc**")
                    st.markdown("---")
                    aliases_seen = {}; has_errors = False

                    for i, col in enumerate(preview):
                        c1, c2, c3, c4, c5 = st.columns([2.5, 2, 2, 2, 0.7])
                        with c1: st.code(col["original"], language=None)
                        with c2: st.caption(col["snowflake_type"])
                        with c3:
                            a = st.text_input("a", value=col["alias"], key=f"ind_up_alias_{i}", label_visibility="collapsed")
                            preview[i]["alias"] = a
                            if a:
                                if not _valid(a): st.error("⚠ Invalid"); has_errors = True
                                elif a in aliases_seen: st.error("⚠ Duplicate"); has_errors = True
                                else: aliases_seen[a] = True
                        with c4:
                            t = st.selectbox("t", DIM_TYPES,
                                             index=DIM_TYPES.index(col["mapped_type"]) if col["mapped_type"] in DIM_TYPES else 0,
                                             key=f"ind_up_type_{i}", label_visibility="collapsed")
                            preview[i]["mapped_type"] = t
                        with c5:
                            inc = st.checkbox("i", value=col["include"], key=f"ind_up_inc_{i}", label_visibility="collapsed")
                            preview[i]["include"] = inc

                    st.session_state.ind_upload_alias_preview = preview
                    included = [c for c in preview if c["include"]]
                    st.markdown(f"**{len(included)} of {len(preview)} columns selected**")

                    if has_errors: st.warning("Fix errors before confirming.")
                    elif not included: st.warning("Select at least one column.")
                    elif not up_table.strip(): st.warning("Table name is required.")
                    else:
                        if st.button("✅ Confirm & Generate SQL →", use_container_width=True, type="primary"):
                            col_lines = [
                                f'{c["original"]} AS {c["alias"]}' if c["alias"].lower() != c["original"].lower() else c["original"]
                                for c in included
                            ]
                            col_str  = ",\n    ".join(col_lines)
                            from_str = ".".join(filter(None, [up_db.strip(), up_schema.strip(), up_table.strip()]))
                            st.session_state.generated_sql    = f"SELECT\n    {col_str}\nFROM {from_str};"
                            st.session_state.ind_upload_confirmed = True
                            st.session_state.ind_preview_mode    = True
                            st.rerun()

    else:
        # ── PREVIEW ──────────────────────────────────────────────────────────
        st.markdown("### SQL Preview")
        st.code(st.session_state.generated_sql, language="sql")

        if st.session_state.ind_sql_mode == "snowflake":
            included = [c for c in st.session_state.ind_sf_alias_preview if c["include"]]
            with st.expander(f"{len(included)} columns from Snowflake"):
                h1,h2,h3,h4 = st.columns([2.5,2,2,2])
                h1.markdown("**Original**"); h2.markdown("**SF Type**"); h3.markdown("**Alias**"); h4.markdown("**YAML Type**")
                for c in included:
                    r1,r2,r3,r4 = st.columns([2.5,2,2,2])
                    r1.code(c["original"], language=None); r2.caption(c["snowflake_type"]); r3.text(c["alias"]); r4.text(c["mapped_type"])
        elif st.session_state.ind_sql_mode == "upload":
            included = [c for c in st.session_state.ind_upload_alias_preview if c["include"]]
            with st.expander(f"{len(included)} columns from uploaded SQL"):
                h1,h2,h3 = st.columns([2.5,2.5,2.5])
                h1.markdown("**Original**"); h2.markdown("**Alias**"); h3.markdown("**YAML Type**")
                for c in included:
                    r1,r2,r3 = st.columns([2.5,2.5,2.5])
                    r1.code(c["original"], language=None); r2.text(c["alias"]); r3.text(c["mapped_type"])

        ec1, ec2 = st.columns(2)
        with ec1:
            if st.button("← Edit SQL"):
                st.session_state.ind_preview_mode = False
                st.session_state.ind_sf_alias_confirmed = False
                st.session_state.ind_upload_confirmed   = False
                st.rerun()
        with ec2:
            st.download_button(
                label="⬇ Download SQL File",
                data=st.session_state.generated_sql,
                file_name="semantic_model.sql",
                mime="text/plain",
                use_container_width=True
            )