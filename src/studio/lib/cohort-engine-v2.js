/* Cohort & Campaign Builder engine — field catalogue, estimates, nGQL, parsing, previews. Illustrative, synthetic numbers. */
(function(){
'use strict';
const fmt=n=>Math.round(n).toLocaleString('en-US');
const clamp=x=>Math.max(0,Math.min(1,x));
const hash=s=>{let h=2166136261;for(const c of s){h^=c.charCodeAt(0);h=Math.imul(h,16777619);}return h>>>0;};
const rng=seed=>{let s=seed||1;return()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296;};};
const Ncdf=(mu,sd)=>x=>{const z=(x-mu)/sd;const t=1/(1+.2316419*Math.abs(z));const d=.3989423*Math.exp(-z*z/2);const p=d*t*(.3193815+t*(-.3565638+t*(1.781478+t*(-1.821256+t*1.330274))));return z>0?1-p:p;};
const numEst=F=>(op,v,v2)=>op==='≥'?1-F(v):op==='≤'?F(v):op==='between'?Math.max(0,F(v2)-F(v)):Math.max(.002,F(v+.5)-F(v-.5));

const BASES=[{id:'daman',label:'Daman members',src:'Claims knowledge graph',n:412300},{id:'seha',label:'SEHA patients',src:'Encounters and labs',n:742310},{id:'pura',label:'PURA app users',src:'App and devices',n:318940}];
const COND=[['E11','Type 2 diabetes',.072],['I10','Hypertension',.11],['E78','Dyslipidaemia',.15],['E66','Obesity',.09],['N18','Chronic kidney disease',.025],['I50','Heart failure',.012],['I25','Coronary artery disease',.03],['I63','Stroke',.008],['J45','Asthma',.06],['J44','COPD',.012],['F32','Depression',.03],['E03','Hypothyroidism',.04],['K76','Fatty liver',.05],['M81','Osteoporosis',.015],['E10','Type 1 diabetes',.004],['O24','Gestational diabetes',.003],['C50','Breast cancer',.004],['B18','Chronic hepatitis',.006]];
const LABS=[['hba1c','HbA1c','%',[7.4,1.4],.09,'E11','≥',8,.1],['egfr','eGFR','mL/min',[88,22],.32,null,'≤',60,1],['uacr','UACR','mg/g',[40,80],.08,null,'≥',30,1],['ldl','LDL','mmol/L',[3,.9],.35,null,'≥',3.4,.1],['sbp','Systolic BP','mmHg',[128,16],.4,null,'≥',140,1],['bmi','BMI','kg/m²',[27.5,5],.3,null,'≥',30,.1],['tsh','TSH','mIU/L',[2.2,1.4],.15,null,'≥',4.5,.1]];
const ATC=[['A10','Diabetes medicines',.075],['A10A','Insulin',.012],['C09','ACE / ARB',.09],['C10','Statins',.13],['C07','Beta blockers',.04],['C03','Diuretics',.03],['B01','Anticoagulants',.02],['R03','Inhalers',.06],['N06A','Antidepressants',.03]];
const SPEC=[['GP','GP / family medicine',.6],['ENDO','Endocrinology',.05],['CARD','Cardiology',.06],['NEPH','Nephrology',.01],['OPH','Ophthalmology',.08],['DIET','Dietitian',.02]];
const numNg=(p,op,v,v2)=>op==='between'?'('+p+' >= '+v+' AND '+p+' <= '+v2+')':p+' '+({'≥':'>=','≤':'<=','=':'=='}[op]||op)+' '+v;
const inNg=(p,vs)=>vs.length===1?p+' == "'+vs[0]+'"':p+' IN ['+vs.map(v=>'"'+v+'"').join(', ')+']';
const F={
 age:{cat:'Who they are',label:'Age',type:'num',unit:'years',op:'between',v:40,v2:65,est:numEst(Ncdf(41,14)),ng:(o,v,v2)=>numNg('m.Member.age',o,v,v2)},
 gender:{cat:'Who they are',label:'Gender',type:'enum',opts:[['F','Female',.46],['M','Male',.54]],ng:vs=>inNg('m.Member.gender',vs)},
 nat:{cat:'Who they are',label:'Nationality',type:'enum',opts:[['UAE','UAE national',.22],['EXP','Expatriate',.78]],ng:vs=>inNg('m.Member.nationality_group',vs)},
 plan:{cat:'Who they are',label:'Plan',type:'enum',opts:[['ENH','Enhanced',.55],['BAS','Basic',.3],['THQ','Thiqa',.15]],ng:vs=>inNg('p.Policy.plan',vs),graph:1},
 region:{cat:'Who they are',label:'Region',type:'enum',opts:[['AUH','Abu Dhabi',.62],['AAN','Al Ain',.28],['ADH','Al Dhafra',.1]],ng:vs=>inNg('m.Member.region',vs)},
 dx:{cat:'Health',label:'Has condition',type:'code',opts:COND,sub:'ICD-10, any claim in 24 months',ng:vs=>'('+vs.map(c=>'m.MemberFeature.dx_'+c+' == true').join(' OR ')+')'},
 newdx:{cat:'Health',label:'Newly diagnosed',type:'code',opts:COND,sub:'first code in the last 90 days',scale:.08,ng:vs=>'('+vs.map(c=>'m.MemberFeature.dx_'+c+'_first_days <= 90').join(' OR ')+')'},
 ncc:{cat:'Health',label:'Chronic conditions',type:'num',unit:'conditions',short:'chronic conditions',op:'≥',v:2,est:numEst(Ncdf(.6,1.1)),ng:(o,v,v2)=>numNg('m.MemberFeature.chronic_count',o,v,v2)},
 lab:{cat:'Tests & results',label:'Latest result',type:'lab',sub:'last value in 12 months',ng:(o,v,v2,l)=>numNg('m.MemberFeature.lab_'+l+'_last',o,v,v2)},
 labage:{cat:'Tests & results',label:'Test overdue',type:'labage',sub:'no result in N days',ng:(o,v,v2,l)=>'(m.MemberFeature.lab_'+l+'_days IS NULL OR m.MemberFeature.lab_'+l+'_days > '+v+')'},
 ed:{cat:'Visits & admissions',label:'ED visits · 12 months',type:'num',unit:'visits',short:'ED visits',op:'≥',v:2,est:numEst(Ncdf(.25,.7)),ng:(o,v,v2)=>numNg('m.MemberFeature.ed_12m',o,v,v2)},
 ip:{cat:'Visits & admissions',label:'Unplanned admissions · 12 months',type:'num',unit:'stays',short:'admissions',op:'≥',v:1,est:numEst(Ncdf(.05,.35)),ng:(o,v,v2)=>numNg('m.MemberFeature.ip_unplanned_12m',o,v,v2)},
 readm:{cat:'Visits & admissions',label:'Readmitted within 30 days',type:'bool',share:.006,short:'Readmitted ≤ 30 days',ng:()=>'m.MemberFeature.readmit_30d == true'},
 nofu:{cat:'Visits & admissions',label:'No outpatient visit',type:'num',unit:'days',short:'days since a visit',op:'≥',v:180,est:(o,v)=>.34*Math.exp(-(v-180)/400),ng:(o,v,v2)=>numNg('m.MemberFeature.days_since_op',o,v,v2)},
 spec:{cat:'Visits & admissions',label:'Saw a specialist · 12 months',type:'code',opts:SPEC,ng:vs=>'('+vs.map(c=>'m.MemberFeature.spec_'+c+'_12m == true').join(' OR ')+')'},
 atc:{cat:'Medicines',label:'Takes medicine class',type:'code',opts:ATC,sub:'ATC, filled in 180 days',ng:vs=>'('+vs.map(c=>'m.MemberFeature.atc_'+c+' == true').join(' OR ')+')'},
 pdc:{cat:'Medicines',label:'Adherence (PDC)',type:'num',unit:'%',short:'% of days covered',op:'≤',v:80,est:(o,v)=>.12*(o==='≤'?v/80:1-(v/100)),ng:(o,v,v2)=>numNg('m.MemberFeature.pdc_min',o,v,v2)},
 poly:{cat:'Medicines',label:'Medicine classes',type:'num',unit:'classes',short:'medicine classes',op:'≥',v:5,est:numEst(Ncdf(1.2,1.6)),ng:(o,v,v2)=>numNg('m.MemberFeature.atc_count',o,v,v2)},
 eye:{cat:'Screenings',label:'Eye exam not on record',type:'bool',share:.06,sub:'24 months',short:'No eye exam',ng:()=>'m.MemberFeature.eye_exam_days > 730'},
 foot:{cat:'Screenings',label:'Foot exam not on record',type:'bool',share:.055,sub:'12 months',short:'No foot exam',ng:()=>'m.MemberFeature.foot_exam_days > 365'},
 cancer:{cat:'Screenings',label:'Cancer screening due',type:'bool',share:.18,short:'Screening due',ng:()=>'m.MemberFeature.cancer_screen_due == true'},
 vacc:{cat:'Screenings',label:'No flu vaccine this season',type:'bool',share:.6,short:'No flu vaccine',ng:()=>'m.MemberFeature.flu_vacc_season == false'},
 innet:{cat:'Network & cost',label:'Visits in network',type:'num',unit:'%',short:'% in network',op:'≤',v:25,est:(o,v)=>o==='≤'?.08+v/100*.4:.92-v/100*.5,ng:(o,v,v2)=>numNg('m.MemberFeature.in_network_share',o,v,v2)},
 cost:{cat:'Network & cost',label:'Claims cost · 12 months',type:'num',unit:'AED',short:'AED claims',op:'≥',v:50000,est:(o,v)=>{const s=.05*Math.pow(50000/Math.max(v,1000),1.1);return o==='≥'?Math.min(.9,s):1-s;},ng:(o,v,v2)=>numNg('m.MemberFeature.cost_12m',o,v,v2)},
 pura:{cat:'Engagement & consent',label:'Active on PURA',type:'bool',share:.19,sub:'30 days',short:'Active on PURA',ng:()=>'m.MemberFeature.pura_active_30d == true'},
 contacted:{cat:'Engagement & consent',label:'Contacted by the care team',type:'num',unit:'days ago or less',short:'days since contact',op:'≤',v:90,est:(o,v)=>.12*v/90,ng:(o,v,v2)=>numNg('m.MemberFeature.days_since_contact',o,v,v2),excl:1},
 optout:{cat:'Engagement & consent',label:'Opted out of contact',type:'bool',share:.03,ng:()=>'m.MemberFeature.contact_opt_out == true',excl:1},
 pregnant:{cat:'Engagement & consent',label:'Currently pregnant',type:'bool',share:.012,ng:()=>'m.MemberFeature.pregnant == true',excl:1},
 onco:{cat:'Engagement & consent',label:'Active cancer treatment',type:'bool',share:.02,ng:()=>'m.MemberFeature.onc_active == true',excl:1}
};
const CATS=['Who they are','Health','Tests & results','Visits & admissions','Medicines','Screenings','Network & cost','Engagement & consent'];
const labOf=k=>LABS.find(l=>l[0]===k)||LABS[0];
let rid=0;
function newRule(f,preset){const d=F[f];const r={id:++rid,f};
 if(d.type==='num'){r.op=d.op;r.v=d.v;r.v2=d.v2??d.v;}else if(d.type==='enum'||d.type==='code')r.vs=[];
 else if(d.type==='lab')Object.assign(r,labPatch('hba1c'));else if(d.type==='labage'){r.l='hba1c';r.v=180;}
 return Object.assign(r,preset||{});}
function labPatch(l){const L=labOf(l);return {l,op:L[6],v:L[7],v2:+(L[7]+L[3][1]).toFixed(L[8]<1?1:0)};}
const ruleOn=r=>{const d=F[r.f];return !((d.type==='enum'||d.type==='code')&&!r.vs.length);};
function share(r,cb){const d=F[r.f];const dxIn=c=>cb.inc.some(x=>x.f==='dx'&&x.vs.includes(c));
 if(r.f==='pdc'&&cb.inc.some(x=>(x.f==='dx'||x.f==='atc')&&x.vs.length))return clamp(r.op==='≤'?.4*r.v/80:1-.4*r.v/80);
 if(d.type==='num')return clamp(d.est(r.op,+r.v,+r.v2));if(d.type==='bool')return d.share;
 if(d.type==='enum')return r.vs.length?r.vs.reduce((s,v)=>s+(d.opts.find(o=>o[0]===v)||[0,0,0])[2],0):1;
 if(d.type==='code')return r.vs.length?clamp(1-r.vs.reduce((p,v)=>p*(1-(d.opts.find(o=>o[0]===v)||[0,0,0])[2]*(d.scale||1)),1)):1;
 const L=labOf(r.l);
 if(d.type==='lab'){let s=numEst(Ncdf(L[3][0],L[3][1]))(r.op,+r.v,+r.v2)*L[4];if(L[5]){const pv=COND.find(c=>c[0]===L[5])[2];s=dxIn(L[5])?Math.min(.95,s/pv):s;}return clamp(s);}
 if(d.type==='labage'){let s=clamp(.45*Math.exp(-(r.v-180)/500));if(L[5])s=dxIn(L[5])?s:s*COND.find(c=>c[0]===L[5])[2];return s;}return 1;}
function estimate(cb){const B=BASES.find(b=>b.id===cb.base).n;let n=B;const steps=[],alone={};const inc=cb.inc.filter(ruleOn),exc=cb.exc.filter(ruleOn);
 inc.forEach(r=>alone[r.id]=B*share(r,cb));
 if(cb.logic==='any'&&inc.length){n=B*(1-inc.reduce((a,r)=>a*(1-share(r,cb)),1));steps.push({id:'any',t:'Any of '+inc.length+' rules',n});}
 else inc.forEach(r=>{n*=share(r,cb);steps.push({id:r.id,t:ruleText(r),n});});
 exc.forEach(r=>{n*=(1-share(r,cb));steps.push({id:r.id,t:'Not: '+ruleText(r),n,ex:1});});
 return {B,n,steps,alone};}
const fv=v=>+v>=1000?fmt(+v):v;
function ruleText(r){const d=F[r.f];
 if(d.type==='num')return d.label+' '+(r.op==='between'?r.v+'–'+r.v2:r.op+' '+fv(r.v))+(d.unit?' '+d.unit:'');
 if(d.type==='bool')return d.label;
 if(d.type==='enum'||d.type==='code')return d.label+': '+(r.vs.map(v=>(d.opts.find(o=>o[0]===v)||[v,v])[1]).join(' or ')||'any');
 const L=labOf(r.l);if(d.type==='lab')return L[1]+' '+(r.op==='between'?r.v+'–'+r.v2:r.op+' '+r.v)+' '+L[2];
 return L[1]+' not done in '+r.v+' days';}
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
 const vl=t.match(/\*\s*\d*\s*\.\.\s*(\d*)/);C.push(['Bounded paths',!vl||(vl[1]&&+vl[1]<=4),vl?'max '+(vl[1]||'∞')+' hops':'no open paths']);
 return {ok:C.every(c=>c[1]),C};}
