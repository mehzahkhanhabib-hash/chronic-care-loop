#!/usr/bin/env python3
"""Generate the SingleStore SQL that depends on the rulebook and the extract layout.

  python3 two-day-build/tools/gen_sql.py

Reads:  rules/*.csv (the rule database), data/raw/glossary.tsv + the sample extract (column types)
Writes: sql/01_schema.sql, sql/02_rules.sql, sql/03_load.sql, sql/04_nightly.sql (from sql/templates/*)
Re-run it after a rule CSV changes; the hand-written files (05, 06, 90) never need regenerating.
"""
import csv, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
from backend.ingest import infer_type  # noqa: E402  (same typing the prototype backend uses)

SQL = os.path.join(HERE, 'sql')
RULES = os.path.join(REPO, 'rules')


def rd(name):
    return list(csv.DictReader(open(os.path.join(RULES, name + '.csv'), encoding='utf-8')))


# ───────── the member table: only the extract columns the loop reads ─────────
MEMBER_COLS = """mask_id GENDER AGE NATIONALITY plan_name Exclusion Persona Clinical_score Comorbid_complication_score Kidney_score Utilization_score Age_sex_score
Total_risk_Score Priority_clinical_review cohort_t2d_l12m cohort_htn_l12m flag_ckd flag_dyslipidemia_l12m flag_obesity flag_ischemic_heart_disease flag_heart_failure
flag_stroke flag_dm_neuropathy flag_dm_retinopathy_l12m flag_pad_l12m flag_dm_foot_ulcer_l12m flag_amputation flag_dka_l12m flag_dm_hypoglycaemia_l12m
flag_dm_hypoglycaemia_last90days flag_no_glucagon_last12months flag_active_insulin flag_active_ACEinhibitor flag_active_ARBinhibitor Last_HbA1c_Value Last_HbA1c_Date
last_hba1c_date2 Last_SystolicPressure_Value Last_DiastolicPressure_Value Last_SystolicPressure_Date Last_eGFR_Value Last_eGFR_Date Last_UACR_Value Last_UACR_Date
Last_MeasuredBMI_Value last_egfr_test_date last_urine_albumin_date last_lipid_panel_date last_renal_panel_date last_potassium_date last_retinal_screen_date
last_ophthalmology_visit last_foot_exam last_podiatry_visit last_dietitian_visit last_diabeducator_visit first_e11_date first_htn_date last_visit_date
last_ip_discharge_date last_ed_visit_date ed_visits_l12m ip_admissions_l12m pdc_any_t2d_noninsulin pdc_any_htn pdc_mra pdc_thiazide days_since_t2d_supply_ran_out
days_since_htn_supply_ran_out l12m_payable_DiaborHTNrelated Trig1_HbA1c_above_target Trig2_HTN_tx_review Trig3_hypoglycemia_tx Trig4_post_discharge_care
Trig5_Kidney_check Trig6_HbA1c_due Trig7_Renal_Potassium_due Trig8_nutrition_due Trig9_medication_adherence Trig10_new_diagnosis Trig11_annual_labs_due
Trig12_eyeexam_due Trig13_highriskfoot_monitor""".split()
RENAME = {'mask_id': 'member_id', 'GENDER': 'gender', 'AGE': 'age', 'NATIONALITY': 'nationality', 'Exclusion': 'excluded', 'Persona': 'persona'}
PLAUSIBLE = {'Last_SystolicPressure_Value': (60, 260), 'Last_DiastolicPressure_Value': (30, 160), 'Last_MeasuredBMI_Value': (10, 80),
             'Last_HbA1c_Value': (3, 20), 'Last_eGFR_Value': (1, 200), 'Last_UACR_Value': (0, 5000)}   # G0: anything outside → NULL
SQLTYPE = {'flag': 'TINYINT', 'num': 'DECIMAL(10,2)', 'share': 'DECIMAL(6,4)', 'date': 'DATE', 'money': 'DECIMAL(14,2)', 'text': 'VARCHAR(120)'}
ARAB = ['EMIRATI', 'EGYPTIAN', 'JORDANIAN', 'LEBANESE', 'MAURITANIAN', 'MOROCCAN', 'PALESTINIAN', 'SUDANESE', 'SYRIAN', 'IRAQI', 'YEMENI', 'OMANI',
        'SAUDI', 'TUNISIAN', 'ALGERIAN', 'BAHRAINI', 'KUWAITI', 'QATARI', 'LIBYAN']

