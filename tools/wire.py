"""WireGuard wire format: authoritative field layout and message construction.

Everything in this module is derived from the WireGuard whitepaper
(Donenfeld, NDSS 2017), section 5.4, and is deterministic: no network, no
cryptography, no external dependency beyond the standard library.  It is the
single source of truth for byte offsets in this artifact.  The correspondence
table in docs/wire-to-model.md and the packet-size figures in the report are
both generated from here, and scripts/verify_wire_table.py cross-checks the
formal models against it, so the three cannot drift apart silently.

Run directly to print the layout tables:  python3 tools/wire.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import List

# Sizes of the primitives WireGuard instantiates Noise_IKpsk2 with.
X25519_PUBLIC = 32   # Curve25519 public value
POLY1305_TAG = 16    # ChaCha20-Poly1305 authentication tag
TAI64N = 12          # TAI64N timestamp
COOKIE = 16          # cookie value
XCHACHA_NONCE = 24   # XChaCha20-Poly1305 nonce used by the cookie reply


@dataclass(frozen=True)
class Field:
    """One field of a WireGuard message.

    `model_term` names the corresponding term in the ProVerif core
    (models/proverif/lib/wireguard_core.pvl).  A value of None means the field
    is deliberately not represented in the formal models; `note` then records
    why, which is the entry that docs/wire-to-model.md reproduces.
    """
    offset: int
    length: int
    name: str
    encrypted: bool
    model_term: str | None
    note: str


def _layout(fields: List[tuple]) -> List[Field]:
    """Build a field list, computing offsets by accumulation.

    Offsets are never written by hand: they are derived from the lengths, so a
    corrected length cannot leave a stale offset behind it.
    """
    out, off = [], 0
    for name, length, encrypted, term, note in fields:
        out.append(Field(off, length, name, encrypted, term, note))
        off += length
    return out


# --- Message 1: handshake initiation ---------------------------------------
INITIATION = _layout([
    ("message_type", 1, False, None,
     "Constant 1. Demultiplexing only; the models use distinct channels."),
    ("reserved", 3, False, None,
     "Zero on transmission, ignored on receipt. Carries no security burden."),
    ("sender_index", 4, False, None,
     "Session demultiplexing. Not modelled: it is chosen freely by the sender "
     "and the protocol's security does not depend on its value."),
    ("unencrypted_ephemeral", X25519_PUBLIC, False, "Ei = pk(ei)",
     "In the clear, by design. Object of the ephemeral-ephemeral term ee."),
    ("encrypted_static", X25519_PUBLIC + POLY1305_TAG, True,
     "msgStatic = aead(k1, 0, g2b(Si), hi1)",
     "32 B key plus 16 B tag. The initiator's identity; object of P8."),
    ("encrypted_timestamp", TAI64N + POLY1305_TAG, True,
     "msgTs = aead(k2, 0, tai64n, hi2)",
     "12 B TAI64N plus 16 B tag. Monotonicity is what P9 rests on."),
    ("mac1", POLY1305_TAG, False,
     "mac(hash(concat(LABEL_MAC1, g2b(Sr))), ...)",
     "Keyed by a public value. Proves knowledge of the responder's static "
     "public key; provides no cryptographic authentication."),
    ("mac2", POLY1305_TAG, False, None,
     "Cookie-dependent, all-zero when the responder is not under load. The "
     "cookie mechanism is a rate-limiting device outside the Dolev-Yao model, "
     "which has no notion of computational load; argued in the report instead."),
])

# --- Message 2: handshake response -----------------------------------------
RESPONSE = _layout([
    ("message_type", 1, False, None,
     "Constant 2. Demultiplexing only; the models use distinct channels."),
    ("reserved", 3, False, None,
     "Zero on transmission, ignored on receipt. Carries no security burden."),
    ("sender_index", 4, False, None,
     "Responder's session index. Chosen freely; carries no security burden."),
    ("receiver_index", 4, False, None, "Echoes the initiator's sender_index."),
    ("unencrypted_ephemeral", X25519_PUBLIC, False, "Er = pk(er)",
     "In the clear, by design."),
    ("encrypted_nothing", 0 + POLY1305_TAG, True,
     "msgEmpty = aead(k3, 0, EMPTY, hi5)",
     "Zero-length plaintext plus 16 B tag. Successful decryption is the "
     "initiator's evidence that the responder holds the same psk."),
    ("mac1", POLY1305_TAG, False,
     "mac(hash(concat(LABEL_MAC1, g2b(Si))), ...)",
     "Keyed by the INITIATOR's static public key. An observer holding a "
     "candidate public key can test it, which is why identity hiding is "
     "conditional on the attacker not knowing the candidates (see 26/27)."),
    ("mac2", POLY1305_TAG, False, None,
     "Cookie-dependent, as in message 1. Not modelled for the same reason: "
     "the symbolic attacker has no notion of computational load."),
])

# --- Message 3: cookie reply ------------------------------------------------
COOKIE_REPLY = _layout([
    ("message_type", 1, False, None,
     "Constant 3. Demultiplexing only; the models use distinct channels."),
    ("reserved", 3, False, None,
     "Zero on transmission, ignored on receipt. Carries no security burden."),
    ("receiver_index", 4, False, None,
     "Echoes the sender's index. Demultiplexing only, no security burden."),
    ("nonce", XCHACHA_NONCE, False, None, "XChaCha20-Poly1305 nonce."),
    ("encrypted_cookie", COOKIE + POLY1305_TAG, True, None,
     "Not modelled: the cookie is a load-shedding mechanism, and the symbolic "
     "attacker has no notion of computational cost."),
])

# --- Message 4: transport data (header only; payload is variable) ----------
TRANSPORT = _layout([
    ("message_type", 1, False, None,
     "Constant 4. Demultiplexing only; the models use distinct channels."),
    ("reserved", 3, False, None,
     "Zero on transmission, ignored on receipt. Carries no security burden."),
    ("receiver_index", 4, False, None,
     "Selects the session. Demultiplexing only; the handshake models cover "
     "key agreement, not the data plane."),
    ("counter", 8, False, None,
     "Nonce counter, also the anti-replay window index. The data plane's "
     "sliding window is outside the handshake models."),
])

MESSAGES = {
    "handshake_initiation": (INITIATION, 148),
    "handshake_response": (RESPONSE, 92),
    "cookie_reply": (COOKIE_REPLY, 64),
    "transport_data_header": (TRANSPORT, 16),
}


def total(fields: List[Field]) -> int:
    """Total encoded length of a message."""
    return sum(f.length for f in fields)


def check() -> List[str]:
    """Verify every message against its documented total length.

    Returns a list of human-readable failures; empty means the layout is
    self-consistent.  Called by scripts/verify_wire_table.py and by `make check`.
    """
    problems = []
    for name, (fields, expected) in MESSAGES.items():
        got = total(fields)
        if got != expected:
            problems.append(f"{name}: computed {got} B, specification says {expected} B")
        # Offsets must be contiguous and start at zero.
        off = 0
        for f in fields:
            if f.offset != off:
                problems.append(f"{name}.{f.name}: offset {f.offset}, expected {off}")
            off += f.length
    return problems


def as_dict() -> dict:
    """Serialisable form, consumed by the table and figure generators."""
    return {
        name: {
            "total_bytes": total(fields),
            "fields": [asdict(f) for f in fields],
        }
        for name, (fields, _) in MESSAGES.items()
    }


def _fmt_table(name: str, fields: List[Field]) -> str:
    lines = [f"{name}  ({total(fields)} bytes)",
             f"{'off':>4} {'len':>4}  {'field':<24} {'enc':<4} model term"]
    for f in fields:
        lines.append(f"{f.offset:>4} {f.length:>4}  {f.name:<24} "
                     f"{'yes' if f.encrypted else '-':<4} {f.model_term or '(not modelled)'}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    problems = check()
    for name, (fields, _) in MESSAGES.items():
        print(_fmt_table(name, fields), end="\n\n")
    if problems:
        print("LAYOUT CHECK FAILED:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        sys.exit(1)
    print("layout check: all messages match the specification totals")