const LEX=[[/type\s*2\s*diabet\w*|\bdiabet\w*|\bt2d\b/i,'E11'],[/hypertens\w*|high blood pressure|\bhtn\b/i,'I10'],[/kidney disease|\bckd\b/i,'N18'],[/heart failure/i,'I50'],[/asthma/i,'J45'],[/copd/i,'J44'],[/obes\w*/i,'E66'],[/depress\w*/i,'F32'],[/cholesterol|dyslipid\w*/i,'E78'],[/coronary|heart disease/i,'I25'],[/stroke/i,'I63'],[/fatty liver/i,'K76']];
function parse(text){let t=' '+text.toLowerCase()+' ';const inc=[],exc=[];
 const parts=t.split(/\b(?:excluding|except|but not|without|other than)\b/);const pos=parts[0],neg=parts.slice(1).join(' ');
 const dx=[],dxN=[];LEX.forEach(([re,c])=>{if(re.test(pos))dx.push(c);else if(re.test(neg))dxN.push(c);});
 if(dx.length)inc.push(newRule('dx',{vs:dx}));let m;
 const labRe=[[/hba1c\s*(?:above|over|>=?|≥|of|at least)?\s*(\d+(?:\.\d)?)/,'hba1c','≥'],[/egfr\s*(?:below|under|<|less than)\s*(\d+)/,'egfr','≤'],[/(?:bp|blood pressure)\s*(?:above|over|>)\s*(\d+)/,'sbp','≥'],[/ldl\s*(?:above|over|>)\s*(\d+(?:\.\d)?)/,'ldl','≥'],[/bmi\s*(?:above|over|>)\s*(\d+)/,'bmi','≥']];
 labRe.forEach(([re,l,op])=>{if((m=t.match(re))){inc.push(newRule('lab',Object.assign(labPatch(l),{op,v:+m[1]})));t=t.replace(m[0],' ');}});
 if((m=t.match(/(?:over|older than|aged|age|above)\s*(\d{2})\b/)))inc.push(newRule('age',{op:'≥',v:+m[1]}));
 if((m=t.match(/(\d)\s*(?:or more)?\s*(?:er|ed|emergency)\b/)))inc.push(newRule('ed',{op:'≥',v:+m[1]}));
 if(/admitted|admission|hospitali[sz]ed|discharg/.test(t))inc.push(newRule('ip'));
 if(/miss\w* (?:refills?|medicines?|doses)|adherence|not taking/.test(t))inc.push(newRule('pdc'));
 if((m=t.match(/no (?:gp |doctor |outpatient )?visit[^\d]*(\d+)\s*months?/)))inc.push(newRule('nofu',{op:'≥',v:+m[1]*30}));else if(/no (?:gp |doctor |outpatient )?visit|not seen/.test(t))inc.push(newRule('nofu'));
 if(/\bwomen\b|\bfemale/.test(t))inc.push(newRule('gender',{vs:['F']}));else if(/\bmen\b|\bmale\b/.test(t))inc.push(newRule('gender',{vs:['M']}));
 if(/out of network|outside (?:the )?network/.test(t))inc.push(newRule('innet'));
 if(/eye exam/.test(t))inc.push(newRule('eye'));if(/foot exam/.test(t))inc.push(newRule('foot'));
 if(/hba1c (?:overdue|not done|missing)|no hba1c/.test(t))inc.push(newRule('labage'));
 if(/statin/.test(pos))inc.push(newRule('atc',{vs:['C10']}));if(/insulin/.test(pos))inc.push(newRule('atc',{vs:['A10A']}));
 if(/high.?cost|expensive/.test(t))inc.push(newRule('cost'));
 if(dxN.length)exc.push(newRule('dx',{vs:dxN}));
 if(/cancer|oncology/.test(neg))exc.push(newRule('onco'));if(/pregnan/.test(t))exc.push(newRule('pregnant'));
 return {inc,exc};}
