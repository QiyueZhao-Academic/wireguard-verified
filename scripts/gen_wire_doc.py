"""Generate docs/wire-to-model.md from tools/wire.py.

The correspondence table is documentation of a data structure, so it is
generated from that data structure rather than maintained beside it.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wire  # noqa: E402

PREAMBLE = (ROOT / "docs" / "wire-to-model.md").read_text().split("\n## `")[0] \
    if (ROOT / "docs" / "wire-to-model.md").exists() else ""


def body() -> str:
    rows = []
    for msg, (fields, tot) in wire.MESSAGES.items():
        rows += [f"\n## `{msg}` — {tot} bytes\n",
                 "| Offset | Length | Field | Encrypted | Model term |",
                 "|---:|---:|---|---|---|"]
        for f in fields:
            term = f"`{f.model_term}`" if f.model_term else "*not modelled*"
            rows.append(f"| {f.offset} | {f.length} | `{f.name}` | "
                        f"{'yes' if f.encrypted else '—'} | {term} |")
        rows.append("")
        un = [f for f in fields if f.model_term is None]
        if un:
            rows.append("**Fields not represented in the models**\n")
            rows += [f"- `{f.name}` — {f.note}" for f in un]
            rows.append("")
    return "\n".join(rows)


if __name__ == "__main__":
    out = ROOT / "docs" / "wire-to-model.md"
    out.write_text(PREAMBLE + body())
    print(f"  wire-to-model.md ok ({sum(len(f) for f, _ in wire.MESSAGES.values())} fields)")
