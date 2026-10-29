#!/usr/bin/env python3
"""Genererar map.js: förenklad statisk karta över Uppsala län.

Källa: https://github.com/okfse/sweden-geojson (swedish_municipalities.geojson, förenklade
kommungränser, ursprungligen från Valmyndigheten via Opendatasoft).
Användning: python3 tools/make_map.py   (kräver shapely)
"""
import json, math, urllib.request
from shapely.geometry import shape, Point
from shapely.ops import polylabel

URL = "https://raw.githubusercontent.com/okfse/sweden-geojson/master/swedish_municipalities.geojson"
LAN = {"Uppsala":"UPP","Enköping":"ENK","Heby":"HEB","Håbo":"HAB","Knivsta":"KNI","Tierp":"TIE","Älvkarleby":"ALV","Östhammar":"OST"}
W = 800.0
data = json.load(urllib.request.urlopen(URL))
feats = data["features"]
lan = [f for f in feats if f["properties"]["lan_code"] == "03"]
geoms = {f["properties"]["kom_namn"]: shape(f["geometry"]) for f in feats}
minx=min(g.bounds[0] for n,g in geoms.items() if n in LAN); maxx=max(g.bounds[2] for n,g in geoms.items() if n in LAN)
miny=min(g.bounds[1] for n,g in geoms.items() if n in LAN); maxy=max(g.bounds[3] for n,g in geoms.items() if n in LAN)
lat0=(miny+maxy)/2; k=math.cos(math.radians(lat0))
pad=0.04
minx-=pad*2; maxx+=pad*2; miny-=pad; maxy+=pad
sx=W/((maxx-minx)*k); H=round((maxy-miny)*sx)
def prj(lon,lat): return ((lon-minx)*k*sx, (maxy-lat)*sx)
def rdp(pts,eps):
    if len(pts)<3: return pts
    (x1,y1),(x2,y2)=pts[0],pts[-1]; dx,dy=x2-x1,y2-y1; L=math.hypot(dx,dy) or 1e-9
    dm,im=0,0
    for i in range(1,len(pts)-1):
        d=abs(dy*pts[i][0]-dx*pts[i][1]+x2*y1-y2*x1)/L
        if d>dm: dm,im=d,i
    if dm>eps: return rdp(pts[:im+1],eps)[:-1]+rdp(pts[im:],eps)
    return [pts[0],pts[-1]]
def path(geom,eps=0.6):
    polys=[geom] if geom.geom_type=="Polygon" else list(geom.geoms)
    out=[]
    for p in polys:
        for ring in [p.exterior]:
            pts=[prj(x,y) for x,y in ring.coords]
            if max(x for x,_ in pts)<-50 or min(x for x,_ in pts)>W+50 or max(y for _,y in pts)<-50 or min(y for _,y in pts)>H+50: continue
            far=max(range(len(pts)),key=lambda i:(pts[i][0]-pts[0][0])**2+(pts[i][1]-pts[0][1])**2)
            pts=rdp(pts[:far+1],eps)[:-1]+rdp(pts[far:],eps)
            if len(pts)<4: continue
            out.append("M"+"L".join(f"{x:.1f} {y:.1f}" for x,y in pts)+"Z")
    return "".join(out)
paths=[]
for n,g in geoms.items():
    inl=n in LAN
    if not inl:
        b=g.bounds
        if b[2]<minx or b[0]>maxx or b[3]<miny or b[1]>maxy: continue
    d=path(g)
    if d: paths.append({"name":n,"in":inl,"d":d})
st={}
for n,i in LAN.items():
    c=polylabel(geoms[n] if geoms[n].geom_type=="Polygon" else max(geoms[n].geoms,key=lambda p:p.area),tolerance=0.001)
    x,y=prj(c.x,c.y); st[i]={"name":n,"x":round(x,1),"y":round(y,1)}
cx,cy=prj((minx+maxx)/2,(miny+maxy)/2)
out={"w":int(W),"h":H,"pxPerKm":round(sx/110.57,3),"stations":st,"G":{"x":round(cx,1),"y":round(cy,1)},"paths":paths}
open("map.js","w",encoding="utf-8").write("/* Genererad av tools/make_map.py. Förenklade kommungränser, se README. */\nconst MAP="+json.dumps(out,ensure_ascii=False,separators=(',',':'))+";\n")
print(W,H,out["pxPerKm"],len(paths),sum(len(p["d"]) for p in paths)//1024,"kB")
for i,s in st.items(): print(i,s)
print("G",out["G"])