const EXAMPLES=['People with diabetes and HbA1c above 9 who missed refills, excluding cancer','Hypertension with blood pressure above 150 and no GP visit in 6 months','Over 60 with 2 or more ER visits and heart failure','Women with diabetes whose eye exam is not on record'];
function suggest(q){const t=q.trim().toLowerCase();if(t.length<2)return [];const out=[];const seen=new Set();const push=o=>{if(!seen.has(o.label)){seen.add(o.label);out.push(o);}};
 const p=parse(q);const words=t.split(/\s+/).length;
 if((words>=3||/\d/.test(t))&&(p.inc.length||p.exc.length))push({kind:'parse',badge:'Sentence',label:'Turn into '+p.inc.length+' rule'+(p.inc.length===1?'':'s')+(p.exc.length?' + '+p.exc.length+' exclusion'+(p.exc.length===1?'':'s'):''),sub:[...p.inc.map(ruleText),...p.exc.map(r=>'not '+ruleText(r))].join(' · ')});
 COND.forEach(c=>{if(c[1].toLowerCase().includes(t)||c[0].toLowerCase()===t)push({kind:'rule',f:'dx',preset:{vs:[c[0]]},badge:'Condition',label:'Has condition: '+c[1],sub:'ICD-10 '+c[0]+' · about '+fmt(c[2]*412300)+' Daman members'});});
 ATC.forEach(c=>{if(c[1].toLowerCase().includes(t)||c[0].toLowerCase()===t)push({kind:'rule',f:'atc',preset:{vs:[c[0]]},badge:'Medicine',label:'Takes '+c[1],sub:'ATC '+c[0]});});
 LABS.forEach(L=>{if(L[1].toLowerCase().includes(t)||L[0].includes(t)){push({kind:'rule',f:'lab',preset:labPatch(L[0]),badge:'Result',label:L[1]+' '+L[6]+' '+L[7]+' '+L[2],sub:'Latest result in 12 months'});push({kind:'rule',f:'labage',preset:{l:L[0],v:180},badge:'Overdue',label:L[1]+' test overdue',sub:'No result in 180 days'});}});
 Object.keys(F).forEach(k=>{const d=F[k];if(d.label.toLowerCase().includes(t)||d.cat.toLowerCase().includes(t)||(d.sub||'').toLowerCase().includes(t))push({kind:'rule',f:k,badge:d.excl?'Exclude':d.kg?'Graph':d.cat.split(' ')[0],label:d.label,sub:d.excl?'Adds to exclusions':d.kg?(d.sub||d.cat)+(d.nTxt?' · '+d.nTxt+' members':''):d.cat});});
 return out.slice(0,7);}
