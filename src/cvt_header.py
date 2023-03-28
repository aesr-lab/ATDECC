#!/usr/bin/env python3
import sys
import re
import pdb

src = sys.argv[1]
dst = sys.argv[2]

lncomment = re.compile(r"^(.*)//.*$")
lnprolong = re.compile(r"^(.*)\\\s*$")
jdksdef = re.compile(r"^\s*#define\s+(JDKSAVDECC_[A-Z_0-9]+)\s+(\(.+\)).*$")

with open(src, 'r') as fsrc:
    with open(dst, 'w') as fdst:
        fln = ""
        for ln in fsrc:
            ln = ln.strip()
            m = lncomment.match(ln)
            if m is not None:
                ln = m.group(1).strip()
                
            m = lnprolong.match(ln)
            if m is not None:
#                print(f"Prolonged {ln}", file=sys.stderr)
                fln += m.group(1).strip()+' '
            else:
                fln += ln
                m = jdksdef.match(fln)
                if m is None:
                    fdst.write(fln+'\n')
                else:
#                    print(f"Matched {fln}", file=sys.stderr)
                    defn = m.group(1).strip()
                    deq = m.group(2).strip()
                    fdst.write(f"enum {{ {defn} = {deq} }};\n")
                fln = ''
