/* Simuleringsmotor för Regionnätsspelet: DC-lastflöde, N-1, PTDF och ledig kapacitet.
   Fiktivt nät, endast för illustration. */
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
  {id:'G', name:'Stamnät'},
  {id:'T1',name:'Station Väst'},
  {id:'T2',name:'Station Öst'},
  {id:'KA',base:40,kind:'industri',gen:[],                          name:'Kommun A',desc:'industri'},
  {id:'KB',base:55,kind:'blandat', gen:[],                          name:'Kommun B',desc:'stad'},
  {id:'KC',base:18,kind:'bostad',  gen:[{kind:'vind',mw:30}],       name:'Kommun C',desc:'landsbygd'},
  {id:'KD',base:30,kind:'industri',gen:[{kind:'vind',mw:40}],       name:'Kommun D',desc:'hamn'},
  {id:'KE',base:50,kind:'bostad',  gen:[],                          name:'Kommun E',desc:'bostäder'},
  {id:'KF',base:12,kind:'bostad',  gen:[{kind:'sol',mw:20}],        name:'Kommun F',desc:'landsbygd'}
];
const IDX = Object.fromEntries(NODES.map((n,i)=>[n.id,i]));
const byId = Object.fromEntries(NODES.map(n=>[n.id,n]));
const LOADS = NODES.filter(n=>n.base!=null);
const BASE_LINES = [
  {id:'L1', a:'G', b:'T1',x:.04,cap:240,label:'transformator Väst'},
  {id:'L2', a:'G', b:'T2',x:.04,cap:240,label:'transformator Öst'},
  {id:'L3', a:'T1',b:'KA',x:.10,cap:125,label:'linjen Väst–Kommun A'},
  {id:'L4', a:'KA',b:'KB',x:.12,cap:100,label:'linjen Kommun A–Kommun B'},
  {id:'L5', a:'KB',b:'T2',x:.10,cap:120,label:'linjen Kommun B–Öst'},
  {id:'L6', a:'T1',b:'KD',x:.10,cap:110,label:'linjen Väst–Kommun D'},
  {id:'L7', a:'KD',b:'KF',x:.08,cap:90, label:'linjen Kommun D–Kommun F'},
  {id:'L8', a:'KF',b:'KE',x:.08,cap:90, label:'linjen Kommun F–Kommun E'},
  {id:'L9', a:'KE',b:'T2',x:.10,cap:120,label:'linjen Kommun E–Öst'},
  {id:'L10',a:'KB',b:'KE',x:.15,cap:70, label:'korslänken Kommun B–Kommun E'},
  {id:'L11',a:'KA',b:'KC',x:.10,cap:45, label:'linjen Kommun A–Kommun C'}
];
const UPG = 1.5;                 /* en förstärkning ger +50 % kapacitet och motsvarande lägre reaktans */
const NEWX = 11;                 /* ny linje: reaktans = NEWX / kapacitet (samma storleksordning som befintliga linjer) */
function buildX(out,lines){
  const m=NODES.length-1;
  const B=Array.from({length:m},()=>Array(m).fill(0));
  lines.forEach((l,i)=>{
    if(i===out) return;
    const b=1/l.x, a=IDX[l.a], c=IDX[l.b];
    if(a>0) B[a-1][a-1]+=b;
    if(c>0) B[c-1][c-1]+=b;
    if(a>0&&c>0){B[a-1][c-1]-=b;B[c-1][a-1]-=b}
  });
  const A=B.map((r,i)=>[...r,...Array.from({length:m},(_,j)=>i===j?1:0)]);
  for(let i=0;i<m;i++){
    let p=i;
    for(let r=i+1;r<m;r++) if(Math.abs(A[r][i])>Math.abs(A[p][i])) p=r;
    if(Math.abs(A[p][i])<1e-9) return null;
    [A[i],A[p]]=[A[p],A[i]];
    const d=A[i][i];
    for(let c=0;c<2*m;c++) A[i][c]/=d;
    for(let r=0;r<m;r++){
      if(r===i) continue;
      const f=A[r][i]; if(f===0) continue;
      for(let c=0;c<2*m;c++) A[r][c]-=f*A[i][c];
    }
  }
  return A.map(r=>r.slice(m));
}
const NETCACHE={};
/* cfg = {up:{L3:true,...}, add:[{id,a,b,cap}]} */
function makeNet(cfg){
  cfg=cfg||{up:{},add:[]};
  const key=JSON.stringify(cfg);
  if(NETCACHE[key]) return NETCACHE[key];
  const lines=BASE_LINES.map(l=>cfg.up[l.id]?{...l,cap:l.cap*UPG,x:l.x/UPG,up:true}:{...l})
    .concat(cfg.add.map(a=>({id:a.id,a:a.a,b:a.b,cap:a.cap,x:NEWX/a.cap,label:`ny linje ${byId[a.a].name.replace('Kommun ','Kommun ')}–${byId[a.b].name}`,added:true})));
  const scen=[{out:-1,X:buildX(-1,lines)}];
  lines.forEach((l,i)=>{const X=buildX(i,lines); if(X) scen.push({out:i,X})});
  scen.forEach(s=>{
    s.PT={};
    for(let k=1;k<NODES.length;k++){
      const th=[0,...s.X.map(r=>-r[k-1])];
      s.PT[k]=lines.map((l,i)=>i===s.out?0:(th[IDX[l.a]]-th[IDX[l.b]])/l.x);
    }
  });
  return (NETCACHE[key]={lines,scen,cfg});
}
const ORIG = makeNet({up:{},add:[]});
let NET = ORIG, LINES = ORIG.lines, SCEN = ORIG.scen;
function setCfg(cfg){NET=makeNet(cfg);LINES=NET.lines;SCEN=NET.scen;return NET}
function flowsFor(s,P,lines){
  const th=[0,...s.X.map(r=>r.reduce((acc,x,j)=>acc+x*P[j],0))];
  return lines.map((l,i)=>i===s.out?0:(th[IDX[l.a]]-th[IDX[l.b]])/l.x);
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
    const parts=NODES.slice(1).map(n=>n.base==null?{load:0,gen:0}:nodeParts(n,h,placed));
    const P=parts.map(p=>p.gen-p.load);
    const inHl=hl.includes(h);
    if(inHl) for(const n of LOADS){const p=parts[IDX[n.id]-1];load[n.id]=Math.max(load[n.id],p.load);gen[n.id]=Math.max(gen[n.id],p.gen)}
    for(const s of scen){
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
  const lres=lines.map((l,i)=>({flow:worst[i].abs,signed:worst[i].signed,out:worst[i].out,h:worst[i].h,util:worst[i].abs/l.cap,cap:l.cap,series:series[i]}));
  return {lines:lres,availU,availI,bindU,bindI,load,gen};
}
const avl = v=>Math.max(0,Math.floor(v+1e-6));
function metrics(res){
  let overloads=0; res.lines.forEach(r=>{if(r.flow>r.cap+0.05) overloads++});
  const ok20=LOADS.filter(l=>res.availU[l.id]>=20-1e-6).length;
  return {overloads,ok20};
}
function ptdfOf(nodeId,outIdx=-1,net){
  net=net||NET; const s=net.scen.find(x=>x.out===outIdx); return s.PT[IDX[nodeId]];
}
//#SIM-END
