#!/usr/bin/env python3
"""Gör lm_uppsala.json av Lantmäteriets Topografi 100 Nedladdning vektor (lagret Ledningar, GeoPackage).

Användning: python3 tools/lm_till_json.py ledningar_ln01.gpkg ledningar_ln03.gpkg ... [--ut lm_uppsala.json]
Behöver pyproj och numpy. Lagren som används: ledningslinje (1702 stam, 1703 region),
transformatoromrade och transformatoromradespunkt (stationer, exakta lägen).
Stationer nära en stamnätsledning blir stamnätsstationer (G), övriga regionnätsstationer (R).
Vattenfalls stationer (vattenfall_ref.json) flyttas till närmaste station i filerna (högst 5 km).
"""
import sqlite3, struct, json, sys, os, collections
import numpy as np
from pyproj import Transformer
from matplotlib.path import Path as MP

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
s = open(os.path.join(ROOT, 'map.js'), encoding='utf-8').read()
M = json.loads(s[s.index('{'):s.rindex('}') + 1]); P = M['proj']; PXKM = M['pxPerKm']
T = Transformer.from_crs(3006, 4326, always_xy=True)

def px(x, y):
    lon, lat = T.transform(x, y)
    return ((lon - P['minx']) * P['k'] * P['sx'], (P['maxy'] - lat) * P['sx'])

def geom(g):
    env = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(g[3] >> 1) & 7]; b = g[8 + env:]
    def rd(o):
        bo = '<' if b[o] == 1 else '>'; t = struct.unpack(bo + 'I', b[o + 1:o + 5])[0] % 1000; o += 5
        if t == 1: return [[struct.unpack(bo + 'dd', b[o:o + 16])]], o + 16
        if t == 2:
            n = struct.unpack(bo + 'I', b[o:o + 4])[0]; o += 4
            return [[struct.unpack(bo + 'dd', b[o + 16 * i:o + 16 * i + 16]) for i in range(n)]], o + 16 * n
        if t == 3:
            nr = struct.unpack(bo + 'I', b[o:o + 4])[0]; o += 4; rings = []
            for _ in range(nr):
                n = struct.unpack(bo + 'I', b[o:o + 4])[0]; o += 4
                rings.append([struct.unpack(bo + 'dd', b[o + 16 * i:o + 16 * i + 16]) for i in range(n)]); o += 16 * n
            return rings, o
        if t in (4, 5, 6):
            n = struct.unpack(bo + 'I', b[o:o + 4])[0]; o += 4; out = []
            for _ in range(n):
                r, o = rd(o); out += r
            return out, o
        raise ValueError(t)
    return rd(0)[0]

def rdp(p, e):
    p = np.array(p)
    if len(p) < 3: return p
    a, b = p[0], p[-1]; ab = b - a; n = np.hypot(*ab)
    d = np.abs(ab[0] * (p[:, 1] - a[1]) - ab[1] * (p[:, 0] - a[0])) / n if n > 0 else np.hypot(*(p - a).T)
    i = d.argmax()
    if d[i] > e: return np.vstack([rdp(p[:i + 1], e)[:-1], rdp(p[i:], e)])
    return np.array([a, b])

def merge_chains(parts, tol=1.5):
    """Slår ihop ledningsbitar som möts i exakt två ändar (utan T-koppling)."""
    key = lambda p: (round(p[0] / tol), round(p[1] / tol))
    parts = [list(map(tuple, p)) for p in parts]
    changed = True
    while changed:
        changed = False
        ends = collections.defaultdict(list)
        for i, p in enumerate(parts):
            if p is None: continue
            ends[key(p[0])].append((i, 0)); ends[key(p[-1])].append((i, 1))
        for k, v in ends.items():
            if len(v) == 2 and v[0][0] != v[1][0]:
                (i, ei), (j, ej) = v
                a = parts[i] if ei == 1 else parts[i][::-1]
                b = parts[j] if ej == 0 else parts[j][::-1]
                parts[i] = a + b[1:]; parts[j] = None; changed = True; break
    return [p for p in parts if p]

