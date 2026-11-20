#!/usr/bin/env python3
"""Regenerate the data-model page (src/hub/database.html, #model-data) from the real backend.

Runs one scripted demo day against a throw-away SQLite database — load the extract, nightly run, a cohort
saved in the builder, a nurse call — then reads the schema (PRAGMA) and sample rows back out. The page
therefore always shows the tables, keys and values the code actually writes.

  python3 tools/gen_model.py && node tools/gen_schema.js
"""
import json, os, re, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['CCL_DB'] = os.path.join(tempfile.mkdtemp(), 'model.db')
os.environ['CCL_QUIET'] = '1'
from backend import store, ingest, engine, cohorts, views  # noqa: E402

PAGE = os.path.join(ROOT, 'src', 'hub', 'database.html')
STORY = ['m133', 'm26', 'm44']   # top of the worklist · a second member in the same campaign · the member with 999 placeholders

DOMAINS = {
    'ing': {'label': 'Ingest & reference', 'sub': 'The raw extract, its glossary, quality checks and the rulebook', 'color': '--d-ing'},
    'pop': {'label': 'Population', 'sub': 'Members and the typed values of every extract column', 'color': '--d-pop'},
    'tgt': {'label': 'Targeting', 'sub': 'Cohorts from the builder and the campaigns that use them', 'color': '--d-tgt'},
    'int': {'label': 'Care intelligence', 'sub': 'Nightly scores, triggers and care plans', 'color': '--d-int'},
    'ops': {'label': 'Care operations', 'sub': 'The team, actions, calls, outcomes and the audit log', 'color': '--d-ops'},
}
TABLES = [
    ('ingest_run', 'ing', 'One row per load of the member-level extract (167 rows × 341 columns in production; 24-row sample here).'),
    ('src_member_row', 'ing', 'Each extract row exactly as received, as JSON, so nothing is lost when values are typed.'),
    ('data_issue', 'ing', 'What the loader found: 999 placeholders, impossible readings, score and tier mismatches.'),
    ('trigger_def', 'ing', 'Rulebook §3: each trigger, the raw columns it reads, the next best action, owner and proof of completion.'),
    ('member', 'pop', 'One row per masked member (mask_id). Consent is the only column the loop writes.'),
    ('feature', 'pop', 'The catalogue: one row per glossary column plus derived fields. Risk, triggers and persona are not selectable.'),
    ('member_feature', 'pop', 'Every extract value in typed long form. Dates hold days before the as-of date, so rules stay simple.'),
    ('cohort', 'tgt', 'A saved builder definition, versioned. row_count is refreshed each run.'),
    ('cohort_rule', 'tgt', 'The builder rules as rows: field, operator, values, include or exclude.'),
    ('cohort_member', 'tgt', 'Who matched on the last run, with the stable-hash 10% holdout flag.'),
    ('campaign', 'tgt', 'Goal, trigger mode, channels, capacity, start and status.'),
    ('campaign_cohort', 'tgt', 'Which cohorts a campaign includes or excludes.'),
    ('assessment', 'int', 'Rulebook §2 per member per run: C+M+K+U+A, tier, alert colour, contact priority P1–P4.'),
    ('signal', 'int', 'A trigger that fired (or could not be judged) for a campaign member on this run.'),
    ('care_plan', 'int', 'One plan per member: pathway, tier and the cadence that follows from it.'),
    ('care_plan_need', 'int', 'One need per trigger, ordered safety → goal. Top 3 are CURRENT, 4–6 NEXT, the rest FUTURE.'),
    ('care_team_user', 'ops', 'Nurses, coordinators and clinical leads, with languages and daily capacity.'),
    ('action', 'ops', 'Work for the team: one care-plan action per CURRENT need, plus worklist calls and retries.'),
    ('contact', 'ops', 'A call attempt: who, when, reached or not, consent and response.'),
    ('outcome', 'ops', 'What happened to a need or action. The nightly run reads and stamps it.'),
    ('event_log', 'ops', 'Every read and write the API makes: the data lens behind both screens.'),
]
FEATURES = ['cohort_t2d_l12m', 'cohort_htn_l12m', 'Last_HbA1c_Value', 'last_hba1c_date2', 'Last_SystolicPressure_Value', 'pdc_any_t2d_noninsulin',
            'ip_admissions_l12m', 'Exclusion', 'Total_risk_Score', 'Trig3_hypoglycemia_tx', 'Trig1_HbA1c_above_target', 'Persona']


