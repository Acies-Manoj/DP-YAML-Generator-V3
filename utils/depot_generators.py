"""
YAML generators for Snowflake Depot files.
Generates: Instance Secret R, Instance Secret RW, Depot, Scanner
Used by: pages/6_Depot.py
"""


def generate_secret_r_yaml(d: dict) -> str:
    return f"""name: {d['name']}-r
version: v1
type: instance-secret
description: "{d['desc_r']}"
layer: {d['layer']}
instance-secret:
  type: key-value-properties
  acl: r
  data:
    username: {d['username']}
    password: {d['password']}
"""


def generate_secret_rw_yaml(d: dict) -> str:
    return f"""name: {d['name']}-rw
version: v1
type: instance-secret
description: "{d['desc_rw']}"
layer: {d['layer']}
instance-secret:
  type: key-value-properties
  acl: rw
  data:
    username: {d['username']}
    password: {d['password']}
"""


def generate_depot_yaml(d: dict) -> str:
    version = d.get("version", "v2alpha") or "v2alpha"
    dtype   = d.get("type", "depot") or "depot"

    lines = []
    lines.append(f"name: {d['name']}")
    lines.append(f"version: {version}")
    lines.append(f"type: {dtype}")
    lines.append(f"description: {d['description']}")

    if d.get("tags"):
        lines.append("tags:")
        for t in d["tags"]:
            if t.strip():
                lines.append(f"  - {t.strip()}")

    lines.append(f"layer: {d['layer']}")
    lines.append("depot:")
    lines.append(f"  name: {d['name']}")
    lines.append("  type: snowflake")
    lines.append(f"  external: {'true' if d.get('external', True) else 'false'}")
    lines.append("  secrets:")
    lines.append(f"    - name: {d['name']}-r")
    lines.append("      allkeys: true")
    lines.append(f"    - name: {d['name']}-rw")
    lines.append("      allkeys: true")
    lines.append("  snowflake:")
    lines.append(f"    warehouse: {d['warehouse']}")
    lines.append(f"    url: {d['url']}")
    lines.append(f"    database: {d['database']}")
    lines.append(f"    account: {d['account']}")

    return "\n".join(lines) + "\n"


def generate_scanner_yaml(d: dict) -> str:
    version = d.get("version", "v1") or "v1"
    dtype   = d.get("type", "workflow") or "workflow"

    lines = []
    lines.append(f"version: {version}")
    lines.append(f"name: {d['workflow_name']}")
    lines.append(f"type: {dtype}")

    if d.get("tags"):
        lines.append("tags:")
        for t in d["tags"]:
            if t.strip():
                lines.append(f"  - {t.strip()}")

    lines.append(f"description: {d['description']}")
    lines.append("")
    lines.append("workflow:")
    lines.append("  dag:")
    lines.append(f"    - name: {d['workflow_name']}")
    lines.append(f"      description: {d['dag_description']}")
    lines.append("      spec:")
    lines.append(f"        stack: {d['stack']}")
    lines.append("        tags:")
    lines.append("          - scanner")
    lines.append(f"        compute: {d['compute']}")
    lines.append(f"        runAsUser: {d['run_as_user']}")
    lines.append("")
    lines.append("        stackSpec:")
    lines.append(f"          depot: dataos://{d['depot_name']}")
    lines.append("")
    lines.append("          sourceConfig:")
    lines.append("            config:")
    lines.append(f"              includeTables: {'true' if d.get('include_tables', True) else 'false'}")
    lines.append(f"              includeViews: {'true' if d.get('include_views', True) else 'false'}")

    schemas = [s.strip() for s in d.get("schemas", []) if s.strip()]
    if schemas:
        lines.append("              schemaFilterPattern:")
        lines.append("                includes:")
        for s in schemas:
            lines.append(f"                  - ^{s}$")

    return "\n".join(lines) + "\n"