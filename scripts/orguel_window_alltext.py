import sys, ezdxf
from ezdxf.math import Vec3
doc = ezdxf.readfile(sys.argv[1])
x0,y0,x1,y1 = map(float, sys.argv[2:6])
msp = doc.modelspace()
items=[]
def add(x,y,s):
    if x0<=x<=x1 and y0<=y<=y1 and s.strip(): items.append((x,y,s.strip()[:140]))
for e in msp:
    t=e.dxftype()
    if t in ('TEXT','MTEXT'):
        p=e.dxf.insert; add(p.x,p.y, e.plain_text() if t=='MTEXT' else e.dxf.text)
    elif t=='INSERT':
        p=e.dxf.insert
        if not (x0-2000<=p.x<=x1+2000 and y0-2000<=p.y<=y1+2000): continue
        for a in e.attribs: add(a.dxf.insert.x, a.dxf.insert.y, a.dxf.text)
        try:
            blk=doc.blocks.get(e.dxf.name)
            import math
            ang=math.radians(e.dxf.rotation); sx=e.dxf.xscale; sy=e.dxf.yscale
            for be in blk:
                bt=be.dxftype()
                if bt in ('TEXT','MTEXT','ATTDEF'):
                    q=be.dxf.insert
                    X=p.x+ (q.x*sx*math.cos(ang)-q.y*sy*math.sin(ang)); Y=p.y+(q.x*sx*math.sin(ang)+q.y*sy*math.cos(ang))
                    add(X,Y, be.plain_text() if bt=='MTEXT' else be.dxf.text)
        except Exception: pass
for x,y,s in sorted(items,key=lambda v:(-round(v[1]/8)*8,v[0])):
    print(f"({x:.0f},{y:.0f}) {s}")
