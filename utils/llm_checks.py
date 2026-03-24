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
LEARNED_PATH = pathlib.Path("utils/qc_learning/reference_qc_rules.json")

library_text = ""

# curated examples
if REFERENCE_PATH.exists():
    with open(REFERENCE_PATH, "r") as f:
        library_text += f.read()

# learned rules
# learned rules
if LEARNED_PATH.exists():

    try:
        with open(LEARNED_PATH, "r") as f:
            learned = json.load(f)
    except Exception:
        learned = []

    if learned:

        library_text += "\n\nLEARNED QC RULES FROM USER FEEDBACK:\n"

        seen = set()

        for r in learned[:15]:

            syntax = r.get("syntax")

            if syntax in seen:
                continue

            seen.add(syntax)

            library_text += f"""
Rule Example:
------------
Category: {r.get('category')}
Column: {r.get('column')}
Syntax: {syntax}
Reason: {r.get('reason')}
"""
QC_REFERENCE_LIBRARY = library_text

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT (STRICT FORMAT + DEEP REASONING)
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a Principal Data Quality Architect specializing in enterprise data governance using SodaCL for DataOS.

You will also receive reference examples of real production SodaCL checks.
Learn patterns from them and generate similar governance-grade checks.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LEARNED QC RULES REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You may also receive previously learned quality rules collected from user feedback.

These rules represent real-world governance patterns discovered from
manual QC improvements made by data engineers.

Use them as guidance when generating new checks.

• Do NOT repeat the same rule verbatim.
• Instead infer the pattern behind the rule.
• Apply similar logic to relevant columns in the current table.

Example patterns you may observe:
• Identifier columns require strict uniqueness
• Status columns require allowed categorical values
• Numeric metrics require non-negative validation
• Temporal fields require freshness validation
• Code fields require regex or length validation

Treat these examples as governance best practices.

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
• For missing_percent checks: NEVER use % symbol. Always use a plain number. 
  Example: missing_percent(col) < 5   (NOT missing_percent(col) < 5%)
• For freshness checks: use short durations like 1d, 7d, 24h. Never use 730d or 2y.
• Never mix metric syntax (= 0) with validity rules inline in the syntax string.
  Validity rules (valid min, valid max, valid values, valid regex) always go in the body field.
• For invalid_count checks with valid values: use ONLY the exact values from
  the "Samples" field shown for that column in the prompt. NEVER invent
  placeholder values like KNOWN_VALUE, UNKNOWN, N/A, ANY_VALUE, or similar.
  If a column has no Samples listed, do NOT generate a valid values check for it.
• Avoid generating complex SQL unless absolutely necessary.
• Do not fabricate columns.
• Do not repeat deterministic checks already generated.
• Generate 5–12 high-value rules.
• Only generate duplicate_count (uniqueness) checks for columns where
  PK = True is explicitly shown in the column metadata above.
  Do NOT generate uniqueness checks for any column where PK = False,
  including columns with "number", "name", "address", "zip" in their name.
  If you are unsure whether a column is a PK, do NOT generate a uniqueness check.
• Do NOT generate valid values checks for any column that already appears
  in ALREADY GENERATED CHECKS with an invalid_count and valid values body.
  This applies regardless of column name casing differences.
• Do NOT generate valid values checks for columns that already have a
  default valid values check listed in ALREADY GENERATED CHECKS.
  Check the ALREADY GENERATED CHECKS section carefully before generating
  any invalid_count check with valid values.
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
        line = f"[{chk['category']}] {col_part} → {chk['syntax']}"
        # Show valid values in summary so LLM knows not to regenerate
        if chk.get("body") and "valid values" in chk["body"]:
            line += " [SKIP — valid values check already exists for this column]"
        lines.append(line)
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

def _build_enum_hint(columns: list[dict]) -> str:
    lines = ["ENUM COLUMNS — use ONLY these exact values in any valid values check:"]
    found = False
    for col in columns:
        samples = col.get("sample_values")
        if samples and col.get("is_likely_enum"):
            clean = [str(v) for v in samples if v is not None]
            if clean:
                lines.append(f"  {col['name']}: {clean}")
                found = True
    if not found:
        lines.append("  (none detected — do not generate valid values checks)")
    return "\n".join(lines)

