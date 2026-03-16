"""
utils/llm_checks.py
Advanced LLM QC Suggestion Engine
Supports:
- Profiling-based reasoning
- Table description
- Column descriptions
- Use-case driven checks
- Cross-column validation
"""

import json
import re

from utils.qc_config import (
    PROVIDER, GROQ_API_KEY, GROQ_DEFAULT_MODEL,
    OLLAMA_BASE_URL, OLLAMA_DEFAULT_MODEL,
)
import pathlib

REFERENCE_PATH = pathlib.Path("utils/qc_reference_library.yaml")

if REFERENCE_PATH.exists():
    with open(REFERENCE_PATH, "r") as f:
        QC_REFERENCE_LIBRARY = f.read()
else:
    QC_REFERENCE_LIBRARY = "No reference patterns available."

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT (STRICT FORMAT + DEEP REASONING)
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a Principal Data Quality Architect specializing in enterprise data governance using SodaCL for DataOS.

You will also receive reference examples of real production SodaCL checks.
Learn patterns from them and generate similar governance-grade checks.

Your objective:
Generate advanced, business-semantic, cross-column aware quality checks for ANY type of table.

You must infer domain meaning from:

• Column names
• Column descriptions
• Table description
• Profiling statistics
• Data patterns

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTELLIGENT SEMANTIC REASONING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When generating checks:

• Infer relationships between related columns
• Detect logical dependencies (e.g., start/end dates, revenue/margin, quantity/price)
• Detect identity columns and business keys
• Detect financial metrics
• Detect temporal columns
• Detect categorical enums
• Detect geographic hierarchies
• Detect numeric metric relationships
• Detect derived fields

If multiple related fields exist:
→ Validate consistency across them.

If temporal fields exist:
→ Validate chronology and valid ranges.

If numeric metrics exist:
→ Validate non-negativity, reasonability, and relationships.

If identifier fields exist:
→ Validate uniqueness and integrity.

If categorical hierarchies exist:
→ Validate logical alignment (e.g., subregion must belong to region).

Think like a domain expert reviewing governance for production systems.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CROSS-COLUMN LOGIC RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If direct column-to-column comparison is not supported by SodaCL,
approximate using:

• min()
• max()
• avg()
• invalid_count()
• thresholds derived from profiling

Prefer safe, executable SodaCL syntax.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY a valid JSON array.

Each object MUST follow:

