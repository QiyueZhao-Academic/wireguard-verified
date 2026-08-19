#!/usr/bin/env bash
# Install everything the full pipeline needs.
#
# Idempotent: every step checks first and skips what is already present, so
# re-running this is cheap and safe.  Nothing is removed or downgraded.
#
# Steps that need administrator rights (only the LaTeX package install) will
# prompt for your password.  Pass --no-latex to skip that step entirely.
#
#   bash scripts/bootstrap.sh              install everything
#   bash scripts/bootstrap.sh --no-latex   skip the LaTeX packages
#   bash scripts/bootstrap.sh --dry-run    print what would happen, change nothing

# `set -u` is deliberately absent: macOS ships bash 3.2, where expanding an
# empty array aborts the script.  See the same note in run.sh.
set -o pipefail

DRY=0; DO_LATEX=1
for a in "$@"; do
  case "$a" in
    --dry-run)  DRY=1 ;;
    --no-latex) DO_LATEX=0 ;;
    -h|--help)  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

BOLD=$'\033[1m'; DIM=$'\033[2m'; RST=$'\033[0m'
step() { printf '\n%s==> %s%s\n' "$BOLD" "$1" "$RST"; }
skip() { printf '    %salready present: %s%s\n' "$DIM" "$1" "$RST"; }
run()  { if [ "$DRY" -eq 1 ]; then printf '    would run: %s\n' "$*"
         else printf '    %s\n' "$*"; "$@"; fi; }
note() { printf '    %s\n' "$1"; }

# Failures are accumulated in a plain space-separated string rather than an
# array.  bash 3.2 cannot expand an empty array safely, and the summary at the
# end has to work in the common case where nothing failed at all.
FAILED=""
fail() { FAILED="$FAILED $1"; }

OS="$(uname -s)"

# --------------------------------------------------------------------------
step "Checking the platform"
note "$OS $(uname -m)"
if [ "$OS" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
  if [ "$(sysctl -in sysctl.proc_translated 2>/dev/null || echo 0)" = "1" ]; then
    echo "    ERROR: this shell is running under Rosetta." >&2
    echo "    Translation makes long proofs non-deterministic near the timeout" >&2
    echo "    boundary, which destroys reproducibility. Open a native arm64" >&2
    echo "    Terminal and re-run." >&2
    exit 1
  fi
  note "native arm64, not translated"
fi

# --------------------------------------------------------------------------
step "Python 3"
if command -v python3 >/dev/null 2>&1; then
  skip "$(python3 -V 2>&1)"
  note "nothing else needed -- this repository imports no third-party package"
else
  if [ "$OS" = "Darwin" ]; then run brew install python@3.12 || fail python3
  else note "install python3 with your package manager"; fail python3; fi
fi

# --------------------------------------------------------------------------
step "Homebrew"
if [ "$OS" = "Darwin" ]; then
  if command -v brew >/dev/null 2>&1; then
    skip "brew $(brew --version 2>/dev/null | head -1 | awk '{print $2}')"
  else
    note "Homebrew is required. Install it from https://brew.sh then re-run."
    fail homebrew
  fi
else
  note "not macOS -- skipping"
fi

# --------------------------------------------------------------------------
step "Tamarin 1.12 (+ Maude)"
if command -v tamarin-prover >/dev/null 2>&1; then
  skip "$(tamarin-prover --version 2>&1 | grep -o 'tamarin-prover [0-9.]*' | head -1)"
elif [ "$OS" = "Darwin" ]; then
  if command -v brew >/dev/null 2>&1; then
    # Homebrew 6 refuses to load formulae from a third-party tap until the tap
    # is explicitly trusted, and it refuses at the point where it resolves the
    # tap's *dependencies* -- so the install aborts on tamarin's `maude`
    # formula with a message about maude, not about tamarin.  Trusting the tap
    # up front is what makes the install work; on older Homebrew the
    # subcommand does not exist and the failure is harmless, hence `|| true`.
    note "trusting the tamarin tap (required by Homebrew 6)"
    if [ "$DRY" -eq 1 ]; then
      note "would run: brew tap tamarin-prover/tap"
      note "would run: brew trust tamarin-prover/tap"
    else
      brew tap tamarin-prover/tap >/dev/null 2>&1 || true
      brew trust tamarin-prover/tap >/dev/null 2>&1 || true
    fi
    # A native arm64 bottle exists, so this is a download, not a build.
    # Never build Tamarin from source on 8 GB: GHC linking spikes to several GB.
    run brew install tamarin-prover/tap/tamarin-prover || fail tamarin-prover
  else
    fail tamarin-prover
  fi
else
  note "download a release binary from"
  note "https://github.com/tamarin-prover/tamarin-prover/releases"
  note "and install maude 3.1+ from your package manager"
  fail tamarin-prover
fi

if command -v tamarin-prover >/dev/null 2>&1 && ! command -v maude >/dev/null 2>&1; then
  if [ "$OS" = "Darwin" ]; then run brew install maude || fail maude
  else note "install maude 3.1+"; fail maude; fi
fi

# Tamarin 1.12.0 accepts a fixed list of Maude versions and prints a warning
# for anything else.  The warning is benign -- the proofs still run and the
# verdicts are still recorded -- but a reader who sees it in the raw output
# deserves to have been told to expect it.
if command -v maude >/dev/null 2>&1; then
  MAUDE_V="$(maude --version 2>/dev/null | head -1)"
  case "$MAUDE_V" in
    2.7.1|3.0|3.1|3.2.1|3.2.2|3.3|3.3.1|3.4|3.5|3.5.1) note "maude $MAUDE_V (supported)" ;;
    "") : ;;
    *) note "maude $MAUDE_V -- Tamarin will print an 'unsupported version'"
       note "warning. It is benign; the proofs run and the verdicts are valid." ;;
  esac
