"""
10_History.py — Generation History viewer for DP YAML Generator.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

st.set_page_config(page_title="Generation History", page_icon="🕓", layout="wide")

from utils.ui_utils import load_global_css, render_sidebar, section_header
from utils.history  import get_history, get_entry, delete_entry, clear_all, get_stats, init_db

load_global_css()
render_sidebar()
init_db()

# ── Label maps ────────────────────────────────────────────────────────────────
DP_TYPE_LABELS = {
    "":         "All Types",
    "CADP":     "CADP",
    "SADP":     "SADP",
    "Specific": "Specific File",
}

FILE_TYPE_LABELS = {
    "":               "All Files",
    "bundle":         "Bundle",
    "spec":           "Spec",
    "scanner":        "Scanner",
    "lens":           "Lens Deployment",
    "table":          "Table YAML",
    "view":           "View YAML",
    "sql":            "SQL File",
    "depot":          "Depot",
    "secret_r":       "Instance Secret (R)",
    "secret_rw":      "Instance Secret (RW)",
    "flare":          "Flare Job",
    "quality_checks": "Quality Checks",
    "user_groups":    "User Groups",
    "repo_cred":      "Repo Credential",
    "zip_cadp":       "ZIP — Full CADP",
    "zip_sadp":       "ZIP — Full SADP",
    "zip_sm":         "ZIP — Semantic Model",
    "zip_depot":      "ZIP — Depot",
}

FILE_TYPE_ICONS = {
    "bundle": "📦", "spec": "📋", "scanner": "🔍", "lens": "🔭",
    "table": "📄", "view": "📄", "sql": "🗄️", "depot": "🏗️",
    "secret_r": "🔑", "secret_rw": "🔑", "flare": "⚡",
    "quality_checks": "✅", "user_groups": "👥", "repo_cred": "🔐",
    "zip_cadp": "🗜️", "zip_sadp": "🗜️", "zip_sm": "🗜️", "zip_depot": "🗜️",
}

DP_TYPE_COLORS = {
    "CADP":     "#3b82f6",
    "SADP":     "#10b981",
    "Specific": "#a78bfa",
}

# ── Page styles ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
.hist-card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 2px;
}
.hist-card:hover { border-color: #374151; }
.hist-filename {
    font-size: 14px;
    font-weight: 600;
    color: #f3f4f6;
}
.hist-meta {
    font-size: 12px;
    color: #9ca3af;
    margin-top: 5px;
}
.hist-dp-tag {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 9px;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-right: 6px;
}
.hist-zip-tag {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 9px;
    border-radius: 20px;
    background: #f9731622;
    color: #fb923c;
    margin-right: 6px;
}
.hist-dp-name {
    font-size: 12px;
    color: #d1d5db;
    margin-left: 4px;
}
.stat-card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
}
.stat-value {
    font-size: 24px;
    font-weight: 700;
    line-height: 1.1;
}
.stat-label {
    font-size: 11px;
    color: #9ca3af;
    margin-top: 5px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🕓 Generation History")
st.markdown(
    '<p style="color:#9ca3af;font-size:13px;margin-top:-8px;margin-bottom:20px;">'
    'All files generated in the last 30 days. Entries auto-delete after 30 days.'
    '</p>',
    unsafe_allow_html=True,
)

# ── Stats bar ─────────────────────────────────────────────────────────────────
stats = get_stats()
s1, s2, s3, s4, s5 = st.columns(5)

def _stat(col, label, value, color):
    col.markdown(
        f'<div class="stat-card" style="border-left:3px solid {color};">'
        f'<div class="stat-value" style="color:{color};">{value}</div>'
        f'<div class="stat-label">{label}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

_stat(s1, "Total",    stats["total"],    "#6b7280")
_stat(s2, "CADP",     stats["cadp"],     "#3b82f6")
_stat(s3, "SADP",     stats["sadp"],     "#10b981")
_stat(s4, "Specific", stats["specific"], "#a78bfa")
_stat(s5, "ZIPs",     stats["zips"],     "#f97316")

st.markdown("<br>", unsafe_allow_html=True)

# ── Filters ───────────────────────────────────────────────────────────────────
f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
with f1:
    dp_filter = st.selectbox(
        "Filter by Type",
        options=list(DP_TYPE_LABELS.keys()),
        format_func=lambda k: DP_TYPE_LABELS[k],
        key="hist_dp_filter",
    )
with f2:
    ft_filter = st.selectbox(
        "Filter by File",
        options=list(FILE_TYPE_LABELS.keys()),
        format_func=lambda k: FILE_TYPE_LABELS[k],
        key="hist_ft_filter",
    )
with f3:
    show_zips = st.checkbox("Include ZIP entries", value=False, key="hist_show_zips")
with f4:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑 Clear All", use_container_width=True):
        st.session_state["hist_confirm_clear"] = True

if st.session_state.get("hist_confirm_clear"):
    st.warning("⚠️ This will permanently delete all history. Are you sure?")
    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("Yes, delete everything", type="primary", use_container_width=True):
            clear_all()
            st.session_state.pop("hist_confirm_clear", None)
            st.success("History cleared.")
            st.rerun()
    with cc2:
        if st.button("Cancel", use_container_width=True):
            st.session_state.pop("hist_confirm_clear", None)
            st.rerun()

st.divider()

# ── Fetch rows ────────────────────────────────────────────────────────────────
rows = get_history(dp_type=dp_filter or None, file_type=ft_filter or None, limit=300)
if not show_zips:
    rows = [r for r in rows if not r["is_zip"]]

if not rows:
    st.markdown(
        '<div style="text-align:center;padding:48px 0;color:#6b7280;font-size:14px;">'
        '📭 No history entries found.<br>'
        '<span style="font-size:12px;color:#4b5563;">Generate some files to see them here.</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()

st.markdown(f'<p style="color:#9ca3af;font-size:13px;margin-bottom:12px;"><b style="color:#e5e7eb;">{len(rows)}</b> entries</p>', unsafe_allow_html=True)

# ── Entry cards ───────────────────────────────────────────────────────────────
if "hist_view_id" not in st.session_state:
    st.session_state.hist_view_id = None

for row in rows:
    ftype    = row["file_type"]
    dp_type  = row["dp_type"]
    icon     = FILE_TYPE_ICONS.get(ftype, "📄")
    dp_color = DP_TYPE_COLORS.get(dp_type, "#6b7280")
    ft_label = FILE_TYPE_LABELS.get(ftype, ftype)
    ts       = row["created_at"].replace("T", " · ")
    dp_name  = row.get("dp_name") or ""
    is_zip   = bool(row["is_zip"])
    entry_id = row["id"]

    col_info, col_actions = st.columns([5, 2])

    with col_info:
        dp_name_html = f'<span class="hist-dp-name">· {dp_name}</span>' if dp_name else ""
        zip_html = '<span class="hist-zip-tag">ZIP</span>' if is_zip else ""
        st.markdown(
            f'<div class="hist-card">'
            f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;margin-bottom:6px;">'
            f'<span class="hist-dp-tag" style="background:{dp_color}22;color:{dp_color};">{dp_type}</span>'
            f'{zip_html}'
            f'<span class="hist-filename">{icon} {row["file_name"]}</span>'
            f'{dp_name_html}'
            f'</div>'
            f'<div class="hist-meta">'
            f'<span style="color:#60a5fa;">{ft_label}</span>'
            f'&nbsp;·&nbsp;{ts}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_actions:
        st.markdown("<br>", unsafe_allow_html=True)
        a1, a2, a3 = st.columns(3)
        with a1:
            is_open = (st.session_state.hist_view_id == entry_id)
            if st.button(
                "Hide" if is_open else "View",
                key=f"hist_view_{entry_id}",
                use_container_width=True,
            ):
                st.session_state.hist_view_id = None if is_open else entry_id
                st.rerun()
        with a2:
            if not is_zip:
                mime = "text/plain" if ftype == "sql" else "text/yaml"
                st.download_button(
                    "↓ Get",
                    data=row["content"],
                    file_name=row["file_name"],
                    mime=mime,
                    key=f"hist_dl_{entry_id}",
                    use_container_width=True,
                )
            else:
                st.button("↓ Get", key=f"hist_dl_{entry_id}",
                          disabled=True, use_container_width=True,
                          help="Re-download not available for ZIPs.")
        with a3:
            if st.button("🗑", key=f"hist_del_{entry_id}",
                         use_container_width=True, help="Delete this entry"):
                delete_entry(entry_id)
                if st.session_state.hist_view_id == entry_id:
                    st.session_state.hist_view_id = None
                st.rerun()

    # Inline viewer
    if st.session_state.hist_view_id == entry_id:
        lang = "sql" if ftype == "sql" else "yaml"
        st.code(row["content"], language=lang)

    st.markdown("<div style='margin-bottom:4px;'></div>", unsafe_allow_html=True)