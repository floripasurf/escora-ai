"""Part 2: combined inventory + geometry extraction in ONE ezdxf read.

Usage: python3 scripts/orguel_extract_all.py <dxf> <tag>
Writes output/orguel_analysis/inv_<tag>.json and geo_<tag>.json
"""
import sys, json, re
from collections import Counter, defaultdict
import ezdxf

path, tag = sys.argv[1], sys.argv[2]
OUT = "output/orguel_analysis"
doc = ezdxf.readfile(path)
msp = doc.modelspace()

kw = re.compile(r'(ESC|VM\s*\d|TORRE|CIMB|BARROTE|GUIA|[Cc]/\s*\d|CRUZETA|FORCADO|'
                r'PAINEL|COMPENSADO|ALU|H20|TRIP|REESC|MECANOR|GS|PONTAL|ESCORAMENTO)', re.I)

ESCORAMENTO_LAYER_PREFIX = ('ESC', 'VM', 'TORRE', 'TA', 'SF', 'TIRANTE', 'BARRA', 'GS', 'ALU', 'PONTAL')

layer_counter = Counter()
insert_counter = Counter()
insert_layer = defaultdict(Counter)
texts = Counter()
recs = []   # (kind, name, layer, x, y, rot, xscale)
dims = []
viga_lines = []
n = 0
xmin = ymin = float('inf'); xmax = ymax = float('-inf')

for e in msp:
    n += 1
    t = e.dxftype()
    lay = e.dxf.layer
    layer_counter[lay] += 1
    if t == 'INSERT':
        name = e.dxf.name
        insert_counter[name] += 1
        insert_layer[name][lay] += 1
        p = e.dxf.insert
        xmin = min(xmin, p.x); xmax = max(xmax, p.x)
        ymin = min(ymin, p.y); ymax = max(ymax, p.y)
        rot = e.dxf.rotation
        sx = e.dxf.xscale
        ll = lay.upper(); nu = name.upper()
        if (ll.startswith('ESC') or nu.startswith('ESC')) and 'CRUZ' not in nu:
            recs.append(('escora', name, lay, p.x, p.y, rot, sx))
        elif 'CRUZ' in nu and 'CORTE' not in nu:
            recs.append(('cruzeta', name, lay, p.x, p.y, rot, sx))
        elif ll.startswith('TORRE') or re.match(r'^\d{6,7}(\+\d+)?$|^\d{6}\+', nu):
            recs.append(('torre', name, lay, p.x, p.y, rot, sx))
        elif ll.startswith('VM80') or nu.startswith('VM80'):
            recs.append(('vm80', name, lay, p.x, p.y, rot, sx))
        elif ll.startswith('VM130') or nu.startswith('VM130'):
            recs.append(('vm130', name, lay, p.x, p.y, rot, sx))
        elif ll.startswith('VM50') or nu.startswith('VM50'):
            recs.append(('vm50', name, lay, p.x, p.y, rot, sx))
        elif ll.startswith('TA_') or nu.startswith('TA-') or 'TUBO' in nu:
            recs.append(('ta', name, lay, p.x, p.y, rot, sx))
        elif nu.startswith('GS') or nu.startswith('ALU') or nu.startswith('H20'):
            recs.append(('guia_outro', name, lay, p.x, p.y, rot, sx))
    elif t in ('TEXT', 'MTEXT'):
        try:
            s = e.plain_text() if t == 'MTEXT' else e.dxf.text
        except Exception:
            s = ''
        s = re.sub(r'\\[A-Za-z][^;]*;|{|}', '', s)[:140].strip()
        if s and kw.search(s):
            texts[(lay, s)] += 1
    elif t == 'DIMENSION':
        try:
            m = e.get_measurement()
            if isinstance(m, (int, float)):
                p = e.dxf.defpoint
                dims.append((lay, round(m, 1), round(p.x, 1), round(p.y, 1)))
        except Exception:
            pass
    if t in ('LINE', 'LWPOLYLINE'):
        lu = lay.upper()
        if 'VIGA' in lu and not lu.startswith(ESCORAMENTO_LAYER_PREFIX):
            if t == 'LINE':
                viga_lines.append((lay, e.dxf.start.x, e.dxf.start.y, e.dxf.end.x, e.dxf.end.y))
            else:
                pts = list(e.get_points('xy'))
                for a, b in zip(pts, pts[1:] + ([pts[0]] if e.closed else [])):
                    viga_lines.append((lay, a[0], a[1], b[0], b[1]))
        if t == 'LINE':
            for p in (e.dxf.start, e.dxf.end):
                xmin = min(xmin, p.x); xmax = max(xmax, p.x)
                ymin = min(ymin, p.y); ymax = max(ymax, p.y)

inv = {
    'path': path, 'n_entities': n,
    'bbox': [xmin, ymin, xmax, ymax],
    'layers': layer_counter.most_common(80),
    'inserts': insert_counter.most_common(150),
    'insert_layers': {k: dict(v) for k, v in list(insert_layer.items())[:200]},
    'text_samples': [[lay, s, cnt] for (lay, s), cnt in texts.most_common(250)],
}
json.dump(inv, open(f"{OUT}/inv_{tag}.json", 'w'), ensure_ascii=False, indent=1)
json.dump({'recs': recs, 'dims': [(d[0], d[1]) for d in dims], 'dims_xy': dims,
           'viga_lines': viga_lines},
          open(f"{OUT}/geo_{tag}.json", 'w'))
print(f"[{tag}] entities={n} recs={len(recs)} dims={len(dims)} viga_lines={len(viga_lines)}")
print(f"[{tag}] bbox= {xmin:.0f},{ymin:.0f} .. {xmax:.0f},{ymax:.0f}")
print(f"[{tag}] kinds:", Counter(r[0] for r in recs))
