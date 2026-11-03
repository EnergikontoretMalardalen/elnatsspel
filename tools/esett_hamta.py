#!/usr/bin/env python3
"""Hämtar timvärden från eSett Open Data (EXP18/Aggregate) för ett eller flera nätområden (MGA)
och sparar dem som JSON, samt skriver ut högsta timvärdet.

Användning (kräver bara Python 3, inga paket):
  python3 tools/esett_hamta.py 10YSE-HBY------G                       # ett helt år (2025)
  python3 tools/esett_hamta.py 10YSE-HBY------G --start 2025-01-01 --slut 2025-01-08   # test: en vecka
  python3 tools/esett_hamta.py KOD1 KOD2 KOD3 --ut esett_2025.json
"""
import sys, json, argparse, urllib.request, urllib.parse

ap = argparse.ArgumentParser()
ap.add_argument('mga', nargs='+')
ap.add_argument('--mba', default='10Y1001A1001A46L')   # SE3
ap.add_argument('--start', default='2025-01-01')
ap.add_argument('--slut', default='2025-12-31')
ap.add_argument('--ut', default='esett_svar.json')
a = ap.parse_args()

res = {}
for mga in a.mga:
    q = urllib.parse.urlencode({'start': a.start + 'T00:00:00.000Z', 'end': a.slut + 'T23:00:00.000Z',
                                'mba': a.mba, 'mga': mga, 'resolution': 'hour'})
    req = urllib.request.Request('https://api.opendata.esett.com/EXP18/Aggregate?' + q, headers={'accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r: d = json.load(r)
    except Exception as e:
        print(mga, 'FEL:', e); continue
    res[mga] = d
    print(mga, 'antal rader:', len(d) if isinstance(d, list) else type(d).__name__)
    if isinstance(d, list) and d: print('  exempel:', json.dumps(d[0], ensure_ascii=False)[:300])
json.dump(res, open(a.ut, 'w'), ensure_ascii=False)
print('Sparat i', a.ut, '- ladda upp filen i chatten.')
