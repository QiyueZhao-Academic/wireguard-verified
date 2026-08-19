# Threat model

## Attacker

Dolev-Yao: full control of the network. The attacker reads, drops, reorders,
replays, and forges arbitrary messages, and may run any number of concurrent
sessions in either role. Cryptographic primitives are perfect — the attacker
learns nothing about a term except through the destructors declared in
`models/proverif/lib/primitives.pvl`.

## Compromise is explicit

No compromise is a built-in capability. Each class of secret is revealed only
by an explicit action, so every query states which compromises it tolerates
and no proof can silently depend on an assumption that was never written down.

| Secret | ProVerif | Tamarin |
|---|---|---|
| Static scalar | published by an explicit process | `Reveal_Ltk` rule with an action fact |
| Pre-shared key | published in the control models | `Reveal_Psk` rule with an action fact |
| Discrete logarithms | phase-1 oracle | not modelled |

## Post-quantum capability

Expressed with ProVerif's phase mechanism.

- **Phase 0** — classical attacker.
- **Phase 1** — the attacker gains a discrete-logarithm oracle. The oracle is
  private in phase 0 and exposed only by a phase-1 process.

Since every ephemeral public value travels in clear, an attacker that recorded
phase-0 traffic can invert all of it once phase 1 begins — statics and
ephemerals alike. This is the standard formalisation of
harvest-now-decrypt-later, and it is what makes post-quantum forward secrecy a
property rather than a slogan.

Symmetric primitives and the pre-shared key remain secure in phase 1. That
asymmetry is the whole point: it is what the P4/P4-control pair measures.

## What is out of scope

- Computational cost, and therefore the cookie mechanism and any denial-of-
  service property that depends on load
- The data plane, its counter, and its anti-replay window
- Endpoint roaming, which is a network-layer behaviour with no counterpart in
  an abstract Noise model
- Side channels, implementation defects, concrete security parameters
- Small-subgroup and invalid-curve behaviour

See `limitations.md`.
