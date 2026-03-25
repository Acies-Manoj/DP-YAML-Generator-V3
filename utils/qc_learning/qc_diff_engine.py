def detect_new_rules(generated_checks, uploaded_df):

    generated_syntax = {
        c["syntax"] for c in generated_checks if c.get("syntax")
    }

    learned_rules = []

    for _, row in uploaded_df.iterrows():

        syntax = str(row.get("syntax","")).strip()

        if not syntax:
            continue

        if syntax not in generated_syntax:

            learned_rules.append({
                "name": row.get("check_name"),
                "col": row.get("column"),
                "category": row.get("category"),
                "syntax": syntax,
                "body": row.get("body"),
                "source": "learned"
            })

    return learned_rules