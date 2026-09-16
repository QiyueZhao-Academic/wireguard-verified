"""Environment self-check.

Reports what is present, what is missing, and what each missing item costs
you, so that an environment problem is never misdiagnosed as a model problem.
Exits 0 even when tools are absent: not having ProVerif installed is a fact
about the machine, not a failure of the repository.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OK, WARN, BAD = "  ok  ", " miss ", " bad  "

# Maude releases Tamarin 1.12 accepts without complaint.
TAMARIN_MAUDE_OK = {"2.7.1", "3.0", "3.1", "3.2.1", "3.2.2",
                    "3.3", "3.3.1", "3.4", "3.5", "3.5.1"}


def _run(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        return (r.stdout + r.stderr).strip()
    except Exception:
        return None


def line(status: str, name: str, detail: str = "") -> None:
    """Print one check. An empty status renders as a continuation line."""
    if not status:
        print(f"{'':<8} {'':<22} {detail}")
    else:
        print(f"[{status}] {name:<22} {detail}")


def main() -> int:
    print("wireguard-verified :: environment check\n")

    # --- platform ---------------------------------------------------------
    mach, sysname = platform.machine(), platform.system()
    line(OK, "platform", f"{sysname} {mach} python {platform.python_version()}")
    if sysname == "Darwin" and mach == "arm64":
        # Rosetta would make long-running proofs non-deterministic near the
        # timeout boundary, which destroys reproducibility.
        tr = _run(["sysctl", "-in", "sysctl.proc_translated"])
        if tr == "1":
            line(BAD, "translation", "running under Rosetta -- use a native arm64 shell")
        else:
            line(OK, "translation", "native arm64, not translated")

    if sys.version_info < (3, 9):
        line(BAD, "python", "3.9+ required")
        return 1

    # --- memory headroom --------------------------------------------------
    # The verifier budget is 2.8 GB; report whether that is realistic here.
    free_mb = None
    if sysname == "Darwin":
        out = _run(["vm_stat"])
        if out:
            try:
                pg = 16384
                free = sum(int(l.split(":")[1].strip().rstrip("."))
                           for l in out.splitlines()
                           if l.startswith(("Pages free", "Pages inactive")))
                free_mb = free * pg // (1024 * 1024)
            except Exception:
                pass
    else:
        try:
            for l in Path("/proc/meminfo").read_text().splitlines():
                if l.startswith("MemAvailable"):
                    free_mb = int(l.split()[1]) // 1024
        except Exception:
            pass
    if free_mb is not None:
        s = OK if free_mb >= 2800 else WARN
        line(s, "memory available", f"{free_mb} MB (suite budget: 2800 MB)")
        if free_mb < 2800:
            line("", "", "close other applications, or lower MEM_KB in the Makefile")

    # State plainly which of the two budgets actually binds here.  Darwin
    # accepts RLIMIT_AS and then ignores it, so on macOS the wall-clock budget
    # is the only real bound -- and a reader comparing runs across platforms
    # needs to know that rather than infer it.
    if sysname == "Darwin":
        line(WARN, "address-space cap",
             "not enforceable on macOS -- the wall-clock budget is the bound")
    else:
        line(OK, "address-space cap", "RLIMIT_AS enforced (MEM_KB in the Makefile)")

    # --- tools ------------------------------------------------------------
    print()
    pv = shutil.which("proverif")
    if pv:
        v = (_run(["proverif", "-help"]) or "").splitlines()[0][:60]
        line(OK, "proverif", v)
    else:
        line(WARN, "proverif", "not found -- `make verify` unavailable")
        line("", "", "install with opam; there is no `brew install proverif`")

    tam = shutil.which("tamarin-prover")
    if tam:
        out = _run(["tamarin-prover", "--version"]) or ""
        ver = next((l for l in out.splitlines() if "tamarin-prover 1" in l), "")
        line(OK, "tamarin-prover", ver.strip()[:60])
        if not shutil.which("maude"):
            line(BAD, "maude", "Tamarin needs Maude on PATH -- brew install maude")
        else:
            mv = (_run(["maude", "--version"]) or "").strip().splitlines()
            mv = mv[0].strip() if mv else "?"
            # Tamarin 1.12 accepts a fixed list and warns loudly on anything
            # else.  The warning is benign -- proofs run and verdicts are
            # valid -- but it appears in every raw output file, so a reader who
            # has not been warned reasonably reads it as a problem.
            if mv in TAMARIN_MAUDE_OK:
                line(OK, "maude", mv)
            else:
                line(WARN, "maude", f"{mv} -- outside Tamarin's supported list")
                line("", "", "benign: Tamarin prints a warning, proofs still run")
    else:
        line(WARN, "tamarin-prover", "not found -- Tamarin lemmas unavailable")
        line("", "", "brew trust tamarin-prover/tap")
        line("", "", "brew install tamarin-prover/tap/tamarin-prover")
        line("", "", "(Homebrew 6 refuses untrusted taps; the trust step is required)")

    # --- repository integrity --------------------------------------------
    print()
    need = ["models/proverif/lib/primitives.pvl",
            "models/proverif/lib/wireguard_core.pvl",
            "models/proverif/lib/kem.pvl",
            "models/tamarin/40_wireguard_state.spthy",
            "expectations.yaml", "tools/wire.py",
            "scripts/runner.py", "scripts/yamlite.py",
            "scripts/check_coverage.py"]
    missing = [p for p in need if not (ROOT / p).exists()]
    line(OK if not missing else BAD, "repository files",
         "complete" if not missing else f"missing: {', '.join(missing)}")

    print("\nTargets needing no external tool: make check, make figures, make tables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
