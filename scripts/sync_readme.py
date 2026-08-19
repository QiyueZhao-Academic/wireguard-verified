"""Inject the generated results table into README.md.

The README and the report must show the same numbers.  Rather than trusting
that they will, the table is written into a delimited block by this script and
never edited by hand.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BEGIN, END = "<!-- BEGIN GENERATED RESULTS -->", "<!-- END GENERATED RESULTS -->"


def main() -> int:
    table = (ROOT / "docs" / "generated" / "results.md").read_text()
    readme = ROOT / "README.md"
    text = readme.read_text()
    if BEGIN not in text or END not in text:
        print("  readme sync      markers missing; left unchanged")
        return 1
    head, _, rest = text.partition(BEGIN)
    _, _, tail = rest.partition(END)
    readme.write_text(f"{head}{BEGIN}\n{table}{END}{tail}")
    print(f"  readme sync      ok ({table.count(chr(10)) - 2} result rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