function lint(cb,e,capWeek){const L=[];const has=cb.inc.some(ruleOn);
 [...cb.inc,...cb.exc].forEach(r=>{const d=F[r.f];if((d.type==='enum'||d.type==='code')&&!r.vs.length)L.push({lvl:'warn',t:'Pick at least one value for “'+d.label+'”, or remove the rule.'});});
 if(!has)L.push({lvl:'info',t:'Add a rule to start narrowing the population.'});
 if(has&&e.n<50)L.push({lvl:'error',t:'Fewer than 50 members. Loosen a rule so results stay reliable and private.'});
 if(has&&!cb.exc.some(r=>r.f==='optout'))L.push({lvl:'warn',t:'Members who opted out of contact are still included.',fix:{label:'Exclude them',exc:'optout'}});
 if(cb.inc.some(r=>r.f==='pdc')&&!cb.inc.some(r=>(r.f==='dx'||r.f==='atc')&&r.vs.length))L.push({lvl:'info',t:'Adherence is measured on chronic medicines. Pair it with a condition or a medicine class.',fix:{label:'Add a condition',inc:'dx'}});
 if(cb.inc.some(r=>r.f==='lab'&&r.l==='hba1c')&&!cb.inc.some(r=>r.f==='dx'&&r.vs.includes('E11')))L.push({lvl:'info',t:'HbA1c is mostly tested in diabetes. Add the diagnosis to keep the cohort clinical.',fix:{label:'Add diabetes',inc:'dx',preset:{vs:['E11']}}});
 const seen={};cb.inc.forEach(r=>{if(seen[r.f]&&cb.logic==='all'&&F[r.f].type!=='lab')L.push({lvl:'info',t:'Two “'+F[r.f].label+'” rules: members must match both.'});seen[r.f]=1;});
 const wk=e.n*.9/capWeek;if(has&&e.n>=50&&wk>26)L.push({lvl:'warn',t:'Very broad: a 6-nurse team needs about '+Math.round(wk)+' weeks to call everyone once. Add a rule to focus.'});
 if(has&&e.n>=50&&!L.some(x=>x.lvl==='error'||x.lvl==='warn'))L.unshift({lvl:'ok',t:'Ready to save. A 6-nurse team reaches everyone in about '+Math.max(1,Math.ceil(wk))+' week'+(Math.ceil(wk)>1?'s':'')+'.'});
 return L;}
