"""Stage 10: print raw sorted coordinates in dense strips to see the actual pattern."""
import sys, json
from collections import Counter, defaultdict

geo = json.load(open(sys.argv[1])); SCALE = float(sys.argv[2])
names = set(sys.argv[3].split(','))
pts = [(round(r[3]*SCALE,3), round(r[4]*SCALE,3), r[1]) for r in geo['recs'] if r[1] in names]
# find densest rows
rows = defaultdict(list)
for x,y,nm in pts: rows[round(y,1)].append((x,nm))
best_rows = sorted(rows.items(), key=lambda kv:-len(kv[1]))[:6]
for y, v in best_rows:
    v.sort()
    print(f"ROW y={y}: " + "  ".join(f"{x:.2f}{'D' if 'FFD' in nm else ''}" for x,nm in v))
cols = defaultdict(list)
for x,y,nm in pts: cols[round(x,1)].append((y,nm))
best_cols = sorted(cols.items(), key=lambda kv:-len(kv[1]))[:6]
for x, v in best_cols:
    v.sort()
    print(f"COL x={x}: " + "  ".join(f"{y:.2f}{'D' if 'FFD' in nm else ''}" for y,nm in v))
# VM80 lines near the densest row, to see relation
vms = [(r[1], round(r[3]*SCALE,2), round(r[4]*SCALE,2), round(r[5])) for r in geo['recs'] if r[0]=='vm80' and r[1].startswith('VM80-')]
y0 = best_rows[0][0]
near = sorted((v for v in vms if abs(v[2]-y0)<0.35 and v[3]%180==0), key=lambda v: v[1])
print(f"\nVM80 horiz near y={y0}:")
for v in near: print('  ', v)
