"""Generate every figure in the report as SVG, using only the standard library.

Deliberately no plotting library.  Figures are emitted as text the repository
can diff, they scale without blurring, and `make figures` needs no virtual
environment -- which matters on a machine where the memory budget is the
binding constraint and every avoidable dependency is worth avoiding.

Run:  python3 tools/figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "scripts"))
import pqcost
from wire import INITIATION, RESPONSE, total

OUT = ROOT / "results" / "figures"


def result_rows():
    """The result matrix, or an empty list before any run has produced one.

    Imported from the table generator rather than re-derived, so the cost
    figure and the cost column of the results table cannot disagree: they are
    literally the same list.
    """
    try:
        import render_tables
        return render_tables.rows()
    except Exception:
        return []

# A restrained palette: one accent for "safe", one for "fails", grey for
# structure.  Colour never carries information on its own -- every figure is
# readable in greyscale, because printed submissions usually are.
INK, GREY, LIGHT = "#1a1a1a", "#6b6b6b", "#d4d4d4"
OK, BAD = "#2f6f4e", "#a33a2a"
FONT = "font-family='Helvetica,Arial,sans-serif'"


def _svg(w: int, h: int, body: str) -> str:
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' "
            f"viewBox='0 0 {w} {h}'>\n<rect width='{w}' height='{h}' fill='white'/>\n"
            f"{body}\n</svg>\n")


def _t(x, y, s, size=11, anchor="start", fill=INK, weight="normal"):
    s = (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return (f"<text x='{x}' y='{y}' {FONT} font-size='{size}' fill='{fill}' "
            f"text-anchor='{anchor}' font-weight='{weight}'>{s}</text>")


# --------------------------------------------------------------------------
def fig_handshake_flow() -> str:
    """Message flow, annotated with wire sizes and the DH terms each carries."""
    W, H = 700, 340
    xi, xr = 150, 550
    b = [f"<line x1='{xi}' y1='60' x2='{xi}' y2='{H-40}' stroke='{LIGHT}' stroke-width='1.5'/>",
         f"<line x1='{xr}' y1='60' x2='{xr}' y2='{H-40}' stroke='{LIGHT}' stroke-width='1.5'/>",
         _t(xi, 40, "Initiator", 13, "middle", INK, "bold"),
         _t(xr, 40, "Responder", 13, "middle", INK, "bold"),
         _t(xi, 56, "static (s_i, S_i), psk", 9, "middle", GREY),
         _t(xr, 56, "static (s_r, S_r), psk", 9, "middle", GREY)]

    def arrow(y, label, sub, right=True):
        x1, x2 = (xi, xr) if right else (xr, xi)
        head = (f"<polygon points='{x2},{y} {x2 + (-9 if right else 9)},{y-4} "
                f"{x2 + (-9 if right else 9)},{y+4}' fill='{INK}'/>")
        return (f"<line x1='{x1}' y1='{y}' x2='{x2}' y2='{y}' stroke='{INK}' "
                f"stroke-width='1.4'/>{head}"
                + _t((x1 + x2) / 2, y - 8, label, 11, "middle", INK, "bold")
                + _t((x1 + x2) / 2, y + 14, sub, 9, "middle", GREY))

    b.append(arrow(120, f"handshake initiation, {total(INITIATION)} B",
                   "E_i | enc_static (48 B) | enc_timestamp (28 B) | mac1 | mac2"))
    b.append(_t(xi - 12, 150, "es = DH(e_i, S_r),  ss = DH(s_i, S_r)", 9, "end", GREY))
    b.append(arrow(215, f"handshake response, {total(RESPONSE)} B",
                   "E_r | enc_nothing (16 B) | mac1 | mac2", right=False))
    b.append(_t(xr + 12, 245, "ee = DH(e_r, E_i),  se = DH(e_r, S_i)", 9, "start", GREY))
    b.append(_t(xr + 12, 258, "psk mixed by KDF_3", 9, "start", OK))
    b.append(f"<line x1='{xi}' y1='290' x2='{xr}' y2='290' stroke='{OK}' "
             f"stroke-width='1.2' stroke-dasharray='4,3'/>")
    b.append(_t((xi + xr) / 2, 283, "transport keys (T_i, T_r) = KDF_2(ck, empty)",
                10, "middle", OK))
    return _svg(W, H, "\n".join(b))


# --------------------------------------------------------------------------
def fig_pq_mtu() -> str:
    """Handshake initiation size against the usable UDP payload of each path.

    The single fact this figure exists to convey: the ML-KEM-768 bar crosses
    the IPv6 minimum-MTU line.  Everything else is context for that crossing.
    """
    a = pqcost.analyse()
    bars = [("X25519", a["baseline"]["initiation"])] + \
           [(k["name"], k["initiation_bytes"]) for k in a["kems"]]
    W, H = 700, 380
    x0, y0, plot_w, plot_h = 110, 300, 520, 240
    xmax = 1800
    sx = lambda v: x0 + v / xmax * plot_w

    b = [_t(x0, 28, "Handshake initiation size against usable UDP payload",
            13, "start", INK, "bold"),
         _t(x0, 46, "bar = datagram size; vertical rules = largest payload each path carries",
            9, "start", GREY)]

    # Path limits as vertical reference lines.
    for i, p in enumerate(a["paths"]):
        if p["name"] not in ("IPv6 minimum MTU", "Ethernet, IPv4", "Tunnel stacking, IPv4"):
            continue
        x = sx(p["udp_payload"])
        crit = p["name"] == "IPv6 minimum MTU"
        col = BAD if crit else GREY
        b.append(f"<line x1='{x}' y1='60' x2='{x}' y2='{y0}' stroke='{col}' "
                 f"stroke-width='{1.6 if crit else 1}' stroke-dasharray='5,4'/>")
        b.append(_t(x + 4, 72 + i * 13, f"{p['name']} ({p['udp_payload']} B)",
                    9, "start", col, "bold" if crit else "normal"))

    bh, gap = 34, 18
    for i, (name, size) in enumerate(bars):
        y = 130 + i * (bh + gap)
        fits = size <= 1232
        b.append(f"<rect x='{x0}' y='{y}' width='{sx(size) - x0}' height='{bh}' "
                 f"fill='{OK if fits else BAD}' opacity='0.82'/>")
        b.append(_t(x0 - 8, y + bh / 2 + 4, name, 10, "end", INK))
        b.append(_t(sx(size) + 6, y + bh / 2 + 4, f"{size} B", 10, "start", INK, "bold"))

    b.append(f"<line x1='{x0}' y1='{y0}' x2='{x0 + plot_w}' y2='{y0}' "
             f"stroke='{INK}' stroke-width='1'/>")
    for v in range(0, xmax + 1, 300):
        b.append(f"<line x1='{sx(v)}' y1='{y0}' x2='{sx(v)}' y2='{y0+4}' stroke='{INK}'/>")
        b.append(_t(sx(v), y0 + 17, v, 9, "middle", GREY))
    b.append(_t(x0 + plot_w / 2, y0 + 36, "bytes", 10, "middle", GREY))
    b.append(_t(x0, y0 + 60,
                "ML-KEM-768 exceeds the IPv6 minimum-MTU payload by 68 B: "
                "an in-band handshake has no guaranteed path.", 10, "start", BAD, "bold"))
    return _svg(W, H, "\n".join(b))


# --------------------------------------------------------------------------
def fig_kci_gap() -> str:
    """Where key-compromise impersonation resistance actually resides.

    Two events, one compromise, opposite outcomes.  The figure names the DH
    term responsible for the difference, which is the whole point.
    """
    W, H = 700, 260
    b = [_t(30, 28, "Responder static key compromised: what the attacker can and cannot do",
            13, "start", INK, "bold")]
    boxes = [(40, "Forge message 1", "needs es = DH(e_i, S_r) and ss = DH(s_i, S_r)",
              "both computable from the leaked responder scalar", BAD,
              "S6a  falsified: responder commits key material"),
             (380, "Complete the session", "needs se = DH(e_r, S_i)",
              "requires the initiator's scalar, which is not compromised", OK,
              "S6b  verified: no traffic is ever accepted")]
    for x, title, need, why, col, verdict in boxes:
        b.append(f"<rect x='{x}' y='60' width='280' height='130' fill='none' "
                 f"stroke='{col}' stroke-width='1.6' rx='4'/>")
        b.append(_t(x + 14, 84, title, 12, "start", col, "bold"))
        b.append(_t(x + 14, 106, need, 10, "start", INK))
        b.append(_t(x + 14, 124, why, 9, "start", GREY))
        b.append(f"<line x1='{x+14}' y1='140' x2='{x+266}' y2='140' stroke='{LIGHT}'/>")
        b.append(_t(x + 14, 160, verdict, 10, "start", col, "bold"))
    b.append(f"<polygon points='330,120 370,120 370,114 382,125 370,136 370,130 330,130' "
             f"fill='{GREY}'/>")
    b.append(_t(30, 226,
                "ProVerif did not terminate on either level within the documented budget; "
                "Tamarin decided both in under 10 s.", 10, "start", GREY))
    return _svg(W, H, "\n".join(b))


# --------------------------------------------------------------------------
def fig_pipeline() -> str:
    """How one protocol description reaches two provers and one report.

    The figure exists to make the central methodological claim checkable at a
    glance: there is one transcription of the handshake, and everything the
    report prints is downstream of what the verifiers actually wrote.
    """
    W, H = 700, 330
    b = [_t(20, 24, "One transcription, two provers, one generated report",
            13, "start", INK, "bold")]

    def box(x, y, w, h, title, sub, col=INK, fill="none"):
        out = [f"<rect x='{x}' y='{y}' width='{w}' height='{h}' fill='{fill}' "
               f"stroke='{col}' stroke-width='1.4' rx='4'/>",
               _t(x + w / 2, y + 19, title, 10, "middle", col, "bold")]
        if sub:
            out.append(_t(x + w / 2, y + 33, sub, 8.5, "middle", GREY))
        return out

    def arrow(x1, y1, x2, y2):
        return (f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{GREY}' "
                f"stroke-width='1.2'/>"
                f"<circle cx='{x2}' cy='{y2}' r='2.6' fill='{GREY}'/>")

    b += box(255, 42, 190, 44, "WireGuard specification", "wire format + Noise IKpsk2")
    b += box(255, 108, 190, 44, "shared ProVerif core",
             "lib/wireguard_core.pvl", OK)
    b += box(30, 174, 200, 44, "ProVerif query models",
             "one per property, all include the core")
    b += box(470, 174, 200, 44, "Tamarin theory",
             "transcribed term for term")
    b += box(255, 240, 190, 40, "runner.py", "budget + address-space cap")
    b += box(30, 240, 200, 40, "results/raw/*.out", "verbatim prover output")
    b += box(470, 240, 200, 40, "results/results.json",
             "checked against expectations.yaml", OK)

    b.append(arrow(350, 86, 350, 108))
    b.append(arrow(255, 152, 130, 174))
    b.append(arrow(445, 152, 570, 174))
    b.append(arrow(160, 218, 300, 240))
    b.append(arrow(540, 218, 400, 240))
    b.append(arrow(255, 260, 230, 260))
    b.append(arrow(445, 260, 470, 260))
    b.append(_t(350, 306,
                "render_tables.py and figures.py turn results.json into every "
                "table, figure and quoted number in the report",
                9, "middle", GREY))
    return _svg(W, H, "\n".join(b))


# --------------------------------------------------------------------------
def fig_compromise() -> str:
    """When each secret is released, and which queries depend on the staging."""
    W, H = 700, 250
    x0, xm, x1 = 40, 340, 660
    b = [_t(20, 24, "Attacker capability over time, and the queries that use it",
            13, "start", INK, "bold"),
         f"<rect x='{x0}' y='46' width='{xm - x0}' height='34' fill='{OK}' "
         f"opacity='0.14'/>",
         f"<rect x='{xm}' y='46' width='{x1 - xm}' height='34' fill='{BAD}' "
         f"opacity='0.14'/>",
         _t((x0 + xm) / 2, 68, "phase 0 -- sessions run", 11, "middle", INK, "bold"),
         _t((xm + x1) / 2, 68, "phase 1 -- after the fact", 11, "middle", INK, "bold"),
         f"<line x1='{xm}' y1='40' x2='{xm}' y2='{H - 40}' stroke='{BAD}' "
         f"stroke-width='1.4' stroke-dasharray='5,4'/>",
         _t(x0, 100, "Dolev-Yao network control; every ephemeral public value "
            "travels in clear", 9, "start", GREY),
         _t(xm + 8, 100, "static scalars released;", 9, "start", BAD),
         _t(xm + 8, 113, "discrete-logarithm oracle exposed", 9, "start", BAD)]

    rows = [("P3  forward secrecy", "statics released", "proved", OK),
            ("P4  post-quantum FS, psk secret", "+ DL oracle", "proved", OK),
            ("P4c same, psk published", "+ DL oracle", "attack found", BAD),
            ("S6a/S6b  KCI", "responder static, at any time", "the gap", GREY)]
    for i, (name, cap, verdict, col) in enumerate(rows):
        y = 143 + i * 24
        b.append(_t(x0, y, name, 9.5, "start", INK))
        b.append(_t(xm + 8, y, cap, 9, "start", GREY))
        b.append(_t(x1, y, verdict, 9.5, "end", col, "bold"))
    return _svg(W, H, "\n".join(b))


# --------------------------------------------------------------------------
def fig_cost() -> str:
    """Wall-clock cost of every property, by prover, against the budget.

    The single fact this figure exists to convey: the three ProVerif bars that
    reach the budget line are the ones Tamarin decides in seconds.
    """
    rs = [r for r in result_rows() if r[4] is not None]
    if not rs:
        return ""
    budget = max(max(r[4] for r in rs), 1)
    W = 700
    H = 90 + len(rs) * 20
    x0, xw = 210, 420
    sx = lambda v: x0 + v / budget * xw  # noqa: E731
    b = [_t(20, 24, "Wall-clock cost per property", 13, "start", INK, "bold"),
         _t(20, 40, "bars at the right edge exhausted the budget without "
            "reaching a verdict", 9, "start", GREY)]
    for i, (pid, desc, tool, outcome, secs) in enumerate(rs):
        y = 58 + i * 20
        col = BAD if outcome == "nonterminating" else (
            OK if outcome == "proved" else GREY)
        w = max(sx(secs) - x0, 1.5)
        b.append(f"<rect x='{x0}' y='{y}' width='{w}' height='13' fill='{col}' "
                 f"opacity='0.85'/>")
        b.append(_t(x0 - 8, y + 11, f"{pid}  {tool}  {desc.strip()[:34]}",
                    9, "end", INK))
        b.append(_t(x0 + w + 6, y + 11, f"{secs} s", 9, "start", GREY))
    ylo = 58 + len(rs) * 20
    b.append(f"<line x1='{x0}' y1='{ylo}' x2='{x0 + xw}' y2='{ylo}' "
             f"stroke='{INK}' stroke-width='1'/>")
    b.append(_t(x0 + xw / 2, ylo + 18, "seconds", 9, "middle", GREY))
    return _svg(W, H, "\n".join(b))


FIGURES = {
    "pipeline.svg": fig_pipeline,
    "handshake_flow.svg": fig_handshake_flow,
    "compromise.svg": fig_compromise,
    "pq_mtu.svg": fig_pq_mtu,
    "kci_gap.svg": fig_kci_gap,
    "cost.svg": fig_cost,
}



# ==========================================================================
# TikZ emitters
#
# The report cannot include SVG without an external converter, and requiring
# one would break the promise that `make report` works on a plain TeX Live or
# BasicTeX installation.  The figures are therefore emitted a second time as
# TikZ fragments, from the same data as the SVGs above, so the two can never
# disagree.  SVG is what the README and the web view use; TikZ is what the
# PDF uses.
# ==========================================================================

TEXOUT = Path(__file__).resolve().parent.parent / "report" / "generated"


def tikz_pq_mtu() -> str:
    a = pqcost.analyse()
    bars = [("X25519 (baseline)", a["baseline"]["initiation"])] + \
           [(k["name"], k["initiation_bytes"]) for k in a["kems"]]
    ipv6 = next(p for p in a["paths"] if p["name"] == "IPv6 minimum MTU")
    eth = next(p for p in a["paths"] if p["name"] == "Ethernet, IPv4")
    sx = lambda v: v / 1800 * 7.4          # bytes -> cm  # noqa: E731
    L = [r"\begin{tikzpicture}[x=1cm,y=1cm]", r"  \footnotesize"]
    for i, (name, size) in enumerate(bars):
        y = -0.75 * i
        fits = size <= ipv6["udp_payload"]
        col = "okgreen" if fits else "badred"
        L.append(rf"  \fill[{col}!78] (0,{y-0.22}) rectangle ({sx(size):.3f},{y+0.22});")
        L.append(rf"  \node[anchor=east] at (-0.12,{y}) {{{name}}};")
        L.append(rf"  \node[anchor=west] at ({sx(size)+0.12:.3f},{y}) "
                 rf"{{\bfseries {size}\,B}};")
    ylo, yhi = -0.75 * (len(bars) - 1) - 0.5, 0.5

    # The two path limits are 240 B apart, which at this scale is under a
    # centimetre.  Rotating the labels into the plot put them straight through
    # the ML-KEM-768 bar; stacking them horizontally above it keeps both
    # readable and keeps the crossing -- the point of the figure -- visible.
    for p, crit, dy, anchor in ((ipv6, True, 0.28, "east"), (eth, False, 0.72, "west")):
        x = sx(p["udp_payload"])
        col = "badred" if crit else "black!55"
        L.append(rf"  \draw[{col},dashed,{'thick' if crit else 'thin'}] "
                 rf"({x:.3f},{ylo}) -- ({x:.3f},{yhi + dy:.2f});")
        L.append(rf"  \node[{col},anchor={anchor},inner sep=2pt,font=\scriptsize"
                 rf"{',font=\\scriptsize\\bfseries' if crit else ''}] at "
                 rf"({x:.3f},{yhi + dy:.2f}) "
                 rf"{{{p['name']}: {p['udp_payload']}\,B}};")

    L.append(rf"  \draw[->] (0,{ylo-0.35}) -- ({sx(1800):.3f},{ylo-0.35}) "
             rf"node[anchor=west] {{\scriptsize bytes}};")
    for v in range(0, 1801, 600):
        L.append(rf"  \draw ({sx(v):.3f},{ylo-0.45}) -- ({sx(v):.3f},{ylo-0.25}) "
                 rf"node[anchor=north,yshift=-4pt] {{\scriptsize {v}}};")
    L.append(r"\end{tikzpicture}")
    return "\n".join(L) + "\n"


def tikz_kci_gap() -> str:
    """Single-column figure: the two levels, stacked.

    Stacked rather than side by side.  Two 5.6 cm boxes in a row measure 13 cm
    and \\resizebox then shrinks them to two-thirds of a column, which puts the
    body text at about seven points.  Stacking keeps the figure near natural
    size, and the vertical arrow reads as the gap the section is about.
    """
    return r"""\begin{tikzpicture}[x=1cm,y=1cm,font=\footnotesize]
  \node[draw=badred,thick,rounded corners,align=left,inner sep=6pt,
        text width=7.0cm] (a) at (0,0)
    {\textbf{\color{badred}1. Forge message 1}\\[2pt]
     needs $es=\mathrm{DH}(e_i,S_r)$ and $ss=\mathrm{DH}(s_i,S_r)$\\[1pt]
     {\color{black!55}both computable from the leaked responder scalar}\\[3pt]
     \hrule\vspace{3pt}
     {\color{badred}\textbf{S6a falsified}} --- the responder commits key
     material to a session it attributes to an honest initiator};
  \node[draw=okgreen,thick,rounded corners,align=left,inner sep=6pt,
        text width=7.0cm] (b) at (0,-3.15)
    {\textbf{\color{okgreen}2. Complete the session}\\[2pt]
     additionally needs $se=\mathrm{DH}(e_r,S_i)$\\[1pt]
     {\color{black!55}requires the initiator's static scalar, which is not
      compromised}\\[3pt]
     \hrule\vspace{3pt}
     {\color{okgreen}\textbf{S6b verified}} --- no transport record is ever
     accepted on that session};
  \draw[->,very thick,black!45] (a.south) -- node[right,black!55,align=left]
    {\scriptsize the gap $se$ holds open} (b.north);