def build_prompt(ctx: dict, default_checks: list[dict]) -> str:
    MAX_LIBRARY_CHARS = 3000
    library_snippet = QC_REFERENCE_LIBRARY[:MAX_LIBRARY_CHARS]
    if len(QC_REFERENCE_LIBRARY) > MAX_LIBRARY_CHARS:
        library_snippet += "\n... (truncated for token budget)"

    return f"""
REFERENCE QUALITY CHECK PATTERNS (REAL PRODUCTION EXAMPLES):

{library_snippet}

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

ENUM COLUMNS WITH REAL VALUES (use ONLY these — never invent):
{_build_enum_hint(ctx['columns'])}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTELLIGENT REASONING INSTRUCTIONS

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

def strengthen_check(s: dict) -> dict | None:
    syntax = s.get("syntax", "")
    col = s.get("col")

    if not col or not syntax:
        return s
    
    min_len = 3

    col_lower = col.lower()

    if "email" in col_lower:
        min_len = 5
    elif "name" in col_lower:
        min_len = 3
    elif "code" in col_lower:
        min_len = 2

    # 🔴 Convert avg_length → regex validity (more reliable than valid min length)
    if syntax.startswith("avg_length"):
        return {
            "col": col,
            "category": "Validity",
            "name": f"{col} should have meaningful values",
            "syntax": f"invalid_count({col}) = 0",
            "body": {
                "valid regex": f"^[A-Za-z0-9 ]{{{min_len},}}$"
            },
            "severity": "warn",
            "source": "auto_fix",
            "reason": "Enforcing regex-based minimum length for meaningful values"
        }
    
    # 🔴 Ensure invalid_count syntax is always = 0 when body has validity rules
    body_check = s.get("body") or {}
    if body_check and any(k in body_check for k in ["valid min", "valid max", "valid min length", "valid max length", "valid regex", "valid values"]):
        if "invalid_count" in syntax and "= 0" not in syntax:
            s["syntax"] = f"invalid_count({col}) = 0"
            syntax = s["syntax"]

    # 🔴 Fix regex without anchors
    if "valid regex" in str(s.get("body", {})):
        body = s.get("body", {})
        regex = body.get("valid regex")

        if regex:
            if not regex.startswith("^"):
                regex = "^" + regex
            if not regex.endswith("$"):
                regex = regex + "$"

            body["valid regex"] = regex

        s["body"] = body
        return s

    # 🔴 Remove empty valid values
    if "valid values" in (s.get("body") or {}):
        vals = s["body"].get("valid values")
        if not vals:
            return {
                "col": col,
                "category": "Completeness",
                "name": f"{col} should not be null",
                "syntax": f"missing_count({col}) = 0",
                "body": None,
                "severity": "fail",
                "source": "auto_fix",
                "reason": "Removed invalid empty value check; enforcing non-null instead"
            }

    return s
# ─────────────────────────────────────────────────────────────────────────────
# MAIN CALL
# ─────────────────────────────────────────────────────────────────────────────

_FAKE_VALUES = {
    "known_value", "unknown", "n/a", "na", "any_value",
    "placeholder", "example_value", "value1", "value2",
    "your_value", "sample_value", "none", "null", "tbd"
}

def call_llm(ctx: dict, default_checks: list[dict]) -> list[dict]:

    prompt = build_prompt(ctx, default_checks)

    # Get LLM suggestions
    try:
        if PROVIDER == "groq":
            suggestions = _call_groq(prompt)
        else:
            suggestions = _call_ollama(prompt)
    except RuntimeError:
        raise  # pass rate limit errors up to the UI
    except Exception as e:
        print(f"⚠️ LLM call failed: {e}")
        suggestions = []

    if suggestions is None:
        suggestions = []

    print(f"🔍 LLM raw suggestions count: {len(suggestions)}")  # ← ADD THIS
    for s in suggestions:
        print(f"   RAW: [{s.get('col')}] {s.get('syntax','')[:60]}")  # ← ADD THIS
    
    

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
                        "valid regex": "^\\+?[0-9]{10,15}$"
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
    seen_syntax = set()

    for s in suggestions:
        s = strengthen_check(s)

        if not s or not isinstance(s, dict):
            continue

        syntax = s.get("syntax", "")
        if not syntax:
            continue

        syntax_text = syntax.lower()
        # normalise body keys — LLM sometimes uses valid_values instead of valid values
        body = s.get("body") or {}
        if "valid_values" in body:
            body["valid values"] = body.pop("valid_values")
            s["body"] = body
        if "valid_min" in body:
            body["valid min"] = body.pop("valid_min")
            s["body"] = body
        if "valid_max" in body:
            body["valid max"] = body.pop("valid_max")
            s["body"] = body
        body_text = str(body).lower()

        # FIX 1: fake values detection (strong)
        if (
            "valid values" in syntax_text
            or "valid values" in body_text
            or "must be one of" in syntax_text
        ):
            if any(x in syntax_text for x in _FAKE_VALUES):
                continue

        # FIX 2: body fake values
        if "valid values" in body_text:
            vals = body.get("valid values")
            if not vals:
                continue
            if any(str(v).lower().strip() in _FAKE_VALUES for v in vals):
                continue

        # remove unsupported syntax
        if any(x in syntax for x in ["concat(", "length(", "regex_match"]):
            continue

        # remove corrupted syntax — LLM put conditions inline instead of in body
        if re.search(r'=\s*0\s+(and|or|\[)', syntax):
            continue

        # remove missing_percent with % symbol — DataOS parser rejects it
        if re.search(r'missing_percent\([^)]+\)\s*[<>]=?\s*\d+%', syntax):
            # fix it by removing the % sign
            syntax = re.sub(r'(\d+)%', r'\1', syntax)
            s["syntax"] = syntax

        # fix freshness using years — convert to days
        if re.search(r'freshness\([^)]+\)\s*[<>]\s*\d+y', syntax):
            syntax = re.sub(r'(\d+)y', lambda m: str(int(m.group(1)) * 365) + 'd', syntax)
            s["syntax"] = syntax

        # cap freshness at 30d maximum
        if syntax.startswith("freshness"):
            match = re.search(r'(\d+)d', syntax)
            if match and int(match.group(1)) > 30:
                syntax = re.sub(r'\d+d', '1d', syntax)
                s["syntax"] = syntax

        # remove SQL expressions inside invalid_count() parentheses
        if re.search(r'invalid_count\([^)]*(<|>|!=|=|<=|>=)[^)]*\)', syntax):
            continue

        # remove duplicates vs default
        if syntax in default_syntax:
            continue
        if syntax.lower() in {d.lower() for d in default_syntax}:
            continue

        col_lower = (s.get("col") or "").lower()

        # FIX 3: block any Validity check for cols already covered by default
        if col_lower and any(
            (d.get("col") or "").lower() == col_lower
            and d.get("category") == "Validity"
            for d in default_checks
        ):
            continue

        # block uniqueness for non-PK
        if syntax.startswith("duplicate_count"):
            col_is_pk = any(
                c.get("is_pk") and (c.get("name") or "").lower() == col_lower
                for c in ctx["columns"]
            )
            if not col_is_pk:
                continue

        # block freshness duplicates
        if syntax.startswith("freshness"):
            if any(
                d.get("category") == "Freshness"
                and (d.get("col") or "").lower() == col_lower
                for d in default_checks
            ):
                continue

        # FIX 4: stronger duplicate detection
        normalized = syntax.lower().replace(" ", "")
        if normalized in seen_syntax:
            continue
        seen_syntax.add(normalized)

        # allow valid SodaCL
        if any(syntax.startswith(p) for p in VALID_PREFIXES):
            s["confidence"] = "high" if s.get("source") in ["rule", "auto_fix"] else "medium"
            cleaned.append(s)

    return cleaned


def fix_escapes(json_text: str) -> str:
    result = []
    i = 0
    while i < len(json_text):
        if json_text[i] == '\\' and i + 1 < len(json_text):
            next_char = json_text[i + 1]
            if next_char in ('"', '\\', '/', 'b', 'f', 'n', 'r', 't', 'u'):
                result.append(json_text[i])
                result.append(next_char)
                i += 2
            else:
                result.append('\\\\')
                i += 1
        else:
            result.append(json_text[i])
            i += 1
    return ''.join(result)

# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE PARSER
# ─────────────────────────────────────────────────────────────────────────────

def _parse_response(raw: str) -> list[dict]:
    if not raw or not raw.strip():
        print("⚠️ Empty LLM response")
        return []

    text = raw.strip()
    print(f"📥 Raw LLM response (first 300 chars): {text[:300]}")  # ← ADD THIS

    # remove markdown
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    def extract_json_array(text: str) -> str:
        start = text.find("[")
        end = text.rfind("]")

        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]

        return text

    # fix escapes
    text = fix_escapes(text)

    try:
        data = json.loads(text)
    except Exception as e:
        print("⚠️ JSON parse failed:", e)
        print("RAW RESPONSE:", text[:500])
        return []

    # Handle json_object wrapper: {"checks": [...]} or {"rules": [...]} etc.
    if isinstance(data, dict):
        for key in ("checks", "rules", "suggestions", "results", "items"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            # Try any list value in the dict
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
            else:
                print("⚠️ json_object response had no list value")
                return []

    if not isinstance(data, list):
        print("⚠️ Parsed JSON is not a list")
        return []

    # 🔧 CLEANUP LOGIC
    for item in data:
        syntax = item.get("syntax", "")

        # convert regex_match → SodaCL format
        if "regex_match" in syntax:
            col = item.get("col")
            pattern = re.findall(r"'(.*?)'", syntax)

            if col and pattern:
                regex = pattern[0]

                if not regex.startswith("^"):
                    regex = "^" + regex
                if not regex.endswith("$"):
                    regex += "$"

                item["syntax"] = f"invalid_count({col}) = 0"
                item["body"] = {"valid regex": regex}

        # remove unsupported syntax
        if any(x in syntax for x in ["concat(", "length(", "custom_sql"]):
            continue

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

    fallback = "llama-3.1-8b-instant"
    models_to_try = [GROQ_DEFAULT_MODEL]
    if GROQ_DEFAULT_MODEL != fallback:
        models_to_try.append(fallback)

    last_err = None
    for model in models_to_try:
        try:
            print(f"🤖 Trying model: {model}")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            return _parse_response(response.choices[0].message.content)

        except Exception as e:
            err_str = str(e)
            if "rate_limit_exceeded" in err_str or "429" in err_str:
                print(f"⚠️ {model} rate limited, trying next...")
                last_err = err_str
                continue
            raise

    raise RuntimeError(
        f"⏳ All Groq models rate limited. Try again later or upgrade to Dev Tier.\n\nDetails: {last_err[:300]}"
    )
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