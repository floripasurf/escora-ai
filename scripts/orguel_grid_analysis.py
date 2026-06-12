"""Stage 5: per-block-name grid analysis with sub-clustering of pranchas."""
import sys, json, math
from collections import Counter, defaultdict

geo = json.load(open(sys.argv[1]))
SCALE = float(sys.argv[2])
recs = [(r[0], r[1], r[2], r[3]*SCALE, r[4]*SCALE, r[5]) for r in geo['recs']]

def subcluster(points, gap=6.0):
    """cluster on X then Y by gaps"""
    out = []
    pts = sorted(points, key=lambda p: p[0])
    groups = [[pts[0]]]
    for p in pts[1:]:
        if p[0] - groups[-1][-1][0] > gap: groups.append([p])
        else: groups[-1].append(p)
    for g in groups:
        g = sorted(g, key=lambda p: p[1])
        sub = [[g[0]]]
        for p in g[1:]:
            if p[1] - sub[-1][-1][1] > gap: sub.append([p])
            else: sub[-1].append(p)
        out.extend(sub)
    return out

def grid_stats(points, label):
    if len(points) < 10: return
    # rows: cluster Y values with tol 0.06
    ys = sorted(p[1] for p in points)
    rows = [[ys[0]]]
    for y in ys[1:]:
        if y - rows[-1][-1] > 0.06: rows.append([y])
        else: rows[-1].append(y)
    rowc = [sum(r)/len(r) for r in rows if len(r) >= 2]
    # column the same
    xs = sorted(p[0] for p in points)
    cols = [[xs[0]]]
    for x in xs[1:]:
        if x - cols[-1][-1] > 0.06: cols.append([x])
        else: cols[-1].append(x)
    colc = [sum(c)/len(c) for c in cols if len(c) >= 2]
    dxh, dyh = Counter(), Counter()
    for p in points: pass
    # dX within rows
    rowmap = defaultdict(list)
    for p in points:
        ri = min(range(len(rows)), key=lambda i: abs(sum(rows[i])/len(rows[i]) - p[1]))
        rowmap[ri].append(p[0])
    for v in rowmap.values():
        v = sorted(v)
        for a, b in zip(v, v[1:]):
            d = b - a
            if 0.1 < d < 3.5: dxh[round(d/0.05)*0.05] += 1
    colmap = defaultdict(list)
    for p in points:
        ci = min(range(len(cols)), key=lambda i: abs(sum(cols[i])/len(cols[i]) - p[0]))
        colmap[ci].append(p[1])
    for v in colmap.values():
        v = sorted(v)
        for a, b in zip(v, v[1:]):
            d = b - a
            if 0.1 < d < 3.5: dyh[round(d/0.05)*0.05] += 1
    # row pitch (distance between consecutive row centers)
    rp = Counter()
    allrow = sorted(sum(r)/len(r) for r in rows)
    for a, b in zip(allrow, allrow[1:]):
        d = b - a
        if 0.1 < d < 3.5: rp[round(d/0.05)*0.05] += 1
    cp = Counter()
    allcol = sorted(sum(c)/len(c) for c in cols)
    for a, b in zip(allcol, allcol[1:]):
        d = b - a
        if 0.1 < d < 3.5: cp[round(d/0.05)*0.05] += 1
    print(f"  {label}: n={len(points)} rows>=2pts={len(rowc)} cols>=2pts={len(colc)}")
    print(f"    dX in-row : {sorted(dxh.items(), key=lambda x:-x[1])[:10]}")
    print(f"    dY in-col : {sorted(dyh.items(), key=lambda x:-x[1])[:10]}")
    print(f"    row pitch : {sorted(rp.items(), key=lambda x:-x[1])[:10]}")
    print(f"    col pitch : {sorted(cp.items(), key=lambda x:-x[1])[:10]}")

names = Counter((r[0], r[1]) for r in recs)
for (kind, name), cnt in names.most_common():
    if cnt < 12 or kind in ('ta', 'cruzeta'): continue
    pts = [(r[3], r[4]) for r in recs if r[1] == name]
    subs = subcluster(pts)
    subs.sort(key=len, reverse=True)
    print(f"\n{kind} / {name} (total {cnt}, {len(subs)} sub-clusters, sizes {[len(s) for s in subs[:5]]})")
    for s in subs[:2]:
        x0 = min(p[0] for p in s); x1 = max(p[0] for p in s)
        y0 = min(p[1] for p in s); y1 = max(p[1] for p in s)
        print(f"  bbox ({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f}) [{x1-x0:.1f} x {y1-y0:.1f} m]")
        grid_stats(s, name)
