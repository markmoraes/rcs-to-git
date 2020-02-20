#!/usr/bin/python3
# Run RCS rlog command on a bunch of files and parse output to extract
# metadata.
# Intention is to cluster that metadata into logical commits and
# generate git commit messages.
# Mark Moraes, 20200219

import os, sys, subprocess
from datetime import datetime
from pprint import pprint
from collections import defaultdict

fhead = "head"
frfile = "rcs"
fwfile = "file"
frevs = "revs"
fdesc = "desc"
fdate = "date"
fdt = "dt"
fauth = "author"

descskip = set(("initial revision",))

def rlogparse(fnames, debug = 0):
    """Run rlog on fnames and parse the output into a list of per-file
       RCS metadata, with a dict of metadata for each file, each containing
       sub-dict of revision data.
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
    kend = "============================================================================="

    rcsmeta = []
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
                rcsmeta.append(d)
                newfile = True # clears the state above on next line
            elif s == kblockend and inblock != None:
                if inblock == fdesc:
                    if debug>1: print("desc end:", vdesc)
                else:
                    if debug>1: print("rev end:", vrevs[inblock])
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
                dt = datetime.strptime(sdate, '%Y/%m/%d %H:%M:%S')
                assert sauth.startswith(kauth), "no "+kauth+" in "+repr(sauth)
                sauth = sauth[len(kauth)+1:].strip();
                i = sauth.find(';')
                assert i >= 0, "no semicolon in "+repr(sauth)
                sauth = sauth[:i]
                if debug>1: print(krev, vrevnum, krevdate, repr(sdate), kauth, repr(sauth))
                inblock, vrevnum = vrevnum, None
                assert inblock not in vrevs, repr(inblock)
                vrevs[inblock] = {fdesc:"", fauth:sauth, fdate:sdate, fdt:dt}
    if debug: print("read", nf, "files,", nr, "lines")
    return rcsmeta

def rcscluster(rcsmeta, timegranularity, debug = 0):
    """Also returns a dict of revisions by date,
       with key being the dates rounded to nearest timegranularity seconds,
       values are list of revisions tuples, each tuple contains actual date
       working filename, revision#, author and description.
     """
    revsbydate = defaultdict(list)
    files = defaultdict(dict)
    for f in rcsmeta:
        vrfile = f[frfile]
        vwfile = f[fwfile]
        vrevs = f[frevs]
        for r in vrevs:
            rinfo = vrevs[r]
            t = rinfo[fdt].timestamp()
            hr = int(t/timegranularity + 0.5)*timegranularity
            hrstr = datetime.fromtimestamp(hr).isoformat()
            rkey = (hrstr,rinfo[fauth])
            if vrfile in files[rkey]:
                raise RuntimeError("file "+vrfile+" already in "+repr(rkey)+" : "+repr(files[rkey][vrfile])+"\n"+repr(rinfo)+"\nMaybe try lowering GRANULARITY")
            files[rkey][vrfile] = rinfo
            revsbydate[rkey].append((rinfo[fdate],vrfile,r,vwfile,rinfo[fdesc]))
    rcscommits = {}
    for c in sorted(revsbydate):
        commit = [[], []]
        revs = revsbydate[c]
        for r in sorted(revs):
            vdesc = r[-1]
            if vdesc.strip().lower() not in descskip and vdesc not in commit[0]:
                commit[0].append(vdesc)
            commit[1].append(r[:-1])
        rcscommits[c] = commit
    return rcscommits

def main():
    if len(sys.argv) == 1 or sys.argv[1].startswith('-'):
        sys.exit("Usage: "+sys.argv[0]+" RCSFILES");
    rmeta = rlogparse(sys.argv[1:])
    if 0:
        pprint(rmeta, compact=True)
    rdate = rcscluster(rmeta, float(os.getenv("GRANULARITY", "600")))
    for d in sorted(rdate):
        pprint((d, rdate[d]), width=os.get_terminal_size(0).columns)
    return 0
    
if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
