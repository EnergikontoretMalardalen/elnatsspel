#!/usr/bin/env python3
"""Gör lm_uppsala.json av Lantmäteriets Topografi 100 Nedladdning vektor (lagret Ledningar, GeoPackage).

Användning: python3 tools/lm_till_json.py ledningar_ln01.gpkg ledningar_ln03.gpkg ... [--ut lm_uppsala.json]
Behöver pyproj och numpy. Lagren som används: ledningslinje (1702 stam, 1703 region),
transformatoromrade och transformatoromradespunkt (stationer, exakta lägen; stationernas lägen finns enbart i Topografi 50).
Stationer nära en stamnätsledning blir stamnätsstationer (G), övriga regionnätsstationer (R).
Glapp på högst 10 km mellan delar av regionnätet överbryggas (antagen markkabel, k:1).
Vattenfalls stationer (vattenfall_ref.json) flyttas till närmaste station i filerna (högst 5 km); de som saknar station i filerna tas bort.
"""
import sqlite3, struct, json, sys, os, collections, re
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
    def dens(q):
        d = []   # tätare punkter så att länsgränsen träffas någorlunda
        for a_, b_ in zip(q[:-1], q[1:]):
            n = max(1, int(np.hypot(b_[0] - a_[0], b_[1] - a_[1]) / (0.7 * PXKM)))
            d += [(a_[0] + (b_[0] - a_[0]) * i / n, a_[1] + (b_[1] - a_[1]) * i / n) for i in range(n)]
        d.append(tuple(q[-1]))
        return d
    def clip_lan(q):
        """Delar upp en regionnätsledning i sträckor i länet och 'svansar' utanför.
        Returnerar (sträckor, svansar). En sträcka är i länet plus en punkt utanför per ände. En ledning som lämnar
        länet och kommer tillbaka inom 30 km behålls hel. En svans är den del som går från länsgränsen ut till
        ledningens ände (en station utanför länet)."""
        d = dens(q); ins = [inlan(p) for p in d]; runs = []; i = 0
        while i < len(d):
            if ins[i]:
                j = i
                while j + 1 < len(d) and ins[j + 1]: j += 1
                runs.append((max(0, i - 1), min(len(d), j + 2))); i = j + 1
            else: i += 1
        merged = []
        for r in runs:
            if merged and r[0] - merged[-1][1] <= 43: merged[-1] = (merged[-1][0], r[1])
            else: merged.append(r)
        tails = []
        if merged:
            if merged[0][0] > 0: tails.append(('start', d[:merged[0][0] + 1][::-1]))   # från gränsen ut till änden
            if merged[-1][1] < len(d): tails.append(('end', d[merged[-1][1] - 1:]))
        return [d[i:j] for i, j in merged], tails, d, merged
    reg_in, reg_tails, reg_out = [], [], []; sp_all = []
    for t, parts in by.items():
        for q in merge_chains(parts):
            if t == 1703:
                runs, tails, d, mg = clip_lan(q)
                if not runs:
                    reg_out.append(dens(q)); continue
                for k, r in enumerate(runs):
                    reg_in.append({'run': r, 'first': k == 0, 'last': k == len(runs) - 1})
                for side, tl in tails: reg_tails.append((side, tl, len(reg_in) - (len(runs) if side == 'start' else 1)))
                continue
            q = rdp(q, 0.8)
            if t == 1702: sp_all += dens(q)
            if not any(0 <= x <= M['w'] and 0 <= y <= M['h'] for x, y in q): continue
            outl.append({'v': 400 if t == 1702 else 70, 'd': 'M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in q)})
            if t == 1702:
                for a, b in zip(q[:-1], q[1:]):
                    n = max(1, int(np.hypot(*(b - a)) / 1.5)); sp += [a + (b - a) * i / n for i in range(n)]
    # utflykter utanför länet: behåll svansar och ledningar helt utanför länet om de tillsammans förbinder
    # minst två ställen på länsgränsen (t.ex. en ledning via en station i Stockholms län)
    TOL = 8.0; LIM = 40 * PXKM
    plen = lambda q: sum(np.hypot(q[k][0] - q[k - 1][0], q[k][1] - q[k - 1][1]) for k in range(1, len(q)))
    nodes = []   # klusterpunkter
    def node(p):
        for n, c in enumerate(nodes):
            if np.hypot(p[0] - c[0], p[1] - c[1]) <= TOL: return n
        nodes.append(tuple(p)); return len(nodes) - 1
    edges = []   # (nodA, nodB, polyline, art, ref)
    for side, tl, ri in reg_tails:
        far = tl[-1]; edges.append((('T', ri, side), node(far), tl))
    for q in reg_out: edges.append((('O',), node(q[0]), q)); edges[-1] = (('O',), (node(q[0]), node(q[-1])), q)
    import heapq
    adj = collections.defaultdict(list)
    for idx, (a, e, q) in enumerate(edges):
        if a[0] == 'O':
            w = plen(q); adj[e[0]].append((e[1], w, idx)); adj[e[1]].append((e[0], w, idx))
    tl_idx = [i for i, (a, e, q) in enumerate(edges) if a[0] == 'T']
    accepted = set(); pairs = []
    def dijk(src, dst, lim):
        dist = {src: 0.0}; prev = {}; hp = [(0.0, src)]
        while hp:
            dd, u = heapq.heappop(hp)
            if dd > dist.get(u, 1e18) or dd > lim: continue
            if u == dst: break
            for v, w, ei in adj[u]:
                nd = dd + w
                if nd < dist.get(v, 1e18) and nd <= lim: dist[v] = nd; prev[v] = (u, ei); heapq.heappush(hp, (nd, v))
        if dst not in dist: return None
        path = []; u = dst
        while u != src: u, ei = prev[u]; path.append(ei)
        return path
    for x in range(len(tl_idx)):
        for y in range(x + 1, len(tl_idx)):
            ix, iy = tl_idx[x], tl_idx[y]
            if edges[ix][0][1:] == edges[iy][0][1:]: continue
            lim = LIM - plen(edges[ix][2]) - plen(edges[iy][2])
            if lim < 0: continue
            path = dijk(edges[ix][1], edges[iy][1], lim)
            if path is not None: accepted.update([ix, iy] + path); pairs.append((ix, iy))
    # kopiera nodernas lägen så att ändarna sammanfaller exakt
    for idx in accepted:
        a, e, q = edges[idx]
        if a[0] == 'O':
            q = [nodes[e[0]]] + list(q[1:-1]) + [nodes[e[1]]]
            r = rdp(q, 0.8); outl.append({'v': 70, 'd': 'M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in r)})
    # svansar som slutar vid ett stamnätsställe utanför länet blir anslutningar till grannlänets stamnät (flaggan x)
    from scipy.spatial import cKDTree as _KD
    _st = _KD(np.array(sp_all)); xt = {}
    for side, tl, ri in reg_tails:
        far = tl[-1]
        tix = [i for i in tl_idx if edges[i][0][1:] == (ri, side)][0]
        if tix in accepted:
            # svans som redan är förbunden med en annan svans (slinga via ett ställe utanför länet): blir ändå en
            # anslutning utanför länet om den slutar vid ett stamnätsställe och den andra änden inte gör det
            near = lambda q: _st.query(q)[0] / PXKM <= 0.5
            partners = [edges[y if x == tix else x][2][-1] for x, y in pairs if tix in (x, y)]
            if not (near(far) and partners and not any(near(p) for p in partners)): continue
        if _st.query(far)[0] / PXKM <= 1.5 and plen(tl) <= 50 * PXKM: xt[(ri, side)] = list(tl)
    ext = {}   # (ref, side) -> svans med slutpunkt i klustret
    for idx in accepted:
        a, e, q = edges[idx]
        if a[0] == 'T': ext[(a[1], a[2])] = list(q[:-1]) + [nodes[e]]
    for ri, rr in enumerate(reg_in):
        r = list(rr['run'])
        if (ri, 'start') in ext and (ri, 'start') not in xt: r = ext[(ri, 'start')][::-1] + r[1:]
        if (ri, 'end') in ext and (ri, 'end') not in xt: r = r[:-1] + ext[(ri, 'end')]
        xf = None
        if (ri, 'start') in xt: r = xt[(ri, 'start')][::-1] + r[1:]; xf = ('start', r[0])
        elif (ri, 'end') in xt: r = r[:-1] + xt[(ri, 'end')]; xf = ('end', r[-1])
        r = rdp(r, 0.8)
        if len(r) >= 2:
            ln = {'v': 70, 'd': 'M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in r)}
            if xf: ln.update({'x': 1, 'xs': xf[0], 'xe': [round(min(M['w'] - 51, max(51, xf[1][0]))), round(min(M['h'] - 19, max(19, xf[1][1])))]})
            outl.append(ln)
    # glapp i regionnätet: ledningar som går i kabel i mark syns inte i Lantmäteriets data. Små glapp (högst 10 km)
    # mellan två fristående delar av regionnätet överbryggas med en rak ledning (k:1 = antagen markkabel).
    GAP = 10 * PXKM; TJ = 4.0
    def pts_of(l): return [tuple(map(float, m)) for m in re.findall(r'([\d.]+) ([\d.]+)', l['d'])]
    rl = [(l, pts_of(l)) for l in outl if l['v'] == 70]
    par = list(range(len(rl)))
    def fnd(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for i, (_, p) in enumerate(rl):
        for j, (_, q) in enumerate(rl):
            if i < j and (any(np.hypot(a[0] - b[0], a[1] - b[1]) <= TJ for a in (p[0], p[-1]) for b in q)
                          or any(np.hypot(a[0] - b[0], a[1] - b[1]) <= TJ for a in (q[0], q[-1]) for b in p)): par[fnd(i)] = fnd(j)
    while True:
        best = None
        for i, (l, p) in enumerate(rl):
            for e in (0, len(p) - 1):
                if l.get('x') and l.get('xs') == ('start' if e == 0 else 'end'): continue
                a = p[e]
                if any(j != i and any(np.hypot(a[0] - b[0], a[1] - b[1]) <= TJ for b in q) for j, (_, q) in enumerate(rl)): continue
                for j, (_, q) in enumerate(rl):
                    if fnd(j) == fnd(i): continue
                    for b in q:
                        dd = np.hypot(a[0] - b[0], a[1] - b[1])
                        if dd <= GAP and (best is None or dd < best[0]): best = (dd, i, j, a, b)
        if not best: break
        dd, i, j, a, b = best; par[fnd(i)] = fnd(j)
        outl.append({'v': 70, 'k': 1, 'd': f'M{a[0]:.1f} {a[1]:.1f}L{b[0]:.1f} {b[1]:.1f}'})
        print(f'kabelglapp {dd / PXKM:.1f} km överbryggat vid ({a[0]:.0f},{a[1]:.0f})-({b[0]:.0f},{b[1]:.0f})')
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
    # Vattenfall-stationer utan station i Lantmäteriets filer tas inte med (läget går inte att kontrollera i kartdata)
    vf = [c for c in vf if c['snap']]; json.dump(vf, open(os.path.join(ROOT, 'vattenfall_ref.json'), 'w'), ensure_ascii=False)
    # stationer som bara har anslutning utanför länet (Stockholm) tas bort efter handpåläggning
    EXKL = [(319, 776)]
    R = [p for p in R if not any(abs(p[0] - x) <= 3 and abs(p[1] - y) <= 3 for x, y in EXKL)]
    fm = lambda p: [round(p[0]), round(p[1]), '']
    json.dump({'src': 'lm', 'stations': [fm(p) for p in G], 'rstations': [fm(p) for p in R], 'lines': outl}, open(out, 'w'), separators=(',', ':'))
    print(len(G), 'stamnätsstationer,', len(R), 'regionnätsstationer (', len(extra), 'Vattenfall-stationer utan träff i Lantmäteriets filer togs bort),', len(outl), 'ledningar,', os.path.getsize(out) // 1024, 'kB')
main()
