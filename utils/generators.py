"""
YAML and file generators for the Semantic Model.
Used by: pages/1_CADP.py (Table YAML, View YAML, Lens Deployment builders)
"""


def generate_table_yaml(table: dict) -> str:
    """Generate Table YAML string from a table dict."""
    lines = []
    lines.append("tables:")
    lines.append(f"  - name: {table['name']}")
    lines.append(f"    sql: {{{{ load_sql('{table['name']}') }}}}")
    if table.get("description", "").strip():
        lines.append(f'    description: "{table["description"].strip()}"')
    if not table.get("public", True):
        lines.append("    public: false")

    if table.get("joins"):
        valid = [j for j in table["joins"] if j.get("name", "").strip()]
        if valid:
            lines.append("")
            lines.append("    joins:")
            for j in valid:
                lines.append(f"      - name: {j['name'].strip()}")
                lines.append(f"        relationship: {j['relationship']}")
                lines.append(f'        sql: "{j["sql"].strip()}"')

    if table.get("dimensions"):
        valid = [d for d in table["dimensions"] if d.get("name", "").strip()]
        if valid:
            lines.append("")
            lines.append("    dimensions:")
            for d in valid:
                lines.append(f"      - name: {d['name'].strip()}")
                lines.append(f"        type: {d['type']}")
                col = d.get("column", "").strip() or d["name"].strip().upper()
                lines.append(f"        column: {col}")
                if d.get("description", "").strip():
                    lines.append(f'        description: "{d["description"].strip()}"')
                if d.get("primary_key"):
                    lines.append("        primary_key: true")
                if not d.get("public", True):
                    lines.append("        public: false")
                lines.append("")

    if table.get("measures"):
        valid = [m for m in table["measures"] if m.get("name", "").strip()]
        if valid:
            lines.append("    measures:")
            for m in valid:
                lines.append(f"      - name: {m['name'].strip()}")
                lines.append(f'        sql: "{m["sql"].strip()}"')
                lines.append(f"        type: {m['type']}")
                if m.get("description", "").strip():
                    lines.append(f'        description: "{m["description"].strip()}"')
                lines.append("")

    if table.get("segments"):
        valid = [s for s in table["segments"] if s.get("name", "").strip()]
        if valid:
            lines.append("    segments:")
            for s in valid:
                lines.append(f"      - name: {s['name'].strip()}")
                lines.append(f'        sql: "{s["sql"].strip()}"')
                if s.get("description", "").strip():
                    lines.append(f"        description: {s['description'].strip()}")
                inc = s.get("includes", [])
                exc = s.get("excludes", [])
                if inc or exc:
                    lines.append("        meta:")
                    lines.append("          secure:")
                    lines.append("            user_groups:")
                    if inc:
                        lines.append("              includes:")
                        for g in inc:
                            lines.append(f"                - {g}")
                    if exc:
                        lines.append("              excludes:")
                        for g in exc:
                            lines.append(f"                - {g}")
                lines.append("")

    return "\n".join(lines)


def generate_view_yaml(view: dict) -> str:
    """Generate View YAML string from a view dict."""
    lines = []
    lines.append("views:")
    lines.append(f"  - name: {view['name'].strip()}")
    if view.get("description", "").strip():
        lines.append(f"    description: {view['description'].strip()}")
    lines.append(f"    public: {'true' if view.get('public', True) else 'false'}")

    meta = view.get("meta", {})
    if meta:
        lines.append("    meta:")
        if meta.get("title", "").strip():
            lines.append(f"      title: {meta['title'].strip()}")
        tags = meta.get("tags", [])
        if tags:
            lines.append("      tags:")
            for t in tags:
                if t.strip():
                    lines.append(f"        - {t.strip()}")
        metric = meta.get("metric", {})
        if metric:
            lines.append("      metric:")
            if metric.get("expression", "").strip():
                lines.append(f'        expression: "{metric["expression"].strip()}"')
            if metric.get("timezone", "").strip():
                lines.append(f'        timezone: "{metric["timezone"].strip()}"')
            if metric.get("window", "").strip():
                lines.append(f'        window: "{metric["window"].strip()}"')
            excludes = metric.get("excludes", [])
            if excludes:
                lines.append("        excludes:")
                for e in excludes:
                    if e.strip():
                        lines.append(f"          - {e.strip()}")

    tables = view.get("tables", [])
    if tables:
        lines.append("    tables:")
        for t in tables:
            if not t.get("join_path", "").strip():
                continue
            lines.append(f"      - join_path: {t['join_path'].strip()}")
            lines.append(f"        prefix: {'true' if t.get('prefix', True) else 'false'}")
            includes = t.get("includes", [])
            if includes:
                lines.append("        includes:")
                for inc in includes:
                    if inc.strip():
                        lines.append(f"          - {inc.strip()}")
            lines.append("")

    return "\n".join(lines)