# Nurse action → follow-up (rulebook §5 write-back, made explicit)
FOLLOWUP = [  # outcome, action_status, need_status, gap_state, hold_days, followup_kind, followup_title, followup_due_days, max_attempts, promote_next, note
    ('reached', 'done', None, None, None, 'follow_up', 'Cadence check-in', None, None, 0, 'Call completed. Next touchpoint on the tier cadence (Tier 4: 7 days, 3: 14, 2: 42, 1: 90).'),
    ('done', 'done', 'done', 'Reported', None, 'follow_up', 'Verify in claims: {done_when}', 14, None, 1, 'Need closes; next need promoted (G7). The gap closes only when the claim arrives.'),
    ('agreed', 'done', 'open', 'Scheduled', None, 'follow_up', 'Check it happened: {done_when}', None, None, 0, 'Member agreed. Follow-up falls on the need due date.'),
    ('declined', 'declined', 'declined', None, 90, 'follow_up', 'Re-offer: {action}', 90, None, 1, 'Held 90 days, never re-offered sooner (G4).'),
    ('not_reached', 'done', None, None, None, 'retry', 'Retry call (attempt {attempt} of 3)', 1, 3, 0, 'Up to 3 attempts in 5 working days; then P1 escalates to the clinical lead.'),
    ('callback', 'done', None, None, None, 'follow_up', 'Callback requested', 1, None, 0, 'Member asked to be called back.'),
    ('carried', 'open', 'open', None, None, None, None, None, None, 0, 'Stays CURRENT with its due date (G9). No new action.'),
    ('escalated', 'done', 'open', None, None, 'escalation', 'Clinician review: {action}', 0, None, 0, 'Red flag on the call: same-day clinician (G1b).'),
]


class Blank(str):
    """An empty string that must stay '' (not NULL) in the SQL."""


def q(v):
    if isinstance(v, Blank):
        return "''"
    if v is None or v == '':
        return 'NULL'
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def ins(table, cols, rows):
    return f'INSERT INTO {table} ({", ".join(cols)}) VALUES\n' + ',\n'.join('  (' + ', '.join(q(v) for v in r) + ')' for r in rows) + ';\n'


