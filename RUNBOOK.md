# Runbook

From a fresh macOS on Apple Silicon to a reproduced result set, with its
figures and tables.

Tested against macOS Tahoe 26.x on an Apple M1 with 8 GB, and on Linux x86-64
and arm64.

---

## The whole thing, in one command

Paste this into Terminal. It does not matter which directory you are in.

```sh
bash ~/wg-verified/wireguard-verified/run.sh
```

That is the entire procedure. It installs ProVerif and Tamarin, runs both
model suites, checks every verdict against `expectations.yaml`, regenerates
the figures and tables, and prints a summary. About nine minutes on an M1.

### The other three commands

Check the environment without changing anything:

```sh
bash ~/wg-verified/wireguard-verified/run.sh --check
```

Install the tools but run nothing:

```sh
bash ~/wg-verified/wireguard-verified/run.sh --install
```

Run the pipeline but install nothing:

```sh
bash ~/wg-verified/wireguard-verified/run.sh --run
```

Everything is **idempotent**. Re-running on a machine that already has the
tools takes a couple of seconds and changes nothing. Nothing is ever removed
or downgraded.

### What you will see

```
=== 1/4  environment ===
=== 2/4  static checks ===
=== 3/4  verification ===          <- the long part, about 8 minutes
=== 4/4  figures and tables ===
```

Three ProVerif queries sit at their full budget and then move on:

```
  proverif 24a_aliveness           300s  budget exhausted at 300s
  proverif 25a_kci_commit          300s  budget exhausted at 300s
  proverif 25b_kci_complete        300s  budget exhausted at 300s
```

**That is correct and expected.** P5a, P6a and P6b are supposed to exhaust
their budget; see section 3. The run ends with `expectations 18/18 match`.

### If a tool is missing

Nothing aborts. Each half of the verification is guarded on its own tool: with
no ProVerif the ProVerif queries are skipped and the shipped ProVerif results
are kept, and likewise for Tamarin. Figures and tables are still
regenerated, and the summary says what was skipped. The static half of the
repository needs nothing but Python 3.

---

## 1. What the one command actually does

Everything below is the same work, one step at a time. Use it when you want to
install only part of the toolchain, or when something above failed and you want
to see where.

```sh
cd ~/wg-verified/wireguard-verified
make doctor
```

`make doctor` reports what is present and what each missing item costs you.
Nothing here needs to be done in order — install only the tools for the targets
you actually want.

**Three targets work immediately, with only Python 3:**

```sh
make check      # wire layout, model lint, table cross-check
make figures    # SVG figures
make tables     # result tables from the shipped results.json
```

If those three pass, the repository is intact.

### Python

macOS ships a Python 3 that is adequate here, since nothing outside the
standard library is used. There is no `requirements.txt` and no virtual
environment to create — deliberately, because on a memory-constrained machine
every avoidable dependency is worth avoiding.

### Tamarin

Tamarin publishes a native `arm64` bottle, so this is a download and not a
build. Do **not** build it from source: GHC linking spikes to several gigabytes
and will thrash an 8 GB machine.

```sh
brew trust tamarin-prover/tap
brew install tamarin-prover/tap/tamarin-prover
```

The `brew trust` line is not optional on Homebrew 6 and later. Without it the
install fails with

```
Error: Refusing to load formula tamarin-prover/tap/maude from untrusted tap
```

which names `maude` even though the formula you asked for was `tamarin-prover`,
because Homebrew refuses at the point where it resolves the tap's dependencies.

Then:

```sh
make verify-tamarin
```

All six lemmas complete in about forty seconds in total.

### ProVerif

**There is no `brew install proverif`.** The formula does not exist; if you try
it you will get "No available formula". ProVerif is OCaml software and is
installed through opam.

```sh
brew install opam
opam init --bare -y
eval "$(opam env)"
opam switch create 4.14.1
eval "$(opam env)"
opam install -y proverif
```

The switch takes a few minutes. During `opam install proverif`, opam offers to
install system dependencies through Homebrew — answer **1**. That pull is
large: gtk+2 and roughly thirty transitive formulae, needed only by
`proverif_interact`, the graphical trace browser. The command-line binary this
repository uses needs none of it, but the opam package declares `lablgtk` as a
hard dependency, so there is no supported way to decline it.

opam installs into `~/.opam` and does not put ProVerif on your `PATH` in a new
shell. Either run `eval "$(opam env)"` first, or add it to `~/.zshrc`, or just
use `run.sh`, which loads the opam environment for you.

Then:

```sh
make verify-proverif
```

Expect roughly seven minutes.

---

## 2. How the budgets are enforced

Every verifier invocation runs under a wall-clock budget and, where the
platform supports it, an address-space cap. Both are applied by
`scripts/runner.py`.

The obvious implementation — `ulimit -v` followed by `timeout` — does not work
on macOS, and fails in the worst possible way:

- `timeout` is GNU coreutils and macOS does not ship it. The shell writes
  `timeout: command not found` into the redirect, which is the query's own
  result file. The collector then reads a file containing no verdict and
  records the query as non-terminating, which is a legitimate outcome and so
  raises no alarm. Every query in the suite is filed as a budget exhaustion,
  and nothing in the output mentions the missing command.
- `ulimit -v` sets `RLIMIT_AS`, which Darwin defines and then does not enforce.

