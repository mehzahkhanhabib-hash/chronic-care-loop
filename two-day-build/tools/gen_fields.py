#!/usr/bin/env python3
"""The field catalogue as data, not code.

Reads   rules/rule_layout.csv            which extract layouts exist (header file, sample file)
        rules/rule_input.csv             rulebook input → field (the mapping the clinical / data team edits)
        data/raw/glossary.tsv            descriptions, where the glossary has them
        the header of every layout file
Writes  rules/rule_field.csv             one row per field ever seen in any layout: sql_name, type, group, description,
                                         in_<layout> flags, load (1 when a rule, a screen or a key needs it), plausibility bounds

Existing hand-edited values in rule_field.csv (load, sql_name, plausible_min/max, group, description) are kept; new fields are added
with defaults; nothing is hard-coded in gen_sql.py any more. Run it whenever a new extract layout arrives, then gen_sql.py.
    python3 two-day-build/tools/gen_fields.py
"""
import csv, os, re, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
from backend.ingest import infer_type  # noqa: E402
RULES = os.path.join(REPO, 'rules')

def rd(name):
    p = os.path.join(RULES, name + '.csv')
    return list(csv.DictReader(open(p, encoding='utf-8-sig'))) if os.path.exists(p) else []

def header_and_values(path):
    rows = list(csv.reader(open(os.path.join(REPO, path), encoding='utf-8-sig'), delimiter='\t'))
    return rows[0], {c: [r[i] for r in rows[1:] if i < len(r)] for i, c in enumerate(rows[0])}

SQLNAME = {'mask_id': 'member_id', 'GENDER': 'gender', 'AGE': 'age', 'NATIONALITY': 'nationality', 'Exclusion': 'excluded', 'Persona': 'persona',
           '# of triggers': 'n_triggers', 'Risk Premium': 'risk_premium', 'eGFR + UACR points': 'egfr_uacr_points'}
def sql_name(c): return SQLNAME.get(c, re.sub(r'[^a-z0-9_]', '_', c.lower()))

def group(c):
    cl = c.lower()
    if c == 'mask_id': return 'Identity'
    if c in ('GENDER', 'AGE', 'NATIONALITY', 'plan_name', 'policy_group', 'policy_type', 'GWP', 'Risk Premium'): return 'Who they are'
    if c.startswith('Trig'): return 'Trigger flags (extract-computed)'
    if c in ('HbA1c_score', 'Clinical_score', 'Comorbid_complication_score', 'eGFR + UACR points', 'Kidney_score', 'Utilization_score', 'Age_sex_score',
             'Total_risk_Score', 'Risk_tier', 'Priority_clinical_review', '# of triggers', 'rank_PURECS_per_payable'): return 'Risk score (extract-computed)'
    if c.startswith(('P1_', 'P2_', 'P3_', 'P4_', 'P5_')) or c in ('Persona', 'Cohort_allocation', 'Initial_target_cohort'): return 'Persona and targeting'
    if c.startswith('Exclusion') or 'excl' in cl or c.startswith(('flag_oncology', 'oncology', 'flag_benign', 'home_nursing', 'max_episode', 'specialty_rx', 'flag_av_access', 'last_av_access')): return 'Exclusions and gates'
    if c.startswith(('cohort_', 't2d_identified', 'htn_identified', 't2d_category', 'htn_category')): return 'Pathway'
    if c.startswith('Last_') or (cl.startswith('last_') and any(k in cl for k in ('glucose', 'hba1c_date2', 'panel', 'albumin', 'egfr_test', 'retinal', 'liver', 'cbc', 'vitb12', 'potassium', 'smoking'))): return 'Labs and readings'
    if cl.startswith('last_') and cl.endswith(('_visit', 'foot_exam')): return 'Visits by specialty'
    if cl.startswith('first_') and 'fill' not in cl and 'visit' not in cl and 'ace' not in cl: return 'Diagnosis dates'
    if c.startswith('flag_') or (cl.startswith('last_') and '_date' in cl) or c in ('dm_complications', 'dm_complication_count', 'ckd_stage_l12m'): return 'Conditions and complications'
    if 'pdc' in cl or 'drug' in cl or 'fill' in cl or 'supply' in cl or 'medicin' in cl or 'rx_gap' in cl or 'glucagon' in cl or 'class_start' in cl: return 'Medicines and adherence'
    if any(k in cl for k in ('ip_', 'ed_', 'er_visits', 'discharge', 'visit', 'gp_claims', 'specialist_claims', 'encounter')) and 'payable' not in cl: return 'Visits and admissions'
    if 'payable' in cl or 'share' in cl or 'provider' in cl or 'groupowner' in cl: return 'Cost and network'
    if c.startswith('last_claim'): return 'Last claim (display)'
    return 'Other'

