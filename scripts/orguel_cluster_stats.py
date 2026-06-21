"""Stage 3: cluster pranchas and compute spacing histograms."""
import sys, json, math
from collections import Counter, defaultdict

geo = json.load(open(sys.argv[1]))
recs = geo['recs']

# spatial clustering: union-find on points within RADIUS
pts = [(r[3], r[4], i) for i, r in enumerate(recs)]
xs = sorted(set(round(p[0]) for p in pts))
# 1-D cluster on X with gap threshold (pranchas side by side)
def cluster_1d(vals, gap):
    vals = sorted(vals)
    groups, cur = [], [vals[0]]
    for v in vals[1:]:
        if v - cur[-1] > gap:
            groups.append(cur); cur = [v]
        else:
            cur.append(v)
    groups.append(cur)
    return groups

# 2D grid clustering with cell flood fill
CELL = 2000.0
cells = defaultdict(list)
for x, y, i in pts:
    cells[(int(x // CELL), int(y // CELL))].append(i)
seen = set(); clusters = []
for c in cells:
    if c in seen: continue
    stack = [c]; seen.add(c); comp = []
    while stack:
        cc = stack.pop(); comp.extend(cells[cc])
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nb = (cc[0] + dx, cc[1] + dy)
                if nb in cells and nb not in seen:
                    seen.add(nb); stack.append(nb)
    clusters.append(comp)
clusters.sort(key=len, reverse=True)
print(f"{len(clusters)} clusters; sizes: {[len(c) for c in clusters[:10]]}")
for ci, comp in enumerate(clusters[:6]):
    kinds = Counter(recs[i][0] for i in comp)
    xs_ = [recs[i][3] for i in comp]; ys_ = [recs[i][4] for i in comp]
    print(f"cluster {ci}: n={len(comp)} bbox=({min(xs_):.0f},{min(ys_):.0f})-({max(xs_):.0f},{max(ys_):.0f}) kinds={dict(kinds)}")
json.dump([[int(i) for i in c] for c in clusters], open(sys.argv[2], 'w'))
