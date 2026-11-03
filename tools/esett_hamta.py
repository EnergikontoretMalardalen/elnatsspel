#!/usr/bin/env python3
"""Hämtar timvärden från eSett Open Data (EXP18/Aggregate) för ett eller flera nätområden (MGA)
och sparar dem som JSON, samt skriver ut högsta timvärdet.

Användning (kräver bara Python 3, inga paket):
  python3 tools/esett_hamta.py 10YSE-HBY------G                       # ett helt år (2025)
  python3 tools/esett_hamta.py 10YSE-HBY------G --start 2025-01-01 --slut 2025-01-08   # test: en vecka
  python3 tools/esett_hamta.py KOD1 KOD2 KOD3 --ut esett_2025.json
"""
import sys, json, argparse, urllib.request, urllib.error, urllib.parse

ap = argparse.ArgumentParser()
ap.add_argument('mga', nargs='*', help='ett eller flera nätområden; utelämna för att fråga om alla i elområdet')
ap.add_argument('--mba', default='10Y1001A1001A46L')   # SE3
ap.add_argument('--start', default='2025-01-01')
ap.add_argument('--slut', default='2025-12-31')
ap.add_argument('--ut', default='esett_svar.json')
a = ap.parse_args()

res = {}
for mga in (a.mga or [None]):
    par = {'start': a.start + 'T00:00:00.000Z', 'end': a.slut + 'T23:00:00.000Z', 'mba': a.mba, 'resolution': 'hour'}
    if mga: par['mga'] = mga
    q = urllib.parse.urlencode(par); mga = mga or 'ALLA'
    req = urllib.request.Request('https://api.opendata.esett.com/EXP18/Aggregate?' + q, headers={'accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read(); status = r.status; ctype = r.headers.get('Content-Type')
    except urllib.error.HTTPError as e:
        print(mga, 'HTTP-FEL', e.code, e.reason, '-', e.read()[:500].decode('utf-8', 'replace')); continue
    except Exception as e:
        print(mga, 'FEL:', e); continue
    print(mga, 'status', status, ctype, 'bytes', len(raw))
    try: d = json.loads(raw)
    except Exception:
        print('  Svaret är inte JSON. Början av svaret:', raw[:500].decode('utf-8', 'replace')); continue
    res[mga] = d
    print(mga, 'antal rader:', len(d) if isinstance(d, list) else type(d).__name__)
    if isinstance(d, list) and d:
        koder = sorted({str(v) for r in d if isinstance(r, dict) for k, v in r.items() if 'mga' in k.lower() and 'name' not in k.lower()})
        if koder: print('  nätområden i svaret:', ', '.join(koder[:200]))
        print('  exempel:', json.dumps(d[0], ensure_ascii=False)[:300])
json.dump(res, open(a.ut, 'w'), ensure_ascii=False)
print('Sparat i', a.ut, '- ladda upp filen i chatten.')