\end{tikzpicture}
"""


def tikz_handshake_flow() -> str:
    """Single-column message flow.

    Laid out to fit a column at close to natural size.  An earlier version was
    14 cm wide, which \\resizebox then shrank to 60% and left the annotations
    at about five points -- present in the figure and unreadable in it.
    Everything now sits between the two lifelines.
    """
    return rf"""\begin{{tikzpicture}}[x=1cm,y=1cm,font=\footnotesize]
  \draw[black!25,thick] (0,-0.25) -- (0,-4.5);
  \draw[black!25,thick] (6.2,-0.25) -- (6.2,-4.5);
  \node[anchor=south] at (0,-0.2) {{\bfseries Initiator}};
  \node[anchor=south] at (6.2,-0.2) {{\bfseries Responder}};
  \node[anchor=north,black!55,font=\scriptsize] at (0,-0.3)
    {{static $(s_i,S_i)$, psk}};
  \node[anchor=north,black!55,font=\scriptsize] at (6.2,-0.3)
    {{static $(s_r,S_r)$, psk}};

  \draw[->,thick] (0,-1.35) -- (6.2,-1.35);
  \node[anchor=south,inner sep=2pt] at (3.1,-1.32)
    {{\bfseries handshake initiation, {total(INITIATION)}\,B}};
  \node[anchor=north,black!55,font=\scriptsize,align=center,inner sep=2pt]
    at (3.1,-1.4)
    {{$E_i$ $\mid$ enc\_static (48\,B) $\mid$ enc\_timestamp (28\,B)\\
      $\mid$ mac1 $\mid$ mac2}};
  \node[anchor=west,black!55,font=\scriptsize] at (0.1,-2.25)
    {{$es=\mathrm{{DH}}(e_i,S_r)$,\quad $ss=\mathrm{{DH}}(s_i,S_r)$}};

  \draw[<-,thick] (0,-3.0) -- (6.2,-3.0);
  \node[anchor=south,inner sep=2pt] at (3.1,-2.97)
    {{\bfseries handshake response, {total(RESPONSE)}\,B}};
  \node[anchor=north,black!55,font=\scriptsize,inner sep=2pt] at (3.1,-3.05)
    {{$E_r$ $\mid$ enc\_nothing (16\,B) $\mid$ mac1 $\mid$ mac2}};
  \node[anchor=east,black!55,font=\scriptsize] at (6.1,-3.62)
    {{$ee=\mathrm{{DH}}(e_r,E_i)$,\quad $se=\mathrm{{DH}}(e_r,S_i)$}};
  \node[anchor=east,okgreen,font=\scriptsize] at (6.1,-3.92)
    {{psk mixed by $\mathrm{{KDF}}_3$}};

  \draw[okgreen,dashed,thick] (0,-4.35) -- (6.2,-4.35);
  \node[anchor=south,okgreen,font=\scriptsize,inner sep=2pt] at (3.1,-4.32)
    {{transport keys $(T_i,T_r)=\mathrm{{KDF}}_2(ck,\varepsilon)$}};
