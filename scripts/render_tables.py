"""Render every table the report inputs, plus the numbers its prose quotes.

One source, several outputs.  `results/results.json`, `tools/wire.py`,
`tools/pqcost.py`, `expectations.yaml` and the Makefile's own budget variables
are read here and turned into LaTeX fragments under `report/generated/` and
Markdown fragments under `docs/generated/`.  None of them is ever edited by
hand.

Why facts.tex exists
--------------------
Generating the tables was not enough.  An earlier revision of the report had
correct tables and prose that quoted timings from a run nobody could identify:
the sentences said 47 s and 51 s while the recorded run said 20 s.  Nothing in
the build could notice, because prose is not data.

facts.tex closes that gap.  Every quantity the prose states -- outcome counts,
wall-clock costs, packet sizes, budgets, tool versions -- is emitted here as a
LaTeX macro and referenced by name in the section files.  A number that changes
in results.json therefore changes in the sentence that quotes it, and a number
with no macro is a number the report is not entitled to state.

Usage
    python3 scripts/render_tables.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "results.json"
RAW = ROOT / "results" / "raw"
TEXOUT = ROOT / "report" / "generated"
MDOUT = ROOT / "docs" / "generated"

sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))
import pqcost  # noqa: E402
import wire  # noqa: E402
import yamlite  # noqa: E402

# Mapping from the file a verdict came from to the property identifier used in
# the report.  Kept here rather than in results.json so that the raw data stays
# a faithful record of what the tools printed.
#
# scripts/check_coverage.py reads this dictionary as data and unpacks each
# value as a three-tuple; keep that shape.
PROPERTY = {
    "20_secrecy.out":            ("P1",  "Session-key secrecy",                 "ProVerif"),
    "21_forward_secrecy.out":    ("P3",  "Forward secrecy",                     "ProVerif"),
    "22_pq_forward_secrecy.out": ("P4",  "Post-quantum forward secrecy (psk)",  "ProVerif"),
    "23_pq_fs_nopsk.out":        ("P4c", "  same, psk absent (control)",        "ProVerif"),
    "24a_aliveness.out":         ("P5a", "Agreement, responder to initiator",   "ProVerif"),
    "24b_agreement.out":         ("P5b", "Agreement, initiator to responder",   "ProVerif"),
    "24c_inj_agreement.out":     ("P5c", "Injective agreement / replay (P9)",   "ProVerif"),
    "25a_kci_commit.out":        ("P6a", "KCI, commitment level",               "ProVerif"),
    "25b_kci_complete.out":      ("P6b", "KCI, completion level",               "ProVerif"),
    "30_kem_psk_ideal.out|pskWitness":   ("P12a", "KEM-derived psk secrecy, K-PK binding",  "ProVerif"),
    "31_kem_psk_reencap.out|pskWitness": ("P12b", "  same, binding absent (control)",       "ProVerif"),
    "30_kem_psk_ideal.out|PskResponder": ("P12c", "KEM-derived psk, responder-view soundness", "ProVerif"),
    "tamarin_executable.out":         ("S0",  "Model admits an honest run",     "Tamarin"),
    "tamarin_session_key_secrecy.out":("S1",  "Session-key secrecy",            "Tamarin"),
    "tamarin_forward_secrecy.out":    ("S3",  "Forward secrecy",                "Tamarin"),
    "tamarin_agreement_responder.out":("S5",  "Agreement, no compromise",       "Tamarin"),
    "tamarin_kci_responder_commit.out":  ("S6a","KCI, commitment level",        "Tamarin"),
    "tamarin_kci_responder_complete.out":("S6b","KCI, completion level",        "Tamarin"),
}

SYMBOL_TEX = {"proved": r"\ok", "attack_found": r"\attack",
              "inconclusive": r"\inconcl", "nonterminating": r"\nonterm"}
SYMBOL_MD = {"proved": "proved", "attack_found": "attack found",
             "inconclusive": "inconclusive", "nonterminating": "non-terminating"}

# Weakest-outcome ordering: a file holding several queries is reported by the
# worst verdict any of them produced.
ORDER = {"proved": 0, "inconclusive": 1, "nonterminating": 2, "attack_found": 3}


# ===========================================================================
# Reading the project's own data
# ===========================================================================

def entries() -> list[dict]:
    return json.loads(RESULTS.read_text())["entries"]


def makevar(name: str) -> str:
    """Read one variable out of the Makefile through its `print-%` accessor.

    The wall-clock budget and the address-space cap are declared in exactly one
    place -- the Makefile -- and the report states both.  Reading them back
    means the sentence and the run cannot disagree about what bounded it.
    """
    try:
        r = subprocess.run(["make", "--no-print-directory", f"print-{name}"],
                           cwd=ROOT, capture_output=True, text=True, timeout=20)
        return r.stdout.strip()
    except Exception:
        return ""


def tool_versions() -> dict[str, str]:
    """Version strings for the two verifiers.

    Preferred source is the tool itself; failing that, whatever the recorded
    output happens to carry.  Tamarin prints its version into every proof it
    produces, so a Tamarin figure survives even on a machine where the tool is
    not installed.  ProVerif prints none, so it degrades to a bare name --
    which is honest, and better than naming a version nobody observed.
    """
    out = {"proverif": "ProVerif", "tamarin": "Tamarin"}

    if shutil.which("proverif"):
        try:
            r = subprocess.run(["proverif", "-help"], capture_output=True,
                               text=True, timeout=20)
            m = re.search(r"Proverif\s+([0-9][0-9.a-z]*)", r.stdout + r.stderr, re.I)
            if m:
                out["proverif"] = f"ProVerif~{m.group(1).rstrip('.')}"
        except Exception:
            pass

    ver = ""
    if shutil.which("tamarin-prover"):
        try:
            r = subprocess.run(["tamarin-prover", "--version"],
                               capture_output=True, text=True, timeout=25)
            m = re.search(r"tamarin-prover\s+([0-9][0-9.]*)", r.stdout + r.stderr)
            ver = m.group(1).rstrip(".") if m else ""
        except Exception:
            pass
    if not ver and RAW.is_dir():
        for f in sorted(RAW.glob("tamarin_*.out")):
            m = re.search(r"Tamarin version ([0-9][0-9.]*)",
                          f.read_text(errors="replace"))
            if m:
                ver = m.group(1).rstrip(".")
                break
    if ver:
        out["tamarin"] = f"Tamarin~{ver}"
    return out


def source_cost() -> dict[str, int | None]:
    """Wall-clock seconds per raw output file, None where none was recorded.

    Every query inside one file shares that file's invocation and therefore its
    cost; the alternative -- apportioning the time between the queries -- would
    invent a figure no tool reported.
    """
    cost: dict[str, int | None] = {}
    for e in entries():
        cost.setdefault(e["source"], e.get("elapsed_s"))
    return cost


# ===========================================================================
# The result matrix
# ===========================================================================

def rows() -> list[tuple[str, str, str, str, "int | None"]]:
    """One row per property: (id, description, prover, outcome, seconds)."""
    cost = source_cost()
    agg: dict[str, str] = {}
    for e in entries():
        src = e["source"]
        q = e.get("query") or ""
        # A row keyed "file|substring" selects one specific query inside a
        # file; a row keyed by the file alone aggregates every query in it to
        # its weakest outcome.  The distinction matters where a file holds
        # queries of unequal informativeness -- the KEM models pair a decisive
        # secrecy query with an agreement query ProVerif cannot decide, and
        # collapsing the two would understate the secrecy result.
        for key in PROPERTY:
            if "|" in key:
                f_, sub = key.split("|", 1)
                if f_ == src and sub in q:
                    cur = agg.get(key)
                    if cur is None or ORDER[e["outcome"]] > ORDER[cur]:
                        agg[key] = e["outcome"]
        cur = agg.get(src)
        if cur is None or ORDER[e["outcome"]] > ORDER[cur]:
            agg[src] = e["outcome"]

    out = []
    for key, (pid, desc, tool) in PROPERTY.items():
        if key in agg:
            out.append((pid, desc, tool, agg[key], cost.get(key.split("|", 1)[0])))
    return out


def _secs(s: "int | None") -> str:
    return r"$<$1" if s == 0 else str(s)


def secs_tex(s: "int | None", outcome: str) -> str:
    """Format one wall-clock cell, unit included.

    The unit belongs inside the cell rather than in the column header: a row
    whose cost was never recorded prints `n/r`, and `n/r s` would read as a
    duration.
    """
    if s is None:
        return r"\textit{n/r}"
    # A non-terminating query has no time-to-verdict; what it has is the budget
    # it consumed without producing one, and the two must not read alike.
    if outcome == "nonterminating":
        return rf"{s}\,s$^\dagger$"
    return _secs(s) + r"\,s"


def secs_md(s: "int | None") -> str:
    return "n/r" if s is None else ("<1" if s == 0 else str(s))


def to_tex(rs) -> str:
    L = [r"\begin{tabular}{@{}lllrl@{}}", r"\toprule",
         r"ID & Property & Prover & Cost & Outcome \\",
         r"\midrule"]
    prev = None
    for pid, desc, tool, outcome, secs in rs:
        if prev is not None and tool != prev:
            L.append(r"\midrule")
        prev = tool
        d = desc.replace("  same", r"\quad same")
        L.append(f"{pid} & {d} & {tool} & {secs_tex(secs, outcome)} & "
                 f"{SYMBOL_TEX[outcome]} \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


def to_md(rs) -> str:
    L = ["| ID | Property | Tool | Outcome |", "|---|---|---|---|"]
    for pid, desc, tool, outcome, _ in rs:
        L.append(f"| {pid} | {desc.strip()} | {tool} | {SYMBOL_MD[outcome]} |")
    return "\n".join(L) + "\n"


def cost_md(rs) -> str:
    """Per-property wall-clock cost, for the documentation under docs/."""
    L = ["<!-- Generated by scripts/render_tables.py. Do not edit. -->",
         "",
         "| ID | Property | Tool | Outcome | Wall-clock (s) |",
         "|---|---|---|---|---:|"]
    for pid, desc, tool, outcome, secs in rs:
        L.append(f"| {pid} | {desc.strip()} | {tool} | "
                 f"{SYMBOL_MD[outcome]} | {secs_md(secs)} |")
    L += ["",
          "A non-terminating row shows the budget it exhausted, not a time to",
          "a verdict. `n/r` means the run behind that row predates per-query",
          "cost recording; re-run `make verify` to populate it.", ""]
    return "\n".join(L) + "\n"


# ===========================================================================
# Scope, wire format, control experiment, prover summary
# ===========================================================================

def _lines(paths) -> int:
    return sum(len(p.read_text(errors="replace").splitlines()) for p in paths)


def scope_tex() -> str:
    """What the artifact contains, measured rather than described."""
    core = sorted((ROOT / "models" / "proverif" / "lib").glob("*.pvl"))
    pv = sorted((ROOT / "models" / "proverif").glob("*.pv")) + \
        sorted((ROOT / "models" / "proverif" / "pq").glob("*.pv"))
    tam = sorted((ROOT / "models" / "tamarin").glob("*.spthy"))
    layout = [ROOT / "tools" / "wire.py"]

    rs = rows()
    n_fields = sum(len(f) for f, _ in wire.MESSAGES.values())
    body = [
        (r"Shared ProVerif core (\texttt{lib/})", core, "---"),
        ("ProVerif query models", pv,
         str(sum(1 for r in rs if r[2] == "ProVerif"))),
        ("Tamarin theory", tam,
         str(sum(1 for r in rs if r[2] == "Tamarin"))),
        (r"Wire-format layout (\texttt{wire.py})", layout,
         rf"{n_fields} fields"),
    ]
    L = [r"\begin{tabular}{@{}lrrr@{}}", r"\toprule",
         r"Component & Files & Lines & Properties \\", r"\midrule"]
    for name, paths, props in body:
        L.append(f"{name} & {len(paths)} & {_lines(paths)} & {props} \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


def _tt(s: str) -> str:
    return s.replace("_", r"\_")


# Model terms are written in wire.py in the models' own ASCII syntax.  The
# report sets them as mathematics, so the handful that appear are translated
# here rather than duplicated in wire.py: the layout file stays readable by the
# tools that consume it, and the paper stays typeset.
TERM_MATH = {
    "Ei = pk(ei)":                           r"$E_i=\mathit{pk}(e_i)$",
    "Er = pk(er)":                           r"$E_r=\mathit{pk}(e_r)$",
    "msgStatic = aead(k1, 0, g2b(Si), hi1)": r"$\mathrm{aead}(k_1,0,S_i,h_1)$",
    "msgTs = aead(k2, 0, tai64n, hi2)":      r"$\mathrm{aead}(k_2,0,\mathit{ts},h_2)$",
    "msgEmpty = aead(k3, 0, EMPTY, hi5)":    r"$\mathrm{aead}(k_3,0,\varepsilon,h_5)$",
    "mac(hash(concat(LABEL_MAC1, g2b(Sr))), ...)": r"$\mathrm{mac}(H(L\|S_r),\cdot)$",
    "mac(hash(concat(LABEL_MAC1, g2b(Si))), ...)": r"$\mathrm{mac}(H(L\|S_i),\cdot)$",
}


def _term_tex(term: "str | None") -> str:
    if term is None:
        return r"\textcolor{black!45}{---}"
    return TERM_MATH.get(term, rf"\texttt{{{_tt(term)}}}")


def wire_tex(message: str) -> str:
    """One wire-format message as a LaTeX table, offsets and all.

    The report used to carry this table typed out by hand, so a corrected field
    length in wire.py left a stale row in the paper.  It is now rendered from
    the same data structure scripts/verify_wire_table.py checks the models
    against, and the three cannot drift apart.
    """
    fields, _ = wire.MESSAGES[message]
    L = [r"\begin{tabular}{@{}rrll@{}}", r"\toprule",
         r"Off & Len & Field & Model term \\", r"\midrule"]
    for f in fields:
        L.append(rf"{f.offset} & {f.length} & \texttt{{{_tt(f.name)}}} & "
                 rf"{_term_tex(f.model_term)} \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


def psk_tex() -> str:
    """The controlled pre-shared-key experiment, with its observed verdicts.

    Three columns, not four: both arms face the same attacker, and a column
    with one repeated value costs width the model file names need.  The
    attacker is named in the caption instead.
    """
    agg = {r[0]: r for r in rows()}
    spec = [("P4",  r"\texttt{22\_pq\_forward\_secrecy.pv}", "secret"),
            ("P4c", r"\texttt{23\_pq\_fs\_nopsk.pv}",        "public")]
    L = [r"\begin{tabular}{@{}llc@{}}", r"\toprule",
         r"Model & psk & Transport-key secrecy \\", r"\midrule"]
    for pid, model, psk in spec:
        outcome = agg[pid][3] if pid in agg else "nonterminating"
        L.append(f"{model} & {psk} & {SYMBOL_TEX[outcome]} \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


def _span(rs, tool: str) -> str:
    """Wall-clock range over the properties this prover actually decided."""
    v = sorted(r[4] for r in rs
               if r[2] == tool and r[3] != "nonterminating" and r[4] is not None)
    if not v:
        return r"\textit{n/r}"
    return _secs(v[0]) if v[0] == v[-1] else f"{_secs(v[0])}--{_secs(v[-1])}"


def provers_tex(vers: dict) -> str:
    """Side-by-side prover summary: verdicts and cost, aggregated per prover."""
    rs = rows()
    cols = []
    for tool in ("ProVerif", "Tamarin"):
        mine = [r for r in rs if r[2] == tool]
        spent = [r[4] for r in mine if r[3] == "nonterminating" and r[4] is not None]
        cols.append({
            "posed": len(mine),
            "by": {k: sum(1 for r in mine if r[3] == k) for k in ORDER},
            "span": _span(rs, tool),
            "spent": str(sum(spent)) if spent else "---",
        })

    L = [r"\begin{tabular}{@{}lrr@{}}", r"\toprule",
         rf" & {vers['proverif']} & {vers['tamarin']} \\", r"\midrule",
         rf"Properties posed & {cols[0]['posed']} & {cols[1]['posed']} \\"]
    for key, label in (("proved", "Proved"),
                       ("attack_found", "Attack found"),
                       ("inconclusive", "Inconclusive"),
                       ("nonterminating", "Non-terminating")):
        L.append(rf"{label} & {cols[0]['by'][key]} & {cols[1]['by'][key]} \\")
    L += [r"\midrule",
          rf"Wall-clock to a verdict (s) & {cols[0]['span']} & {cols[1]['span']} \\",
          rf"Wall-clock spent undecided (s) & {cols[0]['spent']} & {cols[1]['spent']} \\",
          r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


# ===========================================================================
# Post-quantum cost tables
# ===========================================================================

def pq_sizes_tex(a: dict) -> str:
    L = [r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
         r"KEM & $ek$ & $ct$ & initiation & response \\", r"\midrule",
         rf"X25519 (baseline) & 32 & 32 & {a['baseline']['initiation']} & "
         rf"{a['baseline']['response']} \\", r"\midrule"]
    for k in a["kems"]:
        L.append(f"{k['name']} & {k['ek_bytes']} & {k['ct_bytes']} & "
                 f"{k['initiation_bytes']} ($\\times${k['initiation_growth']}) & "
                 f"{k['response_bytes']} ($\\times${k['response_growth']}) \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


def pq_mtu_tex(a: dict) -> str:
    L = [r"\begin{tabular}{@{}lrrr@{}}", r"\toprule",
         r"Path & MTU & usable UDP & ML-KEM-768 initiation \\", r"\midrule"]
    k768 = next(k for k in a["kems"] if k["name"] == "ML-KEM-768")
    for p in a["paths"]:
        f = k768["path_fit"][p["name"]]
        verdict = (rf"fits, {f['margin_bytes']}\,B spare" if f["fits"]
                   else rf"\textbf{{exceeds by {-f['margin_bytes']}\,B}}")
        L.append(f"{p['name']} & {p['mtu']} & {p['udp_payload']} & {verdict} \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


# ===========================================================================
# facts.tex -- every number the prose is allowed to state
# ===========================================================================

def facts_tex(a: dict, vers: dict) -> str:
    rs, ents, cost = rows(), entries(), source_cost()
    timings = [v for v in cost.values() if v is not None]

    def n(k, tool=None):
        return sum(1 for r in rs if r[3] == k and (tool is None or r[2] == tool))

    k512 = next(k for k in a["kems"] if k["name"] == "ML-KEM-512")
    k768 = next(k for k in a["kems"] if k["name"] == "ML-KEM-768")
    k1024 = next(k for k in a["kems"] if k["name"] == "ML-KEM-1024")
    ipv6 = next(p for p in a["paths"] if p["name"] == "IPv6 minimum MTU")

    steps = [e["steps"] for e in ents if "steps" in e]
    fields = sum(len(f) for f, _ in wire.MESSAGES.values())
    modelled = sum(1 for f, _ in wire.MESSAGES.values()
                   for x in f if x.model_term is not None)

    memkb = makevar("MEM_KB") or "2800000"
    try:
        memgb = f"{int(memkb) / 1_000_000:.1f}"
    except ValueError:
        memgb = "2.8"

    spec = yamlite.loads((ROOT / "expectations.yaml").read_text())["queries"]

    def d(name, value):
        return rf"\newcommand{{\{name}}}{{{value}}}"

    L = [
        "%% -----------------------------------------------------------------",
        "%% GENERATED by scripts/render_tables.py -- do not edit.",
        "%%",
        "%% Every quantity the report's prose states is defined here, from",
        "%% results/results.json, tools/wire.py, tools/pqcost.py,",
        "%% expectations.yaml or the Makefile.  A number with no macro is a",
        "%% number the report is not entitled to state.",
        "%% -----------------------------------------------------------------",
        "",
        "%% --- outcomes, counted over properties (one per table row) -------",
        d("wgProps", len(rs)),
        d("wgVerdicts", len(ents)),
        d("wgProved", n("proved")),
        d("wgAttacks", n("attack_found")),
        d("wgInconcl", n("inconclusive")),
        d("wgNonterm", n("nonterminating")),
        d("wgPvProps", sum(1 for r in rs if r[2] == "ProVerif")),
        d("wgPvProved", n("proved", "ProVerif")),
        d("wgPvNonterm", n("nonterminating", "ProVerif")),
        d("wgTamProps", sum(1 for r in rs if r[2] == "Tamarin")),
        d("wgTamProved", n("proved", "Tamarin")),
        d("wgTamNonterm", n("nonterminating", "Tamarin")),
        d("wgExpectations", len(spec)),
        "",
        "%% --- cost --------------------------------------------------------",
        d("wgBudget", makevar("TIMEOUT") or "300"),
        d("wgMemCap", memgb),
        d("wgPvSpan", _span(rs, "ProVerif")),
        d("wgTamSpan", _span(rs, "Tamarin")),
        d("wgSuiteSeconds", sum(timings) if timings else "---"),
        d("wgTamSteps", f"{min(steps)}--{max(steps)}" if steps else r"\textit{n/r}"),
        "",
        "%% --- verifiers ---------------------------------------------------",
        d("wgProVerif", vers["proverif"]),
        d("wgTamarin", vers["tamarin"]),
        "",
        "%% --- wire format -------------------------------------------------",
        d("wgInitBytes", a["baseline"]["initiation"]),
        d("wgRespBytes", a["baseline"]["response"]),
        d("wgFields", fields),
        d("wgFieldsModelled", modelled),
        d("wgFieldsUnmodelled", fields - modelled),
        "",
        "%% --- post-quantum arithmetic --------------------------------------",
        d("wgKemFiveInit", k512["initiation_bytes"]),
        d("wgKemInit", k768["initiation_bytes"]),
        d("wgKemResp", k768["response_bytes"]),
        d("wgKemTenInit", k1024["initiation_bytes"]),
        d("wgKemGrowth", k768["initiation_growth"]),
        d("wgKemTenGrowth", k1024["initiation_growth"]),
        d("wgIpvsixMtu", ipv6["mtu"]),
        d("wgIpvsixPayload", ipv6["udp_payload"]),
        d("wgOvershoot", -k768["path_fit"]["IPv6 minimum MTU"]["margin_bytes"]),
        d("wgPaths", len(a["paths"])),
        "",
        "%% --- did this run record per-query wall-clock cost? ---------------",
        "%% False when results/ predates cost recording; the report then omits",
        "%% the cost figure rather than showing an empty one.",
        r"\newif\ifwgtimings",
        r"\wgtimings" + ("true" if timings and len(timings) == len(cost) else "false"),
    ]
    return "\n".join(L) + "\n"


# ===========================================================================

def main() -> int:
    TEXOUT.mkdir(parents=True, exist_ok=True)
    MDOUT.mkdir(parents=True, exist_ok=True)

    rs, a, vers = rows(), pqcost.analyse(), tool_versions()

    written = {
        "results_table.tex": to_tex(rs),
        "tbl_scope.tex": scope_tex(),
        "tbl_wire_init.tex": wire_tex("handshake_initiation"),
        "tbl_wire_resp.tex": wire_tex("handshake_response"),
        "tbl_psk.tex": psk_tex(),
        "tbl_provers.tex": provers_tex(vers),
        "pq_sizes.tex": pq_sizes_tex(a),
        "pq_mtu.tex": pq_mtu_tex(a),
        "facts.tex": facts_tex(a, vers),
    }
    for name, text in written.items():
        (TEXOUT / name).write_text(text)

    (MDOUT / "results.md").write_text(to_md(rs))
    (MDOUT / "cost.md").write_text(cost_md(rs))

    print(f"rendered {len(rs)} result rows, {len(written)} LaTeX fragments, "
          f"2 Markdown fragments")
    print(to_md(rs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
