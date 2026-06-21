import sys, ezdxf
from collections import Counter
doc = ezdxf.readfile(sys.argv[1])
for name in sys.argv[2:]:
    try:
        blk = doc.blocks.get(name)
    except Exception as ex:
        print(name, 'ERR', ex); continue
    print(f"=== {name} (base {blk.base_point}) ===")
    tc = Counter()
    xmin=ymin=1e18; xmax=ymax=-1e18
    for e in blk:
        tc[e.dxftype()] += 1
        try:
            if e.dxftype()=='LINE':
                for p in (e.dxf.start,e.dxf.end):
                    xmin=min(xmin,p.x);xmax=max(xmax,p.x);ymin=min(ymin,p.y);ymax=max(ymax,p.y)
            elif e.dxftype()=='LWPOLYLINE':
                for x,y in e.get_points('xy'):
                    xmin=min(xmin,x);xmax=max(xmax,x);ymin=min(ymin,y);ymax=max(ymax,y)
            elif e.dxftype()=='CIRCLE':
                cc=e.dxf.center;r=e.dxf.radius
                xmin=min(xmin,cc.x-r);xmax=max(xmax,cc.x+r);ymin=min(ymin,cc.y-r);ymax=max(ymax,cc.y+r)
        except Exception: pass
    print(' entities:', dict(tc))
    if xmax>-1e17: print(f" geom bbox: ({xmin:.1f},{ymin:.1f})-({xmax:.1f},{ymax:.1f})")
