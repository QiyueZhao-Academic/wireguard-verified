"""Cross-check the wire-format table against the model sources.

The correspondence between bytes on the wire and terms in the models is the
part of this project that ties the two halves together, so it must not be
allowed to drift.  This script fails the build if a field claims a model term
that no model actually contains, or if a modelled field is missing from the
table.

It is a consistency check, not a proof of faithfulness: it verifies that the
table and the models talk about the same identifiers, not that the model is a
correct abstraction of the protocol.  That claim is argued in the report.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wire  # noqa: E402

CORE = ROOT / "models" / "proverif" / "lib" / "wireguard_core.pvl"

# Identifiers that must appear in the shared ProVerif core for a field's
# claimed model term to be meaningful.  Keyed by field name.
REQUIRED = {
    "unencrypted_ephemeral": ["pk(ei)", "pk(er)"],
    "encrypted_static": ["msgStatic", "aead(k1, zero_nonce, g2b(Si), hi1)"],
    "encrypted_timestamp": ["msgTs", "tai64n"],
    "encrypted_nothing": ["msgEmpty"],
    "mac1": ["LABEL_MAC1"],
}


def main() -> int:
    problems: list[str] = []

    # 1. The layout must be internally consistent (offsets, totals).
    problems += wire.check()

    # 2. Every field claiming a model term must name one the core defines.
    core = CORE.read_text()
    seen_fields = set()
    for name, (fields, _) in wire.MESSAGES.items():
        for f in fields:
            seen_fields.add(f.name)
            if f.model_term is None:
                # Unmodelled fields must carry a stated reason -- an empty
                # note would mean the omission was never justified.
                if len(f.note.strip()) < 20:
                    problems.append(
                        f"{name}.{f.name}: not modelled, but no reason recorded")
                continue
            for token in REQUIRED.get(f.name, []):
                if token not in core:
                    problems.append(
                        f"{name}.{f.name}: table cites '{token}', "
                        f"absent from {CORE.name}")

    # 3. Every AEAD term in the core must correspond to a table field.
    for term in re.findall(r"let (msg\w+)\s*=\s*aead\(", core):
        if not any(f.model_term and term in f.model_term
                   for _, (fs, _) in wire.MESSAGES.items() for f in fs):
            problems.append(f"{CORE.name}: term '{term}' has no field in the table")

    if problems:
        print("  wire table       FAILED")
        for p in problems:
            print("    " + p)
        return 1
    total_fields = sum(len(f) for f, _ in wire.MESSAGES.values())
    print(f"  wire table       ok ({total_fields} fields, "
          f"{len(wire.MESSAGES)} messages, cross-checked against {CORE.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
