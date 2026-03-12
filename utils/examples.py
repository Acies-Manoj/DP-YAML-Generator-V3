"""
Example YAML templates shown in the ? help button across all pages.
All values use <placeholders> so users understand the expected format.
"""

EXAMPLE_SECRET_R = """\
name: <instance-secret-name>-r
version: v1
type: instance-secret
description: "Read instance-secret for Snowflake depot"
layer: user
instance-secret:
  type: key-value-properties
  acl: r
  data:
    username: <snowflake-username>
    password: <snowflake-password>
"""

EXAMPLE_SECRET_RW = """\
name: <instance-secret-name>-rw
version: v1
type: instance-secret
description: "Read-write instance-secret for Snowflake depot"
layer: user
instance-secret:
  type: key-value-properties
  acl: rw
  data:
    username: <snowflake-username>
    password: <snowflake-password>
"""

EXAMPLE_DEPOT = """\
name: <instance-secret-name>
version: v2alpha
type: depot
description: Depot to fetch data from Snowflake datasource
tags:
  - <tag>
layer: user
depot:
  name: <instance-secret-name>
  type: snowflake
  external: true
  secrets:
    - name: <instance-secret-name>-r
      allkeys: true
    - name: <instance-secret-name>-rw
      allkeys: true
  snowflake:
    warehouse: <warehouse>
    url: <snowflake-url>
    database: <database>
    account: <account-identifier>
"""

EXAMPLE_SCANNER = """\
version: v1
name: <workflow-name>
type: workflow
tags:
  - scanner
description: Workflow to scan Snowflake database tables and register metadata in Metis.

workflow:
  dag:
    - name: <workflow-name>
      description: Scans schemas from Snowflake database and registers metadata to Metis.
      spec:
        stack: scanner:2.0
        tags:
          - scanner
        compute: runnable-default
        runAsUser: <run-as-user>

        stackSpec:
          depot: dataos://<depot-name>

          sourceConfig:
            config:
              includeTables: true
              includeViews: true
              schemaFilterPattern:
                includes:
                  - ^<schema-name>$
"""

EXAMPLE_SQL = """\
SELECT
    <column_one>,
    <column_two>,
    <original_col> AS <alias>,
    CAST(<column_three> AS VARCHAR) AS <alias_three>
FROM <database>.<schema>.<table_name>;
"""

EXAMPLE_TABLE_YAML = """\
tables:
  - name: <table-name>
    sql: {{ load_sql('<table-name>') }}
    description: "<table description>"
    public: true

    joins:
      - name: <joined-table>
        relationship: many_to_one
        sql: "{<table-name>.foreign_key} = {<joined-table>.id}"

    dimensions:
      - name: <column_name>
        type: string
        column: <COLUMN_NAME>
        description: "<dimension description>"
        primary_key: true
        public: true

      - name: <another_column>
        type: number
        column: <ANOTHER_COLUMN>

    measures:
      - name: <measure_name>
        sql: "COUNT(DISTINCT {<column_name>})"
        type: count_distinct
        description: "<measure description>"

    segments:
      - name: <segment_name>
        sql: "{<table-name>.<column_name>} > 1000"
        description: "<segment description>"
        meta:
          secure:
            user_groups:
              includes:
                - <group-name>
              excludes:
                - default
"""

EXAMPLE_VIEW_YAML = """\
views:
  - name: <view-name>
    description: <view description>
    public: true
    meta:
      title: <View Title>
      tags:
        - <tag>
      metric:
        expression: "*/45 * * * *"
        timezone: "UTC"
        window: "day"
        excludes:
          - <measure_to_exclude>

    tables:
      - join_path: <table-name>
        prefix: true
        includes:
          - <dimension_name>
          - <measure_name>

      - join_path: <another-table>
        prefix: true
        includes:
          - <dimension_name>
"""

