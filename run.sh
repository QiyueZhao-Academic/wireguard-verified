#!/usr/bin/env bash
# WireGuard-Verified -- one command, from a fresh machine to a finished result
# set, with its figures and tables.
#
#   bash run.sh                install what is missing, then run everything
#   bash run.sh --check        environment report only, change nothing
#   bash run.sh --install      install dependencies only
#   bash run.sh --run          run the pipeline only, install nothing
#
# Every step is also available on its own; see `make help`.

# Deliberately not `set -u`.  macOS ships bash 3.2, where expanding an empty
# array under `set -u` -- "${ARGS[@]}" with ARGS=() -- aborts with "unbound
# variable" instead of expanding to nothing.  bash 4.4 fixed this, but macOS
# will not ship bash 4 for licensing reasons, so the shell this script actually
# runs under is the broken one.  `set -o pipefail` keeps the part that matters.
set -o pipefail

# Resolve the repository root from the script's own location, so the script
# works when invoked by absolute path from any directory:
#     bash ~/wg-verified/wireguard-verified/run.sh
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
ROOT="$(pwd)"

BOLD=$'\033[1m'; DIM=$'\033[2m'; RST=$'\033[0m'

DO_INSTALL=1; DO_RUN=1; DO_CHECK=0
for a in "$@"; do
  case "$a" in
    --check)      DO_CHECK=1; DO_INSTALL=0; DO_RUN=0 ;;
    --install)    DO_RUN=0 ;;
    --run|--no-install) DO_INSTALL=0 ;;
    -h|--help)    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $a" >&2
       echo "try: bash run.sh --help" >&2; exit 2 ;;
  esac
done

# --- Python is the floor ---------------------------------------------------
# Without it not even the static half runs, so fail here with a usable message
# rather than several screens later inside a make recipe.
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found." >&2
  echo "On macOS:  xcode-select --install    (or: brew install python@3.12)" >&2
  exit 1
fi

# --- opam puts ProVerif on PATH only after its environment is loaded -------
# The installer runs `opam init` non-interactively and so does not touch the
# shell profile.  Loading the environment here means the user never has to
# remember `eval "$(opam env)"` before running this script.
load_opam_env() {
  if command -v opam >/dev/null 2>&1; then
    eval "$(opam env 2>/dev/null)" 2>/dev/null || true
  fi
}
load_opam_env

if [ "$DO_CHECK" -eq 1 ]; then
  exec make --no-print-directory doctor
fi

start=$(date +%s)

if [ "$DO_INSTALL" -eq 1 ]; then
  bash scripts/bootstrap.sh
  # bootstrap runs in its own shell, so anything it added to PATH -- the opam
  # switch in particular -- has to be picked up again here.
  load_opam_env
  [ -d /usr/libexec ] && eval "$(/usr/libexec/path_helper 2>/dev/null)" 2>/dev/null || true
fi

rc=0
if [ "$DO_RUN" -eq 1 ]; then
  make everything
  rc=$?
fi

elapsed=$(( $(date +%s) - start ))
printf '\n%sTotal elapsed: %s min %s s%s\n' \
  "$DIM" "$(( elapsed / 60 ))" "$(( elapsed % 60 ))" "$RST"

if [ "$DO_RUN" -eq 1 ]; then
  echo
  if [ $rc -eq 0 ]; then
    printf '%sDone.%s  Results: %s/results/results.json\n' "$BOLD" "$RST" "$ROOT"
    printf '       Figures: %s/results/figures/\n' "$ROOT"
  else
    printf '%sFinished with a mismatch.%s  Inspect: %s/results/raw/\n' \
      "$BOLD" "$RST" "$ROOT"
    echo "A mismatch means an observed verdict differs from expectations.yaml."
    echo "See RUNBOOK.md, section 'When something does not match'."
  fi
fi
exit $rc
