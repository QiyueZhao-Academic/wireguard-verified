"""Static checks on the model sources, before any verifier is invoked.

These catch a specific class of mistake that costs disproportionate time when
it slips through, because the verifier's error message points at a symptom far
from the cause.  The comment-termination check exists because of a real
incident during development: a ProVerif comment containing the text
`witness*)` was silently closed by the `*)` inside it, and the parse error
surfaced several lines later as an "illegal character".
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check_proverif(path: Path) -> list[str]:
    """Comment nesting, stray backticks, and unbalanced parentheses."""
    t, problems = path.read_text(), []
    depth, i, opened_at = 0, 0, []
    while i < len(t) - 1:
        if t[i:i + 2] == "(*":
            depth += 1
            opened_at.append(t[:i].count("\n") + 1)
            i += 2
            continue
        if t[i:i + 2] == "*)":
            depth -= 1
            if depth < 0:
                problems.append(f"{path}:{t[:i].count(chr(10)) + 1}: "
                                "comment closed without being opened -- a '*)' "
                                "inside prose closes the comment early")
                depth = 0
            elif opened_at:
                opened_at.pop()
            i += 2
            continue
        if depth == 0 and t[i] == "`":
            problems.append(f"{path}:{t[:i].count(chr(10)) + 1}: "
                            "backtick outside a comment is not valid ProVerif")
        i += 1
    if depth > 0:
        problems.append(f"{path}: {depth} comment(s) never closed "
                        f"(opened at line {opened_at[0] if opened_at else '?'})")
    return problems


def check_tamarin(path: Path) -> list[str]:
    t, problems = path.read_text(), []
    if "begin" not in t or not t.rstrip().endswith("end"):
        problems.append(f"{path}: theory must open with 'begin' and close with 'end'")
    for ch, name in (("{", "brace"), ("[", "bracket")):
        close = {"{": "}", "[": "]"}[ch]
        if t.count(ch) != t.count(close):
            problems.append(f"{path}: unbalanced {name}s "
                            f"({t.count(ch)} open, {t.count(close)} close)")
    return problems


def main() -> int:
    problems: list[str] = []
    pv = sorted((ROOT / "models" / "proverif").rglob("*.pv")) + \
         sorted((ROOT / "models" / "proverif").rglob("*.pvl"))
    tam = sorted((ROOT / "models" / "tamarin").rglob("*.spthy"))
    for f in pv:
        problems += check_proverif(f)
    for f in tam:
        problems += check_tamarin(f)

    if problems:
        print("  model lint       FAILED")
        for p in problems:
            print("    " + p)
        return 1
    print(f"  model lint       ok ({len(pv)} ProVerif, {len(tam)} Tamarin sources)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
