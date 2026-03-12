"""
history.py — SQLite-backed generation history for DP YAML Generator.

DB file: history.db  (sits next to app.py, auto-created on first run)

Schema
──────
generation_history
  id          INTEGER  PK AUTOINCREMENT
  created_at  TEXT     ISO-8601 timestamp
  dp_type     TEXT     'CADP' | 'SADP' | 'Specific'
  file_type   TEXT     'bundle' | 'spec' | 'scanner' | 'lens' | 'table' |
                       'view' | 'sql' | 'depot' | 'secret_r' | 'secret_rw' |
                       'flare' | 'quality_checks' | 'user_groups' |
                       'repo_cred' | 'zip_cadp' | 'zip_sadp' | 'zip_sm' | 'zip_depot'
  file_name   TEXT     e.g. 'sales-bundle.yml'
  content     TEXT     raw YAML / SQL / base64-zip bytes as text
  dp_name     TEXT     optional — data product name (from flow)
  is_zip      INTEGER  0 or 1

Auto-cleanup: entries older than 30 days are deleted on every init_db() call.
"""

import os
import sqlite3
import datetime

# ── DB path — same directory as app.py ───────────────────────────────────────
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "history.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create table if not exists, and prune entries older than 30 days."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generation_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT    NOT NULL,
                dp_type    TEXT    NOT NULL,
                file_type  TEXT    NOT NULL,
                file_name  TEXT    NOT NULL,
                content    TEXT    NOT NULL,
                dp_name    TEXT    DEFAULT '',
                is_zip     INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        # Auto-prune entries older than 30 days
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=30)).isoformat()
        conn.execute(
            "DELETE FROM generation_history WHERE created_at < ?", (cutoff,)
        )
        conn.commit()


def save_entry(
    dp_type:   str,
    file_type: str,
    file_name: str,
    content:   str,
    dp_name:   str = "",
    is_zip:    bool = False,
) -> int:
    """
    Insert one history record. Returns the new row id.

    Parameters
    ──────────
    dp_type   : 'CADP' | 'SADP' | 'Specific'
    file_type : short key, e.g. 'bundle', 'lens', 'zip_cadp'
    file_name : filename shown to user, e.g. 'sales-bundle.yml'
    content   : raw text content (YAML / SQL)
    dp_name   : optional human-readable data product name
    is_zip    : True for ZIP entries (content stored as file list summary)
    """
    init_db()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO generation_history
                (created_at, dp_type, file_type, file_name, content, dp_name, is_zip)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (now, dp_type, file_type, file_name, content, dp_name, int(is_zip)),
        )
        conn.commit()
        return cur.lastrowid


def save_zip_entry(
    dp_type:   str,
    file_type: str,
    file_name: str,
    files:     dict,
    dp_name:   str = "",
) -> int:
    """
    Save a ZIP entry — stores a manifest of included files as content
    (not the binary zip itself, since we want it human-readable in history).
    Also saves each individual file inside the ZIP as its own row.

    Returns the row id of the ZIP entry.
    """
    init_db()
    # Build manifest text
    manifest_lines = [f"ZIP: {file_name}", f"Data Product: {dp_name}", "Files included:"]
    manifest_lines += [f"  - {path}" for path in sorted(files.keys())]
    manifest = "\n".join(manifest_lines)

    zip_id = save_entry(
        dp_type=dp_type,
        file_type=file_type,
        file_name=file_name,
        content=manifest,
        dp_name=dp_name,
        is_zip=True,
    )

    # Save each individual file inside the ZIP
    for path, content in files.items():
        if not content:
            continue
        fname = path.split("/")[-1]
        ext   = fname.rsplit(".", 1)[-1] if "." in fname else ""
        ftype = _infer_file_type(fname, ext)
        save_entry(
            dp_type=dp_type,
            file_type=ftype,
            file_name=fname,
            content=content,
            dp_name=dp_name,
            is_zip=False,
        )

    return zip_id


def _infer_file_type(fname: str, ext: str) -> str:
    """Guess file_type label from filename."""
    name = fname.lower()
    if name.endswith(".sql"):              return "sql"
    if "secret-r"  in name or "-r.yml" in name:  return "secret_r"
    if "secret-rw" in name or "-rw.yml" in name: return "secret_rw"
    if "scanner"   in name:               return "scanner"
    if "bundle"    in name:               return "bundle"
    if "spec"      in name:               return "spec"
    if "flare"     in name:               return "flare"
    if "depot"     in name:               return "depot"
    if "lens"      in name or "deployment" in name: return "lens"
    if "user_group" in name:              return "user_groups"
    if "repo" in name or "cred" in name:  return "repo_cred"
    if "quality" in name or "qc" in name: return "quality_checks"
    if "view"      in name:               return "view"
    if "table"     in name:               return "table"
    return ext or "yaml"


def get_history(
    dp_type:   str = None,
    file_type: str = None,
    limit:     int = 200,
) -> list[dict]:
    """
    Fetch history rows, newest first.
    Optionally filter by dp_type and/or file_type.
    Excludes ZIP entries by default — pass file_type='zip_*' to include them.
    Returns list of dicts.
    """
    init_db()
    query  = "SELECT * FROM generation_history WHERE 1=1"
    params = []
    if dp_type:
        query  += " AND dp_type = ?"
        params.append(dp_type)
    if file_type:
        query  += " AND file_type = ?"
        params.append(file_type)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_entry(entry_id: int) -> dict | None:
    """Fetch a single entry by id."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM generation_history WHERE id = ?", (entry_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_entry(entry_id: int):
    """Delete a single history entry."""
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM generation_history WHERE id = ?", (entry_id,))
        conn.commit()


def clear_all():
    """Wipe the entire history table."""
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM generation_history")
        conn.commit()


def get_stats() -> dict:
    """Return summary counts for the history dashboard."""
    init_db()
    with _connect() as conn:
        total   = conn.execute("SELECT COUNT(*) FROM generation_history").fetchone()[0]
        cadp    = conn.execute("SELECT COUNT(*) FROM generation_history WHERE dp_type='CADP'").fetchone()[0]
        sadp    = conn.execute("SELECT COUNT(*) FROM generation_history WHERE dp_type='SADP'").fetchone()[0]
        spec    = conn.execute("SELECT COUNT(*) FROM generation_history WHERE dp_type='Specific'").fetchone()[0]
        zips    = conn.execute("SELECT COUNT(*) FROM generation_history WHERE is_zip=1").fetchone()[0]
        oldest  = conn.execute("SELECT MIN(created_at) FROM generation_history").fetchone()[0]
    return {
        "total":   total,
        "cadp":    cadp,
        "sadp":    sadp,
        "specific": spec,
        "zips":    zips,
        "oldest":  oldest,
    }