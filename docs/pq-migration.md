# Post-quantum migration: packet growth and path reachability

All figures here are produced by `tools/pqcost.py` and follow arithmetically
from the wire-format layout and published ML-KEM parameter sizes (FIPS 203).
No measurement is involved, so nothing in this document depends on the machine
it was produced on.

Regenerate with:

```sh
python3 tools/pqcost.py
```

## The substitution modelled

The cheapest possible in-band construction: the initiator's 32-byte ephemeral
public value becomes an encapsulation key, the responder's becomes the
corresponding ciphertext, every other field keeps its length.

Because this is minimal, the sizes below are a **lower bound on any in-band
design**. That is what makes the reachability conclusion robust rather than
contingent on one particular protocol sketch.

## Packet growth

| KEM | ek | ct | initiation | response |
|---|---:|---:|---|---|
| X25519 (baseline) | 32 | 32 | 148 B | 92 B |
| ML-KEM-512 | 800 | 768 | 916 B (×6.2) | 828 B (×9.0) |
| ML-KEM-768 | 1184 | 1088 | **1300 B (×8.8)** | 1148 B (×12.5) |
| ML-KEM-1024 | 1568 | 1568 | 1684 B (×11.4) | 1628 B (×17.7) |

## Path reachability

Usable UDP payload = MTU − L3 header − 8.

| Path | MTU | Usable UDP | ML-KEM-768 initiation |
|---|---:|---:|---|
| IPv6 minimum MTU | 1280 | 1232 | **exceeds by 68 B** |
| Ethernet, IPv4 | 1500 | 1472 | fits, 172 B spare |
| Ethernet, IPv6 | 1500 | 1452 | fits, 152 B spare |
| PPPoE, IPv4 | 1492 | 1464 | fits, 164 B spare |
| Tunnel stacking, IPv4 | 1400 | 1372 | fits, 72 B spare |

ML-KEM-1024 exceeds every path listed. ML-KEM-512 fits every path listed.

## The chain of consequence

> KEM parameter sizes → datagram size → path MTU → fragmentation or PMTUD
> failure → the handshake is unreachable on some paths → the architecture must
> change.

RFC 8200 requires every IPv6 link to carry a 1280-byte datagram. A datagram
that does not fit has no *guaranteed* path — it may well work on most real
paths, but the protocol can no longer rely on reaching its peer.

This is why post-quantum designs for WireGuard perform the key agreement over
a separate channel and inject the result into the pre-shared key slot rather
than embedding the KEM in the handshake. Rosenpass takes exactly this route.
The analysis above supplies the reason it is *necessary* rather than merely
convenient.

## The trade-off this creates

WireGuard's single-packet, stateless handshake is itself an engineering asset:
no fragment reassembly, no state held before authentication, and it is what
makes the cookie mechanism possible. Post-quantum migration threatens
precisely that asset.

ML-KEM-512 would preserve it but at a security level most deployments will not
choose. ML-KEM-1024 destroys it on every path considered. ML-KEM-768 — the
level NIST guidance treats as general-purpose — sits exactly on the boundary,
fitting common paths while losing the IPv6 guarantee. That is a live
engineering tension, not a textbook exercise.

## The third dimension

Packet size and reachability are two dimensions of the cost. The third is
assumption strength: a KEM-derived pre-shared key preserves the properties of
a configured one only if the KEM binds its shared secret to the encapsulation
key. Without that binding an attacker redirects an observed ciphertext to a
key of its own and recovers the pre-shared key outright, with every primitive
unbroken. See the P12 rows in the result matrix and
`models/proverif/lib/kem.pvl`.
