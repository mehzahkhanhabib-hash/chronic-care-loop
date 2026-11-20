"""Load the member-level extract + glossary into the relational model, with data-quality checks.

  python3 -m backend.ingest data/raw/member_features_sample.tsv [--glossary data/raw/glossary.tsv]
"""
import csv, json, os, re, sys
from datetime import date
from . import store
from .reference import AS_OF, RUN_DATE, NOT_SELECTABLE, TRIGGERS, CARE_TEAM

DATE_RE = re.compile(r'^(\d{1,2})/(\d{1,2})/(\d{4})$')
MAIN_TRIGS = ['Trig1_HbA1c_above_target', 'Trig2_HTN_tx_review', 'Trig3_hypoglycemia_tx', 'Trig4_post_discharge_care', 'Trig5_Kidney_check',
              'Trig6_HbA1c_due', 'Trig7_Renal_Potassium_due', 'Trig8_nutrition_due', 'Trig9_medication_adherence', 'Trig10_new_diagnosis',
              'Trig11_annual_labs_due', 'Trig12_eyeexam_due', 'Trig13_highriskfoot_monitor']
SCORE_PARTS = ['Clinical_score', 'Comorbid_complication_score', 'Kidney_score', 'Utilization_score', 'Age_sex_score']
PLAUSIBLE = {'Last_SystolicPressure_Value': (60, 260), 'Last_DiastolicPressure_Value': (30, 160), 'Last_MeasuredBMI_Value': (10, 80),
             'Last_HbA1c_Value': (3, 20), 'Last_eGFR_Value': (1, 200), 'Last_UACR_Value': (0, 5000)}


def is_null(v):
    return v is None or v.strip() in ('', 'NULL', 'null', 'NaN')


def to_iso(v):
    m = DATE_RE.match(v.strip())
    return f'{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}' if m else None


def to_num(v):
    s = v.strip().replace(',', '')
    if s in ('-', ''):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def infer_type(col, values):
    vals = [v for v in values if not is_null(v)]
    if not vals:   # nothing to look at in this file: type from the column name
        if col.startswith('pdc_') or 'share' in col:
            return 'share'
        if col.startswith(('flag_', 'Trig', 'cohort_')):
            return 'flag'
        if 'date' in col or col.endswith(('_visit', '_exam')):
            return 'date'
        if col.endswith(('_value', '_Value', '_days_l12m')) or col.startswith('rank_'):
            return 'num'
        return 'text'
    if all(DATE_RE.match(v.strip()) for v in vals):
        return 'date'
    if any(re.match(r'^\s+[\d,.-]', v) or ',' in v.strip() and re.match(r'^[\d,.]+$', v.strip()) for v in vals) and all(to_num(v) is not None or v.strip() == '-' for v in vals):
        return 'money'
    if all(to_num(v) is not None for v in vals if v.strip() != '-'):
        nums = [to_num(v) for v in vals if to_num(v) is not None]
        if nums and set(nums) <= {0.0, 1.0} and (col.startswith(('flag_', 'Trig', 'P1_', 'P2_', 'P3_', 'P4_', 'P5_', 'cohort_')) or col in ('Exclusion', 'Priority_clinical_review')):
            return 'flag'
        if 'share' in col or col.startswith('pdc_'):
            return 'share'
        return 'num'
    return 'text'


def label_of(col):
    return col.replace('_', ' ').replace('l12m', '12 m').strip()


