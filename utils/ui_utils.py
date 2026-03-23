"""
ui_utils.py — Shared UI helpers for all pages.
Loads the global CSS design system and provides reusable HTML components.
"""

import os
import streamlit as st


def _clear_nav_state():
    """Clear all flow-specific session state keys before navigating."""
    for _k in ["sm_mode", "sm_origin", "semantic_section",
                "dp_origin", "dp_step", "dp_entry_step",
                "depot_origin", "depot_specific_file", "flare_origin",
                "cadp_qc_origin", "sadp_qc_origin"]:
        st.session_state.pop(_k, None)


def render_sidebar():
    """Render the persistent sidebar with title, Home and History navigation."""
    with st.sidebar:
        st.markdown(
            '<div style="padding:16px 8px 8px 8px;">'
            '<p style="font-size:16px;font-weight:700;color:#f3f4f6;margin:0;letter-spacing:-0.01em;">'
            '⚙️ DP YAML Generator</p>'
            '<p style="font-size:11px;color:#6b7280;margin:4px 0 0 0;">YAML & SQL file builder</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="border-top:1px solid #1f2937;margin:8px 0 12px 0;"></div>',
            unsafe_allow_html=True,
        )
        if st.button("🏠  Home", key="sb_home", use_container_width=True):
            _clear_nav_state()
            st.switch_page("app.py")
        if st.button("🕓  History", key="sb_history", use_container_width=True):
            st.switch_page("pages/10_History.py")
def load_global_css():
    """Inject the global CSS design system."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "assets", "style.css")
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

    # Hide Streamlit's auto-generated page navigation list only
    st.markdown("""
        <style>
            [data-testid="stSidebarNav"] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)



def section_header(icon: str, title: str):
    """Render a styled section header with left accent border."""
    st.markdown(
        f'<div class="section-header"><span>{icon}</span><h4>{title}</h4></div>',
        unsafe_allow_html=True,
    )


def group_label(title: str, dot_class: str = "dot-blue"):
    """Render a category group label with a colored dot."""
    st.markdown(
        f'<div class="group-label"><span class="dot {dot_class}"></span>{title}</div>',
        unsafe_allow_html=True,
    )


def yaml_tab(filename: str):
    """Render a code-editor-style tab bar above a YAML preview block."""
    st.markdown(
        f'<div class="yaml-tab"><span class="yaml-dot"></span>{filename}</div>',
        unsafe_allow_html=True,
    )


def app_footer():
    """Render the app footer."""
    st.markdown(
        '<div class="app-footer">⚙️ &nbsp; Internal Automation Tool — YAML & SQL Generation</div>',
        unsafe_allow_html=True,
    )


# ── Docs URL registry ─────────────────────────────────────────────────────────
DOCS_URLS = {
    "lens":        ("Lens Docs",        "https://dataos.info/resources/lens/"),
    "segments":    ("Segments Docs",    "https://dataos.info/resources/lens/segments/"),
    "user_groups": ("User Groups Docs", "https://dataos.info/resources/lens/user_groups_and_data_policies/"),
    "views":       ("Views Docs",       "https://dataos.info/resources/lens/views/"),
    "bundle":      ("Bundle Docs",      "https://dataos.info/resources/bundle/"),
    "spec":        ("DP Spec Docs",     "https://dataos.info/learn/dp_foundations1_learn_track/create_dp_spec/"),
    "scanner":     ("Scanner Docs",     "https://dataos.info/resources/stacks/scanner/"),
    "depot":       ("Depot Docs",       "https://dataos.info/resources/depot/"),
    "flare":       ("Flare Docs",       "https://dataos.info/resources/stacks/flare/"),
    "dp_learn":    ("DP Learn Track",   "https://dataos.info/learn/dp_developer_learn_track/"),
}


def floating_docs(*keys: str):
    """Render a floating docs button (bottom-right).
    Pass one key for a single button, multiple keys for a multi-link panel.
    Keys must be from DOCS_URLS registry.
    """
    # Build CSS only once per render (idempotent — browsers deduplicate)
    css = """
<style>
.floating-docs {
    position: fixed; bottom: 28px; right: 28px; z-index: 9999;
    display: flex; flex-direction: column; align-items: flex-end; gap: 8px;
}
.floating-docs a {
    display: flex; align-items: center; gap: 8px;
    background: #1e2638; border: 1px solid #3b82f6;
    color: #93c5fd !important; text-decoration: none !important;
    padding: 10px 16px; border-radius: 999px;
    font-size: 13px; font-weight: 600; font-family: 'DM Sans', sans-serif;
    box-shadow: 0 4px 16px rgba(59,130,246,0.25); transition: all 0.2s ease;
    white-space: nowrap;
}
.floating-docs a:hover {
    background: #253047; border-color: #60a5fa; color: #bfdbfe !important;
    box-shadow: 0 6px 20px rgba(59,130,246,0.4); transform: translateY(-2px);
}
</style>"""
    links_html = "\n".join(
        f'    <a href="{DOCS_URLS[k][1]}" target="_blank">📖 {DOCS_URLS[k][0]}</a>'
        for k in keys if k in DOCS_URLS
    )
    st.markdown(
        f'{css}\n<div class="floating-docs">\n{links_html}\n</div>',
        unsafe_allow_html=True,
    )


def inline_docs_banner(*keys: str):
    """Render a compact inline docs link bar (useful inside step wizards)."""
    links = " &nbsp;·&nbsp; ".join(
        f'<a href="{DOCS_URLS[k][1]}" target="_blank" '
        f'style="color:#60a5fa;font-size:12px;text-decoration:none;">📖 {DOCS_URLS[k][0]}</a>'
        for k in keys if k in DOCS_URLS
    )
    st.markdown(
        f'<div style="margin-bottom:12px; padding:8px 12px; background:#111827; '
        f'border:1px solid #1f2937; border-radius:8px;">{links}</div>',
        unsafe_allow_html=True,
    )