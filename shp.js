/* Läser shapefiler (.zip eller .shp + .dbf) direkt i webbläsaren och gör om dem till spelets kartkoordinater.
   Inget skickas någonstans. Samma omvandling som tools/stamnat_till_json.py och tools/natomraden_till_json.py. */
const SHP = (()=>{
  const dec = new TextDecoder('utf-8');
  const base = n=>n.replace(/^.*[\\/]/,'').replace(/\.[^.]+$/,'').toLowerCase();
  const ext = n=>(n.match(/\.([^.]+)$/)||[,''])[1].toLowerCase();

  async function inflate(bytes){
    const ds=new DecompressionStream('deflate-raw'), w=ds.writable.getWriter();
    w.write(bytes); w.close();
    return new Uint8Array(await new Response(ds.readable).arrayBuffer());
  }
  async function unzip(buf){
    const dv=new DataView(buf), u8=new Uint8Array(buf); let e=-1;
    for(let i=buf.byteLength-22;i>=Math.max(0,buf.byteLength-66000);i--) if(dv.getUint32(i,true)===0x06054b50){e=i;break}
    if(e<0) throw new Error('Ingen giltig zip-fil');
    const n=dv.getUint16(e+10,true); let p=dv.getUint32(e+16,true); const out=[];
    for(let k=0;k<n;k++){
      if(dv.getUint32(p,true)!==0x02014b50) break;
      const method=dv.getUint16(p+10,true), csize=dv.getUint32(p+20,true), nl=dv.getUint16(p+28,true), xl=dv.getUint16(p+30,true), cl=dv.getUint16(p+32,true), off=dv.getUint32(p+42,true);
      const name=dec.decode(u8.subarray(p+46,p+46+nl)); p+=46+nl+xl+cl;
      if(name.endsWith('/')) continue;
      const ln=dv.getUint16(off+26,true), lx=dv.getUint16(off+28,true), start=off+30+ln+lx, raw=u8.subarray(start,start+csize);
      out.push({name, data: method===0?raw:await inflate(raw)});
    }
    return out;
  }
  function parseShp(u8){
    const dv=new DataView(u8.buffer,u8.byteOffset,u8.byteLength), len=dv.getInt32(24)*2, out={type:'',shapes:[]};
    const t=dv.getInt32(32,true); out.type=[1,11,21].includes(t)?'point':[3,13,23].includes(t)?'line':[5,15,25].includes(t)?'poly':'';
    let p=100;
    while(p+8<=Math.min(len,u8.length)){
      const cl=dv.getInt32(p+4)*2, c=p+8, st=dv.getInt32(c,true); p=c+cl;
      if(st===0) continue;
      if(out.type==='point'){out.shapes.push({pts:[[dv.getFloat64(c+4,true),dv.getFloat64(c+12,true)]],parts:[0]});continue}
      const np=dv.getInt32(c+36,true), npt=dv.getInt32(c+40,true), parts=[], pts=[];
      for(let i=0;i<np;i++) parts.push(dv.getInt32(c+44+i*4,true));
      const o=c+44+np*4;
      for(let i=0;i<npt;i++) pts.push([dv.getFloat64(o+i*16,true),dv.getFloat64(o+i*16+8,true)]);
      out.shapes.push({pts,parts});
    }
    return out;
  }
  function parseDbf(u8){
    const dv=new DataView(u8.buffer,u8.byteOffset,u8.byteLength), n=dv.getUint32(4,true), hl=dv.getUint16(8,true), rl=dv.getUint16(10,true), f=[];
    for(let p=32;p<hl-1&&u8[p]!==0x0D;p+=32){
      let nm=''; for(let i=0;i<11&&u8[p+i];i++) nm+=String.fromCharCode(u8[p+i]);
      f.push({name:dec.decode(u8.subarray(p,p+11)).replace(/\0.*$/,''),len:u8[p+16]});
    }
    const rows=[];
    for(let r=0;r<n;r++){
      let p=hl+r*rl+1; const o={};
      for(const x of f){o[x.name]=dec.decode(u8.subarray(p,p+x.len)).trim(); p+=x.len}
      rows.push(o);
    }
    return rows;
  }
  /* files: FileList/array. Returnerar [{name,type,shapes,rows}] */
  async function read(files){
    const entries=[];
    for(const f of files){
      const e=ext(f.name), buf=await f.arrayBuffer();
      if(e==='zip') entries.push(...await unzip(buf)); else entries.push({name:f.name,data:new Uint8Array(buf)});
    }
    const sets={};
    for(const x of entries){const e=ext(x.name); if(e==='shp'||e==='dbf') (sets[base(x.name)]=sets[base(x.name)]||{})[e]=x.data}
    const out=[];
    for(const [name,s] of Object.entries(sets)){
      if(!s.shp) continue;
      const g=parseShp(s.shp); g.name=name; g.rows=s.dbf?parseDbf(s.dbf):[]; out.push(g);
    }
    return out;
  }

  /* SWEREF 99 TM (EPSG:3006) -> WGS84 (Lantmäteriets formler för Gauss-Krüger) */
  const A=6378137.0, F=1/298.257222101, K0=0.9996, FE=500000, L0=15*Math.PI/180;
  const e2=F*(2-F), n=F/(2-F), aR=A/(1+n)*(1+n*n/4+n**4/64);
  const d1=n/2-2*n*n/3+37*n**3/96-n**4/360, d2=n*n/48+n**3/15-437*n**4/1440, d3=17*n**3/480-37*n**4/840, d4=4397*n**4/161280;
  const As=e2+e2**2+e2**3+e2**4, Bs=-(7*e2**2+17*e2**3+30*e2**4)/6, Cs=(224*e2**3+889*e2**4)/120, Ds=-(4279*e2**4)/1260;
  function toLonLat(E,N){
    if(Math.abs(E)<400&&Math.abs(N)<400) return [E,N];   /* redan grader */
    const xi=N/(K0*aR), eta=(E-FE)/(K0*aR);
    const xp=xi-d1*Math.sin(2*xi)*Math.cosh(2*eta)-d2*Math.sin(4*xi)*Math.cosh(4*eta)-d3*Math.sin(6*xi)*Math.cosh(6*eta)-d4*Math.sin(8*xi)*Math.cosh(8*eta);
    const ep=eta-d1*Math.cos(2*xi)*Math.sinh(2*eta)-d2*Math.cos(4*xi)*Math.sinh(4*eta)-d3*Math.cos(6*xi)*Math.sinh(6*eta)-d4*Math.cos(8*xi)*Math.sinh(8*eta);
    const ps=Math.asin(Math.sin(xp)/Math.cosh(ep)), dl=Math.atan(Math.sinh(ep)/Math.cos(xp));
    const s=Math.sin(ps), lat=ps+s*Math.cos(ps)*(As+Bs*s*s+Cs*s**4+Ds*s**6);
    return [(L0+dl)*180/Math.PI, lat*180/Math.PI];
  }
  const P=MAP.proj;
  const toPx=(E,N)=>{const [lo,la]=toLonLat(E,N); return [(lo-P.minx)*P.k*P.sx,(P.maxy-la)*P.sx]};

  /* testobjekt för "ligger punkten i länet" */
  let probe=null;
  function lanTest(){
    if(probe) return probe;
    const ns='http://www.w3.org/2000/svg', svg=document.createElementNS(ns,'svg');
    svg.setAttribute('width','0'); svg.setAttribute('height','0'); svg.style.position='absolute'; svg.setAttribute('aria-hidden','true');
    const ps=MAP.paths.filter(p=>p.in).map(p=>{const e=document.createElementNS(ns,'path'); e.setAttribute('d',p.d); svg.appendChild(e); return e});
    document.body.appendChild(svg);
    const pt=(x,y)=>new DOMPoint(x,y);
    return (probe={inLan:(x,y)=>ps.some(e=>e.isPointInFill(pt(x,y))), svg, ns});
  }
  function rdp(p,eps){
    if(p.length<3) return p;
    const keep=new Uint8Array(p.length); keep[0]=keep[p.length-1]=1; const st=[[0,p.length-1]];
    while(st.length){
      const [a,b]=st.pop(); let dm=0,im=-1; const [x1,y1]=p[a],[x2,y2]=p[b], dx=x2-x1, dy=y2-y1, L=Math.hypot(dx,dy)||1e-9;
      for(let i=a+1;i<b;i++){const d=Math.abs(dy*p[i][0]-dx*p[i][1]+x2*y1-y2*x1)/L; if(d>dm){dm=d;im=i}}
      if(dm>eps&&im>0){keep[im]=1; st.push([a,im],[im,b])}
    }
    return p.filter((_,i)=>keep[i]);
  }
  const W=MAP.w, H=MAP.h, inView=([x,y])=>x>=-20&&x<=W+20&&y>=-20&&y<=H+20;
  const f1=v=>v.toFixed(1);

  /* stationer (punkter) och ledningar (linjer) -> {stations, lines} */
  function stamnat(sets){
    const t=lanTest(), st=[], byKv={};
    /* SVK_STAMNAT.zip innehåller även STATIONSOMRÅDEN och SVK_STOLPAR: använd bara stationer och ledningar */
    const isSt=x=>/^stationer$/i.test(x.name), isLe=x=>/ledning/i.test(x.name);
    const named=sets.some(x=>isSt(x)||isLe(x));
    sets=named?sets.filter(x=>isSt(x)||isLe(x)):sets;
    for(const s of sets){
      if(s.type==='point'){
        for(const sh of s.shapes){
          const [x,y]=toPx(...sh.pts[0]); if(!t.inLan(x,y)) continue;
          if(!st.some(q=>Math.hypot(q[0]-x,q[1]-y)<14)) st.push([x,y]);
        }
      }else if(s.type==='line'){
        const kvf=s.rows[0]&&Object.keys(s.rows[0]).find(k=>/SP.NNING/i.test(k));
        s.shapes.forEach((sh,ri)=>{
          const kv=kvf&&/^\d+$/.test(s.rows[ri][kvf])?+s.rows[ri][kvf]:0, parts=[...sh.parts,sh.pts.length];
          for(let i=0;i<parts.length-1;i++){
            const px=sh.pts.slice(parts[i],parts[i+1]).map(p=>toPx(...p));
            for(let j=0;j<px.length-1;j++){
              if(!inView(px[j])&&!inView(px[j+1])) continue;
              byKv[kv]=(byKv[kv]||'')+`M${f1(px[j][0])} ${f1(px[j][1])}L${f1(px[j+1][0])} ${f1(px[j+1][1])}`;
            }
          }
        });
      }
    }
    st.sort((a,b)=>a[1]-b[1]||a[0]-b[0]);
    return {stations:st.map(p=>[+f1(p[0]),+f1(p[1])]), lines:Object.entries(byKv).map(([v,d])=>({v:+v,d}))};
  }

  /* polygoner -> {areas:[{k,n,a,i,x,y,d}]} */
  function nat(sets){
    const t=lanTest(), areas=[], ns=t.ns;
    for(const s of sets){
      if(s.type!=='poly') continue;
      const key=n=>Object.keys(s.rows[0]||{}).find(k=>k.toLowerCase().replace(/[åä]/g,'a')===n)||n;
      const fk=key('natomrade'), fn=key('namn'), fa=key('agare');
      s.shapes.forEach((sh,ri)=>{
        const parts=[...sh.parts,sh.pts.length], rings=[];
        for(let i=0;i<parts.length-1;i++) rings.push(sh.pts.slice(parts[i],parts[i+1]).map(p=>toPx(...p)));
        const all=rings.flat(); if(!all.length) return;
        const bx=[Math.min(...all.map(p=>p[0])),Math.max(...all.map(p=>p[0]))], by=[Math.min(...all.map(p=>p[1])),Math.max(...all.map(p=>p[1]))];
        if(bx[1]<0||bx[0]>W||by[1]<0||by[0]>H) return;
        const ring=r=>{let far=0,m=-1; for(let k=1;k<r.length;k++){const dd=(r[k][0]-r[0][0])**2+(r[k][1]-r[0][1])**2; if(dd>m){m=dd;far=k}} return far<2?r:rdp(r.slice(0,far+1),0.6).slice(0,-1).concat(rdp(r.slice(far),0.6))};
        const d=rings.map(r=>{const q=ring(r); return q.length<3?'':'M'+q.map(p=>f1(p[0])+' '+f1(p[1])).join('L')+'Z'}).join('');
        if(!d) return;
        const pe=document.createElementNS(ns,'path'); pe.setAttribute('d',d); pe.setAttribute('fill-rule','evenodd'); t.svg.appendChild(pe);
        let i=false, lx=0, ly=0, n=0, sx=0, sy=0;
        const gx0=Math.max(0,bx[0]), gx1=Math.min(W,bx[1]), gy0=Math.max(0,by[0]), gy1=Math.min(H,by[1]);
        for(let a=0;a<14;a++) for(let b=0;b<14;b++){
          const x=gx0+(gx1-gx0)*(a+.5)/14, y=gy0+(gy1-gy0)*(b+.5)/14;
          if(pe.isPointInFill(new DOMPoint(x,y))){ n++; sx+=x; sy+=y; if(t.inLan(x,y)) i=true }
        }
        t.svg.removeChild(pe);
        if(n){lx=sx/n; ly=sy/n}else{lx=(gx0+gx1)/2; ly=(gy0+gy1)/2}
        const r=s.rows[ri]||{};
        areas.push({k:r[fk]||'',n:r[fn]||'',a:r[fa]||'',i,x:+f1(lx),y:+f1(ly),d});
      });
    }
    return {areas};
  }
  return {read,stamnat,nat};
})();
