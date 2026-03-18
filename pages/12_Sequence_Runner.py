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

from utils.ui_utils      import load_global_css, render_sidebar, app_footer, section_header
from utils.folder_scanner import scan_folder
from utils.deployer      import build_command, run_command, format_command_display
from utils.sequences     import load_sequences, save_sequence, delete_sequence

load_global_css()
render_sidebar()

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
    "sr_selected_playbook": None,   # name of playbook currently in detail view
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Load persisted paths once
if not st.session_state.sr_ctl_dir:
    st.session_state.sr_ctl_dir = _get_env("DATAOS_CTL_DIR")
if not st.session_state.sr_dp_dir:
    st.session_state.sr_dp_dir = _get_env("DATAOS_DP_DIR")

# ── Page-level CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── File rows in Setup ──────────────────────────────────── */
.sr-file-row {
    display: flex;
    align-items: center;
    padding: 9px 14px;
    margin-bottom: 4px;
    background: #0d1117;
    border: 1px solid #1f2937;
    border-radius: 8px;
    font-size: 13px;
    gap: 12px;
}
.sr-file-row:hover { border-color: #374151; }
.sr-filename  { font-weight: 500; color: #e5e7eb; }
.sr-rel-path  {
    font-size: 11px;
    color: #4b5563;
    font-family: 'JetBrains Mono', monospace;
    margin-left: auto;
}

/* ── Step rows in Build ──────────────────────────────────── */
.sr-step-row {
    padding: 10px 14px;
    margin-bottom: 4px;
    background: #0f172a;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    font-size: 13px;
}
.sr-step-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px; height: 22px;
    border-radius: 50%;
    background: #1e3a5f;
    color: #60a5fa;
    font-size: 11px;
    font-weight: 700;
    flex-shrink: 0;
    vertical-align: middle;
    margin-right: 6px;
}

/* ── Action badges ───────────────────────────────────────── */
.badge-delete {
    display: inline-block;
    background: #7f1d1d;
    color: #fca5a5;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.03em;
    vertical-align: middle;
    margin-right: 6px;
}
.badge-apply {
    display: inline-block;
    background: #052e16;
    color: #6ee7b7;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.03em;
    vertical-align: middle;
    margin-right: 6px;
}

/* ── Run screen step headers ─────────────────────────────── */
.sr-run-step-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    background: #0f172a;
    border: 1px solid #1e3a5f;
    border-radius: 8px 8px 0 0;
    font-size: 13px;
    margin-top: 14px;
}
.sr-run-step-header.success {
    background: #031a0e;
    border-color: #059669;
}
.sr-run-step-header.failed {
    background: #1a0303;
    border-color: #dc2626;
}
.sr-run-step-header.skipped {
    opacity: 0.4;
    border-radius: 8px;
}
.sr-step-abs {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: #4b5563;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 480px;
}

/* ── Path pill (config screen) ───────────────────────────── */
.sr-path-pill {
    display: inline-block;
    background: #1e2638;
    border: 1px solid #374151;
    color: #6b7280;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
    word-break: break-all;
}

