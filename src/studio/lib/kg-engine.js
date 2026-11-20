/* Knowledge-graph question → traversal → reusable feature. Illustrative, synthetic estimates. */
(function(){
'use strict';
const hash=s=>{let h=2166136261;for(const c of s){h^=c.charCodeAt(0);h=Math.imul(h,16777619);}return h>>>0;};
const rng=seed=>{let s=seed||1;return()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296;};};
const fmt=n=>Math.round(n).toLocaleString('en-US');
const COND=[[/type\s*2\s*diabet\w*|\bdiabet\w*|\bt2d\b/i,'E11','Type 2 diabetes',.072],[/hypertens\w*|high blood pressure|\bhtn\b/i,'I10','Hypertension',.11],[/kidney|\bckd\b/i,'N18','Chronic kidney disease',.025],[/heart failure|\bhf\b/i,'I50','Heart failure',.012],[/asthma/i,'J45','Asthma',.06],[/copd/i,'J44','COPD',.012],[/obes\w*/i,'E66','Obesity',.09],[/depress\w*/i,'F32','Depression',.03],[/cholesterol|dyslipid\w*|lipid/i,'E78','Dyslipidaemia',.15],[/coronary|angina|heart disease/i,'I25','Coronary artery disease',.03]];
const DRUG=[[/insulin/i,'A10A','Insulin',.012],[/sglt2|jardiance|empagliflozin/i,'A10BK','SGLT2 inhibitors',.03],[/glp-?1|ozempic|semaglutide/i,'A10BJ','GLP-1 agonists',.02],[/metformin/i,'A10BA','Metformin',.05],[/statin/i,'C10','Statins',.13],[/ace|arb|\bacei\b/i,'C09','ACE / ARB',.09],[/anticoag\w*|warfarin|apixaban|eliquis/i,'B01','Anticoagulants',.02],[/inhaler/i,'R03','Inhalers',.06]];
const SPEC=[[/cardiolog\w*/i,'CARD','Cardiology',.06],[/endocrin\w*/i,'ENDO','Endocrinology',.05],[/nephrolog\w*/i,'NEPH','Nephrology',.01],[/eye|ophthalm\w*|retina\w*/i,'OPH','Ophthalmology',.08],[/\bgp\b|family (medicine|doctor)|primary care/i,'GP','GP / family medicine',.6],[/dietit\w*|nutrition/i,'DIET','Dietitian',.02]];
const LAB=[[/hba1c|a1c/i,'HbA1c','%',.09],[/egfr/i,'eGFR','mL/min',.32],[/ldl/i,'LDL','mmol/L',.35],[/uacr|albumin/i,'UACR','mg/g',.08],[/blood pressure|\bbp\b|systolic/i,'SBP','mmHg',.4]];
const SCHEMA={tags:['Member','Card','Policy','Claim','ClaimLine','Diagnosis','Procedure','Observation','Drug','DrugClass','Provider','MemberFeature'],edges:['HAS_CARD','UNDER_POLICY','FILED','HAS_LINE','CODED_AS','FOR_PROCEDURE','FOR_OBSERVATION','FOR_DRUG','IN_CLASS','AT_PROVIDER']};
const EXAMPLES=['How many ER visits did each diabetic member have in the last 90 days?','Days since the last HbA1c result for members on insulin','Members filling SGLT2 inhibitors with no endocrinology visit in 12 months','Share of claims at out-of-network providers over 12 months','Heart failure members readmitted within 30 days of discharge'];
function windowDays(t){let m;
  if((m=t.match(/(\d+)\s*(days?|d)\b/)))return +m[1];
  if((m=t.match(/(\d+)\s*(month|mo)/)))return +m[1]*30;
  if((m=t.match(/(\d+)\s*(year|yr)/)))return +m[1]*365;
  if(/last year|past year|12 months/.test(t))return 365;if(/6 months|half/.test(t))return 180;if(/quarter|3 months/.test(t))return 90;return 365;}
function slug(s){return s.toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'').slice(0,40);}
function ask(text,base,cat){
  const t=(text||'').trim();if(!t)return null;const L=t.toLowerCase();
  const conds=COND.filter(c=>c[0].test(L)),drugs=DRUG.filter(d=>d[0].test(L)),specs=SPEC.filter(s=>s[0].test(L)),labs=LAB.filter(l=>l[0].test(L));
  const er=/\b(er|ed|emergency)\b/.test(L),adm=/admi\w*|readmi\w*|discharg\w*|hospital/.test(L),oon=/out[- ]of[- ]network|non[- ]network/.test(L),neg=/\bno\b|without|never|missing|not seen/.test(L);
  const days=windowDays(L);
  let kind='bool';if(/how many|number of|count|visits did/.test(L))kind='count';if(/days since|how long since|last .* (result|test)|time since/.test(L))kind='days';if(/share|percent|%|proportion|ratio/.test(L))kind='share';
  if(!conds.length&&!drugs.length&&!specs.length&&!labs.length&&!er&&!adm&&!oon)return {ok:false,msg:'I couldn’t find a condition, medicine, test, provider or visit type in that question. Try naming one.'};
  /* traversal */
  const path=[{n:'Member',v:'m'}];const hops=[];const where=[];let aggr='';
  const claimHop=()=>{if(!hops.some(h=>h.k==='claim')){hops.push({k:'claim'});path.push({e:'FILED'},{n:'Claim',v:'c'});}};
  if(conds.length){claimHop();path.push({e:'CODED_AS'},{n:'Diagnosis',v:'d'});where.push('('+conds.map(c=>'d.code STARTS WITH "'+c[1]+'"').join(' OR ')+')');}
  if(!hops.length&&(er||adm||oon))claimHop();
  if(drugs.length){path.push({br:1},{n:'Member',v:'m'},{e:'FILED'},{n:'Claim',v:'rx'},{e:'FOR_DRUG'},{n:'Drug'},{e:'IN_CLASS'},{n:'DrugClass',v:'dc'});where.push('('+drugs.map(d=>'dc.atc STARTS WITH "'+d[1]+'"').join(' OR ')+')');}
  if(labs.length){path.push({br:1},{n:'Member',v:'m'},{e:'FILED'},{n:'Claim',v:'lc'},{e:'FOR_OBSERVATION'},{n:'Observation',v:'o'});where.push('o.code IN ['+labs.map(l=>'"'+l[1]+'"').join(', ')+']');}
  if(specs.length||oon){path.push({br:1},{n:'Member',v:'m'},{e:'FILED'},{n:'Claim',v:'pc'},{e:'AT_PROVIDER'},{n:'Provider',v:'p'});if(specs.length)where.push((neg?'NOT ':'')+'p.specialty IN ['+specs.map(s=>'"'+s[1]+'"').join(', ')+']');}
  if(er)where.push('c.setting == "ED"');if(adm)where.push('c.setting == "IP"'+(/readmi|within/.test(L)?' AND c.days_since_prior_discharge <= 30':''));
  const cv=hops.length?'c':drugs.length?'rx':labs.length?'lc':'pc';
  where.push(cv+'.service_date >= date() - duration({days: '+days+'})');
  const sp=base==='seha'?'seha_kg':'daman_kg';
  const subj=[...conds.map(c=>c[2]),...drugs.map(d=>d[2]),...labs.map(l=>l[1]),...specs.map(s=>s[2])];
  let label,unit='',type='num',op='≥',v=1,valExpr;
  const win=days>=365?'12 mo':days>=180?'6 mo':days+' d';
  if(kind==='count'){valExpr='count(DISTINCT '+(er||adm?'c':'c')+')';label=(er?'ER visits':adm?'Admissions':'Claims')+(conds.length?' · '+conds[0][2].toLowerCase():'')+' · '+win;unit=er?'visits':adm?'stays':'claims';v=2;}
  else if(kind==='days'){valExpr='duration.between(max(o.observed_at), date()).days';label='Days since last '+(labs[0]?labs[0][1]:'visit')+(drugs.length?' · on '+drugs[0][2].toLowerCase():'');unit='days';v=180;}
  else if(kind==='share'){valExpr='100.0 * sum(CASE WHEN p.in_network == false THEN 1 ELSE 0 END) / count(pc)';label='Out-of-network claim share · '+win;unit='%';v=50;}
  else{type='bool';valExpr='true';label=subj.slice(0,2).join(' + ')+(neg&&specs.length?' · no '+specs[0][2].toLowerCase()+' visit':'')+(er?' · ER visit':'')+(adm?(/readmi/.test(L)?' · 30-day readmission':' · admitted'):'')+' · '+win;}
  if(!label.trim()||label.startsWith(' · '))label=label.replace(/^ · /,'');
  const key='kg_'+slug(label);
  const ng='USE '+sp+';\nMATCH '+renderPath(path)+'\nWHERE '+where.join('\n  AND ')+'\nWITH m, '+valExpr+' AS value\nRETURN id(m) AS member_vid, value;';
  /* estimate */
  /* one source of truth: for concepts the feature catalogue already knows, use the catalogue's prevalence
     (cat.shares, keyed by ICD-10 / ATC code) so a graph count matches the same rule built in Rules mode */
  const SH=(cat&&cat.shares)||{},pv=(code,dflt)=>SH[code]!=null?SH[code]:dflt;
  let share=1;conds.forEach(c=>share*=pv(c[1],c[3]));drugs.forEach(d=>share*=Math.min(.9,pv(d[1],d[3])*(conds.length?6:1)));labs.forEach(l=>share*=Math.min(.95,l[3]*(conds.length?4:1)));specs.forEach(s=>share*=neg?1-s[3]*(conds.length||drugs.length?4:1):s[3]);
  if(er)share*=.18*(days/365+.3);if(adm)share*=(/readmi/.test(L)?.04:.08)*(days/365+.3);if(oon)share*=.62;
  share=Math.max(.0004,Math.min(.92,share));
  const B={daman:412300,seha:742310,pura:318940}[base||'daman'];const n=Math.round(B*share);
  const R=rng(hash(t));
  const dist=kind==='bool'?null:Array.from({length:8},(_,i)=>Math.round(n*(kind==='count'?Math.exp(-i*.7):kind==='days'?(.6+R()*.8)/8:(.4+R())/8)*(.15+R()*.1)));
  const bins=kind==='count'?['1','2','3','4','5','6','7','8+']:kind==='days'?['<30','30–90','90–180','180–270','270–365','1–2 y','2–3 y','never']:['0–12','12–25','25–37','37–50','50–62','62–75','75–87','87–100'];
  const masks=['x57','x12','x84','x106','x35','x108','x23','x91'];
  const sample=masks.slice(0,5).map(mk=>({id:'M-'+mk,v:kind==='bool'?'true':kind==='count'?String(1+Math.floor(R()*4)):kind==='days'?String(Math.round(30+R()*420)):(R()*90).toFixed(0)+'%'}));
  const concepts=[...conds.map(c=>['Diagnosis',c[2]+' · '+c[1]]),...drugs.map(d=>['DrugClass',d[2]+' · '+d[1]]),...labs.map(l=>['Observation',l[1]]),...specs.map(s=>['Provider',(neg?'not ':'')+s[2]]),er?['Claim','ED setting']:null,adm?['Claim','Inpatient'+(/readmi/.test(L)?' · ≤30 d after discharge':'')]:null,oon?['Provider','Out of network']:null,['Window','last '+days+' days']].filter(Boolean);
  const est=type==='bool'?null:(o,val)=>{const x=+val,s=kind==='count'?Math.exp(-(x-1)*.7):kind==='days'?Math.max(.05,1-x/600):Math.max(.02,1-x/100);return Math.max(.0004,Math.min(.95,share*(o==='≤'?1-s:s)));};
  const feature={key,label,type,unit,op,v,share,cat:'Graph features',sub:'From the knowledge graph · '+win,ngql:ng,kind,
    ng:type==='bool'?()=>'m.MemberFeature.'+key+' == true':(o,a,b)=>o==='between'?'(m.MemberFeature.'+key+' >= '+a+' AND m.MemberFeature.'+key+' <= '+b+')':'m.MemberFeature.'+key+' '+({'≥':'>=','≤':'<=','=':'=='}[o]||o)+' '+a,
    est:est||undefined};
  /* each concept, and whether the existing feature catalogue can already express it (cat = catalogue codes) */
  const C=cat||{dx:[],atc:[],lab:[],spec:[]},yr=days>=365,readm=/readmi|within/.test(L);
  const parts=[...conds.map(c=>({label:c[2],ok:C.dx.includes(c[1]),term:c[2]})),
    ...drugs.map(d=>({label:d[2],ok:C.atc.includes(d[1]),term:d[2]})),
    ...labs.map(l=>({label:(kind==='days'?'Days since last ':'')+l[1],ok:C.lab.includes(l[1].toLowerCase())&&(kind!=='days'||true),term:l[1]})),
    ...specs.map(s=>({label:(neg?'No ':'')+s[2]+' visit',ok:!neg&&C.spec.includes(s[1]),term:s[2]})),
    er?{label:'ER visits · '+(yr?'12 months':'last '+days+' days'),ok:yr,term:'ED visits'}:null,
    adm?{label:readm?'30-day readmission':'Admissions · '+(yr?'12 months':'last '+days+' days'),ok:readm||yr,term:readm?'Readmitted':'admissions'}:null,
    oon?{label:'Out-of-network share',ok:true,term:'network'}:null].filter(Boolean);
  const terms=parts.map(p=>p.term);
  return {ok:true,kind,label,unit,path,concepts,ngql:ng,n,nTxt:fmt(n),pct:(share*100).toFixed(share<.01?2:1)+'%',bins,dist,sample,feature,days,parts,terms};
}
/* Describe flow: 1) look for existing features (the same search the Rules box uses), 2) only if the
   catalogue cannot express the question, fall back to a graph traversal that becomes a new feature. */
