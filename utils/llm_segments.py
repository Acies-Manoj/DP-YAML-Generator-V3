"""
utils/llm_segments.py
LLM Segment Suggestion Engine

Given a table name, its dimensions (columns), and optional table description,
calls the configured LLM to suggest 3–5 meaningful segments with name, SQL
filter expression, and description.

Reuses the shared provider config from utils/description_engine/config.py.
"""

import json
import re

from utils.description_engine.config import (
    PROVIDER,
    GROQ_API_KEY,
    DEFAULT_GROQ_MODEL as GROQ_DEFAULT_MODEL,
    OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL as OLLAMA_DEFAULT_MODEL,
)

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior analytics engineer specializing in semantic data modeling for DataOS Lens.

Your task:
Given a table name, its columns (name + type + optional description), and an optional table
description, suggest 3 to 5 meaningful segments for a semantic Lens model.

What is a segment?
A segment is a named SQL WHERE-style filter that pre-selects a business-meaningful subset
of rows. Users apply segments to slice their analysis (e.g. "show me only high-value customers").

Rules:
- Infer business groupings from column names, types, and descriptions.
- SQL expressions must use Lens format: {column_name} (curly braces, no table prefix, no quotes around column).
- String comparisons: {status} = 'active'
- Numeric comparisons: {lifetime_value} > 1000
- NULL checks: {deleted_at} IS NULL
- Combined: {status} = 'active' AND {country} = 'US'
- Do NOT fabricate column names. Only reference columns that exist in the provided list.
- name must be snake_case, short, and descriptive (e.g. active_customers, high_value_orders).
- description must be 1 sentence, business-facing (e.g. "Customers who are currently active.").
- Do NOT include includes or excludes — those are user-group access controls set by the user.
- Suggest segments that are genuinely useful: status filters, tier filters, date/activity filters,
  geographic filters, numeric threshold filters.

Return ONLY a valid JSON array. No markdown, no explanation, no code fences.

Example output:
[
  {
    "name": "active_customers",
    "sql": "{status} = 'active'",
    "description": "Customers with an active account status."
  },
  {
    "name": "high_value_customers",
    "sql": "{lifetime_value} > 1000",
    "description": "Customers whose lifetime spend exceeds 1000."
  },
  {
    "name": "recent_signups",
    "sql": "{created_at} >= DATEADD(day, -30, CURRENT_DATE)",
    "description": "Customers who signed up in the last 30 days."
  }
]
"""

# ─────────────────────────────────────────────────────────────────────────────
# PROMPT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def _build_prompt(table_name: str, dimensions: list[dict], table_desc: str = "") -> str:
    col_lines = "\n".join(
        "  - {name} (type: {typ}{desc})".format(
            name=d.get("name") or d.get("column", ""),
            typ=d.get("type", "string"),
            desc=f", description: {d['description']}" if d.get("description") else "",
        )
        for d in dimensions
        if (d.get("name") or d.get("column", "")).strip()
    )

    return f"""\
TABLE NAME: {table_name}

TABLE DESCRIPTION: {table_desc.strip() or "Not provided"}

COLUMNS:
{col_lines or "  (no columns defined yet)"}

Suggest 3–5 meaningful segments for this table. Return only a JSON array.
"""


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

    cleaned = []
    for item in data:
        name = str(item.get("name", "")).strip()
        sql  = str(item.get("sql",  "")).strip()
        desc = str(item.get("description", "")).strip()

        if not name or not sql:
            continue

        cleaned.append({
            "name":        name,
            "sql":         sql,
            "description": desc,
        })

    return cleaned


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
            {"role": "user",   "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
    )
    return _parse_response(response.choices[0].message.content)


# ─────────────────────────────────────────────────────────────────────────────
# OLLAMA
# ─────────────────────────────────────────────────────────────────────────────

def _call_ollama(prompt: str) -> list[dict]:
    import urllib.request

    payload = json.dumps({
        "model":  OLLAMA_DEFAULT_MODEL,
        "prompt": SYSTEM_PROMPT + "\n\n" + prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())

    return _parse_response(data.get("response", ""))


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def suggest_segments(
    table_name: str,
    dimensions: list[dict],
    table_desc: str = "",
) -> list[dict]:
    """
    Call the configured LLM to suggest segments for a table.

    Args:
        table_name:  The table name.
        dimensions:  List of dimension dicts with 'name'/'column', 'type', 'description' keys.
        table_desc:  Optional table description for richer context.

    Returns:
        List of segment dicts: [{"name", "sql", "description"}, ...]
        Returns [] on any failure.

    Raises:
        RuntimeError with a human-readable message on failure.
    """
    prompt = _build_prompt(table_name, dimensions, table_desc)

    try:
        if PROVIDER == "groq":
            return _call_groq(prompt)
        else:
            return _call_ollama(prompt)
    except Exception as e:
        raise RuntimeError(f"Segment suggestion failed ({PROVIDER}): {e}") from e