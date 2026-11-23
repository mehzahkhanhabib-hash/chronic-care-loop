"""Build LINEAGE.html: every front-end element → the tables and views it reads or writes,
with a clickable definition of each table (kind, who writes it, columns, SQL for views).
Everything is parsed from sql/01_schema.sql, sql/06_views.sql and mapping/ui_to_column.csv,
so the page never drifts from the kit.   Run from two-day-build/:  python3 tools/make_lineage_page.py
"""
import re, csv, json, html, pathlib, collections
HERE = pathlib.Path(__file__).resolve().parent.parent
sch = (HERE / 'sql/01_schema.sql').read_text()
vw = (HERE / 'sql/06_views.sql').read_text()
rows = list(csv.DictReader(open(HERE / 'mapping/ui_to_column.csv', encoding='utf-8')))

def split_top(s):
    out, d, cur = [], 0, ''
    for ch in s:
        if ch == '(': d += 1
        if ch == ')': d -= 1
        if ch == ',' and d == 0: out.append(cur); cur = ''
        else: cur += ch
    if cur.strip(): out.append(cur)
    return out

tables = collections.OrderedDict()
for m in re.finditer(r'CREATE (REFERENCE |ROWSTORE )?TABLE IF NOT EXISTS (\w+) \(([^\n]*)\n(.*?)\n\);', sch, re.S):
    kind, name, head, body = (m.group(1) or '').strip(), m.group(2), m.group(3), m.group(4)
    comment = head.split('--', 1)[1].strip() if '--' in head else ''
    cols, keys = [], []
    for line in body.split('\n'):
        code, _, cm = line.partition('--')
        parts = split_top(code)
        for i, p in enumerate(parts):
            p = p.strip().strip('`')
            if not p: continue
            if re.match(r'(PRIMARY KEY|SHARD KEY|KEY|UNIQUE)', p): keys.append(p); continue
            mm = re.match(r'`?(\w+)`?\s+([A-Z]+(?:\([^)]*\))?)(.*)', p)
            if mm:
                flags = mm.group(3).strip()
                cols.append({'c': mm.group(1), 't': mm.group(2) + (' PK' if 'PRIMARY KEY' in flags else ''), 'd': cm.strip() if i == len(parts) - 1 else ''})
    tables[name] = {'name': name, 'store': kind, 'comment': comment, 'cols': cols, 'keys': keys}

views = collections.OrderedDict()
for m in re.finditer(r'(?:--\s*([^\n]*)\n)?DROP VIEW IF EXISTS \w+;\nCREATE VIEW (\w+) AS\n(.*?);\n', vw, re.S):
    body = m.group(3)
    refs = sorted({w for w in re.findall(r'\b(?:FROM|JOIN)\s+(\w+)', body) if w in tables or w.startswith('v_')})
    views[m.group(2)] = {'name': m.group(2), 'comment': (m.group(1) or '').strip(' ─'), 'sql': body, 'refs': refs}

KIND = {}
for t in tables:
    if t.startswith('rule_'): KIND[t] = 'rule'
    elif t in ('run_config', 'nurse', 'nurse_language', 'campaign'): KIND[t] = 'config'
    elif t in ('stg_extract', 'member'): KIND[t] = 'source'
    elif t == 'outcome': KIND[t] = 'input'
    else: KIND[t] = 'derived'