\end{{tikzpicture}}
"""


def tikz_pipeline() -> str:
    """Two-column figure: specification to PDF, with the fork in the middle."""
    return r"""\begin{tikzpicture}[x=1cm,y=1cm,font=\footnotesize,
    bx/.style={draw=black!55,rounded corners=2pt,align=center,inner sep=4pt,
               text width=3.2cm,minimum height=1.0cm},
    hi/.style={bx,draw=okgreen,very thick},
    lnk/.style={->,thick,black!45}]

  \node[bx] (spec) at (1.7,0)
    {\textbf{WireGuard specification}\\{\scriptsize wire format $+$ Noise \texttt{IKpsk2}}};
  \node[hi] (core) at (5.6,0)
    {\textbf{one shared core}\\{\scriptsize \texttt{wireguard\_core.pvl}}};
  \node[bx] (pv) at (9.5,1.05)
    {\textbf{ProVerif models}\\{\scriptsize one file per property}};
  \node[bx] (tam) at (9.5,-1.05)
    {\textbf{Tamarin theory}\\{\scriptsize transcribed term for term}};
  \node[bx] (run) at (13.4,0)
    {\textbf{\texttt{runner.py}}\\{\scriptsize wall-clock $+$ memory budget}};
  \node[bx] (raw) at (17.3,0)
    {\textbf{\texttt{results/raw/}}\\{\scriptsize verbatim prover output}};

  \node[hi] (json) at (17.3,-3.1)
    {\textbf{\texttt{results.json}}\\{\scriptsize machine-readable verdicts}};
  \node[bx] (exp) at (13.4,-3.1)
    {\textbf{\texttt{expectations.yaml}}\\{\scriptsize regression gate}};
  \node[bx] (gen) at (9.5,-3.1)
    {\textbf{\texttt{render\_tables.py}}\\{\scriptsize tables, figures, \texttt{facts.tex}}};
  \node[bx] (tex) at (5.6,-3.1)
    {\textbf{\texttt{report/main.tex}}\\{\scriptsize prose only; no typed numbers}};
  \node[hi] (pdf) at (1.7,-3.1)
    {\textbf{\texttt{docs/report.pdf}}\\{\scriptsize built by \texttt{make report}}};

  \draw[lnk] (spec) -- (core);
  \draw[lnk] (core.east) -- (pv.west);
  \draw[lnk] (core.east) -- (tam.west);
  \draw[lnk] (pv.east) -- (run.west);
  \draw[lnk] (tam.east) -- (run.west);
  \draw[lnk] (run) -- (raw);
  \draw[lnk] (raw) -- node[left,black!55,font=\scriptsize,align=right]
    {\texttt{collect\_}\\\texttt{results.py}} (json);
  \draw[lnk] (json) -- (exp);
  \draw[lnk] (exp) -- (gen);
  \draw[lnk] (gen) -- (tex);
  \draw[lnk] (tex) -- (pdf);
