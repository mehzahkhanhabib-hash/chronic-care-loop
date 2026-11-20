/* Chronic Care Studio — builder estimation + care-intelligence derivations (illustrative, synthetic). */
(function(){
'use strict';
const fmt=n=>Math.round(n).toLocaleString('en-US');
const clamp=x=>Math.max(0,Math.min(1,x));
/* ───────── builder ───────── */
const BASES=[{id:'daman',label:'Daman members',src:'Claims knowledge graph',n:412300},{id:'seha',label:'SEHA patients',src:'Encounters and labs',n:742310},{id:'pura',label:'PURA app users',src:'App and devices',n:318940}];
const Ncdf=(mu,sd)=>x=>{const z=(x-mu)/sd;const t=1/(1+.2316419*Math.abs(z));const d=.3989423*Math.exp(-z*z/2);const p=d*t*(.3193815+t*(-.3565638+t*(1.781478+t*(-1.821256+t*1.330274))));return z>0?1-p:p;};
const numEst=F=>(op,v,v2)=>op==='≥'?1-F(v):op==='≤'?F(v):op==='between'?Math.max(0,F(v2)-F(v)):Math.max(.002,F(v+.5)-F(v-.5));
const COND=[['E11','Type 2 diabetes',.072],['I10','Hypertension',.11],['E78','Dyslipidaemia',.15],['E66','Obesity',.09],['N18','Chronic kidney disease',.025],['I50','Heart failure',.012],['I25','Coronary artery disease',.03],['J45','Asthma',.06],['J44','COPD',.012],['F32','Depression',.03]];
const LABS=[['hba1c','HbA1c','%',[7.4,1.4],.09,'E11'],['egfr','eGFR','mL/min',[88,22],.32,null],['ldl','LDL','mmol/L',[3,0.9],.35,null],['sbp','Systolic BP','mmHg',[128,16],.4,null],['bmi','BMI','kg/m²',[27.5,5],.3,null]];
const ATC=[['A10','Diabetes medicines',.075],['A10A','Insulin',.012],['C09','ACE / ARB',.09],['C10','Statins',.13],['B01','Anticoagulants',.02]];
const F={
 age:{cat:'Who they are',label:'Age',type:'num',unit:'years',op:'between',v:40,v2:65,est:numEst(Ncdf(41,14)),ng:(op,v,v2)=>numNg('m.Member.age',op,v,v2)},
 gender:{cat:'Who they are',label:'Gender',type:'enum',opts:[['F','Female',.46],['M','Male',.54]],ng:vs=>inNg('m.Member.gender',vs)},
 plan:{cat:'Who they are',label:'Plan',type:'enum',opts:[['ENH','Enhanced',.55],['BAS','Basic',.3],['THQ','Thiqa',.15]],ng:vs=>inNg('p.Policy.plan',vs),graph:1},
 region:{cat:'Who they are',label:'Region',type:'enum',opts:[['AUH','Abu Dhabi',.62],['AAN','Al Ain',.28],['ADH','Al Dhafra',.1]],ng:vs=>inNg('m.Member.region',vs)},
 dx:{cat:'Health',label:'Has condition',type:'code',opts:COND,sub:'ICD-10, any claim in 24 months',ng:vs=>'('+vs.map(c=>'m.MemberFeature.dx_'+c+' == true').join(' OR ')+')'},
 ncc:{cat:'Health',label:'Chronic conditions',type:'num',unit:'or more',op:'≥',v:2,est:numEst(Ncdf(.6,1.1)),ng:(op,v,v2)=>numNg('m.MemberFeature.chronic_count',op,v,v2)},
 lab:{cat:'Tests & results',label:'Latest result',type:'lab',sub:'last value in 12 months',ng:(op,v,v2,l)=>numNg('m.MemberFeature.lab_'+l+'_last',op,v,v2)},
 labage:{cat:'Tests & results',label:'Test overdue',type:'labage',sub:'no result in N days',ng:(op,v,v2,l)=>'(m.MemberFeature.lab_'+l+'_days IS NULL OR m.MemberFeature.lab_'+l+'_days > '+v+')'},
 ed:{cat:'Visits & admissions',label:'ED visits · 12 months',type:'num',unit:'visits',op:'≥',v:2,est:numEst(Ncdf(.25,.7)),ng:(op,v,v2)=>numNg('m.MemberFeature.ed_12m',op,v,v2)},
 ip:{cat:'Visits & admissions',label:'Unplanned admissions',type:'num',unit:'stays',op:'≥',v:1,est:numEst(Ncdf(.05,.35)),ng:(op,v,v2)=>numNg('m.MemberFeature.ip_unplanned_12m',op,v,v2)},
 nofu:{cat:'Visits & admissions',label:'No outpatient visit',type:'num',unit:'days',op:'≥',v:180,est:(op,v)=>.34*Math.exp(-(v-180)/400),ng:(op,v,v2)=>numNg('m.MemberFeature.days_since_op',op,v,v2)},
 atc:{cat:'Medicines',label:'Takes medicine class',type:'code',opts:ATC,sub:'ATC, fill in 180 days',ng:vs=>'('+vs.map(c=>'m.MemberFeature.atc_'+c+' == true').join(' OR ')+')'},
 pdc:{cat:'Medicines',label:'Adherence (PDC)',type:'num',unit:'%',op:'≤',v:80,est:(op,v)=>.12*(op==='≤'?v/80:1-(v/100)),ng:(op,v,v2)=>numNg('m.MemberFeature.pdc_min',op,v,v2)},
 eye:{cat:'Screenings',label:'Eye exam not on record',type:'bool',share:.06,sub:'24 months',ng:()=>'m.MemberFeature.eye_exam_days > 730'},
 foot:{cat:'Screenings',label:'Foot exam not on record',type:'bool',share:.055,sub:'12 months',ng:()=>'m.MemberFeature.foot_exam_days > 365'},
 innet:{cat:'Network & cost',label:'Visits in network',type:'num',unit:'%',op:'≤',v:25,est:(op,v)=>op==='≤'?.08+v/100*.4:.92-v/100*.5,ng:(op,v,v2)=>numNg('m.MemberFeature.in_network_share',op,v,v2)},
 cost:{cat:'Network & cost',label:'Claims cost · 12 months',type:'num',unit:'AED',op:'≥',v:50000,est:(op,v)=>Math.min(.9,.05*Math.pow(50000/Math.max(v,1000),1.1)),ng:(op,v,v2)=>numNg('m.MemberFeature.cost_12m',op,v,v2)},
 pura:{cat:'Engagement & consent',label:'Active on PURA',type:'bool',share:.19,sub:'30 days',ng:()=>'m.MemberFeature.pura_active_30d == true'},
 optout:{cat:'Engagement & consent',label:'Opted out of contact',type:'bool',share:.03,ng:()=>'m.MemberFeature.contact_opt_out == true'},
 pregnant:{cat:'Engagement & consent',label:'Currently pregnant',type:'bool',share:.012,ng:()=>'m.MemberFeature.pregnant == true'},
 onco:{cat:'Engagement & consent',label:'Active cancer treatment',type:'bool',share:.02,ng:()=>'m.MemberFeature.onc_active == true'}
};
const CATS=['Who they are','Health','Tests & results','Visits & admissions','Medicines','Screenings','Network & cost','Engagement & consent'];
const numNg=(p,op,v,v2)=>op==='between'?'('+p+' >= '+v+' AND '+p+' <= '+v2+')':p+' '+({'≥':'>=','≤':'<=','=':'=='}[op]||op)+' '+v;
const inNg=(p,vs)=>vs.length===1?p+' == "'+vs[0]+'"':p+' IN ['+vs.map(v=>'"'+v+'"').join(', ')+']';
let rid=0;
function newRule(f){const d=F[f];const r={id:++rid,f};
 if(d.type==='num'){r.op=d.op;r.v=d.v;r.v2=d.v2??d.v;}else if(d.type==='enum'||d.type==='code')r.vs=[];
 else if(d.type==='lab'){r.l='hba1c';r.op='≥';r.v=8;r.v2=10;}else if(d.type==='labage'){r.l='hba1c';r.v=180;}return r;}
const ruleOn=r=>{const d=F[r.f];return !((d.type==='enum'||d.type==='code')&&!r.vs.length);};
function share(r,cb){const d=F[r.f];const dxIn=c=>cb.inc.some(x=>x.f==='dx'&&x.vs.includes(c));
 if(r.f==='pdc'&&cb.inc.some(x=>(x.f==='dx'||x.f==='atc')&&x.vs.length))return clamp(r.op==='≤'?.4*r.v/80:1-.4*r.v/80);
 if(d.type==='num')return clamp(d.est(r.op,+r.v,+r.v2));if(d.type==='bool')return d.share;
 if(d.type==='enum')return r.vs.length?r.vs.reduce((s,v)=>s+(d.opts.find(o=>o[0]===v)||[0,0,0])[2],0):1;
 if(d.type==='code')return r.vs.length?clamp(1-r.vs.reduce((p,v)=>p*(1-(d.opts.find(o=>o[0]===v)||[0,0,0])[2]),1)):1;
 const L=LABS.find(x=>x[0]===r.l);
 if(d.type==='lab'){let s=numEst(Ncdf(L[3][0],L[3][1]))(r.op,+r.v,+r.v2)*L[4];if(L[5]){const pv=COND.find(c=>c[0]===L[5])[2];s=dxIn(L[5])?Math.min(.95,s/pv):s;}return clamp(s);}
 if(d.type==='labage'){let s=clamp(.45*Math.exp(-(r.v-180)/500));if(L[5])s=dxIn(L[5])?s:s*COND.find(c=>c[0]===L[5])[2];return s;}return 1;}
function ruleText(r){const d=F[r.f];
 if(d.type==='num')return d.label+' '+(r.op==='between'?r.v+'–'+r.v2:r.op+' '+(+r.v>=1000?fmt(+r.v):r.v))+(d.unit?' '+d.unit:'');
 if(d.type==='bool')return d.label;
 if(d.type==='enum'||d.type==='code')return d.label+': '+(r.vs.map(v=>(d.opts.find(o=>o[0]===v)||[v,v])[1]).join(' or ')||'any');
 const L=LABS.find(x=>x[0]===r.l);if(d.type==='lab')return L[1]+' '+(r.op==='between'?r.v+'–'+r.v2:r.op+' '+r.v)+' '+L[2];
 return L[1]+' not done in '+r.v+' days';}
function estimate(cb){const B=BASES.find(b=>b.id===cb.base).n;let n=B;const steps=[];const inc=cb.inc.filter(ruleOn),exc=cb.exc.filter(ruleOn);
 if(cb.logic==='any'&&inc.length){n=B*(1-inc.reduce((a,r)=>a*(1-share(r,cb)),1));steps.push({t:'Any of '+inc.length+' rules',n,id:'any'});}
 else inc.forEach(r=>{n*=share(r,cb);steps.push({t:ruleText(r),n,id:r.id});});
 exc.forEach(r=>{n*=(1-share(r,cb));steps.push({t:'Not: '+ruleText(r),n,ex:1,id:r.id});});
 return {B,n,steps};}
function ngql(cb){const pol=[...cb.inc,...cb.exc].some(r=>F[r.f].graph);const sp=cb.base==='seha'?'seha_kg':'daman_kg';
 let q='USE '+sp+';\n'+(pol?'MATCH (m:Member)-[:HAS_CARD]->(:Card)-[:UNDER_POLICY]->(p:Policy)':'MATCH (m:Member)');
 const P=r=>{const d=F[r.f];return d.type==='enum'||d.type==='code'?d.ng(r.vs):d.type==='lab'||d.type==='labage'?d.ng(r.op,r.v,r.v2,r.l):d.type==='num'?d.ng(r.op,r.v,r.v2):d.ng();};
 const inc=cb.inc.filter(ruleOn).map(P),exc=cb.exc.filter(ruleOn).map(P);const w=[];if(cb.base==='pura')w.push('m.MemberFeature.pura_user == true');
 if(inc.length)w.push(cb.logic==='any'?'(\n       '+inc.join('\n    OR ')+'\n  )':inc.join('\n  AND '));exc.forEach(e=>w.push('NOT '+e));
 if(w.length)q+='\nWHERE '+w.join('\n  AND ');return q+'\nRETURN DISTINCT id(m) AS member_vid;';}
const TAGS=['Member','Card','Policy','Claim','ClaimLine','Diagnosis','Procedure','Observation','Drug','DrugClass','Provider','MemberFeature'],EDGES=['HAS_CARD','UNDER_POLICY','FILED','HAS_LINE','CODED_AS','FOR_PROCEDURE','FOR_OBSERVATION','FOR_DRUG','IN_CLASS','AT_PROVIDER'];
function check(q){const t=q.replace(/--[^\n]*/g,'');const C=[];
 const w=t.match(/\b(INSERT|UPDATE|UPSERT|DELETE|DROP|CREATE|ALTER|CLEAR|SUBMIT|GRANT|REVOKE|INGEST|KILL)\b/i);C.push(['Read-only',!w,w?w[1].toUpperCase()+' not allowed':'no writes']);
 const sp=(t.match(/USE\s+(\w+)/i)||[])[1];C.push(['Allowed space',sp==='daman_kg'||sp==='seha_kg',sp||'missing USE']);
 C.push(['Starts at Member',/MATCH\s*\(\s*m\s*:\s*Member\b/i.test(t),'(m:Member)']);
 C.push(['Returns member_vid',/RETURN\s+(DISTINCT\s+)?id\(m\)\s+AS\s+member_vid/i.test(t),'id(m) AS member_vid']);
 const tags=[...t.matchAll(/\(\s*\w*\s*:\s*([A-Z]\w*)/g)].map(x=>x[1]),edges=[...t.matchAll(/\[\s*\w*\s*:\s*([A-Z_]+)/g)].map(x=>x[1]);
 const bad=tags.filter(x=>!TAGS.includes(x)).concat(edges.filter(x=>!EDGES.includes(x)));C.push(['Known schema',!bad.length,bad.length?'unknown: '+bad.join(', '):'all tags known']);
 const sc=/MemberRisk|tier|r_total|risk_score/i.test(t);C.push(['Inputs only',!sc,sc?'risk is computed after hand-off':'no scores used']);
 return {ok:C.every(c=>c[1]),C};}
const LEX=[[/type\s*2\s*diabet\w*|\bdiabet\w*|\bt2d\b/i,'E11'],[/hypertens\w*|high blood pressure|\bhtn\b/i,'I10'],[/kidney disease|\bckd\b/i,'N18'],[/heart failure/i,'I50'],[/asthma/i,'J45'],[/copd/i,'J44'],[/obes\w*/i,'E66'],[/depress\w*/i,'F32'],[/cholesterol|dyslipid\w*/i,'E78'],[/coronary|heart disease/i,'I25']];
function parse(text){const t=text.toLowerCase();const inc=[],exc=[];const parts=t.split(/\b(?:excluding|except|but not|without)\b/);const pos=parts[0],neg=parts.slice(1).join(' ');
 const dx=[],dxN=[];LEX.forEach(([re,c])=>{if(re.test(pos))dx.push(c);else if(re.test(neg))dxN.push(c);});
 if(dx.length){const r=newRule('dx');r.vs=dx;inc.push(r);}let m;
 if((m=t.match(/hba1c\s*(?:above|over|>=?|≥|of)?\s*(\d+(?:\.\d)?)/))){const r=newRule('lab');r.l='hba1c';r.op='≥';r.v=+m[1];inc.push(r);}
 if((m=t.match(/egfr\s*(?:below|under|<)\s*(\d+)/))){const r=newRule('lab');r.l='egfr';r.op='≤';r.v=+m[1];inc.push(r);}
 if((m=t.match(/(?:bp|blood pressure)\s*(?:above|over)\s*(\d+)/))){const r=newRule('lab');r.l='sbp';r.op='≥';r.v=+m[1];inc.push(r);}
 if((m=t.match(/(?:over|above|older than|aged)\s*(\d{2})\b(?!\s*(?:mmhg|%))/))&&!/(?:bp|blood pressure|hba1c)\s*(?:above|over)\s*\d{2}/.test(t.slice(Math.max(0,m.index-20),m.index+m[0].length))){const r=newRule('age');r.op='≥';r.v=+m[1];inc.push(r);}
 if((m=t.match(/(\d)\s*(?:or more)?\s*(?:er|ed|emergency)\b/))){const r=newRule('ed');r.op='≥';r.v=+m[1];inc.push(r);}
 if(/admitted|admission|hospitali[sz]ed/.test(t))inc.push(newRule('ip'));
 if(/miss\w* (?:refills?|medicines?)|adherence|not taking/.test(t))inc.push(newRule('pdc'));
 if(/no (?:gp |doctor |outpatient )?visit|not seen/.test(t))inc.push(newRule('nofu'));
 if(/\bwomen\b|\bfemale/.test(t)){const r=newRule('gender');r.vs=['F'];inc.push(r);}
 if(/eye exam/.test(t))inc.push(newRule('eye'));if(/foot exam/.test(t))inc.push(newRule('foot'));
 if(dxN.length){const r=newRule('dx');r.vs=dxN;exc.push(r);}
 if(/cancer|oncology/.test(neg))exc.push(newRule('onco'));if(/pregnan/.test(t))exc.push(newRule('pregnant'));if(inc.length)exc.push(newRule('optout'));
 return {inc,exc};}
const EXAMPLES=['People with diabetes and HbA1c above 9 who missed refills, excluding cancer','Hypertension with blood pressure above 150 and no GP visit in 6 months','2 or more ER visits with heart failure','Women with diabetes whose eye exam is not on record'];
const TRIG=[['T1','HbA1c above target','E11'],['T2','BP treatment review','I10'],['T3','Hypoglycaemia','E11'],['T4','Post-discharge care','*'],['T5','Kidney check','*'],['T6','HbA1c test due','E11'],['T7','Potassium due','I10'],['T8','Nutrition and education','E11'],['T9','Medication adherence','*'],['T12','Eye exam due','E11'],['T13','High-risk foot','E11']];
const COHORTS=[
 {id:'COH-0101',name:'Diabetes · above goal',base:'daman',n:13420,refresh:'Nightly',owner:'Population health',ver:2,def:'Type 2 diabetes · HbA1c ≥ 8 %',src:'Builder'},
 {id:'COH-0102',name:'Hypertension · drifting from care',base:'daman',n:21980,refresh:'Every 3 days',owner:'Population health',ver:1,def:'Hypertension · no outpatient visit ≥ 180 days',src:'Builder'},
 {id:'COH-0103',name:'Post-discharge chronic',base:'daman',n:4120,refresh:'Daily',owner:'Care management',ver:1,def:'Chronic conditions ≥ 1 · unplanned admissions ≥ 1',src:'Builder'},
 {id:'COH-0104',name:'Diabetes · eye and foot gaps',base:'daman',n:9840,refresh:'Weekly',owner:'Quality',ver:1,def:'Type 2 diabetes · eye and foot exams not on record',src:'nGQL'}];
const CAMPAIGNS=[
 {id:'CMP-0101',name:'Diabetes control',goal:'Bring HbA1c to goal',inc:['COH-0101'],mode:'automated',trig:[],ch:['Voice'],nurses:8,calls:25,hold:10,status:'Live',start:'23 Nov',weeks:8},
 {id:'CMP-0102',name:'Back into care',goal:'Re-engage members without follow-up',inc:['COH-0102','COH-0103'],mode:'business',trig:['T9','T4'],ch:['Voice','WhatsApp'],nurses:6,calls:25,hold:10,status:'Scheduled',start:'1 Dec',weeks:6}];

/* ───────── care intelligence ───────── */
const CLS={safety:['Safety','#FBEEF0','#934450'],acute:['Acute','#F4EFE6','#8A6A3E'],unctl:['Uncontrolled','#F4F0E4','#7A6440'],barrier:['Barrier','#EAF1F9','#3F6C9F'],gap:['Care gap','#EAF1F9','#3F6C9F']};
const ORDER=['safety','acute','unctl','barrier','gap'];
const lab=(m,k)=>m.labs.find(l=>l.k===k);const last=l=>l?l.series[l.series.length-1]:null;
function needsFor(m){const N=[];const first=m.name.split(' ')[0];const tr=m.trigger.reason;const a1c=lab(m,'HbA1c'),ldl=lab(m,'LDL'),eg=lab(m,'eGFR');
 const add=o=>{if(!N.some(x=>x.id===o.id))N.push(o);};
 const dm=m.conds.some(c=>c.short==='DM');
 if(/Wearable/.test(tr))add({id:'det',cls:'safety',title:'Same-day clinician review',why:m.det.drivers.slice(0,2).join(' · '),ref:'Early-warning model',book:{d:0,label:'Clinician call'},why2:'Your '+m.wear.dev.split(' (')[0]+' readings over the last two weeks show '+m.det.drivers[0].toLowerCase()+'.',ask:'Could one of our clinicians call you back later today to check in?'});
 if(/Repeat ER/.test(tr))add({id:'gp',cls:'acute',title:'GP follow-up within 72 h',why:m.trigger.detail,ref:'DoH-14',book:{d:3,label:'GP visit'},why2:'I can see you have needed the emergency department twice recently. I would like your own doctor to follow that up.',ask:'Can I book you a GP visit in the next three days? '+m.pref+' works for you, is that right?'});
 if(/BP uncontrolled/.test(tr))add({id:'bp',cls:'unctl',title:'Home BP recheck and clinician review',why:m.trigger.detail+' · home BP '+m.wear.bp.join('/'),ref:'DoH-5 · ESC 2024',book:{d:2,label:'BP review'},why2:'Your recent blood pressure readings have been above the target your doctor set.',ask:'Could you take two home readings this week, then I book a short review with the clinic?'});
 if(/eGFR/.test(tr)||(eg&&last(eg)<60))add({id:'kid',cls:'unctl',title:'Kidney check: eGFR and UACR',why:eg?'eGFR '+eg.series.join(' → ')+' mL/min':'No eGFR on record',ref:'KDIGO 2024',book:{d:5,label:'Kidney labs'},why2:'Your kidney test results have been drifting down, which is worth checking early.',ask:'Can I book a blood and urine test at an in-network lab this week?'});
 if(a1c&&/HbA1c overdue/.test(tr))add({id:'a1t',cls:'gap',title:'HbA1c test at an in-network lab',why:m.trigger.detail,ref:'DoH-8',book:{d:4,label:'HbA1c lab'},why2:'It has been a while since your last diabetes blood test.',ask:'Shall I book an HbA1c test near you this week?'});
 else if(a1c&&last(a1c)>a1c.target)add({id:'a1c',cls:'unctl',title:'Diabetes treatment review',why:'HbA1c '+a1c.series.join(' → ')+' %',ref:'DoH-6 · ADA',book:{d:7,label:'Diabetes review'},why2:'Your HbA1c has risen to '+last(a1c)+'%, above your target of '+a1c.target+'%.',ask:'Would you like a review with your doctor to look at your diabetes treatment?'});
 const low=m.meds.filter(x=>x.pdc<80&&x.cls!=='Other').sort((a,b)=>a.pdc-b.pdc)[0];
 if(low)add({id:'adh',cls:'barrier',title:low.drug+' refill and barrier check',why:low.drug+' covers '+low.pdc+'% of days',ref:'DoH-7',book:{d:1,label:'Refill ready'},why2:'Our records show your '+low.drug+' refills have had some gaps.',ask:'Is anything making it hard to keep it going? I can arrange a refill for tomorrow.'});
 if(ldl&&last(ldl)>ldl.target)add({id:'ldl',cls:'unctl',title:'Cholesterol (statin) review',why:'LDL '+ldl.series.join(' → ')+' mmol/L',ref:'DoH-9',book:{d:10,label:'Lipid review'},why2:'Your LDL cholesterol is above target.',ask:'Can we add a cholesterol review to your next GP visit?'});
 if(dm)add({id:'eye',cls:'gap',title:'Eye exam',why:'No retinal exam on record in 24 months',ref:'DoH-13',book:{d:12,label:'Eye exam'},why2:'People with diabetes should have an eye check every year.',ask:'Shall I book an eye exam for you?'});
 if(dm)add({id:'foot',cls:'gap',title:'Foot exam',why:'No foot exam in 12 months',ref:'DoH-12 · IWGDF',book:{d:9,label:'Foot exam'},why2:'A yearly foot check helps prevent problems.',ask:'Can we add a foot check to your next visit?'});
 N.sort((a,b)=>ORDER.indexOf(a.cls)-ORDER.indexOf(b.cls));return N;}
function riskOf(m){const h=last(lab(m,'HbA1c')),e=last(lab(m,'eGFR'));const htn=m.conds.some(c=>/HTN/.test(c.short))||m.wear.bp[0]>=140;
 const C=Math.min(5,(h==null?0:h>=10?4:h>=9?3:h>=8?2:h>=7?1:0)+(htn?2:0));
 const M=Math.min(6,Math.max(0,m.conds.length-1)+(m.conds.some(c=>/IHD|HF/.test(c.short))?2:0));
 const K=e==null?0:e<30?3:e<45?2:e<60?1:0;const U=Math.min(5,Math.min(3,Math.round(m.er12/2))+(m.adm12>=2?2:m.adm12?1:0));
 const A=m.sex==='Male'?(m.age>=60?2:m.age>=40?1:0):(m.age>=70?2:m.age>=45?1:0);const R=C+M+K+U+A;
 return {R,tier:R>=13?4:R>=8?3:R>=4?2:1,prov:e==null,parts:[['Clinical',C,5],['Comorbidity',M,6],['Kidney',K,5],['Hospital use',U,5],['Age and sex',A,2]]};}
const TIER=['','Low','Moderate','High','Very high'];
const TIERC={1:['#E8F1EE','#3F7A66'],2:['#F4F0E4','#7A6440'],3:['#F4EFE6','#8A6A3E'],4:['#FBEEF0','#934450']};
const SLOTS=['09:30','10:15','11:00','12:30','14:00','15:15','16:30','17:30','18:15'];
function enrich(m,i){const N=needsFor(m),r=riskOf(m);const safety=N.some(n=>n.cls==='safety'),acute=N.some(n=>n.cls==='acute')||m.det.band==='Elevated';
 const alert=safety?'urgent':acute?'priority':'routine';
 const parts=m.name.split(' ');
 const slot=alert==='urgent'?'09:00':/after 4|evening/i.test(m.pref)?SLOTS[6+(i%3)]:/morning/i.test(m.pref)?SLOTS[i%3]:SLOTS[3+(i%3)];
 return Object.assign({},m,{id:m.mask,first:parts[0],initials:parts[0][0]+parts[parts.length-1][0],needs:N,risk2:r,alert,slot,
  consent:/enrolled|agreed/.test(m.status)?'granted':'pending',condTxt:m.conds.map(c=>c.name).join(', ')});}
const ALERT={urgent:['Urgent · clinician today','#FBEEF0','#934450',0],priority:['Priority · within 72 h','#F4EFE6','#8A6A3E',1],routine:['Routine','#F1F6FB','#345C8A',2]};
window.CCC={fmt,BASES,F,CATS,LABS,newRule,ruleOn,estimate,ruleText,ngql,check,parse,EXAMPLES,TRIG,COHORTS,CAMPAIGNS,CLS,TIER,TIERC,ALERT,
 members:()=>(window.CCC_MEMBERS||[]).map(enrich).sort((a,b)=>ALERT[a.alert][3]-ALERT[b.alert][3]||b.risk2.R-a.risk2.R)};
})();
