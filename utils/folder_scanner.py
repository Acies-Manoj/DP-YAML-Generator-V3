"""
utils/folder_scanner.py — Scan a DP folder and return all YAML files.

Walks the folder using os.walk(), skips system/tool directories,
and returns every .yml/.yaml file found with its full absolute path.

No classification is done — the user decides which files to deploy.

Each FileInfo dict contains:
  filename  : "deployment.yml"
  rel_path  : "build/semantic-model/deployment.yml"   (always forward-slash)
  abs_path  : "C:\\...\\build\\semantic-model\\deployment.yml"  (OS native)
"""

import os

# Folders to skip entirely during walk — system/tool folders only
_SKIP_DIRS = frozenset({
    "__pycache__", ".git", "node_modules",
    ".desc_cache", ".venv", "venv", ".idea", ".vscode",
})


def scan_folder(dp_dir: str) -> dict:
    """
    Walk dp_dir and return all YAML files with full absolute paths.

    Parameters
    ──────────
    dp_dir : root folder of the data product (e.g. C:\\...\\my-data-product)

    Returns
    ───────
    {
        "deployable":  [FileInfo, ...],   # all YAML files found
        "model_files": [],                # always empty — no classification
    }
    """
    dp_dir = os.path.normpath(dp_dir)
    all_files = []

    for root, dirs, files in os.walk(dp_dir):
        # Prune skipped directories in-place
        dirs[:] = sorted(
            d for d in dirs
            if d not in _SKIP_DIRS and not d.startswith(".")
        )

        for fname in sorted(files):
            if not fname.lower().endswith((".yml", ".yaml")):
                continue

            abs_path   = os.path.join(root, fname)
            rel_native = os.path.relpath(abs_path, dp_dir)
            rel_path   = rel_native.replace("\\", "/")

            all_files.append({
                "filename": fname,
                "rel_path": rel_path,
                "abs_path": abs_path,
            })

    return {
        "deployable":  sorted(all_files, key=lambda x: x["rel_path"]),
        "model_files": [],   # removed — user decides what to deploy
    }