def demo_day(con):
    ingest.load(os.path.join(ROOT, 'data', 'raw', 'member_features_sample.tsv'), con=con)
    engine.run(con)
    engine.save_cohort(con, 'COH-0106', 'T2D · HbA1c 9 % or more', [{'f': 'dx', 'vs': ['E11']}, {'f': 'lab', 'l': 'hba1c', 'op': '≥', 'v': 9}], [{'f': 'optout'}])
    con.commit()
    engine.record(con, {'member_id': 'm133', 'kind': 'call', 'reached': True, 'consent': 'granted', 'response': 'Engaged', 'campaign_id': 'CMP-0101'})
    engine.record(con, {'member_id': 'm133', 'kind': 'need', 'need': 'Trig3', 'result': 'done'})
    engine.record(con, {'member_id': 'm26', 'kind': 'call', 'reached': False, 'campaign_id': 'CMP-0101'})
    engine.run(con)


def schema(con, name):
    fks = {r[3]: r[2] for r in con.execute(f'PRAGMA foreign_key_list("{name}")')}
    cols = []
    for cid, col, typ, notnull, dflt, pk in con.execute(f'PRAGMA table_info("{name}")'):
        flags = (['PK'] if pk else []) + ([f'FK:{fks[col]}'] if col in fks else []) + ([] if notnull or pk else ['NULL'])
        cols.append([col, {'TEXT': 'text', 'INTEGER': 'int', 'REAL': 'numeric'}.get(typ.upper(), typ.lower()), ','.join(flags)])
    return cols


def sample(con, name):
    S = "('" + "','".join(STORY) + "')"
    q = {
        'src_member_row': f'SELECT * FROM src_member_row WHERE member_id IN {S}',
        'data_issue': f"SELECT * FROM data_issue WHERE member_id IN {S} OR member_id IS NULL ORDER BY issue_id LIMIT 9",
        'member': f'SELECT * FROM member WHERE member_id IN {S}',
        'feature': 'SELECT * FROM feature WHERE feature_key IN (' + ','.join(f"'x:{f}'" for f in FEATURES) + ",'d:pdc_min_pct','d:chronic_count') ORDER BY feature_key",
        'member_feature': "SELECT * FROM member_feature WHERE member_id = 'm133' AND feature_key IN (" + ','.join(f"'x:{f}'" for f in FEATURES) + ",'d:pdc_min_pct','d:chronic_count') "
                          "UNION ALL SELECT * FROM member_feature WHERE member_id = 'm26' AND feature_key IN ('x:cohort_t2d_l12m','x:Last_HbA1c_Value','x:Total_risk_Score') ORDER BY 1, 2",
        'cohort_rule': 'SELECT r.* FROM cohort_rule r JOIN cohort c ON c.cohort_id = r.cohort_id AND c.version = r.version ORDER BY r.cohort_id, r.rule_id',
        'cohort_member': f'SELECT * FROM cohort_member WHERE member_id IN {S} ORDER BY cohort_id, member_id',
        'assessment': f'SELECT * FROM assessment WHERE member_id IN {S}',
        'signal': f'SELECT * FROM signal WHERE member_id IN {S} ORDER BY member_id, signal_id',
        'care_plan': f'SELECT * FROM care_plan WHERE member_id IN {S}',
        'care_plan_need': f'SELECT n.* FROM care_plan_need n JOIN care_plan p USING (care_plan_id) WHERE p.member_id IN {S} ORDER BY n.care_plan_id, n.slot, n.need_id',
        'action': f'SELECT * FROM action WHERE member_id IN {S} ORDER BY member_id, action_id',
        'event_log': 'SELECT * FROM (SELECT * FROM event_log ORDER BY event_id DESC LIMIT 12) ORDER BY event_id',
    }.get(name, f'SELECT * FROM "{name}"')
    rows = [list(r) for r in con.execute(q).fetchall()]
    if name == 'src_member_row':   # the full row is 341 columns: keep the first few for the page
        for r in rows:
            d = json.loads(r[2])
            r[2] = json.dumps({k: d[k] for k in list(d)[:6]})[:-1] + ', … 335 more}'
    for r in rows:
        for i, v in enumerate(r):
            if isinstance(v, float) and v.is_integer():
                r[i] = int(v)
            elif isinstance(v, float):
                r[i] = round(v, 3)
    return rows


