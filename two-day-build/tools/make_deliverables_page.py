#!/usr/bin/env python3
"""Markdown → page (one reading column, contents rail, copyable Teams post, screenshots). Run from two-day-build/.
    python3 tools/make_deliverables_page.py                       # DELIVERABLES.md → DELIVERABLES.html
    python3 tools/make_deliverables_page.py DEVELOPER_GUIDE.md DEVELOPER_GUIDE.html "Developer Guide" "eyebrow" "Heading" "Intro sentence"
"""
import re, html, sys
A = sys.argv[1:]
SRC, OUT = (A[0], A[1]) if len(A) >= 2 else ('DELIVERABLES.md', 'DELIVERABLES.html')
TITLE = A[2] if len(A) > 2 else 'GCEO Demo Build Plan'
EYEBROW = A[3] if len(A) > 3 else 'Chronic Care Loop · SingleStore · 2 days · 3 developers · GCEO demo'
HEAD = A[4] if len(A) > 4 else 'The GCEO demo: member 360, rules, care portal, nurse action, worklist'
INTRO = A[5] if len(A) > 5 else 'One live story on real data, the three layers that carry it, the two-day plan, the Teams post to send tonight, and the kickoff script for tomorrow morning. Everything referenced is in the kit folder <code>two-day-build/</code>.'
md = open(SRC, encoding='utf-8').read()
def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', t)
    return t
out = []; lines = md.split('\n'); i = 0; sec = 0; toc = []; buf = []
def flush_p():
    global buf
    if buf: out.append('<p>' + inline(' '.join(buf)) + '</p>')
    buf = []
while i < len(lines):
    l = lines[i]
    if l.startswith('```'):
        flush_p(); j = i + 1; code = []
        while not lines[j].startswith('```'): code.append(lines[j]); j += 1
        out.append('<pre>' + html.escape('\n'.join(code)) + '</pre>'); i = j + 1; continue
    if l.startswith('|') and i + 1 < len(lines) and re.match(r'^\|[-| ]+\|$', lines[i + 1]):
        flush_p(); hdr = [c.strip() for c in l.strip('|').split('|')]; j = i + 2; rows = []
        while j < len(lines) and lines[j].startswith('|'):
            rows.append([c.strip() for c in lines[j].strip('|').split('|')]); j += 1
        wide = len(hdr) >= 4
        t = '<div class="tw"><table class="%s"><thead><tr>%s</tr></thead><tbody>' % ('grid' if wide else '', ''.join(f'<th>{inline(h)}</th>' for h in hdr))
        for r in rows:
            cells = ''.join((f'<th scope="row">{inline(c)}</th>' if k == 0 and wide and hdr[0] == '' else f'<td>{inline(c)}</td>') for k, c in enumerate(r))
            t += f'<tr>{cells}</tr>'
        out.append(t + '</tbody></table></div>'); i = j; continue
    if l.startswith('>'):
        flush_p(); j = i; q = []
        while j < len(lines) and lines[j].startswith('>'): q.append(lines[j][2:] if lines[j].startswith('> ') else ''); j += 1
        body = []; p = []
        for ql in q:
            if ql.strip() == '':
                if p: body.append('<p>' + inline(' '.join(p)) + '</p>'); p = []
            elif re.match(r'^\d+\. ', ql) or ql.startswith('- '):
                if p: body.append('<p>' + inline(' '.join(p)) + '</p>'); p = []
                body.append('<p class="li">' + inline(ql) + '</p>')
            else: p.append(ql)
        if p: body.append('<p>' + inline(' '.join(p)) + '</p>')
        out.append('<div class="post"><div class="postbar"><span>Teams · ready to paste</span><button type="button" id="copy-post">Copy post</button></div><blockquote id="post-text">'
                   + ''.join(body) + '</blockquote><textarea id="post-raw" hidden>' + html.escape('\n'.join(q)) + '</textarea></div>')
        i = j; continue
    im = re.match(r'^!\[(.*?)\]\((.*?)\)\s*$', l)
    if im:
        flush_p(); out.append(f'<figure><img src="{html.escape(im.group(2))}" alt="{html.escape(im.group(1))}" loading="lazy"><figcaption>{inline(im.group(1))}</figcaption></figure>'); i += 1; continue
    m = re.match(r'^(#{1,3}) (.*)', l)
    if m:
        flush_p(); lv = len(m.group(1)); txt = m.group(2)
        if lv == 1: out.append(f'<h1 hidden>{inline(txt)}</h1>')
        elif lv == 2:
            sec += 1; sid = f's{sec}'; toc.append((sid, txt))
            out.append(('' if sec == 1 else '</section>') + f'<section id="{sid}"><h2>{inline(txt)}</h2>')
        else: out.append(f'<h3>{inline(txt)}</h3>')
        i += 1; continue
    if re.match(r'^(\d+\. |- )', l):
        flush_p(); j = i; items = []; ol = l[0].isdigit()
        while j < len(lines) and re.match(r'^(\d+\. |- )', lines[j]): items.append(re.sub(r'^(\d+\. |- )', '', lines[j])); j += 1
        out.append(('<ol>' if ol else '<ul>') + ''.join(f'<li>{inline(x)}</li>' for x in items) + ('</ol>' if ol else '</ul>')); i = j; continue
    if l.strip() in ('', '---'):
        flush_p(); i += 1; continue
    buf.append(l); i += 1