function rangeOf(r){return r.op==='between'?[+r.v,+r.v2]:r.op==='≥'?[+r.v,120]:r.op==='≤'?[0,+r.v]:[+r.v,+r.v];}
function restrict(opts,r){if(!r||!r.vs.length)return opts.map(o=>[o[1],o[2]]);const t=opts.filter(o=>r.vs.includes(o[0])).reduce((s,o)=>s+o[2],0)||1;return opts.map(o=>[o[1],r.vs.includes(o[0])?o[2]/t:0]);}
const AGEB=[['18–39',18,39],['40–54',40,54],['55–64',55,64],['65+',65,90]];
function profile(cb){const inc=cb.inc.filter(ruleOn);const dx=inc.filter(r=>r.f==='dx').flatMap(r=>r.vs);const chronic=dx.length||inc.some(r=>['ncc','ip','pdc','poly'].includes(r.f));
 let age=chronic?[.14,.34,.31,.21]:[.38,.33,.19,.1];const ar=inc.find(r=>r.f==='age');
 if(ar){const [lo,hi]=rangeOf(ar);age=age.map((s,i)=>{const b=AGEB[i];const ov=Math.max(0,Math.min(hi,b[2])-Math.max(lo,b[1])+1)/(b[2]-b[1]+1);return s*ov;});}
 const at=age.reduce((a,b)=>a+b,0)||1;age=age.map(s=>s/at);
 let fem=dx.some(c=>['I50','I25','I63'].includes(c))?.38:dx.includes('O24')?1:.46;const g=inc.find(r=>r.f==='gender');if(g&&g.vs.length===1)fem=g.vs[0]==='F'?1:0;
 const net=inc.find(r=>r.f==='innet');const inn=net?(net.op==='≤'?Math.min(.95,net.v/100*.6):.85):.58;
 return {age:AGEB.map((b,i)=>[b[0],age[i]]),sex:[['Women',fem],['Men',1-fem]],plan:restrict(F.plan.opts,inc.find(r=>r.f==='plan')),region:restrict(F.region.opts,inc.find(r=>r.f==='region')),net:[['In network',inn],['Out of network',1-inn]]};}