def generate_lens_yaml(d: dict) -> str:
    """Generate Lens Deployment YAML string from a lens config dict."""
    lines = []
    lines.append(f"version: {d.get('version', 'v1alpha')}")
    lines.append(f"name: \"{d['name']}\"")
    lines.append(f"layer: {d['layer']}")
    lines.append("type: lens")
    lines.append("tags:")
    for t in d.get("tags", ["lens"]):
        if t.strip():
            lines.append(f"  - {t.strip()}")
    lines.append(f"description: {d['description']}")
    lines.append("lens:")
    lines.append(f"  compute: {d['compute']}")
    lines.append("  secrets:")
    for s in d.get("secrets", []):
        if s.get("name", "").strip():
            lines.append(f"    - name: {s['name'].strip()}")
            lines.append(f"      allKeys: {'true' if s.get('allKeys') else 'false'}")
    src = d["source"]
    lines.append("  source:")
    lines.append(f"    type: {src['type']}")
    lines.append(f"    name: {src['name']}")
    lines.append(f"    catalog: {src['catalog']}")
    repo = d["repo"]
    lines.append("  repo:")
    lines.append(f"    url: {repo['url']}")
    lines.append(f"    lensBaseDir: {repo['lensBaseDir']}")
    lines.append("    syncFlags:")
    for sf in repo.get("syncFlags", ["--ref=main"]):
        if sf.strip():
            lines.append(f"      - {sf.strip()}")
    api = d.get("api", {})
    lines.append("")
    lines.append("  api:   # optional")
    lines.append(f"    replicas: {api.get('replicas', 1)} # optional")
    lines.append(f"    logLevel: {api.get('logLevel', 'info')}  # optional")
    lines.append("    # envs:")
    lines.append("    #   LENS2_SCHEDULED_REFRESH_TIMEZONES: \"UTC,America/Vancouver,America/Toronto\"")
    lines.append("    resources: # optional")
    lines.append("      requests:")
    lines.append(f"        cpu: {api.get('req_cpu', '100m')}")
    lines.append(f"        memory: {api.get('req_mem', '256Mi')}")
    lines.append("      limits:")
    lines.append(f"        cpu: {api.get('lim_cpu', '500m')}")
    lines.append(f"        memory: {api.get('lim_mem', '500Mi')}")
    wkr = d.get("worker", {})
    lines.append("  worker: # optional")
    lines.append(f"    replicas: {wkr.get('replicas', 1)} # optional")
    lines.append(f"    logLevel: {wkr.get('logLevel', 'debug')}  # optional")
    lines.append("    # envs:")
    lines.append("    #   LENS2_SCHEDULED_REFRESH_TIMEZONES: \"UTC,America/Vancouver,America/Toronto\"")
    lines.append("    resources: # optional")
    lines.append("      requests:")
    lines.append(f"        cpu: {wkr.get('req_cpu', '100m')}")
    lines.append(f"        memory: {wkr.get('req_mem', '256Mi')}")
    lines.append("      limits:")
    lines.append(f"        cpu: {wkr.get('lim_cpu', '500m')}")
    lines.append(f"        memory: {wkr.get('lim_mem', '500Mi')}")
    rtr = d.get("router", {})
    lines.append("  router: # optional")
    lines.append(f"    logLevel: {rtr.get('logLevel', 'info')}  # optional")
    lines.append("    # envs:")
    lines.append("    #   LENS2_SCHEDULED_REFRESH_TIMEZONES: \"UTC,America/Vancouver,America/Toronto\"")
    lines.append("    resources: # optional")
    lines.append("      requests:")
    lines.append(f"        cpu: {rtr.get('req_cpu', '100m')}")
    lines.append(f"        memory: {rtr.get('req_mem', '256Mi')}")
    lines.append("      limits:")
    lines.append(f"        cpu: {rtr.get('lim_cpu', '500m')}")
    lines.append(f"        memory: {rtr.get('lim_mem', '500Mi')}")
    lines.append("  # iris:")
    lines.append("  #   logLevel: info")
    lines.append("  #   resources:")
    lines.append("  #     requests:")
    lines.append("  #       cpu: 200m")
    lines.append("  #       memory: 256Mi")
    lines.append("  #     limits:")
    lines.append("  #       cpu: 1000m")
    lines.append("  #       memory: 1024Mi")
    met = d.get("metric", {})
    lines.append("")
    lines.append("  metric:")
    lines.append(f"    logLevel: {met.get('logLevel', 'info')}")
    return "\n".join(lines)


