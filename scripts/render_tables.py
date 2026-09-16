"""Render the result tables as Markdown, from results/results.json.

One source, two outputs.  `results/results.json` is read here and turned into
Markdown fragments under `docs/generated/`: the result matrix, and the same
matrix with the wall-clock cost of each property.  Neither is ever edited by
hand.

`PROPERTY` and `rows()` are also imported by tools/figures.py (the cost
figure) and scripts/check_coverage.py (the coverage check), so the tables, the
figure and the coverage check all read the same row map.

Usage
    python3 scripts/render_tables.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "results.json"
MDOUT = ROOT / "docs" / "generated"

# Mapping from the file a verdict came from to the property identifier used in
# the result tables.  Kept here rather than in results.json so that the raw
# data stays a faithful record of what the tools printed.
#
# scripts/check_coverage.py reads this dictionary as data and unpacks each
# value as a three-tuple; keep that shape.
PROPERTY = {
    "20_secrecy.out":            ("P1",  "Session-key secrecy",                 "ProVerif"),
    "21_forward_secrecy.out":    ("P3",  "Forward secrecy",                     "ProVerif"),
    "22_pq_forward_secrecy.out": ("P4",  "Post-quantum forward secrecy (psk)",  "ProVerif"),
    "23_pq_fs_nopsk.out":        ("P4c", "  same, psk absent (control)",        "ProVerif"),
    "24a_aliveness.out":         ("P5a", "Agreement, responder to initiator",   "ProVerif"),
    "24b_agreement.out":         ("P5b", "Agreement, initiator to responder",   "ProVerif"),
    "24c_inj_agreement.out":     ("P5c", "Injective agreement / replay (P9)",   "ProVerif"),
    "25a_kci_commit.out":        ("P6a", "KCI, commitment level",               "ProVerif"),
    "25b_kci_complete.out":      ("P6b", "KCI, completion level",               "ProVerif"),
    "30_kem_psk_ideal.out|pskWitness":   ("P12a", "KEM-derived psk secrecy, K-PK binding",  "ProVerif"),
    "31_kem_psk_reencap.out|pskWitness": ("P12b", "  same, binding absent (control)",       "ProVerif"),
    "30_kem_psk_ideal.out|PskResponder": ("P12c", "KEM-derived psk, responder-view soundness", "ProVerif"),
    "tamarin_executable.out":         ("S0",  "Model admits an honest run",     "Tamarin"),
    "tamarin_session_key_secrecy.out":("S1",  "Session-key secrecy",            "Tamarin"),
    "tamarin_forward_secrecy.out":    ("S3",  "Forward secrecy",                "Tamarin"),
    "tamarin_agreement_responder.out":("S5",  "Agreement, no compromise",       "Tamarin"),
    "tamarin_kci_responder_commit.out":  ("S6a","KCI, commitment level",        "Tamarin"),
    "tamarin_kci_responder_complete.out":("S6b","KCI, completion level",        "Tamarin"),
}

SYMBOL_MD = {"proved": "proved", "attack_found": "attack found",
             "inconclusive": "inconclusive", "nonterminating": "non-terminating"}

# Weakest-outcome ordering: a file holding several queries is reported by the
# worst verdict any of them produced.
ORDER = {"proved": 0, "inconclusive": 1, "nonterminating": 2, "attack_found": 3}


# ===========================================================================
# Reading the project's own data
# ===========================================================================

def entries() -> list[dict]:
    return json.loads(RESULTS.read_text())["entries"]


def source_cost() -> dict[str, int | None]:
    """Wall-clock seconds per raw output file, None where none was recorded.

    Every query inside one file shares that file's invocation and therefore its
    cost; the alternative -- apportioning the time between the queries -- would
    invent a figure no tool reported.
    """
    cost: dict[str, int | None] = {}
    for e in entries():
        cost.setdefault(e["source"], e.get("elapsed_s"))
    return cost


# ===========================================================================
# The result matrix
# ===========================================================================

def rows() -> list[tuple[str, str, str, str, "int | None"]]:
    """One row per property: (id, description, prover, outcome, seconds)."""
    cost = source_cost()
    agg: dict[str, str] = {}
    for e in entries():
        src = e["source"]
        q = e.get("query") or ""
        # A row keyed "file|substring" selects one specific query inside a
        # file; a row keyed by the file alone aggregates every query in it to
        # its weakest outcome.  The distinction matters where a file holds
        # queries of unequal informativeness -- the KEM models pair a decisive
        # secrecy query with an agreement query ProVerif cannot decide, and
        # collapsing the two would understate the secrecy result.
        for key in PROPERTY:
            if "|" in key:
                f_, sub = key.split("|", 1)
                if f_ == src and sub in q:
                    cur = agg.get(key)
                    if cur is None or ORDER[e["outcome"]] > ORDER[cur]:
                        agg[key] = e["outcome"]
        cur = agg.get(src)
        if cur is None or ORDER[e["outcome"]] > ORDER[cur]:
            agg[src] = e["outcome"]

    out = []
    for key, (pid, desc, tool) in PROPERTY.items():
        if key in agg:
            out.append((pid, desc, tool, agg[key], cost.get(key.split("|", 1)[0])))
    return out


def secs_md(s: "int | None") -> str:
    return "n/r" if s is None else ("<1" if s == 0 else str(s))


def to_md(rs) -> str:
    L = ["| ID | Property | Tool | Outcome |", "|---|---|---|---|"]
    for pid, desc, tool, outcome, _ in rs:
        L.append(f"| {pid} | {desc.strip()} | {tool} | {SYMBOL_MD[outcome]} |")
    return "\n".join(L) + "\n"


def cost_md(rs) -> str:
    """Per-property wall-clock cost, for the documentation under docs/."""
    L = ["<!-- Generated by scripts/render_tables.py. Do not edit. -->",
         "",
         "| ID | Property | Tool | Outcome | Wall-clock (s) |",
         "|---|---|---|---|---:|"]
    for pid, desc, tool, outcome, secs in rs:
        L.append(f"| {pid} | {desc.strip()} | {tool} | "
                 f"{SYMBOL_MD[outcome]} | {secs_md(secs)} |")
    L += ["",
          "A non-terminating row shows the budget it exhausted, not a time to",
          "a verdict. `n/r` means the run behind that row predates per-query",
          "cost recording; re-run `make verify` to populate it.", ""]
    return "\n".join(L) + "\n"


# ===========================================================================

def main() -> int:
    MDOUT.mkdir(parents=True, exist_ok=True)

    rs = rows()

    (MDOUT / "results.md").write_text(to_md(rs))
    (MDOUT / "cost.md").write_text(cost_md(rs))

    print(f"rendered {len(rs)} result rows, 2 Markdown fragments")
    print(to_md(rs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
