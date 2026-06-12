"""Stage 6: dimension entities with location + text, restricted to a window; also NN per block name."""
import sys, json, math, re
from collections import Counter, defaultdict
import ezdxf

path = sys.argv[1]
x0, y0, x1, y1 = map(float, sys.argv[2:6])  # window in drawing units
doc = ezdxf.readfile(path)
msp = doc.modelspace()
c = Counter()
texts_in_win = Counter()
for e in msp:
    t = e.dxftype()
    try:
        if t == 'DIMENSION':
            p = e.dxf.defpoint
            if not (x0 <= p.x <= x1 and y0 <= p.y <= y1): continue
            m = e.get_measurement()
            if isinstance(m, (int, float)) and 10 <= m <= 400:
                c[(e.dxf.layer, round(m))] += 1
        elif t in ('TEXT', 'MTEXT'):
            p = e.dxf.insert
            if not (x0 <= p.x <= x1 and y0 <= p.y <= y1): continue
            s = e.dxf.text if t == 'TEXT' else e.text
            s = re.sub(r'\\[A-Za-z][^;]*;|{|}|\\P', ' ', s).strip()
            if s: texts_in_win[(e.dxf.layer, s[:90])] += 1
    except Exception:
        pass
print("=== DIMENSIONS in window (layer, cm) ===")
agg = Counter()
for (lay, v), n in c.items(): agg[v] += n
for v, n in sorted(agg.items(), key=lambda x: -x[1])[:40]:
    print(f"{v} cm : {n}")
print("\n=== TEXTS in window ===")
for (lay, s), n in texts_in_win.most_common(80):
    print(n, '|', lay, '|', s)