const NF=['Fatima Al Mansoori','Aisha Al Ketbi','Priya Nair','Maryam Al Suwaidi','Noura Al Shamsi','Hessa Al Nuaimi','Leila Haddad','Sara Thomas','Reem Al Falasi','Anjali Pillai'];
const NM=['Ahmed Al Hammadi','Mohammed Khan','Rajesh Kumar','Joseph Mathew','Salem Al Dhaheri','Imran Qureshi','Anil Menon','Khalid Al Zaabi','Omar Haddad','Saeed Al Mazrouei'];
const strip=r=>Object.assign({},r,{id:0});
function factOf(r,R){const d=F[r.f];
 if(d.type==='code'){const v=r.vs[Math.floor(R()*r.vs.length)];return (d.opts.find(o=>o[0]===v)||[v,v])[1];}
 if(d.type==='enum')return r.f==='gender'?null:(d.opts.find(o=>o[0]===r.vs[Math.floor(R()*r.vs.length)])||['',''])[1];
 if(d.type==='bool')return d.short||d.label;
 if(d.type==='lab'){const L=labOf(r.l),sd=L[3][1];let x=r.op==='≥'?+r.v+R()*sd*.8:r.op==='≤'?+r.v-R()*sd*.6:r.op==='between'?+r.v+(r.v2-r.v)*R():+r.v;x=Math.max(0,x);return L[1]+' '+(L[8]<1?x.toFixed(1):Math.round(x))+(L[2]==='%'?'%':' '+L[2]);}
 if(d.type==='labage'){const L=labOf(r.l);return L[1]+' '+(+r.v+Math.round(R()*220))+' days ago';}
 if(r.f==='age')return null;const [lo,hi]=rangeOf(r);const span=r.f==='cost'?40000:r.f==='nofu'?240:r.f==='pdc'||r.f==='innet'?30:3;
 let x=r.op==='≥'?lo+R()*span:r.op==='≤'?Math.max(0,hi-R()*span):lo+(hi-lo)*R();x=Math.round(x);
 if(r.f==='cost')return 'AED '+fmt(x)+' claims';if(r.f==='pdc'||r.f==='innet')return Math.min(100,x)+d.short;return x+' '+d.short;}