flush_p(); out.append('</section>')
nav = ''.join(f'<a href="#{s}">{html.escape(t)}</a>' for s, t in toc)
page = '<title>' + html.escape(TITLE) + '''</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
/* Layout: one reading column with a sticky contents rail; the demo-story and three-layer tables are the centrepiece, the Teams post is a copyable block. */
:root{--bg:#F5F7FA;--surface:#FFFFFF;--ink:#1D2939;--mut:#5D6B80;--line:#E1E7EF;--sunk:#EEF2F7;--acc:#3F6C9F;--accS:#EAF1F9;--band:#13223A;--bandInk:#E6EDF6;
 --sans:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif;--mono:'IBM Plex Mono',ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0F1620;--surface:#161F2B;--ink:#E6EBF2;--mut:#9AA7B8;--line:#273243;--sunk:#1C2634;--acc:#7FA6D4;--accS:#1B2A3D;--band:#0A111B;--bandInk:#E6EDF6;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0F1620;--surface:#161F2B;--ink:#E6EBF2;--mut:#9AA7B8;--line:#273243;--sunk:#1C2634;--acc:#7FA6D4;--accS:#1B2A3D;--band:#0A111B;--bandInk:#E6EDF6;color-scheme:dark}
body{background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans);margin:0}
.band{background:var(--band);color:var(--bandInk)}
.band .in{max-width:1180px;margin:0 auto;padding-block:30px 26px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.band code{background:rgba(255,255,255,.14);color:inherit}
.band small{display:block;font:600 11px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;opacity:.75;margin-bottom:10px}
h1{font:700 28px/1.2 var(--sans);margin:0;text-wrap:balance;letter-spacing:-.01em}
.band p{margin:10px 0 0;max-width:70ch;opacity:.9}
.wrap{max-width:1180px;margin:0 auto;padding-block:20px 60px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:grid;grid-template-columns:200px minmax(0,1fr);gap:28px}
nav{position:sticky;top:16px;align-self:start;display:flex;flex-direction:column;gap:4px;font-size:13px}
nav a{color:var(--mut);text-decoration:none;padding:6px 10px;border-left:2px solid var(--line)}nav a:hover{color:var(--acc);border-color:var(--acc)}
main{min-width:0}
section{padding:10px 0 26px;border-bottom:1px solid var(--line)}section:last-child{border:0}
h2{font:600 21px/1.25 var(--sans);margin:12px 0 10px;text-wrap:balance}
h3{font:600 15px/1.3 var(--sans);margin:22px 0 8px}
p{margin:8px 0;max-width:78ch}
code{font:500 12.5px var(--mono);background:var(--sunk);padding:1px 5px;border-radius:4px}
pre{font:12.5px/1.45 var(--mono);background:var(--band);color:var(--bandInk);padding:14px 16px;border-radius:8px;overflow-x:auto;margin:10px 0}
.tw{overflow-x:auto;margin:10px 0}
table{border-collapse:collapse;width:100%;font-size:13px;background:var(--surface);border:1px solid var(--line);border-radius:8px}
th,td{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--line)}
thead th{font:600 11px/1.2 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--mut);background:var(--sunk)}
tbody tr:last-child td,tbody tr:last-child th{border-bottom:0}
table.grid th[scope=row]{font-weight:600;white-space:nowrap;background:var(--sunk);width:1%}
table.grid td{min-width:200px}
ul,ol{margin:6px 0 6px 22px;padding:0}li{margin:4px 0}
.post{background:var(--surface);border:1px solid var(--line);border-radius:10px;margin:12px 0}
.postbar{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 14px;border-bottom:1px solid var(--line);font:600 11px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--mut)}
.postbar button{font:600 12px var(--sans);color:var(--acc);background:var(--accS);border:0;border-radius:6px;padding:6px 10px;cursor:pointer}.postbar button:focus-visible{outline:2px solid var(--acc)}
figure{margin:14px 0;background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden}figure img{display:block;width:100%;height:auto}figcaption{font-size:12.5px;color:var(--mut);padding:8px 12px;border-top:1px solid var(--line)}
blockquote{margin:0;padding:12px 18px 14px}blockquote p{margin:7px 0}blockquote .li{margin:3px 0 3px 14px}
@media (max-width:820px){.wrap{grid-template-columns:1fr}nav{position:static;flex-direction:row;flex-wrap:wrap}nav a{border-left:0;border-bottom:2px solid var(--line)}}
</style>
<div class="band"><div class="in"><small>''' + html.escape(EYEBROW) + '''</small>
<h1>''' + html.escape(HEAD) + '''</h1>
<p>''' + INTRO + '''</p></div></div>
<div class="wrap"><nav aria-label="Contents">''' + nav + '''</nav><main>
''' + '\n'.join(out) + '''
</main></div>
<script>
(function(){var b=document.getElementById('copy-post'),t=document.getElementById('post-raw');if(!b||!t)return;
b.addEventListener('click',function(){var txt=t.value;function done(ok){b.textContent=ok?'Copied':'Select and copy';setTimeout(function(){b.textContent='Copy post'},1800)}
function sel(){var r=document.createRange();r.selectNodeContents(document.getElementById('post-text'));var s=getSelection();s.removeAllRanges();s.addRange(r);done(false)}
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(txt).then(function(){done(true)},sel)}else sel();});})();
</script>'''
open(OUT, 'w', encoding='utf-8').write(page)
print('ok', len(page) // 1024, 'KB', len(toc), 'sections')
