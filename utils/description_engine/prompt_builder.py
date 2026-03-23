"""
prompt_builder.py — Builds the LLM prompt from structured metadata.
Keeps all prompt logic in one place for easy iteration.
Produces generic, factual descriptions — no domain assumptions.
"""

import json


def build_prompt(metadata: dict, user_context: str = None) -> str:
    """
    Build a constrained prompt for table + column description generation.

    Args:
        metadata:     Structured dict from metadata_builder.build_metadata()
        user_context: Optional plain-text business context provided by the user.
                      When given, injected into the prompt so the LLM can produce
                      more accurate, domain-specific descriptions.
                      Pass None (default) for standard column-name-only behaviour.

    Returns:
        Full prompt string ready to send to LLM.
    """
    table_name = metadata["table_name"]
    columns    = metadata["columns"]

    # Build column summary lines for prompt
    col_lines = []
    for col in columns:
        parts = [f"  - {col['name']} ({col['data_type']})"]

        flags = []
        if col.get("is_pk"):
            flags.append("PRIMARY KEY")
        if col.get("is_fk"):
            flags.append("FOREIGN KEY")
        if not col.get("nullable"):
            flags.append("NOT NULL")
        if flags:
            parts.append(f"[{', '.join(flags)}]")

        if col.get("sample_values"):
            samples = col["sample_values"][:5]
            parts.append(f"sample values: {samples}")

        if col.get("distinct_count") is not None:
            parts.append(f"~{col['distinct_count']} distinct values")

        if col.get("null_pct") is not None:
            parts.append(f"{col['null_pct']:.1f}% nulls")

        col_lines.append(" ".join(parts))

    col_block = "\n".join(col_lines)

    prompt = f"""You are a a senior data analyst documenting this table for a business intelligence team.

Your job is to generate short, factual descriptions for a database table and its columns.

STRICT RULES:
1. Base descriptions ONLY on column names, data types, constraints, and sample values provided.
2. Use general common knowledge about what this type of field is typically used for in data analysis.
3. Use only the column metadata and any business context explicitly provided below. Do not invent information beyond what is given.
4. Table description: 1-2 sentences max.
5. Column descriptions: 1 sentence max each.
6. PRIMARY KEY columns: mention they uniquely identify records.
7. FOREIGN KEY columns: mention they reference another table.
8. Do NOT use markdown, bullet points, or headers in descriptions.
9. Output MUST be valid JSON only. No preamble, no explanation, no markdown fences.
10. Do not include any information in descriptions that is not explicitly stated in the metadata.
11. If sample values are provided, use them to inform the description but do not assume any additional context.
12. If the column name is ambiguous (e.g., "value", "data", "info"), acknowledge the ambiguity in the description.
13. Don't give any word in fully capital letters more importance than others.
14. Describe, what analytical purpose does each field serves.

TABLE: {table_name}
COLUMNS:
{col_block}
"""

    # ── Inject user-provided business context when available ─────────────────
    if user_context:
        prompt += f"""
BUSINESS CONTEXT PROVIDED BY USER:
{user_context}

Use the above context alongside the column metadata to make descriptions more accurate
and domain-specific. Do not contradict the column metadata. Do not invent details
beyond what is stated in either the metadata or the context above.
"""

    prompt += f"""
Respond with this exact JSON structure:
{{
  "table_description": "...",
  "columns": [
    {{"name": "column_name", "description": "..."}},
    ...
  ]
}}

Generate descriptions for ALL {len(columns)} columns listed above. Output JSON only."""

    return prompt