{
  "col": "column_name or null",
  "category": "Schema | Completeness | Uniqueness | Freshness | Validity | Accuracy",
  "name": "Human readable description",
  "syntax": "Valid SodaCL expression",
  "body": null or { additional yaml fields },
  "severity": "fail or warn",
  "reason": "Business justification"
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SEVERITY PRINCIPLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use "fail" for:

• Logical contradictions
• Business key violations
• Identity violations
• Temporal inconsistencies
• Financial inconsistencies
• Invalid categorical relationships
• Negative values where not allowed

Use "warn" for:

• Statistical anomalies
• Distribution drift
• Soft thresholds
• Length drift
• Ratio monitoring

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUALITY REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Prefer checks using missing_count, duplicate_count, invalid_count, avg_length, and row_count.
• Avoid generating complex SQL unless absolutely necessary.
• Do not fabricate columns.
• Do not repeat deterministic checks already generated.
• Generate 5–12 high-value rules.
• Prefer cross-column validation when meaningful.
• Infer domain meaning automatically.
• Prioritize governance and business correctness.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALLOWED SODACL CONSTRUCTS (STRICT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Only generate checks using these SodaCL constructs:

schema

missing_count(COLUMN)
missing_percent(COLUMN)

duplicate_count(COLUMN)

invalid_count(COLUMN)
  valid min
  valid max
  valid values
  valid regex
  valid min length
  valid max length

avg_length(COLUMN)

row_count

freshness(COLUMN)

failed rows:
  fail query: SQL query


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORBIDDEN FUNCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Never generate these functions:

regex_match()
custom_sql()
python expressions

If regex validation is required ALWAYS use:

invalid_count(COLUMN) = 0
valid regex: "pattern"
Return only JSON.
"""
# ─────────────────────────────────────────────────────────────────────────────
# PROMPT BUILDER
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# SNAPSHOT QC REFERENCE (REAL PRODUCTION EXAMPLES)
# ─────────────────────────────────────────────────────────────────────────────

def _build_column_context(columns: list[dict]) -> str:
    lines = []

    for col in columns:
        parts = [
            f"Column: {col['name']}",
            f"  Snowflake type : {col['sf_type']}",
            f"  Nullable       : {col['nullable']}",
            f"  PK             : {col['is_pk']}  | FK: {col['is_fk']}",
        ]

        if col.get("description"):
            parts.append(f"  Description    : {col['description']}")

        if col.get("min_val") is not None:
            parts.append(
                f"  Min/Max/Avg    : {col['min_val']} / {col['max_val']} / {col.get('avg_val')}"
            )

        if col.get("null_pct") is not None:
            parts.append(
                f"  Null %         : {col['null_pct']}% | Distinct: {col.get('distinct_count')}"
            )

        if col.get("avg_length") is not None:
            parts.append(
                f"  Avg Length     : {col['avg_length']}"
            )

        if col.get("sample_values"):
            parts.append(
                f"  Samples        : {col['sample_values']}"
            )

        lines.append("\n".join(parts))

    return "\n\n".join(lines)


def _build_default_summary(default_checks: list[dict]) -> str:
    lines = []
    for chk in default_checks:
        col_part = chk["col"] if chk.get("col") else "table-level"
        lines.append(f"[{chk['category']}] {col_part} → {chk['syntax']}")
    return "\n".join(lines)


def _build_schema_context(schema_overview: dict) -> str:
    """
    Build lightweight schema context for all tables in schema.
    Only table + first few column names are shown.
    """
    if not schema_overview:
        return "No schema overview provided."

    lines = []
    for table, cols in schema_overview.items():
        col_names = ", ".join(c["name"] for c in cols[:10])
        if len(cols) > 10:
            col_names += " ..."
        lines.append(f"{table}: {col_names}")

    return "\n".join(lines)


def build_prompt(ctx: dict, default_checks: list[dict]) -> str:
    return f"""
REFERENCE QUALITY CHECK PATTERNS (REAL PRODUCTION EXAMPLES):

{QC_REFERENCE_LIBRARY}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TABLE NAME:
{ctx.get('table')}

TABLE DESCRIPTION:
{ctx.get('table_description', 'Not provided')}

USE CASE:
{ctx.get('use_case', 'Not provided')}

ROW COUNT:
{ctx.get('row_count')}

COLUMNS:
{_build_column_context(ctx['columns'])}

FULL SCHEMA OVERVIEW:
{_build_schema_context(ctx.get('schema_overview', {}))}

ALREADY GENERATED CHECKS:
{_build_default_summary(default_checks)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTELLIGENT REASONING INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Infer business logic from semantic metadata.

If related columns exist:
→ Generate relationship validation.

If hierarchy fields exist:
→ Validate logical structure.

If temporal fields exist:
→ Validate chronological integrity.

If numeric metrics exist:
→ Validate reasonability, non-negativity, and relationships.

If identifier columns appear to reference other tables in the schema:
→ Suggest referential integrity checks using "failed rows" syntax.

Never use custom_sql or concat functions.

Only generate checks for the selected table.
Do NOT generate checks for other tables.

Generate additional advanced checks now.
"""
# ─────────────────────────────────────────────────────────────────────────────
# MAIN CALL
# ─────────────────────────────────────────────────────────────────────────────

def call_llm(ctx: dict, default_checks: list[dict]) -> list[dict]:
    prompt = build_prompt(ctx, default_checks)

    # Get LLM suggestions
    if PROVIDER == "groq":
        suggestions = _call_groq(prompt)
    else:
        suggestions = _call_ollama(prompt)
    if suggestions is None:
        suggestions = []

    # -------------------------------------------------
    # Add rule-based suggestions (email / phone / pin)
    # -------------------------------------------------

    for col in ctx["columns"]:
        col_name = col["name"]
        name_lower = col_name.lower()

        # Email validation
        if "email" in name_lower:

            already_exists = any(
                f"invalid_count({col_name.lower()})" in s.get("syntax","").lower()
                for s in suggestions
            )

            if not already_exists:
                suggestions.append({
                    "col": col_name,
                    "category": "Validity",
                    "name": f"{col_name} should follow valid email format",
                    "syntax": f"invalid_count({col_name}) = 0",
                    "body": {
                        "valid regex": "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"
                    },
                    "severity": "fail", 
                    "source": "rule",
                    "reason": "Email columns should follow standard email format"
                })

        # Phone validation
        if "phone" in name_lower or "mobile" in name_lower:
            already_exists = any(
                col_name.lower() in s.get("syntax","").lower()
                and "invalid_count" in s.get("syntax","").lower()
                for s in suggestions
            )

            if not already_exists:
                suggestions.append({
                    "col": col_name,
                    "category": "Validity",
                    "name": f"{col_name} should contain valid phone numbers",
                    "syntax": f"invalid_count({col_name}) = 0",
                    "body": {
                        "valid regex": "^[6-9][0-9]{9}$"
                    },
                    "severity": "fail",
                    "source": "rule", 
                    "reason": "Phone numbers should follow a valid numeric pattern"
                })

        # Pincode validation
        if "pin" in name_lower or "zipcode" in name_lower or "postal" in name_lower:
            already_exists = any(
                col_name.lower() in s.get("syntax","").lower()
                and "invalid_count" in s.get("syntax","").lower()
                for s in suggestions
            )

            if not already_exists:
                suggestions.append({
                    "col": col_name,
                    "category": "Validity",
                    "name": f"{col_name} should contain valid postal codes",
                    "syntax": f"invalid_count({col_name}) = 0",
                    "body": {
                        "valid regex": "^[1-9][0-9]{5}$"
                    },
                    "severity": "fail", 
                    "source": "rule",
                    "reason": "Postal codes should follow standard numeric format"
                })

    VALID_PREFIXES = [
    "missing_count",
    "duplicate_count",
    "invalid_count",
    "avg_length",
    "row_count",
    "freshness",
    "schema",
    "failed rows"
    ]
    default_syntax = {d["syntax"] for d in default_checks if d.get("syntax")}

    cleaned = []

    for s in suggestions:

        syntax = s.get("syntax", "")
        if not syntax:
            continue

        # remove unsupported constructs
        if any(x in syntax for x in ["concat(", "length(", "regex_match"]):
            continue

        # remove duplicates vs default checks
        if syntax in default_syntax:
            continue

        # keep only allowed SodaCL checks
        if any(syntax.startswith(p) for p in VALID_PREFIXES):
            cleaned.append(s)

    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE PARSER
# ─────────────────────────────────────────────────────────────────────────────

def _parse_response(raw: str) -> list[dict]:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)

    data = json.loads(text)

    # Fix regex_match syntax produced by LLM
    for item in data:
        syntax = item.get("syntax", "")

        # convert regex_match() → invalid_count regex
        if "regex_match" in syntax:
            col = item.get("col")

            pattern = re.findall(r"'(.*?)'", syntax)

            if col and pattern:
                item["syntax"] = f"invalid_count({col}) = 0"
                regex = pattern[0]

                # add anchors if missing
                if not regex.startswith("^"):
                    regex = "^" + regex

                if not regex.endswith("$"):
                    regex = regex + "$"

                item["body"] = {"valid regex": regex}

        # remove concat() based checks (not SodaCL)
        if "concat(" in syntax:
            item["syntax"] = ""

        # remove unsupported length() checks
        if "length(" in syntax:
            item["syntax"] = ""

    for item in data:
        item["source"] = "llm"
        if "body" not in item:
            item["body"] = None

    return data


# ─────────────────────────────────────────────────────────────────────────────
# GROQ
# ─────────────────────────────────────────────────────────────────────────────

def _call_groq(prompt: str) -> list[dict]:
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)

    response = client.chat.completions.create(
        model=GROQ_DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=4000,
    )

    raw = response.choices[0].message.content
    return _parse_response(raw)


# ─────────────────────────────────────────────────────────────────────────────
# OLLAMA
# ─────────────────────────────────────────────────────────────────────────────

def _call_ollama(prompt: str) -> list[dict]:
    import urllib.request

    payload = json.dumps({
        "model": OLLAMA_DEFAULT_MODEL,
        "prompt": SYSTEM_PROMPT + "\n\n" + prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())

    return _parse_response(data.get("response", ""))