#!/usr/bin/env python3
"""Build every artefact into dist/ as single self-contained HTML files."""
import os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from bundle import build  # noqa: E402

OUT = os.path.join(ROOT, 'dist')
os.makedirs(OUT, exist_ok=True)
build(os.path.join(ROOT, 'src/briefing'), os.path.join(OUT, 'Chronic-Care-Loop-Briefing.html'))
build(os.path.join(ROOT, 'src/studio'), os.path.join(OUT, 'Chronic-Care-Studio.html'))   # embeds the portal as screen 3
build(os.path.join(ROOT, 'src/portal'), os.path.join(OUT, 'Care-Coordinator-Portal.html'))
build(os.path.join(ROOT, 'src/builder'), os.path.join(OUT, 'Cohort-Campaign-Builder.html'))
shutil.copy(os.path.join(ROOT, 'src/hub/index.html'), os.path.join(OUT, 'index.html'))
print('copied', os.path.join(OUT, 'index.html'))
# database.html is authored as an artifact body (no <html>/<head>); wrap it for standalone use
body = open(os.path.join(ROOT, 'src/hub/database.html'), encoding='utf-8').read()
head = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
        'body{margin:0}[hidden]{display:none!important}</style>\n')
open(os.path.join(OUT, 'database.html'), 'w', encoding='utf-8').write(head + body + '\n</html>\n')
print('wrapped', os.path.join(OUT, 'database.html'))
