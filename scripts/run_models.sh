#!/usr/bin/env bash
# Run the model suite outside make, or run a single query.
#
#   bash scripts/run_models.sh                  everything
#   bash scripts/run_models.sh 20_secrecy       one ProVerif query
#   bash scripts/run_models.sh executable       one Tamarin lemma
#
# Budgets are the Makefile's and are overridden the same way:
#   TIMEOUT=600 MEM_KB=4000000 bash scripts/run_models.sh
#
# The query lists live in the Makefile and are read from it here rather than
# repeated.  Two copies of a list is one copy too many: the day someone adds a
# model, whichever copy they miss keeps passing while silently proving less.
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

TIMEOUT="${TIMEOUT:-300}"
MEM_KB="${MEM_KB:-2800000}"
WANT="${1:-}"

# Read a variable's value from the Makefile through its print-% accessor.
makevar() { make --no-print-directory "print-$1"; }

PVQ="$(makevar PVQ)"
PVKEM="$(makevar PVKEM)"
TAMLEM="$(makevar TAMLEM)"

if [ -z "$PVQ" ] || [ -z "$TAMLEM" ]; then
  echo "could not read the query lists from the Makefile." >&2
  echo "Run this from a complete checkout: bash scripts/run_models.sh" >&2
  exit 1
fi

runner() { python3 scripts/runner.py --timeout "$TIMEOUT" --mem-kb "$MEM_KB" "$@"; }

matched=0
for q in $PVQ; do
  [ -n "$WANT" ] && [ "$WANT" != "$q" ] && continue
  matched=1
  runner --label "proverif $q" --cwd models/proverif \
    --out "results/raw/$q.out" -- \
    proverif -lib lib/primitives -lib lib/wireguard_core "$q.pv"
done

for q in $PVKEM; do
  n="$(basename "$q")"
  [ -n "$WANT" ] && [ "$WANT" != "$n" ] && [ "$WANT" != "$q" ] && continue
  matched=1
  runner --label "proverif $n" --cwd models/proverif \
    --out "results/raw/$n.out" -- \
    proverif -lib lib/primitives -lib lib/kem "$q.pv"
done

for l in $TAMLEM; do
  [ -n "$WANT" ] && [ "$WANT" != "$l" ] && continue
  matched=1
  runner --label "tamarin  $l" --cwd models/tamarin \
    --out "results/raw/tamarin_$l.out" -- \
    tamarin-prover "--prove=$l" --derivcheck-timeout=0 40_wireguard_state.spthy
done

if [ -n "$WANT" ] && [ "$matched" -eq 0 ]; then
  echo "no query or lemma named '$WANT'." >&2
  echo "ProVerif: $PVQ $PVKEM" >&2
  echo "Tamarin:  $TAMLEM" >&2
  exit 2
fi

python3 scripts/collect_results.py
python3 scripts/check_expectations.py
