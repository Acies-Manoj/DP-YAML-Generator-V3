"""
pages/12_Sequence_Runner.py — Sequence Runner sub-application.

Flow:
  Screen 1 (setup)  — Configure CTL/DP paths, scan folder, select changed files
  Screen 2 (build)  — Build the deployment sequence step by step, save as playbook
  Screen 3 (run)    — Execute the sequence with live CLI output per step
"""

import os
import sys
import time

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

st.set_page_config(page_title="Sequence Runner", layout="wide")

from utils.ui_utils       import load_global_css, render_sidebar, app_footer, section_header
from utils.folder_scanner import scan_folder
from utils.deployer       import build_command, run_command, format_command_display
from utils.sequences      import load_sequences, save_sequence, delete_sequence
from utils.deploy_history import save_run, get_recent_runs, init_deploy_history

load_global_css()
render_sidebar()
init_deploy_history()

# ── .env helpers ──────────────────────────────────────────────────────────────
try:
    from dotenv import dotenv_values, set_key as _dotenv_set_key
    _ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")

    def _get_env(key: str) -> str:
        return dotenv_values(_ENV_PATH).get(key, "") or ""

    def _set_env(key: str, val: str) -> None:
        _dotenv_set_key(_ENV_PATH, key, val)
except ImportError:
    def _get_env(key: str) -> str:
        return os.environ.get(key, "")
    def _set_env(key: str, val: str) -> None:
        pass

