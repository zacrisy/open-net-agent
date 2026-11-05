#!/usr/bin/env python3
"""Program synthesis over a small grid DSL; diagnostic for abstraction."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from arc_tasks import TASKS


def _copy(g): return [r[:] for r in g]
def _flip_h(g): return [r[::-1] for r in g]
def _flip_v(g): return g[::-1]
def _rot90(g): return [list(r) for r in zip(*g[::-1])]
def _rot180(g): return [r[::-1] for r in g[::-1]]
def _transpose(g): return [list(r) for r in zip(*g)]
def _tile2(g): return [r + r for r in g] + [r + r for r in g]
def _crop(g):
    cells = [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v]
    if not cells: return g
    r0, r1 = min(r for r, _ in cells), max(r for r, _ in cells)
    c0, c1 = min(c for _, c in cells), max(c for _, c in cells)
    return [row[c0:c1+1] for row in g[r0:r1+1]]
def _border(g):
    w = len(g[0]) + 2
    return [[4] * w] + [[4] + row + [4] for row in g] + [[4] * w]
def _count(g): return [[sum(1 for row in g for v in row if v)]]
def _mirror(g): return [row + row[::-1] for row in g]
def _shift(dx, dy):
    def f(g):
        h, w = len(g), len(g[0]); out = [[0] * w for _ in range(h)]
        for r in range(h):
            for c in range(w):
                nr, nc = r + dy, c + dx
                if 0 <= nr < h and 0 <= nc < w: out[nr][nc] = g[r][c]
        return out
    return f


def _color_map(g, mapping): return [[mapping.get(v, v) for v in row] for row in g]
def _learn_colors(inp, out):
    if len(inp) != len(out) or any(len(a) != len(b) for a, b in zip(inp, out)): return {}
    m = {}
    for ra, rb in zip(inp, out):
        for a, b in zip(ra, rb):
            if a in m and m[a] != b: return {}
            m[a] = b
    return m


PRIMS = {
    "id": lambda g: _copy(g), "flip_h": _flip_h, "flip_v": _flip_v,
    "rot90": _rot90, "rot180": _rot180, "transpose": _transpose,
    "tile2": _tile2, "crop": _crop, "border": _border, "count": _count, "mirror": _mirror,
}
for dx in (-2, -1, 0, 1, 2):
    for dy in (-2, -1, 0, 1, 2):
        if dx or dy:
            PRIMS[f"shift_{dx}_{dy}"] = _shift(dx, dy)


def _apply(g, names):
    out = g
    for n in names:
        out = PRIMS[n](out)
    return out


def solve(task):
    inp, out = task["input"], task["output"]
    m = _learn_colors(inp, out)
    names = list(PRIMS)
    for n in names:
        try:
            if _apply(inp, [n]) == out: return [n]
        except Exception: pass
    if m:
        try:
            if _color_map(inp, m) == out: return ["color_map"]
        except Exception: pass
    for a in names:
        for b in names:
            try:
                if _apply(inp, [a, b]) == out: return [a, b]
            except Exception: pass
    return None


def main():
    rows = []
    for t in TASKS:
        p = solve(t); rows.append({"id": t["id"], "program": p, "solved": bool(p)})
    solved = sum(x["solved"] for x in rows)
    out = {"n": len(rows), "solved": solved, "accuracy": round(solved / len(rows), 3), "rows": rows}
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "arc_results.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
