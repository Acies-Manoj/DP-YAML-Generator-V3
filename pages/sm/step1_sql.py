import re as _re_sql
import streamlit as st
from utils.snowflake_utils import sf_connect, sf_fetch_databases, sf_fetch_schemas, sf_fetch_tables, sf_fetch_columns
from utils.sql_parser import parse_ddl
from utils.examples import EXAMPLE_SQL, show_example
from sm.state import new_table


# ── helpers ────────────────────────────────────────────────────────────────────

def _valid_col_name(n):
    return bool(_re_sql.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', n))


def _build_col_line(orig, alias, cast_as):
    cast_as = (cast_as or "").strip()
    alias   = (alias   or "").strip()
    expr    = f"CAST({orig} AS {cast_as})" if cast_as else orig
    if alias and (alias.lower() != orig.lower() or cast_as):
        return f"{expr} AS {alias}"
    return expr


def _render_col_grid(preview, key_prefix):
    DIM_TYPES_INNER = ["string", "number", "boolean", "time"]
    h1, h2, h3, h4, h5, h6 = st.columns([2.2, 1.6, 1.9, 1.9, 1.8, 0.6])
    h1.markdown("**Column**"); h2.markdown("**SF Type**")
    h3.markdown("**Alias**");  h4.markdown("**Cast As**")
    h5.markdown("**YAML Type**"); h6.markdown("**✓**")
    st.markdown("---")
    aliases_seen = {}; has_errors = False
    for i, col in enumerate(preview):
        c1, c2, c3, c4, c5, c6 = st.columns([2.2, 1.6, 1.9, 1.9, 1.8, 0.6])
        with c1: st.code(col["original"], language=None)
        with c2: st.caption(col.get("snowflake_type", ""))
        with c3:
            new_alias = st.text_input(
                "alias", value=col.get("alias", col["original"].lower()),
                key=f"{key_prefix}_al_{i}", label_visibility="collapsed",
                placeholder=col["original"].lower())
            preview[i]["alias"] = new_alias
            if new_alias:
                if not _valid_col_name(new_alias):
                    st.error("Invalid"); has_errors = True
                elif new_alias in aliases_seen:
                    st.error("Duplicate"); has_errors = True
                else:
                    aliases_seen[new_alias] = True
        with c4:
            preview[i]["cast_as"] = st.text_input(
                "cast_as", value=col.get("cast_as", ""),
                key=f"{key_prefix}_ca_{i}", label_visibility="collapsed",
                placeholder="e.g. VARCHAR")
        with c5:
            cur = col.get("mapped_type", "string")
            preview[i]["mapped_type"] = st.selectbox(
                "type", DIM_TYPES_INNER,
                index=DIM_TYPES_INNER.index(cur) if cur in DIM_TYPES_INNER else 0,
                key=f"{key_prefix}_ty_{i}", label_visibility="collapsed")
        with c6:
            preview[i]["include"] = st.checkbox(
                "inc", value=col.get("include", True),
                key=f"{key_prefix}_in_{i}", label_visibility="collapsed")
    included = [c for c in preview if c["include"]]
    return preview, included, has_errors


def _preview_to_dims(included):
    return [
        {"name": c.get("alias", c["original"]).strip() or c["original"],
         "type": c.get("mapped_type", "string"), "column": c["original"],
         "description": "", "primary_key": False, "public": True}
        for c in included
    ]


# ── sub-renderers ──────────────────────────────────────────────────────────────

def _render_manual(tables, tidx):
    t = tables[tidx]
    if not tables[tidx].get("manual_cols"):
        tables[tidx]["manual_cols"] = [
            {"original": "", "alias": "", "cast_as": "", "mapped_type": "string",
             "snowflake_type": "", "include": True}
        ]

    if st.button("➕ Add Column", key=f"b_add_col_{tidx}"):
        tables[tidx]["manual_cols"].append(
            {"original": "", "alias": "", "cast_as": "", "mapped_type": "string",
             "snowflake_type": "", "include": True})
        st.rerun()

    with st.form(f"bundle_sql_form_{tidx}"):
        bc1, bc2, bc3 = st.columns(3)
        with bc1: b_db     = st.text_input("Database Name", value=t.get("db", ""),     placeholder="e.g. icebase")
        with bc2: b_schema = st.text_input("Schema Name",   value=t.get("schema", ""), placeholder="e.g. retail")
        with bc3: b_tname  = st.text_input("Table Name *",  value=t.get("name", ""),   placeholder="e.g. customer")

        st.markdown("#### Columns")
        st.caption("Alias renames the column in SQL. Cast As wraps it in CAST(col AS type). Both optional.")
        mh1, mh2, mh3, mh4, mh5, mh6, mh7 = st.columns([2.2, 1.6, 1.9, 1.9, 1.8, 0.6, 0.5])
        mh1.markdown("**Column Name**"); mh2.markdown("—")
        mh3.markdown("**Alias**"); mh4.markdown("**Cast As**")
        mh5.markdown("**YAML Type**"); mh6.markdown("**✓**")
        st.markdown("---")

        manual_cols = tables[tidx]["manual_cols"]
        DIM_TYPES_M = ["string", "number", "boolean", "time"]
        for i, col in enumerate(manual_cols):
            mc1, mc2, mc3, mc4, mc5, mc6, mc7 = st.columns([2.2, 1.6, 1.9, 1.9, 1.8, 0.6, 0.5])
            with mc1:
                manual_cols[i]["original"] = st.text_input(
                    f"col_{i}", value=col.get("original", ""),
                    key=f"m_orig_{tidx}_{i}", label_visibility="collapsed",
                    placeholder="e.g. customer_id")
            with mc2: st.caption("")
            with mc3:
                manual_cols[i]["alias"] = st.text_input(
                    "alias", value=col.get("alias", ""),
                    key=f"m_al_{tidx}_{i}", label_visibility="collapsed",
                    placeholder=col.get("original", "col").lower() or "alias")
            with mc4:
                manual_cols[i]["cast_as"] = st.text_input(
                    "cast", value=col.get("cast_as", ""),
                    key=f"m_ca_{tidx}_{i}", label_visibility="collapsed",
                    placeholder="e.g. VARCHAR")
            with mc5:
                cur_t = col.get("mapped_type", "string")
                manual_cols[i]["mapped_type"] = st.selectbox(
                    "type", DIM_TYPES_M,
                    index=DIM_TYPES_M.index(cur_t) if cur_t in DIM_TYPES_M else 0,
                    key=f"m_ty_{tidx}_{i}", label_visibility="collapsed")
            with mc6:
                manual_cols[i]["include"] = st.checkbox(
                    "inc", value=col.get("include", True),
                    key=f"m_in_{tidx}_{i}", label_visibility="collapsed")
            with mc7:
                if st.form_submit_button("✕", key=f"m_rm_{tidx}_{i}"):
                    tables[tidx]["manual_cols"].pop(i); st.rerun()
        tables[tidx]["manual_cols"] = manual_cols
        submit1 = st.form_submit_button("Preview SQL", use_container_width=True)

    if submit1:
        included_m = [c for c in tables[tidx]["manual_cols"]
                      if c.get("original", "").strip() and c.get("include", True)]
        if not b_tname.strip():
            st.error("Table Name is required.")
        elif not included_m:
            st.error("Add at least one column.")
        else:
            col_lines = [_build_col_line(
                c["original"].strip(),
                c.get("alias", "").strip() or c["original"].strip().lower(),
                c.get("cast_as", "")
            ) for c in included_m]
            col_str  = ",\n    ".join(col_lines)
            from_str = ".".join(filter(None, [b_db.strip(), b_schema.strip(), b_tname.strip()]))
            tables[tidx]["generated_sql"]    = f"SELECT\n    {col_str}\nFROM {from_str};"
            tables[tidx]["name"]             = b_tname.strip()
            tables[tidx]["db"]               = b_db.strip()
            tables[tidx]["schema"]           = b_schema.strip()
            tables[tidx]["dims"]             = _preview_to_dims(included_m)
            tables[tidx]["sql_preview_mode"] = True
            st.rerun()


def _render_snowflake(tables, tidx):
    t = tables[tidx]
    _shared_conn = st.session_state.sf_shared_conn

    if _shared_conn is None:
        st.markdown("#### Snowflake Credentials")
        _depot_account   = st.session_state.get("depot_account", "")
        _depot_user      = st.session_state.get("depot_username", "")
        _depot_password  = st.session_state.get("depot_password", "")
        _depot_warehouse = st.session_state.get("depot_warehouse", "")
        if _depot_account or _depot_user:
            st.info("Credentials pre-filled from your Depot. Click Connect to proceed.")
        else:
            st.caption("Credentials are held in memory only and never stored.")

        with st.form("sf_creds_form_shared"):
            cr1, cr2 = st.columns(2)
            with cr1:
                sf_account = st.text_input("Account Identifier *", value=_depot_account, placeholder="e.g. abc12345.us-east-1.aws")
                sf_user    = st.text_input("Username *",           value=_depot_user,    placeholder="e.g. john_doe")
            with cr2:
                sf_password  = st.text_input("Password *",           value=_depot_password, type="password")
                sf_role      = st.text_input("Role (optional)",       placeholder="e.g. SYSADMIN")
                sf_warehouse = st.text_input("Warehouse (optional)",  value=_depot_warehouse, placeholder="e.g. COMPUTE_WH")
            connect_btn = st.form_submit_button("Connect to Snowflake", use_container_width=True)

        if connect_btn:
            if not sf_account or not sf_user or not sf_password:
                st.error("Account identifier, username and password are required.")
            else:
                with st.spinner("Connecting..."):
                    try:
                        _new_conn = sf_connect(sf_account.strip(), sf_user.strip(), sf_password, sf_role, sf_warehouse)
                        st.session_state.sf_shared_conn      = _new_conn
                        st.session_state.sf_shared_account   = sf_account.strip()
                        st.session_state.sf_shared_user      = sf_user.strip()
                        st.session_state.sf_shared_databases = sf_fetch_databases(_new_conn)
                        st.success("Connected!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Connection failed: {e}")

    elif not t["sf_alias_confirmed"]:
        _shared_conn = st.session_state.sf_shared_conn
        cb1, cb2 = st.columns([5, 1])
        with cb1:
            st.success(
                f"✅ Connected as **{st.session_state.sf_shared_user}**"
                f" @ `{st.session_state.sf_shared_account}` "
                f"— connection shared across all tables")
        with cb2:
            if st.button("Disconnect", key="sf_disconnect_btn"):
                st.session_state.sf_shared_conn      = None
                st.session_state.sf_shared_account   = ""
                st.session_state.sf_shared_user      = ""
                st.session_state.sf_shared_databases = []
                for _tbl in st.session_state.bundle_tables:
                    _tbl.update({
                        "sf_last_db": "", "sf_last_schema": "", "sf_last_table": "",
                        "sf_schemas": [], "sf_tables": [], "sf_raw_columns": [],
                        "sf_alias_preview": [], "sf_alias_confirmed": False,
                    })
                st.rerun()

        st.markdown("#### Select Database → Schema → Table")
        dd1, dd2, dd3 = st.columns(3)

        with dd1:
            _db_opts = ["— select —"] + st.session_state.sf_shared_databases
            _db_idx  = _db_opts.index(t.get("sf_last_db", "")) if t.get("sf_last_db") in _db_opts else 0
            sel_db   = st.selectbox("Database", _db_opts, index=_db_idx, key=f"sf_db_{tidx}")
            if sel_db != "— select —" and sel_db != t.get("sf_last_db"):
                tables[tidx].update({"sf_last_db": sel_db, "sf_last_schema": "", "sf_last_table": "",
                    "sf_schemas": sf_fetch_schemas(_shared_conn, sel_db), "sf_tables": [], "sf_alias_preview": []})
                st.rerun()

        with dd2:
            _sch_opts  = ["— select —"] + t.get("sf_schemas", [])
            _sch_idx   = _sch_opts.index(t.get("sf_last_schema", "")) if t.get("sf_last_schema") in _sch_opts else 0
            sel_schema = st.selectbox("Schema", _sch_opts, index=_sch_idx,
                key=f"sf_schema_{tidx}", disabled=not t.get("sf_schemas"))
            if sel_schema != "— select —" and sel_schema != t.get("sf_last_schema"):
                tables[tidx].update({"sf_last_schema": sel_schema, "sf_last_table": "",
                    "sf_tables": sf_fetch_tables(_shared_conn, t.get("sf_last_db", ""), sel_schema),
                    "sf_alias_preview": []})
                st.rerun()

        with dd3:
            _tbl_opts = ["— select —"] + t.get("sf_tables", [])
            _tbl_idx  = _tbl_opts.index(t.get("sf_last_table", "")) if t.get("sf_last_table") in _tbl_opts else 0
            sel_table = st.selectbox("Table", _tbl_opts, index=_tbl_idx,
                key=f"sf_table_{tidx}", disabled=not t.get("sf_tables"))
            if sel_table != "— select —" and sel_table != t.get("sf_last_table"):
                _raw = sf_fetch_columns(_shared_conn, t.get("sf_last_db", ""), t.get("sf_last_schema", ""), sel_table)
                tables[tidx]["sf_last_table"]   = sel_table
                tables[tidx]["sf_raw_columns"]  = _raw
                tables[tidx]["sf_alias_preview"] = [
                    {"original": c["original"], "snowflake_type": c["snowflake_type"],
                     "mapped_type": c["mapped_type"], "alias": c["original"].lower(), "cast_as": "", "include": True}
                    for c in _raw
                ]
                st.rerun()

        if t["sf_alias_preview"]:
            st.divider()
            st.markdown("#### Preview & Configure Columns")
            st.caption("Alias renames the column in SQL. Cast As wraps it in CAST(col AS type). Both optional.")
            _preview_sf, _included_sf, _errors_sf = _render_col_grid(t["sf_alias_preview"], f"sf_{tidx}")
            tables[tidx]["sf_alias_preview"] = _preview_sf
            st.markdown(f"**{len(_included_sf)} of {len(_preview_sf)} columns selected**")

            if not _errors_sf and _included_sf:
                if st.button("Confirm Columns & Generate SQL", use_container_width=True, type="primary"):
                    _sf_db  = t.get("sf_last_db", "")
                    _sf_sch = t.get("sf_last_schema", "")
                    _sf_tbl = t.get("sf_last_table", "")
                    _col_str = ",\n    ".join([_build_col_line(c["original"], c.get("alias", ""), c.get("cast_as", "")) for c in _included_sf])
                    tables[tidx].update({
                        "generated_sql":    f"SELECT\n    {_col_str}\nFROM {_sf_db}.{_sf_sch}.{_sf_tbl};",
                        "name":             _sf_tbl, "db": _sf_db, "schema": _sf_sch,
                        "dims":             _preview_to_dims(_included_sf),
                        "sf_alias_confirmed": True, "sql_preview_mode": True,
                    })
                    st.rerun()


def _render_ddl(tables, tidx):
    t = tables[tidx]
    if not t["upload_alias_confirmed"]:
        st.markdown("#### Paste your CREATE TABLE DDL")
        ddl_input = st.text_area("DDL Statement", height=220,
            placeholder="CREATE OR REPLACE TABLE DB.SCHEMA.TABLE_NAME (\n\tCOLUMN_ONE VARCHAR(16777216),\n\t...\n);",
            key=f"b_ddl_{tidx}", label_visibility="collapsed")
        if st.button("Parse DDL", use_container_width=True, type="primary", key=f"b_parse_{tidx}"):
            if ddl_input.strip():
                parsed = parse_ddl(ddl_input)
                if parsed["columns"]:
                    tables[tidx]["upload_alias_preview"] = [
                        {"original": c["original"], "alias": c["alias"],
                         "snowflake_type": c["snowflake_type"], "mapped_type": c["mapped_type"],
                         "cast_as": "", "include": True}
                        for c in parsed["columns"]
                    ]
                    tables[tidx]["b_parsed_db"]     = parsed["db"]
                    tables[tidx]["b_parsed_schema"] = parsed["schema"]
                    tables[tidx]["b_parsed_table"]  = parsed["table"]
                    st.rerun()
                else:
                    st.error("Could not parse columns.")

        if t["upload_alias_preview"]:
            st.markdown("#### Source Table")
            up1, up2, up3 = st.columns(3)
            with up1: up_db     = st.text_input("Database", value=t.get("b_parsed_db", ""),     key=f"up_db_{tidx}")
            with up2: up_schema = st.text_input("Schema",   value=t.get("b_parsed_schema", ""), key=f"up_schema_{tidx}")
            with up3: up_table  = st.text_input("Table",    value=t.get("b_parsed_table", ""),  key=f"up_table_{tidx}")

            st.divider()
            st.markdown("#### Preview & Configure Columns")
            st.caption("Alias renames the column in SQL. Cast As wraps it in CAST(col AS type). Both optional.")
            _preview_up, _included_up, _errors_up = _render_col_grid(t["upload_alias_preview"], f"up_{tidx}")
            tables[tidx]["upload_alias_preview"] = _preview_up
            st.markdown(f"**{len(_included_up)} of {len(_preview_up)} selected**")

            if not _errors_up and _included_up and up_table.strip():
                if st.button("Confirm & Generate SQL", use_container_width=True, type="primary", key=f"up_confirm_{tidx}"):
                    _col_str_up  = ",\n    ".join([_build_col_line(c["original"], c.get("alias", ""), c.get("cast_as", "")) for c in _included_up])
                    _from_str_up = ".".join(filter(None, [up_db.strip(), up_schema.strip(), up_table.strip()]))
                    tables[tidx].update({
                        "generated_sql": f"SELECT\n    {_col_str_up}\nFROM {_from_str_up};",
                        "name": up_table.strip(), "db": up_db.strip(), "schema": up_schema.strip(),
                        "dims": _preview_to_dims(_included_up), "upload_alias_confirmed": True,
                        "sql_preview_mode": True,
                    })
                    st.rerun()


# ── main entry point ───────────────────────────────────────────────────────────

def render_step1():
    tables = st.session_state.bundle_tables
    tidx   = st.session_state.bundle_table_idx
    t      = tables[tidx]

    # Summary of completed tables
    done_tables = [i for i, tbl in enumerate(tables) if tbl.get("generated_sql")]
    if done_tables:
        st.markdown("**SQL files generated so far:**")
        for i in done_tables:
            col_name, col_edit, col_del = st.columns([4, 1, 1])
            with col_name: st.markdown(f"- `{tables[i]['name']}.sql` ✅")
            with col_edit:
                if st.button("Edit", key=f"sql_edit_{i}"):
                    tables[i]["sql_preview_mode"] = False
                    tables[i]["generated_sql"]    = ""
                    st.session_state.bundle_table_idx = i
                    st.rerun()
            with col_del:
                if len(tables) > 1:
                    if st.button("🗑️", key=f"sql_del_{i}", help="Delete this table"):
                        st.session_state.bundle_tables.pop(i)
                        st.session_state.bundle_table_idx = min(tidx, len(st.session_state.bundle_tables) - 1)
                        st.rerun()
        st.divider()

    if not t.get("sql_preview_mode"):
        n_label = f"Table {tidx + 1}" if not t.get("name") else t["name"]
        if tidx > 0 and not t.get("generated_sql"):
            st.info(f"Adding SQL for Table {tidx + 1}. Changed your mind?")
            if st.button("← Discard & Continue with Existing Tables", use_container_width=True):
                st.session_state.bundle_tables.pop(tidx)
                st.session_state.bundle_table_idx = len(st.session_state.bundle_tables) - 1
                st.rerun()
            st.divider()

        st.subheader(f"Step 1 — SQL File for: {n_label}")
        show_example(st, "SQL File", EXAMPLE_SQL)

        mode_col1, mode_col2, mode_col3 = st.columns(3)
        with mode_col1:
            if st.button("Enter Manually", use_container_width=True,
                type="primary" if t["sql_input_mode"] == "manual" else "secondary"):
                tables[tidx].update({"sql_input_mode": "manual", "sf_alias_confirmed": False, "upload_alias_confirmed": False})
                st.rerun()
        with mode_col2:
            if st.button("Connect to Snowflake", use_container_width=True,
                type="primary" if t["sql_input_mode"] == "snowflake" else "secondary"):
                tables[tidx].update({"sql_input_mode": "snowflake", "upload_alias_confirmed": False})
                st.rerun()
        with mode_col3:
            if st.button("Paste DDL", use_container_width=True,
                type="primary" if t["sql_input_mode"] == "upload" else "secondary"):
                tables[tidx].update({"sql_input_mode": "upload", "sf_alias_confirmed": False})
                st.rerun()

        st.markdown(" ")

        if t["sql_input_mode"] == "manual":
            _render_manual(tables, tidx)
        elif t["sql_input_mode"] == "snowflake":
            _render_snowflake(tables, tidx)
        elif t["sql_input_mode"] == "upload":
            _render_ddl(tables, tidx)

    else:
        st.subheader(f"SQL Preview — {t['name']}")
        st.code(t["generated_sql"], language="sql")

        all_sql_done       = all(tbl.get("generated_sql") for tbl in st.session_state.bundle_tables)
        is_last_table_empty = not t.get("generated_sql") and tidx > 0

        if is_last_table_empty:
            st.warning("This table has no SQL yet.")
            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button("← Discard & Go Back", use_container_width=True):
                    st.session_state.bundle_tables.pop(tidx)
                    st.session_state.bundle_table_idx = len(st.session_state.bundle_tables) - 1
                    st.rerun()
            with bc2:
                if st.button("Continue Filling SQL", use_container_width=True, type="primary"):
                    tables[tidx]["sql_preview_mode"] = False
                    st.rerun()
        else:
            pc1, pc2, pc3, pc4 = st.columns(4)
            with pc1:
                if st.button("Edit SQL"):
                    tables[tidx].update({"sql_preview_mode": False, "generated_sql": "", "sf_alias_confirmed": False})
                    st.rerun()
            with pc2:
                if len(st.session_state.bundle_tables) > 1:
                    if st.button("🗑️ Delete Table", use_container_width=True):
                        st.session_state.bundle_tables.pop(tidx)
                        st.session_state.bundle_table_idx = min(tidx, len(st.session_state.bundle_tables) - 1)
                        st.rerun()
                else:
                    st.button("🗑️ Delete Table", disabled=True, use_container_width=True, help="Cannot delete the only table.")
            with pc3:
                if st.button("Add Another Table", use_container_width=True):
                    st.session_state.bundle_tables.append(new_table())
                    st.session_state.bundle_table_idx = len(st.session_state.bundle_tables) - 1
                    st.rerun()
            with pc4:
                if all_sql_done:
                    if st.button("Continue to Table YAML", use_container_width=True, type="primary"):
                        st.session_state.bundle_tables = [t for t in st.session_state.bundle_tables if t.get("generated_sql")]
                        st.session_state.bundle_table_idx = 0
                        st.session_state.bundle_step = 2
                        st.rerun()
                else:
                    st.info("Complete SQL for all tables first.")