# ── Session-state initialisation ──────────────────────────────────────────────
_DEFAULTS: dict = {
    "sr_screen":            "setup",
    "sr_ctl_dir":           "",
    "sr_dp_dir":            "",
    "sr_scanned":           False,
    "sr_all_files":         [],
    "sr_model_files":       [],
    "sr_selected_rels":     set(),
    "sr_steps":             [],
    "sr_run_results":       [],
    "sr_execute_now":       False,
    "sr_run_done":          False,
    "sr_failed_at":         None,
    "sr_selected_playbook": None,
    "sr_confirm_delete":    None,   # name of playbook pending delete confirmation
    "sr_rescan_warning":    None,   # warning msg when files dropped from selection on rescan
    "sr_current_seq_name":  None,   # name of sequence being run (for history)
    "sr_stop_on_failure":          True,   # True = stop on first failure, False = run all steps
    "sr_confirm_clear_history": False,  # confirm before wiping run history
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

if not st.session_state.sr_ctl_dir:
    st.session_state.sr_ctl_dir = _get_env("DATAOS_CTL_DIR")
if not st.session_state.sr_dp_dir:
    st.session_state.sr_dp_dir = _get_env("DATAOS_DP_DIR")

# ── Page-level CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── File rows ───────────────────────────────────────────────── */
.sr-file-row {
    display: flex;
    align-items: center;
    padding: 8px 14px;
    margin-bottom: 3px;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 7px;
    font-size: 13px;
    gap: 10px;
}
.sr-file-row:hover { background: #f9fafb; border-color: #d1d5db; }
.sr-filename { font-weight: 500; color: #111827; }

/* ── Step number circle ──────────────────────────────────────── */
.sr-step-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px; height: 22px;
    border-radius: 50%;
    background: #dbeafe;
    color: #1d4ed8;
    font-size: 11px;
    font-weight: 700;
    flex-shrink: 0;
    vertical-align: middle;
    margin-right: 6px;
}

/* ── Action badges ───────────────────────────────────────────── */
.badge-delete {
    display: inline-block;
    background: #fef2f2;
    color: #dc2626;
    padding: 2px 9px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    vertical-align: middle;
    margin-right: 6px;
    border: 1px solid #fecaca;
}
.badge-apply {
    display: inline-block;
    background: #f0fdf4;
    color: #16a34a;
    padding: 2px 9px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    vertical-align: middle;
    margin-right: 6px;
    border: 1px solid #bbf7d0;
}

/* ── Run step headers ────────────────────────────────────────── */
.sr-run-step-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px 8px 0 0;
    font-size: 13px;
    margin-top: 14px;
}
.sr-run-step-header.success { background: #f0fdf4; border-color: #86efac; }
.sr-run-step-header.failed  { background: #fef2f2; border-color: #fecaca; }
.sr-run-step-header.skipped { opacity: 0.45; border-radius: 8px; }
.sr-step-filename { font-weight: 600; color: #111827; }
.sr-step-abs {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: #9ca3af;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 420px;
}
.sr-run-status { margin-left: auto; font-size: 12px; white-space: nowrap; }

/* ── Path pill ───────────────────────────────────────────────── */
.sr-path-pill {
    display: inline-block;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    color: #374151;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
    word-break: break-all;
}

/* ── Playbook list row ───────────────────────────────────────── */
.pb-list-row {
    padding: 12px 16px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-left: 3px solid #6366f1;
    border-radius: 8px;
    margin-bottom: 4px;
    transition: border-color 0.15s ease;
}
.pb-list-row.active { border-color: #818cf8; background: #eef2ff; }
.pb-list-row:hover  { border-color: #a5b4fc; background: #f5f3ff; }
.pb-name { font-size: 14px; font-weight: 600; color: #111827; }
.pb-meta { font-size: 12px; color: #6b7280; margin-top: 3px; }

/* ── Playbook detail panel ───────────────────────────────────── */
.pb-detail {
    background: #fafafa;
    border: 1px solid #a5b4fc;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 6px 0 14px 0;
}
.pb-detail-title {
    font-size: 13px;
    font-weight: 700;
    color: #4f46e5;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid #e5e7eb;
}

/* ── Confirm delete box ──────────────────────────────────────── */
.confirm-box {
    padding: 10px 16px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 8px;
    font-size: 13px;
    color: #dc2626;
    margin-bottom: 6px;
}

/* ── History rows ────────────────────────────────────────────── */
.hist-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 9px 14px;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 7px;
    margin-bottom: 4px;
    font-size: 13px;
}
.hist-row.success { border-left: 3px solid #16a34a; }
.hist-row.failed  { border-left: 3px solid #dc2626; }
.hist-row.partial { border-left: 3px solid #d97706; }
.hist-name { font-weight: 600; color: #111827; min-width: 180px; }
.hist-meta { font-size: 11px; color: #6b7280; }
.hist-ts   { font-size: 11px; color: #9ca3af; margin-left: auto; white-space: nowrap; }

/* ── Empty placeholder ───────────────────────────────────────── */
.seq-empty {
    padding: 24px;
    text-align: center;
    color: #9ca3af;
    border: 1px dashed #d1d5db;
    border-radius: 8px;
    font-size: 13px;
}

/* ── Run summary ─────────────────────────────────────────────── */
.run-summary {
    padding: 16px 20px;
    border-radius: 10px;
    margin-top: 16px;
    font-size: 14px;
    line-height: 1.9;
}
.run-summary.success { background: #f0fdf4; border: 1px solid #86efac; color: #15803d; }
.run-summary.failed  { background: #fef2f2; border: 1px solid #fecaca; color: #dc2626; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _abs_path(rel_path: str) -> str:
    return os.path.join(st.session_state.sr_dp_dir, rel_path.replace("/", os.sep))


def _badge(action: str) -> str:
    cls = "badge-delete" if action == "delete" else "badge-apply"
    return f'<span class="{cls}">{action.upper()}</span>'


def _label(text: str, color: str = "#6b7280", size: str = "12px", weight: str = "400") -> str:
    """Inline styled label — use instead of st.caption() for better contrast on dark bg."""
    return f'<p style="font-size:{size};color:{color};font-weight:{weight};margin:4px 0 8px 0;">{text}</p>'


# ════════════════════════════════════════════════════════════════════════════
# SCREEN 1 — SETUP
# ════════════════════════════════════════════════════════════════════════════

def render_setup() -> None:
    st.markdown("## Sequence Runner")
    st.markdown(_label("Configure paths, scan your DP folder, select changed files, then build and run."), unsafe_allow_html=True)

    nav_l, _ = st.columns([1, 6])
    with nav_l:
        if st.button("← Home", key="sr_home"):
            st.session_state.home_screen = "home"
            st.switch_page("app.py")

    st.divider()

    # ── Configuration ─────────────────────────────────────────────────────────
    section_header("⚙️", "Configuration")
    st.markdown(_label("Saved to .env — only needs to be entered once per machine."), unsafe_allow_html=True)

    cfg_c1, cfg_c2 = st.columns(2, gap="large")

    with cfg_c1:
        st.markdown('<p style="font-size:13px;font-weight:600;color:#111827;margin-bottom:6px;">CTL Directory</p>', unsafe_allow_html=True)
        ctl_input = st.text_input("CTL Directory", value=st.session_state.sr_ctl_dir,
            placeholder=r"e.g.  C:\Users\Manoj\Desktop\DataOS\windows-amd64",
            key="sr_ctl_input", label_visibility="collapsed", help="Folder containing dataos-ctl")
        if st.button("Save CTL Path", key="sr_save_ctl", use_container_width=True):
            st.session_state.sr_ctl_dir = ctl_input.strip()
            _set_env("DATAOS_CTL_DIR", ctl_input.strip())
            st.success("CTL path saved.")
        if st.session_state.sr_ctl_dir:
            st.markdown(f'<p style="margin-top:6px;font-size:11px;color:#6b7280;">Saved: <span class="sr-path-pill">{st.session_state.sr_ctl_dir}</span></p>', unsafe_allow_html=True)

    with cfg_c2:
        st.markdown('<p style="font-size:13px;font-weight:600;color:#111827;margin-bottom:6px;">DP Folder Path</p>', unsafe_allow_html=True)
        dp_input = st.text_input("DP Folder Path", value=st.session_state.sr_dp_dir,
            placeholder=r"e.g.  C:\Users\Manoj\Desktop\my-data-product",
            key="sr_dp_input", label_visibility="collapsed", help="Root folder of your Data Product")
        if st.button("Save DP Path", key="sr_save_dp", use_container_width=True):
            st.session_state.sr_dp_dir  = dp_input.strip()
            st.session_state.sr_scanned = False
            _set_env("DATAOS_DP_DIR", dp_input.strip())
            st.success("DP folder path saved.")
        if st.session_state.sr_dp_dir:
            st.markdown(f'<p style="margin-top:6px;font-size:11px;color:#6b7280;">Saved: <span class="sr-path-pill">{st.session_state.sr_dp_dir}</span></p>', unsafe_allow_html=True)

    st.markdown(" ")

    # ── Scan buttons ──────────────────────────────────────────────────────────
    dp_set  = bool(st.session_state.sr_dp_dir.strip())
    scan_c1, scan_c2, _ = st.columns([2, 2, 3])

    with scan_c1:
        if st.button("Scan DP Folder", key="sr_scan_btn", type="primary",
                     disabled=not dp_set, use_container_width=True):
            dp = st.session_state.sr_dp_dir.strip()
            if not os.path.isdir(dp):
                st.error(f"Folder not found: `{dp}`")
                st.stop()
            result = scan_folder(dp)
            new_files = result["deployable"]
            new_rels  = {f["rel_path"] for f in new_files}

            # ── Re-scan: preserve selections that still exist ─────────────────
            old_sel  = st.session_state.sr_selected_rels
            kept     = old_sel & new_rels
            dropped  = old_sel - new_rels
            if dropped and old_sel:
                dropped_names = ", ".join(p.split("/")[-1] for p in sorted(dropped))
                st.session_state.sr_rescan_warning = (
                    f"{len(dropped)} previously selected file{'s' if len(dropped)>1 else ''} "
                    f"no longer found and deselected: {dropped_names}"
                )
            else:
                st.session_state.sr_rescan_warning = None

            st.session_state.sr_all_files         = new_files
            st.session_state.sr_model_files       = result["model_files"]
            st.session_state.sr_scanned           = True
            st.session_state.sr_selected_rels     = kept
            st.session_state.sr_selected_playbook = None
            st.rerun()

    with scan_c2:
        # Re-scan button — only shown after first scan, keeps selections
        if st.session_state.sr_scanned:
            if st.button("Re-scan (keep selection)", key="sr_rescan_btn",
                         disabled=not dp_set, use_container_width=True):
                dp = st.session_state.sr_dp_dir.strip()
                if not os.path.isdir(dp):
                    st.error(f"Folder not found: `{dp}`")
                    st.stop()
                result   = scan_folder(dp)
                new_files = result["deployable"]
                new_rels  = {f["rel_path"] for f in new_files}
                old_sel   = st.session_state.sr_selected_rels
                kept      = old_sel & new_rels
                dropped   = old_sel - new_rels
                if dropped and old_sel:
                    dropped_names = ", ".join(p.split("/")[-1] for p in sorted(dropped))
                    st.session_state.sr_rescan_warning = (
                        f"{len(dropped)} previously selected file{'s' if len(dropped)>1 else ''} "
                        f"no longer found and deselected: {dropped_names}"
                    )
                else:
                    st.session_state.sr_rescan_warning = None
                st.session_state.sr_all_files   = new_files
                st.session_state.sr_model_files = result["model_files"]
                st.session_state.sr_selected_rels = kept
                st.rerun()

    if not dp_set:
        st.markdown(_label("Enter and save the DP Folder Path first."), unsafe_allow_html=True)

    # Show rescan warning once
    if st.session_state.sr_rescan_warning:
        st.warning(st.session_state.sr_rescan_warning)
        st.session_state.sr_rescan_warning = None

    if not st.session_state.sr_scanned:
        app_footer()
        return

    all_files   = st.session_state.sr_all_files
    model_files = st.session_state.sr_model_files

    if not all_files and not model_files:
        st.warning("No YAML files found in the folder.")
        app_footer()
        return

    st.markdown(" ")
    section_header("📋", f"Files Found  ·  {len(all_files)} deployable")
    st.markdown(_label("Check every file you changed. Folders are collapsible — use Select all to check an entire folder at once."), unsafe_allow_html=True)

    # ── 2-level tree ──────────────────────────────────────────────────────────
    from collections import defaultdict
    tree: dict = defaultdict(lambda: defaultdict(list))
    for f in all_files:
        parts = f["rel_path"].split("/")
        top   = parts[0] if len(parts) > 1 else "."
        sub   = "/".join(parts[1:-1]) if len(parts) > 2 else ""
        tree[top][sub].append(f)

    _TOP_COLORS = ["#3b82f6", "#10b981", "#f97316", "#8b5cf6", "#14b8a6", "#f59e0b"]

    # ── Pre-compute global_idx for every file once ────────────────────────────
    # This lets us read checkbox widget state from session state keys
    # (which Streamlit updates BEFORE the script reruns) rather than from
    # sr_selected_rels (which lags one run behind for the expander label).
    file_idx_map = {f["rel_path"]: all_files.index(f) for f in all_files}

    def _is_checked(rel_path: str) -> bool:
        """Read actual current checkbox state from widget key."""
        idx = file_idx_map.get(rel_path)
        if idx is not None and f"sr_chk_{idx}" in st.session_state:
            return bool(st.session_state[f"sr_chk_{idx}"])
        return rel_path in st.session_state.sr_selected_rels

    # Pre-initialize all checkbox keys from sr_selected_rels so Streamlit
    # owns them from the start — this avoids the "default value + session
    # state API" conflict when select-all writes to them directly.
    for _f in all_files:
        _k = f"sr_chk_{file_idx_map[_f['rel_path']]}"
        if _k not in st.session_state:
            st.session_state[_k] = _f["rel_path"] in st.session_state.sr_selected_rels

    for ti, top_folder in enumerate(sorted(tree.keys())):
        sub_map   = tree[top_folder]
        color     = _TOP_COLORS[ti % len(_TOP_COLORS)]
        top_total = sum(len(v) for v in sub_map.values())
        top_files = [f for files in sub_map.values() for f in files]
        top_rels  = [f["rel_path"] for f in top_files]

        # Count for select-all logic only — NOT in the expander label.
        # Putting the count in the label causes the label string to change on
        # every checkbox tick, which makes Streamlit treat it as a new widget
        # and collapse the expander. Label stays stable → expander stays open.
        n_checked = sum(1 for r in top_rels if _is_checked(r))
        exp_label = f"📁  {top_folder}  —  {top_total} file{'s' if top_total != 1 else ''}"

        with st.expander(exp_label, expanded=False):

            # ── Select all checkbox ───────────────────────────────────────────
            all_checked = (n_checked == top_total)
            sa_col, sa_lbl = st.columns([0.4, 10])
            with sa_col:
                select_all = st.checkbox("", value=all_checked, key=f"sr_selall_{ti}",
                                         label_visibility="collapsed")
            with sa_lbl:
                st.markdown('<p style="padding:6px 0 2px 4px;font-size:12px;font-weight:600;color:#374151;margin:0;">Select all in folder</p>', unsafe_allow_html=True)

            # When select-all is toggled, explicitly set every child checkbox
            # widget key so they immediately reflect the new state on rerun.
            if select_all and not all_checked:
                for f in top_files:
                    idx = file_idx_map[f["rel_path"]]
                    st.session_state[f"sr_chk_{idx}"] = True
                    st.session_state.sr_selected_rels.add(f["rel_path"])
                st.rerun()
            elif not select_all and all_checked:
                for f in top_files:
                    idx = file_idx_map[f["rel_path"]]
                    st.session_state[f"sr_chk_{idx}"] = False
                    st.session_state.sr_selected_rels.discard(f["rel_path"])
                st.rerun()

            # ── Individual file checkboxes ────────────────────────────────────
            for sub_folder in sorted(sub_map.keys()):
                files_here = sub_map[sub_folder]
                if sub_folder:
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:6px;margin:12px 0 4px 4px;'
                        f'padding-bottom:4px;border-bottom:1px solid #e5e7eb;">'
                        f'<span style="font-size:12px;">📂</span>'
                        f'<span style="font-size:12px;font-weight:600;color:#374151;">{sub_folder}</span>'
                        f'<span style="font-size:11px;color:#6b7280;margin-left:6px;">'
                        f'{len(files_here)} file{"s" if len(files_here)!=1 else ""}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                for f in files_here:
                    global_idx = file_idx_map[f["rel_path"]]
                    chk_col, info_col = st.columns([0.4, 10])
                    with chk_col:
                        # value= only applies on first render; after that Streamlit
                        # uses the stored widget key. We keep sr_selected_rels in
                        # sync here so the rest of the app can use it normally.
                        # No value= here — session state key owns the state.
                        # Key is pre-initialized above; select-all writes to it directly.
                        checked = st.checkbox(
                            "",
                            key=f"sr_chk_{global_idx}",
                            label_visibility="collapsed",
                        )
                        if checked:
                            st.session_state.sr_selected_rels.add(f["rel_path"])
                        else:
                            st.session_state.sr_selected_rels.discard(f["rel_path"])
                    with info_col:
                        indent = "margin-left:20px;" if sub_folder else "margin-left:4px;"
                        st.markdown(
                            f'<div class="sr-file-row" style="{indent}border-left:2px solid {color}66;">'
                            f'<span style="font-size:11px;color:#9ca3af;margin-right:6px;">└</span>'
                            f'<span class="sr-filename">{f["filename"]}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

    if model_files:
        with st.expander(f"Model files ({len(model_files)}) — part of Lens, not deployed individually", expanded=False):
            from collections import defaultdict as _dd
            model_tree: dict = _dd(lambda: _dd(list))
            for mf in model_files:
                parts = mf["rel_path"].split("/")
                top   = parts[0] if len(parts) > 1 else "."
                sub   = "/".join(parts[1:-1]) if len(parts) > 2 else ""
                model_tree[top][sub].append(mf)
            for top_folder in sorted(model_tree.keys()):
                st.markdown(f'<p style="font-size:12px;font-weight:600;color:#374151;padding:6px 4px 4px 4px;margin-top:6px;">📁 {top_folder}</p>', unsafe_allow_html=True)
                for sub_folder, mfs in sorted(model_tree[top_folder].items()):
                    if sub_folder:
                        st.markdown(f'<p style="font-size:11px;color:#6b7280;padding:3px 4px 3px 12px;margin:0;">📂 {sub_folder}</p>', unsafe_allow_html=True)
                    for mf in mfs:
                        st.markdown(
                            f'<div class="sr-file-row" style="opacity:0.5;margin-left:20px;border-left:2px solid #e5e7eb;">'
                            f'<span style="font-size:11px;color:#9ca3af;margin-right:6px;">└</span>'
                            f'<span class="sr-filename">{mf["filename"]}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

    st.markdown(" ")

    # ── Saved Playbooks ───────────────────────────────────────────────────────
    saved = load_sequences()
    if saved:
        st.divider()
        section_header("📚", f"Saved Playbooks  ·  {len(saved)}")
        st.markdown(_label("Select a playbook to preview its steps and load it — or select files manually above."), unsafe_allow_html=True)

        rel_set   = {f["rel_path"] for f in all_files}
        active_pb = st.session_state.sr_selected_playbook
        confirm   = st.session_state.sr_confirm_delete

        for seq in saved:
            steps_in  = seq.get("steps", [])
            n_steps   = len(steps_in)
            ts        = seq.get("updated_at", seq.get("created_at", ""))[:10]
            is_active = (active_pb == seq["name"])
            missing   = [s for s in steps_in if s["rel_path"] not in rel_set]

            warn_pill = (
                f'<span style="font-size:10px;color:#f59e0b;background:#2d1f00;'
                f'border:1px solid #92400e;padding:1px 7px;border-radius:4px;margin-left:8px;">'
                f'{len(missing)} missing</span>'
                if missing else ""
            )
            row_cls = "pb-list-row active" if is_active else "pb-list-row"
            st.markdown(
                f'<div class="{row_cls}">'
                f'  <div class="pb-name">{seq["name"]}{warn_pill}</div>'
                f'  <div class="pb-meta">{n_steps} step{"s" if n_steps!=1 else ""}  ·  {ts}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # ── Row action buttons ─────────────────────────────────────────────
            if confirm == seq["name"]:
                # Confirm-delete state
                st.markdown('<div class="confirm-box">Delete this playbook permanently?</div>', unsafe_allow_html=True)
                cd_yes, cd_no, _ = st.columns([1.2, 1, 5])
                with cd_yes:
                    if st.button("Yes, delete", key=f"sr_cd_yes_{seq['name']}", use_container_width=True):
                        delete_sequence(seq["name"])
                        st.session_state.sr_confirm_delete    = None
                        st.session_state.sr_selected_playbook = None
                        st.rerun()
                with cd_no:
                    if st.button("Cancel", key=f"sr_cd_no_{seq['name']}", use_container_width=True):
                        st.session_state.sr_confirm_delete = None
                        st.rerun()
            else:
                btn_sel, btn_del, _ = st.columns([1, 0.7, 5])
                with btn_sel:
                    if is_active:
                        if st.button("Deselect", key=f"sr_pb_desel_{seq['name']}", use_container_width=True):
                            st.session_state.sr_selected_playbook = None
                            st.rerun()
                    else:
                        if st.button("Select", key=f"sr_pb_sel_{seq['name']}", use_container_width=True):
                            st.session_state.sr_selected_playbook = seq["name"]
                            st.session_state.sr_confirm_delete    = None
                            st.rerun()
                with btn_del:
                    if st.button("Delete", key=f"sr_pb_del_{seq['name']}", use_container_width=True):
                        st.session_state.sr_confirm_delete    = seq["name"]
                        st.session_state.sr_selected_playbook = None
                        st.rerun()

            # ── Detail panel for active playbook ──────────────────────────────
            if is_active:
                step_rows_html = ""
                for idx_s, s in enumerate(steps_in):
                    fname     = s["rel_path"].split("/")[-1]
                    folder    = "/".join(s["rel_path"].split("/")[:-1])
                    is_miss   = s["rel_path"] not in rel_set
                    badge_cls = "badge-delete" if s["action"] == "delete" else "badge-apply"
                    fname_col = "#9ca3af" if is_miss else "#111827"
                    fold_col  = "#9ca3af" if is_miss else "#6b7280"
                    miss_tag  = (
                        '<span style="font-size:10px;color:#f59e0b;background:#2d1f00;'
                        'border:1px solid #92400e;padding:1px 6px;border-radius:4px;'
                        'margin-left:8px;">not found</span>'
                        if is_miss else ""
                    )
                    step_rows_html += (
                        f'<div style="display:flex;align-items:center;gap:10px;'
                        f'padding:7px 0;border-bottom:1px solid #f3f4f6;">'
                        f'<span style="font-size:11px;color:#6b7280;width:20px;'
                        f'text-align:right;flex-shrink:0;">{idx_s+1}</span>'
                        f'<span class="{badge_cls}" style="flex-shrink:0;width:56px;'
                        f'text-align:center;">{s["action"].upper()}</span>'
                        f'<span style="font-size:13px;font-weight:500;color:{fname_col};'
                        f'min-width:160px;">{fname}</span>'
                        f'<span style="font-size:11px;color:{fold_col};font-family:monospace;">{folder}</span>'
                        f'{miss_tag}</div>'
                    )

                warn_html = ""
                if missing:
                    mnames = ", ".join(s["rel_path"].split("/")[-1] for s in missing)
                    warn_html = (
                        f'<div style="margin-top:10px;padding:8px 12px;background:#1c1200;'
                        f'border:1px solid #f59e0b;border-radius:6px;font-size:12px;color:#d97706;">'
                        f'{len(missing)} file{"s" if len(missing)>1 else ""} not found in current '
                        f'folder — steps load anyway, remove before running: {mnames}</div>'
                    )

                st.markdown(
                    f'<div class="pb-detail">'
                    f'  <div class="pb-detail-title">Steps in "{seq["name"]}"</div>'
                    f'  {step_rows_html}{warn_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if st.button(f"Load & Continue  —  {seq['name']}",
                             key=f"sr_pb_load_{seq['name']}", type="primary",
                             use_container_width=True):
                    st.session_state.sr_selected_rels = {
                        s["rel_path"] for s in steps_in if s["rel_path"] in rel_set
                    }
                    st.session_state.sr_steps = [
                        {"action": s["action"], "rel_path": s["rel_path"],
                         "abs_path": _abs_path(s["rel_path"]),
                         "filename": s["rel_path"].split("/")[-1]}
                        for s in steps_in
                    ]
                    st.session_state.sr_run_results       = []
                    st.session_state.sr_run_done          = False
                    st.session_state.sr_failed_at         = None
                    st.session_state.sr_selected_playbook = None
                    st.session_state.sr_current_seq_name  = seq["name"]
                    st.session_state.sr_screen            = "build"
                    st.rerun()

                st.markdown(" ")

    # ── Continue button ───────────────────────────────────────────────────────
    n_sel = len(st.session_state.sr_selected_rels)
    bot_l, _, bot_r = st.columns([3, 4, 2])
    with bot_l:
        if n_sel:
            st.success(f"**{n_sel}** file{'s' if n_sel > 1 else ''} selected.")
        else:
            st.markdown(_label("Select files manually above — or use a saved playbook."), unsafe_allow_html=True)
    with bot_r:
        if st.button("Build Sequence →", key="sr_to_build", type="primary",
                     disabled=(n_sel == 0), use_container_width=True):
            st.session_state.sr_steps            = []
            st.session_state.sr_run_results      = []
            st.session_state.sr_run_done         = False
            st.session_state.sr_current_seq_name = "Manual"
            st.session_state.sr_screen           = "build"
            st.rerun()

    app_footer()


# ════════════════════════════════════════════════════════════════════════════
# SCREEN 2 — BUILD
# ════════════════════════════════════════════════════════════════════════════

def render_build() -> None:
    st.markdown("## Build Sequence")
    st.markdown(_label("Click + Delete or + Apply on each file to add steps in order. Reorder and remove as needed."), unsafe_allow_html=True)

    nav_l, _ = st.columns([1, 6])
    with nav_l:
        if st.button("← Back", key="sr_build_back"):
            st.session_state.sr_screen = "setup"
            st.rerun()

    st.divider()

    sel_rels  = st.session_state.sr_selected_rels
    all_files = st.session_state.sr_all_files
    sel_files = [f for f in all_files if f["rel_path"] in sel_rels]

    section_header("📁", "Selected Files — Add to Sequence")
    st.markdown(" ")

    for f in sel_files:
        fc_name, fc_del, fc_apl = st.columns([6, 1.5, 1.5])
        with fc_name:
            st.markdown(
                f'<div style="padding:8px 0 6px 0;">'
                f'<span style="font-size:13px;font-weight:500;color:#111827;">{f["filename"]}</span>'
                f'&nbsp;&nbsp;<span style="font-size:11px;color:#6b7280;font-family:monospace;">{f["rel_path"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with fc_del:
            if st.button("+ Delete", key=f"sr_add_del_{f['rel_path']}", use_container_width=True):
                st.session_state.sr_steps.append({
                    "action": "delete", "rel_path": f["rel_path"],
                    "abs_path": _abs_path(f["rel_path"]), "filename": f["filename"],
                })
                st.rerun()
        with fc_apl:
            if st.button("+ Apply", key=f"sr_add_apl_{f['rel_path']}", use_container_width=True):
                st.session_state.sr_steps.append({
                    "action": "apply", "rel_path": f["rel_path"],
                    "abs_path": _abs_path(f["rel_path"]), "filename": f["filename"],
                })
                st.rerun()

    st.markdown(" ")
    st.divider()

    steps = st.session_state.sr_steps

    hdr_l, hdr_r = st.columns([6, 1.5])
    with hdr_l:
        section_header("🔢", f"Sequence  ·  {len(steps)} step{'s' if len(steps) != 1 else ''}")
    with hdr_r:
        st.markdown("<br>", unsafe_allow_html=True)
        if steps and st.button("Clear All", key="sr_clear_all", use_container_width=True):
            st.session_state.sr_steps = []
            st.rerun()

    st.markdown(" ")

    if not steps:
        st.markdown('<div class="seq-empty">No steps yet — click + Delete or + Apply above</div>', unsafe_allow_html=True)
    else:
        for i, step in enumerate(steps):
            sc_num, sc_action, sc_fname, sc_up, sc_dn, sc_rm = st.columns([0.45, 1.6, 6, 0.45, 0.45, 0.45])

            with sc_num:
                st.markdown(f'<div style="padding-top:7px;text-align:center;"><span class="sr-step-num">{i+1}</span></div>', unsafe_allow_html=True)

            with sc_action:
                new_action = st.selectbox("", options=["delete", "apply"],
                    index=0 if step["action"] == "delete" else 1,
                    key=f"sr_action_{i}", label_visibility="collapsed")
                if new_action != step["action"]:
                    st.session_state.sr_steps[i]["action"] = new_action

            with sc_fname:
                st.markdown(
                    f'<div style="padding:7px 0 4px 0;font-size:13px;">'
                    f'<span style="color:#111827;font-weight:500;">{step["filename"]}</span>'
                    f'&nbsp;&nbsp;<span style="font-size:11px;color:#6b7280;font-family:monospace;">{step["rel_path"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with sc_up:
                if st.button("↑", key=f"sr_up_{i}", disabled=(i==0), use_container_width=True):
                    st.session_state.sr_steps[i], st.session_state.sr_steps[i-1] = st.session_state.sr_steps[i-1], st.session_state.sr_steps[i]
                    k_i, k_p = f"sr_action_{i}", f"sr_action_{i-1}"
                    st.session_state[k_i], st.session_state[k_p] = st.session_state.get(k_p, steps[i-1]["action"]), st.session_state.get(k_i, steps[i]["action"])
                    st.rerun()

            with sc_dn:
                if st.button("↓", key=f"sr_dn_{i}", disabled=(i==len(steps)-1), use_container_width=True):
                    st.session_state.sr_steps[i], st.session_state.sr_steps[i+1] = st.session_state.sr_steps[i+1], st.session_state.sr_steps[i]
                    k_i, k_n = f"sr_action_{i}", f"sr_action_{i+1}"
                    st.session_state[k_i], st.session_state[k_n] = st.session_state.get(k_n, steps[i+1]["action"]), st.session_state.get(k_i, steps[i]["action"])
                    st.rerun()

            with sc_rm:
                if st.button("✕", key=f"sr_rm_{i}", use_container_width=True):
                    st.session_state.sr_steps.pop(i)
                    st.rerun()

    st.markdown(" ")

    # ── Save as Playbook ──────────────────────────────────────────────────────
    if steps:
        st.divider()
        section_header("💾", "Save as Playbook")
        st.markdown(_label("Saves with relative paths — reusable on any DP folder."), unsafe_allow_html=True)

        sv_name, sv_btn = st.columns([5, 1.5])
        with sv_name:
            pb_name = st.text_input("Playbook Name", placeholder="e.g.  Redeploy after SM change",
                                    key="sr_pb_name_input", label_visibility="collapsed")
        with sv_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Save Playbook", key="sr_save_pb", use_container_width=True):
                name = pb_name.strip()
                if not name:
                    st.warning("Enter a name first.")
                else:
                    save_sequence(name, [{"action": s["action"], "rel_path": s["rel_path"]} for s in steps])
                    st.success(f"Playbook **{name}** saved ✓")

    st.markdown(" ")

    # ── Saved Playbooks (Build screen) ────────────────────────────────────────
    saved   = load_sequences()
    confirm = st.session_state.sr_confirm_delete

    with st.expander(f"Saved Playbooks ({len(saved)})", expanded=(len(saved) > 0 and not steps)):
        if not saved:
            st.markdown(_label("No saved playbooks yet."), unsafe_allow_html=True)
        else:
            for seq in saved:
                n_steps = len(seq.get("steps", []))
                ts      = seq.get("updated_at", seq.get("created_at", ""))[:10]

                st.markdown(
                    f'<div class="pb-list-row">'
                    f'  <div class="pb-name">{seq["name"]}</div>'
                    f'  <div class="pb-meta">{n_steps} step{"s" if n_steps!=1 else ""}  ·  {ts}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if confirm == seq["name"]:
                    st.markdown('<div class="confirm-box">Delete this playbook permanently?</div>', unsafe_allow_html=True)
                    cd_y, cd_n, _ = st.columns([1.2, 1, 5])
                    with cd_y:
                        if st.button("Yes, delete", key=f"sr_bcd_yes_{seq['name']}", use_container_width=True):
                            delete_sequence(seq["name"])
                            st.session_state.sr_confirm_delete = None
                            st.rerun()
                    with cd_n:
                        if st.button("Cancel", key=f"sr_bcd_no_{seq['name']}", use_container_width=True):
                            st.session_state.sr_confirm_delete = None
                            st.rerun()
                else:
                    pb_load, pb_del, _ = st.columns([1, 0.7, 5])
                    with pb_load:
                        if st.button("Load", key=f"sr_load_{seq['name']}", use_container_width=True):
                            loaded, missing = [], []
                            for s in seq.get("steps", []):
                                abs_p = _abs_path(s["rel_path"])
                                if os.path.exists(abs_p):
                                    loaded.append({"action": s["action"], "rel_path": s["rel_path"],
                                                   "abs_path": abs_p, "filename": os.path.basename(s["rel_path"])})
                                else:
                                    missing.append(s["rel_path"])
                            st.session_state.sr_steps            = loaded
                            st.session_state.sr_current_seq_name = seq["name"]
                            if missing:
                                st.warning("Files not found:\n" + "\n".join(f"• {p}" for p in missing))
                            else:
                                st.success("Playbook loaded ✓")
                            st.rerun()
                    with pb_del:
                        if st.button("Delete", key=f"sr_bdel_{seq['name']}", use_container_width=True):
                            st.session_state.sr_confirm_delete = seq["name"]
                            st.rerun()

    st.markdown(" ")

    # ── Command preview + Run ─────────────────────────────────────────────────
    if steps:
        if not st.session_state.sr_ctl_dir.strip():
            st.warning("CTL Directory is not set — go back to Setup to configure it.")
        else:
            st.divider()
            section_header("👁", "Command Preview")
            st.markdown(_label("Exact commands that will run — review before executing."), unsafe_allow_html=True)

            preview_lines = []
            for i, step in enumerate(steps):
                yaml_content = ""
                try:
                    with open(step["abs_path"], "r", encoding="utf-8") as fh:
                        yaml_content = fh.read()
                except Exception:
                    pass
                cmd = build_command(st.session_state.sr_ctl_dir.strip(), step["action"],
                                    step["abs_path"], yaml_content)
                preview_lines.append(f"# Step {i+1}")
                preview_lines.append(format_command_display(cmd))
                preview_lines.append("")

            st.code("\n".join(preview_lines).strip(), language="bash")
            st.markdown(" ")

            # ── Failure behaviour toggle ──────────────────────────────────────
            section_header("⚡", "On Step Failure")
            st.markdown(_label(
                "Stop on failure works best for dependent sequences (delete → apply chains). "
                "Run all steps works best for independent files like QC checks."
            ), unsafe_allow_html=True)

            failure_choice = st.radio(
                "On step failure",
                options=["Stop execution", "Run all steps"],
                index=0 if st.session_state.sr_stop_on_failure else 1,
                key="sr_failure_radio",
                label_visibility="collapsed",
                horizontal=True,
            )
            st.session_state.sr_stop_on_failure = (failure_choice == "Stop execution")

            # Visual hint below the radio
            if st.session_state.sr_stop_on_failure:
                st.markdown(
                    '<p style="font-size:12px;color:#d97706;margin:4px 0 12px 0;">'
                    '⚠️  If any step fails, remaining steps will not run.</p>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<p style="font-size:12px;color:#059669;margin:4px 0 12px 0;">'
                    '✓  All steps will run regardless of individual failures.</p>',
                    unsafe_allow_html=True,
                )

            if st.button(f"Run Sequence  ·  {len(steps)} step{'s' if len(steps)!=1 else ''}",
                         key="sr_run_btn", type="primary", use_container_width=True):
                st.session_state.sr_run_results = []
                st.session_state.sr_run_done    = False
                st.session_state.sr_failed_at   = None
                st.session_state.sr_execute_now = True
                st.session_state.sr_screen      = "run"
                st.rerun()

    # ── Run History ───────────────────────────────────────────────────────────
    from utils.deploy_history import clear_runs
    runs = get_recent_runs(15)
    st.markdown(" ")
    with st.expander(f"Run History  ({len(runs)} recent)", expanded=False):
        if not runs:
            st.markdown(_label("No runs recorded yet."), unsafe_allow_html=True)
        else:
            # ── Clear history — confirm before wiping ─────────────────────────
            if st.session_state.get("sr_confirm_clear_history"):
                st.markdown(
                    '<div class="confirm-box">Clear all run history permanently?</div>',
                    unsafe_allow_html=True,
                )
                cc_yes, cc_no, _ = st.columns([1.2, 1, 5])
                with cc_yes:
                    if st.button("Yes, clear", key="sr_clear_hist_yes", use_container_width=True):
                        clear_runs()
                        st.session_state.sr_confirm_clear_history = False
                        st.rerun()
                with cc_no:
                    if st.button("Cancel", key="sr_clear_hist_no", use_container_width=True):
                        st.session_state.sr_confirm_clear_history = False
                        st.rerun()
            else:
                _, clr_col = st.columns([6, 1.5])
                with clr_col:
                    if st.button("Clear History", key="sr_clear_hist_btn", use_container_width=True):
                        st.session_state.sr_confirm_clear_history = True
                        st.rerun()

            for run in runs:
                icon = "✅" if run["status"] == "success" else ("⚠️" if run["status"] == "partial" else "❌")
                ts   = run["ran_at"][:16].replace("T", "  ")
                dur  = f"{run['duration_s']}s" if run["duration_s"] is not None else ""
                st.markdown(
                    f'<div class="hist-row {run["status"]}">'
                    f'  <span style="font-size:14px;">{icon}</span>'
                    f'  <span class="hist-name">{run["sequence_name"]}</span>'
                    f'  <span class="hist-meta">{run["ran_steps"]}/{run["total_steps"]} steps  ·  {dur}</span>'
                    f'  <span class="hist-ts">{ts}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                with st.expander(f"Details — {run['sequence_name']}  {ts}", expanded=False):
                    for s in run.get("steps", []):
                        ok      = s.get("status") == "success"
                        s_icon  = "✅" if ok else "❌"
                        s_col   = "#16a34a" if ok else "#dc2626"
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:10px;'
                            f'padding:5px 0;border-bottom:1px solid #f3f4f6;">'
                            f'<span>{s_icon}</span>'
                            f'{_badge(s.get("action",""))}'
                            f'<span style="font-size:13px;font-weight:500;color:{s_col};">{s.get("filename","")}</span>'
                            f'<span style="font-size:11px;color:#6b7280;margin-left:auto;">{s.get("elapsed","")}s</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        if s.get("output"):
                            with st.expander("Output", expanded=False):
                                st.code("\n".join(s["output"]), language="bash")

    app_footer()


# ════════════════════════════════════════════════════════════════════════════
# SCREEN 3 — RUN
# ════════════════════════════════════════════════════════════════════════════

def render_run() -> None:
    steps   = st.session_state.sr_steps
    ctl_dir = st.session_state.sr_ctl_dir.strip()

    if not st.session_state.sr_execute_now:
        nav_l, _ = st.columns([1, 6])
        with nav_l:
            if st.button("← Edit Sequence", key="sr_run_back"):
                st.session_state.sr_screen = "build"
                st.rerun()

    st.markdown("## Running Sequence")
    st.divider()

    if st.session_state.sr_execute_now:
        st.session_state.sr_execute_now = False
        stop_on_failure = st.session_state.get("sr_stop_on_failure", True)
        results:   list     = []
        failed_at: int|None = None
        total_steps         = len(steps)

        # ── Live progress bar — updates as each step starts ───────────────────
        progress_ph = st.empty()
        status_ph   = st.empty()

        def _update_progress(step_n: int, filename: str, state: str = "running"):
            """Update the top progress indicator in real time."""
            pct  = (step_n - 1) / total_steps
            colors = {
                "running": "#3b82f6",
                "done":    "#16a34a",
                "failed":  "#dc2626",
            }
            col = colors.get(state, "#3b82f6")
            progress_ph.progress(pct, text=f"Step {step_n} of {total_steps}")
            status_ph.markdown(
                f'<div style="padding:8px 14px;background:#f0f9ff;border:1px solid #bae6fd;'
                f'border-radius:8px;margin-bottom:12px;display:flex;align-items:center;gap:10px;">'
                f'<span style="font-size:13px;font-weight:600;color:{col};">'
                f'{"▶ Running" if state=="running" else ("✅ Done" if state=="done" else "❌ Failed")}'
                f'</span>'
                f'<span style="font-size:13px;color:#374151;">{filename}</span>'
                f'<span style="font-size:11px;color:#6b7280;margin-left:auto;">'
                f'Step {step_n} / {total_steps}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        for i, step in enumerate(steps):
            step_n = i + 1

            # Update live progress indicator immediately when step starts
            _update_progress(step_n, step["filename"], "running")

            hdr_ph = st.empty()
            hdr_ph.markdown(
                f'<div class="sr-run-step-header">'
                f'<span class="sr-step-num">{step_n}</span>'
                f'{_badge(step["action"])}'
                f'<span class="sr-step-filename">{step["filename"]}</span>'
                f'<span class="sr-run-status" style="color:#3b82f6;">running...</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            out_ph = st.empty()
            yaml_content = ""
            try:
                with open(step["abs_path"], "r", encoding="utf-8") as fh:
                    yaml_content = fh.read()
            except Exception:
                pass

            cmd     = build_command(ctl_dir, step["action"], step["abs_path"], yaml_content)
            lines   = [f"$ {format_command_display(cmd)}"]
            out_ph.code("\n".join(lines), language="bash")

            rc = 0
            t0 = time.time()
            for evt, val in run_command(cmd):
                if evt == "line":
                    lines.append(val)
                    out_ph.code("\n".join(lines), language="bash")
                else:
                    rc = val

            elapsed = round(time.time() - t0, 1)
            result  = {**step, "step_n": step_n, "status": "success" if rc == 0 else "failed",
                       "lines": lines, "elapsed": elapsed, "rc": rc}
            results.append(result)

            if rc != 0:
                hdr_ph.markdown(
                    f'<div class="sr-run-step-header failed">'
                    f'<span class="sr-step-num">{step_n}</span>'
                    f'{_badge(step["action"])}'
                    f'<span class="sr-step-filename" style="color:#dc2626;">{step["filename"]}</span>'
                    f'<span class="sr-run-status" style="color:#dc2626;">failed  ·  {elapsed}s</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                # Track first failure
                if failed_at is None:
                    failed_at = step_n

                _update_progress(step_n, step["filename"], "failed")

                if stop_on_failure:
                    # Show remaining steps as not-run and stop
                    for j in range(i+1, len(steps)):
                        rem = steps[j]
                        st.markdown(
                            f'<div class="sr-run-step-header skipped">'
                            f'<span class="sr-step-num">{j+1}</span>'
                            f'{_badge(rem["action"])}'
                            f'<span class="sr-step-filename" style="color:#6b7280;">{rem["filename"]}</span>'
                            f'<span class="sr-run-status" style="color:#9ca3af;">not run</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    break
                # else: continue to next step
            else:
                _update_progress(step_n, step["filename"], "done")
                hdr_ph.markdown(
                    f'<div class="sr-run-step-header success">'
                    f'<span class="sr-step-num">{step_n}</span>'
                    f'{_badge(step["action"])}'
                    f'<span class="sr-step-filename">{step["filename"]}</span>'
                    f'<span class="sr-run-status" style="color:#16a34a;">done  ·  {elapsed}s</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # Clear live progress indicators before final rerun
        progress_ph.empty()
        status_ph.empty()

        # Save to run history
        save_run(
            sequence_name=st.session_state.get("sr_current_seq_name", "Manual"),
            results=results,
            failed_at=failed_at,
            total_steps=len(steps),
        )

        st.session_state.sr_run_results    = results
        st.session_state.sr_failed_at      = failed_at
        st.session_state.sr_run_done       = True
        st.rerun()

    elif st.session_state.sr_run_done:
        results         = st.session_state.sr_run_results
        failed_at       = st.session_state.sr_failed_at
        stop_on_failure = st.session_state.get("sr_stop_on_failure", True)
        total           = len(steps)
        ran             = len(results)

        # ── Per-step results ──────────────────────────────────────────────────
        for r in results:
            ok      = r["status"] == "success"
            hdr_cls = "success" if ok else "failed"
            name_c  = "#111827" if ok else "#dc2626"
            icon    = "✅" if ok else "❌"

            st.markdown(
                f'<div class="sr-run-step-header {hdr_cls}">'
                f'<span class="sr-step-num">{r["step_n"]}</span>'
                f'{_badge(r["action"])}'
                f'<span class="sr-step-filename" style="color:{name_c};">{r["filename"]}</span>'
                f'<span class="sr-step-abs">{r["abs_path"]}</span>'
                f'<span class="sr-run-status">{icon}  ·  {r["elapsed"]}s</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            with st.expander("Show output", expanded=(r["status"] == "failed")):
                st.code("\n".join(r["lines"]), language="bash")

        # Not-run steps (stop mode only — in run-all mode all steps ran)
        if stop_on_failure and failed_at is not None:
            for j in range(ran, total):
                rem = steps[j]
                st.markdown(
                    f'<div class="sr-run-step-header skipped">'
                    f'<span class="sr-step-num">{j+1}</span>'
                    f'{_badge(rem["action"])}'
                    f'<span class="sr-step-filename" style="color:#6b7280;">{rem["filename"]}</span>'
                    f'<span class="sr-run-status" style="color:#9ca3af;">not run</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown(" ")

        # ── Summary ───────────────────────────────────────────────────────────
        n_passed = sum(1 for r in results if r["status"] == "success")
        n_failed = sum(1 for r in results if r["status"] == "failed")

        if n_failed == 0:
            # Full success — same for both modes
            st.markdown(
                f'<div class="run-summary success">'
                f'All {total} step{"s" if total!=1 else ""} completed successfully.'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(" ")
            ok_l, ok_r = st.columns(2)
            with ok_l:
                if st.button("Run Another Sequence", key="sr_run_again", use_container_width=True):
                    st.session_state.sr_screen      = "setup"
                    st.session_state.sr_scanned     = False
                    st.session_state.sr_steps       = []
                    st.session_state.sr_run_results = []
                    st.session_state.sr_run_done    = False
                    st.rerun()
            with ok_r:
                if st.button("← Back to Sequence", key="sr_back_ok", use_container_width=True):
                    st.session_state.sr_screen = "build"
                    st.rerun()

        elif stop_on_failure:
            # Stop mode — existing behaviour
            n_done   = failed_at - 1
            n_notrun = total - ran
            done_txt = f"Steps 1–{n_done}" if n_done > 0 else "—"
            st.markdown(
                f'<div class="run-summary failed">'
                f'<b>Execution stopped at Step {failed_at}.</b><br>'
                f'Completed: {done_txt}<br>'
                f'Failed at: Step {failed_at} — {results[failed_at-1]["filename"]}<br>'
                + (f'Not run: {n_notrun} step{"s" if n_notrun!=1 else ""}' if n_notrun else "")
                + '</div>',
                unsafe_allow_html=True,
            )
            st.markdown(" ")
            fa_l, fa_r = st.columns(2)
            with fa_l:
                if st.button(f"Retry from Step {failed_at}", key="sr_retry",
                             type="primary", use_container_width=True):
                    st.session_state.sr_steps       = steps[failed_at-1:]
                    st.session_state.sr_run_results = []
                    st.session_state.sr_run_done    = False
                    st.session_state.sr_failed_at   = None
                    st.session_state.sr_execute_now = True
                    st.rerun()
            with fa_r:
                if st.button("← Edit Sequence", key="sr_edit_fail", use_container_width=True):
                    st.session_state.sr_steps  = steps
                    st.session_state.sr_screen = "build"
                    st.rerun()

        else:
            # Run-all mode — show passed/failed breakdown
            failed_names = [r["filename"] for r in results if r["status"] == "failed"]
            failed_list  = "".join(f"&nbsp;&nbsp;• {n}<br>" for n in failed_names)
            st.markdown(
                f'<div class="run-summary failed">'
                f'<b>Run complete — {n_failed} step{"s" if n_failed!=1 else ""} failed.</b><br><br>'
                f'✅ &nbsp;Passed: {n_passed} step{"s" if n_passed!=1 else ""}<br>'
                f'❌ &nbsp;Failed: {n_failed} step{"s" if n_failed!=1 else ""}<br>'
                f'{failed_list}'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(" ")
            ra_l, ra_r = st.columns(2)
            with ra_l:
                if st.button("Run Another Sequence", key="sr_run_again", use_container_width=True):
                    st.session_state.sr_screen      = "setup"
                    st.session_state.sr_scanned     = False
                    st.session_state.sr_steps       = []
                    st.session_state.sr_run_results = []
                    st.session_state.sr_run_done    = False
                    st.rerun()
            with ra_r:
                if st.button("← Edit Sequence", key="sr_edit_runall", use_container_width=True):
                    st.session_state.sr_steps  = steps
                    st.session_state.sr_screen = "build"
                    st.rerun()

    app_footer()


# ── Screen routing ─────────────────────────────────────────────────────────────
_screen = st.session_state.sr_screen
if _screen == "setup":  render_setup()
elif _screen == "build": render_build()
elif _screen == "run":   render_run()