"""Run one verifier invocation under a wall-clock budget, portably.

Why this file exists
--------------------
The obvious way to bound a verifier run from a Makefile is

    ulimit -v $MEM_KB ; timeout $SECONDS proverif model.pv > out 2>&1

and neither half of that survives contact with macOS.

`timeout` is GNU coreutils.  macOS does not ship it.  The shell therefore
writes "timeout: command not found" into the redirect -- that is, into the
query's own result file -- and exits.  collect_results.py then reads a file
with no RESULT line in it and records the query as `nonterminating`, which is
a legitimate outcome and so raises no alarm.  Every query in the suite is
filed as a budget exhaustion, check_expectations reports twelve mismatches,
and nothing anywhere in the output mentions the missing command.  A silent
wrong answer is worse than a loud failure, and this was one.

`ulimit -v` sets RLIMIT_AS.  Darwin defines the constant but does not enforce
the limit, so the cap is honoured on Linux and advisory on macOS.  Rather than
pretend otherwise, the runner records which of the two it got in the output
file, so a result carries its own provenance.

Doing both from Python needs nothing that is not already required: the
repository's floor is a bare Python 3, and this file imports only the standard
library.

Usage
    python3 scripts/runner.py --label 20_secrecy --out results/raw/20_secrecy.out \
        --cwd models/proverif --timeout 300 --mem-kb 2800000 \
        -- proverif -lib lib/primitives 20_secrecy.pv
"""

from __future__ import annotations

import argparse
import os
import platform
import resource
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

# Written into the output file when the runner kills a process.  collect_results
# looks for this exact prefix, so the two must be changed together; the constant
# is defined here and imported there rather than being spelled twice.
KILL_MARKER = "[runner] killed:"

# Wall-clock cost of the invocation, appended to the output file so that the
# figure survives the terminal session that produced it.  The report quotes
# per-query timings, and a timing that lives only in scrollback cannot be
# re-derived by a reader -- which is how a paper ends up carrying numbers from
# a run nobody can reproduce.  collect_results.py reads this prefix into the
# `elapsed_s` field of results/results.json; the two must change together.
ELAPSED_MARKER = "[runner] elapsed:"

# Exit status used when the verifier binary is not installed.  Distinct from
# any status the verifier itself can return, so the Makefile can tell "tool
# absent" apart from "tool ran and disagreed".
EXIT_TOOL_MISSING = 127


def _limit_address_space(mem_kb: int):
    """Return a preexec function capping RLIMIT_AS, or None if unavailable.

    Returns None on Darwin: the limit is accepted there and then ignored by the
    kernel, and a cap that silently does nothing is worse than no cap, because
    it invites the reader to believe the run was bounded when it was not.  The
    wall-clock budget is the real protection on macOS.
    """
    if platform.system() == "Darwin" or mem_kb <= 0:
        return None

    def _apply():
        want = mem_kb * 1024
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        # Never raise an existing limit, and never exceed the hard ceiling.
        ceiling = want if hard == resource.RLIM_INFINITY else min(want, hard)
        resource.setrlimit(resource.RLIMIT_AS, (ceiling, hard))

    return _apply


def _memory_note(mem_kb: int) -> str:
    if mem_kb <= 0:
        return "address-space cap: none requested"
    if platform.system() == "Darwin":
        return (f"address-space cap: {mem_kb} kB requested, NOT ENFORCED "
                "(Darwin does not honour RLIMIT_AS); the wall-clock budget "
                "is the effective bound on this platform")
    return f"address-space cap: {mem_kb} kB (RLIMIT_AS, enforced)"


def run(label: str, out: Path, cwd: Path, timeout: int, mem_kb: int,
        cmd: list[str]) -> int:
    """Run `cmd`, capturing everything into `out`. Returns a process status."""
    if shutil.which(cmd[0]) is None:
        print(f"  {label:<32} skipped -- {cmd[0]} is not on PATH")
        return EXIT_TOOL_MISSING

    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()

    # start_new_session puts the child in its own process group.  Verifiers
    # spawn helpers -- Tamarin drives maude as a subprocess -- and killing only
    # the parent on timeout would leave those helpers running and holding
    # memory, which on an 8 GB machine is how one abandoned query poisons every
    # query that follows it.
    with out.open("w", encoding="utf-8", errors="replace") as fh:
        fh.write(f"[runner] {' '.join(cmd)}\n")
        fh.write(f"[runner] wall-clock budget: {timeout} s\n")
        fh.write(f"[runner] {_memory_note(mem_kb)}\n")
        fh.write("[runner] ---- verifier output follows ----\n")
        fh.flush()

        proc = subprocess.Popen(
            cmd, cwd=str(cwd), stdout=fh, stderr=subprocess.STDOUT,
            start_new_session=True, preexec_fn=_limit_address_space(mem_kb),
        )
        try:
            status = proc.wait(timeout=timeout)
            verdict = f"exit {status}"
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            status = None
            verdict = f"budget exhausted at {timeout}s"

    elapsed = int(time.time() - started)

    # Appended after the handle is closed so these lines are the last words of
    # the file whatever the verifier left in its buffers.  The kill marker must
    # come first: collect_results.py distinguishes an honest budget exhaustion
    # from a broken run by what the output ends with, and the elapsed line is
    # written for every invocation, successful or not.
    with out.open("a", encoding="utf-8") as fh:
        if status is None:
            fh.write(f"\n{KILL_MARKER} wall-clock budget of {timeout} s "
                     f"exhausted; recorded as non-terminating\n")
        fh.write(f"{ELAPSED_MARKER} {elapsed} s\n")

    print(f"  {label:<32} {elapsed:>4}s  {verdict}")
    return 0 if status in (0, None) else status


def _kill_group(proc: subprocess.Popen) -> None:
    """Terminate the child's whole process group, politely then not."""
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        return
    for sig, grace in ((signal.SIGTERM, 3.0), (signal.SIGKILL, 2.0)):
        try:
            os.killpg(pgid, sig)
        except OSError:
            return
        try:
            proc.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            continue


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--label", required=True, help="name shown in the progress line")
    ap.add_argument("--out", required=True, type=Path, help="file to capture output into")
    ap.add_argument("--cwd", default=".", type=Path, help="directory to run in")
    ap.add_argument("--timeout", type=int, default=300, help="wall-clock budget, seconds")
    ap.add_argument("--mem-kb", type=int, default=0, help="address-space cap, kB")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="-- followed by the command to run")
    args = ap.parse_args()

    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        ap.error("no command given; put it after --")

    root = Path(__file__).resolve().parent.parent
    cwd = args.cwd if args.cwd.is_absolute() else root / args.cwd
    out = args.out if args.out.is_absolute() else root / args.out
    return run(args.label, out, cwd, args.timeout, args.mem_kb, cmd)


if __name__ == "__main__":
    sys.exit(main())