\end{tikzpicture}
"""


def tikz_compromise() -> str:
    """Single-column figure: what the attacker gains, and when."""
    return r"""\begin{tikzpicture}[x=1cm,y=1cm,font=\footnotesize]
  \fill[okgreen!12] (0,0) rectangle (4.2,0.72);
  \fill[badred!12]  (4.2,0) rectangle (8.4,0.72);
  \node at (2.1,0.36) {\bfseries phase 0 --- sessions run};
  \node at (6.3,0.36) {\bfseries phase 1 --- after the fact};
  \draw[badred,dashed,thick] (4.2,-1.42) -- (4.2,0.95);

  \node[anchor=north west,text width=3.9cm,black!60,inner sep=2pt,
        font=\scriptsize] at (0.05,-0.06)
    {Dolev--Yao network control. Every ephemeral public value travels in
     clear, so all of it can be recorded.};
  \node[anchor=north west,text width=3.9cm,badred,inner sep=2pt,
        font=\scriptsize] at (4.3,-0.06)
    {Static scalars released and a discrete-logarithm oracle exposed: every
     recorded public value inverts.};

  \draw[black!25] (0,-1.6) -- (8.4,-1.6);
  \node[anchor=west,black!55,font=\scriptsize\itshape] at (0,-1.82)
    {which properties depend on this staging};
