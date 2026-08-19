"""Compare observed verdicts against expectations.yaml.

This is what turns formal verification into a regression suite.  A model that
silently stops proving what it used to prove is a bug; so is one that starts
proving something it should not.  Outcomes that are attacks are expectations
too: 23_pq_fs_nopsk.pv is supposed to be refuted, and a run in which it
succeeded would mean the model had drifted, not that WireGuard had improved.

Exit code 1 on any mismatch, so `make verify` fails the build.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yamlite  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "results.json"
EXPECT = ROOT / "expectations.yaml"


RANK = {"proved": 0, "inconclusive": 1, "nonterminating": 2, "attack_found": 3}


def entries() -> list[dict]:
    return json.loads(RESULTS.read_text())["entries"]


def observed(src: str, want_query: str | None) -> str | None:
    """Outcome recorded for `src`.

    When the expectation names a specific query, match on it: a model file may
    hold several queries of unequal informativeness, and collapsing them to the
    weakest would report a decisive secrecy proof as inconclusive merely
    because a secondary query alongside it could not be decided.  When no query
    is named, fall back to the weakest outcome in the file.
    """
    rows = [e for e in entries() if e["source"] == src]
    if not rows:
        return None
    if want_query:
        # ProVerif prints queries with its own spacing and variable renaming,
        # so compare on a distinctive fragment rather than the whole string.
        key = _fingerprint(want_query)
        hits = [e for e in rows if e.get("query") and key in _fingerprint(e["query"])]
        if hits:
            return max((e["outcome"] for e in hits), key=lambda o: RANK[o])
    return max((e["outcome"] for e in rows), key=lambda o: RANK[o])


def _fingerprint(q: str) -> str:
    """Strip spacing and ProVerif's variable suffixes for robust comparison."""
    import re as _re
    return _re.sub(r"[\s_]|\b\d+\b", "", q)


def source_for(model: str, tool: str) -> str:
    """The raw-output filename a model's run is recorded under."""
    stem = Path(model).stem
    return f"tamarin_{stem}.out" if tool == "tamarin" else f"{stem}.out"


def main() -> int:
    if not RESULTS.exists():
        print("  expectations     no results.json -- run `make verify` first")
        return 1

    spec = yamlite.loads(EXPECT.read_text())["queries"]

    ok, mismatched, absent = 0, [], []
    for q in spec:
        tool, model, want = q["tool"], q["model"], q["expect"]
        # Tamarin lemmas share one theory file; they are keyed by lemma name.
        src = (f"tamarin_{q['query']}.out" if tool == "tamarin"
               else source_for(model, tool))
        # Match on the query for both tools.  Every `--prove=L` run writes a
        # summary block naming all six lemmas, and today only L carries a real
        # verdict while the rest read "analysis incomplete" -- so collapsing a
        # file to its weakest outcome happens to work.  It stops working the
        # moment anyone runs tamarin-prover without --prove, at which point all
        # six verdicts are real and every lemma inherits the falsified one.
        # Keying on the lemma name costs nothing and removes the trap.
        got = observed(src, q.get("query"))
        if got is None:
            absent.append((q["property"], src))
        elif got != want:
            mismatched.append((q["property"], src, want, got))
        else:
            ok += 1

    print(f"  expectations     {ok}/{len(spec)} match")
    for pid, src in absent:
        print(f"    [{pid}] no result recorded for {src}")
    for pid, src, want, got in mismatched:
        print(f"    [{pid}] {src}: expected {want}, observed {got}")

    if mismatched:
        print("\n  A mismatch means the model changed, not the protocol. "
              "Inspect results/raw/ before updating expectations.yaml.")
        return 1
    return 0 if not absent else 1


if __name__ == "__main__":
    sys.exit(main())
