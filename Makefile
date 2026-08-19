# WireGuard-Verified -- unified entry point.
#
# Targets are grouped by what they need:
#   no dependencies beyond Python 3 : check figures tables wire-doc
#   LaTeX                           : report
#   ProVerif and Tamarin            : verify verify-proverif verify-tamarin
#
# Run `make doctor` first; it reports exactly which group is available.

PY      ?= python3
PV      ?= proverif
TAMARIN ?= tamarin-prover

# Wall-clock budget and address-space cap for every verifier invocation.
#
# The cap matters more than its value: without one a runaway query drags the
# whole machine into swap and produces a run that is slow, irreproducible and
# hostile to anything else running.  With one, a query either finishes within
# budget or fails deterministically -- which is a reportable outcome.
#
# Both are applied by scripts/runner.py, not by `timeout` and `ulimit -v`.
# `timeout` is GNU coreutils and absent on macOS; `ulimit -v` sets RLIMIT_AS,
# which Darwin accepts and then ignores.  Using either would have made every
# query on macOS record a false non-termination.  See scripts/runner.py.
MEM_KB  ?= 2800000
TIMEOUT ?= 300

RUNNER  := $(PY) scripts/runner.py --timeout $(TIMEOUT) --mem-kb $(MEM_KB)

PVLIBS  := -lib lib/primitives -lib lib/wireguard_core
PVDIR   := models/proverif
PVQ     := 20_secrecy 21_forward_secrecy 22_pq_forward_secrecy 23_pq_fs_nopsk \
           24a_aliveness 24b_agreement 24c_inj_agreement \
           25a_kci_commit 25b_kci_complete
PVKEM   := pq/30_kem_psk_ideal pq/31_kem_psk_reencap
TAMLEM  := executable session_key_secrecy forward_secrecy agreement_responder \
           kci_responder_commit kci_responder_complete

.PHONY: all everything install doctor check figures tables wire-doc report \
        summary verify verify-proverif verify-tamarin clean distclean help

# Introspection: `make print-PVQ` echoes one variable.  scripts/run_models.sh
# reads the query lists through this instead of keeping a second copy of them.
# Two copies of a list is one copy too many -- the day someone adds a model,
# whichever copy they miss keeps passing while silently proving less.
print-%:
	@echo "$($*)"

help:
	@echo "ONE COMMAND DOES EVERYTHING"
	@echo "  bash run.sh          install what is missing, then run the pipeline"
	@echo ""
	@echo "OR THE TWO HALVES SEPARATELY"
	@echo "  make install         install ProVerif, Tamarin and LaTeX (idempotent)"
	@echo "  make everything      run the whole pipeline end to end (~9 min)"
	@echo ""
	@echo "INDIVIDUAL STEPS (all still available)"
	@echo "  make doctor          environment self-check"
	@echo "  make check           layout, model and coverage checks (Python only)"
	@echo "  make figures         SVG and TikZ figures (Python only)"
	@echo "  make tables          result tables from results/results.json"
	@echo "  make wire-doc        regenerate docs/wire-to-model.md from tools/wire.py"
	@echo "  make report          compile the IEEE-format report (needs LaTeX)"
	@echo "  make verify          both model suites, then check expectations"
	@echo "  make verify-proverif ProVerif queries only (~7 min)"
	@echo "  make verify-tamarin  Tamarin lemmas only (~40 s)"
	@echo "  make summary         print the headline results"
	@echo "  make all             check + figures + tables + report (no verifiers)"
	@echo "  make clean           remove build intermediates"
	@echo "  make distclean       also remove generated results"

all: check figures tables report

# --- Installation ----------------------------------------------------------
# Idempotent: every step checks first and skips what is already present.
install:
	@bash scripts/bootstrap.sh

# --- The full pipeline -----------------------------------------------------
# Runs to completion even when a verifier is absent: the static half still
# produces figures, tables and the report, and the summary says what is
# missing.  About nine minutes with both verifiers installed.
everything:
	@echo ""
	@echo "=== 1/5  environment ==============================================="
	@$(MAKE) --no-print-directory doctor
	@echo ""
	@echo "=== 2/5  static checks ============================================="
	@$(MAKE) --no-print-directory check
	@echo ""
	@echo "=== 3/5  verification =============================================="
	@if command -v $(PV) >/dev/null 2>&1 || command -v $(TAMARIN) >/dev/null 2>&1; then \
	   $(MAKE) --no-print-directory verify || \
	     echo "  (see results/raw/ for the detail of any mismatch)"; \
	 else \
	   echo "  no verifier on PATH -- keeping the shipped results/"; \
	   echo "  run 'make install' to add ProVerif and Tamarin"; \
	   $(PY) scripts/collect_results.py; \
	 fi
	@echo ""
	@echo "=== 4/5  figures and tables ========================================"
	@$(MAKE) --no-print-directory figures
	@$(MAKE) --no-print-directory tables
	@echo ""
	@echo "=== 5/5  report ===================================================="
	@if command -v latexmk >/dev/null 2>&1; then $(MAKE) --no-print-directory report; \
	 else echo "  latexmk not found -- no docs/report.pdf produced"; \
	      echo "  install a TeX distribution, then: make report"; fi
	@$(PY) scripts/summary.py

summary:
	@$(PY) scripts/summary.py

