"""
utils/dp_editor.py — ZIP/folder helpers for the DP Editor page.

Functions
─────────
parse_zip(uploaded_file)  → dict[str, str]
build_zip(files, name)    → BytesIO
get_file_tree(files)      → dict[str, list[str]]
detect_language(filename) → "yaml" | "sql" | "json" | "text"
get_changed_files(orig, current) → dict[str, str]
"""

import io
import zipfile
from pathlib import Path


# ── File type detection ───────────────────────────────────────────────────────

_EXT_MAP = {
    ".yml":  "yaml",
    ".yaml": "yaml",
    ".sql":  "sql",
    ".json": "json",
    ".md":   "markdown",
    ".txt":  "text",
    ".sh":   "sh",
    ".env":  "text",
}

_SKIP_EXTENSIONS = {".pyc", ".pyo", ".class", ".db"}

# Folder name segments that should be excluded entirely
_SKIP_FOLDER_SEGMENTS = {
    ".git", "__macosx", ".github", "__pycache__",
    ".idea", ".vscode", "node_modules",
}


def detect_language(filename: str) -> str:
    """Return the Ace editor language string for a given filename."""
    ext = Path(filename).suffix.lower()
    return _EXT_MAP.get(ext, "text")


# ── ZIP parse / build ─────────────────────────────────────────────────────────

def parse_zip(uploaded_file) -> dict[str, str]:
    """
    Extract a ZIP file and return a dict mapping file paths to content strings.
    Binary files and system files are skipped.
    Paths are normalised to forward slashes. Leading shared root folder is stripped.
    """
    raw: dict[str, str] = {}

    with zipfile.ZipFile(io.BytesIO(uploaded_file.read())) as zf:
        for info in zf.infolist():
            # Normalise to forward slashes immediately (Windows ZIPs use backslashes)
            path = info.filename.replace("\\", "/").strip("/")

            if info.is_dir():
                continue

            # Split into parts and check every segment
            parts = [p for p in path.split("/") if p]
            if not parts:
                continue

            # Skip if any path segment is a known system folder
            if any(p.lower() in _SKIP_FOLDER_SEGMENTS for p in parts):
                continue

            # Skip hidden files/folders (starts with dot) at any level
            if any(p.startswith(".") for p in parts):
                continue

            # Skip by extension
            if Path(parts[-1]).suffix.lower() in _SKIP_EXTENSIONS:
                continue

            try:
                content = zf.read(info.filename).decode("utf-8")
                raw[path] = content
            except (UnicodeDecodeError, KeyError):
                continue

    if not raw:
        return raw

    # Strip common root folder if all files share one top-level folder
    all_parts = [p.split("/") for p in raw]
    if all(len(p) > 1 for p in all_parts):
        roots = {p[0] for p in all_parts}
        if len(roots) == 1:
            root = roots.pop() + "/"
            raw = {k[len(root):]: v for k, v in raw.items() if k.startswith(root)}

    return raw


def build_zip(files: dict[str, str], zip_name: str = "data_product") -> io.BytesIO:
    """
    Build a ZIP from a dict of {path: content} and return a BytesIO buffer.
    """
    buf = io.BytesIO()
    folder = Path(zip_name).stem
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(f"{folder}/{path}", content)
    buf.seek(0)
    return buf


# ── File tree builder ─────────────────────────────────────────────────────────

def get_file_tree(files: dict[str, str]) -> dict[str, list[str]]:
    """
    Build a folder → [filenames] mapping from the flat files dict.
    Root-level files are stored under the key "" (empty string).
    All paths use forward slashes.
    """
    tree: dict[str, list[str]] = {}
    for path in sorted(files.keys()):
        # Ensure forward slashes (defensive — should already be normalised)
        path = path.replace("\\", "/")
        if "/" in path:
            folder, fname = path.rsplit("/", 1)
        else:
            folder, fname = "", path
        tree.setdefault(folder, []).append(fname)
    return tree


# ── Diff helper ───────────────────────────────────────────────────────────────

def get_changed_files(
    original: dict[str, str],
    current: dict[str, str],
) -> dict[str, str]:
    """
    Return only files whose content differs from the original snapshot,
    plus any files added in the current session.
    """
    changed = {}
    for path, content in current.items():
        if original.get(path) != content:
            changed[path] = content
    return changed