def main():
    gl = [r['column'] for r in csv.DictReader(open(os.path.join(REPO, 'data/raw/glossary.tsv'), encoding='utf-8'), delimiter='\t')]
    rows = list(csv.reader(open(os.path.join(REPO, 'data/raw/member_features_sample.tsv'), encoding='utf-8'), delimiter='\t'))
    hdr = rows[0]
    vals = {c: [r[i] for r in rows[1:]] for i, c in enumerate(hdr)}
    types = {c: infer_type(c, vals.get(c, [])) for c in MEMBER_COLS}
    types['mask_id'] = 'text'
    name = lambda c: RENAME.get(c, c.lower())

    # ── 01 schema (staging + member generated; the rest is a template) ──
    stg = 'CREATE ROWSTORE TABLE IF NOT EXISTS stg_extract (\n' + ',\n'.join(f'  `{c}` TEXT' for c in gl) + ',\n  SHARD KEY (`mask_id`)\n);\n'
    mem_cols = []
    for c in MEMBER_COLS:
        n = name(c)
        t = 'VARCHAR(20) NOT NULL' if n == 'member_id' else SQLTYPE[types[c]]
        mem_cols.append(f'  {n:<34} {t}')
    member = ('CREATE ROWSTORE TABLE IF NOT EXISTS member (\n' + ',\n'.join(mem_cols) + ''',
  -- set by the load
  language                           VARCHAR(20),
  has_t2d                            TINYINT,
  has_htn                            TINYINT,
  consent                            VARCHAR(10) NOT NULL DEFAULT 'pending',   -- pending | granted | declined (written by the portal)
  -- set by the nightly run (rulebook §2 and §4)
  r_total                            INT,
  tier                               INT,           -- 1 Low · 2 Moderate · 3 High · 4 Very high
  alert                              VARCHAR(6),    -- RED | AMBER | YELLOW | GREEN
  contact_priority                   VARCHAR(2),    -- P1 … P4
  scored_on                          DATE,
  PRIMARY KEY (member_id)
);
''')
    tpl = open(os.path.join(SQL, 'templates', '01_schema.sql'), encoding='utf-8').read()
    open(os.path.join(SQL, '01_schema.sql'), 'w', encoding='utf-8').write(tpl.replace('-- @@STAGING@@', stg).replace('-- @@MEMBER@@', member))

    # ── 02 rules ──
    trig = {r['trigger_code']: r for r in rd('rule_trigger')}
    act = {r['trigger_code']: r for r in rd('rule_action')}
    cls = {r['class']: r for r in rd('rule_need_class')}
    out = ['-- Rule data: the CCC Rulebook (T2D and Hypertension, 20 Nov 2026). Generated from rules/*.csv by tools/gen_sql.py.\n',
           'DELETE FROM rule_trigger;\n' + ins('rule_trigger', ['trigger_code', 'name', 'pathway', 'class', 'class_label', 'class_order', 'trigger_order', 'due_days',
                                                                 'raw_data', 'fires_when', 'extract_flag', 'action_code', 'action_title', 'owner_role', 'channel', 'done_when', 'evidence',
                                                                 'escalate_to', 'use_variant', 'status'],
                                              [(c, t['name'], t['pathway'], t['class'], cls[t['class']]['label'], int(cls[t['class']]['sort_order']), int(t['sort_order']),
                                                int(cls[t['class']]['due_days']), t['raw_data_rulebook'], t['fires_when_rulebook'], t['extract_flag'] or None,
                                                act[c]['action_code'], act[c]['title'], act[c]['owner_role'], act[c]['channel'], act[c]['done_when'],
                                                act[c]['evidence'], act[c]['escalate_to'] or None, t['use_variant'], t['status']) for c, t in sorted(trig.items(), key=lambda x: int(x[1]['sort_order']))]),
           'DELETE FROM rule_priority;\n' + ins('rule_priority', ['priority', 'alert', 'needs_trigger', 'sla_days', 'channel', 'match_order'],
                                                [(r['priority'], r['alert'], r['also_requires_trigger'] or Blank(''), r['sla_days'] or None, r['channel'], i + 1)
                                                 for i, r in enumerate(rd('rule_contact_priority'))]),
           'DELETE FROM rule_tier;\n' + ins('rule_tier', ['tier', 'label', 'r_min', 'r_max'], [(int(r['tier']), r['label'], int(r['r_min']), int(r['r_max'])) for r in rd('rule_tier')]),
           'DELETE FROM rule_cadence;\n' + ins('rule_cadence', ['tier', 'step', 'day_offset'],
                                               [(int(r['tier']), i + 1, int(d)) for r in rd('rule_tier') for i, d in enumerate(r['cadence_days'].split(','))]),
           'DELETE FROM rule_followup;\n' + ins('rule_followup', ['outcome', 'action_status', 'need_status', 'gap_state', 'hold_days', 'followup_kind', 'followup_title',
                                                                   'followup_due_days', 'max_attempts', 'promote_next', 'note'], FOLLOWUP)]
    open(os.path.join(SQL, '02_rules.sql'), 'w', encoding='utf-8').write('\n'.join(out))

    # ── 03 load: staging → typed member with the cleaning formulas (G0) ──
    sel = []
    for c in MEMBER_COLS:
        s, t, n = f'TRIM(s.`{c}`)', types[c], name(c)
        blank = f"{s} IN ('', 'NULL', 'null', 'NaN')"
        if t == 'text':
            e = f"CASE WHEN {blank} THEN NULL ELSE {s} END"
        elif t == 'date':
            e = f"CASE WHEN {s} REGEXP '^[0-9]{{1,2}}/[0-9]{{1,2}}/[0-9]{{4}}$' THEN STR_TO_DATE({s}, '%m/%d/%Y') END"
        elif t == 'money':
            m = f"REPLACE({s}, ',', '')"
            e = f"CASE WHEN {s} = '-' THEN 0 WHEN {m} REGEXP '^-?[0-9]+(\\\\.[0-9]+)?$' THEN CAST({m} AS DECIMAL(14,2)) END"
        else:
            e = f"CASE WHEN {s} REGEXP '^-?[0-9]+(\\\\.[0-9]+)?$' THEN CAST({s} AS DECIMAL(14,4)) END"
            if c in PLAUSIBLE:
                lo, hi = PLAUSIBLE[c]
                e = f"CASE WHEN ({e}) BETWEEN {lo} AND {hi} THEN ({e}) END"
        sel.append(f'  {e} AS {n}')
    cols = [name(c) for c in MEMBER_COLS]
    load = open(os.path.join(SQL, 'templates', '03_load.sql'), encoding='utf-8').read()
    upd = ', '.join(f'{c} = VALUES({c})' for c in cols[1:] + ['language', 'has_t2d', 'has_htn'])
    load = load.replace('-- @@INSERT@@', f'''INSERT INTO member ({", ".join(cols)}, language, has_t2d, has_htn)
SELECT {(","+chr(10)).join(sel)},
  CASE WHEN UPPER(TRIM(s.`NATIONALITY`)) IN ({", ".join(q(a) for a in ARAB)}) THEN 'Arabic' ELSE 'English' END,
  CASE WHEN TRIM(s.`cohort_t2d_l12m`) = '1' THEN 1 ELSE 0 END,
  CASE WHEN TRIM(s.`cohort_htn_l12m`) = '1' THEN 1 ELSE 0 END
FROM stg_extract s
WHERE TRIM(s.`mask_id`) <> ''
ON DUPLICATE KEY UPDATE {upd};   -- consent and scores survive a reload''')
    open(os.path.join(SQL, '03_load.sql'), 'w', encoding='utf-8').write(load)

    # ── 04 nightly: trigger SQL generated from rule_condition ──
    def term(c):
        col, op, v = name(c['column_name']), c['op'], c['value']
        is_date = types.get(c['column_name']) == 'date'
        x = f'DATEDIFF(rc.as_of, m.{col})' if is_date else f'm.{col}'
        if op == 'is_null':
            return f'm.{col} IS NULL'
        if op == 'not_null':
            return f'm.{col} IS NOT NULL'
        if op == 'missing_or_gt':
            return f'(m.{col} IS NULL OR {x} > {v})'
        return f'{x} {op} {v}'

    groups = {}
    for c in rd('rule_condition'):
        groups.setdefault((c['rule_type'], c['target'], c['variant']), {}).setdefault(int(c['group_no']), []).append(c)

    def cond(key):
        g = groups.get(key)
        if not g:
            return None
        return '(' + '\n       OR '.join('(' + ' AND '.join(term(c) for c in cs) + ')' for _, cs in sorted(g.items())) + ')'

    def evidence(keys):
        cols_ = []
        for k in keys:
            for cs in groups.get(k, {}).values():
                for c in cs:
                    n = c['column_name']
                    if not n.startswith(('cohort_', 'Trig')) and n not in cols_:
                        cols_.append(n)
        if not cols_:
            return "'Flag set in the extract'"
        parts = [f"CONCAT('{n} ', COALESCE(CAST(m.{name(n)} AS CHAR), 'none'))" for n in cols_[:4]]
        return 'CONCAT_WS(\'; \', ' + ', '.join(parts) + ')'

    blocks = []
    for code, t in sorted(trig.items(), key=lambda x: int(x[1]['sort_order'])):
        ext, rb = cond(('trigger', code, 'extract')), cond(('trigger', code, 'rulebook'))
        variants = []
        if ext:
            variants.append(f"(t.use_variant = 'extract' AND {ext})")
        if rb:
            variants.append(f"(t.use_variant = 'rulebook' AND {rb})")
        fired = '(' + '\n    OR '.join(variants) + ')'
        blocks.append(f"""-- {code} · {t['name']} · fires when: {t['fires_when_rulebook']}
SELECT m.member_id, '{code}', 'fired', {evidence([('trigger', code, 'rulebook')])}, rc.run_date
FROM member m JOIN run_config rc JOIN rule_trigger t ON t.trigger_code = '{code}'
WHERE {fired}""")
        ct = cond(('cannot_tell', code, 'any'))
        if ct:
            blocks.append(f"""-- {code} · cannot tell (a needed value is missing: ask the nurse once, G8)
SELECT m.member_id, '{code}', 'cannot_tell', '{groups[('cannot_tell', code, 'any')][1][-1]['note']}', rc.run_date
FROM member m JOIN run_config rc JOIN rule_trigger t ON t.trigger_code = '{code}'
WHERE {ct}
  AND NOT {fired}""")
    signals = 'INSERT INTO member_signal (member_id, trigger_code, state, evidence, run_date)\n' + '\nUNION ALL\n'.join(blocks) + ';\n'
    alerts = {k: cond(('alert', k, 'any')) for k in ('RED', 'AMBER')}
    nightly = open(os.path.join(SQL, 'templates', '04_nightly.sql'), encoding='utf-8').read()
    nightly = nightly.replace('-- @@SIGNALS@@', signals).replace('@@RED@@', alerts['RED']).replace('@@AMBER@@', alerts['AMBER'])
    open(os.path.join(SQL, '04_nightly.sql'), 'w', encoding='utf-8').write(nightly)
    print('generated 01_schema.sql, 02_rules.sql, 03_load.sql, 04_nightly.sql')


if __name__ == '__main__':
    main()
