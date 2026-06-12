import sys, re, ezdxf
doc = ezdxf.readfile(sys.argv[1])
blk = doc.blocks.get(sys.argv[2])
for e in blk:
    if e.dxftype()=='MTEXT':
        s = e.plain_text()
        print(s)
        print('-----')
