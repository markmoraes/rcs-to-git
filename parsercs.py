#!/usr/bin/python3
# Run RCS rlog command on a bunch of files and parse output to extract
# metadata.
# Intention is to cluster that metadata into logical commits and
# generate git commit messages.
# Mark Moraes, 20200219

import os, sys, subprocess
from pprint import pprint
from collections import defaultdict

def rlogparse(fnames, debug = 1):
    """Run rlog on fnames and parse the output into a list of per-file
       RCS metadata, with a dict of metadata for each file, each containing
       sub-dict of revision data
    """
    cmd = ["/usr/bin/rlog"] + fnames
    if debug>1: print(cmd)

    krfile = "RCS file:"
    kwfile = "Working file:"
    khead = "head:"
    kdesc = "description:"
    krev = "revision"
    krevdate = "date:"
    kauth = "author:"
    kblockend = "----------------------------"
    fhead = "head"
    frfile = "rcs"
    fwfile = "file"
    frevs = "revs"
    fdesc = "desc"
    fdate = "date"
    fauth = "author"
    kend = "============================================================================="

    rcsdata = []
    rcsbydate = defaultdict(list)
    with subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE) as p:
        newfile = True
        nr = nf = 0
        for line in p.stdout:
            if newfile:
                vrfile = vwfile = vhead = vdesc = inblock = None
                newfile = False
                vrevs = {}
            nr += 1
            s = line.decode().rstrip('\n')
            if debug>1: print("read", repr(s))
            if s == kend:
                d = {frfile:vrfile, fwfile:vwfile, fhead:vhead, fdesc:vdesc, frevs:vrevs}
                rcsdata.append(d)
                newfile = True # clears the state above on next line
            elif s == kblockend and inblock != None:
                if inblock == fdesc:
                    if debug>1: print("desc end:", vdesc)
                else:
                    if debug>1: print("rev end:", vrevs[inblock])
                    rcsbydate[vrevs[inblock][fdate]].append((vwfile,inblock,vrevs[inblock][fauth],vrevs[inblock][fdesc]))
                inblock = None
            elif inblock != None:
                if inblock == fdesc:
                    vdesc += s + '\n'
                else:
                    vrevs[inblock][fdesc] += s + '\n'
            elif s.startswith(krfile):
                vrfile = s[len(krfile)+1:].strip()
                if debug>1: print(krfile, vrfile)
                nf += 1
            elif s.startswith(kwfile):
                vwfile = s[len(kwfile)+1:].strip()
                if debug>1: print(kwfile, vwfile)
            elif s.startswith(khead):
                vhead = s[len(khead)+1:].strip()
                if debug>1: print(khead, vhead)
            elif s.startswith(kdesc):
                inblock = fdesc
                vdesc = ''
            elif s.startswith(krev):
                vrevnum = s[len(krev)+1:].strip();
                i = vrevnum.find('\t')
                if i >= 0:
                    vrevnum = vrevnum[:i]
                if debug>1: print(krev, repr(vrevnum))
            elif s.startswith(krevdate):
                sdate = s[len(krevdate)+1:].strip()
                i = sdate.find(';')
                assert i >= 0, "no semicolon in "+repr(sdate)
                sauth = sdate[i+1:].strip()
                sdate = sdate[:i]
                assert sauth.startswith(kauth), "no "+kauth+" in "+repr(sauth)
                sauth = sauth[len(kauth)+1:].strip();
                i = sauth.find(';')
                assert i >= 0, "no semicolon in "+repr(sauth)
                sauth = sauth[:i]
                if debug>1: print(krev, vrevnum, krevdate, repr(sdate), kauth, repr(sauth))
                inblock, vrevnum = vrevnum, None
                assert inblock not in vrevs, repr(inblock)
                vrevs[inblock] = {fdesc:"", fauth:sauth, fdate:sdate}
    if debug: print("read", nf, "files,", nr, "lines")
    return rcsdata, rcsbydate

def main():
    if len(sys.argv) == 1 or sys.argv[1].startswith('-'):
        sys.exit("Usage: "+sys.argv[0]+" RCSFILES");
    rmeta, rdate = rlogparse(sys.argv[1:], debug=1)
    if 0:
        pprint(rmeta, compact=True)
    if 1:
        pprint(rdate, compact=True)
    return 0
    
if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
