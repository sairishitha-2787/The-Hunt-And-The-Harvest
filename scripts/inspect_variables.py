"""List every variable in the ISSP Stata file with its label and value labels.

Usage:
    python scripts/inspect_variables.py data/raw/ZA10000_v2-0-0.dta > variables.md

Use the output to confirm the names and codes marked CONFIRM in
src/harvest_hunt/config.py. The output contains no respondent data,
only the codebook, so it is safe to commit.
"""

import sys

import pandas as pd

KEYWORDS = ["household", "laundry", "groceries", "meals", "clean", "sick", "plan",
            "hours", "work", "income", "earn", "partner", "spouse", "sex", "weight",
            "child", "age", "educ", "country", "woman", "women", "mother"]


def main(path: str) -> None:
    with pd.io.stata.StataReader(path) as reader:
        var_labels = reader.variable_labels()
        value_labels = reader.value_labels()
        lbl_names = reader._lbllist  # value-label set used by each column
        names = list(var_labels)

    print(f"# Variables in {path}\n\n{len(names)} variables.\n")
    print("| Variable | Label | Relevant? |\n|---|---|---|")
    for name in names:
        label = var_labels[name].replace("|", "/")
        hit = "yes" if any(k in label.lower() for k in KEYWORDS) else ""
        print(f"| `{name}` | {label} | {hit} |")

    print("\n# Value labels for relevant variables\n")
    for name, lbl in zip(names, lbl_names):
        label = var_labels[name].lower()
        if lbl and lbl in value_labels and any(k in label for k in KEYWORDS):
            codes = "; ".join(f"{k} = {v}" for k, v in value_labels[lbl].items())
            print(f"- `{name}`: {codes}")


if __name__ == "__main__":
    main(sys.argv[1])