def generate_user_groups_yaml(groups: list) -> str:
    """Generate user_groups.yaml content from a list of group dicts."""
    lines = ["user_groups:"]
    for g in groups:
        lines.append(f"  - name: {g['name']}")
        lines.append("    api_scopes:")
        for scope in g.get("api_scopes", []):
            lines.append(f"      - {scope}")
        includes = g.get("includes", [])
        lines.append("    includes:")
        if includes == ["*"] or includes == "*":
            lines.append('      - "*"')
        else:
            for uid in includes:
                if uid.strip():
                    lines.append(f"      - {uid.strip()}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_repo_cred_yaml(d: dict) -> str:
    """Generate repo credential instance-secret YAML."""
    lines = []
    lines.append(f"name: {d['name']}")
    lines.append(f"version: {d.get('version', 'v1')}")
    lines.append("type: instance-secret")
    lines.append("tags:")
    for t in d.get("tags", []):
        if t.strip():
            lines.append(f"  - {t.strip()}")
    lines.append(f"description: {d.get('description', '')}")
    lines.append(f"owner: \"{d.get('owner', '')}\"")
    lines.append(f"layer: {d.get('layer', 'user')}")
    lines.append("instance-secret:")
    lines.append(f"  type: {d.get('secret_type', 'key-value')}")
    lines.append(f"  acl: {d.get('acl', 'r')}")
    lines.append("  data:")
    lines.append(f"    GITSYNC_USERNAME: \"{d.get('git_username', '')}\"")
    lines.append(f"    GITSYNC_PASSWORD: \"{d.get('git_password', '')}\"")
    return "\n".join(lines)


def generate_flare_yaml(d: dict) -> str:
    """Generate a Flare Workflow YAML string from a flare job config dict."""
    lines = []
    lines.append(f"version: {d.get('version', 'v1') or 'v1'}")
    lines.append(f"name: {d['name']}")
    lines.append(f"type: {d.get('type', 'workflow') or 'workflow'}")

    tags = [t.strip() for t in d.get("tags", []) if t.strip()]
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {t}")

    if d.get("description", "").strip():
        lines.append(f"description: {d['description'].strip()}")

    lines.append("workflow:")
    if d.get("wf_title", "").strip():
        lines.append(f"  title: {d['wf_title'].strip()}")
    lines.append("  # schedule:")
    if d.get("cron", "").strip():
        lines.append(f"  #   cron: '{d['cron'].strip()}'")
    else:
        lines.append("  #   cron: '00 20 * * *'")
    lines.append("  #   concurrencyPolicy: Forbid")

    dag_name = d.get("dag_name", "").strip()
    if not dag_name:
        wf = d["name"]
        dag_name = "dg-" + wf[3:] if wf.startswith("wf-") else "dg-" + wf

    lines.append("  dag:")
    lines.append(f"  - name: {dag_name}")
    if d.get("dag_title", "").strip():
        lines.append(f"    title: {d['dag_title'].strip()}")
    if d.get("description", "").strip():
        lines.append(f"    description: {d['description'].strip()}")
    lines.append("    spec:")

    dag_tags = [t.strip() for t in d.get("dag_tags", []) if t.strip()]
    if dag_tags:
        lines.append("      tags:")
        for t in dag_tags:
            lines.append(f"      - {t}")

    lines.append(f"      stack: {d.get('stack', 'flare:7.0')}")
    lines.append(f"      compute: {d.get('compute', 'runnable-default')}")
    lines.append("      stackSpec:")

    drv = d.get("driver", {})
    lines.append("        driver:")
    lines.append(f"          coreLimit: {drv.get('core_limit', '2000m')}")
    lines.append(f"          cores: {drv.get('cores', 1)}")
    lines.append(f"          memory: {drv.get('memory', '2000m')}")

    exc = d.get("executor", {})
    lines.append("        executor:")
    lines.append(f"          coreLimit: {exc.get('core_limit', '2000m')}")
    lines.append(f"          cores: {exc.get('cores', 1)}")
    lines.append(f"          instances: {exc.get('instances', 1)}")
    lines.append(f"          memory: {exc.get('memory', '2000m')}")

    lines.append("        job:")
    lines.append(f"          explain: {'true' if d.get('explain', True) else 'false'}")
    lines.append(f"          logLevel: {d.get('log_level', 'INFO')}")

    inputs = [i for i in d.get("inputs", []) if i.get("name", "").strip()]
    if inputs:
        lines.append("          inputs:")
        for inp in inputs:
            lines.append(f"           - name: {inp['name'].strip()}")
            lines.append(f"             dataset: {inp['dataset'].strip()}")
            lines.append(f"             format: {inp.get('format', 'csv')}")
            if inp.get("schema_path", "").strip():
                lines.append(f"             schemaPath: {inp['schema_path'].strip()}")
            if inp.get("infer_schema", False):
                lines.append("             options:")
                lines.append("               inferSchema: true")

    steps = [s for s in d.get("steps", []) if s.get("name", "").strip()]
    if steps:
        lines.append("          steps:")
        lines.append("          - sequence:")
        for step in steps:
            lines.append(f"              - name: {step['name'].strip()}")
            if step.get("doc", "").strip():
                lines.append(f"                doc: {step['doc'].strip()}")
            sql = step.get("sql", "").strip()
            if sql:
                lines.append("                sql: |")
                for sql_line in sql.splitlines():
                    lines.append(f"                    {sql_line}")

    outputs = [o for o in d.get("outputs", []) if o.get("name", "").strip()]
    if outputs:
        lines.append("          outputs:")
        for out in outputs:
            lines.append(f"            - name: {out['name'].strip()}")
            lines.append(f"              dataset: {out['dataset'].strip()}")
            lines.append(f"              format: {out.get('format', 'Iceberg')}")
            if out.get("description", "").strip():
                lines.append(f"              description: {out['description'].strip()}")
            lines.append("              options:")
            lines.append(f"                saveMode: {out.get('save_mode', 'append')}")
            part_col = out.get("partition_col", "").strip()
            if part_col:
                lines.append("                sort:")
                lines.append("                  mode: partition")
                lines.append("                  columns:")
                lines.append(f"                    - name: {part_col}")
                lines.append(f"                      order: {out.get('partition_order', 'desc')}")
            lines.append("                iceberg:")
            lines.append("                  properties:")
            lines.append(f"                    write.format.default: {out.get('write_format', 'parquet')}")
            lines.append(f"                    write.metadata.compression-codec: {out.get('compression', 'gzip')}")
            if part_col:
                lines.append("                  partitionSpec:")
                lines.append(f"                    - type: {out.get('partition_type', 'identity')}")
                lines.append(f"                      column: {part_col}")

    return "\n".join(lines)


def generate_bundle_yaml(d: dict) -> str:
    """Generate Bundle YAML for a CADP data product."""
    import os as _os
    lines = []
    lines.append(f"name: {d['name']}")
    lines.append("version: v1beta")
    lines.append("type: bundle")

    tags = [t.strip() for t in d.get("tags", []) if t.strip()]
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {t}")

    if d.get("description", "").strip():
        lines.append(f"description: {d['description'].strip()}")

    lines.append(f"layer: \"{d.get('layer', 'user')}\"")
    lines.append("bundle:")
    lines.append("  resources:")

    # ── Lens resource (always active, always first) ───────────────────────────
    lines.append("    - id: lens")
    lines.append(f"      file: {d.get('lens_file', 'build/semantic-model/deployment.yml').strip()}")
    lines.append(f"      workspace: {d.get('lens_workspace', 'public').strip()}")

    # ── Quality Checks resources (active, one entry per item in qc_resources) ─
    qc_resources = [q for q in d.get("qc_resources", []) if q.get("file", "").strip()]
    for qc in qc_resources:
        qc_id = _os.path.basename(qc["file"]).replace(".yml", "").replace(".yaml", "")
        lines.append("")
        lines.append(f"    - id: {qc_id}")
        lines.append(f"      file: {qc['file'].strip()}")
        lines.append(f"      workspace: {qc.get('workspace', 'public').strip()}")

    # ── Commented optional blocks ─────────────────────────────────────────────
    lines.append("")
    lines.append("    # - id: api")
    lines.append("    #   file: activation/data-apis/service.yml")
    lines.append("    #   workspace: public")
    lines.append("    #   dependencies:")
    lines.append("    #     - lens")
    lines.append("")
    lines.append("    # - id: filter_policy")
    lines.append("    #   file: policy/filter-policy.yml")
    lines.append("    #   workspace: public")
    lines.append("    #   dependencies:")
    lines.append("    #     - api")

    return "\n".join(lines)


def generate_spec_yaml(d: dict) -> str:
    """Generate Spec YAML for a CADP data product."""
    lines = []
    lines.append(f"name: {d['name']}")
    lines.append("version: v1beta")
    lines.append("entity: product")
    lines.append("type: data")

    tags = [t.strip() for t in d.get("tags", []) if t.strip()]
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {t}")

    if d.get("description", "").strip():
        lines.append(f"description: {d['description'].strip()}")

    refs = [r for r in d.get("refs", []) if r.get("title", "").strip() and r.get("href", "").strip()]
    if refs:
        lines.append("refs:")
        for r in refs:
            lines.append(f"  - title: '{r['title'].strip()}'")
            lines.append(f"    href: {r['href'].strip()}")

    lines.append("v1beta:")
    lines.append("  data:")
    lines.append("    meta:")
    if d.get("title", "").strip():
        lines.append(f"      title: {d['title'].strip()}")
    if d.get("source_code_url", "").strip():
        lines.append(f"      sourceCodeUrl: {d['source_code_url'].strip()}")
    if d.get("tracker_url", "").strip():
        lines.append(f"      trackerUrl: {d['tracker_url'].strip()}")

    collaborators = [c for c in d.get("collaborators", []) if c.get("name", "").strip()]
    if collaborators:
        lines.append("    collaborators:")
        for c in collaborators:
            lines.append(f"      - name: {c['name'].strip()}")
            lines.append(f"        description: {c.get('description', 'consumer').strip()}")

    lines.append("    resource:")
    lines.append("      refType: dataos")
    lines.append(f"      ref: bundle:v1beta:{d['bundle_name']}")

    inputs = [i for i in d.get("inputs", []) if i.get("ref", "").strip()]
    if inputs:
        lines.append("    inputs:")
        for inp in inputs:
            lines.append("      - refType: dataos")
            lines.append(f"        ref: {inp['ref'].strip()}")

    outputs = [o for o in d.get("outputs", []) if o.get("ref", "").strip()]
    if outputs:
        lines.append("    outputs:")
        for out in outputs:
            lines.append("      - refType: dataos")
            lines.append(f"        ref: {out['ref'].strip()}")

    lens_name = d.get("lens_name", "").strip()
    lens_ws   = d.get("lens_workspace", "public").strip()
    lines.append("    ports:")
    lines.append("      lens:")
    lines.append(f"        ref: lens:v1alpha:{lens_name}:{lens_ws}")
    lines.append("        refType: dataos")
    lines.append("")
    lines.append("      # talos:")
    lines.append("      #   - ref: service:v1:<api-name>:public")
    lines.append("      #     refType: dataos")

    return "\n".join(lines)


def generate_dp_scanner_yaml(d: dict) -> str:
    """Generate Data Product Scanner Workflow YAML."""
    lines = []
    lines.append("version: v1")
    lines.append(f"name: {d['name']}")
    lines.append("type: workflow")

    tags = [t.strip() for t in d.get("tags", ["scanner", "data-product"]) if t.strip()]
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {t}")

    if d.get("description", "").strip():
        lines.append(f"description: {d['description'].strip()}")

    dag_name = d.get("dag_name", "").strip() or (d["name"] + "-job")
    lines.append("workflow:")
    lines.append("  dag:")
    lines.append(f"    - name: {dag_name}")
    if d.get("dag_description", "").strip():
        lines.append(f"      description: {d['dag_description'].strip()}")
    lines.append("      spec:")

    dag_tags = [t.strip() for t in d.get("dag_tags", ["scanner2"]) if t.strip()]
    if dag_tags:
        lines.append("        tags:")
        for t in dag_tags:
            lines.append(f"          - {t}")

    lines.append(f"        stack: {d.get('stack', 'scanner:2.0')}")
    lines.append(f"        compute: {d.get('compute', 'runnable-default')}")
    lines.append("        stackSpec:")
    lines.append("          type: data-product")
    lines.append("          sourceConfig:")
    lines.append("            config:")
    lines.append("              type: DataProduct")
    lines.append(f"              markDeletedDataProducts: {str(d.get('mark_deleted', True)).lower()}")
    lines.append("              dataProductFilterPattern:")
    lines.append("                includes:")
    for dp in d.get("data_products", []):
        if dp.strip():
            lines.append(f"                  - {dp.strip()}")

    return "\n".join(lines)


def generate_sadp_bundle_yaml(d: dict) -> str:
    """Generate Bundle YAML for a SADP data product (no lens, quality checks as active resources)."""
    import os as _os
    lines = []
    lines.append(f"name: {d['name']}")
    lines.append("version: v1beta")
    lines.append("type: bundle")

    tags = [t.strip() for t in d.get("tags", []) if t.strip()]
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {t}")

    if d.get("description", "").strip():
        lines.append(f"description: {d['description'].strip()}")

    lines.append(f"layer: \"{d.get('layer', 'user')}\"")
    lines.append("bundle:")
    lines.append("  resources:")

    # ── Quality Checks resources (one active entry per item) ──────────────────
    qc_resources = [q for q in d.get("qc_resources", []) if q.get("file", "").strip()]
    if qc_resources:
        for qc in qc_resources:
            qc_id = _os.path.basename(qc["file"]).replace(".yml", "").replace(".yaml", "")
            lines.append(f"    - id: {qc_id}")
            lines.append(f"      file: {qc['file'].strip()}")
            lines.append(f"      workspace: {qc.get('workspace', 'public').strip()}")
            lines.append("")
    else:
        # No QC resources provided — render as commented placeholder
        lines.append("    # - id: quality-checks")
        lines.append("    #   file: build/quality-checks/checks.yml")
        lines.append("    #   workspace: public")
        lines.append("")

    # ── Commented optional blocks ─────────────────────────────────────────────
    lines.append("    # - id: api")
    lines.append("    #   file: activation/data-apis/service.yml")
    lines.append("    #   workspace: public")
    lines.append("    #   dependencies:")
    lines.append("    #     - quality-checks")
    lines.append("")
    lines.append("    # - id: filter_policy")
    lines.append("    #   file: policy/filter-policy.yml")
    lines.append("    #   workspace: public")
    lines.append("    #   dependencies:")
    lines.append("    #     - api")

    return "\n".join(lines)


def generate_sadp_spec_yaml(d: dict) -> str:
    """Generate Spec YAML for a SADP data product (no lens port)."""
    lines = []
    lines.append(f"name: {d['name']}")
    lines.append("version: v1beta")
    lines.append("entity: product")
    lines.append("type: data")

    tags = [t.strip() for t in d.get("tags", []) if t.strip()]
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {t}")

    if d.get("description", "").strip():
        lines.append(f"description: {d['description'].strip()}")

    refs = [r for r in d.get("refs", []) if r.get("title", "").strip() and r.get("href", "").strip()]
    if refs:
        lines.append("refs:")
        for r in refs:
            lines.append(f"  - title: '{r['title'].strip()}'")
            lines.append(f"    href: {r['href'].strip()}")

    lines.append("v1beta:")
    lines.append("  data:")
    lines.append("    meta:")
    if d.get("title", "").strip():
        lines.append(f"      title: {d['title'].strip()}")
    if d.get("source_code_url", "").strip():
        lines.append(f"      sourceCodeUrl: {d['source_code_url'].strip()}")
    if d.get("tracker_url", "").strip():
        lines.append(f"      trackerUrl: {d['tracker_url'].strip()}")

    collaborators = [c for c in d.get("collaborators", []) if c.get("name", "").strip()]
    if collaborators:
        lines.append("    collaborators:")
        for c in collaborators:
            lines.append(f"      - name: {c['name'].strip()}")
            lines.append(f"        description: {c.get('description', 'consumer').strip()}")

    lines.append("    resource:")
    lines.append("      refType: dataos")
    lines.append(f"      ref: bundle:v1beta:{d['bundle_name']}")

    inputs = [i for i in d.get("inputs", []) if i.get("ref", "").strip()]
    if inputs:
        lines.append("    inputs:")
        for inp in inputs:
            lines.append("      - refType: dataos")
            lines.append(f"        ref: {inp['ref'].strip()}")

    outputs = [o for o in d.get("outputs", []) if o.get("ref", "").strip()]
    if outputs:
        lines.append("    outputs:")
        for out in outputs:
            lines.append("      - refType: dataos")
            lines.append(f"        ref: {out['ref'].strip()}")

    lines.append("    ports:")
    lines.append("      # talos:")
    lines.append("      #   - ref: service:v1:<api-name>:public")
    lines.append("      #     refType: dataos")

    return "\n".join(lines)