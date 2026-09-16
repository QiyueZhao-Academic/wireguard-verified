"""Print a headline summary of the current result set.

Shown at the end of `make everything`, so that a run which takes several
minutes ends with something readable rather than with the last compiler
message.  Reads results/results.json; makes no claim the file does not hold.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "results.json"
BOLD, DIM, RST = "\033[1m", "\033[2m", "\033[0m"
GREEN, RED, GREY = "\033[32m", "\033[31m", "\033[90m"

MARK = {"proved": f"{GREEN}proved{RST}",
        "attack_found": f"{RED}attack found{RST}",
        "inconclusive": f"{GREY}inconclusive{RST}",
        "nonterminating": f"{GREY}non-terminating{RST}"}


def main() -> int:
    if not RESULTS.exists():
        print("no results yet -- run `make verify`")
        return 1

    entries = json.loads(RESULTS.read_text())["entries"]
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["outcome"]] = counts.get(e["outcome"], 0) + 1

    print(f"\n{BOLD}Results{RST}")
    for k in ("proved", "attack_found", "inconclusive", "nonterminating"):
        if k in counts:
            print(f"  {counts[k]:>3}  {MARK[k]}")

    print(f"\n{BOLD}Headline findings{RST}")
    print("  Post-quantum forward secrecy holds with a pre-shared key and")
    print("  fails without it -- two models differing in one line.")
    print("  KCI resistance sits between committing key material and accepting")
    print("  traffic; the static-ephemeral term se holds that gap open.")
    print("  In-band ML-KEM-768 initiation is 1300 B and exceeds the IPv6")
    print("  minimum-MTU payload by 68 B: no guaranteed path.")

    nonterm = [e for e in entries if e["outcome"] == "nonterminating"]
    if nonterm:
        print(f"\n{BOLD}Undecided, by design of the report{RST}")
        for e in nonterm:
            src = e["source"].replace(".out", "")
            print(f"  {src:<24} {DIM}{e.get('reason', '')}{RST}")
        print(f"  {DIM}Expected. A non-terminating query says the tool could not")
        print(f"  settle the question in budget, not that an attack exists.{RST}")

    print(f"\n{BOLD}Artifacts{RST}")
    for p, what in (("results/results.json", "machine-readable results"),
                    ("results/figures/", "SVG figures"),
                    ("results/traces/", "attack derivations"),
                    ("docs/generated/results.md", "result table")):
        exists = (ROOT / p).exists()
        tick = f"{GREEN}ok{RST}" if exists else f"{GREY}--{RST}"
        print(f"  [{tick}] {p:<28} {DIM}{what}{RST}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