def main():
    args = sys.argv[1:]; out = os.path.join(ROOT, 'lm_uppsala.json')
    if '--ut' in args: i = args.index('--ut'); out = args[i + 1]; del args[i:i + 2]
    lines, areas, pts = {}, {}, {}
    for f in args:
        c = sqlite3.connect(f)
        for g, oid, t in c.execute("select geom,objektidentitet,objekttypnr from ledningslinje"):
            lines[oid] = (t, [[px(*p) for p in part] for part in geom(g)])
        for g, oid in c.execute("select geom,objektidentitet from transformatoromrade"):
            areas[oid] = [[px(*p) for p in r] for r in geom(g)]
        for g, oid in c.execute("select geom,objektidentitet from transformatoromradespunkt"):
            pts[oid] = px(*geom(g)[0][0])
    polys = {p['name']: [np.array([[float(v) for v in q.split()] for q in sub.replace('Z', '').split('L') if q.strip()]) for sub in p['d'].split('M')[1:]]
             for p in M['paths'] if p.get('in')}
    mps = [MP(sub) for subs in polys.values() for sub in subs]
    inlan = lambda pt: any(m.contains_point(pt) for m in mps)
    # stationer: punkter, samt områden utan punkt
    apaths = {o: MP(np.array(r[0])) for o, r in areas.items()}
    used = set(); st = []
    for p in pts.values():
        a = [k for k, mp in apaths.items() if mp.contains_point(p)]; used.update(a); st.append(p)
    for o, r in areas.items():
        if o not in used: st.append(tuple(np.mean(np.array(r[0]), axis=0)))
    st = [p for p in st if inlan(p)]
    merged = []
    for p in st:   # slå ihop stationer närmare än 1 km
        for q in merged:
            if np.hypot(p[0] - q[0], p[1] - q[1]) < 1.0 * PXKM: break
        else: merged.append(p)
    # linjer: slå ihop kedjor per typ, förenkla, behåll de som syns i kartan
    by = {1702: [], 1703: []}
    for t, parts in lines.values(): by[t] += parts
    outl = []; sp = []
    def clip_lan(q):
        """Behåller bara de delar av en regionnätsledning som ligger i länet (plus en punkt utanför per ände)."""
        d = []   # tätare punkter så att länsgränsen träffas någorlunda
        for a_, b_ in zip(q[:-1], q[1:]):
            n = max(1, int(np.hypot(b_[0] - a_[0], b_[1] - a_[1]) / (0.7 * PXKM)))
            d += [(a_[0] + (b_[0] - a_[0]) * i / n, a_[1] + (b_[1] - a_[1]) * i / n) for i in range(n)]
        d.append(tuple(q[-1]))
        ins = [inlan(p) for p in d]; runs = []; i = 0
        while i < len(d):
            if ins[i]:
                j = i
                while j + 1 < len(d) and ins[j + 1]: j += 1
                runs.append(d[max(0, i - 1):min(len(d), j + 2)]); i = j + 1
            else: i += 1
        return runs
    for t, parts in by.items():
        for q in merge_chains(parts):
            if t == 1703:
                for r in clip_lan(q):
                    r = rdp(r, 0.8)
                    if len(r) >= 2: outl.append({'v': 70, 'd': 'M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in r)})
                continue
            q = rdp(q, 0.8)
            if not any(0 <= x <= M['w'] and 0 <= y <= M['h'] for x, y in q): continue
            outl.append({'v': 400 if t == 1702 else 70, 'd': 'M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in q)})
            if t == 1702:
                for a, b in zip(q[:-1], q[1:]):
                    n = max(1, int(np.hypot(*(b - a)) / 1.5)); sp += [a + (b - a) * i / n for i in range(n)]
    from scipy.spatial import cKDTree
    ts = cKDTree(np.array(sp))
    G = [p for p in merged if ts.query(p)[0] / PXKM < 0.5]; R = [p for p in merged if ts.query(p)[0] / PXKM >= 0.5]
    # Vattenfall: flytta till närmaste station
    vf = json.load(open(os.path.join(ROOT, 'vattenfall_ref.json')))
    allst = np.array(G + R); extra = []
    for c in vf:
        d = np.hypot(*(allst - np.array([c['x'], c['y']])).T) / PXKM; i = d.argmin()
        if d[i] <= 5: c['x'], c['y'] = round(allst[i][0]), round(allst[i][1]); c['snap'] = True
        else:
            c['snap'] = False; extra.append((c['x'], c['y']))
    json.dump(vf, open(os.path.join(ROOT, 'vattenfall_ref.json'), 'w'), ensure_ascii=False)
    R += extra   # Vattenfall-stationer utan station i filerna (ungefärligt läge)
    fm = lambda p: [round(p[0]), round(p[1]), '']
    json.dump({'src': 'lm', 'stations': [fm(p) for p in G], 'rstations': [fm(p) for p in R], 'lines': outl}, open(out, 'w'), separators=(',', ':'))
    print(len(G), 'stamnätsstationer,', len(R), 'regionnätsstationer (varav', len(extra), 'från Vattenfall utan träff),', len(outl), 'ledningar,', os.path.getsize(out) // 1024, 'kB')
main()
