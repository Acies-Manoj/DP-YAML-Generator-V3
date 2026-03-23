"""
DDL parser.
Parses a Snowflake CREATE [OR REPLACE] TABLE statement to extract
database, schema, table name, and column definitions with their types.

Example input:
    CREATE OR REPLACE TABLE TRAINING_OBS.SAMPLE_MANOJ.ACCOUNTS (
        ACCOUNT_ID VARCHAR(16777216),
        ACCOUNT_NAME VARCHAR(16777216),
        CUSTOMER_ID NUMBER(38,0) NOT NULL,
        CREATED_AT TIMESTAMP_NTZ(9)
    );

Used by: pages/1_CADP.py (SQL Builder — Paste DDL mode)
"""

import re


# Map Snowflake DDL base types → YAML dimension types
_TYPE_MAP = {
    "VARCHAR": "string", "TEXT": "string", "STRING": "string",
    "CHAR": "string", "NCHAR": "string", "NVARCHAR": "string",
    "NVARCHAR2": "string", "VARIANT": "string", "OBJECT": "string", "ARRAY": "string",
    "NUMBER": "number", "INT": "number", "INTEGER": "number",
    "BIGINT": "number", "SMALLINT": "number", "TINYINT": "number",
    "BYTEINT": "number", "FLOAT": "number", "FLOAT4": "number",
    "FLOAT8": "number", "DOUBLE": "number", "REAL": "number",
    "DECIMAL": "number", "NUMERIC": "number", "FIXED": "number",
    "BOOLEAN": "boolean",
    "DATE": "time",
    "TIMESTAMP": "time", "TIMESTAMP_NTZ": "time", "TIMESTAMP_LTZ": "time",
    "TIMESTAMP_TZ": "time", "DATETIME": "time", "TIME": "time",
}


def _map_type(raw_type: str) -> str:
    base = raw_type.split("(")[0].strip().upper()
    return _TYPE_MAP.get(base, "string")


def parse_ddl(ddl_text: str) -> dict:
    """
    Parse a Snowflake CREATE [OR REPLACE] TABLE DDL statement.

    Returns:
        {
          "db":      str,
          "schema":  str,
          "table":   str,
          "columns": [{"original": str, "alias": str, "snowflake_type": str, "mapped_type": str}]
        }
    """
    text = ddl_text.strip()

    # ── 1. Extract table name (db.schema.table / schema.table / table) ────────
    table_match = re.search(
        r'CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+([\w\."]+(?:\.[\w\."]+)*)',
        text, re.IGNORECASE
    )
    db, schema, table = "", "", ""
    if table_match:
        parts = [p.strip('"') for p in table_match.group(1).split(".")]
        if len(parts) == 3:
            db, schema, table = parts
        elif len(parts) == 2:
            schema, table = parts
        else:
            table = parts[0]

    # ── 2. Extract column block between the outermost ( ... ) ─────────────────
    paren_match = re.search(r'\((.*)\)', text, re.DOTALL)
    columns = []
    if paren_match:
        col_block = paren_match.group(1)

        # Split on commas that are NOT inside parentheses (handles VARCHAR(255))
        col_defs = _split_col_defs(col_block)

        for raw in col_defs:
            raw = raw.strip()
            if not raw:
                continue

            # Skip table-level constraints (PRIMARY KEY, UNIQUE, FOREIGN KEY, etc.)
            if re.match(r'(PRIMARY\s+KEY|UNIQUE|FOREIGN\s+KEY|CONSTRAINT|CHECK)\b',
                        raw, re.IGNORECASE):
                continue

            # Match: COL_NAME  TYPE[(size)] [optional modifiers]
            col_match = re.match(
                r'[""]?(\w+)[""]?\s+([\w]+(?:\([\d\s,]+\))?)',
                raw, re.IGNORECASE
            )
            if col_match:
                col_name  = col_match.group(1)
                raw_type  = col_match.group(2)
                columns.append({
                    "original":      col_name,
                    "alias":         col_name.lower(),
                    "snowflake_type": raw_type.upper(),
                    "mapped_type":   _map_type(raw_type),
                })

    return {"db": db, "schema": schema, "table": table, "columns": columns}


def _split_col_defs(col_block: str) -> list:
    """Split column definitions by comma, ignoring commas inside parentheses."""
    parts = []
    depth = 0
    current = []
    for ch in col_block:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return parts


# ── Keep old name as alias so nothing else breaks ─────────────────────────────
def parse_sql_file(sql_text: str) -> dict:
    """Alias for parse_ddl — kept for backward compatibility."""
    return parse_ddl(sql_text)