#!/usr/bin/env python3
"""Omvandlar shapefilen över nätområden (SWEREF 99 TM, polygoner) till natomraden.json i spelets
kartkoordinater. Filen laddas i spelet med knappen "Ladda nätområden".

Användning:
  python3 tools/natomraden_till_json.py Natomraden_SE3_Sw99TM.shp natomraden.json
Kräver: pip install pyshp pyproj shapely

OBS: natomraden.json ligger i .gitignore. Lägg inte in filen i det publika repot utan att ha
kontrollerat att datan får publiceras.
"""
import json, math, sys, urllib.request
import shapefile
from pyproj import Transformer
from shapely.geometry import shape, Polygon, box
from shapely.ops import unary_union

src, out = sys.argv[1:3]
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
lan=unary_union([Polygon([prj(x,y) for x,y in (g.exterior.coords if g.geom_type=="Polygon" else max(g.geoms,key=lambda p:p.area).exterior.coords)]) for g in G]).buffer(0)
clip=box(0,0,W,H)

def rings(poly):
    def r(c): return [prj(*T.transform(x,y)) for x,y,*_ in c]
    return Polygon(r(poly[0]), [r(h) for h in poly[1:]])

rd=shapefile.Reader(src,encoding="utf-8"); areas=[]
for sh,rec in zip(rd.shapes(),rd.records()):
    d=rec.as_dict(); parts=list(sh.parts)+[len(sh.points)]
    rs=[sh.points[a:b] for a,b in zip(parts[:-1],parts[1:])]
    polys=[Polygon([prj(*T.transform(x,y)) for x,y,*_ in r]).buffer(0) for r in rs if len(r)>=4]
    if not polys: continue
    geom=unary_union(polys).intersection(clip)
    if geom.is_empty: continue
    geom=geom.simplify(0.6)
    ps=[geom] if geom.geom_type=="Polygon" else [g for g in getattr(geom,"geoms",[]) if g.geom_type=="Polygon"]
    path="".join("M"+"L".join(f"{x:.1f} {y:.1f}" for x,y in p.exterior.coords)+"Z"+"".join("M"+"L".join(f"{x:.1f} {y:.1f}" for x,y in h.coords)+"Z" for h in p.interiors) for p in ps)
    if not path: continue
    rp=geom.representative_point()
    areas.append({"k":d["Natomrade"],"n":d["Namn"],"a":d["Agare"],"i":bool(geom.intersection(lan).area>200),"x":round(rp.x,1),"y":round(rp.y,1),"d":path})
json.dump({"w":W,"h":H,"areas":areas},open(out,"w"),ensure_ascii=False,separators=(",",":"))
print(f"{len(areas)} nätområden på kartan, {sum(a['i'] for a in areas)} berör länet -> {out}")