def load(path, glossary_path=None, con=None):
    con = con or store.connect()
    store.create_schema(con)
    glossary_path = glossary_path or os.path.join(os.path.dirname(path), 'glossary.tsv')
    gl = {r['column']: r for r in csv.DictReader(open(glossary_path, encoding='utf-8'), delimiter='\t')}
    with open(path, encoding='utf-8') as f:
        rdr = csv.reader(f, delimiter='\t')
        header = next(rdr)
        data = [r for r in rdr if r and any(x.strip() for x in r)]
    run_id = 'RUN-' + store.now().replace('-', '').replace(':', '').replace(' ', '-')
    issues = []

    def issue(member, col, val, rule, sev):
        issues.append((run_id, member, col, val, rule, sev))

    if missing := [c for c in header if c not in gl]:
        issue(None, ','.join(missing), None, 'Columns not described in the glossary', 'warn')
    if extra := [c for c in gl if c not in header]:
        issue(None, ','.join(extra), None, 'Glossary columns missing from the file', 'warn')
    for i, r in enumerate(data):
        if len(r) != len(header):
            issue(r[0] if r else None, None, str(len(r)), f'Row has {len(r)} values for {len(header)} columns', 'error')
    data = [r for r in data if len(r) == len(header)]
    cols = {c: [r[i] for r in data] for i, c in enumerate(header)}
    types = {c: infer_type(c, cols[c]) for c in header}

    with store._lock:
        cur = con.cursor()
        cur.execute('INSERT INTO ingest_run VALUES (?,?,?,?,?,?)', (run_id, os.path.basename(path), AS_OF, len(data), len(header), store.now()))
        for u in CARE_TEAM:
            cur.execute('INSERT OR IGNORE INTO care_team_user VALUES (?,?,?,?,?)', u)
        # feature catalogue: one row per extract column + derived fields
        for c in header:
            g = gl.get(c, {})
            cat = g.get('category', 'Uncategorised')
            cur.execute('INSERT OR REPLACE INTO feature VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        ('x:' + c, label_of(c), cat, g.get('description', ''), 'extract', types[c],
                         'AED' if types[c] == 'money' else ('days before as-of' if types[c] == 'date' else None),
                         0 if cat in NOT_SELECTABLE or c == 'mask_id' else 1, None, 'U-0201', store.now()))
        derived = [('d:chronic_count', 'Chronic conditions', 'num', 'Count of T2D, HTN, dyslipidaemia, obesity, CKD, IHD, heart failure, stroke flags'),
                   ('d:readmit_30d', 'Readmitted within 30 days', 'flag', 'Last admission within 30 days of the previous discharge'),
                   ('d:pdc_min_pct', 'Lowest adherence (PDC %)', 'num', 'min(pdc_any_t2d_noninsulin, pdc_any_htn) × 100'),
                   ('d:phg_share_pct', 'Encounters at PHG (%)', 'num', 'phg_share_l12m_encounters × 100')]
        for k, l, t, d in derived:
            cur.execute('INSERT OR REPLACE INTO feature VALUES (?,?,?,?,?,?,?,?,?,?,?)', (k, l, 'Derived', d, 'derived', t, None, 1, d, 'U-0201', store.now()))
        cur.execute('DELETE FROM member_feature')

        for r in data:
            raw = dict(zip(header, r))
            mid = raw['mask_id'].strip()
            cur.execute('INSERT OR REPLACE INTO src_member_row VALUES (?,?,?)', (run_id, mid, json.dumps(raw)))
            num = lambda c: to_num(raw[c]) if c in raw and not is_null(raw[c]) else None
            cur.execute('''INSERT INTO member (member_id, gender, age, nationality, plan_name, policy_group, policy_type, gwp, risk_premium)
                           VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(member_id) DO UPDATE SET gender=excluded.gender, age=excluded.age,
                           nationality=excluded.nationality, plan_name=excluded.plan_name, policy_group=excluded.policy_group,
                           policy_type=excluded.policy_type, gwp=excluded.gwp, risk_premium=excluded.risk_premium''',
                        (mid, raw['GENDER'].strip() or None, int(num('AGE') or 0) or None, raw['NATIONALITY'].strip() or None, raw['plan_name'].strip() or None,
                         None if raw['policy_group'].strip() in ('', '-') else raw['policy_group'].strip(), None if raw['policy_type'].strip() in ('', '-') else raw['policy_type'].strip(),
                         num('GWP'), num('Risk Premium')))
            vals = {}
            for c in header:
                v, t = raw[c], types[c]
                if is_null(v):
                    continue
                vn, vt = None, None
                if t == 'date':
                    iso = to_iso(v)
                    vt, vn = iso, (date.fromisoformat(AS_OF) - date.fromisoformat(iso)).days if iso else None
                    if iso and iso > RUN_DATE:
                        issue(mid, c, v, 'Date after the run date', 'warn')
                elif t == 'money':
                    vn = to_num(v) if v.strip() != '-' else 0.0
                elif t in ('num', 'flag', 'share'):
                    vn = to_num(v)
                else:
                    vt = v.strip()
                if c in PLAUSIBLE and vn is not None:
                    lo, hi = PLAUSIBLE[c]
                    if not lo <= vn <= hi:
                        issue(mid, c, v, '999 placeholder' if vn == 999 else f'Implausible value (expected {lo}-{hi})', 'error')
                        vn = None
                if vn is None and vt is None:
                    continue
                vals[c] = vn if vn is not None else vt
                cur.execute('INSERT INTO member_feature VALUES (?,?,?,?,?)', (mid, 'x:' + c, vn, vt, AS_OF))
            # consistency checks against the extract's own definitions
            parts = [vals.get(p) for p in SCORE_PARTS]
            if None not in parts and vals.get('Total_risk_Score') is not None and sum(parts) != vals['Total_risk_Score']:
                issue(mid, 'Total_risk_Score', str(vals['Total_risk_Score']), f'Total ≠ sum of parts ({int(sum(parts))})', 'error')
            n_trig = sum(int(vals.get(t, 0) or 0) for t in MAIN_TRIGS)
            if vals.get('# of triggers') is not None and n_trig != vals['# of triggers']:
                issue(mid, '# of triggers', str(vals['# of triggers']), f'Count ≠ number of main trigger flags ({n_trig})', 'warn')
            R = vals.get('Total_risk_Score')
            if R is not None:
                expect = '1. Very High' if R >= 13 else '2. High' if R >= 8 else '3. Moderate' if R >= 4 else '4. Low'
                if str(vals.get('Risk_tier', '')).strip() != expect:
                    issue(mid, 'Risk_tier', str(vals.get('Risk_tier')), f'Tier label does not match R = {int(R)} (expected {expect})', 'warn')
            a1 = vals.get('Last_HbA1c_Value')
            if vals.get('Trig1_HbA1c_above_target') == 1 and a1 is not None and a1 < 8:
                issue(mid, 'Trig1_HbA1c_above_target', str(a1), 'Fires below the rulebook goal (~8%): extract threshold is 6.5%', 'info')
            if vals.get('Last_HbA1c_Date') and vals.get('last_hba1c_date2') and vals['Last_HbA1c_Date'] != vals['last_hba1c_date2']:
                issue(mid, 'last_hba1c_date2', raw['last_hba1c_date2'], 'HbA1c test billed on a different date from the latest result', 'info')
            # derived features
            flags = ['cohort_t2d_l12m', 'cohort_htn_l12m', 'flag_dyslipidemia_l12m', 'flag_obesity', 'flag_ckd', 'flag_ischemic_heart_disease', 'flag_heart_failure', 'flag_stroke']
            d = {'d:chronic_count': sum(int(vals.get(f, 0) or 0) for f in flags)}
            if vals.get('last_ip_admit_date') and vals.get('second_last_ip_discharge_date'):
                gap = vals['second_last_ip_discharge_date'] - vals['last_ip_admit_date']   # both in days before as-of
                d['d:readmit_30d'] = 1 if 0 <= gap <= 30 else 0
            else:
                d['d:readmit_30d'] = 0
            pdcs = [vals[p] for p in ('pdc_any_t2d_noninsulin', 'pdc_any_htn') if vals.get(p) is not None]
            if pdcs:
                d['d:pdc_min_pct'] = round(min(pdcs) * 100, 1)
            if vals.get('phg_share_l12m_encounters') is not None:
                d['d:phg_share_pct'] = round(vals['phg_share_l12m_encounters'] * 100, 1)
            for k, v in d.items():
                cur.execute('INSERT INTO member_feature VALUES (?,?,?,?,?)', (mid, k, v, None, AS_OF))

        # file-level findings
        if all(is_null(v) for v in cols.get('rank_PURECS_per_payable', [])):
            issue(None, 'rank_PURECS_per_payable', '', 'Empty for every row', 'warn')
        issue(None, 'Risk_tier', '1. Very High … 4. Low', 'Reverse numbering vs rulebook (1 Low … 4 Very high); backend stores rulebook numbering', 'info')
        if any(v.strip() == 'PREVHEALTH' for v in cols.get('Cohort_allocation', [])):
            issue(None, 'Cohort_allocation', 'PREVHEALTH', "Glossary spells it 'PREVHEATH'", 'info')
        money = [c for c in header if types[c] == 'money']
        if money:
            issue(None, ', '.join(money[:3]) + (' …' if len(money) > 3 else ''), ' 7,268.55 ', f'{len(money)} money columns use spreadsheet formatting (spaces, thousands separators, "-" for zero)', 'info')
        cur.executemany('INSERT INTO data_issue (run_id, member_id, column_name, raw_value, rule, severity) VALUES (?,?,?,?,?,?)', issues)
        store.log(con, 'WRITE', 'ingest_run', {'run_id': run_id, 'rows': len(data)}, 'ingest')
        store.log(con, 'WRITE', 'member_feature', f'{len(data)} members × {len(header)} columns', 'ingest')
        con.commit()
    return {'run_id': run_id, 'rows': len(data), 'columns': len(header), 'issues': len(issues),
            'types': {t: sum(1 for c in types if types[c] == t) for t in set(types.values())}}


if __name__ == '__main__':
    args = sys.argv[1:]
    g = args[args.index('--glossary') + 1] if '--glossary' in args else None
    print(json.dumps(load(args[0], g), indent=1))
