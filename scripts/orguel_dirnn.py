"""Stage 8: directional nearest-neighbor histograms for a symbol set."""
import sys, json
from collections import Counter

geo = json.load(open(sys.argv[1]))
SCALE = float(sys.argv[2])
names = sys.argv[3].split(',')
tol = 0.08
pts = [(r[3]*SCALE, r[4]*SCALE) for r in geo['recs'] if r[1] in names]
print(f"points: {len(pts)} for {names}")
right = Counter(); up = Counter()
for x, y in pts:
    bx = by = None
    for x2, y2 in pts:
        if abs(y2-y) < tol and x2 > x + 0.01:
            d = x2 - x
            if bx is None or d < bx: bx = d
        if abs(x2-x) < tol and y2 > y + 0.01:
            d = y2 - y
            if by is None or d < by: by = d
    if bx and bx < 4: right[round(bx/0.05)*0.05] += 1
    if by and by < 4: up[round(by/0.05)*0.05] += 1
print("dX to right-neighbor:", sorted(right.items(), key=lambda v:-v[1])[:18])
print("dY to up-neighbor   :", sorted(up.items(), key=lambda v:-v[1])[:18])
print("n right:", sum(right.values()), "n up:", sum(up.values()))
