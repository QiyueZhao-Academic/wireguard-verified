# WireGuard-Verified

## 📄 [Full verification report (PDF)](./REPORT.pdf)
Successful local run on macOS · [Read online](./docs/wire-to-model.md)

**From wire format to formal model: symbolic verification of the WireGuard
handshake and the three-dimensional cost of post-quantum migration.**

Qiyue Zhao

---

## Résumé (en français)

> *Cette section est en français ; le reste du dépôt est en anglais.*

Ce projet vérifie formellement la poignée de main de WireGuard, qui instancie
le motif Noise `IKpsk2`. Le protocole est transcrit une seule fois, puis
confié à deux vérificateurs symboliques distincts — ProVerif et Tamarin — de
sorte que tout écart entre leurs verdicts soit imputable à l'outil et non à la
modélisation. Onze propriétés de sécurité ont été vérifiées, et chaque terme
des modèles est relié à une plage d'octets sur le fil par une table de
correspondance vérifiée automatiquement.

Trois résultats se dégagent. D'abord, une expérience contrôlée isole
l'apport réel de la clé pré-partagée : face à un adversaire disposant d'un
oracle de logarithme discret, le secret des clés de transport est **prouvé**
lorsqu'une clé pré-partagée est configurée et **réfuté** lorsqu'elle ne l'est
pas, les deux modèles ne différant que par cette seule ligne. Ensuite, la
résistance à l'usurpation par compromission de clé (KCI) est localisée
précisément : le répondeur engage bien du matériel de clé pour une session
qu'il attribue à un pair honnête, mais n'accepte jamais de trafic sur cette
session ; c'est le terme statique-éphémère `se` qui sépare les deux niveaux.
Enfin, une analyse arithmétique montre qu'une initiation ML-KEM-768 intégrée
atteint 1300 octets et dépasse de 68 octets la charge utile UDP du MTU minimal
IPv6 — aucun chemin garanti n'existe, ce qui explique pourquoi les
architectures à canal séparé sont nécessaires et non simplement commodes.

Trois requêtes ProVerif n'ont pas terminé dans le budget fixé ; Tamarin en a
tranché deux en moins de dix secondes. Ces échecs sont rapportés comme des
résultats, avec le profil de ressources de chaque requête.

---

## What this is

Two entry points into one repository.

| If you care about **formal methods** | If you care about **protocol engineering** |
|---|---|
| Models → `models/proverif/`, `models/tamarin/` | Wire-format table → `docs/wire-to-model.md` |
| Result matrix → below, and `docs/generated/results.md` | Packet growth and MTU → `docs/pq-migration.md` |
| Attack traces → `results/traces/` | Network lab (Linux) → `lab/` |
| Tool comparison → `docs/tool-comparison.md` | Modelling notes → `docs/model-notes.md` |

The technical report is built, not shipped: `make report` compiles
`report/main.tex` into `docs/report.pdf`. Every table, figure and quoted
number in it is generated from `results/results.json` at build time, so the
PDF always describes the run that is actually in `results/`.

## Results

Every cell is populated: proved, refuted, inconclusive, or non-terminating
with a recorded cause. Rendered from `results/results.json`; never written by
hand.

<!-- BEGIN GENERATED RESULTS -->
| ID | Property | Tool | Outcome |
|---|---|---|---|
| P1 | Session-key secrecy | ProVerif | proved |
| P3 | Forward secrecy | ProVerif | proved |
| P4 | Post-quantum forward secrecy (psk) | ProVerif | proved |
| P4c | same, psk absent (control) | ProVerif | attack found |
| P5a | Agreement, responder to initiator | ProVerif | non-terminating |
| P5b | Agreement, initiator to responder | ProVerif | proved |
| P5c | Injective agreement / replay (P9) | ProVerif | proved |
| P6a | KCI, commitment level | ProVerif | non-terminating |
| P6b | KCI, completion level | ProVerif | non-terminating |
| P12a | KEM-derived psk secrecy, K-PK binding | ProVerif | proved |
| P12b | same, binding absent (control) | ProVerif | attack found |
| P12c | KEM-derived psk, responder-view soundness | ProVerif | inconclusive |
| S0 | Model admits an honest run | Tamarin | proved |
| S1 | Session-key secrecy | Tamarin | proved |
| S3 | Forward secrecy | Tamarin | proved |
| S5 | Agreement, no compromise | Tamarin | proved |
| S6a | KCI, commitment level | Tamarin | attack found |
| S6b | KCI, completion level | Tamarin | proved |
<!-- END GENERATED RESULTS -->

