"""
pages/11_Edit_DP.py — DP Folder Upload & Edit
Upload a zipped Data Product folder, edit files in-browser, download changes.
"""

import sys
import os
import io

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

st.set_page_config(page_title="Edit Data Product", layout="wide")

from utils.ui_utils import load_global_css, render_sidebar, app_footer
from utils.dp_editor import (
    parse_zip,
    build_zip,
    get_file_tree,
    detect_language,
    get_changed_files,
)

load_global_css()
render_sidebar()

# ── Try to import streamlit-ace; degrade gracefully if not installed ──────────
try:
    from streamlit_ace import st_ace
    ACE_AVAILABLE = True
except ImportError:
    ACE_AVAILABLE = False


# ── Page-level CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* File tree container */
.file-tree-file {
    padding: 5px 10px 5px 16px;
    border-radius: 6px;
    font-size: 12px;
    font-family: 'JetBrains Mono', monospace;
    color: #9ca3af;
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: flex;
    align-items: center;
    gap: 6px;
}
.file-tree-file.active {
    background: #1e3a5f;
    color: #93c5fd;
}
.file-tree-file.modified {
    color: #fbbf24;
}
.file-tree-file.active.modified {
    background: #2d2008;
    color: #fbbf24;
}
/* Modified badge in editor header */
.modified-badge {
    display: inline-block;
    background: #f59e0b22;
    color: #fbbf24;
    border: 1px solid #f59e0b44;
    font-size: 10px;
    font-weight: 700;
    padding: 1px 8px;
    border-radius: 999px;
    margin-left: 8px;
    vertical-align: middle;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
/* Editor path header */
.editor-path {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    color: #d1d5db;
    padding: 8px 12px;
    background: #1f2937;
    border: 1px solid #374151;
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    display: flex;
    align-items: center;
    gap: 6px;
}
/* Upload zone hint */
.upload-hint {
    font-size: 12px;
    color: #6b7280;
    margin-top: 6px;
    line-height: 1.7;
}
/* Download section */
.dl-section {
    background: #0d1117;
    border: 1px solid #1f2937;
    border-radius: 8px;
    padding: 14px 16px;
    margin-top: 12px;
}
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "edit_stage":          "upload",
        "edit_files":          {},
        "edit_files_original": {},
        "edit_zip_name":       "data_product",
        "edit_selected_file":  None,
        "edit_unsaved":        False,   # tracks whether ace content differs from saved
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _icon(filename: str) -> str:
    lang = detect_language(filename)
    return {"yaml": "📄", "sql": "🗄️", "json": "{}", "markdown": "📝"}.get(lang, "📃")


def _folder_icon(folder: str) -> str:
    low = folder.lower()
    if "depot"    in low: return "🏗️"
    if "semantic" in low or "model" in low: return "🔭"
    if "table"    in low: return "📊"
    if "view"     in low: return "👁️"
    if "flare"    in low: return "⚡"
    if "quality"  in low or "qc" in low:   return "✅"
    if "deploy"   in low or "dp-deploy" in low: return "🚀"
    if "secret"   in low: return "🔑"
    if "build"    in low: return "📦"
    return "📁"


def _reset():
    for k in ["edit_stage", "edit_files", "edit_files_original",
              "edit_zip_name", "edit_selected_file", "edit_unsaved"]:
        st.session_state.pop(k, None)
    _init_state()
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — UPLOAD
# ─────────────────────────────────────────────────────────────────────────────
def _render_upload():
    st.markdown("## Edit Existing Data Product")
    st.markdown(
        '<p style="color:#6b7280;font-size:14px;margin-top:-8px;margin-bottom:24px;">'
        'Upload a zipped DP folder, edit files in the browser, then download your changes.'
        '</p>',
        unsafe_allow_html=True,
    )

    col_up, col_tip = st.columns([3, 2], gap="large")

    with col_up:
        uploaded = st.file_uploader(
            "Upload your Data Product ZIP",
            type=["zip"],
            label_visibility="collapsed",
            help="Zip your DP folder (e.g. right-click → Compress) and upload it here.",
        )

        st.markdown(
            '<div class="upload-hint">'
            '✓ Supports <b>.yml</b> · <b>.yaml</b> · <b>.sql</b> · <b>.json</b> · <b>.md</b> · <b>.txt</b><br>'
            '✗ Binary files and <code>.git/</code> folders are automatically excluded'
            '</div>',
            unsafe_allow_html=True,
        )

        if uploaded:
            with st.spinner("Extracting ZIP…"):
                try:
                    files = parse_zip(uploaded)
                except Exception as e:
                    st.error(f"Could not read ZIP: {e}")
                    return

            if not files:
                st.error("No readable text files found inside the ZIP.")
                return

            st.session_state.edit_files          = files
            st.session_state.edit_files_original = dict(files)  # snapshot
            st.session_state.edit_zip_name       = uploaded.name
            st.session_state.edit_selected_file  = next(iter(files))
            st.session_state.edit_stage          = "editor"
            st.rerun()

    with col_tip:
        st.markdown(
            """
            <div style="background:#111827;border:1px solid #1f2937;border-left:3px solid #3b82f6;
                        border-radius:8px;padding:16px 18px;">
                <p style="font-size:13px;font-weight:600;color:#93c5fd;margin:0 0 10px 0;">
                    💡 How to zip your DP folder
                </p>
                <p style="font-size:12px;color:#6b7280;line-height:1.8;margin:0;">
                    <b style="color:#9ca3af;">Mac:</b> Right-click folder → Compress<br>
                    <b style="color:#9ca3af;">Windows:</b> Right-click → Send to → Compressed folder<br>
                    <b style="color:#9ca3af;">Linux:</b> <code style="color:#60a5fa;">zip -r dp.zip my-dp/</code>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    app_footer()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — EDITOR
# ─────────────────────────────────────────────────────────────────────────────
def _render_editor():
    files:    dict[str, str] = st.session_state.edit_files
    original: dict[str, str] = st.session_state.edit_files_original
    selected: str | None     = st.session_state.edit_selected_file
    zip_name: str            = st.session_state.edit_zip_name

    changed = get_changed_files(original, files)
    tree    = get_file_tree(files)

    # ── Top bar ───────────────────────────────────────────────────────────────
    hdr_l, hdr_r = st.columns([5, 2])
    with hdr_l:
        st.markdown(
            f'<p style="font-size:18px;font-weight:700;color:#f3f4f6;margin:0;">'
            f'📂 {zip_name}'
            f'</p>'
            f'<p style="font-size:12px;color:#6b7280;margin:2px 0 0 0;">'
            f'{len(files)} files · {len(changed)} modified</p>',
            unsafe_allow_html=True,
        )
    with hdr_r:
        if st.button("← Upload New ZIP", use_container_width=True):
            _reset()

    st.markdown("<div style='margin:8px 0;border-top:1px solid #1f2937;'></div>",
                unsafe_allow_html=True)

    # ── Two-column layout ─────────────────────────────────────────────────────
    tree_col, editor_col = st.columns([1, 3], gap="small")

    # ── LEFT: File tree ───────────────────────────────────────────────────────
    with tree_col:
        st.markdown(
            '<p style="font-size:11px;font-weight:700;color:#4b5563;'
            'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">'
            'FILES</p>',
            unsafe_allow_html=True,
        )

        # Group folders: root first, then alphabetical
        root_files  = tree.get("", [])
        sub_folders = {k: v for k, v in tree.items() if k != ""}

        # Root-level files
        if root_files:
            for fname in sorted(root_files):
                fpath    = fname
                is_sel   = (fpath == selected)
                is_mod   = (fpath in changed)
                dot      = " ●" if is_mod else ""
                btn_type = "primary" if is_sel else "secondary"
                label    = f"{_icon(fname)} {fname}{dot}"
                if st.button(label, key=f"ftree_{fpath}", use_container_width=True,
                             type=btn_type):
                    st.session_state.edit_selected_file = fpath
                    st.rerun()

        # Sub-folders
        for folder in sorted(sub_folders.keys()):
            folder_files = sub_folders[folder]
            # Show ● on folder if any file inside is modified
            folder_mod   = any(f"{folder}/{f}" in changed for f in folder_files)
            folder_dot   = " ●" if folder_mod else ""
            folder_label = f"{_folder_icon(folder)} {folder.split('/')[-1]}{folder_dot}"
            # Default expanded if selected file is in this folder
            is_open = selected is not None and selected.startswith(folder + "/")
            with st.expander(folder_label, expanded=is_open):
                for fname in sorted(folder_files):
                    fpath    = f"{folder}/{fname}"
                    is_sel   = (fpath == selected)
                    is_mod   = (fpath in changed)
                    dot      = " ●" if is_mod else ""
                    btn_type = "primary" if is_sel else "secondary"
                    label    = f"{_icon(fname)} {fname}{dot}"
                    if st.button(label, key=f"ftree_{fpath}", use_container_width=True,
                                 type=btn_type):
                        st.session_state.edit_selected_file = fpath
                        st.rerun()

    # ── RIGHT: Editor ─────────────────────────────────────────────────────────
    with editor_col:
        if not selected or selected not in files:
            st.info("Select a file from the tree on the left to start editing.")
        else:
            lang        = detect_language(selected)
            content     = files[selected]
            is_modified = selected in changed

            # Path header bar
            mod_badge = (
                '<span class="modified-badge">modified</span>' if is_modified else ""
            )
            st.markdown(
                f'<div class="editor-path">'
                f'{_icon(selected)} <span style="color:#6b7280;">{selected}</span>'
                f'{mod_badge}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # ── Editor ──────────────────────────────────────────────────────
            if ACE_AVAILABLE:
                new_content = st_ace(
                    value=content,
                    language=lang,
                    theme="monokai",
                    font_size=14,
                    tab_size=2,
                    show_gutter=True,
                    wrap=False,
                    auto_update=False,
                    min_lines=28,
                    key=f"ace_{selected}",   # forces re-render on file switch
                )
            else:
                # Graceful fallback — plain text area
                st.warning(
                    "Install `streamlit-ace` for the full IDE experience: "
                    "`pip install streamlit-ace`",
                    icon="⚠️",
                )
                new_content = st.text_area(
                    "File Content",
                    value=content,
                    height=500,
                    key=f"textarea_{selected}",
                    label_visibility="collapsed",
                )

            # ── Save button ──────────────────────────────────────────────────
            sv_col, _ = st.columns([1, 3])
            with sv_col:
                if st.button("💾 Save File", key=f"save_{selected}",
                             use_container_width=True, type="primary"):
                    st.session_state.edit_files[selected] = new_content
                    st.success(f"Saved `{selected}`")
                    st.rerun()

            # ── Download section ─────────────────────────────────────────────
            st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

            dl_changed = get_changed_files(
                st.session_state.edit_files_original,
                st.session_state.edit_files,
            )

            dl1, dl2 = st.columns(2)

            with dl1:
                if dl_changed:
                    changed_zip = build_zip(dl_changed, zip_name.replace(".zip", "") + "-changes")
                    st.download_button(
                        f"⬇ Download Changed Files ({len(dl_changed)})",
                        data=changed_zip,
                        file_name=zip_name.replace(".zip", "") + "-changes.zip",
                        mime="application/zip",
                        use_container_width=True,
                        type="primary",
                    )
                else:
                    st.button(
                        "⬇ Download Changed Files (0)",
                        disabled=True,
                        use_container_width=True,
                        help="No changes yet — edit and save a file first.",
                    )

            with dl2:
                full_zip = build_zip(st.session_state.edit_files,
                                     zip_name.replace(".zip", ""))
                st.download_button(
                    "⬇ Download Full ZIP",
                    data=full_zip,
                    file_name=zip_name if zip_name.endswith(".zip") else zip_name + ".zip",
                    mime="application/zip",
                    use_container_width=True,
                )


# ─────────────────────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.edit_stage == "upload":
    _render_upload()
else:
    _render_editor()