for v in views: KIND[v] = 'view'
KIND_INFO = {
 'source':  ('Loaded', 'Loaded from the member extract by sql/03_load.sql. Nothing is typed in: stg_extract is the raw TSV, member is the typed copy whose column list comes from rule_field (is_loaded = 1). Step 3 of the run also writes the derived score columns onto member (r_total, tier, alert, contact_priority, baseline, next_touchpoint).'),
 'rule':    ('Rule table', 'Rulebook rows, not code. Source is rules/<table>.csv; tools/gen_sql.py writes them into sql/02_rules.sql. REFERENCE table: replicated to every SingleStore node. Change a threshold, an action or a class order here and the next run changes the screens.'),
 'config':  ('Hard-coded setup', 'Demo configuration written by sql/02b_setup.sql: run dates, the nurses and their languages and capacity, the demo campaigns. Edit freely before the demo. campaign is also written by Studio screen 1 (POST /campaigns compiles the builder rules into where_sql).'),
 'derived': ('Derived by the run', 'Written by sql/04_nightly.sql (POST /runs/rules) from member + the rule tables. Rebuilt or upserted every run; never edited by hand. Follow-up rows in action are added by sql/05_followup.sql when a nurse records an outcome.'),
 'input':   ('Nurse input', 'Written only by the Care Portal through POST /actions/{id}/outcome (sql/05_followup.sql). One row per decision the nurse records; the next run reads it (hold 90 days, Reported, retry, escalate).'),
 'view':    ('View (derived, read-only)', 'A SELECT over the tables below; the screens read views, never the tables. Redesigning a screen changes HTML only as long as it reads the same view columns.'),
}
WRITER = {
 'stg_extract': '03_load.sql · LOAD DATA from member_features.tsv', 'member': '03_load.sql (typed copy) · 04_nightly step 3 (scores, tier, alert, priority) · 05_followup (consent)',
 'campaign_member': '04_nightly step 1 · who is in which campaign, 10% holdout', 'work_member': '04_nightly step 1 and 7 · scratch: owner campaign, top need, open contact',
 'member_signal': '04_nightly step 2 · one row per member per trigger: fired / cannot_tell / not fired + evidence (conditions from rules/rule_condition.csv)',
 'care_plan_need': '04_nightly step 4 (open, hold, close in claims) and 5 (slots) · 05_followup (gap_state after an outcome)',
 'work_rank': '04_nightly step 5 · ROW_NUMBER by class_order, trigger_order per member', 'action': '04_nightly step 6 (care-plan action per CURRENT need) and 7 (call or nudge) · 05_followup (follow-up, retry, escalation)',
 'worklist': '04_nightly step 8 · today / queued per nurse, language match, continuity with the nurse holding open actions', 'outcome': '05_followup via POST /actions/{id}/outcome',
 'run_config': '02b_setup.sql', 'nurse': '02b_setup.sql', 'nurse_language': '02b_setup.sql', 'campaign': '02b_setup.sql · POST /campaigns',
}
OVERRIDE = {
 'same, as NOT': ['campaign'], 'one count per prefix': ['member', 'campaign'], "other saved cohorts": ['campaign'],
 'Chronic conditions': ['member'], 'POST /campaigns then': ['campaign', 'campaign_member'],
 "first CURRENT need's": ['v_care_plan', 'action'], 'count of review rows': ['v_care_plan'],
 'derived from the outcomes recorded': ['outcome', 'v_action_chain'], 'as screen 2': ['v_member_summary', 'v_rulebook_member', 'v_care_plan'],
 "slot IN ('NEXT'": ['care_plan_need', 'v_care_plan'],
}
member_cols = {c['c'] for c in tables['member']['cols']}
names = set(tables) | set(views)

elements = []
for i, r in enumerate(rows):
    s = r['source_table_column']
    words = re.findall(r'\b([A-Za-z_][A-Za-z_0-9]*)\b', s)
    refs = []
    for w in words:
        wl = w.lower()
        if wl in names and wl not in refs: refs.append(wl)
        elif (wl in member_cols or wl == 'extract') and 'member' not in refs: refs.append('member')
    kind = 'write' if re.search(r'POST|writes?|outcome\b', s) and 'v_' not in s else 'read'
    if re.match(r'^(none|no table|none in the kit)', s.strip(), re.I): refs = []
    for frag, extra in OVERRIDE.items():          # rows whose source text names no table but the kit does serve them
        if frag in r['element'] or frag in s: refs = extra
    elements.append({'id': i, 'screen': r['screen'], 'el': r['element'], 'shown': r['shown_as'], 'src': s, 'ref': r['rulebook_ref'], 'status': r['status'], 'tables': refs, 'dir': kind})

