"""Post-quantum migration cost: packet growth and path-MTU reachability.

This module is deliberately free of measurement.  Every number it produces
follows by arithmetic from two inputs: the WireGuard message layout in
wire.py, and the published parameter sizes of the KEMs considered.  Nothing
here depends on the machine it runs on, which is why the conclusions in
Section VI of the report are the most robust the project has.

Run directly:  python3 tools/pqcost.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List

from wire import INITIATION, RESPONSE, X25519_PUBLIC, total


@dataclass(frozen=True)
class Kem:
    """A key-encapsulation mechanism, by its encoded parameter sizes."""
    name: str
    ek_bytes: int    # encapsulation key ("public key")
    ct_bytes: int    # ciphertext
    source: str


# FIPS 203 (ML-KEM) parameter sizes.  ML-KEM-768 is the level the NIST
# guidance treats as the general-purpose choice and is what Rosenpass uses.
KEMS: List[Kem] = [
    Kem("ML-KEM-512", 800, 768, "FIPS 203, Table 3"),
    Kem("ML-KEM-768", 1184, 1088, "FIPS 203, Table 3"),
    Kem("ML-KEM-1024", 1568, 1568, "FIPS 203, Table 3"),
]


@dataclass(frozen=True)
class Path:
    """A network path characterised by its MTU and encapsulation overhead."""
    name: str
    mtu: int
    l3_header: int
    note: str

    @property
    def udp_payload(self) -> int:
        """Largest UDP payload that traverses the path without fragmentation."""
        return self.mtu - self.l3_header - 8  # 8 = UDP header


PATHS: List[Path] = [
    Path("IPv6 minimum MTU", 1280, 40,
         "RFC 8200 requires every IPv6 link to carry 1280 B. A datagram that "
         "does not fit here has no guaranteed path."),
    Path("Ethernet, IPv4", 1500, 20, "The common case on a LAN."),
    Path("Ethernet, IPv6", 1500, 40, "The common case on a dual-stack LAN."),
    Path("PPPoE, IPv4", 1492, 20, "Residential DSL and some fibre deployments."),
    Path("Tunnel stacking, IPv4", 1400, 20,
         "Representative of WireGuard inside another tunnel, a routine "
         "deployment shape."),
]


def substitute(kem: Kem) -> Dict[str, int]:
    """Size the handshake when X25519 is replaced in-band by `kem`.

    The substitution modelled is the minimal one: the initiator's 32-byte
    ephemeral public value becomes an encapsulation key, and the responder's
    32-byte ephemeral becomes the corresponding ciphertext.  Every other field
    keeps its length.  This is the cheapest possible in-band construction, so
    the sizes below are a lower bound on any in-band design -- which is what
    makes the reachability conclusion robust rather than contingent.
    """
    init = total(INITIATION) - X25519_PUBLIC + kem.ek_bytes
    resp = total(RESPONSE) - X25519_PUBLIC + kem.ct_bytes
    return {"initiation": init, "response": resp}


def analyse() -> dict:
    """Full analysis: sizes per KEM, and fit against every path."""
    base = {"initiation": total(INITIATION), "response": total(RESPONSE)}
    out = {
        "baseline": base,
        "kems": [],
        "paths": [{"name": p.name, "mtu": p.mtu, "l3_header": p.l3_header,
                   "udp_payload": p.udp_payload, "note": p.note} for p in PATHS],
    }
    for kem in KEMS:
        sizes = substitute(kem)
        fits = {}
        for p in PATHS:
            margin = p.udp_payload - sizes["initiation"]
            fits[p.name] = {"margin_bytes": margin, "fits": margin >= 0}
        out["kems"].append({
            "name": kem.name,
            "ek_bytes": kem.ek_bytes,
            "ct_bytes": kem.ct_bytes,
            "source": kem.source,
            "initiation_bytes": sizes["initiation"],
            "response_bytes": sizes["response"],
            "initiation_growth": round(sizes["initiation"] / base["initiation"], 1),
            "response_growth": round(sizes["response"] / base["response"], 1),
            "path_fit": fits,
        })
    return out


if __name__ == "__main__":
    a = analyse()
    b = a["baseline"]
    print(f"Baseline: initiation {b['initiation']} B, response {b['response']} B\n")
    print(f"{'KEM':<14} {'ek':>6} {'ct':>6} {'init':>7} {'resp':>7} {'x init':>7} {'x resp':>7}")
    for k in a["kems"]:
        print(f"{k['name']:<14} {k['ek_bytes']:>6} {k['ct_bytes']:>6} "
              f"{k['initiation_bytes']:>7} {k['response_bytes']:>7} "
              f"{k['initiation_growth']:>6}x {k['response_growth']:>6}x")
    print(f"\n{'Path':<24} {'MTU':>5} {'UDP payload':>12}   fit of in-band initiation")
    for p in a["paths"]:
        row = f"{p['name']:<24} {p['mtu']:>5} {p['udp_payload']:>12}   "
        marks = []
        for k in a["kems"]:
            f = k["path_fit"][p["name"]]
            marks.append(f"{k['name'].split('-')[-1]}:"
                         + (f"+{f['margin_bytes']}" if f["fits"] else f"{f['margin_bytes']}"))
        print(row + "  ".join(marks))
    print("\n(margin = usable UDP payload - initiation size; negative means unreachable)")
