import sys, re, math, ezdxf
doc = ezdxf.readfile(sys.argv[1])
target = sys.argv[2]
R = float(sys.argv[3])
msp = doc.modelspace()
anchors = []
items = []
for e in msp:
    t = e.dxftype()
    if t in ('TEXT','MTEXT'):
        s = e.plain_text() if t=='MTEXT' else e.dxf.text
        p = e.dxf.insert
        items.append((p.x, p.y, s))
        if target.lower() in s.lower(): anchors.append((p.x, p.y))
for ax, ay in anchors:
    print(f"### anchor at ({ax:.0f},{ay:.0f})")
    near = [(y, x, s) for x, y, s in items if abs(x-ax) < R and abs(y-ay) < R]
    for y, x, s in sorted(near, key=lambda v: (-v[0], v[1])):
        print(f"  ({x:.0f},{y:.0f}) {s.strip()[:120]}")