def build():
    con = store.connect()
    store.create_schema(con)
    demo_day(con)
    tables = []
    for name, dom, purpose in TABLES:
        tables.append({'name': name, 'domain': dom, 'purpose': purpose, 'cols': schema(con, name), 'rows': sample(con, name)})
    T = {t['name']: t for t in tables}

    def idx(t, **match):
        cols = [c[0] for c in T[t]['cols']]
        out = [i for i, r in enumerate(T[t]['rows']) if all((r[cols.index(k)] in v if isinstance(v, (list, tuple, set)) else r[cols.index(k)] == v) for k, v in match.items())]
        return out

    allrows = lambda t: list(range(len(T[t]['rows'])))
    fv = {r[0]: r[1:] for r in con.execute("SELECT feature_key, value_num, value_text FROM member_feature WHERE member_id = 'm133'")}
    lit = lambda v: 'NULL' if v is None else (f"'{v}'" if isinstance(v, str) else (str(int(v)) if float(v).is_integer() else str(v)))
    a = store.one(con, "SELECT * FROM assessment WHERE member_id = 'm133'")
    load_sql = ("INSERT INTO member_feature (member_id, feature_key, value_num, value_text, as_of)\nVALUES ('m133', 'x:Last_HbA1c_Value', "
                + lit(fv['x:Last_HbA1c_Value'][0]) + ", NULL, '2026-10-31'),\n       ('m133', 'x:last_hba1c_date2', " + lit(fv['x:last_hba1c_date2'][0]) + ', '
                + lit(fv['x:last_hba1c_date2'][1]) + ", '2026-10-31');  -- dates: days before as-of")
    assess_sql = ("INSERT INTO assessment (member_id, run_id, clinical, comorbid, kidney, utilisation, age_sex,\n  kidney_provisional, r_total, tier, tier_label, persona, allocation, priority_review, excluded, alert, contact_priority)\nVALUES ("
                  + ', '.join(lit(a[k]) for k in ['member_id', 'run_id', 'clinical', 'comorbid', 'kidney', 'utilisation', 'age_sex', 'kidney_provisional', 'r_total', 'tier', 'tier_label', 'persona', 'allocation', 'priority_review', 'excluded', 'alert', 'contact_priority']) + ');')
    est = cohorts.estimate(con, cohorts.definition(con, 'COH-0106'))
    groups = [
        {'id': 'load', 'label': 'Extract load', 'who': 'Data team · python3 -m backend.ingest'},
        {'id': 'studio1', 'label': 'Studio · Cohort & campaign builder', 'who': 'Layla M. · population health'},
        {'id': 'nightly', 'label': 'Nightly run', 'who': 'POST /api/runs/nightly · backend/engine.py'},
        {'id': 'studio2', 'label': 'Studio · Care intelligence', 'who': 'Dr. Rana K. · clinical lead'},
        {'id': 'portal', 'label': 'Care portal', 'who': 'Nadia R. · nurse'},
    ]
    steps = [
        {'id': 'load', 'group': 'load', 'title': 'Load the extract and glossary',
         'what': 'The 341-column file is kept as received (src_member_row), typed into member_feature, and every glossary column becomes a catalogue feature. Members are upserted, so consent recorded by the loop survives a reload.',
         'ops': [{'t': 'ingest_run', 'w': ['run_id', 'source_file', 'as_of_date', 'row_count', 'column_count'], 'rows': allrows('ingest_run')},
                 {'t': 'src_member_row', 'w': ['run_id', 'member_id', 'raw_json'], 'rows': allrows('src_member_row')},
                 {'t': 'feature', 'w': ['feature_key', 'label', 'category', 'value_type', 'cohort_selectable'], 'rows': allrows('feature')},
                 {'t': 'member', 'w': ['member_id', 'gender', 'age', 'nationality', 'plan_name'], 'rows': allrows('member')},
                 {'t': 'member_feature', 'w': ['member_id', 'feature_key', 'value_num', 'value_text', 'as_of'], 'rows': allrows('member_feature')}],
         'sql': load_sql},
        {'id': 'dq', 'group': 'load', 'title': 'Check data quality',
         'what': 'Placeholders such as 999 and impossible readings such as BP 1/1 are set to empty and logged, so they never reach a rule. File-level findings (empty columns, reversed tier numbering, spreadsheet-formatted money) are logged once.',
         'ops': [{'t': 'data_issue', 'w': ['member_id', 'column_name', 'raw_value', 'rule', 'severity'], 'rows': allrows('data_issue')}],
         'sql': "SELECT member_id, column_name, raw_value, rule\nFROM data_issue\nWHERE severity = 'error';   -- GET /api/data-quality"},
        {'id': 'search', 'group': 'studio1', 'title': 'Search the catalogue',
         'what': 'Typing in the builder searches feature labels and glossary descriptions, with a live member count. Risk score, Trigger and Persona columns are never offered (rulebook §2).',
         'ops': [{'t': 'feature', 'r': ['feature_key', 'label', 'category', 'description', 'cohort_selectable'], 'rows': idx('feature', cohort_selectable=1)},
                 {'t': 'member_feature', 'r': ['feature_key', 'value_num'], 'rows': idx('member_feature', member_id='m133')}],
         'sql': "SELECT f.feature_key, f.label,\n       (SELECT count(*) FROM member_feature mf WHERE mf.feature_key = f.feature_key) AS members\nFROM feature f\nWHERE f.cohort_selectable = 1 AND f.description LIKE '%hba1c%';   -- GET /api/features?q=hba1c"},
        {'id': 'estimate', 'group': 'studio1', 'title': 'Live count while building',
         'what': f"Each builder rule compiles to an EXISTS over member_feature. The funnel shows each step: {est['B']} → " + ' → '.join(str(s['n']) for s in est['steps']) + '. Rules the extract cannot answer (for example LDL) are listed, not silently dropped.',
         'ops': [{'t': 'member', 'r': ['member_id', 'consent_status'], 'rows': allrows('member')},
                 {'t': 'member_feature', 'r': ['member_id', 'feature_key', 'value_num'], 'rows': idx('member_feature', feature_key=['x:cohort_t2d_l12m', 'x:Last_HbA1c_Value'])}],
         'sql': est['sql'].replace('?', '9.0') + ';   -- POST /api/cohorts/estimate'},
        {'id': 'save', 'group': 'studio1', 'title': 'Save the cohort',
         'what': 'Saving writes a new version with its rules as rows, runs it straight away and flags a stable 10% holdout (hash of cohort and member, so a member stays in or out run after run).',
         'ops': [{'t': 'cohort', 'w': ['cohort_id', 'version', 'name', 'base', 'logic', 'row_count'], 'rows': idx('cohort', cohort_id='COH-0106')},
                 {'t': 'cohort_rule', 'w': ['rule_id', 'cohort_id', 'field', 'operator', 'value', 'codes', 'lab', 'is_exclusion'], 'rows': idx('cohort_rule', cohort_id='COH-0106')},
                 {'t': 'cohort_member', 'w': ['cohort_id', 'member_id', 'holdout'], 'rows': idx('cohort_member', cohort_id='COH-0106')}],
         'sql': "INSERT INTO cohort_rule (rule_id, cohort_id, version, field, operator, value, codes, lab, is_exclusion)\nVALUES ('COH-0106-v1-R2', 'COH-0106', 1, 'lab', '≥', '9', '[]', 'hba1c', 0);   -- POST /api/cohorts"},
        {'id': 'campaign', 'group': 'studio1', 'title': 'Create the campaign and hand off',
         'what': 'A campaign names its cohorts, trigger mode (all triggers, or a business-chosen list), channels and capacity. Hand-off sets it Live and runs care intelligence.',
         'ops': [{'t': 'campaign', 'w': ['campaign_id', 'name', 'trigger_mode', 'triggers_json', 'channels', 'priority', 'status'], 'rows': allrows('campaign')},
                 {'t': 'campaign_cohort', 'w': ['campaign_id', 'cohort_id', 'role'], 'rows': allrows('campaign_cohort')}],
         'sql': "INSERT INTO campaign_cohort (campaign_id, cohort_id, role)\nVALUES ('CMP-0103', 'COH-0104', 'include'), ('CMP-0103', 'COH-0101', 'exclude');   -- POST /api/campaigns"},
        {'id': 'outcomes', 'group': 'nightly', 'title': 'Apply the day’s outcomes',
         'what': 'Unprocessed outcomes close needs (done), hold them 90 days (declined), schedule retries (not reached, up to 3) or set consent. The next need is promoted into CURRENT.',
         'ops': [{'t': 'outcome', 'r': ['outcome_id', 'need_id', 'action_id', 'result'], 'w': ['processed_at'], 'rows': allrows('outcome')},
                 {'t': 'care_plan_need', 'w': ['status', 'slot', 'hold_until'], 'rows': idx('care_plan_need', status=['done', 'declined'])},
                 {'t': 'member', 'w': ['consent_status'], 'rows': idx('member', member_id='m133')}],
         'sql': "SELECT * FROM outcome WHERE processed_at IS NULL ORDER BY recorded_at;"},
        {'id': 'cohorts', 'group': 'nightly', 'title': 'Re-run cohorts, pick campaign members',
         'what': 'Each cohort re-runs against the latest extract. A live campaign reaches its cohorts minus exclusions, the holdout, Exclusion = 1 in the extract and declined consent. A member belongs to the highest-priority campaign only.',
         'ops': [{'t': 'cohort_rule', 'r': ['cohort_id', 'field', 'operator', 'value', 'is_exclusion'], 'rows': allrows('cohort_rule')},
                 {'t': 'cohort_member', 'w': ['cohort_id', 'member_id', 'holdout', 'run_at'], 'rows': allrows('cohort_member')},
                 {'t': 'campaign_cohort', 'r': ['campaign_id', 'cohort_id', 'role'], 'rows': allrows('campaign_cohort')}],
         'sql': "SELECT cm.member_id FROM campaign_cohort cc JOIN cohort_member cm USING (cohort_id)\nJOIN member m USING (member_id)\nWHERE cc.campaign_id = 'CMP-0101' AND cc.role = 'include' AND cm.holdout = 0\n  AND m.consent_status <> 'declined'\n  AND NOT EXISTS (SELECT 1 FROM member_feature f WHERE f.member_id = cm.member_id\n                  AND f.feature_key = 'x:Exclusion' AND f.value_num = 1);"},
        {'id': 'assess', 'group': 'nightly', 'title': 'Score and prioritise',
         'what': 'R = C + M + K + U + A from the extract’s score columns. Tier 1 Low 0–3, 2 Moderate 4–7, 3 High 8–12, 4 Very high 13+ (the extract numbers tiers the other way round). Very high tier, a safety flag or BP ≥ 180/110 makes the alert RED (P1, same day); High tier or a recent discharge makes it AMBER (P2, next working day).',
         'ops': [{'t': 'member_feature', 'r': ['feature_key', 'value_num'], 'rows': idx('member_feature', feature_key=['x:Total_risk_Score', 'x:Persona', 'x:Last_SystolicPressure_Value'])},
                 {'t': 'assessment', 'w': ['r_total', 'tier', 'tier_label', 'alert', 'contact_priority', 'priority_review'], 'rows': allrows('assessment')}],
         'sql': assess_sql},
        {'id': 'signals', 'group': 'nightly', 'title': 'Fire triggers',
         'what': 'A trigger fires from its Trig flag in the extract; BP urgent is computed from the latest reading. When the data needed is missing the signal says cannot_tell instead of guessing.',
         'ops': [{'t': 'trigger_def', 'r': ['trigger_code', 'name', 'fires_when', 'class'], 'rows': allrows('trigger_def')},
                 {'t': 'signal', 'w': ['signal_id', 'campaign_id', 'trigger_code', 'state', 'evidence', 'status'], 'rows': allrows('signal')}],
         'sql': "INSERT OR REPLACE INTO signal VALUES\n  ('SIG-m133-Trig3', 'm133', 'CMP-0101', '…', 'Trig3', 'fired', 'Insulin / SU without rescue glucagon', 'open');"},
        {'id': 'plans', 'group': 'nightly', 'title': 'Build care plans',
         'what': 'One plan per member. Each fired trigger becomes a need, ordered safety → acute → uncontrolled → barrier → gap → goal. Top 3 are CURRENT, 4–6 NEXT. Done needs stay done; declined needs wait out their 90-day hold.',
         'ops': [{'t': 'care_plan', 'w': ['care_plan_id', 'pathway', 'tier', 'cadence'], 'rows': allrows('care_plan')},
                 {'t': 'care_plan_need', 'w': ['need_key', 'class', 'slot', 'title', 'due_date', 'status'], 'rows': allrows('care_plan_need')}],
         'sql': "SELECT need_id, class, need_key FROM care_plan_need\nWHERE care_plan_id = 'CP-m133' AND status = 'open';  -- sorted by class order, then slotted 3 / 3 / rest"},
        {'id': 'actions', 'group': 'nightly', 'title': 'Create actions and the call list',
         'what': 'Each CURRENT need gets exactly one care-plan action (unique index). Each member gets one worklist call due by contact priority (P1 today, P2 next day, P3 in 3 days, P4 a digital nudge), spread across nurses by open workload.',
         'ops': [{'t': 'action', 'w': ['action_id', 'need_id', 'kind', 'title', 'due_date', 'assignee', 'status', 'source'], 'rows': allrows('action')},
                 {'t': 'care_team_user', 'r': ['user_id', 'name', 'daily_capacity'], 'rows': allrows('care_team_user')}],
         'sql': "CREATE UNIQUE INDEX action_one_per_need ON action (need_id) WHERE kind = 'care_plan';"},
        {'id': 'intel', 'group': 'studio2', 'title': 'Review the scored list',
         'what': 'The care-intelligence screen lists members by alert then score, with the five risk parts, the ordered needs and their evidence. Nothing is written.',
         'ops': [{'t': 'assessment', 'r': ['r_total', 'tier', 'alert'], 'rows': allrows('assessment')},
                 {'t': 'signal', 'r': ['trigger_code', 'state', 'evidence'], 'rows': idx('signal', status='open')},
                 {'t': 'care_plan_need', 'r': ['need_key', 'class', 'slot', 'title'], 'rows': idx('care_plan_need', status='open')}],
         'sql': "SELECT a.member_id, a.r_total, a.tier_label, a.alert, n.slot, n.title\nFROM assessment a JOIN care_plan p USING (member_id) JOIN care_plan_need n USING (care_plan_id)\nWHERE n.status = 'open' ORDER BY a.alert, a.r_total DESC;   -- GET /api/intel"},
        {'id': 'queue', 'group': 'portal', 'title': 'Open the worklist',
         'what': 'The portal loads members with open signals: the record, needs, linked actions and the last contact. Clinical detail stays locked until consent is on record.',
         'ops': [{'t': 'member', 'r': ['member_id', 'age', 'plan_name', 'consent_status'], 'rows': allrows('member')},
                 {'t': 'action', 'r': ['action_id', 'kind', 'title', 'due_date', 'assignee', 'status'], 'rows': allrows('action')},
                 {'t': 'event_log', 'w': ['op', 'table_name', 'endpoint', 'detail'], 'rows': allrows('event_log')}],
         'sql': "SELECT * FROM action WHERE assignee = 'U-0142' AND status = 'open' ORDER BY due_date;   -- GET /api/portal/members"},
        {'id': 'call', 'group': 'portal', 'title': 'Record the call',
         'what': 'Saving a call writes a contact and its outcomes: consent granted or declined, or not reached (which schedules a retry). A reached call closes the open worklist call.',
         'ops': [{'t': 'contact', 'w': ['contact_id', 'member_id', 'campaign_id', 'user_id', 'reached', 'consent', 'response'], 'rows': allrows('contact')},
                 {'t': 'outcome', 'w': ['outcome_id', 'contact_id', 'member_id', 'result', 'recorded_by'], 'rows': allrows('outcome')},
                 {'t': 'member', 'w': ['consent_status'], 'rows': idx('member', member_id='m133')}],
         'sql': "INSERT INTO outcome (outcome_id, contact_id, member_id, need_id, action_id, result, recorded_by, recorded_at)\nVALUES ('O-000001', 'C-00001', 'm133', NULL, NULL, 'consent_granted', 'U-0142', '…');   -- POST /api/portal/event"},
        {'id': 'done', 'group': 'portal', 'title': 'Close a care-plan need',
         'what': 'Marking a need done in the care plan (or completing its linked action) writes an outcome, closes the need and its action, and promotes the next need into CURRENT straight away. The nightly run re-scores on top.',
         'ops': [{'t': 'outcome', 'w': ['need_id', 'action_id', 'result'], 'rows': idx('outcome', result='done')},
                 {'t': 'care_plan_need', 'w': ['status', 'slot'], 'rows': idx('care_plan_need', care_plan_id='CP-m133')},
                 {'t': 'action', 'w': ['status', 'closed_at'], 'rows': idx('action', member_id='m133')}],
         'sql': "UPDATE care_plan_need SET status = 'done', slot = 'CLOSED' WHERE need_id = 'N-m133-Trig3';\nUPDATE action SET status = 'done' WHERE need_id = 'N-m133-Trig3' AND kind = 'care_plan';"},
    ]
    return {'domains': DOMAINS, 'tables': tables, 'groups': groups, 'steps': steps}


if __name__ == '__main__':
    M = build()
    html = open(PAGE, encoding='utf-8').read()
    blob = json.dumps(M, ensure_ascii=False).replace('</', '<\\/')
    html = re.sub(r'(<script type="application/json" id="model-data">)(.*?)(</script>)', lambda m: m.group(1) + blob + m.group(3), html, count=1, flags=re.S)
    open(PAGE, 'w', encoding='utf-8').write(html)
    print(f"model: {len(M['tables'])} tables · {len(M['steps'])} steps · {sum(len(t['rows']) for t in M['tables'])} sample rows")