Post-quantum in-band substitution, computed by `tools/pqcost.py`:

| KEM | ek | ct | initiation | response |
|---|---|---|---|---|
| X25519 (baseline) | 32 | 32 | 148 B | 92 B |
| ML-KEM-512 | 800 | 768 | 916 B (×6.2) | 828 B (×9.0) |
| ML-KEM-768 | 1184 | 1088 | **1300 B (×8.8)** | 1148 B (×12.5) |
| ML-KEM-1024 | 1568 | 1568 | 1684 B (×11.4) | 1628 B (×17.7) |

The IPv6 minimum MTU leaves 1232 B of usable UDP payload. **ML-KEM-768
exceeds it by 68 B**, so an in-band handshake has no guaranteed path.

## Quick start

One command, from anywhere:

```sh
bash ~/wg-verified/wireguard-verified/run.sh
```

It installs ProVerif, Tamarin and the LaTeX packages, runs both model suites,
checks every verdict against `expectations.yaml`, regenerates the figures and
tables, compiles the report, and prints a summary. About nine minutes; the
installation step is idempotent, so re-running it is cheap.

Three variants, same shape:

```sh
bash run.sh --check      # environment report only, changes nothing
bash run.sh --install    # install the tools, run nothing
bash run.sh --run        # run the pipeline, install nothing
```

Use `bash run.sh`, not `./run.sh`: the execute bit does not survive every
archive format, and `bash` does not care.

**Nothing is hidden behind these.** Every step remains available on its own:

```sh
make doctor           # environment check; says exactly what is missing
make check            # layout, model and coverage checks — Python 3 only
make figures          # SVG + TikZ figures — Python 3 only
make tables           # result tables from results/results.json
make verify           # both model suites, then check expectations
make verify-tamarin   # Tamarin lemmas only (~40 s)
make verify-proverif  # ProVerif queries only (~7 min)
make report           # compile the IEEE-format report (needs LaTeX)
make summary          # headline results
make help             # this list
```

`make check`, `make figures` and `make tables` work on a bare macOS with only
Python 3. The pipeline degrades gracefully: each verification suite is guarded
on its own tool, so a machine with one verifier installed runs that half and
keeps the shipped results for the other.

See **[RUNBOOK.md](RUNBOOK.md)** for the manual installation route and a
troubleshooting table.

## Requirements

| Tool | Version used | macOS (Apple Silicon) |
|---|---|---|
| Python | 3.12 | preinstalled, or `brew install python@3.12` |
| ProVerif | 2.05 | via **opam** — there is no `brew install proverif` |
| Tamarin | 1.12.0 | `brew trust tamarin-prover/tap` then `brew install tamarin-prover/tap/tamarin-prover` |
| Maude | 3.2+ | pulled in by the Tamarin formula |
| LaTeX | TeX Live 2023+ | BasicTeX plus `tlmgr install` — see RUNBOOK |

Verification was carried out on a single core under a **300 s wall-clock
budget per query** and, on Linux, a 2.8 GB address-space cap — chosen to match
what remains free on an 8 GB laptop with an editor open. Nothing in this
repository needs a larger machine.

macOS does not enforce `RLIMIT_AS`, so on Darwin the wall-clock budget is the
only bound that actually binds. `make doctor` says which of the two you are
getting rather than leaving you to assume. Both are applied by
`scripts/runner.py`; see RUNBOOK section 2 for why neither `timeout` nor
`ulimit -v` is used.

## Reproducing

```sh
bash run.sh              # everything, from scratch
make verify              # or just the model suites
```

`expectations.yaml` declares the expected verdict for all eighteen results in
the table above — every row, not a subset — and the build fails on any
mismatch. Outcomes that are attacks are expectations too:
`23_pq_fs_nopsk.pv` is *supposed* to be refuted, and a run in which it
succeeded would mean the model had drifted.

## Honest gaps

- Three ProVerif queries did not terminate within budget (P5a, P6a, P6b).
  Two were decided by Tamarin; the third remains open. See
  `docs/tool-comparison.md`.
- One ProVerif query is inconclusive (P12c) rather than restated until it
  passed.
- The network laboratory in `lab/` requires Linux network namespaces and was
  **not exercised for this release**. No latency or throughput figure appears
  anywhere in the report, and none should be inferred. The post-quantum
  analysis depends on no measurement at all.

## Licence

Models, code and documentation: see `LICENSE`.
