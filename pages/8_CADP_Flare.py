import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.examples import EXAMPLE_FLARE, show_example
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.generators import generate_flare_yaml
from utils.history import save_entry

st.set_page_config(page_title="CADP — Flare Jobs", layout="wide")
from utils.ui_utils import load_global_css, render_sidebar, floating_docs
load_global_css()
render_sidebar()
floating_docs("flare")

st.markdown("""
<style>
.stButton>button { width: 100%; height: 45px; border-radius: 8px; font-size: 15px; }
.section-label {
    font-size: 12px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# STATE INIT
# ─────────────────────────────────────────────────────────────────────────────
FLARE_KEYS_TO_CLEAR = [
    "flare_tags", "flare_dag_tags",
    "flare_inputs", "flare_steps", "flare_outputs",
    "flare_generated_yaml", "flare_job_name_for_file",
]

for k, v in [
    ("flare_tags",     [""]),
    ("flare_dag_tags", [""]),
    ("flare_inputs",   [{"name": "", "dataset": "", "format": "csv", "schema_path": "", "infer_schema": True}]),
    ("flare_steps",    [{"name": "final", "doc": "", "sql": ""}]),
    ("flare_outputs",  [{
        "name": "final", "dataset": "", "format": "Iceberg", "description": "",
        "save_mode": "overwrite", "write_format": "parquet", "compression": "gzip",
        "partition_col": "", "partition_type": "identity", "partition_order": "desc",
    }]),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────────────
# NAV
# ─────────────────────────────────────────────────────────────────────────────
_flare_origin = st.session_state.get("flare_origin", "specific")

def _flare_back():
    if _flare_origin == "cadp_full":
        st.switch_page("pages/cadp_flow.py")
    else:
        st.session_state.home_screen = "specific"
        st.switch_page("app.py")

nav_l, _, nav_r = st.columns([1, 4, 1.5])
with nav_l:
    if st.button("← Back"):
        _flare_back()
with nav_r:
    if st.button("✖ Clear / Start Over"):
        for k in FLARE_KEYS_TO_CLEAR:
            st.session_state.pop(k, None)
        st.rerun()

st.title("CADP — Flare Jobs")
st.caption("Generate a Flare Workflow YAML for ingesting and transforming data into the DataOS lakehouse.")
st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# ADVANCED OPTIONS  (outside form — expanders not allowed inside forms)
# ─────────────────────────────────────────────────────────────────────────────
with st.expander("⚙️ Advanced Options"):
    st.caption("Pre-filled with standard defaults — edit only if needed.")
    st.markdown("**Compute & Stack**")
    cs1, cs2, cs3, cs4 = st.columns(4)
    with cs1: st.text_input("Stack", value="flare:6.0", key="fadv_stack")
    with cs2: st.text_input("Compute", value="runnable-default", key="fadv_compute")
    with cs3: st.text_input("Log Level", value="INFO",
                help="Common values: INFO, DEBUG, WARN, ERROR", key="fadv_log_level")
    with cs4: st.checkbox("explain: true", value=True, key="fadv_explain")

    st.markdown("**Driver**")
    dr1, dr2, dr3 = st.columns(3)
    with dr1: st.text_input("Core Limit", value="2000m", key="fadv_drv_cl")
    with dr2: st.number_input("Cores", value=1, min_value=1, key="fadv_drv_c")
    with dr3: st.text_input("Memory", value="2000m", key="fadv_drv_m")

    st.markdown("**Executor**")
    ex1, ex2, ex3, ex4 = st.columns(4)
    with ex1: st.text_input("Core Limit", value="2000m", key="fadv_exc_cl")
    with ex2: st.number_input("Cores", value=1, min_value=1, key="fadv_exc_c")
    with ex3: st.number_input("Instances", value=1, min_value=1, key="fadv_exc_i")
    with ex4: st.text_input("Memory", value="2000m", key="fadv_exc_m")

_CRON_PRESETS = {
    "None (commented out)": "",
    "Every 15 minutes":     "*/15 * * * *",
    "Every 30 minutes":     "*/30 * * * *",
    "Every hour":           "0 * * * *",
    "Every 6 hours":        "0 */6 * * *",
    "Daily at 8 PM":        "00 20 * * *",
    "Every day (midnight)": "0 0 * * *",
    "Custom":               None,
}

# ─────────────────────────────────────────────────────────────────────────────
# FORM
# ─────────────────────────────────────────────────────────────────────────────
with st.form("flare_form"):

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — Workflow Metadata
    # ══════════════════════════════════════════════════════════════════════════
    st.subheader("Workflow Metadata")
    st.caption("Required — unique to each job.")

    wm1, wm2 = st.columns(2)
    with wm1:
        wf_name = st.text_input(
            "Workflow Name *",
            placeholder="e.g. wf-product-data",
            help="DAG name is auto-derived: wf-product-data → dg-product-data",
        )
    with wm2:
        wf_desc = st.text_input(
            "Description *",
            value=st.session_state.get("flare_wf_desc", "Ingesting data into the lakehouse"),
        )

    wm3, wm4 = st.columns(2)
    with wm3:
        wf_title = st.text_input(
            "Workflow Title",
            placeholder="e.g. Connect City",
            help="Human-readable title shown in the DataOS UI.",
        )

    _th1, _th2 = st.columns([5, 1])
    with _th1: st.markdown("**Tags**")
    with _th2:
        if st.form_submit_button("➕ Add", key="flare_add_tag"):
            st.session_state.flare_tags.append(""); st.rerun()
    updated_tags = []
    for i, tag in enumerate(st.session_state.flare_tags):
        tc1, tc2 = st.columns([5, 1])
        with tc1:
            val = st.text_input(f"Tag {i+1}", value=tag, key=f"ftag_{i}",
                                placeholder="e.g. crm", label_visibility="collapsed")
            updated_tags.append(val)
        with tc2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("❌", key=f"rm_ftag_{i}"):
                st.session_state.flare_tags.pop(i); st.rerun()

    st.markdown("**Schedule** (optional)")
    _preset_opts = list(_CRON_PRESETS.keys())
    cr1, cr2 = st.columns(2)
    with cr1:
        cron_preset = st.selectbox(
            "Schedule Preset", _preset_opts, index=0, key="flare_cron_preset",
            help="Pick a common schedule, or choose Custom to type your own.")
    with cr2:
        cron_val = st.text_input(
            "Cron Expression",
            value=_CRON_PRESETS.get(cron_preset, "") or "",
            placeholder="e.g. 00 20 * * *",
            help="Auto-filled from preset. Editable when Custom is selected.",
        )

    st.divider()
    # ══════════════════════════════════════════════════════════════════════════
    _dth1, _dth2 = st.columns([5, 1])
    with _dth1: st.markdown("**DAG Tags**")
    with _dth2:
        if st.form_submit_button("➕ Add", key="flare_add_dag_tag"):
            st.session_state.flare_dag_tags.append(""); st.rerun()
    updated_dag_tags = []
    for i, tag in enumerate(st.session_state.flare_dag_tags):
        dtc1, dtc2 = st.columns([5, 1])
        with dtc1:
            val = st.text_input(f"DAG Tag {i+1}", value=tag, key=f"fdtag_{i}",
                                placeholder="e.g. Connect", label_visibility="collapsed")
            updated_dag_tags.append(val)
        with dtc2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("❌", key=f"rm_fdtag_{i}"):
                st.session_state.flare_dag_tags.pop(i); st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — Inputs
    # ══════════════════════════════════════════════════════════════════════════
    _inh1, _inh2 = st.columns([5, 1])
    with _inh1: st.subheader("Inputs")
    with _inh2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.form_submit_button("➕ Add Input", key="flare_add_inp"):
            st.session_state.flare_inputs.append(
                {"name": "", "dataset": "", "format": "csv", "schema_path": "", "infer_schema": True}
            ); st.rerun()
    st.caption("Define each input dataset. Dataset path format: `dataos://<depot>:<collection>/<file>`")

    for i, inp in enumerate(st.session_state.flare_inputs):
        st.markdown(f"**Input {i + 1}**")
        ic1, ic2 = st.columns(2)
        with ic1:
            st.session_state.flare_inputs[i]["name"] = st.text_input(
                "Input Name *", value=inp["name"], key=f"inp_name_{i}",
                placeholder="e.g. city_connect",
            )
            st.session_state.flare_inputs[i]["dataset"] = st.text_input(
                "Dataset Path *", value=inp["dataset"], key=f"inp_ds_{i}",
                placeholder="e.g. dataos://thirdparty01:none/city",
            )
        with ic2:
            st.session_state.flare_inputs[i]["format"] = st.text_input(
                "Format", value=inp.get("format", "csv"), key=f"inp_fmt_{i}",
                help="csv, json, parquet, orc, avro, delta, iceberg…",
            )
            st.session_state.flare_inputs[i]["schema_path"] = st.text_input(
                "Schema Path (optional)", value=inp.get("schema_path", ""), key=f"inp_sp_{i}",
                placeholder="e.g. dataos://thirdparty01:none/schemas/avsc/city.avsc",
                help="Avro schema path — rendered as schemaPath in YAML.",
            )
        ia1, _ = st.columns([2, 4])
        with ia1:
            st.session_state.flare_inputs[i]["infer_schema"] = st.checkbox(
                "inferSchema", value=inp.get("infer_schema", True), key=f"inp_is_{i}",
                help="Adds options.inferSchema: true — recommended for CSV.",
            )
        if i > 0:
            if st.form_submit_button("❌ Remove Input", key=f"rm_inp_{i}"):
                st.session_state.flare_inputs.pop(i); st.rerun()
        if i < len(st.session_state.flare_inputs) - 1:
            st.markdown("---")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — Steps (SQL transformations)
    # ══════════════════════════════════════════════════════════════════════════
    _sth1, _sth2 = st.columns([5, 1])
    with _sth1: st.subheader("Steps")
    with _sth2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.form_submit_button("➕ Add Step", key="flare_add_step"):
            st.session_state.flare_steps.append({"name": "", "doc": "", "sql": ""}); st.rerun()
    st.caption("Each step is a named SQL transformation. The step name must match the corresponding output name below.")

    for i, step in enumerate(st.session_state.flare_steps):
        st.markdown(f"**Step {i + 1}**")
        sc1, sc2 = st.columns([1, 4])
        with sc1:
            st.session_state.flare_steps[i]["name"] = st.text_input(
                "Step Name *", value=step["name"], key=f"step_name_{i}",
                placeholder="e.g. cities",
                help="This name links to the output.",
            )
            st.session_state.flare_steps[i]["doc"] = st.text_input(
                "Doc (optional)", value=step.get("doc", ""), key=f"step_doc_{i}",
                placeholder="Short description of this step",
            )
        with sc2:
            st.session_state.flare_steps[i]["sql"] = st.text_area(
                "SQL *", value=step["sql"], key=f"step_sql_{i}", height=160,
                placeholder=(
                    "SELECT\n"
                    "  *,\n"
                    "  date_format(now(), 'yyyyMMddHHmm') AS version\n"
                    "FROM city_connect"
                ),
            )
        if i > 0:
            if st.form_submit_button("❌ Remove Step", key=f"rm_step_{i}"):
                st.session_state.flare_steps.pop(i); st.rerun()
        if i < len(st.session_state.flare_steps) - 1:
            st.markdown("---")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5 — Outputs
    # ══════════════════════════════════════════════════════════════════════════
    _oth1, _oth2 = st.columns([5, 1])
    with _oth1: st.subheader("Outputs")
    with _oth2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.form_submit_button("➕ Add Output", key="flare_add_out"):
            st.session_state.flare_outputs.append({
                "name": "", "dataset": "", "format": "Iceberg", "description": "",
                "save_mode": "overwrite", "write_format": "parquet", "compression": "gzip",
                "partition_col": "", "partition_type": "identity", "partition_order": "desc",
            }); st.rerun()
    st.caption("Output name must match step name. Dataset path: `dataos://<depot>:<collection>/<table>?acl=rw`")

    for i, out in enumerate(st.session_state.flare_outputs):
        st.markdown(f"**Output {i + 1}**")
        oc1, oc2, oc3 = st.columns(3)
        with oc1:
            st.session_state.flare_outputs[i]["name"] = st.text_input(
                "Output Name *", value=out["name"], key=f"out_name_{i}",
                placeholder="e.g. cities",
                help="Must match the step name whose result you want to write.",
            )
            st.session_state.flare_outputs[i]["dataset"] = st.text_input(
                "Dataset Path *", value=out["dataset"], key=f"out_ds_{i}",
                placeholder="e.g. dataos://lakehouse01:retailsample/city?acl=rw",
            )
            st.session_state.flare_outputs[i]["description"] = st.text_input(
                "Description (optional)", value=out.get("description", ""), key=f"out_desc_{i}",
                placeholder="e.g. City data ingested from external csv",
            )
        with oc2:
            st.session_state.flare_outputs[i]["format"] = st.text_input(
                "Format", value=out.get("format", "Iceberg"), key=f"out_fmt_{i}",
                help="Iceberg, parquet, delta, csv, json…",
            )
            st.session_state.flare_outputs[i]["save_mode"] = st.text_input(
                "Save Mode", value=out.get("save_mode", "overwrite"), key=f"out_sm_{i}",
                help="overwrite, append, ignore, errorIfExists",
            )
        with oc3:
            st.session_state.flare_outputs[i]["write_format"] = st.text_input(
                "write.format.default", value=out.get("write_format", "parquet"), key=f"out_wf_{i}",
                help="parquet, orc, avro",
            )
            st.session_state.flare_outputs[i]["compression"] = st.text_input(
                "compression-codec", value=out.get("compression", "gzip"), key=f"out_comp_{i}",
                help="gzip, snappy, zstd, none",
            )

        st.markdown("**Partition / Sort** (optional — leave blank to skip)")
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            st.session_state.flare_outputs[i]["partition_col"] = st.text_input(
                "Partition Column", value=out.get("partition_col", ""), key=f"out_pc_{i}",
                placeholder="e.g. version",
            )
        with pc2:
            st.session_state.flare_outputs[i]["partition_type"] = st.text_input(
                "Partition Type", value=out.get("partition_type", "identity"), key=f"out_pt_{i}",
                help="identity, day, month, year, hour…",
            )
        with pc3:
            st.session_state.flare_outputs[i]["partition_order"] = st.text_input(
                "Sort Order", value=out.get("partition_order", "desc"), key=f"out_po_{i}",
                help="asc or desc",
            )

        if i > 0:
            if st.form_submit_button("❌ Remove Output", key=f"rm_out_{i}"):
                st.session_state.flare_outputs.pop(i); st.rerun()
        if i < len(st.session_state.flare_outputs) - 1:
            st.markdown("---")

    st.markdown(" ")
    generate_btn = st.form_submit_button("Generate Flare YAML", use_container_width=True)

# Persist tag lists (must happen after form closes)
st.session_state.flare_tags     = updated_tags
st.session_state.flare_dag_tags = updated_dag_tags

# ─────────────────────────────────────────────────────────────────────────────
# VALIDATE + GENERATE
# ─────────────────────────────────────────────────────────────────────────────
if generate_btn:
    errors = []
    if not wf_name.strip():
        errors.append("Workflow Name is required.")
    if not wf_desc.strip():
        errors.append("Description is required.")
    for i, inp in enumerate(st.session_state.flare_inputs):
        if not inp.get("name", "").strip():
            errors.append(f"Input {i + 1}: Name is required.")
        if not inp.get("dataset", "").strip():
            errors.append(f"Input {i + 1}: Dataset Path is required.")
    for i, step in enumerate(st.session_state.flare_steps):
        if not step.get("name", "").strip():
            errors.append(f"Step {i + 1}: Step Name is required.")
        if not step.get("sql", "").strip():
            errors.append(f"Step {i + 1}: SQL is required.")
    for i, out in enumerate(st.session_state.flare_outputs):
        if not out.get("name", "").strip():
            errors.append(f"Output {i + 1}: Output Name is required.")
        if not out.get("dataset", "").strip():
            errors.append(f"Output {i + 1}: Dataset Path is required.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        flare_data = {
            "name":        wf_name.strip(),
            "description": wf_desc.strip(),
            "wf_title":    wf_title.strip(),
            "tags":        [t for t in st.session_state.flare_tags     if t.strip()],
            "dag_tags":    [t for t in st.session_state.flare_dag_tags if t.strip()],
            "cron":        cron_val.strip() if cron_preset == "Custom" else (_CRON_PRESETS.get(cron_preset) or ""),
            "stack":       st.session_state.get("fadv_stack", "flare:6.0") or "flare:6.0",
            "compute":     st.session_state.get("fadv_compute", "runnable-default") or "runnable-default",
            "log_level":   st.session_state.get("fadv_log_level", "INFO") or "INFO",
            "explain":     st.session_state.get("fadv_explain", True),
            "driver": {
                "core_limit": st.session_state.get("fadv_drv_cl", "2000m"),
                "cores":      int(st.session_state.get("fadv_drv_c", 1)),
                "memory":     st.session_state.get("fadv_drv_m", "2000m"),
            },
            "executor": {
                "core_limit": st.session_state.get("fadv_exc_cl", "2000m"),
                "cores":      int(st.session_state.get("fadv_exc_c", 1)),
                "instances":  int(st.session_state.get("fadv_exc_i", 1)),
                "memory":     st.session_state.get("fadv_exc_m", "2000m"),
            },
            "inputs":  st.session_state.flare_inputs,
            "steps":   st.session_state.flare_steps,
            "outputs": st.session_state.flare_outputs,
        }
        st.session_state.flare_generated_yaml    = generate_flare_yaml(flare_data)
        st.session_state.flare_job_name_for_file = wf_name.strip()
        save_entry("CADP", "flare", f"{wf_name.strip()}.yml", st.session_state.flare_generated_yaml, dp_name=wf_name.strip())

# ─────────────────────────────────────────────────────────────────────────────
# PREVIEW + DOWNLOAD
# ─────────────────────────────────────────────────────────────────────────────
if "flare_generated_yaml" in st.session_state:
    st.divider()
    st.subheader("Flare Workflow YAML Preview")
    show_example(st, "Flare Job YAML", EXAMPLE_FLARE)
    st.code(st.session_state.flare_generated_yaml, language="yaml")
    st.download_button(
        label="⬇ Download Flare YAML",
        data=st.session_state.flare_generated_yaml,
        file_name=f"{st.session_state.get('flare_job_name_for_file', 'flare-job')}.yml",
        mime="text/yaml",
        use_container_width=True,
    )

    if _flare_origin == "cadp_full":
        st.divider()
        st.success("Flare Job complete. Return to the CADP flow to continue.")
        if st.button("Back to CADP Flow", use_container_width=True, type="primary"):
            if "cadp_completed_steps" not in st.session_state:
                st.session_state.cadp_completed_steps = set()
            st.session_state.cadp_completed_steps.add(4)
            st.switch_page("pages/cadp_flow.py")