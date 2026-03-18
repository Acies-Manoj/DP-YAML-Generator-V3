"""
utils/deployer.py — CLI deployment engine for Sequence Runner.

Builds dataos-ctl commands, runs them via subprocess, and streams
output line-by-line. The only auto-detection here is is_dp_spec()
which reads one line to decide between `dataos-ctl apply` vs
`dataos-ctl product apply`.
"""

import os
import subprocess


# ── DP Spec detection ─────────────────────────────────────────────────────────

def is_dp_spec(yaml_content: str) -> bool:
    """Return True if the YAML file is a DP Spec (entity: product)."""
    return "entity: product" in yaml_content


# ── Command builder ───────────────────────────────────────────────────────────

def build_command(ctl_dir: str, action: str, abs_path: str, yaml_content: str = "") -> list:
    """
    Build the full CLI command as a list of strings.

    Regular file:   [ctl_exe, action, "-f", abs_path]
    DP Spec file:   [ctl_exe, "product", action, "-f", abs_path]

    dataos-ctl is used as-is — no .exe suffix.

    Parameters
    ──────────
    ctl_dir      : folder where dataos-ctl lives
    action       : "apply" or "delete"
    abs_path     : full absolute path to the YAML file on disk
    yaml_content : raw YAML string — used only for dp_spec detection
    """
    ctl_exe = os.path.join(ctl_dir.rstrip("/\\"), "dataos-ctl")

    if is_dp_spec(yaml_content):
        return [ctl_exe, "product", action, "-f", abs_path]
    return [ctl_exe, action, "-f", abs_path]


def format_command_display(cmd: list) -> str:
    """
    Return a human-readable command string for display in the UI.

    Only the file path (last element, after -f) is quoted.
    The exe and all flags are shown as-is — matching exactly what
    you would type in CMD.

    e.g.  dataos-ctl delete -f "C:\\...\\bundle.yml"
          dataos-ctl product apply -f "C:\\...\\spec.yml"
    """
    if not cmd:
        return ""
    parts = []
    for i, part in enumerate(cmd):
        # Only quote the last element — the file path
        if i == len(cmd) - 1:
            parts.append(f'"{part}"')
        else:
            parts.append(part)
    return " ".join(parts)


# ── Command runner ────────────────────────────────────────────────────────────

def run_command(cmd: list):
    """
    Execute a CLI command and yield output events.

    Yields
    ──────
    ("line", str)   — one line of stdout/stderr output
    ("done", int)   — process exit code (0 = success, non-zero = failure)

    Windows fix: dataos-ctl output is UTF-8 (includes emoji like ✅ ❌ 🚀).
    We force encoding="utf-8" + errors="replace" so that any character that
    can't be decoded is shown as a replacement char (?) instead of crashing
    with a UnicodeDecodeError / charmap error.

    We also set PYTHONIOENCODING and the Windows console code page (chcp 65001)
    via env so the subprocess itself emits clean UTF-8.
    """
    try:
        # On Windows, ensure the child process outputs UTF-8.
        # PYTHONUTF8=1  — tells Python subprocesses to default to UTF-8
        # PYTHONIOENCODING=utf-8 — belt-and-suspenders for Python children
        env = os.environ.copy()
        env["PYTHONUTF8"]        = "1"
        env["PYTHONIOENCODING"]  = "utf-8"

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            # Do NOT use text=True here — we decode manually so we can
            # control the encoding and error handler.
            text=False,
            bufsize=0,
            env=env,
        )

        for raw_line in iter(process.stdout.readline, b""):
            # Decode as UTF-8; replace any byte that can't be decoded
            # (e.g. stray Windows-1252 chars) with the Unicode replacement char.
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            if line:
                yield ("line", line)

        process.stdout.close()
        process.wait()
        yield ("done", process.returncode)

    except FileNotFoundError:
        yield ("line", f"ERROR: dataos-ctl not found at: {cmd[0]}")
        yield ("line", "Check that the CTL Directory path is correct and dataos-ctl is installed.")
        yield ("done", 1)

    except PermissionError:
        yield ("line", f"ERROR: Permission denied running: {cmd[0]}")
        yield ("line", "You may need to make the file executable or run as administrator.")
        yield ("done", 1)

    except Exception as exc:
        yield ("line", f"ERROR: Unexpected error — {exc}")
        yield ("done", 1)