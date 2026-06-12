"""Stage 2: extract escoramento geometry from Orguel DXF and compute spacing stats."""
import sys, json, math, re
from collections import Counter, defaultdict
import ezdxf

path = sys.argv[1]
out = sys.argv[2]
# patterns for block-name classification
ESC_PAT = re.compile(r'^(ESC\d+|TRIPEESC|ESCORA)', re.I)
TORRE_PAT = re.compile(r'^(\d{6,}|100100|1541000|1001\d+|1002\d+|TORRE)', re.I)
VM_PAT = re.compile(r'^(VM\d+|ALU\d+|TA)-?(\d+)?', re.I)

doc = ezdxf.readfile(path)
msp = doc.modelspace()

recs = []  # (kind, name, layer, x, y, rot)
dims = []
viga_lines = []  # lines on structural viga layers
for e in msp:
    t = e.dxftype()
    lay = e.dxf.layer
    if t == 'INSERT':
        name = e.dxf.name
        p = e.dxf.insert
        rot = e.dxf.rotation
        sx = e.dxf.xscale
        ll = lay.upper()
        if ll.startswith('ESC') and 'CRUZ' not in name.upper():
            recs.append(('escora', name, lay, p.x, p.y, rot, sx))
        elif 'CRUZ' in name.upper() and 'CORTE' not in name.upper():
            recs.append(('cruzeta', name, lay, p.x, p.y, rot, sx))
        elif ll.startswith('TORRE'):
            recs.append(('torre', name, lay, p.x, p.y, rot, sx))
        elif ll.startswith('VM80') or name.upper().startswith('VM80-'):
            recs.append(('vm80', name, lay, p.x, p.y, rot, sx))
        elif ll.startswith('VM130') or name.upper().startswith('VM130'):
            recs.append(('vm130', name, lay, p.x, p.y, rot, sx))
        elif ll.startswith('VM50') or name.upper().startswith('VM50'):
            recs.append(('vm50', name, lay, p.x, p.y, rot, sx))
        elif ll.startswith('TA_') or name.upper().startswith('TA-') or 'TUBO' in name.upper():
            recs.append(('ta', name, lay, p.x, p.y, rot, sx))
    elif t == 'DIMENSION':
        try:
            m = e.get_measurement()
            if isinstance(m, (int, float)):
                dims.append((lay, round(m, 1)))
        except Exception:
            pass
    elif t in ('LINE',) and lay.upper() in ('VIGAS', 'WP_VIGAS_PLANTA', 'TORRE_VIGA'):
        viga_lines.append((lay, e.dxf.start.x, e.dxf.start.y, e.dxf.end.x, e.dxf.end.y))
    elif t == 'LWPOLYLINE' and lay.upper() in ('VIGAS', 'WP_VIGAS_PLANTA', 'TORRE_VIGA'):
        pts = list(e.get_points('xy'))
        for a, b in zip(pts, pts[1:] + ([pts[0]] if e.closed else [])):
            viga_lines.append((lay, a[0], a[1], b[0], b[1]))

json.dump({'recs': recs, 'dims': dims, 'viga_lines': viga_lines}, open(out, 'w'))
print('recs', len(recs), 'dims', len(dims), 'viga_lines', len(viga_lines))
k = Counter(r[0] for r in recs)
print(k)
