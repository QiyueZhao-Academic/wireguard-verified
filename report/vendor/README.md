# Vendored LaTeX class and bibliography style

This directory holds two unmodified files from the IEEEtran distribution:

| File           | Version | Purpose                                  |
|----------------|---------|------------------------------------------|
| `IEEEtran.cls` | V1.8b   | the IEEE conference document class       |
| `IEEEtran.bst` | V1.14   | the matching bibliography style          |

## Why they are here

`make report` used to depend on `IEEEtran.cls` being installed system-wide,
normally through `sudo tlmgr install ieeetran`. That install step is the one
part of the toolchain that fails quietly: on a BasicTeX installation whose
`tlmgr` repository is out of date, `tlmgr install ieeetran` exits non-zero,
`bootstrap.sh` records it as "already present or not applicable", and the
first sign of trouble is `report: compilation failed` several minutes later.

A document class is a text file. Shipping it removes the failure mode
entirely: `make report` now works on any TeX installation that provides
pdflatex, latexmk and the standard `booktabs` / `pgf` / `hyperref` packages,
with no privileged install and no network access.

The report build puts this directory first on `TEXINPUTS` and `BSTINPUTS`, so
this copy is used even when a system-wide IEEEtran is also present. That is
deliberate: the report then renders identically on every machine, which is
what an artifact should do.

## Licence

Both files are distributed under the LaTeX Project Public License (LPPL)
version 1.3, which permits redistribution of unmodified copies. Neither file
has been modified; all contribution notices and credits are retained inside
them. `IEEEtran.cls` is maintained by Michael Shell
(<http://www.michaelshell.org/tex/ieeetran/>, <http://www.ctan.org/pkg/ieeetran>).

Nothing else in this repository is third-party code.