function sample(cb,k){const R=rng(hash(JSON.stringify([cb.base,cb.logic,cb.inc.map(strip),cb.exc.map(strip)])));const pr=profile(cb);const inc=cb.inc.filter(ruleOn);const ar=inc.find(r=>r.f==='age');const out=[];const used={};
 for(let i=0;i<k;i++){const fem=R()<pr.sex[0][1];const pool=fem?NF:NM;let j=Math.floor(R()*pool.length);while(used[pool[j]])j=(j+1)%pool.length;used[pool[j]]=1;const nm=pool[j].split(' ');
  let u=R(),b=0;while(b<3&&u>pr.age[b][1]){u-=pr.age[b][1];b++;}let lo=AGEB[b][1],hi=AGEB[b][2];if(ar){const [a1,a2]=rangeOf(ar);lo=Math.max(lo,a1);hi=Math.min(hi,a2);if(lo>hi){lo=a1;hi=Math.min(a2,90);}}
  const facts=(cb.logic==='any'?[inc[Math.floor(R()*inc.length)]].filter(Boolean):inc).map(r=>factOf(r,R)).filter(Boolean).slice(0,3);
  out.push({id:'x'+(100+Math.floor(R()*900)),name:nm[0]+' '+nm[nm.length-1][0]+'.',ini:nm[0][0]+nm[nm.length-1][0],age:Math.round(lo+(hi-lo)*R()),sex:fem?'F':'M',facts});}
 return out;}
const dxOf=rules=>rules.filter(r=>r.f==='dx'&&ruleOn(r)).flatMap(r=>r.vs);
function overlap(cb,e,cohorts){const mine=dxOf(cb.inc),mf=new Set(cb.inc.filter(ruleOn).map(r=>r.f));
 return cohorts.filter(c=>c.id!==cb.from&&c.base===cb.base).map(c=>{const theirs=dxOf(c.rules.inc);const sh=mine.filter(x=>theirs.includes(x)).length;const sf=c.rules.inc.filter(r=>mf.has(r.f)&&r.f!=='dx').length;
  const ov=sh?Math.min(e.n,c.n)*Math.min(.92,.5+.15*sf):e.n*c.n/e.B*(1+.6*sf);return {id:c.id,name:c.name,n:Math.min(ov,e.n),pct:e.n?Math.min(1,ov/e.n):0};}).sort((a,b)=>b.pct-a.pct).slice(0,4);}
function build(spec){return spec.map(([f,p])=>newRule(f,p));}
const TEMPLATES=[
 {name:'Diabetes above goal',d:'Type 2 diabetes with HbA1c of 8% or more',inc:[['dx',{vs:['E11']}],['lab',{l:'hba1c',op:'≥',v:8,v2:9.4}]]},
 {name:'Hypertension drifting from care',d:'Hypertension and no outpatient visit in 6 months',inc:[['dx',{vs:['I10']}],['nofu',{op:'≥',v:180}]]},
 {name:'Post-discharge chronic',d:'A chronic condition and an unplanned admission',inc:[['ncc',{op:'≥',v:1}],['ip',{op:'≥',v:1}]]},
 {name:'Diabetes care gaps',d:'Type 2 diabetes missing eye and foot exams',inc:[['dx',{vs:['E11']}],['eye'],['foot']]}];
