#!/usr/bin/env python3
"""Build the delivery folder (and a zip) from the repo:

  release/Chronic-Care-Loop/
    START-HERE.md
    index.html                         overview page linking the four products
    1-care-portal/                     Care coordinator portal
    2-cohort-campaign-builder/         Cohort & campaign builder
    3-care-studio/                     Care studio: builder → care intelligence → portal
    4-data-model/                      data model page, schemas, rule database
    server/                            the backend (Python 3.10+, standard library only)
    docs/                              developer handoff, hosting, demo script
    run.sh, run.bat, Dockerfile

  python3 tools/build_all.py && python3 tools/package.py
"""
import os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, 'dist')
OUT = os.path.join(ROOT, 'release', 'Chronic-Care-Loop')

PLACE = {   # built page → folder in the delivery
    'Care-Coordinator-Portal.html': '1-care-portal',
    'Cohort-Campaign-Builder.html': '2-cohort-campaign-builder',
    'Chronic-Care-Studio.html': '3-care-studio',
    'database.html': '4-data-model',
    'Chronic-Care-Loop-Briefing.html': 'docs',
    'index.html': '',
}


def relink(html, here):
    """Point each link to a sibling product at its new folder."""
    for name, folder in PLACE.items():
        target = (folder + '/' if folder else '') + name
        rel = os.path.relpath(target, here or '.').replace(os.sep, '/')
        if rel == name:
            continue
        html = re.sub(r'(["\'])' + re.escape(name), lambda m: m.group(1) + rel, html)
    return html


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for name, folder in PLACE.items():
        d = os.path.join(OUT, folder)
        os.makedirs(d, exist_ok=True)
        html = open(os.path.join(DIST, name), encoding='utf-8').read()
        open(os.path.join(d, name), 'w', encoding='utf-8').write(relink(html, folder))
    # 4 · data model and rules
    dm = os.path.join(OUT, '4-data-model')
    shutil.copy(os.path.join(ROOT, 'docs', 'schema.sql'), os.path.join(dm, 'schema.postgres.sql'))
    shutil.copy(os.path.join(ROOT, 'backend', 'schema.sql'), os.path.join(dm, 'schema.sqlite.sql'))
    for f in ('DATA_MODEL.md', 'DATA_FINDINGS.md'):
        shutil.copy(os.path.join(ROOT, 'docs', f), dm)
    shutil.copytree(os.path.join(ROOT, 'rules'), os.path.join(dm, 'rules'))
    # server
    srv = os.path.join(OUT, 'server')
    shutil.copytree(os.path.join(ROOT, 'backend'), os.path.join(srv, 'backend'), ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(os.path.join(ROOT, 'tests'), os.path.join(srv, 'tests'), ignore=shutil.ignore_patterns('__pycache__'))
    os.makedirs(os.path.join(srv, 'data'))
    shutil.copytree(os.path.join(ROOT, 'data', 'raw'), os.path.join(srv, 'data', 'raw'))
    # docs and launchers
    for f in ('HANDOFF.md', 'HOSTING.md', 'DEMO.md'):
        shutil.copy(os.path.join(ROOT, 'docs', f), os.path.join(OUT, 'docs'))
    for f in ('START-HERE.md', 'run.sh', 'run.bat', 'Dockerfile', '.dockerignore'):
        shutil.copy(os.path.join(ROOT, 'release_files', f), OUT)
    os.chmod(os.path.join(OUT, 'run.sh'), 0o755)
    # zip
    z = os.path.join(ROOT, 'release', 'Chronic-Care-Loop.zip')
    if os.path.exists(z):
        os.remove(z)
    subprocess.run(['zip', '-qr', z, 'Chronic-Care-Loop'], cwd=os.path.join(ROOT, 'release'), check=True)
    print('folder', OUT)
    print('zip   ', z, f'{os.path.getsize(z) // 1024} KB')


if __name__ == '__main__':
    sys.exit(main())
