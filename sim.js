/* Simuleringsmotor för Regionnätsspelet: DC-lastflöde, N-1, PTDF och ledig kapacitet.
   Fiktivt nät, endast för illustration. Kräver map.js (laddas före). */
//#SIM-START
const HRS = Array.from({length:24},(_,i)=>i);
const bump = (h,c,w)=>Math.exp(-Math.pow((h-c)/w,2));
const norm = a=>{const m=Math.max(...a);return a.map(v=>v/m)};
const PROFILES = {
  industri: norm(HRS.map(h=>0.70+0.30*bump(h,12.5,5))),
  bostad:   norm(HRS.map(h=>0.38+0.22*bump(h,7.5,1.6)+0.62*bump(h,19,2.4))),
  blandat:  norm(HRS.map(h=>0.50+0.20*bump(h,12,4)+0.30*bump(h,18.5,2.5)))
};
const cyc = (h,c)=>{const d=Math.abs(h-c);return Math.min(d,24-d)};
const KINDS = {
  dc:   {type:'load', name:'Datacenter',    short:'DC',     desc:'Jämn dygnet runt',  mw:40, profile:h=>1},
  batt: {type:'load', name:'Batterifabrik', short:'Batteri',desc:'Mest dagtid',       mw:40, profile:h=>0.55+0.45*bump(h,13,5.5)},
  h2:   {type:'load', name:'Elektrolysör',  short:'H₂',     desc:'Jämn, kan styras',  mw:45, profile:h=>1},
  ladd: {type:'load', name:'Laddhubb',      short:'Ladd',   desc:'Mest nattetid',     mw:25, profile:h=>0.35+0.65*Math.exp(-Math.pow(cyc(h,2)/3.5,2))},
  vind: {type:'gen',  name:'Vindpark',      short:'Vind',   desc:'Mest natt och kväll',mw:50, profile:h=>0.50+0.38*bump(h,2,6)+0.12*bump(h,22,3)},
  sol:  {type:'gen',  name:'Solpark',       short:'Sol',    desc:'Dagtid, sommar',    mw:30, profile:h=>0.95*bump(h,12.5,3.3)}
};
const isGen = k=>KINDS[k].type==='gen';
const inFlex = h=>h>=16&&h<=20;
const FLEXF = h=>inFlex(h)?0.25:1;
const NODES = [
  {id:'G',  name:'Stamnätet'},
  {id:'UPP',base:150,kind:'blandat', gen:[],                      name:'Uppsala',    desc:'stad'},
  {id:'ENK',base:55, kind:'blandat', gen:[{kind:'sol', mw:30}],   name:'Enköping',   desc:'stad'},
  {id:'HEB',base:18, kind:'bostad',  gen:[{kind:'vind',mw:25}],   name:'Heby',       desc:'landsbygd'},
  {id:'HAB',base:30, kind:'bostad',  gen:[],                      name:'Håbo',       desc:'bostäder'},
  {id:'KNI',base:32, kind:'bostad',  gen:[],                      name:'Knivsta',    desc:'bostäder'},
  {id:'TIE',base:28, kind:'industri',gen:[{kind:'vind',mw:40}],   name:'Tierp',      desc:'industri'},
  {id:'ALV',base:12, kind:'bostad',  gen:[{kind:'sol', mw:20}],   name:'Älvkarleby', desc:'landsbygd'},
  {id:'OST',base:30, kind:'industri',gen:[{kind:'vind',mw:60}],   name:'Östhammar',  desc:'industri'}
];
const IDX = Object.fromEntries(NODES.map((n,i)=>[n.id,i]));
const byId = Object.fromEntries(NODES.map(n=>[n.id,n]));
const LOADS = NODES.filter(n=>n.base!=null);
/* kartpositioner (px) från map.js; avstånd i km styr reaktansen hos nya ledningar */
const POS = {G:MAP.G, ...Object.fromEntries(Object.entries(MAP.stations).map(([k,v])=>[k,{x:v.x,y:v.y}]))};
const kmP = (a,b,pos)=>Math.max(8,Math.hypot(pos[a].x-pos[b].x,pos[a].y-pos[b].y)/MAP.pxPerKm);
const kmBetween = (a,b)=>kmP(a,b,POS);
/* fysiska stamnätsstationer heter G, G1, G2 ... och är alla samma elektriska nod (stamnätet, referensnod) */
const E = id=>(id[0]==='G'||id[0]==='X')?'G':id;  /* X = anslutning utanför länet, räknas som starkt nät som stamnätet */
const stName = id=>id==='G'?'Stamnätet':id[0]==='G'?'Stamnätet '+id.slice(1):id[0]==='X'?'Utanför länet '+id.slice(1):byId[id].name;
const XK = 0.275;                /* reaktans = XK * längd(km) / kapacitet(MW); 40 km och 60 MW ger ca 0,18 */
const STAR = {UPP:230,ENK:110,HEB:55,HAB:70,KNI:75,TIE:90,ALV:45,OST:110};
/* startnät: stjärna, varje kommunstation har en egen ledning till stamnätsstationen */
const BASE_LINES = LOADS.map((n,i)=>({id:'L'+(i+1),a:'G',b:n.id,cap:STAR[n.id],x:XK*kmBetween('G',n.id)/STAR[n.id],label:'anslutningen till stamnätet i '+n.name,km:kmBetween('G',n.id)}));
const UPG = 1.5;                 /* standard (om ingen mängd anges): +50 %. cfg.up[id] kan vara true eller antal extra MW; reaktansen skalas med kapaciteten */
/* noder som är sammankopplade med stamnätet (G) när ledning `out` är ur drift */
function reach(out,lines){
  const seen=new Set(['G']); let grow=true;
  while(grow){grow=false; lines.forEach((l,i)=>{if(i===out)return; const a=E(l.a),b=E(l.b); if(seen.has(a)!==seen.has(b)){seen.add(a);seen.add(b);grow=true}})}
  return seen;
}
/* inversen av den reducerade B-matrisen över noder som når stamnätet; övriga rader/kolumner är noll */
function buildX(out,lines,active){
  const m=NODES.length-1;
  const X=Array.from({length:m},()=>Array(m).fill(0));
  const ids=NODES.slice(1).map((n,k)=>k).filter(k=>active.has(NODES[k+1].id));
  const q=ids.length; if(!q) return X;
  const pos=Object.fromEntries(ids.map((k,r)=>[k+1,r]));
  const B=Array.from({length:q},()=>Array(q).fill(0));
  lines.forEach((l,i)=>{
    if(i===out) return;
    const b=1/l.x, a=IDX[E(l.a)], c=IDX[E(l.b)];
    if(a===c) return;
    if(a>0&&pos[a]!==undefined) B[pos[a]][pos[a]]+=b;
    if(c>0&&pos[c]!==undefined) B[pos[c]][pos[c]]+=b;
    if(a>0&&c>0&&pos[a]!==undefined&&pos[c]!==undefined){B[pos[a]][pos[c]]-=b;B[pos[c]][pos[a]]-=b}
  });
  const A=B.map((r,i)=>[...r,...Array.from({length:q},(_,j)=>i===j?1:0)]);
  for(let i=0;i<q;i++){
    let p=i;
    for(let r=i+1;r<q;r++) if(Math.abs(A[r][i])>Math.abs(A[p][i])) p=r;
    [A[i],A[p]]=[A[p],A[i]];
    const d=A[i][i];
    for(let c=0;c<2*q;c++) A[i][c]/=d;
    for(let r=0;r<q;r++){
      if(r===i) continue;
      const f=A[r][i]; if(f===0) continue;
      for(let c=0;c<2*q;c++) A[r][c]-=f*A[i][c];
    }
  }
  ids.forEach((ki,r)=>ids.forEach((kj,c)=>{X[ki][kj]=A[r][q+c]}));
  return X;
}
const NETCACHE={};
/* cfg = {up:{L3:extraMW,...}, add:[{id,a,b,cap,extra?}], base:'star'|'none', ks:[kommun-id som har station], pos:{id:{x,y}}} */
function makeNet(cfg){
  cfg=cfg||{up:{},add:[]};
  const key=JSON.stringify(cfg);
  if(NETCACHE[key]) return NETCACHE[key];
  const pos=cfg.pos||POS, base=cfg.base==='none'?[]:BASE_LINES;
  const present=new Set(cfg.ks||LOADS.map(n=>n.id));
  const lines=base.map(l=>{const e=(cfg.up||{})[l.id]; if(!e) return {...l}; const ex=e===true?l.cap*(UPG-1):e; const f=(l.cap+ex)/l.cap; return {...l,cap:l.cap+ex,x:l.x/f,up:true,extra:ex}})
    .concat(cfg.add.map(a=>{const ex=a.extra||0, cap=a.cap+ex, km=kmP(a.a,a.b,pos); return {id:a.id,a:a.a,b:a.b,cap,x:XK*km/cap,km,label:`ny ledning ${stName(a.a)}–${stName(a.b)}`,added:true,up:ex>0,extra:ex}}));
  const act0=reach(-1,lines);
  const scen=[{out:-1,X:buildX(-1,lines,act0),iso:[]}];
  const inPresent=NODES.filter(n=>n.base!=null&&present.has(n.id)).map(n=>n.id);
  lines.forEach((l,i)=>{
    const act=reach(i,lines);
    scen.push({out:i,X:buildX(i,lines,act),iso:inPresent.filter(id=>act0.has(id)&&!act.has(id))});
  });
  scen.forEach(s=>{
    s.PT={};
    for(let k=1;k<NODES.length;k++){
      const th=[0,...s.X.map(r=>-r[k-1])];
      s.PT[k]=lines.map((l,i)=>i===s.out?0:(th[IDX[E(l.a)]]-th[IDX[E(l.b)]])/l.x);
    }
  });
  const iso0=inPresent.filter(id=>!act0.has(id));
  return (NETCACHE[key]={lines,scen,cfg,present,iso0});
}
const ORIG = makeNet({up:{},add:[]});
let NET = ORIG, LINES = ORIG.lines, SCEN = ORIG.scen;
function setCfg(cfg){NET=makeNet(cfg);LINES=NET.lines;SCEN=NET.scen;return NET}
function flowsFor(s,P,lines){
  const th=[0,...s.X.map(r=>r.reduce((acc,x,j)=>acc+x*P[j],0))];
  return lines.map((l,i)=>i===s.out?0:(th[IDX[E(l.a)]]-th[IDX[E(l.b)]])/l.x);
}
function nodeParts(n,h,placed){
  let load=n.base*PROFILES[n.kind][h], gen=0;
  for(const g of n.gen) gen+=g.mw*KINDS[g.kind].profile(h);
  for(const p of placed) if(p.node===n.id){
    const v=p.mw*KINDS[p.kind].profile(h)*(p.flex?FLEXF(h):1);
    if(isGen(p.kind)) gen+=v; else load+=v;
  }
  return {load,gen};
}
/* största jämna tillägg d (MW) i en nod innan en linje når sin gräns; dir=+1 förbrukning, -1 produktion */
function dmaxFor(f,pt,dir,lines){
  let best=Infinity,bl=-1;
  for(let l=0;l<lines.length;l++){
    const p=pt[l]*dir; if(Math.abs(p)<1e-9) continue;
    const cap=lines[l].cap;
    const d=p>0?(cap-f[l])/p:(f[l]+cap)/(-p);
    if(d<best){best=d;bl=l}
  }
  return {d:best,l:bl};
}
function compute(placed,mode,hour,crit,net){
  net=net||NET; const lines=net.lines;
  const scen=crit==='n1'?net.scen:[net.scen[0]];
  const hl=mode==='worst'?HRS:[hour];
  const nl=lines.length;
  const series=lines.map(()=>HRS.map(()=>0));
  const worst=lines.map(()=>({abs:-1,signed:0,out:-1}));
  const availU={},availI={},bindU={},bindI={},load={},gen={};
  for(const n of LOADS){availU[n.id]=Infinity;availI[n.id]=Infinity;bindU[n.id]=null;bindI[n.id]=null;load[n.id]=0;gen[n.id]=0}
  for(const h of HRS){
    const parts=NODES.slice(1).map(n=>(n.base==null||!net.present.has(n.id))?{load:0,gen:0}:nodeParts(n,h,placed));
    const P=parts.map(p=>p.gen-p.load);
    const inHl=hl.includes(h);
    if(inHl) for(const n of LOADS){const p=parts[IDX[n.id]-1];load[n.id]=Math.max(load[n.id],p.load);gen[n.id]=Math.max(gen[n.id],p.gen)}
    for(const s of scen){
      /* N-1: en ledning faller bort och noder blir utan matning, alltså ingen reserv alls */
      if(inHl) for(const id of s.iso){availU[id]=0;availI[id]=0;bindU[id]=bindI[id]={line:s.out,out:s.out,h}}
      const f=flowsFor(s,P,lines);
      for(let l=0;l<nl;l++){
        const a=Math.abs(f[l]);
        if(a>series[l][h]) series[l][h]=a;
        if(inHl&&a>worst[l].abs) worst[l]={abs:a,signed:f[l],out:s.out,h};
      }
      if(inHl) for(const n of LOADS){
        const ru=dmaxFor(f,s.PT[IDX[n.id]],1,lines);
        if(ru.d<availU[n.id]){availU[n.id]=ru.d;bindU[n.id]={line:ru.l,out:s.out,h}}
        const ri=dmaxFor(f,s.PT[IDX[n.id]],-1,lines);
        if(ri.d<availI[n.id]){availI[n.id]=ri.d;bindI[n.id]={line:ri.l,out:s.out,h}}
      }
    }
  }
  for(const id of net.iso0){availU[id]=0;availI[id]=0;bindU[id]=bindI[id]=null}
  const lres=lines.map((l,i)=>({flow:worst[i].abs,signed:worst[i].signed,out:worst[i].out,h:worst[i].h,util:worst[i].abs/l.cap,cap:l.cap,series:series[i]}));
  return {lines:lres,availU,availI,bindU,bindI,load,gen,iso:net.iso0,present:net.present};
}
const avl = v=>Math.max(0,Math.floor(v+1e-6));
function metrics(res){
  let overloads=0; res.lines.forEach(r=>{if(r.flow>r.cap+0.05) overloads++});
  const ok20=LOADS.filter(l=>res.present.has(l.id)&&res.availU[l.id]>=20-1e-6).length;
  return {overloads,ok20};
}
function ptdfOf(nodeId,outIdx=-1,net){
  net=net||NET; const s=net.scen.find(x=>x.out===outIdx); return s?s.PT[IDX[nodeId]]:net.lines.map(()=>0);
}
//#SIM-END
