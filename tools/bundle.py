#!/usr/bin/env python3
"""Unpack / rebuild self-contained bundled HTML pages.

  python3 tools/bundle.py unpack <bundle.html> <src-dir> [name=uuid ...]
  python3 tools/bundle.py build  <src-dir> <out.html>

A bundle is a loader page that carries three JSON islands: a manifest of
assets (uuid -> base64, optionally gzipped), a template (the page HTML that
references assets by uuid) and an optional page_order (uuids of nested pages
mounted in iframes). `unpack` writes every asset as a readable file plus
bundle.json; `build` reverses it. A nested page can be produced by another
build: give its asset {"build": "<other-src-dir>"}.
"""
import base64, gzip, json, os, re, sys

ISLANDS = ('manifest', 'template', 'ext_resources', 'page_order')
EXT = {'text/html': '.html', 'application/javascript': '.js', 'text/javascript': '.js', 'text/css': '.css', 'font/woff2': '.woff2'}


def island(text, name):
    m = re.search(r'(<script type="__bundler/' + name + r'">)(.*?)(</script>)', text, re.S)
    return m


def unpack(src, out, names):
    t = open(src, encoding='utf-8').read()
    os.makedirs(out, exist_ok=True)
    man = json.loads(island(t, 'manifest').group(2))
    tpl = json.loads(island(t, 'template').group(2))
    ext = json.loads(island(t, 'ext_resources').group(2)) if island(t, 'ext_resources') else []
    po = json.loads(island(t, 'page_order').group(2)) if island(t, 'page_order') else []
    shell = t
    for n in ISLANDS:
        m = island(shell, n)
        if m:
            shell = shell[:m.start(2)] + '@@' + n.upper() + '@@' + shell[m.end(2):]
    open(os.path.join(out, 'shell.html'), 'w', encoding='utf-8').write(shell)
    rev = {v: k for k, v in names.items()}
    assets = {}
    for uid, e in man.items():
        raw = base64.b64decode(e['data'])
        if e.get('compressed'):
            raw = gzip.decompress(raw)
        mime = e['mime']
        if uid in rev:
            fn = rev[uid]
        elif mime.startswith('font/'):
            fn = 'assets/fonts/' + uid + EXT.get(mime, '.bin')
        else:
            fn = 'assets/' + uid + EXT.get(mime.split(';')[0], '.bin')
        p = os.path.join(out, fn)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(raw)
        assets[uid] = {'file': fn, 'mime': mime, 'compressed': bool(e.get('compressed'))}
    open(os.path.join(out, 'index.template.html'), 'w', encoding='utf-8').write(tpl)
    json.dump({'template': 'index.template.html', 'ext_resources': ext, 'page_order': po, 'assets': assets},
              open(os.path.join(out, 'bundle.json'), 'w'), indent=1)


def build(srcdir, out=None):
    cfg = json.load(open(os.path.join(srcdir, 'bundle.json')))
    shell = open(os.path.join(srcdir, 'shell.html'), encoding='utf-8').read()
    man = {}
    for uid, a in cfg['assets'].items():
        if 'build' in a:
            raw = build(os.path.normpath(os.path.join(srcdir, a['build']))).encode('utf-8')
        else:
            raw = open(os.path.join(srcdir, a['file']), 'rb').read()
        comp = a.get('compressed', False)
        data = gzip.compress(raw, 9, mtime=0) if comp else raw
        man[uid] = {'mime': a['mime'], 'compressed': comp, 'data': base64.b64encode(data).decode()}
    tpl = open(os.path.join(srcdir, cfg['template']), encoding='utf-8').read()
    enc = lambda o: json.dumps(o, ensure_ascii=False).replace('</', '<\\u002F')
    vals = {'MANIFEST': json.dumps(man), 'TEMPLATE': enc(tpl), 'EXT_RESOURCES': enc(cfg.get('ext_resources', [])), 'PAGE_ORDER': enc(cfg.get('page_order', []))}
    html = shell
    for k, v in vals.items():
        html = html.replace('@@' + k + '@@', v, 1)
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        open(out, 'w', encoding='utf-8').write(html)
        print('built', out, len(html) // 1024, 'KB')
    return html


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'unpack':
        unpack(sys.argv[2], sys.argv[3], dict(a.split('=', 1) for a in sys.argv[4:]))
    elif cmd == 'build':
        build(sys.argv[2], sys.argv[3])
