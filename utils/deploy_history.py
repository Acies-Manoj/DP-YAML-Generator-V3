"""
utils/deploy_history.py — Run history / audit log for Sequence Runner.

Stores every sequence execution in the existing history.db file
under a new table: deploy_runs.

Schema
──────
deploy_runs
  id             INTEGER  PK AUTOINCREMENT
  ran_at         TEXT     ISO-8601 timestamp
  sequence_name  TEXT     e.g. "Changed - Lens" or "Manual"
  total_steps    INTEGER
  ran_steps      INTEGER  how many actually executed (< total if stopped early)
  status         TEXT     "success" | "failed" | "partial"
  failed_step    INTEGER  1-based, NULL if success
  duration_s     REAL     total wall-clock seconds
  steps_json     TEXT     JSON — list of step result dicts

Auto-cleanup: entries older than 60 days pruned on init.
"""

import json
import os
import sqlite3
import datetime

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "history.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_deploy_history() -> None:
    """Create table if not exists and prune old entries."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deploy_runs (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                ran_at         TEXT    NOT NULL,
                sequence_name  TEXT    NOT NULL,
                total_steps    INTEGER NOT NULL,
                ran_steps      INTEGER NOT NULL,
                status         TEXT    NOT NULL,
                failed_step    INTEGER,
                duration_s     REAL,
                steps_json     TEXT    NOT NULL
            )
        """)
        conn.commit()
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=60)).isoformat()
        conn.execute("DELETE FROM deploy_runs WHERE ran_at < ?", (cutoff,))
        conn.commit()


def save_run(
    sequence_name: str,
    results: list,
    failed_at: int | None,
    total_steps: int,
) -> None:
    """
    Persist one sequence execution.

    Parameters
    ──────────
    sequence_name : display name ("Changed - Lens" or "Manual")
    results       : list of step result dicts from render_run
    failed_at     : 1-based step number of failure, None if all succeeded
    total_steps   : total steps in sequence (including not-run ones)
    """
    init_deploy_history()

    ran_steps  = len(results)
    duration_s = round(sum(r.get("elapsed", 0) for r in results), 2)

    if failed_at is None:
        status = "success"
    elif ran_steps < total_steps:
        status = "partial"
    else:
        status = "failed"

    # Strip large output lines to keep DB lean — keep last 20 lines per step
    slim_results = []
    for r in results:
        slim_results.append({
            "step_n":   r.get("step_n"),
            "action":   r.get("action"),
            "filename": r.get("filename"),
            "rel_path": r.get("rel_path"),
            "status":   r.get("status"),
            "elapsed":  r.get("elapsed"),
            "rc":       r.get("rc"),
            "output":   r.get("lines", [])[-20:],   # last 20 lines only
        })

    now = datetime.datetime.now().isoformat(timespec="seconds")

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO deploy_runs
                (ran_at, sequence_name, total_steps, ran_steps,
                 status, failed_step, duration_s, steps_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now, sequence_name, total_steps, ran_steps,
                status, failed_at, duration_s,
                json.dumps(slim_results),
            ),
        )
        conn.commit()


def get_recent_runs(limit: int = 15) -> list:
    """Return the most recent deploy runs, newest first."""
    init_deploy_history()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM deploy_runs ORDER BY ran_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    runs = []
    for row in rows:
        d = dict(row)
        d["steps"] = json.loads(d.pop("steps_json", "[]"))
        runs.append(d)
    return runs


def clear_runs() -> None:
    """Wipe all deploy run history."""
    init_deploy_history()
    with _connect() as conn:
        conn.execute("DELETE FROM deploy_runs")
        conn.commit()