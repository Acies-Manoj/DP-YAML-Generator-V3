"""
utils/folder_scanner.py — Scan a DP folder and return deployable YAML files.

Walks the folder using os.walk(), skips non-deployable directories,
and classifies each .yml/.yaml file as either:
  - deployable : standalone files that can be applied/deleted directly
  - model_file : individual table/view/sql files inside model/ that are
                 deployed via Lens, not individually

Each FileInfo dict contains:
  filename  : "deployment.yml"
  rel_path  : "build/semantic-model/deployment.yml"   (always forward-slash)
  abs_path  : "C:\\...\\build\\semantic-model\\deployment.yml"  (OS native)
"""

import os

# Folders to skip entirely during walk
_SKIP_DIRS = frozenset({
    "__pycache__", ".git", ".gitignore", "node_modules",
    ".desc_cache", ".venv", "venv", ".idea", ".vscode",
})

# rel_path substrings that mark a file as a model file (not standalone-deployable)
_MODEL_INDICATORS = ("model/sqls/", "model/tables/", "model/views/")


def scan_folder(dp_dir: str) -> dict:
    """
    Walk dp_dir and return all deployable YAML files with full absolute paths.

    Parameters
    ──────────
    dp_dir : root folder of the data product (e.g. C:\\...\\my-data-product)

    Returns
    ───────
    {
        "deployable":  [FileInfo, ...],   # standalone-deployable files
        "model_files": [FileInfo, ...],   # model/ files (lens-deployed)
    }
    """
    dp_dir = os.path.normpath(dp_dir)
    deployable  = []
    model_files = []

    for root, dirs, files in os.walk(dp_dir):
        # Prune skipped directories in-place (prevents descending into them)
        dirs[:] = sorted(
            d for d in dirs
            if d not in _SKIP_DIRS and not d.startswith(".")
        )

        for fname in sorted(files):
            if not fname.lower().endswith((".yml", ".yaml")):
                continue

            abs_path = os.path.join(root, fname)
            rel_native = os.path.relpath(abs_path, dp_dir)
            rel_path   = rel_native.replace("\\", "/")   # always forward-slash for display

            info = {
                "filename": fname,
                "rel_path": rel_path,          # display + save to sequences.json
                "abs_path": abs_path,           # passed directly to CLI command
            }

            if any(ind in rel_path for ind in _MODEL_INDICATORS):
                model_files.append(info)
            else:
                deployable.append(info)

    return {
        "deployable":  sorted(deployable,  key=lambda x: x["rel_path"]),
        "model_files": sorted(model_files, key=lambda x: x["rel_path"]),
    }