fi

# --------------------------------------------------------------------------
step "ProVerif 2.05 (via opam)"
# There is no `brew install proverif`; the formula does not exist.
if command -v proverif >/dev/null 2>&1; then
  skip "$(proverif -help 2>&1 | head -1 | cut -c1-40)"
else
  if ! command -v opam >/dev/null 2>&1; then
    if [ "$OS" = "Darwin" ]; then run brew install opam || fail opam
    else note "install opam with your package manager"; fail opam; fi
  else
    skip "opam $(opam --version 2>/dev/null)"
  fi
  if command -v opam >/dev/null 2>&1; then
    [ -d "$HOME/.opam" ] || run opam init --bare -y --disable-sandboxing
    eval "$(opam env 2>/dev/null)" 2>/dev/null || true
    if ! opam switch list 2>/dev/null | grep -qE '4\.1[0-9]|5\.[0-9]'; then
      note "creating an OCaml switch (a few minutes, one time only)"
      run opam switch create 4.14.1 || fail "opam-switch"
    fi
    eval "$(opam env 2>/dev/null)" 2>/dev/null || true
    # opam will offer to install ProVerif's system dependencies through brew.
    # That pull is large -- gtk+2 and roughly thirty transitive formulae -- and
    # is needed only by proverif_interact, the graphical trace browser. The
    # command-line binary this repository uses does not need any of it, but the
    # opam package declares lablgtk as a hard dependency, so there is no
    # supported way to decline it.
    note "opam may ask to install system dependencies via brew; answer 1"
    run opam install -y proverif || fail proverif
    eval "$(opam env 2>/dev/null)" 2>/dev/null || true
  fi
  if command -v proverif >/dev/null 2>&1; then
    note "ProVerif installed"
  else
    note "if a new shell cannot find proverif, run:  eval \"\$(opam env)\""
    note "run.sh does this for you automatically."
  fi
fi

# --------------------------------------------------------------------------
step "LaTeX packages for the report"
if [ "$DO_LATEX" -eq 0 ]; then
  note "skipped (--no-latex); 'make report' will be unavailable"
elif ! command -v kpsewhich >/dev/null 2>&1; then
  if [ "$OS" = "Darwin" ]; then
    note "no TeX installation found"
    run brew install --cask basictex || fail basictex
    note "open a new Terminal (or run: eval \"\$(/usr/libexec/path_helper)\")"
    note "then re-run this script to add the packages"
  else
    note "install TeX Live with your package manager"; fail latex
  fi
elif kpsewhich booktabs.sty >/dev/null 2>&1 && kpsewhich tikz.sty >/dev/null 2>&1; then
  # IEEEtran is deliberately not checked for: it is bundled in report/vendor
  # and put first on TEXINPUTS by the Makefile.  Requiring it here is what
  # made this step look like it had succeeded when tlmgr had in fact failed.
  skip "LaTeX packages for the report (IEEEtran is bundled)"
else
  note "adding packages -- this asks for your macOS login password"
  note "(nothing is displayed while you type; that is normal)"
  note "to skip this step entirely, re-run with --no-latex"
  # Installed one at a time: some are already present in a full TeX Live and
  # tlmgr aborts the whole batch if any single name is unknown there.
  #
  # `ieeetran` is deliberately absent from this list.  It used to be the first
  # entry, and on a BasicTeX whose tlmgr repository is out of date the install
  # exits non-zero, gets reported below as "already present or not applicable",
  # and the first sign of trouble is a failed `make report` several minutes
  # later.  The class is bundled in report/vendor/ instead, so this loop only
  # has to cover packages a normal TeX installation already ships.
  for p in latexmk booktabs pgf xcolor microtype cite hyperref \
           amsmath ec collection-fontsrecommended; do
    if [ "$DRY" -eq 1 ]; then echo "    would run: sudo tlmgr install $p"
    else sudo tlmgr install "$p" >/dev/null 2>&1 \
           && echo "    + $p" \
           || echo "    . $p (already present or not applicable)"; fi
  done
fi

# --------------------------------------------------------------------------
step "Result"
if [ -z "$FAILED" ]; then
  echo "    all dependencies satisfied"
  echo
  echo "    next:  make everything      (full pipeline, about 9 minutes)"
  echo "    or:    make doctor          (see exactly what is available)"
  exit 0
else
  echo "    could not install:$FAILED"
  echo "    See RUNBOOK.md for the manual route for each."
  echo "    Targets not needing these still work: make check, make figures, make tables"
  exit 1
fi
