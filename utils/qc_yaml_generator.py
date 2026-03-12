"""
utils/yaml_generator.py
Assembles the complete Soda workflow YAML from metadata + accepted checks.
"""

import yaml as _yaml
from typing import Any


# ─────────────────────────────────────────────────────────────
# Force block style for multiline strings (for failed queries)
# ─────────────────────────────────────────────────────────────
def _str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_yaml.add_representer(str, _str_presenter)


# ─────────────────────────────────────────────────────────────
# Main YAML Builder
# ─────────────────────────────────────────────────────────────

def generate_qc_yaml(
    metadata: dict,
    accepted_checks: list[dict],
    dataset_udl: str,
    workspace: str,
    engine: str | None = None,
    cluster: str | None = None,
) -> str:
    """
    Build the complete Soda workflow YAML string.

    Args:
        metadata: {
            "workflow_name": str,
            "description":   str,
            "tags":          list[str],
        }
        accepted_checks: list of check dicts
        dataset_udl:     e.g. "dataos://depot:DB.SCHEMA/TABLE"
        workspace:       workspace name (mandatory)
        engine:          optional execution engine
        cluster:         optional cluster name
    """

    checks_block = _build_checks_block(accepted_checks)

    # ─────────────────────────────────────────────
    # Dataset block
    # ─────────────────────────────────────────────
    dataset_block = {
        "dataset": dataset_udl
    }

    # Optional execution options
    if engine or cluster:
        dataset_block["options"] = {}
        if engine:
            dataset_block["options"]["engine"] = engine
        if cluster:
            dataset_block["options"]["clusterName"] = cluster

    dataset_block["profile"] = {
        "columns": [
            {"include": "*"}
        ]
    }

    dataset_block["checks"] = checks_block

    # ─────────────────────────────────────────────
    # Full YAML document
    # ─────────────────────────────────────────────
    doc = {
        "name": metadata["workflow_name"],
        "version": "v1",
        "type": "workflow",
        "tags": metadata.get("tags", []),
        "description": metadata.get("description", ""),
        "workspace": workspace,
        "workflow": {
            "dag": [
                {
                    "name": f"dag-{metadata['workflow_name']}",
                    "spec": {
                        "stack": "soda+python:1.0",
                        "compute": "runnable-default",
                        "resources": {
                            "requests": {
                                "cpu": "1000m",
                                "memory": "250Mi"
                            },
                            "limits": {
                                "cpu": "2000m",
                                "memory": "500Mi"
                            }
                        },
                        "logLevel": "INFO",
                        "stackSpec": {
                            "inputs": [
                                dataset_block
                            ]
                        }
                    }
                }
            ]
        }
    }

    return _yaml.dump(
        doc,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        indent=2,
        width=120,
    )


# ─────────────────────────────────────────────────────────────
# Convert checks to YAML structure
# ─────────────────────────────────────────────────────────────
def _build_checks_block(accepted_checks: list[dict]) -> list:
    """
    Convert accepted check dicts into the YAML-serialisable checks list.
    """

    result = []

    for chk in accepted_checks:
        syntax = chk["syntax"]
        body = chk.get("body")
        name = chk["name"]
        category = chk["category"]

        entry: dict[str, Any] = {}

        # ─────────────────────────────────────────
        # Schema checks
        # ─────────────────────────────────────────
        if syntax == "schema":
            inner = {"name": name}

            if body:
                inner.update(body)

            inner["attributes"] = {"category": category}
            entry["schema"] = inner

        # ─────────────────────────────────────────
        # Checks with sub-parameters (invalid_count, failed rows, etc.)
        # ─────────────────────────────────────────
        elif body:
            inner: dict[str, Any] = {"name": name}
            inner.update(body)
            inner["attributes"] = {"category": category}
            entry[syntax] = inner

        # ─────────────────────────────────────────
        # Simple checks
        # ─────────────────────────────────────────
        else:
            entry[syntax] = {
                "name": name,
                "attributes": {
                    "category": category
                },
            }

        result.append(entry)

    return result