EXAMPLE_LENS = """\
version: v1alpha
name: "<lens-name>"
layer: user
type: lens
tags:
  - lens
description: Semantic model for the data product
lens:
  compute: runnable-default
  secrets:
    - name: <secret-name>
      allKeys: true
  source:
    type: minerva
    name: <source-name>
    catalog: <catalog-name>
  repo:
    url: https://github.com/<org>/<repo>
    lensBaseDir: <repo>/<path>/model
    syncFlags:
      - --ref=main

  api:
    replicas: 1
    logLevel: info
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        cpu: 500m
        memory: 500Mi

  worker:
    replicas: 1
    logLevel: debug
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        cpu: 500m
        memory: 500Mi

  router:
    logLevel: info
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        cpu: 500m
        memory: 500Mi

  metric:
    logLevel: info
"""

EXAMPLE_FLARE = """\
version: v1
name: wf-<product-name>
type: workflow
tags:
  - <tag>
description: Ingesting data into the lakehouse
workflow:
  # schedule:
  #   cron: '00 20 * * *'
  #   concurrencyPolicy: Forbid
  dag:
    - name: dg-<product-name>
      spec:
        stack: flare:6.0
        compute: runnable-default
        stackSpec:
          driver:
            coreLimit: 2000m
            cores: 1
            memory: 2000m
          executor:
            coreLimit: 2000m
            cores: 1
            instances: 1
            memory: 2000m
          job:
            explain: true
            logLevel: INFO
            inputs:
              - name: <input-name>
                dataset: dataos://<depot>/<schema>/<table>
                format: <format>
                options:
                  inferSchema: true
            steps:
              - sequence:
                  - name: <step-name>
                    sql: >
                      SELECT * FROM <input-name>
            outputs:
              - name: <output-name>
                dataset: dataos://<depot>/<schema>/<table>
                format: Iceberg
                options:
                  saveMode: overwrite
                  iceberg:
                    properties:
                      write.format.default: parquet
                      write.metadata.compression-codec: gzip
"""

EXAMPLE_BUNDLE = """\
name: <bundle-name>
version: v1beta
type: bundle
tags:
  - <tag>
description: Bundle resource for the data product
layer: "user"
bundle:
  resources:
    - id: lens
      file: build/semantic-model/deployment.yml
      workspace: public

    # - id: api
    #   file: activation/data-apis/service.yml
    #   workspace: public
    #   dependencies:
    #     - lens
"""

EXAMPLE_SPEC = """\
name: <dp-name>
version: v1beta
entity: product
type: data
tags:
  - <tag>
description: Data product spec
v1beta:
  data:
    meta:
      title: <Product Title>
      sourceCodeUrl: https://github.com/<org>/<repo>
    collaborators:
      - name: <username>
        description: consumer
    resource:
      refType: dataos
      ref: bundle:v1beta:<bundle-name>
    inputs:
      - refType: dataos
        ref: dataset:icebase:<schema>:<table>
    outputs:
      - refType: dataos
        ref: dataset:icebase:<schema>:<output-table>
    ports:
      lens:
        ref: lens:v1alpha:<lens-name>:public
        refType: dataos
"""

EXAMPLE_DP_SCANNER = """\
version: v1
name: <scanner-workflow-name>
type: workflow
tags:
  - scanner
  - data-product
description: The job scans data product from poros
workflow:
  dag:
    - name: <scanner-workflow-name>-job
      description: The job scans data product from poros and registers data to Metis
      spec:
        tags:
          - scanner2
        stack: scanner:2.0
        compute: runnable-default
        stackSpec:
          type: data-product
          sourceConfig:
            config:
              type: DataProduct
              markDeletedDataProducts: true
              dataProductFilterPattern:
                includes:
                  - <dp-name>
"""


# ── Streamlit helper ──────────────────────────────────────────────────────────
def show_example(st, label, yaml_str):
    """Blue ? expander button showing example YAML. Pass st explicitly for import simplicity."""
    with st.expander(f"❓ See example output — {label}"):
        st.code(yaml_str, language="yaml")