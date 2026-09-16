# ProVerif and Tamarin on one protocol

The handshake is transcribed once. Every ProVerif query file includes the
shared core in `models/proverif/lib/wireguard_core.pvl`; the Tamarin theory is
written term for term against it. Differences in outcome are therefore
attributable to the tools.

## Where the transcriptions could not be made identical

**Diffie-Hellman.** ProVerif needs the two-symbol `pk`/`dh` encoding to bound
term depth (see `model-notes.md`). Tamarin uses its built-in DH theory. The
equational theories agree; what differs is what the attacker can syntactically
construct, and only one tool needs the restriction.

**Compromise.** ProVerif uses phases, which impose a global ordering — exactly
what harvest-now-decrypt-later needs, and why the post-quantum experiment lives
on the ProVerif side. Tamarin uses action facts, letting a lemma quantify over
the relative order of individual compromise and session events, which is what
the KCI lemmas need.

## Resource profile

Measured on a single core under a 300 s wall-clock budget per query, and a
2.8 GB address-space cap where the platform enforces one (Linux; macOS does
not honour RLIMIT_AS). Budgets are applied by `scripts/runner.py`.

| Query | ProVerif | Tamarin |
|---|---|---|
| Session-key secrecy | proved | verified (7 steps) |
| Forward secrecy | proved | verified (7 steps) |
| Post-quantum forward secrecy | proved | not attempted (phases) |
| Agreement, initiator → responder | proved | verified (18 steps) |
| Injective agreement / replay | proved | not attempted |
| Agreement, responder → initiator | **non-terminating** | not attempted |
| KCI, commitment level | **non-terminating** | falsified (18 steps) |
| KCI, completion level | **non-terminating** | verified (17 steps) |

Wall-clock cost is deliberately absent from this table. It is machine-specific
and it changes on every run, so writing it down here is how a document starts
disagreeing with the results it describes — which is exactly what happened to
an earlier revision of the report. The measured cost of the run currently in
`results/` is generated into [`generated/cost.md`](generated/cost.md) by
`make tables`.

The pattern is one-directional. ProVerif proved what it could prove quickly
and then failed completely rather than slowly, exhausting its budget rather
than converging late.

## Why the KCI queries diverge in ProVerif

Releasing the responder's static scalar lets the attacker compute every
responder-side Diffie-Hellman term. Saturation then generates clauses for all
of them and does not converge. Bounding the initiator to one and then two
sessions reduced memory pressure but not the divergence, so the bounded runs
were abandoned rather than reported as a weaker result.

Tamarin is not sensitive in the same way: constraint solving reasons backwards
from the property rather than saturating forwards from the rules, so a large
attacker-derivable term set does not have to be enumerated.

## A practical rule, as this project found it

Reach for **ProVerif** when the property is secrecy or a correspondence over
honest parties, when many variants of one model must be run, or when a global
staging of attacker capability is the natural formulation. Fully automatic and
fast in that regime.

Reach for **Tamarin** when a long-term secret is compromised as part of the
scenario rather than after it, when the property depends on the ordering of
specific events, or when explicit mutable state is needed.

The KCI pair is all three at once, and is the clearest single instance: every
ProVerif formulation we tried exhausted its budget, and Tamarin decided both
levels well inside its own. See `generated/cost.md` for the current figures.

This is an observation from one protocol, not a general claim about the tools.
It is recorded because comparisons of this kind are rarely published with the
failures included, and the failures are the informative part.
