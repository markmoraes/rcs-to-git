#!/usr/bin/python3
# Run RCS rlog command on a bunch of files and parse output to extract
# metadata.
# Cluster that metadata into logical commits and generate git commit messages.
#
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

# Reasonable clustering of RCS revisions into commits is tricky: we try to find
# big separations by time as the obvious demarcation (> 1 hr), or a change of
# author, or the same file already exists in the cluster, or
# a medium separation of time (between smalltimesep and bigtimesep)
# with the same description or revision#?
def rcscluster(rcsmeta, smalltimesep = 10, bigtimesep = 3600, debug = 0):
    """Also returns a dict of revisions by date,
       with key being the dates rounded to nearest timegranularity seconds,
       values are list of revisions tuples, each tuple contains actual date
       working filename, revision#, author and description.
     """
    # first make a flat list of all revisions of all files that we can sort by time
    revsbydate = []
    mintime = sys.float_info.max
    for f in rcsmeta:
        vrfile = f[frfile]
        vwfile = f[fwfile]
        vrevs = f[frevs]
        for rev in vrevs:
            rinfo = vrevs[rev]
            revtime = rinfo[fdt].timestamp()
            mintime = min(mintime, revtime)
            revsbydate.append((revtime, rinfo[fauth], rinfo[fdate], vrfile, rev, vwfile, rinfo[fdesc]))
    # sort by time
    rcscommits = []
    prevtime = mintime
    prevauth = prevdate = prevdesc = prevrev = commit = None
    files = set()
    for revtime, revauth, revdate, vrfile, rev, vwfile, revdesc in sorted(revsbydate):
        dt = revtime - prevtime
        if debug: print(dt, revauth, prevauth, vrfile, vrfile in files, repr(revdesc), repr(prevdesc), rev, prevrev)
        if revauth != prevauth or vrfile in files or \
            (dt > bigtimesep or \
             (dt > smalltimesep and \
              revdesc != prevdesc and rev != prevrev)):
            if prevauth:
                if debug: print("commit", repr((prevauth, prevdate, commit)))
                rcscommits.append((prevauth, prevdate, commit))
            prevauth = revauth
            prevdate = revdate
            files = set()
            descs = set()
            commit = [[], []]
        prevtime = revtime
        prevdesc = revdesc
        prevrev = rev
        files.add(vrfile)
        canondesc = revdesc.strip().lower()
        if canondesc not in descskip and canondesc not in descs:
            commit[0].append(vwfile + ": "+ revdesc)
            descs.add(canondesc)
        commit[1].append((revdate, vrfile, rev, vwfile))
    if prevauth:
        rcscommits.append((prevauth, prevdate, commit))
    return rcscommits

def main():
    if len(sys.argv) == 1 or sys.argv[1].startswith('-'):
        sys.exit("Usage: "+sys.argv[0]+" RCSFILES");
    rmeta = rlogparse(sys.argv[1:])
    if 0:
        pprint(rmeta, compact=True)
    rdate = rcscluster(rmeta, float(os.getenv("GRANULARITY", "600")))
    for d in rdate:
        pprint(d, width=os.get_terminal_size(0).columns)
    return 0
    
if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
