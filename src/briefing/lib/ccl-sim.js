/* Chronic Care Loop simulation engine — ported from the original simulator. Deterministic (fixed seed). */
(function(){
'use strict';
const TRIG={
 T3:['Hypoglycaemia / DKA','T2D','safety','Same-day clinician review + hypo/DKA plan','Doctor','DoH DMP · hypo'],
 BPU:['BP urgent ≥180/110','HTN','safety','Stop script · escalate same day','Doctor','DoH HTN'],
 T4:['Post-discharge care','T2D · HTN','acute','GP follow-up within 72 h + med reconciliation','Coordinator','DOH-14'],
 T1:['HbA1c above target','T2D','unctl','Glycaemic treatment review','Doctor','DOH-6 · ADA 6'],
 T2:['BP treatment review','HTN','unctl','Home BP recheck + clinician review','Nurse','DOH-5 · ESC 2024'],
 T5:['Kidney check','T2D · HTN','unctl','eGFR + UACR; nephrology if eGFR < 30','Coordinator','KDIGO 2024'],
 T9:['Medication adherence','T2D · HTN','barrier','Refill + barrier check','Coordinator','DOH-7'],
 T6:['HbA1c test due','T2D','gap','HbA1c at in-network lab','Coordinator','DOH-8'],
 T12:['Eye exam due','T2D','gap','Confirm last eye exam or refer','Nurse','DOH-13'],
 T13:['High-risk foot','T2D','gap','Foot exam; podiatry if high risk','Nurse','DOH-12 · IWGDF'],
 T7:['Potassium due','HTN','gap','Add K+ to next lab order','Coordinator','DoH HTN'],
 T8:['Nutrition & education','T2D','goal','Self-management goal · dietitian','Nurse','DSMES']};
const PLAIN={T3:'Low or dangerous blood sugar',BPU:'Dangerously high blood pressure',T4:'Recently discharged from hospital',T1:'Diabetes not under control',T2:'Blood pressure above target',T5:'Kidney check needed',T9:'Not taking medicines regularly',T6:'Diabetes test overdue',T12:'Eye check overdue',T13:'Foot at risk',T7:'Blood test for BP medicines due',T8:'Needs diet and self-care support'};
const ACT={T3:'Same-day clinician review',BPU:'Same-day blood pressure escalation',T4:'GP follow-up within 72 hours',T1:'Diabetes treatment review',T2:'Blood pressure review',T5:'Kidney blood and urine test',T9:'Medicine refill and barrier check',T6:'HbA1c lab test',T12:'Eye exam',T13:'Foot exam',T7:'Potassium blood test',T8:'Diet and self-care coaching'};
const CLS=['safety','acute','unctl','barrier','gap','goal'];
const tierOfR=R=>R>=13?4:R>=8?3:R>=4?2:1;

function createSim(opts){
 const L=Object.assign({n:300,nurses:4,calls:12,reach:60,consent:80,done:65,decl:10,hold:10,mode:'automated'},opts||{});
 let seed=20261120;
 const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
 const pick=a=>a[Math.floor(rnd()*a.length)];
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
 let POP,HIST,IT,EV,CUM,LASTQ,CAND=[],TI=0;
 function score(m){
  const H=m.dm&&m.a1c!=null?(m.a1c>=10?4:m.a1c>=9?3:m.a1c>=8?2:m.a1c>=7?1:0):0;
  const C=Math.min(5,H+(m.htn?2:0)+2*(m.hypo?1:0)+3*(m.dka?1:0));
  const M=Math.min(6,(m.lip?1:0)+(m.obes?1:0)+(m.smoke?1:0)+(m.cad?3:0)+(m.hf?3:0)+(m.retino?2:0));
  let K=0,prov=false;if(m.egfr!=null||m.uacr!=null)K=(m.egfr==null?0:m.egfr<15?4:m.egfr<30?3:m.egfr<45?2:m.egfr<60?1:0)+(m.uacr==null?0:m.uacr>=300?2:m.uacr>=30?1:0);else{prov=true;K=m.ckd||0;}
  K=Math.min(5,K);const U=Math.min(5,Math.min(3,m.ed)+(m.ip>=2?4:m.ip===1?3:0));
  const A=m.male?(m.age>=60?2:m.age>=40?1:0):(m.age>=70?2:m.age>=45?1:0);
  const R=C+M+K+U+A;return {C,M,K,U,A,R,prov,tier:tierOfR(R),safety:m.hypo||m.dka};
 }
 function fire(m){const f=[];
  if(m.dm&&(m.hypo||m.dka))f.push('T3');if(m.htn&&m.sbp>=180)f.push('BPU');if(m.discharged)f.push('T4');
  if(m.dm&&m.a1c!=null&&m.a1c>=8)f.push('T1');if(m.htn&&m.sbp>=(m.dm||m.egfr<60?130:140))f.push('T2');
  if((m.egfr!=null&&m.egfr<60)||m.egfr==null)f.push('T5');if(m.pdc<80)f.push('T9');
  if(m.dm&&m.a1cAge>180)f.push('T6');if(m.dm&&m.eyeAge>730)f.push('T12');if(m.dm&&m.footAge>365)f.push('T13');
  if(m.htn&&m.kAge>365)f.push('T7');if(m.dm&&!m.dsmes)f.push('T8');
  return f.filter(t=>L.mode==='automated'||['T9','T4'].includes(t)||TRIG[t][2]==='safety');}
 function alertOf(m){const t=m.trig;if(m.s.safety||t.some(x=>TRIG[x][2]==='safety'))return 'RED';
  if(t.includes('T4')||(m.a1c>=9)||m.sbp>=160||m.pdc<50)return 'AMBER';if(t.length)return 'YELLOW';return 'GREEN';}
 const P_OF=m=>m.alert==='RED'?1:m.alert==='AMBER'||m.s.tier===4?2:m.s.tier===3?3:4;
 const holdOf=id=>{let h=0;for(const c of id)h=(h*31+c.charCodeAt(0))>>>0;return (h%100)<L.hold;};
 function mkMember(i){const dm=rnd()<.72,htn=!dm||rnd()<.62;const age=30+Math.floor(rnd()*45);
  const m={id:'x'+(1000+i*7+Math.floor(rnd()*7)),dm,htn,male:rnd()<.55,age,lang:pick(['Arabic','Arabic','English','Hindi','Urdu']),
   a1c:dm?(rnd()<.12?null:+(6.4+rnd()*rnd()*6).toFixed(1)):null,sbp:htn?Math.round(122+rnd()*rnd()*62):128,
   egfr:rnd()<.38?null:Math.round(clamp(100-rnd()*rnd()*85,8,110)),uacr:rnd()<.55?null:Math.round(rnd()*rnd()*420),ckd:0,
   hypo:dm&&rnd()<.025,dka:dm&&rnd()<.012,lip:rnd()<.55,obes:rnd()<.38,smoke:rnd()<.12,cad:rnd()<.11,hf:rnd()<.05,retino:dm&&rnd()<.08,
   ed:Math.floor(rnd()*rnd()*4),ip:rnd()<.15?(rnd()<.3?2:1):0,pdc:Math.round(clamp(40+rnd()*65,20,100)),
   a1cAge:Math.round(rnd()*400),eyeAge:Math.round(rnd()*1200),footAge:Math.round(rnd()*700),kAge:Math.round(rnd()*600),dsmes:rnd()<.25,
   net:rnd()<.62?'In network':'Out of network',discharged:false,consent:'none',hold:false,st:{},gap:{},att:0,log:[],traj:[]};
  if(m.egfr==null&&rnd()<.25)m.ckd=1+Math.floor(rnd()*2);m.discharged=m.ip>0&&rnd()<.35;m.hold=holdOf(m.id);return m;}
 function intel(){POP.forEach(m=>{m.s=score(m);m.trig=fire(m);m.alert=alertOf(m);m.p=P_OF(m);
  const needs=m.trig.map(t=>({t,cls:TRIG[t][2]})).filter(n=>!(m.st[n.t]==='declined'&&m.st[n.t+'@']>IT));
  needs.sort((a,b)=>CLS.indexOf(a.cls)-CLS.indexOf(b.cls));m.needs=needs;m.cur=needs.slice(0,3);m.next=needs.slice(3,6);m.fut=needs.slice(6);});}
 function queue(){return POP.filter(m=>!m.hold&&m.consent!=='declined'&&m.needs.length&&m.p<4).sort((a,b)=>a.p-b.p||b.s.R-a.s.R||b.att-a.att);}
 function snapshot(){const tr=POP.filter(m=>!m.hold),ho=POP.filter(m=>m.hold);const avg=a=>a.length?a.reduce((s,m)=>s+m.s.R,0)/a.length:0;
  const tiers=[1,2,3,4].map(t=>POP.filter(m=>m.s.tier===t).length);
  const gapsOpen=POP.reduce((s,m)=>s+m.trig.filter(t=>TRIG[t][2]==='gap'||TRIG[t][2]==='unctl').length,0);
  const closed=POP.reduce((s,m)=>s+Object.values(m.gap).filter(v=>v===4).length,0);
  HIST.push({it:IT,tiers,red:POP.filter(m=>m.alert==='RED').length,amber:POP.filter(m=>m.alert==='AMBER').length,gapsOpen,closed,rT:avg(tr),rH:avg(ho),consented:POP.filter(m=>m.consent==='granted').length});
  POP.forEach(m=>m.traj.push(m.s.R));}
 function lg(m,kind,what){m.log.unshift({it:IT,kind,what});}
 function ev(m,kind,what){EV.push({id:m.id,kind});lg(m,kind,what);}
 function reset(){seed=20261120;POP=Array.from({length:L.n},(_,i)=>mkMember(i));HIST=[];IT=0;EV=[];LASTQ=0;
  CUM={calls:0,reached:0,consent:0,refused:0,done:0,decl:0,assert:0,red:0};intel();snapshot();
  CAND=queue().filter(m=>m.dm||m.htn).slice(0,30).map(m=>m.id);}
 function applyDone(m,t){
  if(t==='T1'){m.a1c=+(m.a1c-(0.5+rnd()*0.9)).toFixed(1);m.a1cAge=0;}
  if(t==='T2'||t==='BPU'){m.sbp=Math.round(m.sbp-(8+rnd()*12));}
  if(t==='T5'){if(m.egfr==null){m.egfr=Math.round(clamp(95-rnd()*rnd()*70,10,110));m.uacr=Math.round(rnd()*rnd()*300);}m.kAge=0;}
  if(t==='T9'){m.pdc=Math.min(100,m.pdc+15+Math.round(rnd()*15));}
  if(t==='T4'){m.discharged=false;}
  if(t==='T3'){m.hypo=rnd()<.3;m.dka=false;}
  if(t==='T6'){m.a1cAge=0;if(m.a1c==null)m.a1c=+(7+rnd()*3).toFixed(1);}
  if(t==='T12')m.eyeAge=0;if(t==='T13')m.footAge=0;if(t==='T7')m.kAge=0;if(t==='T8')m.dsmes=true;
  if(['T6','T12','T13','T7','T5'].includes(t)){m.gap[t]=4;}else if(TRIG[t][2]==='unctl')m.gap[t]=3;
  delete m.st[t];}
 function step(){IT++;EV=[];const cap=L.nurses*L.calls*10;const Q=queue().slice(0,cap);LASTQ=Q.length;
  Q.forEach(m=>{m.att++;
   if(rnd()*100>L.reach){ev(m,'nr','Call attempted, no answer · retry next working day');return;}
   if(m.consent==='none'){if(rnd()*100<L.consent){m.consent='granted';ev(m,'consent','Agreed to join on a recorded call · health record unlocked');}
    else{m.consent='declined';ev(m,'refused','Declined to join · no further contact');return;}}
   if(m.alert==='RED')ev(m,'red','Urgent · escalated to a clinician the same day');
   m.cur.forEach(n=>{const r=rnd()*100;
    if(r<L.done){m.st[n.t]='done';ev(m,'done',ACT[n.t]+' · completed');applyDone(m,n.t);}
    else if(r<L.done+L.decl){m.st[n.t]='declined';m.st[n.t+'@']=IT+6;ev(m,'decl',ACT[n.t]+' · declined, offered again in 90 days');}
    else ev(m,'carried',ACT[n.t]+' · carried to the next call');});
   if(rnd()<.25){ev(m,'assert','Member '+pick(['reports stopping one medicine','shares a private-clinic HbA1c result','reports a new home BP monitor','reports an eye exam last year']));}
  });
  POP.forEach(m=>{const treated=m.consent==='granted'&&!m.hold;
   if(m.dm&&m.a1c!=null&&!treated){m.a1c=+(m.a1c+(rnd()<.5?.1:0)).toFixed(1);}
   if(m.htn&&!treated)m.sbp=Math.round(m.sbp+rnd()*3);
   m.a1cAge+=14;m.eyeAge+=14;m.footAge+=14;m.kAge+=14;m.discharged=false;
   const pAdm=[0,.004,.01,.025,.05][m.s.tier]*(treated?.55:1);if(rnd()<pAdm){m.ip=Math.min(3,m.ip+1);m.discharged=true;lg(m,'adm','Unplanned hospital admission, seen in claims');}
   if(rnd()<.08&&m.ip>0&&IT%6===0)m.ip--;});
  const k=kind=>EV.filter(e=>e.kind===kind).length;
  CUM.calls+=Q.length;CUM.reached+=Q.length-k('nr');CUM.consent+=k('consent');CUM.refused+=k('refused');CUM.done+=k('done');CUM.decl+=k('decl');CUM.assert+=k('assert');CUM.red+=k('red');
  intel();snapshot();}
 function memberView(){const id=CAND.length?CAND[TI%CAND.length]:null;const m=POP.find(x=>x.id===id)||POP[0];
  return {id:m.id,cond:m.dm&&m.htn?'Diabetes and high blood pressure':m.dm?'Diabetes':'High blood pressure',age:m.age,sex:m.male?'Man':'Woman',lang:m.lang,net:m.net,
   tier:m.s.tier,tier0:tierOfR(m.traj[0]),R:m.s.R,R0:m.traj[0],traj:m.traj.slice(),alert:m.alert,consent:m.consent,
   a1c:m.a1c,sbp:m.sbp,pdc:m.pdc,a1c0:m.a1c0,log:m.log.slice(0,8),needs:m.cur.map(n=>PLAIN[n.t]),att:m.att};}
 function summary(){const h=HIST[HIST.length-1],a=HIST[0],tr=POP.filter(m=>!m.hold),ho=POP.filter(m=>m.hold);
  const cnt={};POP.forEach(m=>m.trig.forEach(t=>cnt[t]=(cnt[t]||0)+1));
  const top=Object.entries(cnt).sort((x,y)=>y[1]-x[1]).slice(0,6).map(([t,n])=>({t,label:PLAIN[t],n}));
  const Q=queue(),cap=L.nurses*L.calls*10,lastT=m=>tierOfR(m.traj[m.traj.length-1]);
  const k=kind=>EV.filter(e=>e.kind===kind).length;
  return {IT,n:POP.length,treated:tr.length,holdout:ho.length,
   both:POP.filter(m=>m.dm&&m.htn).length,dmOnly:POP.filter(m=>m.dm&&!m.htn).length,htnOnly:POP.filter(m=>!m.dm).length,
   hist:HIST.slice(),tiers:h.tiers,tiers0:a.tiers,red:h.red,amber:h.amber,closed:h.closed,gapsOpen:h.gapsOpen,
   flagged:POP.reduce((s,m)=>s+m.trig.length,0),flaggedMembers:POP.filter(m=>m.trig.length).length,top,
   queue:Q.length,cap,urgentQ:Q.filter(m=>m.p<=2).length,
   next:Q.slice(0,4).map(m=>({id:m.id,alert:m.alert,tier:m.s.tier,lang:m.lang,net:m.net,need:PLAIN[m.needs[0].t],action:ACT[m.needs[0].t]})),
   cum:Object.assign({},CUM),
   last:{calls:LASTQ,nr:k('nr'),consent:k('consent'),refused:k('refused'),done:k('done'),decl:k('decl'),carried:k('carried'),assert:k('assert'),red:k('red')},
   down:tr.filter(m=>lastT(m)<tierOfR(m.traj[0])).length,up:tr.filter(m=>lastT(m)>tierOfR(m.traj[0])).length,
   diff:(h.rH-a.rH)-(h.rT-a.rT),capacity:cap,member:memberView()};}
 reset();
 return {L,reset,step,run(n){for(let i=0;i<n;i++)step();return this;},get IT(){return IT;},summary,setTrace(i){TI=Math.max(0,i|0);}};
}
window.CCLSim={createSim,TRIG,PLAIN,ACT};
})();
