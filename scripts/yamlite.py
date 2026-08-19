"""A reader for the subset of YAML used by expectations.yaml.

PyYAML would do this in one line, but requiring a pip install to run the
regression check would undermine the claim that the static half of this
repository works on a bare Python 3.  The subset handled is exactly what
expectations.yaml uses: nested mappings, lists of mappings, inline
`{k: v, ...}` maps, folded `>` blocks, comments and quoted scalars.
"""

from __future__ import annotations

import re


def _scalar(v: str):
    v = v.strip()
    if v.startswith(("'", '"')) and v.endswith(("'", '"')) and len(v) > 1:
        return v[1:-1]
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if v in ("true", "false"):
        return v == "true"
    return v


def _inline_map(v: str) -> dict:
    out = {}
    for part in v.strip()[1:-1].split(","):
        if ":" in part:
            k, _, val = part.partition(":")
            out[k.strip()] = _scalar(val)
    return out


def loads(text: str) -> dict:
    """Parse the document into nested dicts and lists."""
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lines.append(raw.rstrip())

    root: dict = {}
    stack = [(-1, root)]          # (indent, container)
    i = 0
    while i < len(lines):
        line = lines[i]
        indent = len(line) - len(line.lstrip())
        body = line.strip()

        while stack and indent <= stack[-1][0] and len(stack) > 1:
            stack.pop()
        parent = stack[-1][1]

        if body.startswith("- "):
            item_txt = body[2:]
            lst = parent if isinstance(parent, list) else None
            if lst is None:
                i += 1
                continue
            entry: dict = {}
            lst.append(entry)
            k, _, v = item_txt.partition(":")
            entry_indent = indent + 2
            if v.strip():
                entry[k.strip()] = (_inline_map(v) if v.strip().startswith("{")
                                    else _scalar(v))
            stack.append((indent, entry))
            # remaining keys of this list item
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                nind = len(nxt) - len(nxt.lstrip())
                if nind < entry_indent or nxt.strip().startswith("- "):
                    break
                kk, _, vv = nxt.strip().partition(":")
                if vv.strip() == ">":
                    buf, j2 = [], j + 1
                    while j2 < len(lines) and (len(lines[j2]) - len(lines[j2].lstrip())) > nind:
                        buf.append(lines[j2].strip())
                        j2 += 1
                    entry[kk.strip()] = " ".join(buf)
                    j = j2
                    continue
                entry[kk.strip()] = (_inline_map(vv) if vv.strip().startswith("{")
                                     else _scalar(vv))
                j += 1
            i = j
            continue

        k, _, v = body.partition(":")
        if not v.strip():
            child: list | dict = []
            parent[k.strip()] = child
            stack.append((indent, child))
        else:
            parent[k.strip()] = _scalar(v)
        i += 1
    return root