function fromTemplate(t){return {inc:build(t.inc),exc:build([['optout']]),logic:'all'};}
function trend(n,seed){const R=rng(seed);const a=[];let v=n*(.82+R()*.08);for(let i=0;i<12;i++){v+=(n-v)/(12-i)+(R()-.5)*n*.02;a.push(Math.round(v));}a[11]=n;return a;}
function seedCohorts(){return [
 {id:'COH-0101',name:'Diabetes · above goal',base:'daman',n:13420,refresh:'Nightly',owner:'Population health',src:'Builder',rules:{logic:'all',inc:build([['dx',{vs:['E11']}],['lab',{l:'hba1c',op:'≥',v:8,v2:9.4}]]),exc:build([['optout']])},versions:[{v:1,date:'2 Sep',n:15210,note:'Created · HbA1c ≥ 9 %'},{v:2,date:'14 Oct',n:13420,note:'HbA1c threshold 9 → 8 %, opt-outs excluded'}]},
 {id:'COH-0102',name:'Hypertension · drifting from care',base:'daman',n:21980,refresh:'Every 3 days',owner:'Population health',src:'Builder',rules:{logic:'all',inc:build([['dx',{vs:['I10']}],['nofu',{op:'≥',v:180}]]),exc:build([['optout']])},versions:[{v:1,date:'21 Sep',n:21980,note:'Created'}]},
 {id:'COH-0103',name:'Post-discharge chronic',base:'daman',n:4120,refresh:'Daily',owner:'Care management',src:'Builder',rules:{logic:'all',inc:build([['ncc',{op:'≥',v:1}],['ip',{op:'≥',v:1}]]),exc:build([['optout']])},versions:[{v:1,date:'5 Oct',n:4120,note:'Created'}]},
 {id:'COH-0104',name:'Diabetes · eye and foot gaps',base:'daman',n:9840,refresh:'Weekly',owner:'Quality',src:'nGQL',rules:{logic:'all',inc:build([['dx',{vs:['E11']}],['eye'],['foot']]),exc:build([['optout']])},versions:[{v:1,date:'28 Oct',n:9840,note:'Loaded from nGQL'}]}
].map((c,i)=>Object.assign(c,{trend:trend(c.n,i+7)}));}
const TRIG=[['Trig1','HbA1c above target','E11'],['Trig2','BP treatment review','I10'],['Trig3','Hypoglycaemia','E11'],['Trig4','Post-discharge care','*'],['Trig5','Kidney check','*'],['Trig6','HbA1c test due','E11'],['Trig7','Potassium due','I10'],['Trig8','Nutrition and education','E11'],['Trig9','Medication adherence','*'],['Trig10','New diagnosis','*'],['Trig11','Annual labs due','*'],['Trig12','Eye exam due','E11'],['Trig13','High-risk foot','E11']];
function seedCampaigns(){return [
 {id:'CMP-0101',name:'Diabetes control',goal:'Bring HbA1c to goal',inc:['COH-0101'],exc:[],start:'2026-11-23',weeks:8,prio:1,mode:'automated',trig:[],ch:['Voice'],nurses:8,calls:25,hold:10,status:'Live'},
 {id:'CMP-0102',name:'Back into care',goal:'Re-engage members without follow-up',inc:['COH-0102','COH-0103'],exc:[],start:'2026-12-01',weeks:6,prio:2,mode:'business',trig:['Trig9','Trig4'],ch:['Voice','WhatsApp'],nurses:6,calls:25,hold:10,status:'Scheduled'},
 {id:'CMP-0103',name:'Eye and foot catch-up',goal:'Close annual screening gaps',inc:['COH-0104'],exc:['COH-0101'],start:'2027-01-04',weeks:6,prio:3,mode:'business',trig:['Trig12','Trig13'],ch:['WhatsApp','SMS'],nurses:3,calls:30,hold:10,status:'Draft'}];}
function campN(c,cohorts){const t=c.inc.reduce((s,id)=>s+((cohorts.find(x=>x.id===id)||{n:0}).n),0)*(c.inc.length>1?.88:1);return c.exc.reduce(s=>s*.85,t);}
function dxForCamp(c,cohorts){const s=new Set();c.inc.forEach(id=>{const k=cohorts.find(x=>x.id===id);if(k)dxOf(k.rules.inc).forEach(x=>s.add(x));});return [...s];}
function capacity(c,n){const treated=n*(1-c.hold/100),wk=c.nurses*c.calls*5,weeksAll=wk?treated/wk:0,cov=treated?Math.min(1,wk*c.weeks/treated):0;const need=Math.ceil(treated/(c.calls*5*Math.max(1,c.weeks)));return {treated,wk,weeksAll,cov,need,hold:n*c.hold/100};}
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const D0=Date.UTC(2026,10,16);
const fdate=iso=>{const d=new Date(iso+'T00:00:00Z');return d.getUTCDate()+' '+MON[d.getUTCMonth()];};
const weekCol=iso=>Math.floor((Date.parse(iso+'T00:00:00Z')-D0)/(7*864e5));
const WEEKS=Array.from({length:16},(_,i)=>{const d=new Date(D0+i*7*864e5);return {d:d.getUTCDate(),m:MON[d.getUTCMonth()],first:i===0||d.getUTCDate()<=7};});
window.CohortEngine={fmt,hash,BASES,F,CATS,LABS,COND,labOf,labPatch,newRule,ruleOn,estimate,ruleText,ngql,check,parse,suggest,lint,profile,sample,overlap,EXAMPLES,TEMPLATES,fromTemplate,seedCohorts,TRIG,seedCampaigns,campN,dxForCamp,capacity,fdate,weekCol,WEEKS,trend,TODAY:'2026-11-20'};
})();