`runner.py` therefore does both from Python, which the repository already
requires. On Linux the address-space cap is enforced; **on macOS it is not, and
the wall-clock budget is the only real bound.** `make doctor` states which of
the two you are getting rather than leaving you to assume.

A run stopped by the budget has a marker as the last line of its output file,
so a killed run and a crashed one are never confused.

---

## 3. Reading the results

```sh
make verify
```

The last line should read `expectations 18/18 match`.

**A failing query is not necessarily a problem.** Three queries are *expected*
to exhaust their budget, and two models are *expected* to be refuted:

| Query | Expected | Why |
|---|---|---|
| P4c (`23_pq_fs_nopsk`) | attack found | It is the control. Without a psk a quantum attacker recovers the transport keys. If this ever passed, the model had drifted. |
| P12b (`31_kem_psk_reencap`) | attack found | Control for P12a. Without K-PK binding the attacker redirects the ciphertext to a key it controls. |
| S6a (`kci_responder_commit`) | attack found | The KCI result. With the responder's static key compromised, the responder commits key material to a session it attributes to an honest initiator. |
| P5a, P6a, P6b | non-terminating | ProVerif does not converge on these; see `docs/tool-comparison.md`. Tamarin decides two of them. |

`make verify` fails only on a *mismatch* with `expectations.yaml`, which is the
point: it is a regression suite, not a green-tick generator.

### When something does not match

```
  expectations     17/18 match
    [S6a] tamarin_kci_responder_commit.out: expected attack_found, observed proved
```

Read the raw output before touching `expectations.yaml`:

```sh
less results/raw/tamarin_kci_responder_commit.out
```

A mismatch means a model changed, not that the protocol did. If a file holds a
shell error instead of a proof, the collector says so explicitly:

```
  !! 20_secrecy.out: verifier did not run -- output holds a shell error, not a proof
```

Re-run one query on its own while you work on it:

```sh
bash scripts/run_models.sh 20_secrecy
bash scripts/run_models.sh kci_responder_commit
```

---

## 4. The network laboratory (Linux only)

`lab/` contains a multi-node network-namespace topology. **It cannot run on
macOS**: `ip netns` is a Linux kernel interface and XNU has no equivalent.

It was not exercised for this release, and no measurement from it appears in
the report. To run it you need a Linux VM:

```sh
brew install lima
limactl start --name=wg template://ubuntu-lts
limactl shell wg
# inside the VM:
sudo apt-get install -y wireguard-tools tcpdump iproute2
cd /path/to/wireguard-verified && sudo lab/topology.sh
```

See `lab/README.md`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `brew install proverif` → No available formula | The formula does not exist | Use opam, section 1 |
| `Refusing to load formula ... from untrusted tap` | Homebrew 6 requires explicit trust | `brew trust tamarin-prover/tap`, then install again |
| `make: proverif: No such file` | opam environment not loaded in this shell | `eval "$(opam env)"`, or use `run.sh` |
| Every query reports non-terminating | An old checkout using `timeout` | Fixed here; confirm `scripts/runner.py` exists and `make doctor` passes |
| `!! <file>: verifier did not run` | The output file holds a shell error | `make doctor`; the named tool is missing or not on PATH |
| Tamarin: `maude tool: not found` | Maude not on PATH | `brew install maude` |
| Tamarin: `unsupported version '3.2'` | Maude outside Tamarin's accepted list | Benign. Proofs run and verdicts are valid |
| Tamarin wellformedness warning about derivation checks | A heuristic pre-check timed out | Benign. `--derivcheck-timeout=0` disables it; the Makefile already passes it |
| Results look stale after editing a model | `results.json` not regenerated | `make verify` then `make tables` |
| Whole machine sluggish during `make verify` | Two verifiers running at once | Run `make verify-proverif` and `make verify-tamarin` separately |
| `Permission denied` running a script | Execute bit lost in transit | Use `bash run.sh` rather than `./run.sh` |
| `make install` cannot find `brew` | Homebrew not installed | Install from https://brew.sh, then re-run |
| `unbound variable` from a shell script | An old checkout, on bash 3.2 | Fixed here; these scripts no longer use `set -u` |

## Rebuilding from scratch

```sh
make distclean
bash run.sh --run
```

Or in pieces:

```sh
make distclean
make verify        # regenerate results (needs both verifiers)
make all           # checks, figures, tables
make summary       # headline results
```

## Command reference

`make help` prints this list at any time.

| Command | Needs | Time |
|---|---|---|
| `bash run.sh` | nothing (installs what it needs) | ~9 min |
| `bash run.sh --check` | Python 3 | instant |
| `make install` | Homebrew on macOS | ~5 min first time, seconds after |
| `make everything` | nothing (degrades gracefully) | ~9 min |
| `make doctor` | Python 3 | instant |
| `make check` | Python 3 | instant |
| `make figures` | Python 3 | instant |
| `make tables` | Python 3 | instant |
| `make wire-doc` | Python 3 | instant |
| `make verify-tamarin` | Tamarin | ~40 s |
| `make verify-proverif` | ProVerif | ~7 min |
| `make verify` | both | ~8 min |
| `make summary` | Python 3 | instant |

### Useful overrides

```sh
make verify TIMEOUT=600                    # a longer budget per query
make verify MEM_KB=4000000                 # a larger address-space cap (Linux)
bash scripts/run_models.sh 20_secrecy      # one query only
bash run.sh --run                          # pipeline only, no installation
bash scripts/bootstrap.sh --dry-run        # show what installation would do
```
