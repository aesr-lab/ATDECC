#!/usr/bin/env python3
import sys
import re
from functools import reduce

src = sys.argv[1]
dst = sys.argv[2]

lncomment = re.compile(r"^(.*)//(.*)$")
lnprolong = re.compile(r"^(.*)\\\s*$")
jdksdef = re.compile(r"^\s*#define\s+(JDKSAVDECC_[A-Z_0-9]+)\s+(\(.+\)).*$")

def reduce_str(s1, s2):
    """
    Find common beginning of two strings
    """
    common = []
    for c1, c2 in zip(s1, s2):
        if c1 == c2:
            common.append(c1)
        else:
            break
    return ''.join(common)


def cnv_to_enum(defs):
    """
    Generate enum from definitions
    """
    # use common string for enum naming
    common = reduce(reduce_str, (d for d,_ in defs))
    if common:
        common = "e_"+common
#    common = ''
        
    return f"enum {common} {{\n"+ \
           "\n".join(f"{d1} = {d2}," for d1,d2 in defs)+ \
           "\n};"


def conversion(fsrc):
    fln = ""
    defs = []
    
    for ln in fsrc:
        ln = ln.strip()
        cnv = True
        
        # check for end-of-line comment: //
        m = lncomment.match(ln)
        if m is not None:
            ln = m.group(1).strip()
            if "NO CONVERSION" in m.group(2):
                cnv = False
            
        # check if line will be continued: /
        m = lnprolong.match(ln)
        if m is not None:
            fln += m.group(1).strip()+' '
            continue

        fln += ln
        # check if line contains a definition
        m = jdksdef.match(fln)
        if m is None or not cnv:
            # we have not found a convertible line
            # convert and output the previously found defs
            if len(defs):
                yield cnv_to_enum(defs)
                defs = []
            yield fln
        else:
            # add convertible definition to list
            defs.append((m.group(1).strip(), m.group(2).strip()))
        fln = ''
        
    if len(defs):
        yield cnv_to_enum(defs)


with open(src, 'r') as fsrc:
    with open(dst, 'w') as fdst:
        for res in conversion(fsrc):
            fdst.write(res+'\n')
