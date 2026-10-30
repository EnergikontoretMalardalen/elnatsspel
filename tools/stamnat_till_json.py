#!/usr/bin/env python3
"""Omvandlar shapefiler över stamnätets stationer och ledningar (SWEREF 99 TM) till stamnat.json
i spelets kartkoordinater. Filen laddas i spelet med knappen "Ladda stamnät".

Användning:
  python3 tools/stamnat_till_json.py STATIONER.shp SVK_LEDNINGAR.shp stamnat.json
Kräver: pip install pyshp pyproj shapely

OBS: stamnat.json ligger i .gitignore. Lägg inte in filen i det publika repot utan att
ha kontrollerat att datan får publiceras.
"""
import json, math, sys, urllib.request
import shapefile
from pyproj import Transformer
from shapely.geometry import shape, Point, LineString, box
from shapely.ops import unary_union

stat, led, out = sys.argv[1:4]
LAN = {"Uppsala","Enköping","Heby","Håbo","Knivsta","Tierp","Älvkarleby","Östhammar"}
URL = "https://raw.githubusercontent.com/okfse/sweden-geojson/master/swedish_municipalities.geojson"
feats = json.load(urllib.request.urlopen(URL))["features"]
geoms = {f["properties"]["kom_namn"]: shape(f["geometry"]) for f in feats}
G = [geoms[n] for n in LAN]
# samma projektion som tools/make_map.py
minx=min(g.bounds[0] for g in G); maxx=max(g.bounds[2] for g in G); miny=min(g.bounds[1] for g in G); maxy=max(g.bounds[3] for g in G)
k=math.cos(math.radians((miny+maxy)/2)); pad=0.04; minx-=pad*2; maxx+=pad*2; miny-=pad; maxy+=pad
W=800.0; sx=W/((maxx-minx)*k); H=round((maxy-miny)*sx)
prj=lambda lon,lat:((lon-minx)*k*sx,(maxy-lat)*sx)
T=Transformer.from_crs(3006,4326,always_xy=True)
lan=unary_union(G)

# stationer inom länet; stationer närmare än 14 px slås ihop
pts=[]
for s in shapefile.Reader(stat,encoding="utf-8").shapes():
    lon,lat=T.transform(s.points[0][0],s.points[0][1])
    if lan.contains(Point(lon,lat)): pts.append(list(prj(lon,lat)))
st=[]
for p in pts:
    for q in st:
        if math.hypot(p[0]-q[0],p[1]-q[1])<14: break
    else: st.append(p)
st.sort(key=lambda p:(p[1],p[0]))

# ledningar, beskurna till kartan
clip=box(-20,-20,W+20,H+20); bykv={}
rd=shapefile.Reader(led,encoding="utf-8")
for sh,rec in zip(rd.shapes(), rd.records()):
    v=rec.as_dict().get("SPÄNNING")
    parts=list(sh.parts)+[len(sh.points)]
    for a,b in zip(parts[:-1],parts[1:]):
        xy=[prj(*T.transform(x,y)) for x,y,*_ in sh.points[a:b]]
        if len(xy)<2: continue
        g=LineString(xy).intersection(clip)
        for seg in ([g] if g.geom_type=="LineString" else list(getattr(g,"geoms",[]))):
            if seg.geom_type!="LineString" or seg.is_empty: continue
            c=list(seg.simplify(0.5).coords)
            kv=int(v) if v and v.isdigit() else 0
            bykv[kv]=bykv.get(kv,"")+"M"+"L".join(f"{x:.1f} {y:.1f}" for x,y in c)
lines=[{"v":kv,"d":d} for kv,d in sorted(bykv.items())]
json.dump({"w":W,"h":H,"stations":[[round(x,1),round(y,1)] for x,y in st],"lines":lines},open(out,"w"),separators=(",",":"))
print(f"{len(st)} stationer i länet, {len(lines)} spänningsnivåer -> {out}")
