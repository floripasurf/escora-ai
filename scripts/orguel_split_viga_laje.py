"""Stage 9: classify escoras as under-viga vs laje using viga lines; directional NN per class."""
import sys, json, math
from collections import Counter

geo = json.load(open(sys.argv[1]))
SCALE = float(sys.argv[2])
names = set(sys.argv[3].split(','))
DV = float(sys.argv[4]) if len(sys.argv) > 4 else 0.20

vl = [(a*SCALE, b*SCALE, c*SCALE, d*SCALE) for (lay, a, b, c, d) in geo['viga_lines'] if lay == 'VIGAS']
def dist_seg(px, py, s):
    x0, y0, x1, y1 = s
    dx, dy = x1-x0, y1-y0
    L2 = dx*dx + dy*dy
    if L2 == 0: return math.hypot(px-x0, py-y0)
    t = max(0, min(1, ((px-x0)*dx + (py-y0)*dy)/L2))
    return math.hypot(px-x0-t*dx, py-y0-t*dy)

esc = [(r[3]*SCALE, r[4]*SCALE, r[1]) for r in geo['recs'] if r[1] in names]
viga_esc, laje_esc = [], []
for x, y, nm in esc:
    near = any(dist_seg(x, y, s) < DV for s in vl)
    (viga_esc if near else laje_esc).append((x, y, nm))
print(f"escoras: viga={len(viga_esc)} laje={len(laje_esc)} (viga-line dist < {DV} m, {len(vl)} viga lines)")

def dirnn(pts, label):
    right = Counter(); up = Counter()
    for x, y, _ in pts:
        bx = by = None
        for x2, y2, _ in pts:
            if abs(y2-y) < 0.08 and x2 > x+0.01:
                d = x2-x
                if bx is None or d < bx: bx = d
            if abs(x2-x) < 0.08 and y2 > y+0.01:
                d = y2-y
                if by is None or d < by: by = d
        if bx and bx < 4: right[round(bx/0.05)*0.05] += 1
        if by and by < 4: up[round(by/0.05)*0.05] += 1
    print(f"{label} dX:", sorted(right.items(), key=lambda v:-v[1])[:14])
    print(f"{label} dY:", sorted(up.items(), key=lambda v:-v[1])[:14])
    nm = Counter(p[2] for p in pts)
    print(f"{label} names:", dict(nm))
dirnn(viga_esc, "VIGA")
dirnn(laje_esc, "LAJE")
