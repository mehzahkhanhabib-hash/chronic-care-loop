#!/usr/bin/env python3
"""Make a raw extract loadable: the kit expects the 341-column layout with mask_id first.
A snapshot exported without mask_id (header starts GENDER, AGE, …) gets a pseudonymous id (s1, s2, …) and the
empty rank_PURECS_per_payable column prepended. Columns are matched by name against data/raw/glossary.tsv.

    python3 tools/add_ids.py snapshot_250.tsv data/member_features.tsv
"""
import csv, os, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
gl = [r['column'] for r in csv.DictReader(open(os.path.join(REPO, 'data/raw/glossary.tsv'), encoding='utf-8'), delimiter='\t')]
src, dst = sys.argv[1], sys.argv[2]
rows = list(csv.reader(open(src, encoding='utf-8', newline=''), delimiter='\t'))
hdr = rows[0]
if hdr and hdr[0] == 'mask_id':
    print('already has mask_id; copying'); out = rows
else:
    pos = {c: i for i, c in enumerate(hdr)}
    missing = [c for c in gl if c not in pos and c not in ('mask_id', 'rank_PURECS_per_payable')]
    if missing:
        sys.exit(f'columns missing from the snapshot: {missing[:10]} …')
    out = [gl]
    for n, r in enumerate(rows[1:], 1):
        if not any(r):
            continue
        out.append([f's{n}', ''] + [r[pos[c]] if pos[c] < len(r) else '' for c in gl[2:]])
with open(dst, 'w', encoding='utf-8', newline='') as f:
    csv.writer(f, delimiter='\t', lineterminator='\n').writerows(out)
print(f'wrote {dst}: {len(out) - 1} members, {len(out[0])} columns')
