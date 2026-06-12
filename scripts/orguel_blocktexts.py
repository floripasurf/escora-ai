import sys, re, ezdxf
doc = ezdxf.readfile(sys.argv[1])
def dump(blk, depth=0):
    for e in blk:
        t = e.dxftype()
        if t in ('TEXT','MTEXT','ATTDEF'):
            s = e.dxf.text if t!='MTEXT' else e.text
            s = re.sub(r'\\[A-Za-z][^;]*;|{|}', '', s).replace('\\P','\n')
            for ln in s.split('\n'):
                ln=ln.strip()
                if ln: print(' '*depth + ln)
        elif t=='INSERT' and depth<2:
            try: dump(doc.blocks.get(e.dxf.name), depth+1)
            except Exception: pass
for name in sys.argv[2:]:
    print(f"\n########## {name} ##########")
    try: dump(doc.blocks.get(name))
    except Exception as ex: print('ERR', ex)
