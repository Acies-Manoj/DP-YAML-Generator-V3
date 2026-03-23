import json
from pathlib import Path

REF_PATH = Path("utils/qc_learning/reference_qc_rules.json")


def load_reference_rules():

    if not REF_PATH.exists():
        return []

    with open(REF_PATH, "r") as f:
        return json.load(f)


def save_reference_rules(new_rules):

    existing = load_reference_rules()

    existing_syntax = {r["syntax"] for r in existing}

    saved_count = 0

    for rule in new_rules:

        syntax = rule.get("syntax")

        if syntax and syntax not in existing_syntax:

            existing.append(rule)
            existing_syntax.add(syntax)
            saved_count += 1

    REF_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(REF_PATH, "w") as f:
        json.dump(existing, f, indent=2)

    return saved_count