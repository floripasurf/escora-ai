import sys, json, math
from collections import Counter
geo = json.load(open(sys.argv[1])); SCALE=float(sys.argv[2])
for lay in ('TORRE_LAJE','TORRE_VIGA','Torre_Laje','TORRE_VIGA'):
    pts = [(r[3]*SCALE, r[4]*SCALE, r[1]) for r in geo['recs'] if r[0]=='torre' and r[2]==lay and 'Console' not in r[1] and 'CONS' not in r[1]]
    if not pts: continue
    nn = Counter()
    for i,(x,y,_) in enumerate(pts):
        best=None
        for j,(x2,y2,_) in enumerate(pts):
            if i==j: continue
            d=math.hypot(x2-x,y2-y)
            if best is None or d<best: best=d
        if best and best<6: nn[round(best/0.05)*0.05]+=1
    print(lay, len(pts), Counter(p[2] for p in pts))
    print('  NN:', sorted(nn.items(), key=lambda x:-x[1])[:12])
