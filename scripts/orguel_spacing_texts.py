import sys, re, ezdxf
from collections import Counter
doc = ezdxf.readfile(sys.argv[1])
pat = re.compile(r'[Cc]/\s*\d+|CADA\s+\d|@\s*\d+|COMPENSADO|TABELA', re.I)
c = Counter()
def scan(layout, depth=0):
    for e in layout:
        t = e.dxftype()
        if t in ('TEXT','MTEXT','ATTDEF'):
            s = e.plain_text() if t=='MTEXT' else e.dxf.text
            if pat.search(s): c[s.strip()[:160]] += 1
        elif t=='INSERT' and depth < 1:
            try: scan(doc.blocks.get(e.dxf.name), depth+1)
            except Exception: pass
scan(doc.modelspace())
for s, n in c.most_common(60): print(n, '|', s)
