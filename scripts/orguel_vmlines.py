"""Stage 7: build VM segments from inserts, chain collinear lines, relate escoras."""
import sys, json, math, re
from collections import Counter, defaultdict

geo = json.load(open(sys.argv[1]))
SCALE = float(sys.argv[2])
KIND = sys.argv[3] if len(sys.argv) > 3 else 'vm80'
ESC_NAMES = sys.argv[4].split(',') if len(sys.argv) > 4 else None

segs = []  # (x0,y0,x1,y1,ang,name)
for r in geo['recs']:
    if r[0] != KIND: continue
    m = re.match(r'^[A-Z]+\d*-(\d+)', r[1])
    if not m: continue
    L = int(m.group(1)) / 100.0
    x, y = r[3]*SCALE, r[4]*SCALE
    a = math.radians(r[5])
    segs.append((x, y, x + L*math.cos(a), y + L*math.sin(a), round(r[5]) % 360, r[1]))
print(f"{KIND} segments: {len(segs)}; angles: {Counter(s[4]%180 for s in segs).most_common()}")

# horizontal lines: group by y (tol 0.05); vertical: by x
def chain(segs, vert):
    lines = defaultdict(list)  # key rounded coord -> list of (lo,hi)
    for s in segs:
        if vert != (s[4] % 180 == 90): continue
        c = s[0] if vert else s[1]
        lo, hi = (min(s[1], s[3]), max(s[1], s[3])) if vert else (min(s[0], s[2]), max(s[0], s[2]))
        lines[round(c, 1)].append((lo, hi, c))
    # merge keys within 0.05
    keys = sorted(lines)
    merged = []
    for k in keys:
        if merged and k - merged[-1][0] <= 0.051:
            merged[-1][1].extend(lines[k])
        else:
            merged.append([k, list(lines[k])])
    return merged

def analyze(merged, label):
    gaps = Counter(); lens = Counter(); pitches = Counter()
    coords = []
    for k, iv in merged:
        iv.sort()
        coords.append(sum(v[2] for v in iv)/len(iv))
        # chain runs: gap>0.30 new run
        run = [iv[0]]
        for a in iv[1:]:
            g = a[0] - run[-1][1]
            if g > 0.30:
                lens[round((run[-1][1]-run[0][0])/0.05)*0.05] += 1
                run = [a]
            else:
                gaps[round(g/0.05)*0.05] += 1
                run.append(a)
        lens[round((run[-1][1]-run[0][0])/0.05)*0.05] += 1
    coords.sort()
    for a, b in zip(coords, coords[1:]):
        d = b - a
        if 0.10 < d < 4.0: pitches[round(d/0.05)*0.05] += 1
    print(f"\n{label}: {len(merged)} line positions")
    print("  joint gaps (m):", sorted(gaps.items(), key=lambda x:-x[1])[:10])
    print("  run lengths (m):", sorted(lens.items(), key=lambda x:-x[1])[:14])
    print("  line pitch (m):", sorted(pitches.items(), key=lambda x:-x[1])[:16])
    return merged

H = analyze(chain(segs, False), 'horizontal VM lines')
V = analyze(chain(segs, True), 'vertical VM lines')

# escora spacing along lines
esc = [(r[3]*SCALE, r[4]*SCALE) for r in geo['recs'] if r[0]=='escora' and (ESC_NAMES is None or r[1] in ESC_NAMES)]
along = Counter(); offline = 0
for merged, vert in ((H, False), (V, True)):
    for k, iv in merged:
        c = sum(v[2] for v in iv)/len(iv)
        lo = min(v[0] for v in iv); hi = max(v[1] for v in iv)
        on = sorted(p[0 if vert else 1] is None or (p[1] if vert else p[0]) for p in [])
        pts = sorted((p[1] if vert else p[0]) for p in esc
                     if abs((p[0] if vert else p[1]) - c) < 0.12 and lo-0.3 <= (p[1] if vert else p[0]) <= hi+0.3)
        for a, b in zip(pts, pts[1:]):
            d = b - a
            if 0.1 < d < 4.0: along[round(d/0.05)*0.05] += 1
print("\nESC spacing ALONG VM lines:", sorted(along.items(), key=lambda x:-x[1])[:16])