/* ── Playbook list row ───────────────────────────────────── */
.pb-list-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: #111827;
    border: 1px solid #1f2937;
    border-left: 3px solid #6366f1;
    border-radius: 8px;
    margin-bottom: 6px;
    transition: border-color 0.15s ease;
}
.pb-list-row.active {
    border-color: #818cf8;
    background: #1a1f35;
}
.pb-list-row:hover { border-color: #4f46e5; }
.pb-name   { font-size: 14px; font-weight: 600; color: #e5e7eb; }
.pb-meta   { font-size: 11px; color: #4b5563; margin-top: 2px; }

/* ── Playbook detail panel ───────────────────────────────── */
.pb-detail {
    background: #0d1117;
    border: 1px solid #6366f1;
    border-radius: 10px;
    padding: 16px 18px;
    margin: 8px 0 16px 0;
}
.pb-detail-title {
    font-size: 13px;
    font-weight: 600;
    color: #818cf8;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid #1f2937;
}

/* ── Empty sequence placeholder ─────────────────────────── */
.seq-empty {
    padding: 24px;
    text-align: center;
    color: #374151;
    border: 1px dashed #1f2937;
    border-radius: 8px;
    font-size: 13px;
}

/* ── Summary box after run ───────────────────────────────── */
.run-summary {
    padding: 16px 20px;
    border-radius: 10px;
    margin-top: 16px;
    font-size: 14px;
    line-height: 1.8;
}
.run-summary.success { background: #031a0e; border: 1px solid #059669; color: #6ee7b7; }
.run-summary.failed  { background: #1a0303; border: 1px solid #dc2626; color: #fca5a5; }
</style>
""", unsafe_allow_html=True)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _abs_path(rel_path: str) -> str:
    """Resolve rel_path against the current sr_dp_dir to a full OS path."""
    return os.path.join(
        st.session_state.sr_dp_dir,
        rel_path.replace("/", os.sep),
    )


def _badge(action: str) -> str:
    cls = "badge-delete" if action == "delete" else "badge-apply"
    return f'<span class="{cls}">{action.upper()}</span>'


# ════════════════════════════════════════════════════════════════════════════
# SCREEN 1 — SETUP: configure paths, scan folder, select changed files
# ════════════════════════════════════════════════════════════════════════════

def render_setup() -> None:
    st.markdown("## Sequence Runner")
    st.markdown(
        '<p style="color:#6b7280;font-size:13px;margin-top:-8px;margin-bottom:20px;">'
        'Configure your paths, scan your DP folder, select the files you changed, '
        'then build and run a deployment sequence.</p>',
        unsafe_allow_html=True,
    )

    nav_l, _ = st.columns([1, 6])
    with nav_l:
        if st.button("← Home", key="sr_home"):
            st.session_state.home_screen = "home"
            st.switch_page("app.py")

    st.divider()

    # ── Path configuration ────────────────────────────────────────────────────
    section_header("⚙️", "Configuration")
    st.caption("Saved to .env — only needs to be set once per machine.")
    st.markdown(" ")

    cfg_c1, cfg_c2 = st.columns(2, gap="large")

    with cfg_c1:
        st.markdown(
            '<p style="font-size:13px;font-weight:600;color:#d1d5db;margin-bottom:6px;">'
            'CTL Directory</p>',
            unsafe_allow_html=True,
        )
        ctl_input = st.text_input(
            "CTL Directory",
            value=st.session_state.sr_ctl_dir,
            placeholder=r"e.g.  C:\Users\Manoj\Desktop\DataOS\windows-amd64",
            key="sr_ctl_input",
            label_visibility="collapsed",
            help="Folder that contains dataos-ctl",
        )
        if st.button("Save CTL Path", key="sr_save_ctl", use_container_width=True):
            st.session_state.sr_ctl_dir = ctl_input.strip()
            _set_env("DATAOS_CTL_DIR", ctl_input.strip())
            st.success("CTL path saved.")
        if st.session_state.sr_ctl_dir:
            st.markdown(
                f'<p style="margin-top:6px;font-size:11px;color:#6b7280;">'
                f'Saved: <span class="sr-path-pill">{st.session_state.sr_ctl_dir}</span></p>',
                unsafe_allow_html=True,
            )

    with cfg_c2:
        st.markdown(
            '<p style="font-size:13px;font-weight:600;color:#d1d5db;margin-bottom:6px;">'
            'DP Folder Path</p>',
            unsafe_allow_html=True,
        )
        dp_input = st.text_input(
            "DP Folder Path",
            value=st.session_state.sr_dp_dir,
            placeholder=r"e.g.  C:\Users\Manoj\Desktop\my-data-product",
            key="sr_dp_input",
            label_visibility="collapsed",
            help="Root folder of your Data Product",
        )
        if st.button("Save DP Path", key="sr_save_dp", use_container_width=True):
            st.session_state.sr_dp_dir  = dp_input.strip()
            st.session_state.sr_scanned = False
            _set_env("DATAOS_DP_DIR", dp_input.strip())
            st.success("DP folder path saved.")
        if st.session_state.sr_dp_dir:
            st.markdown(
                f'<p style="margin-top:6px;font-size:11px;color:#6b7280;">'
                f'Saved: <span class="sr-path-pill">{st.session_state.sr_dp_dir}</span></p>',
                unsafe_allow_html=True,
            )

    st.markdown(" ")

    # ── Scan button ───────────────────────────────────────────────────────────
    scan_col, _ = st.columns([2, 5])
    with scan_col:
        dp_set = bool(st.session_state.sr_dp_dir.strip())
        if st.button(
            "Scan DP Folder",
            key="sr_scan_btn",
            type="primary",
            disabled=not dp_set,
            use_container_width=True,
        ):
            dp = st.session_state.sr_dp_dir.strip()
            if not os.path.isdir(dp):
                st.error(f"Folder not found: `{dp}`")
                st.stop()
            result = scan_folder(dp)
            st.session_state.sr_all_files   = result["deployable"]
            st.session_state.sr_model_files = result["model_files"]
            st.session_state.sr_scanned     = True
            st.session_state.sr_selected_rels     = set()
            st.session_state.sr_selected_playbook = None
            st.rerun()

        if not dp_set:
            st.caption("Enter and save the DP Folder Path first.")

    # ── File list ─────────────────────────────────────────────────────────────
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
    st.caption("Check every file you have changed and want to redeploy. Each folder is collapsible — use **Select all** to check an entire folder at once.")
    st.markdown(" ")

    # ── Build 2-level tree: top_folder → sub_folder → [files] ────────────────
    from collections import defaultdict

    tree: dict = defaultdict(lambda: defaultdict(list))
    for f in all_files:
        parts = f["rel_path"].split("/")
        top   = parts[0] if len(parts) > 1 else "."
        sub   = "/".join(parts[1:-1]) if len(parts) > 2 else ""
        tree[top][sub].append(f)

    _TOP_COLORS = ["#3b82f6", "#10b981", "#f97316", "#8b5cf6", "#14b8a6", "#f59e0b"]

    for ti, top_folder in enumerate(sorted(tree.keys())):
        sub_map   = tree[top_folder]
        color     = _TOP_COLORS[ti % len(_TOP_COLORS)]
        top_total = sum(len(v) for v in sub_map.values())
        top_rels  = [f["rel_path"] for files in sub_map.values() for f in files]
        n_checked = sum(1 for r in top_rels if r in st.session_state.sr_selected_rels)

        sel_all_key  = f"sr_selall_{ti}"
        checked_note = f"  ✓ {n_checked} selected" if n_checked else ""
        exp_label    = f"📁  {top_folder}  -  {top_total} file{'s' if top_total != 1 else ''}{checked_note}"

        with st.expander(exp_label, expanded=False):

            sa_col, sa_lbl = st.columns([0.4, 10])
            with sa_col:
                all_checked = (n_checked == top_total)
                select_all  = st.checkbox(
                    "",
                    value=all_checked,
                    key=sel_all_key,
                    label_visibility="collapsed",
                )
            with sa_lbl:
                st.markdown(
                    '<div style="padding:6px 0 2px 4px;font-size:12px;'
                    'font-weight:600;color:#6b7280;">Select all in folder</div>',
                    unsafe_allow_html=True,
                )

            if select_all and not all_checked:
                for r in top_rels:
                    st.session_state.sr_selected_rels.add(r)
                st.rerun()
            elif not select_all and all_checked:
                for r in top_rels:
                    st.session_state.sr_selected_rels.discard(r)
                st.rerun()

            for sub_folder in sorted(sub_map.keys()):
                files_here = sub_map[sub_folder]

                if sub_folder:
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:6px;'
                        f'margin:12px 0 4px 4px;padding-bottom:4px;'
                        f'border-bottom:1px solid #1f2937;">'
                        f'<span style="font-size:12px;">📂</span>'
                        f'<span style="font-size:12px;font-weight:600;color:#9ca3af;">'
                        f'{sub_folder}</span>'
                        f'<span style="font-size:11px;color:#374151;margin-left:4px;">'
                        f'· {len(files_here)} file{"s" if len(files_here)!=1 else ""}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                for f in files_here:
                    global_idx = all_files.index(f)
                    chk_col, info_col = st.columns([0.4, 10])
                    with chk_col:
                        checked = st.checkbox(
                            "",
                            value=(f["rel_path"] in st.session_state.sr_selected_rels),
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
                            f'<div class="sr-file-row" style="{indent}'
                            f'border-left:2px solid {color}33;">'
                            f'<span style="font-size:11px;color:#4b5563;margin-right:6px;">└</span>'
                            f'<span class="sr-filename">{f["filename"]}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

    # ── Model files expander ──────────────────────────────────────────────────
    if model_files:
        with st.expander(
            f"Model files ({len(model_files)}) — part of Lens, not deployed individually",
            expanded=False,
        ):
            model_tree: dict = defaultdict(lambda: defaultdict(list))
            for mf in model_files:
                parts = mf["rel_path"].split("/")
                top   = parts[0] if len(parts) > 1 else "."
                sub   = "/".join(parts[1:-1]) if len(parts) > 2 else ""
                model_tree[top][sub].append(mf)

            for top_folder in sorted(model_tree.keys()):
                st.markdown(
                    f'<div style="font-size:12px;font-weight:600;color:#4b5563;'
                    f'padding:6px 4px 4px 4px;margin-top:6px;">'
                    f'📁 {top_folder}</div>',
                    unsafe_allow_html=True,
                )
                for sub_folder, mfs in sorted(model_tree[top_folder].items()):
                    if sub_folder:
                        st.markdown(
                            f'<div style="font-size:11px;color:#374151;'
                            f'padding:3px 4px 3px 12px;">📂 {sub_folder}</div>',
                            unsafe_allow_html=True,
                        )
                    for mf in mfs:
                        st.markdown(
                            f'<div class="sr-file-row" style="opacity:0.4;margin-left:20px;'
                            f'border-left:2px solid #37415122;">'
                            f'<span style="font-size:11px;color:#374151;margin-right:6px;">└</span>'
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
        st.caption("Select a playbook to preview its steps, then load it — or select files manually above.")
        st.markdown(" ")

        rel_set          = {f["rel_path"] for f in all_files}
        active_pb        = st.session_state.sr_selected_playbook

        for seq in saved:
            steps_in = seq.get("steps", [])
            n_steps  = len(steps_in)
            ts       = seq.get("updated_at", seq.get("created_at", ""))[:10]
            is_active = (active_pb == seq["name"])
            missing   = [s for s in steps_in if s["rel_path"] not in rel_set]

            # ── Row: name + meta + Select/Deselect button ─────────────────────
            row_cls   = "pb-list-row active" if is_active else "pb-list-row"
            warn_pill = (
                f'<span style="font-size:10px;color:#f59e0b;background:#2d1f00;'
                f'border:1px solid #92400e;padding:1px 6px;border-radius:4px;'
                f'margin-left:8px;">{len(missing)} missing</span>'
                if missing else ""
            )
            st.markdown(
                f'<div class="{row_cls}">'
                f'  <div>'
                f'    <div class="pb-name">{seq["name"]}{warn_pill}</div>'
                f'    <div class="pb-meta">{n_steps} step{"s" if n_steps!=1 else ""}  ·  {ts}</div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            btn_col1, btn_col2 = st.columns([1, 5])
            with btn_col1:
                if is_active:
                    if st.button("Deselect", key=f"sr_pb_desel_{seq['name']}", use_container_width=True):
                        st.session_state.sr_selected_playbook = None
                        st.rerun()
                else:
                    if st.button("Select", key=f"sr_pb_sel_{seq['name']}", use_container_width=True):
                        st.session_state.sr_selected_playbook = seq["name"]
                        st.rerun()

            # ── Detail panel — shown only for the active playbook ─────────────
            if is_active:
                # Build step rows
                step_rows_html = ""
                for idx_s, s in enumerate(steps_in):
                    fname     = s["rel_path"].split("/")[-1]
                    folder    = "/".join(s["rel_path"].split("/")[:-1])
                    is_miss   = s["rel_path"] not in rel_set
                    badge_cls = "badge-delete" if s["action"] == "delete" else "badge-apply"
                    name_col  = "#6b7280" if is_miss else "#e5e7eb"
                    fold_col  = "#374151" if is_miss else "#4b5563"
                    miss_tag  = (
                        '<span style="font-size:10px;color:#f59e0b;background:#2d1f00;'
                        'border:1px solid #92400e;padding:1px 6px;border-radius:4px;'
                        'margin-left:8px;">not found</span>'
                        if is_miss else ""
                    )
                    step_rows_html += (
                        f'<div style="display:flex;align-items:center;gap:10px;'
                        f'padding:7px 0;border-bottom:1px solid #1f2937;">'
                        f'<span style="font-size:11px;color:#374151;width:20px;'
                        f'text-align:right;flex-shrink:0;">{idx_s+1}</span>'
                        f'<span class="{badge_cls}" style="flex-shrink:0;'
                        f'width:56px;text-align:center;">{s["action"].upper()}</span>'
                        f'<span style="font-size:13px;font-weight:500;color:{name_col};'
                        f'min-width:160px;">{fname}</span>'
                        f'<span style="font-size:11px;color:{fold_col};'
                        f'font-family:monospace;">{folder}</span>'
                        f'{miss_tag}'
                        f'</div>'
                    )

                warn_html = ""
                if missing:
                    mnames = ", ".join(s["rel_path"].split("/")[-1] for s in missing)
                    warn_html = (
                        f'<div style="margin-top:10px;padding:8px 12px;background:#1c1200;'
                        f'border:1px solid #92400e;border-radius:6px;'
                        f'font-size:12px;color:#f59e0b;">'
                        f'⚠️  {len(missing)} file{"s" if len(missing)>1 else ""} not in '
                        f'current folder — steps will still load, remove before running: '
                        f'{mnames}</div>'
                    )

                st.markdown(
                    f'<div class="pb-detail">'
                    f'  <div class="pb-detail-title">Steps in "{seq["name"]}"</div>'
                    f'  {step_rows_html}'
                    f'  {warn_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if st.button(
                    f"Load & Continue  —  {seq['name']}",
                    key=f"sr_pb_load_{seq['name']}",
                    type="primary",
                    use_container_width=True,
                ):
                    # Auto-select files + build steps
                    st.session_state.sr_selected_rels = {
                        s["rel_path"] for s in steps_in if s["rel_path"] in rel_set
                    }
                    st.session_state.sr_steps = [
                        {
                            "action":   s["action"],
                            "rel_path": s["rel_path"],
                            "abs_path": _abs_path(s["rel_path"]),
                            "filename": s["rel_path"].split("/")[-1],
                        }
                        for s in steps_in
                    ]
                    st.session_state.sr_run_results       = []
                    st.session_state.sr_run_done          = False
                    st.session_state.sr_failed_at         = None
                    st.session_state.sr_selected_playbook = None
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
            st.caption("Select files manually above — or use a saved playbook.")
    with bot_r:
        if st.button(
            "Build Sequence →",
            key="sr_to_build",
            type="primary",
            disabled=(n_sel == 0),
            use_container_width=True,
        ):
            st.session_state.sr_steps       = []
            st.session_state.sr_run_results = []
            st.session_state.sr_run_done    = False
            st.session_state.sr_screen      = "build"
            st.rerun()

    app_footer()


# ════════════════════════════════════════════════════════════════════════════
# SCREEN 2 — BUILD: assemble the sequence, save playbooks
# ════════════════════════════════════════════════════════════════════════════

def render_build() -> None:
    st.markdown("## Build Sequence")
    st.markdown(
        '<p style="color:#6b7280;font-size:13px;margin-top:-8px;margin-bottom:16px;">'
        'Click <b>+ Delete</b> or <b>+ Apply</b> on each file to add steps in order. '
        'Reorder and remove as needed.</p>',
        unsafe_allow_html=True,
    )

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
                f'<span style="font-size:13px;font-weight:500;color:#e5e7eb;">{f["filename"]}</span>'
                f'&nbsp;&nbsp;<span style="font-size:11px;color:#4b5563;'
                f'font-family:\'JetBrains Mono\',monospace;">{f["rel_path"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with fc_del:
            if st.button(
                "+ Delete",
                key=f"sr_add_del_{f['rel_path']}",
                use_container_width=True,
            ):
                st.session_state.sr_steps.append({
                    "action":   "delete",
                    "rel_path": f["rel_path"],
                    "abs_path": _abs_path(f["rel_path"]),
                    "filename": f["filename"],
                })
                st.rerun()
        with fc_apl:
            if st.button(
                "+ Apply",
                key=f"sr_add_apl_{f['rel_path']}",
                use_container_width=True,
            ):
                st.session_state.sr_steps.append({
                    "action":   "apply",
                    "rel_path": f["rel_path"],
                    "abs_path": _abs_path(f["rel_path"]),
                    "filename": f["filename"],
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
        st.markdown(
            '<div class="seq-empty">No steps yet — click + Delete or + Apply above</div>',
            unsafe_allow_html=True,
        )
    else:
        for i, step in enumerate(steps):
            sc_num, sc_action, sc_fname, sc_up, sc_dn, sc_rm = st.columns(
                [0.45, 1.6, 6, 0.45, 0.45, 0.45]
            )

            with sc_num:
                st.markdown(
                    f'<div style="padding-top:7px;text-align:center;">'
                    f'<span class="sr-step-num">{i + 1}</span></div>',
                    unsafe_allow_html=True,
                )

            with sc_action:
                new_action = st.selectbox(
                    "",
                    options=["delete", "apply"],
                    index=0 if step["action"] == "delete" else 1,
                    key=f"sr_action_{i}",
                    label_visibility="collapsed",
                )
                if new_action != step["action"]:
                    st.session_state.sr_steps[i]["action"] = new_action

            with sc_fname:
                st.markdown(
                    f'<div style="padding:7px 0 4px 0;font-size:13px;">'
                    f'<span style="color:#e5e7eb;font-weight:500;">{step["filename"]}</span>'
                    f'&nbsp;&nbsp;<span style="font-size:11px;color:#4b5563;'
                    f'font-family:\'JetBrains Mono\',monospace;">{step["rel_path"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with sc_up:
                if st.button("↑", key=f"sr_up_{i}", disabled=(i == 0),
                             use_container_width=True):
                    st.session_state.sr_steps[i], st.session_state.sr_steps[i - 1] = (
                        st.session_state.sr_steps[i - 1],
                        st.session_state.sr_steps[i],
                    )
                    k_i, k_prev = f"sr_action_{i}", f"sr_action_{i-1}"
                    v_i    = st.session_state.get(k_i,   steps[i]["action"])
                    v_prev = st.session_state.get(k_prev, steps[i-1]["action"])
                    st.session_state[k_i]    = v_prev
                    st.session_state[k_prev] = v_i
                    st.rerun()

            with sc_dn:
                if st.button("↓", key=f"sr_dn_{i}", disabled=(i == len(steps) - 1),
                             use_container_width=True):
                    st.session_state.sr_steps[i], st.session_state.sr_steps[i + 1] = (
                        st.session_state.sr_steps[i + 1],
                        st.session_state.sr_steps[i],
                    )
                    k_i, k_nxt = f"sr_action_{i}", f"sr_action_{i+1}"
                    v_i  = st.session_state.get(k_i,  steps[i]["action"])
                    v_nxt = st.session_state.get(k_nxt, steps[i+1]["action"])
                    st.session_state[k_i]  = v_nxt
                    st.session_state[k_nxt] = v_i
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
        st.caption("Saves this sequence with relative paths — reusable on any DP folder structure.")
        st.markdown(" ")

        sv_name, sv_btn = st.columns([5, 1.5])
        with sv_name:
            pb_name = st.text_input(
                "Playbook Name",
                placeholder="e.g.  Redeploy after SM change",
                key="sr_pb_name_input",
                label_visibility="collapsed",
            )
        with sv_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Save Playbook", key="sr_save_pb", use_container_width=True):
                name = pb_name.strip()
                if not name:
                    st.warning("Enter a name first.")
                else:
                    save_steps = [
                        {"action": s["action"], "rel_path": s["rel_path"]}
                        for s in steps
                    ]
                    save_sequence(name, save_steps)
                    st.success(f"Playbook **{name}** saved ✓")

    st.markdown(" ")

    # ── Saved Playbooks in Build screen ──────────────────────────────────────
    saved = load_sequences()
    with st.expander(
        f"Saved Playbooks ({len(saved)})",
        expanded=(len(saved) > 0 and not steps),
    ):
        if not saved:
            st.caption("No saved playbooks yet.")
        else:
            for seq in saved:
                pb_l, pb_load, pb_del = st.columns([6, 1.2, 0.7])
                n_steps = len(seq.get("steps", []))
                ts = seq.get("updated_at", seq.get("created_at", ""))[:10]

                with pb_l:
                    st.markdown(
                        f'<div class="pb-list-row">'
                        f'  <div>'
                        f'    <div class="pb-name">{seq["name"]}</div>'
                        f'    <div class="pb-meta">{n_steps} step{"s" if n_steps != 1 else ""}  ·  {ts}</div>'
                        f'  </div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with pb_load:
                    if st.button("Load", key=f"sr_load_{seq['name']}", use_container_width=True):
                        loaded, missing = [], []
                        for s in seq.get("steps", []):
                            abs_p = _abs_path(s["rel_path"])
                            if os.path.exists(abs_p):
                                loaded.append({
                                    "action":   s["action"],
                                    "rel_path": s["rel_path"],
                                    "abs_path": abs_p,
                                    "filename": os.path.basename(s["rel_path"]),
                                })
                            else:
                                missing.append(s["rel_path"])
                        st.session_state.sr_steps = loaded
                        if missing:
                            st.warning(
                                "Files not found in current DP folder:\n"
                                + "\n".join(f"• {p}" for p in missing)
                            )
                        else:
                            st.success("Playbook loaded into sequence ✓")
                        st.rerun()
                with pb_del:
                    if st.button("✕", key=f"sr_del_pb_{seq['name']}", use_container_width=True):
                        delete_sequence(seq["name"])
                        st.rerun()

    st.markdown(" ")

    # ── Command preview + Run button ──────────────────────────────────────────
    if steps:
        if not st.session_state.sr_ctl_dir.strip():
            st.warning("CTL Directory is not set — go back to Setup to configure it.")
        else:
            st.divider()
            section_header("👁", "Command Preview")
            st.caption("Exact commands that will run — review before executing.")
            st.markdown(" ")

            preview_lines = []
            for i, step in enumerate(steps):
                yaml_content = ""
                try:
                    with open(step["abs_path"], "r", encoding="utf-8") as fh:
                        yaml_content = fh.read()
                except Exception:
                    pass
                cmd = build_command(
                    st.session_state.sr_ctl_dir.strip(),
                    step["action"],
                    step["abs_path"],
                    yaml_content,
                )
                preview_lines.append(f"# Step {i + 1}")
                preview_lines.append(format_command_display(cmd))
                preview_lines.append("")

            st.code("\n".join(preview_lines).strip(), language="bash")
            st.markdown(" ")

            if st.button(
                f"Run Sequence  ·  {len(steps)} step{'s' if len(steps) != 1 else ''}",
                key="sr_run_btn",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.sr_run_results = []
                st.session_state.sr_run_done    = False
                st.session_state.sr_failed_at   = None
                st.session_state.sr_execute_now = True
                st.session_state.sr_screen      = "run"
                st.rerun()

    app_footer()


# ════════════════════════════════════════════════════════════════════════════
# SCREEN 3 — RUN: execute sequence and stream live output
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

    # ── EXECUTION BLOCK ───────────────────────────────────────────────────────
    if st.session_state.sr_execute_now:
        st.session_state.sr_execute_now = False

        results:   list     = []
        failed_at: int|None = None

        for i, step in enumerate(steps):
            step_n = i + 1

            hdr_ph = st.empty()
            hdr_ph.markdown(
                f'<div class="sr-run-step-header">'
                f'<span class="sr-step-num">{step_n}</span>'
                f'{_badge(step["action"])}'
                f'<span style="color:#e5e7eb;font-weight:500;">{step["filename"]}</span>'
                f'<span style="margin-left:auto;font-size:12px;color:#60a5fa;">running...</span>'
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
            cmd_str = format_command_display(cmd)
            lines   = [f"$ {cmd_str}"]
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

            result = {
                **step,
                "step_n":  step_n,
                "status":  "success" if rc == 0 else "failed",
                "lines":   lines,
                "elapsed": elapsed,
                "rc":      rc,
            }
            results.append(result)

            if rc != 0:
                hdr_ph.markdown(
                    f'<div class="sr-run-step-header failed">'
                    f'<span class="sr-step-num">{step_n}</span>'
                    f'{_badge(step["action"])}'
                    f'<span style="color:#fca5a5;font-weight:500;">{step["filename"]}</span>'
                    f'<span style="margin-left:auto;font-size:12px;color:#f87171;">'
                    f'failed  ·  {elapsed}s</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                failed_at = step_n
                for j in range(i + 1, len(steps)):
                    rem = steps[j]
                    st.markdown(
                        f'<div class="sr-run-step-header skipped">'
                        f'<span class="sr-step-num">{j + 1}</span>'
                        f'{_badge(rem["action"])}'
                        f'<span style="color:#9ca3af;">{rem["filename"]}</span>'
                        f'<span style="margin-left:auto;font-size:11px;color:#4b5563;">not run</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                break
            else:
                hdr_ph.markdown(
                    f'<div class="sr-run-step-header success">'
                    f'<span class="sr-step-num">{step_n}</span>'
                    f'{_badge(step["action"])}'
                    f'<span style="color:#e5e7eb;font-weight:500;">{step["filename"]}</span>'
                    f'<span style="margin-left:auto;font-size:12px;color:#34d399;">'
                    f'done  ·  {elapsed}s</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.session_state.sr_run_results = results
        st.session_state.sr_failed_at   = failed_at
        st.session_state.sr_run_done    = True
        st.rerun()

    # ── RESULTS VIEW ─────────────────────────────────────────────────────────
    elif st.session_state.sr_run_done:
        results   = st.session_state.sr_run_results
        failed_at = st.session_state.sr_failed_at
        total     = len(steps)
        ran       = len(results)

        for r in results:
            ok      = r["status"] == "success"
            hdr_cls = "success" if ok else "failed"
            icon    = "✅" if ok else "❌"
            name_c  = "#e5e7eb" if ok else "#fca5a5"

            st.markdown(
                f'<div class="sr-run-step-header {hdr_cls}">'
                f'<span class="sr-step-num">{r["step_n"]}</span>'
                f'{_badge(r["action"])}'
                f'<span style="color:{name_c};font-weight:500;">{r["filename"]}</span>'
                f'<span class="sr-step-abs">{r["abs_path"]}</span>'
                f'<span style="margin-left:auto;font-size:12px;">{icon}  ·  {r["elapsed"]}s</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            with st.expander("Show output", expanded=(r["status"] == "failed")):
                st.code("\n".join(r["lines"]), language="bash")

        if failed_at is not None:
            for j in range(ran, total):
                rem = steps[j]
                st.markdown(
                    f'<div class="sr-run-step-header skipped">'
                    f'<span class="sr-step-num">{j + 1}</span>'
                    f'{_badge(rem["action"])}'
                    f'<span style="color:#9ca3af;">{rem["filename"]}</span>'
                    f'<span style="margin-left:auto;font-size:11px;color:#4b5563;">not run</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown(" ")

        if failed_at is None:
            st.markdown(
                f'<div class="run-summary success">'
                f'All {total} step{"s" if total != 1 else ""} completed successfully.'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(" ")
            ok_l, ok_r = st.columns([2, 2])
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
        else:
            n_done   = failed_at - 1
            n_notrun = total - ran
            done_txt = f"Steps 1–{n_done}" if n_done > 0 else "—"

            st.markdown(
                f'<div class="run-summary failed">'
                f'<b>Execution stopped at Step {failed_at}.</b><br>'
                f'Completed: {done_txt}<br>'
                f'Failed at: Step {failed_at} — {results[-1]["filename"]}<br>'
                + (f'Not run: {n_notrun} step{"s" if n_notrun != 1 else ""}' if n_notrun else "")
                + '</div>',
                unsafe_allow_html=True,
            )
            st.markdown(" ")

            fa_l, fa_r = st.columns([2, 2])
            with fa_l:
                if st.button(
                    f"Retry from Step {failed_at}",
                    key="sr_retry",
                    type="primary",
                    use_container_width=True,
                ):
                    st.session_state.sr_steps       = steps[failed_at - 1:]
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

    app_footer()


# ── Screen routing ────────────────────────────────────────────────────────────
_screen = st.session_state.sr_screen

if _screen == "setup":
    render_setup()
elif _screen == "build":
    render_build()
elif _screen == "run":
    render_run()