"""Exploratory inventory of an Orguel DXF: layers, blocks, texts, bbox."""
import sys, json, re
from collections import Counter, defaultdict
import ezdxf

path = sys.argv[1]
out = sys.argv[2]
doc = ezdxf.readfile(path)
msp = doc.modelspace()

layer_counter = Counter()
type_by_layer = defaultdict(Counter)
insert_counter = Counter()
insert_layer = defaultdict(Counter)
texts = []
kw = re.compile(r'(ESC|VM\s*\d|VM80|VM130|VM50|TORRE|CIMB|FORMA|BARROTE|GUIA|C/\s*\d|c/\s*\d|CRUZETA|FORCADO|PAINEL|COMPENSADO|ALU|H20|PROP|SHORING)', re.I)
n = 0
xmin = ymin = float('inf'); xmax = ymax = float('-inf')
for e in msp:
    n += 1
    lay = e.dxf.layer
    t = e.dxftype()
    layer_counter[lay] += 1
    type_by_layer[lay][t] += 1
    if t == 'INSERT':
        name = e.dxf.name
        insert_counter[name] += 1
        insert_layer[name][lay] += 1
        p = e.dxf.insert
        xmin = min(xmin, p.x); xmax = max(xmax, p.x)
        ymin = min(ymin, p.y); ymax = max(ymax, p.y)
    elif t in ('TEXT', 'MTEXT'):
        s = e.dxf.text if t == 'TEXT' else e.text
        s = re.sub(r'\\[A-Za-z][^;]*;|{|}', '', s)[:120]
        if kw.search(s):
            texts.append((lay, s.strip()))
    elif t == 'LINE':
        for p in (e.dxf.start, e.dxf.end):
            xmin = min(xmin, p.x); xmax = max(xmax, p.x)
            ymin = min(ymin, p.y); ymax = max(ymax, p.y)

res = {
 'path': path, 'n_entities': n,
 'bbox': [xmin, ymin, xmax, ymax],
 'layers': layer_counter.most_common(),
 'types_by_layer': {k: dict(v) for k, v in type_by_layer.items()},
 'inserts': insert_counter.most_common(),
 'insert_layers': {k: dict(v) for k, v in insert_layer.items()},
 'text_samples': [list(x) for x in Counter(texts).most_common(200)],
}
with open(out, 'w') as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print('entities', n, 'layers', len(layer_counter), 'block-names', len(insert_counter))
print('bbox', xmin, ymin, xmax, ymax)
