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
shutil.copy(os.path.join(ROOT, 'src/hub/index.html'), os.path.join(OUT, 'index.html'))
print('copied', os.path.join(OUT, 'index.html'))
