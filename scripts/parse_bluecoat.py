"""Parse Blue Coat SGOS W3C ELFF access logs into compact numpy arrays.
Only the first 17 space-separated fields are used (the User-Agent and later fields contain spaces).
Object id = 64-bit hash of host+path (query string dropped). Run with PYTHONHASHSEED=0 for stable ids."""
import sys, os, numpy as np, calendar, time
ACTIONS = {}
def code(tbl, k):
    if k not in tbl: tbl[k] = len(tbl)
    return tbl[k]
src, dst = sys.argv[1], sys.argv[2]
ts, obj, size, act, st, get, cli, taken = [], [], [], [], [], [], [], []
tcache = {}
bad = 0
with open(src, 'rb') as fh:
    for raw in fh:
        if raw[:1] == b'#': continue
        p = raw.decode('latin-1').split(' ', 17)
        if len(p) < 17: bad += 1; continue
        try:
            key = p[0] + p[1][:2]
            if key not in tcache:
                tcache[key] = calendar.timegm(time.strptime(p[0] + ' ' + p[1][:2], '%Y-%m-%d %H'))
            t = tcache[key] + int(p[1][3:5]) * 60 + int(p[1][6:8])
            ts.append(t); obj.append(hash(p[10] + p[11])); size.append(int(p[6]) if p[6].isdigit() else 0)
            act.append(code(ACTIONS, p[5])); st.append(int(p[4]) if p[4].isdigit() else 0)
            get.append(p[8] == 'GET'); cli.append(hash(p[3])); taken.append(int(p[2]) if p[2].isdigit() else 0)
        except Exception:
            bad += 1
np.savez_compressed(dst, ts=np.array(ts, np.int64), obj=np.array(obj, np.int64), size=np.array(size, np.int64),
                    act=np.array(act, np.int16), status=np.array(st, np.int16), get=np.array(get, bool),
                    cli=np.array(cli, np.int64), taken=np.array(taken, np.int32),
                    actions=np.array(sorted(ACTIONS, key=ACTIONS.get)))
print(src, 'rows', len(ts), 'bad', bad)