doctor:
	@$(PY) scripts/doctor.py

# --- Static checks: no external tool required ------------------------------
check:
	@$(PY) tools/wire.py >/dev/null && echo "  wire layout      ok"
	@$(PY) scripts/verify_wire_table.py
	@$(PY) scripts/lint_models.py
	@$(PY) scripts/check_coverage.py

figures:
	@$(PY) tools/figures.py

# docs/wire-to-model.md is generated from tools/wire.py, so it is regenerated
# alongside every other derived artifact rather than drifting quietly.
wire-doc:
	@$(PY) scripts/gen_wire_doc.py

tables: wire-doc
	@$(PY) scripts/collect_results.py
	@$(PY) scripts/render_tables.py >/dev/null && echo "  tables rendered"
	@$(PY) scripts/sync_readme.py

# --- Report ----------------------------------------------------------------
# TEXINPUTS/BSTINPUTS put report/vendor first so the vendored IEEEtran.cls and
# IEEEtran.bst are used even where a system-wide copy exists.  That is what
# makes `make report` work on a plain BasicTeX with no privileged install: the
# previous arrangement depended on `sudo tlmgr install ieeetran`, which fails
# quietly on an out-of-date tlmgr repository and left the shipped PDF in place
# while printing a one-line failure nobody had to act on.  The trailing colon
# keeps the default search path after ours.  See report/vendor/README.md.
#
# latexmk resolves cross-references and the bibliography by re-running as
# needed, but on a clean tree the first pdflatex has no .aux to work from, so
# bibtex has nothing to read and citations would render as [?].  Running
# latexmk twice guarantees a settled document whatever state the tree was in.
#
# A failed compilation is an error, not a note: the target exits non-zero and
# prints the first real LaTeX error, because a build that says "failed" in
# passing is a build whose output nobody checks.
report: figures tables
	@cd report && \
	  TEXINPUTS="./vendor:$$TEXINPUTS" BSTINPUTS="./vendor:$$BSTINPUTS" \
	    latexmk -pdf -interaction=nonstopmode main.tex >/dev/null 2>&1; \
	  TEXINPUTS="./vendor:$$TEXINPUTS" BSTINPUTS="./vendor:$$BSTINPUTS" \
	    latexmk -pdf -interaction=nonstopmode main.tex >/dev/null 2>&1; \
	  if [ -f main.pdf ]; then \
	    cp main.pdf ../docs/report.pdf; \
	    echo "  docs/report.pdf written"; \
	    if grep -qE 'Reference .* undefined|Citation .* undefined' main.log 2>/dev/null; then \
	      echo "  report: unresolved references remain -- see report/main.log"; \
	    fi; \
	  else \
	    echo "  report: COMPILATION FAILED"; \
	    grep -m3 -A2 '^!' main.log 2>/dev/null | sed 's/^/    /' || true; \
	    echo "    full log: report/main.log"; \
	    exit 1; \
	  fi

# --- Verification ----------------------------------------------------------
# One query per invocation with a clean heap.  Proving everything in a single
# process lets one divergent query take the whole suite down with it.
#
# Each suite is guarded on its own tool rather than on "either tool present".
# Running the Tamarin loop without Tamarin installed would overwrite six good
# tamarin_*.out files with a shell error and silently destroy the shipped
# results, which is exactly the kind of loss a reader cannot detect.
verify: verify-proverif verify-tamarin
	@$(PY) scripts/collect_results.py
	@$(PY) scripts/check_expectations.py

verify-proverif:
	@if ! command -v $(PV) >/dev/null 2>&1; then \
	  echo "  proverif not on PATH -- skipping (shipped results kept)"; \
	  echo "  if it is installed via opam, run:  eval \"\$$(opam env)\""; \
	else \
	  mkdir -p results/raw; \
	  for q in $(PVQ); do \
	    $(RUNNER) --label "proverif $$q" --cwd $(PVDIR) \
	      --out results/raw/$$q.out -- $(PV) $(PVLIBS) $$q.pv; \
	  done; \
	  for q in $(PVKEM); do \
	    n=$$(basename $$q); \
	    $(RUNNER) --label "proverif $$n" --cwd $(PVDIR) \
	      --out results/raw/$$n.out -- $(PV) -lib lib/primitives -lib lib/kem $$q.pv; \
	  done; \
	fi

verify-tamarin:
	@if ! command -v $(TAMARIN) >/dev/null 2>&1; then \
	  echo "  tamarin-prover not on PATH -- skipping (shipped results kept)"; \
	  echo "  install with:  brew trust tamarin-prover/tap"; \
	  echo "                 brew install tamarin-prover/tap/tamarin-prover"; \
	else \
	  mkdir -p results/raw; \
	  for l in $(TAMLEM); do \
	    $(RUNNER) --label "tamarin  $$l" --cwd models/tamarin \
	      --out results/raw/tamarin_$$l.out -- \
	      $(TAMARIN) --prove=$$l --derivcheck-timeout=0 40_wireguard_state.spthy; \
	  done; \
	fi

clean:
	@cd report && latexmk -C >/dev/null 2>&1 || true
	@rm -rf report/*.aux report/*.log report/*.out report/*.bbl report/*.blg
	@find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "  cleaned"

distclean: clean
	@rm -rf results/raw/*.out results/results.json
	@echo "  removed generated results (re-create with make verify)"
