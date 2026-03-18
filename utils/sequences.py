"""
utils/sequences.py — Saved playbook persistence for Sequence Runner.

Sequences are stored in sequences.json next to app.py.

Schema
──────
{
  "sequences": [
    {
      "name": "Redeploy after SM change",
      "created_at": "2025-01-15T10:30:00",
      "updated_at": "2025-01-15T12:00:00",   // optional, set on edit
      "steps": [
        { "action": "delete", "rel_path": "dp-deployment/bundle.yml" },
        { "action": "delete", "rel_path": "build/semantic-model/deployment.yml" },
        { "action": "apply",  "rel_path": "build/semantic-model/deployment.yml" },
        { "action": "apply",  "rel_path": "dp-deployment/bundle.yml" }
      ]
    }
  ]
}

Note: Only rel_paths are stored. Absolute paths are resolved at runtime
by combining the current DATAOS_DP_DIR with each rel_path. This means
saved playbooks work across different machines or if the folder is moved.
"""

import json
import os
import datetime

_SEQ_PATH = os.path.join(os.path.dirname(__file__), "..", "sequences.json")


def load_sequences() -> list:
    """Return all saved sequences as a list of dicts, newest first."""
    if not os.path.exists(_SEQ_PATH):
        return []
    try:
        with open(_SEQ_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("sequences", [])
    except Exception:
        return []


def save_sequence(name: str, steps: list) -> None:
    """
    Save (or update) a sequence by name.

    steps must be a list of:
        { "action": "apply"|"delete", "rel_path": "..." }

    Existing sequence with the same name is updated in-place.
    New names are appended.
    """
    seqs = load_sequences()
    now  = datetime.datetime.now().isoformat(timespec="seconds")

    for seq in seqs:
        if seq["name"] == name:
            seq["steps"]      = steps
            seq["updated_at"] = now
            break
    else:
        seqs.append({
            "name":       name,
            "created_at": now,
            "steps":      steps,
        })

    _write(seqs)


def delete_sequence(name: str) -> None:
    """Delete a saved sequence by name. No-op if name not found."""
    seqs = [s for s in load_sequences() if s["name"] != name]
    _write(seqs)


def rename_sequence(old_name: str, new_name: str) -> None:
    """Rename a saved sequence."""
    seqs = load_sequences()
    for seq in seqs:
        if seq["name"] == old_name:
            seq["name"] = new_name
            break
    _write(seqs)


def _write(seqs: list) -> None:
    with open(_SEQ_PATH, "w", encoding="utf-8") as f:
        json.dump({"sequences": seqs}, f, indent=2, ensure_ascii=False)
