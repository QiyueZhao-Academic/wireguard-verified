"""Check that the suite's four lists agree with each other.

There are four places that independently decide which properties this artifact
has: the query lists in the Makefile, the models on disk, the expectations in
expectations.yaml, and the row map in render_tables.py.  Nothing forces them to
agree, and the failure is silent in the direction that matters most -- a result
that is produced and displayed but has no expectation is a result nobody is
checking.  That is not hypothetical: before this check existed, expectations
covered twelve of the eighteen rows in the results table, and the six it missed
included the falsified KCI lemma the report presents as a headline finding.

Run by `make check`, so it costs nothing and cannot be forgotten.

    python3 scripts/check_coverage.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import yamlite  # noqa: E402


def makevar(name: str) -> list[str]:
    """Read a variable out of the Makefile through its print-% accessor."""
    r = subprocess.run(["make", "--no-print-directory", f"print-{name}"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.stdout.split()


def main() -> int:
    problems: list[str] = []

    spec = yamlite.loads((ROOT / "expectations.yaml").read_text())["queries"]

    # --- 1. Every model the Makefile runs is on disk -----------------------
    for stem in makevar("PVQ") + makevar("PVKEM"):
        if not (ROOT / "models" / "proverif" / f"{stem}.pv").exists():
            problems.append(f"Makefile runs {stem}.pv, which does not exist")

    theory = ROOT / "models" / "tamarin" / "40_wireguard_state.spthy"
    lemmas = set(re.findall(r"^lemma (\w+):", theory.read_text(), re.M))
    for lemma in makevar("TAMLEM"):
        if lemma not in lemmas:
            problems.append(f"Makefile proves lemma '{lemma}', "
                            f"absent from {theory.name}")

    # --- 2. Every model an expectation names is on disk --------------------
    for q in spec:
        if not (ROOT / "models" / q["model"]).exists():
            problems.append(f"[{q['property']}] names models/{q['model']}, "
                            "which does not exist")
        if q["tool"] == "tamarin" and q["query"] not in lemmas:
            problems.append(f"[{q['property']}] expects lemma '{q['query']}', "
                            f"absent from {theory.name}")

    # --- 3. Expectations and the results table cover the same properties ---
    # Imported rather than parsed: the row map is Python, and reading it as
    # data keeps this check honest if its shape ever changes.
    import render_tables
    table_ids = {pid for pid, _, _ in render_tables.PROPERTY.values()}
    expect_ids = {q["property"] for q in spec}

    for pid in sorted(table_ids - expect_ids):
        problems.append(f"[{pid}] is displayed in the results table but has "
                        "no entry in expectations.yaml -- it is a result "
                        "nobody is checking")
    for pid in sorted(expect_ids - table_ids):
        problems.append(f"[{pid}] has an expectation but no row in "
                        "render_tables.PROPERTY -- it will never be displayed")

    # --- 4. Expected outcomes are drawn from the declared vocabulary -------
    allowed = {"proved", "attack_found", "inconclusive", "nonterminating"}
    for q in spec:
        if q["expect"] not in allowed:
            problems.append(f"[{q['property']}] expects '{q['expect']}', "
                            f"not one of {sorted(allowed)}")
        if q["tool"] not in ("proverif", "tamarin"):
            problems.append(f"[{q['property']}] names tool '{q['tool']}'")

    if problems:
        print("  coverage         FAILED")
        for p in problems:
            print("    " + p)
        return 1
    print(f"  coverage         ok ({len(spec)} expectations, "
          f"{len(table_ids)} table rows, {len(lemmas)} lemmas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