function resolve(text,base,E){
  const t=(text||'').trim();if(!t||!E)return null;
  const cat={dx:E.COND.map(c=>c[0]),atc:E.F.atc.opts.map(o=>o[0]),lab:E.LABS.map(l=>l[1].toLowerCase()),spec:E.F.spec.opts.map(o=>o[0]),
    shares:Object.fromEntries(E.COND.concat(E.F.atc.opts).map(c=>[c[0],c[2]]))};
  const r=ask(t,base,cat),hits=[],seen=new Set();
  const add=s=>{const k=s.kind+'|'+s.label;if(!seen.has(k)){seen.add(k);hits.push(s);}};
  E.suggest(t).forEach(add);
  if(r&&r.ok)r.terms.forEach(w=>E.suggest(w).filter(s=>s.kind!=='parse').slice(0,3).forEach(add));
  const saved=r&&r.ok&&E.F[r.feature.key]?r.feature.key:null;
  if(saved){hits.forEach((h,i)=>{if(h.f===saved)hits.splice(i,1);});hits.unshift({kind:'rule',f:saved,badge:'Graph',label:E.F[saved].label,sub:'Saved graph feature · already in your library'});}
  const missing=r&&r.ok?r.parts.filter(p=>!p.ok).map(p=>p.label):[];
  const status=saved?'saved':r&&r.ok?(missing.length?'new':'covered'):hits.length?'covered':'none';
  return {kg:r,hits:hits.slice(0,8),missing,status,saved};
}
function renderPath(p){let s='',first=true;p.forEach(x=>{if(x.br){s+=',\n      ';first=true;return;}if(x.n)s+='('+(x.v||'')+':'+x.n+')';else s+='-[:'+x.e+']->';first=false;});return s;}
window.KG={ask,resolve,EXAMPLES,SCHEMA,fmt};
})();
