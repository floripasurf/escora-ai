"""Stage 11: gap between VM line run ends and nearest perpendicular viga face line."""
import sys, json, math, re
from collections import Counter, defaultdict

geo = json.load(open(sys.argv[1])); SCALE = float(sys.argv[2]); KIND = sys.argv[3]
segs = []
for r in geo['recs']:
    if r[0] != KIND: continue
    m = re.match(r'^[A-Z]+\d*-(\d+)', r[1])
    if not m: continue
    L = int(m.group(1))/100.0
    x, y = r[3]*SCALE, r[4]*SCALE
    a = math.radians(r[5])
    segs.append((x, y, x+L*math.cos(a), y+L*math.sin(a), round(r[5])%180))
vl = [(a*SCALE, b*SCALE, c*SCALE, d*SCALE) for (lay, a, b, c, d) in geo['viga_lines'] if lay=='VIGAS']
# vertical viga lines (for horizontal VM ends) and horizontal viga lines
vvl = [s for s in vl if abs(s[0]-s[2]) < 0.02 and abs(s[1]-s[3]) > 0.3]
hvl = [s for s in vl if abs(s[1]-s[3]) < 0.02 and abs(s[0]-s[2]) > 0.3]
def runs(vert):
    lines = defaultdict(list)
    for s in segs:
        if vert != (s[4]==90): continue
        c = s[0] if vert else s[1]
        lo, hi = (min(s[1],s[3]),max(s[1],s[3])) if vert else (min(s[0],s[2]),max(s[0],s[2]))
        lines[round(c*10)/10].append((lo,hi,c))
    out = []
    for k, iv in lines.items():
        iv.sort()
        run = [iv[0]]
        for a in iv[1:]:
            if a[0] - run[-1][1] > 0.30:
                out.append((k, run[0][0], max(r[1] for r in run))); run = [a]
            else: run.append(a)
        out.append((k, run[0][0], max(r[1] for r in run)))
    return out
gapc = Counter()
for vert in (False, True):
    faces = vvl if not vert else hvl
    for c, lo, hi in runs(vert):
        for endv, sign in ((lo, -1), (hi, +1)):
            best = None
            for f in faces:
                fc = f[0] if not vert else f[1]
                flo, fhi = (min(f[1],f[3]), max(f[1],f[3])) if not vert else (min(f[0],f[2]), max(f[0],f[2]))
                if not (flo - 0.05 <= c <= fhi + 0.05): continue
                d = (fc - endv) * sign  # positive: viga face beyond VM end
                if abs(d) < 1.0 and (best is None or abs(d) < abs(best)): best = d
            if best is not None:
                gapc[round(best/0.025)*0.025] += 1
print(f"{KIND} run-end -> nearest perpendicular viga face (m, + = face beyond end):")
for v, n in sorted(gapc.items(), key=lambda x:-x[1])[:20]: print(f"  {v:+.3f} : {n}")
print("total ends measured:", sum(gapc.values()))
