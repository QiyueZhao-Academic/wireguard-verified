# Limitations

Stated plainly because a reader who has to discover these for themselves will
reasonably wonder what else was not mentioned.

## The symbolic abstraction

Both models assume a Dolev-Yao attacker and perfect primitives. They say
nothing about side channels, implementation defects, or concrete security
parameters. A proof here means "no attack exists within this model", and the
model's boundaries are the ones listed below.

**Diffie-Hellman.** Every 32-byte value is treated as `g^t` for some `t`. This
excludes small-subgroup and invalid-curve behaviour and the all-zero output
check. It is faithful for a prime-order group and is the standard symbolic
abstraction, but it is an abstraction.

**The transcript hash.** Modelling `h` after step *i* as a flat
collision-resistant function of the prefix binds the same data as the iterated
formulation, but assumes the chain is collision-free as a whole rather than
deriving that from a compression function. A collision attack on BLAKE2s would
be invisible — as it would be to any symbolic model.

**The cookie mechanism.** `mac2` and the cookie reply are load-shedding
devices. A symbolic attacker has no notion of computational cost, so the
property they provide cannot be stated in this framework. It is argued in the
report rather than verified, and the argument is clearly marked as such.

## The resource budget is not identical on both platforms

Every query runs under a 300 s wall-clock budget and a 2.8 GB address-space
cap. The cap is enforced on Linux, through `RLIMIT_AS`. **It is not enforced on
macOS**: Darwin defines the limit and ignores it, so on Darwin the wall-clock
budget is the only bound that binds.

This matters when comparing a run against the shipped results. A query that
exhausts its budget does so for the same reason on both platforms — none of the
three non-terminating queries here is anywhere near the memory ceiling; they
diverge in the saturation loop and are stopped by the clock. But a future query
that failed on memory would fail differently on the two platforms, and that
would be a property of the machine rather than of the protocol.

`make doctor` reports which of the two budgets is in force. `scripts/runner.py`
records the same fact in the header of every raw output file, so a result
carries its own provenance rather than depending on a reader remembering which
machine produced it.

## Undecided queries

Three ProVerif queries did not terminate within budget: agreement in the
responder-to-initiator direction (P5a), and both KCI levels (P6a, P6b).

**A non-terminating query is not a proof of absence.** It says the tool could
not settle the question within the budget and nothing whatever about the
protocol. Two of the three were subsequently decided by Tamarin. The third,
P5a, remains open in this artifact.

One query is inconclusive (P12c) rather than restated until something passed.
ProVerif's over-approximation could not decide a disjunctive statement about
the responder's view of a KEM-derived pre-shared key.

## Bounded runs

The ProVerif KCI queries were also attempted with the initiator bounded to one
and to two sessions. Those runs would have established the property for that
number of sessions only. They diverged anyway and are reported as
non-terminating; no bounded result is claimed anywhere.

## Scope: verification, not measurement

This artifact verifies the handshake. It does not measure it.

The network laboratory in `lab/` — a multi-node network-namespace topology
with traffic capture and injected wide-area conditions — is provided as a
Linux companion and **was not exercised for this release**. Network namespaces
are a Linux kernel interface with no macOS equivalent, and the development
machine is an Apple Silicon laptop.

Consequently: **no latency, throughput, or packet-count measurement appears
anywhere in the report, and none should be inferred from it.** The
post-quantum analysis in Section VI depends on no measurement at all — it
follows arithmetically from the wire-format layout and published KEM parameter
sizes, which is precisely what makes it the most robust part of the work.

## Attribution and originality

WireGuard has been analysed before: symbolically by Donenfeld and Milner, and
in the computational model by Lipp, Blanchet and Bhargavan. This is an
independent reconstruction undertaken from the specification. **It claims no
new vulnerability.**

Where conclusions differ from prior work, the difference is a modelling
assumption rather than a finding. The assumptions are stated in
`model-notes.md` so that such differences can be traced rather than argued
about.