# fields a screen or a key needs even when no rule reads them (the only list in this file, and it is a list of screen needs, not of columns)
SCREEN_FIELDS = {'mask_id', 'GENDER', 'AGE', 'NATIONALITY', 'plan_name', 'policy_type', 'Exclusion', 'Persona', 'Cohort_allocation', 'Risk_tier',
                 'last_ip_facility', 'last_ip_dx_desc', 'last_ed_dx_desc', 'last_claim_date', 'last_claim_medicines', 'active_drug_classes',
                 'dm_complications', 'ckd_stage_l12m', 't2d_category', 'htn_category', 'phg_share_l12m_encounters', 'l12m_payable_allcause'}
PLAUSIBLE = {'Last_SystolicPressure_Value': (60, 260), 'Last_DiastolicPressure_Value': (30, 160), 'Last_MeasuredBMI_Value': (10, 80),
             'Last_HbA1c_Value': (3, 20), 'Last_eGFR_Value': (1, 200), 'Last_UACR_Value': (0, 5000)}   # G0 defaults for new rows; edit in the CSV afterwards

def main():
    layouts = rd('rule_layout'); assert layouts, 'rules/rule_layout.csv is missing'
    gl = {r['column']: r for r in csv.DictReader(open(os.path.join(REPO, 'data/raw/glossary.tsv'), encoding='utf-8'), delimiter='\t')}
    existing = {r['field']: r for r in rd('rule_field')}
    used = {r['field'] for r in rd('rule_input')} | {r['column_name'] for r in rd('rule_condition')}
    seen, types, inlay = [], {}, {}
    for L in layouts:
        hdr, vals = header_and_values(L['sample_file'])
        for c in hdr:
            if c not in seen: seen.append(c)
            inlay.setdefault(c, set()).add(L['layout_id'])
            t = infer_type(c, vals.get(c, []))
            types[c] = t if types.get(c) in (None, 'text') else types[c]   # a typed guess beats 'text'
    out = []
    for c in seen:
        e = existing.get(c, {})
        row = {'field': c, 'sql_name': e.get('sql_name') or sql_name(c), 'type': 'text' if c == 'mask_id' else types[c],
               'group': e.get('group') or group(c), 'description': e.get('description') or gl.get(c, {}).get('description', ''),
               'load': '1' if (c in used or c in SCREEN_FIELDS or e.get('load') == '1') else '0',   # a rule or a screen needs it, or someone set it by hand
               'plausible_min': e.get('plausible_min') or (str(PLAUSIBLE[c][0]) if c in PLAUSIBLE else ''),
               'plausible_max': e.get('plausible_max') or (str(PLAUSIBLE[c][1]) if c in PLAUSIBLE else '')}
        for L in layouts: row['in_' + L['layout_id']] = '1' if L['layout_id'] in inlay[c] else '0'
        row['read_by_rules'] = '; '.join(sorted({f"{r['rule_table']}:{r['rule_key']}" for r in rd('rule_input') if r['field'] == c}))
        out.append(row)
    cols = ['field', 'sql_name', 'type', 'group', 'load'] + ['in_' + L['layout_id'] for L in layouts] + ['plausible_min', 'plausible_max', 'read_by_rules', 'description']
    with open(os.path.join(RULES, 'rule_field.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(out)
    print(f"rule_field.csv: {len(out)} fields, {sum(r['load']=='1' for r in out)} loaded, layouts: {[L['layout_id'] for L in layouts]}")

if __name__ == '__main__':
    main()