data = {'tables': [dict(t, kind=KIND[n], writer=WRITER.get(n, '')) for n, t in tables.items()],
        'views': [dict(v, kind='view') for v in views.values()],
        'kinds': KIND_INFO, 'elements': elements}
# which elements use each table (directly or through a view)
use = collections.defaultdict(set)
for e in elements:
    for t in e['tables']:
        use[t].add(e['id'])
        for ref in views.get(t, {}).get('refs', []): use[ref].add(e['id'])
data['use'] = {k: sorted(v) for k, v in use.items()}

PAGE = r'''<title>Screen to Table Lineage</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600&display=swap">
<style>
/* Layout: a screen picker, then two columns (elements left, tables right) with an SVG overlay for the joins; a slide-in panel defines a table. */
:root{--bg:#f6f7f9;--panel:#fff;--fg:#182028;--muted:#5d6974;--line:#d8dee6;--accent:#0f6e8c;--accent-soft:#e2f0f5;
 --k-source:#2e7d32;--k-rule:#6a3fb5;--k-config:#8a6d00;--k-derived:#0f6e8c;--k-input:#c2571f;--k-view:#546e7a;
 --font-body:"Inter",system-ui,sans-serif;--font-head:"Space Grotesk","Inter",system-ui,sans-serif;--font-mono:ui-monospace,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1418;--panel:#171e25;--fg:#e7ecf1;--muted:#9aa6b2;--line:#2b3540;--accent:#5fc0da;--accent-soft:#143442;
 --k-source:#7fcf84;--k-rule:#b79bea;--k-config:#e0c05a;--k-derived:#5fc0da;--k-input:#f0956a;--k-view:#9fb4bf;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0f1418;--panel:#171e25;--fg:#e7ecf1;--muted:#9aa6b2;--line:#2b3540;--accent:#5fc0da;--accent-soft:#143442;
 --k-source:#7fcf84;--k-rule:#b79bea;--k-config:#e0c05a;--k-derived:#5fc0da;--k-input:#f0956a;--k-view:#9fb4bf;color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--font-body);font-size:14px;line-height:1.5}
.wrap{max-width:1240px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:1.5rem 4rem}
h1{font-family:var(--font-head);font-size:clamp(24px,3.4vw,34px);margin:0 0 .4rem;text-wrap:balance}
.lede{color:var(--muted);max-width:72ch;margin:0 0 1rem}
.legend{display:flex;flex-wrap:wrap;gap:.5rem 1rem;font-size:13px;margin:.6rem 0 1.2rem}
.legend span::before{content:"";display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:.4rem;background:var(--c);vertical-align:-1px}
.tabs{display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:1rem}
.tabs button{font:inherit;font-weight:500;border:1px solid var(--line);background:var(--panel);color:var(--fg);border-radius:999px;padding:.4rem .9rem;cursor:pointer}
.tabs button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.tabs button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.board{position:relative;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:48px;align-items:start}
@media (max-width:820px){.board{grid-template-columns:1fr;gap:20px}.wires{display:none}}
.wires{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible}
.wires path{fill:none;stroke:var(--line);stroke-width:1.2;opacity:.55}
.wires path.on{stroke:var(--accent);stroke-width:2;opacity:1}
.wires path.dim{opacity:.12}
.col h2{font-family:var(--font-head);font-size:16px;margin:0 0 .6rem;color:var(--muted);font-weight:600}
.el{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:.5rem .7rem;margin-bottom:6px;cursor:pointer;display:grid;grid-template-columns:1fr auto;gap:.2rem .6rem;min-width:0}
.el:hover,.el.on{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-soft)}
.el .nm{font-weight:500}
.el .sh{grid-column:1/-1;color:var(--muted);font-size:12.5px}
.el .src{grid-column:1/-1;font-size:12px;color:var(--muted);font-family:var(--font-mono);word-break:break-word}
.el .st{font-size:11px;color:var(--muted);white-space:nowrap}
.el .st.warn{color:var(--k-input)}
.chips{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:4px}
.chip{font-family:var(--font-mono);font-size:11.5px;border:1px solid var(--c);color:var(--c);border-radius:4px;padding:0 .35rem;background:transparent;cursor:pointer}
.chip.w::after{content:" ✎"}
.grp{margin-bottom:14px}
.grp h3{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--c);margin:0 0 .4rem;font-weight:600}
.tb{display:flex;align-items:center;gap:.5rem;background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:6px;padding:.45rem .7rem;margin-bottom:5px;cursor:pointer;font-family:var(--font-mono);font-size:13px}
.tb:hover,.tb.on{border-color:var(--c);box-shadow:0 0 0 2px var(--accent-soft)}
.tb.dim{opacity:.35}
.tb small{font-family:var(--font-body);color:var(--muted);margin-left:auto;font-size:11.5px;white-space:nowrap}
.panel{position:fixed;top:env(safe-area-inset-top,0px);right:0;bottom:0;width:min(560px,100%);background:var(--panel);border-left:1px solid var(--line);box-shadow:-8px 0 24px rgba(0,0,0,.12);transform:translateX(102%);transition:transform .2s;overflow:auto;z-index:20;padding:1.2rem max(16px,env(safe-area-inset-right,0px)) 2rem 1.2rem}
.panel.open{transform:none}
@media (prefers-reduced-motion:reduce){.panel{transition:none}}
.panel h2{font-family:var(--font-mono);font-size:20px;margin:0 0 .3rem;word-break:break-all}
.badge{display:inline-block;font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:#fff;background:var(--c);border-radius:4px;padding:.15rem .5rem;margin-bottom:.6rem}
.panel p{margin:.4rem 0;font-size:13.5px}
.panel h4{font-family:var(--font-head);font-size:13px;margin:1rem 0 .3rem;color:var(--muted)}
.panel table{border-collapse:collapse;width:100%;font-size:12.5px}
.panel td{padding:.25rem .4rem;border-bottom:1px solid var(--line);vertical-align:top}
.panel td:first-child{font-family:var(--font-mono);white-space:nowrap}
.panel td:nth-child(2){font-family:var(--font-mono);color:var(--muted);white-space:nowrap}
.panel pre{font-family:var(--font-mono);font-size:11.5px;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:.6rem;overflow:auto;max-height:340px;line-height:1.45}
.close{position:absolute;top:.6rem;right:.8rem;font:inherit;border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:6px;padding:.2rem .6rem;cursor:pointer}
.ul{margin:.2rem 0;padding-left:1.1rem;font-size:13px}
.ul li{margin:.1rem 0}
.link{color:var(--accent);cursor:pointer;text-decoration:underline dotted}
.hint{font-size:12.5px;color:var(--muted);margin:.4rem 0 1rem}
</style>
<div class="wrap">
<h1>Every screen element, the tables behind it, and what kind of table that is</h1>
<p class="lede">Pick a screen. Hover or click an element on the left to light up the tables and views it reads or writes on the right. Click any table or view to see whether it is loaded, rule-based, hard-coded setup, derived by the run or nurse input, who writes it, and its exact columns. Views show their SQL and the tables they join.</p>
<div class="legend">
 <span style="--c:var(--k-source)">Loaded from the extract</span><span style="--c:var(--k-rule)">Rule table (rulebook rows)</span><span style="--c:var(--k-config)">Hard-coded setup</span><span style="--c:var(--k-derived)">Derived by the run</span><span style="--c:var(--k-input)">Nurse input</span><span style="--c:var(--k-view)">View (read-only)</span>
</div>
<div class="tabs" id="tabs" role="tablist"></div>
<p class="hint" id="hint"></p>
<div class="board" id="board">
  <svg class="wires" id="wires" aria-hidden="true"></svg>
  <div class="col"><h2 id="elh">Front-end elements</h2><div id="els"></div></div>
  <div class="col"><h2>Tables and views in the kit</h2><div id="tbs"></div></div>
</div>
</div>
<aside class="panel" id="panel" aria-label="Table definition"><button class="close" id="close">Close</button><div id="pbody"></div></aside>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const KC={source:'var(--k-source)',rule:'var(--k-rule)',config:'var(--k-config)',derived:'var(--k-derived)',input:'var(--k-input)',view:'var(--k-view)'};
const ORDER=['source','rule','config','derived','input','view'];
const T={};D.tables.forEach(t=>T[t.name]=t);D.views.forEach(v=>T[v.name]=v);
const screens=[...new Set(D.elements.map(e=>e.screen))];
let screen=screens[0],sel=null;
const $=id=>document.getElementById(id);
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function tabs(){$('tabs').innerHTML=screens.map(s=>`<button role="tab" aria-pressed="${s===screen}" data-s="${esc(s)}">${esc(s)}</button>`).join('');
 $('tabs').querySelectorAll('button').forEach(b=>b.onclick=()=>{screen=b.dataset.s;sel=null;render()})}
function render(){tabs();
 const els=D.elements.filter(e=>e.screen===screen);
 $('elh').textContent=`Front-end elements · ${els.length}`;
 $('hint').textContent=sel===null?'Hover an element to trace it. Click to pin. Click a table name anywhere to open its definition.':'';
 $('els').innerHTML=els.map(e=>`<div class="el${sel===e.id?' on':''}" data-id="${e.id}" tabindex="0">
  <div class="nm">${esc(e.el)}</div><div class="st${/Ready/.test(e.status)?'':' warn'}">${esc(e.status)}</div>
  <div class="sh">${esc(e.shown)}${e.ref?' · rulebook '+esc(e.ref):''}</div>
  <div class="src">${esc(e.src)}</div>
  <div class="chips">${e.tables.length?e.tables.map(t=>`<span class="chip${e.dir==='write'?' w':''}" style="--c:${KC[T[t].kind]}" data-t="${t}">${t}</span>`).join(''):'<span class="st">front-end only / not in the kit</span>'}</div></div>`).join('');
 const used=new Set();els.forEach(e=>e.tables.forEach(t=>{used.add(t);(T[t].refs||[]).forEach(r=>used.add(r))}));
 $('tbs').innerHTML=ORDER.map(k=>{const L=[...D.tables,...D.views].filter(t=>t.kind===k);if(!L.length)return '';
  return `<div class="grp" style="--c:${KC[k]}"><h3>${esc(D.kinds[k][0])}</h3>${L.map(t=>`<div class="tb${used.has(t.name)?'':' dim'}" data-t="${t.name}" tabindex="0" style="--c:${KC[k]}">${t.name}<small>${t.cols?t.cols.length+' cols':(t.refs||[]).length+' joins'}</small></div>`).join('')}</div>`}).join('');
 $('els').querySelectorAll('.el').forEach(x=>{x.onmouseenter=()=>wire(+x.dataset.id,false);x.onmouseleave=()=>wire(sel,false);
  x.onclick=ev=>{if(ev.target.classList.contains('chip'))return;sel=sel===+x.dataset.id?null:+x.dataset.id;render()};x.onkeydown=ev=>{if(ev.key==='Enter')x.click()}});
 document.querySelectorAll('[data-t]').forEach(x=>{x.onclick=()=>openT(x.dataset.t);x.onkeydown=ev=>{if(ev.key==='Enter')openT(x.dataset.t)}});
 requestAnimationFrame(()=>wire(sel,true))}
function wire(focus,all){const svg=$('wires'),B=$('board').getBoundingClientRect();svg.setAttribute('viewBox',`0 0 ${B.width} ${B.height}`);svg.setAttribute('width',B.width);svg.setAttribute('height',B.height);
 const els=D.elements.filter(e=>e.screen===screen);let paths='';
 const pos=(sel2)=>{const n=document.querySelector(sel2);if(!n)return null;const r=n.getBoundingClientRect();return {x1:r.left-B.left,x2:r.right-B.left,y:r.top-B.top+r.height/2}};
 els.forEach(e=>{const a=pos(`.el[data-id="${e.id}"]`);if(!a)return;const on=focus===e.id;
  const targets=new Set(e.tables);e.tables.forEach(t=>(T[t].refs||[]).forEach(r=>targets.add(r)));
  targets.forEach(t=>{const b=pos(`.tb[data-t="${t}"]`);if(!b)return;const via=!e.tables.includes(t);
   const cls=on?'on':(focus===null||focus===undefined?'':'dim');
   paths+=`<path class="${cls}" ${via&&on?'stroke-dasharray="4 3"':''} d="M${a.x2} ${a.y} C ${a.x2+60} ${a.y}, ${b.x1-60} ${b.y}, ${b.x1} ${b.y}"/>`})});
 svg.innerHTML=paths;
 document.querySelectorAll('.tb').forEach(x=>{x.classList.toggle('on',focus!==null&&focus!==undefined&&(()=>{const e=D.elements[focus];const s=new Set(e.tables);e.tables.forEach(t=>(T[t].refs||[]).forEach(r=>s.add(r)));return s.has(x.dataset.t)})())})}
function openT(name){const t=T[name];if(!t)return;const k=D.kinds[t.kind];const users=(D.use[name]||[]).map(i=>D.elements[i]);
 let h=`<span class="badge" style="--c:${KC[t.kind]}">${esc(k[0])}</span><h2>${esc(name)}</h2>`;
 if(t.comment)h+=`<p><b>${esc(t.comment)}</b></p>`;
 h+=`<p>${esc(k[1])}</p>`;
 if(t.writer)h+=`<h4>Written by</h4><p>${esc(t.writer)}</p>`;
 if(t.kind==='rule')h+=`<h4>Source file</h4><p>rules/${esc(name)}.csv → sql/02_rules.sql</p>`;
 if(t.refs){h+=`<h4>Joins</h4><p>${t.refs.map(r=>`<span class="link" data-t="${r}" style="color:${KC[T[r].kind]}">${r}</span>`).join(' · ')}</p><h4>Definition (SQL)</h4><pre>${esc(t.sql)}</pre>`}
 if(t.cols){h+=`<h4>Columns · ${t.cols.length}${t.store?' · '+esc(t.store):''}</h4>`;
  const show=t.cols.length>60?t.cols.slice(0,60):t.cols;
  h+=`<table>${show.map(c=>`<tr><td>${esc(c.c)}</td><td>${esc(c.t)}</td><td>${esc(c.d)}</td></tr>`).join('')}</table>`;
  if(t.cols.length>60)h+=`<p class="hint">${t.cols.length-60} more extract columns; the full list is rules/rule_field.csv (is_loaded = 1).</p>`;
  if(t.keys&&t.keys.length)h+=`<p class="hint">${esc(t.keys.join(' · '))}</p>`}
 h+=`<h4>Used by ${users.length} screen element${users.length===1?'':'s'}</h4><ul class="ul">${users.slice(0,40).map(e=>`<li>${esc(e.el)} <span style="color:var(--muted)">· ${esc(e.screen.split(':')[0])}</span></li>`).join('')}${users.length>40?`<li>… and ${users.length-40} more</li>`:''}</ul>`;
 $('pbody').innerHTML=h;$('panel').classList.add('open');
 $('pbody').querySelectorAll('[data-t]').forEach(x=>x.onclick=()=>openT(x.dataset.t))}
$('close').onclick=()=>$('panel').classList.remove('open');
document.addEventListener('keydown',e=>{if(e.key==='Escape')$('panel').classList.remove('open')});
window.addEventListener('resize',()=>wire(sel,true));
render();
</script>
'''
out = PAGE.replace('__DATA__', json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))
(HERE / 'LINEAGE.html').write_text(out)
print('tables', len(tables), 'views', len(views), 'elements', len(elements), 'no-table elements', sum(1 for e in elements if not e['tables']), 'size KB', len(out) // 1024)
for e in elements:
    if not e['tables']: print('  -', e['el'][:50], '|', e['src'][:60])
