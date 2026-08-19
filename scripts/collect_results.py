"""Turn raw verifier output into results/results.json.

Result tables in the report and the README are rendered from this file and
never written by hand.  A hand-maintained table goes stale the first time a
model changes, and a stale table costs a reader's trust in everything else in
the repository.

Usage
    python3 scripts/collect_results.py            # parse results/raw/
    python3 scripts/collect_results.py --check    # also compare to expectations
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "results" / "raw"
OUT = ROOT / "results" / "results.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner import ELAPSED_MARKER, KILL_MARKER  # noqa: E402

# Wall-clock cost, written by runner.py as the last line of every output file.
# Absent from output produced before runner.py existed, so it is optional
# everywhere downstream: a missing timing is recorded as null and rendered as
# "n/r" rather than guessed at.
PV_ELAPSED = re.compile(re.escape(ELAPSED_MARKER) + r"\s*(\d+)\s*s", re.M)

# Lines the runner itself appends after the verifier has finished.  They are
# stripped before the truncation signature below is tested: that signature is
# anchored at the end of the file, and a trailing runner line would defeat it.
RUNNER_LINE = re.compile(r"(?:^\[runner\][^\n]*\n?)+\Z", re.M)


def elapsed_of(text: str) -> int | None:
    """Wall-clock seconds for this invocation, or None if it was not recorded."""
    m = PV_ELAPSED.search(text)
    return int(m.group(1)) if m else None

# --- ProVerif ---------------------------------------------------------------
# ProVerif prints one "RESULT <query> is true|false." line per query, or
# "cannot be proved" when its approximation is too coarse to decide.
PV_RESULT = re.compile(r"^RESULT (.+?) is (true|false)\.\s*$", re.M)
PV_INCONCL = re.compile(r"^RESULT (.+?) cannot be proved\.\s*$", re.M)

# A run stopped mid-saturation ends on one of ProVerif's own progress lines.
# Matching the *end* of the file rather than anywhere in it is what makes this
# a truncation signature: every long run prints these lines, but only an
# interrupted one has one as its last word.
PV_TRUNCATED = re.compile(r"\d+ rules inserted\. Base: \d+ rules[^\n]*\n?\s*\Z")

# --- Tamarin ----------------------------------------------------------------
TAM_RESULT = re.compile(r"^\s{2}(\w+) \((?:all-traces|exists-trace)\): "
                        r"(verified|falsified)[^\n]*\((\d+) steps\)", re.M)


def classify_proverif(text: str) -> list[dict]:
    """Map ProVerif verdicts onto the vocabulary used in expectations.yaml.

    A query that ran out of memory or wall-clock produces no RESULT line at
    all; the caller reports that as `nonterminating`, which is a legitimate
    outcome rather than a missing one.
    """
    out = []
    for q, verdict in PV_RESULT.findall(text):
        # "not attacker(x) is true" means secrecy holds; "is false" means the
        # attacker reached it, i.e. an attack was found.
        out.append({"query": q.strip(),
                    "outcome": "proved" if verdict == "true" else "attack_found"})
    for q in PV_INCONCL.findall(text):
        out.append({"query": q.strip(), "outcome": "inconclusive"})
    return out


def classify_tamarin(text: str) -> list[dict]:
    out = []
    for lemma, verdict, steps in TAM_RESULT.findall(text):
        out.append({"query": lemma,
                    "outcome": "proved" if verdict == "verified" else "attack_found",
                    "steps": int(steps)})
    return out


def collect() -> dict:
    entries = []
    for f in sorted(RAW.glob("*.out")):
        text = f.read_text(errors="replace")
        tool = "tamarin" if f.name.startswith("tamarin_") else "proverif"
        secs = elapsed_of(text)
        found = classify_tamarin(text) if tool == "tamarin" else classify_proverif(text)
        if not found:
            # No verdict line.  Three causes, and the difference matters: a
            # query that exhausted its budget is a reportable result, while a
            # file truncated by a crashed or missing tool is a broken run
            # masquerading as one.  runner.py writes an explicit marker on
            # timeout precisely so the two are never confused.
            low = text.lower()
            if KILL_MARKER.lower() in low:
                reason = "wall-clock budget exhausted"
            elif "out of memory" in low or "cannot allocate" in low:
                reason = "out of memory"
            elif "command not found" in low or "no such file" in low:
                reason = ("verifier did not run -- output holds a shell error, "
                          "not a proof; check `make doctor`")
            elif PV_TRUNCATED.search(RUNNER_LINE.sub("", text)):
                # ProVerif was still inserting Horn clauses when the file ended.
                # That is the signature of a run stopped mid-saturation, and it
                # is what the results shipped with this artifact look like: they
                # were produced before runner.py existed, so they carry no
                # marker, but the evidence of how they ended is in the output
                # itself and is read from there rather than assumed.
                reason = "budget exhausted mid-saturation"
            else:
                reason = "no verdict recorded"
            entries.append({"tool": tool, "source": f.name, "query": None,
                            "outcome": "nonterminating", "reason": reason,
                            "elapsed_s": secs})
            continue
        for r in found:
            # Every query in a file shares that file's invocation, so they
            # share its wall-clock cost.  The alternative -- dividing the time
            # among the queries -- would invent a per-query figure the tool
            # never reported.
            entries.append({"tool": tool, "source": f.name, **r,
                            "elapsed_s": secs})
    return {"schema": 1, "entries": entries}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="after collecting, compare outcomes against "
                         "expectations.yaml and exit non-zero on a mismatch")
    args = ap.parse_args()

    data = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2) + "\n")

    n = len(data["entries"])
    by = {}
    for e in data["entries"]:
        by[e["outcome"]] = by.get(e["outcome"], 0) + 1
    print(f"{OUT.relative_to(ROOT)}: {n} entries")
    for k in sorted(by):
        print(f"  {k:<16} {by[k]}")

    # Surface runs that produced no verdict for a reason other than an honest
    # budget exhaustion.  Left unreported, a verifier that never started looks
    # exactly like a query that diverged.
    broken = [e for e in data["entries"]
              if e.get("reason", "").startswith("verifier did not run")]
    for e in broken:
        print(f"  !! {e['source']}: {e['reason']}")

    if args.check:
        # Imported here rather than at module scope: collecting results must
        # not require expectations.yaml to be readable.
        import check_expectations
        return check_expectations.main()
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