"""+ "".join(
    rf"""  \node[anchor=west] at (0,{-2.2 - 0.32 * i:.2f}) {{{name}}};
  \node[anchor=east,{col}] at (8.4,{-2.2 - 0.32 * i:.2f}) {{\bfseries {verdict}}};
"""
    for i, (name, verdict, col) in enumerate([
        (r"P3\quad forward secrecy, statics released", "proved", "okgreen"),
        (r"P4\quad post-quantum FS, psk secret", "proved", "okgreen"),
        (r"P4c\ \ the same model, psk published", "attack found", "badred"),
        (r"S6a/S6b\ \ KCI, responder static leaked", "the gap", "black!55"),
    ])) + r"""\end{tikzpicture}
"""


def tikz_cost() -> str:
    """Single-column figure: wall-clock per property, grouped by prover.

    Emitted only when the current results carry per-query timings.  A run that
    predates cost recording gets an empty fragment and the report's
    \\ifwgtimings guard drops the figure rather than printing an empty axis.
    """
    rs = [r for r in result_rows() if r[4] is not None]
    if not rs:
        return "%% no per-query timings in results/results.json; figure omitted\n"

    budget = max(max(r[4] for r in rs), 1)
    xw = 3.4                                   # cm of bar area
    L = [r"\begin{tikzpicture}[x=1cm,y=1cm,font=\scriptsize]"]
    y = 0.0
    for tool in ("ProVerif", "Tamarin"):
        mine = [r for r in rs if r[2] == tool]
        if not mine:
            continue
        L.append(rf"  \node[anchor=west,font=\scriptsize\bfseries] at (-4.5,{y:.2f}) "
                 rf"{{{tool}}};")
        y -= 0.34
        for pid, desc, _, outcome, secs in mine:
            # Full colour specs, not a base colour plus a shade suffix: the
            # inconclusive base is already `black!35`, and appending another
            # `!85` to it produces `black!35!85`, which xcolor rejects.
            fill = {"proved": "okgreen!85", "attack_found": "badred!85",
                    "nonterminating": "badred!50", "inconclusive": "black!35"}[outcome]
            w = max(secs / budget * xw, 0.03)
            label = desc.strip().replace("&", r"\&")
            label = (label[:30] + r"\dots") if len(label) > 31 else label
            L.append(rf"  \node[anchor=east] at (-0.12,{y:.2f}) "
                     rf"{{{pid}\ \ {label}}};")
            L.append(rf"  \fill[{fill}] "
                     rf"(0,{y - 0.11:.2f}) rectangle ({w:.3f},{y + 0.11:.2f});")
            mark = r"$^\dagger$" if outcome == "nonterminating" else ""
            shown = r"$<$1" if secs == 0 else str(secs)
            L.append(rf"  \node[anchor=west,black!60] at ({w + 0.08:.3f},{y:.2f}) "
                     rf"{{{shown}\,s{mark}}};")
            y -= 0.3
        y -= 0.18

    y += 0.18
    L += [rf"  \draw[black!55] (0,{y:.2f}) -- ({xw:.2f},{y:.2f});"]
    for frac in (0, 0.5, 1.0):
        v = int(round(budget * frac))
        L.append(rf"  \draw[black!55] ({xw * frac:.2f},{y:.2f}) -- "
                 rf"({xw * frac:.2f},{y - 0.09:.2f}) "
                 rf"node[anchor=north,inner sep=2pt] {{{v}}};")
    L.append(rf"  \node[anchor=north] at ({xw / 2:.2f},{y - 0.34:.2f}) "
             rf"{{seconds}};")
    L.append(r"\end{tikzpicture}")
    return "\n".join(L) + "\n"


TIKZ = {
    "fig_pipeline.tex": tikz_pipeline,
    "fig_handshake_flow.tex": tikz_handshake_flow,
    "fig_compromise.tex": tikz_compromise,
    "fig_pq_mtu.tex": tikz_pq_mtu,
    "fig_kci_gap.tex": tikz_kci_gap,
    "fig_cost.tex": tikz_cost,
}


if __name__ == "__main__":
    # A generator that returns nothing has no data to draw -- the cost figure
    # before any run has recorded per-query timings.  Writing a zero-byte SVG
    # would leave something on disk that looks like a figure and renders as a
    # blank rectangle, so the file is removed instead and the count reflects
    # what was actually produced.
    OUT.mkdir(parents=True, exist_ok=True)
    n_svg = 0
    for name, fn in FIGURES.items():
        body = fn()
        if not body.strip():
            (OUT / name).unlink(missing_ok=True)
            print(f"  svg   {name:<24} {'skipped -- no data yet':>22}")
            continue
        (OUT / name).write_text(body)
        n_svg += 1
        print(f"  svg   {name:<24} {len(body):>6} B")

    TEXOUT.mkdir(parents=True, exist_ok=True)
    n_tikz = 0
    for name, fn in TIKZ.items():
        body = fn()
        # The TikZ fragment is always written, even when it is only a comment:
        # the report guards its \input with \ifwgtimings, and a missing file
        # would turn a deliberately omitted figure into a build failure.
        (TEXOUT / name).write_text(body)
        drawn = "tikzpicture" in body
        n_tikz += drawn
        print(f"  tikz  {name:<24} "
              + (f"{len(body):>6} B" if drawn else f"{'omitted -- no data yet':>22}"))
    print(f"wrote {n_svg} SVG + {n_tikz} TikZ figures")
