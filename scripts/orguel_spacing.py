"""Stage 4: spacing histograms for escoras/torres/VMs."""
import sys, json, math
from collections import Counter, defaultdict

geo = json.load(open(sys.argv[1]))
recs = geo['recs']
SCALE = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0  # units -> meters

def pts_of(kind):
    return [(r[3] * SCALE, r[4] * SCALE, r[1], r[5]) for r in recs if r[0] == kind]

esc = pts_of('escora')
xs = sorted(p[0] for p in esc); ys = sorted(p[1] for p in esc)
print(f"escoras n={len(esc)} xrange={xs[0]:.2f}..{xs[-1]:.2f} yrange={ys[0]:.2f}..{ys[-1]:.2f}")

def row_spacings(points, axis, tol):
    """group by the other coordinate (rows/cols), diff along axis"""
    other = 1 - axis
    groups = defaultdict(list)
    for p in points:
        groups[round(p[other] / tol)].append(p[axis])
    sp = Counter()
    for g in groups.values():
        g = sorted(g)
        for a, b in zip(g, g[1:]):
            d = b - a
            if 0.05 < d < 4.0:
                sp[round(d / 0.05) * 0.05] += 1
    return sp

for tol in (0.10,):
    spx = row_spacings(esc, 0, tol)
    spy = row_spacings(esc, 1, tol)
    print("ESC dX (rows, tol %.2f):" % tol, sorted(spx.items(), key=lambda x: -x[1])[:15])
    print("ESC dY (cols, tol %.2f):" % tol, sorted(spy.items(), key=lambda x: -x[1])[:15])

tor = pts_of('torre')
print(f"\ntorres n={len(tor)}")
for p in tor: pass
# torre pairwise nearest neighbor
def nn_dists(points, maxd=5.0):
    c = Counter()
    for i, p in enumerate(points):
        best = None
        for j, q in enumerate(points):
            if i == j: continue
            d = math.hypot(p[0]-q[0], p[1]-q[1])
            if best is None or d < best: best = d
        if best and best < maxd:
            c[round(best / 0.05) * 0.05] += 1
    return c
print("torre NN:", sorted(nn_dists(tor).items(), key=lambda x: -x[1])[:15])
print("torre names:", Counter(r[2] for r in tor))

# VM80: rotation histogram, name->length, perpendicular step between parallel VMs
vm = [(r[3]*SCALE, r[4]*SCALE, r[1], r[5] % 180, r[2]) for r in recs if r[0] == 'vm80']
rotc = Counter(round(v[3]) for v in vm)
print(f"\nvm80 n={len(vm)} rotations: {rotc.most_common(8)}")
namec = Counter(v[2] for v in vm)
print("vm80 names:", namec.most_common())
# group by layer+orientation; step = spacing along perpendicular axis
for lay in set(v[4] for v in vm):
    for ang in (0, 90):
        sel = [v for v in vm if v[4] == lay and abs(v[3]-ang) < 2]
        if len(sel) < 5: continue
        ax = 1 if ang == 0 else 0   # horizontal vm -> step in Y
        sp = row_spacings([(v[0], v[1]) for v in sel], ax, 0.30)
        print(f"vm80 {lay} ang={ang} n={len(sel)} step:", sorted(sp.items(), key=lambda x: -x[1])[:12])

# escora NN overall
print("\nESC NN:", sorted(nn_dists(esc, 3.0).items(), key=lambda x: -x[1])[:15])

# dims histogram (annotated measurements)
dims = Counter(round(d[1] * SCALE, 2) for d in geo['dims'] if 0.2 < d[1]*SCALE < 3.0)
print("\nDIM values 0.2-3.0 m:", sorted(dims.items(), key=lambda x: -x[1])[:25])
