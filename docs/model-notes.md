# Modelling notes

A record of the decisions that shaped the models, including the ones that were
wrong first. These are kept because they are the part of a formal-methods
project that is hardest to reconstruct afterwards and most useful to a reader
attempting something similar.

## The Diffie-Hellman encoding, and why the obvious one does not work

The natural way to write X25519 in ProVerif is

```
fun exp(G, exponent): G.
equation forall x: exponent, y: exponent;
  exp(exp(gen, x), y) = exp(exp(gen, y), x).
```

This was the first formulation used here, and it does not terminate. The
equation normalises towers of depth two and no deeper, so an attacker
supplying `exp(exp(exp(gen,a),b),c)` as a peer's ephemeral generates terms the
rewriting system cannot reduce, and each such term generates more. On the
secrecy query, saturation reached roughly 1.2 × 10⁴ Horn clauses and exhausted
a 2.6 GB cap without producing a verdict. Each role *alone* verified in under
a second; only the combination diverged, which is what made the cause
non-obvious.

The formulation now in `lib/primitives.pvl` is

```
fun pk(exponent): G.
fun dh(G, exponent): key.
equation forall x: exponent, y: exponent; dh(pk(x), y) = dh(pk(y), x).
```

Two properties do the work. `pk` is the only constructor of type `G`, so every
group element the attacker can build is `g^t` for a term `t` it knows — which
is faithful for a prime-order group, where every X25519 output has that form.
And `dh` returns `key`, not `G`, so a Diffie-Hellman result cannot re-enter as
a group element. Term depth is bounded by construction. The same query is now
proved well inside the budget; the measured cost of the current run is
in [`generated/cost.md`](generated/cost.md).

The Tamarin model does not need this restriction and uses the built-in DH
theory directly, which normalises such terms natively. This is one of the two
places where the two transcriptions genuinely differ; see
`tool-comparison.md`.

## Flattening the transcript hash

Noise updates `h ← HASH(h ‖ field)` after every field. Here `h` after step *i*
is modelled as a distinct collision-resistant function `hT_i` of the whole
transcript prefix.

The justification is narrow and worth stating exactly. `h` is never
transmitted and is used only as AEAD associated data, so the sole property the
protocol requires of it is that it bind the transcript prefix injectively.
Both formulations bind the same data; the flat one keeps term depth constant
instead of growing it linearly in the number of fields.

What this costs: the model assumes the chain is collision-free as a whole
rather than deriving that from the compression function. A collision attack
on BLAKE2s would be invisible — as it would be to any symbolic model.
Recorded in `limitations.md`.

## Splitting KCI into two levels

The KCI queries were first written as a single question: with the responder's
static key compromised, can the attacker impersonate an honest initiator to
it? Writing it that way would have produced one verdict and hidden the actual
structure.

Reading the key schedule suggested the two levels would separate. Forging
message 1 needs `es = DH(e_i, S_r)` and `ss = DH(s_i, S_r)`, both computable
from the leaked responder scalar. Deriving the transport keys additionally
needs `se = DH(e_r, S_i)`, which needs a scalar the attacker does not have.
The prediction was made from the model source before either query was run, and
Tamarin confirmed it: `kci_responder_commit` falsified, `kci_responder_complete`
verified.

This is why the responder emits two distinct events rather than one. A model
with a single "session established" event would have answered a question
nobody asked.

## Queries that were restated, and one that was not

The KEM experiment originally asked for agreement between the initiator's and
responder's view of the established pre-shared key. That question is
ill-posed: a bare KEM encapsulation authenticates nobody, since anyone holding
the public encapsulation key can send a well-formed ciphertext. The query was
restated disjunctively — either the honest initiator produced the key, or the
attacker already knows it — and ProVerif returned `cannot be proved`.

It is reported as inconclusive (P12c) rather than weakened further until
something passed. The separating result for that experiment is secrecy, which
is decisive: proved with K-PK binding, refuted without it.

## A parsing trap worth knowing about

A ProVerif comment containing the text `witness*)` is closed by the `*)`
inside it. The parse error then surfaces several lines later as "illegal
character", pointing at a symptom far from the cause. `scripts/lint_models.py`
checks comment nesting for exactly this reason.
