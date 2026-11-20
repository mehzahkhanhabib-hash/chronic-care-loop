"""Cohort rules (the Studio builder's JSON) → SQL over member_feature. Rulebook §2: raw inputs only."""
import hashlib, json
from . import store
from .reference import RUN_DATE

OPS = {'≥': '>=', '≤': '<=', '=': '=', '>=': '>=', '<=': '<=', '>': '>', '<': '<'}
LABS = {'hba1c': 'Last_HbA1c_Value', 'egfr': 'Last_eGFR_Value', 'uacr': 'Last_UACR_Value', 'sbp': 'Last_SystolicPressure_Value', 'bmi': 'Last_MeasuredBMI_Value'}
LAB_DATES = {'hba1c': 'last_hba1c_date2', 'egfr': 'last_egfr_test_date', 'uacr': 'last_urine_albumin_date', 'ldl': 'last_lipid_panel_date'}
DX = {'E11': 'cohort_t2d_l12m', 'I10': 'cohort_htn_l12m', 'E78': 'flag_dyslipidemia_l12m', 'E66': 'flag_obesity', 'N18': 'flag_ckd',
      'I50': 'flag_heart_failure', 'I25': 'flag_ischemic_heart_disease', 'I63': 'flag_stroke'}
NEWDX = {'E11': 'first_e11_date', 'I10': 'first_htn_date'}
SPEC = {'ENDO': 'last_endocrinology_visit', 'CARD': 'last_cardiology_visit', 'NEPH': 'last_nephrology_visit', 'OPH': 'last_ophthalmology_visit', 'DIET': 'last_dietitian_visit'}
NUM_FIELDS = {'age': 'x:AGE', 'ncc': 'd:chronic_count', 'ed': 'x:ed_visits_l12m', 'ip': 'x:ip_admissions_l12m', 'nofu': 'x:last_visit_date',
              'pdc': 'd:pdc_min_pct', 'poly': 'x:active_drug_class_count', 'innet': 'd:phg_share_pct', 'cost': 'x:l12m_payable_DiaborHTNrelated'}
FLAG_FIELDS = {'readm': 'd:readmit_30d', 'pregnant': 'x:flag_excl_pregnant_postpartum', 'onco': 'x:flag_oncology_l24m'}


def _has(key, cond='1=1'):
    return f"EXISTS (SELECT 1 FROM member_feature f WHERE f.member_id = m.member_id AND f.feature_key = '{key}' AND {cond})"


def _num(key, op, v, v2=None):
    if op == 'between':
        return _has(key, 'f.value_num BETWEEN ? AND ?'), [float(v), float(v2)]
    return _has(key, f'f.value_num {OPS.get(op, ">=")} ?'), [float(v)]


def compile_rule(r):
    """Return (sql, params, reason). sql is None when the extract cannot answer the rule."""
    f = r.get('f') or r.get('field')
    vs = r.get('vs') or r.get('codes') or []
    if isinstance(vs, str):
        vs = json.loads(vs or '[]')
    op, v, v2 = r.get('op') or r.get('operator') or '≥', r.get('v', r.get('value')), r.get('v2', r.get('value2'))
    try:
        if f in NUM_FIELDS:
            return (*_num(NUM_FIELDS[f], op, v, v2), None)
        if f in FLAG_FIELDS:
            return _has(FLAG_FIELDS[f], 'f.value_num = 1'), [], None
        if f == 'gender':
            return (_has('x:GENDER', f"f.value_text IN ({','.join('?' * len(vs))})"), list(vs), None) if vs else (None, [], 'pick a value')
        if f == 'nat':
            parts = []
            if 'UAE' in vs: parts.append(_has('x:NATIONALITY', "f.value_text = 'EMIRATI'"))
            if 'EXP' in vs: parts.append(_has('x:NATIONALITY', "f.value_text <> 'EMIRATI'"))
            return ('(' + ' OR '.join(parts) + ')', [], None) if parts else (None, [], 'pick a value')
        if f == 'plan':
            like = {'ENH': "f.value_text LIKE 'Enhanced%'", 'BAS': "(f.value_text LIKE 'Core%' OR f.value_text LIKE 'Basic%')", 'THQ': "f.value_text LIKE 'Thiqa%'"}
            parts = [_has('x:plan_name', like[c]) for c in vs if c in like]
            return ('(' + ' OR '.join(parts) + ')', [], None) if parts else (None, [], 'pick a value')
        if f in ('dx', 'newdx'):
            table = DX if f == 'dx' else NEWDX
            known = [c for c in vs if c in table]
            if not known:
                return None, [], 'not in the extract: ' + ', '.join(vs) if vs else 'pick a value'
            cond = 'f.value_num = 1' if f == 'dx' else 'f.value_num <= 90'
            return '(' + ' OR '.join(_has('x:' + table[c], cond) for c in known) + ')', [], (None if len(known) == len(vs) else 'ignored: ' + ', '.join(set(vs) - set(known)))
        if f == 'lab':
            col = LABS.get(r.get('l'))
            return (*_num('x:' + col, op, v, v2), None) if col else (None, [], f"{r.get('l')} is not in the extract")
        if f == 'labage':
            col = LAB_DATES.get(r.get('l'))
            return ('NOT ' + _has('x:' + col, 'f.value_num <= ?'), [float(v)], None) if col else (None, [], f"{r.get('l')} test date is not in the extract")
        if f == 'eye':
            return 'NOT ' + _has('x:last_retinal_screen_date', 'f.value_num <= 730'), [], None
        if f == 'foot':
            return 'NOT ' + _has('x:last_foot_exam', 'f.value_num <= 365'), [], None
        if f == 'spec':
            parts = [_has('x:' + SPEC[c], 'f.value_num <= 365') for c in vs if c in SPEC]
            if 'GP' in vs: parts.append(_has('x:gp_claims_6m', 'f.value_num >= 1'))
            return ('(' + ' OR '.join(parts) + ')', [], None) if parts else (None, [], 'not in the extract')
        if f == 'atc':
            m = {'A10': _has('x:t2d_drug_classes_l12m'), 'A10A': _has('x:flag_active_insulin', 'f.value_num = 1'),
                 'C09': '(' + _has('x:flag_active_ACEinhibitor', 'f.value_num = 1') + ' OR ' + _has('x:flag_active_ARBinhibitor', 'f.value_num = 1') + ')',
                 'C07': _has('x:active_drug_classes', "f.value_text LIKE '%BETA_BLOCKER%'"), 'C03': _has('x:active_drug_classes', "f.value_text LIKE '%THIAZIDE%'")}
            parts = [m[c] for c in vs if c in m]
            return ('(' + ' OR '.join(parts) + ')', [], None) if parts else (None, [], 'medicine class not in the extract')
        if f == 'contacted':
            return ("EXISTS (SELECT 1 FROM contact c WHERE c.member_id = m.member_id AND julianday(?) - julianday(c.started_at) <= ?)", [RUN_DATE, float(v)], None)
        if f == 'optout':
            return "m.consent_status = 'declined'", [], None
        if f and f.startswith('x:'):
            ft = r.get('type')
            if ft == 'flag' or (v is None and not vs):
                return _has(f, 'f.value_num = 1'), [], None
            if vs:
                return _has(f, f"f.value_text IN ({','.join('?' * len(vs))})"), list(vs), None
            return (*_num(f, op, v, v2), None)
    except (TypeError, ValueError):
        return None, [], 'value missing'
    return None, [], 'not in the extract (' + str(f) + ')'


def base_sql(base):
    if base == 'seha':
        return _has('x:phg_share_l12m_encounters', 'f.value_num > 0'), 'members with any encounter at PHG (SEHA / SSMC)'
    if base == 'pura':
        return '0', 'PURA app users are not in this extract'
    return '1=1', 'every member in the extract'


def estimate(con, cb):
    """Live count for a builder state: base, funnel steps, per-rule counts, exclusions."""
    base_where, base_note = base_sql(cb.get('base', 'daman'))
    count = lambda where, params: con.execute(f'SELECT count(*) FROM member m WHERE {where}', params).fetchone()[0]
    B = count(base_where, [])
    inc, exc = cb.get('inc', []), cb.get('exc', [])
    steps, alone, unsupported, sql_parts, params = [], {}, [], [], []
    compiled_inc = []
    for r in inc:
        s, p, why = compile_rule(r)
        if s is None:
            unsupported.append({'id': r.get('id'), 'field': r.get('f'), 'reason': why})
            continue
        if why:
            unsupported.append({'id': r.get('id'), 'field': r.get('f'), 'reason': why})
        compiled_inc.append((r, s, p))
        alone[str(r.get('id'))] = count(f'({base_where}) AND {s}', p)
    where, wp = base_where, []
    if cb.get('logic') == 'any' and compiled_inc:
        where = f"({base_where}) AND (" + ' OR '.join(s for _, s, _ in compiled_inc) + ')'
        wp = [x for _, _, p in compiled_inc for x in p]
        steps.append({'id': 'any', 't': f'Any of {len(compiled_inc)} rules', 'n': count(where, wp)})
    else:
        for r, s, p in compiled_inc:
            where, wp = f'{where} AND {s}', wp + p
            steps.append({'id': r.get('id'), 'n': count(where, wp)})
    for r in exc:
        s, p, why = compile_rule(r)
        if s is None:
            unsupported.append({'id': r.get('id'), 'field': r.get('f'), 'reason': why, 'exclusion': True})
            continue
        where, wp = f'{where} AND NOT {s}', wp + p
        steps.append({'id': r.get('id'), 'n': count(where, wp), 'ex': True})
    n = count(where, wp)
    prof, sample = _profile(con, where, wp)
    store.log(con, 'READ', 'member_feature', f'estimate: {len(inc)} rules, {len(exc)} exclusions → {n} of {B}', 'builder', '/api/cohorts/estimate')
    return {'B': B, 'n': n, 'steps': steps, 'alone': alone, 'unsupported': unsupported, 'base_note': base_note,
            'sql': f'SELECT m.member_id FROM member m\nWHERE {where}', 'params': wp, 'profile': prof, 'sample': sample}


def members_for(con, cb):
    e = estimate(con, cb)
    return [r[0] for r in con.execute(e['sql'], e['params']).fetchall()]


def holdout(cohort_id, member_id, pct=10):
    return int(hashlib.md5(f'{cohort_id}:{member_id}'.encode()).hexdigest(), 16) % 100 < pct


def rule_rows(cohort_id, version, inc, exc):
    out = []
    for i, (r, ex) in enumerate([(r, 0) for r in inc] + [(r, 1) for r in exc]):
        out.append((f'{cohort_id}-v{version}-R{i + 1}', cohort_id, version, r.get('f'), r.get('op'), None if r.get('v') is None else str(r.get('v')),
                    None if r.get('v2') is None else str(r.get('v2')), json.dumps(r.get('vs') or []), r.get('l'), ex))
    return out


def definition(con, cohort_id):
    c = store.one(con, 'SELECT * FROM cohort WHERE cohort_id = ?', (cohort_id,))
    rs = store.rows(con, 'SELECT * FROM cohort_rule WHERE cohort_id = ? AND version = ? ORDER BY rule_id', (cohort_id, c['version']))
    to = lambda x: {'id': x['rule_id'], 'f': x['field'], 'op': x['operator'], 'v': _n(x['value']), 'v2': _n(x['value2']),
                    'vs': json.loads(x['codes'] or '[]'), 'l': x['lab']}
    return {'base': c['base'], 'logic': c['logic'], 'inc': [to(x) for x in rs if not x['is_exclusion']], 'exc': [to(x) for x in rs if x['is_exclusion']]}


def _n(v):
    if v is None:
        return None
    try:
        return float(v) if '.' in v else int(v)
    except ValueError:
        return v


def run_cohort(con, cohort_id, pct=10):
    c = store.one(con, 'SELECT * FROM cohort WHERE cohort_id = ?', (cohort_id,))
    ids = members_for(con, definition(con, cohort_id))
    con.execute('DELETE FROM cohort_member WHERE cohort_id = ?', (cohort_id,))
    con.executemany('INSERT INTO cohort_member VALUES (?,?,?,?,?)', [(cohort_id, m, c['version'], int(holdout(cohort_id, m, pct)), store.now()) for m in ids])
    con.execute('UPDATE cohort SET row_count = ? WHERE cohort_id = ?', (len(ids), cohort_id))
    return len(ids)


AGE_BANDS = [('18–39', 0, 39), ('40–54', 40, 54), ('55–64', 55, 64), ('65+', 65, 200)]
PROFILE_SQL = """SELECT m.*,
  (SELECT value_num FROM member_feature f WHERE f.member_id = m.member_id AND f.feature_key = 'x:phg_share_l12m_encounters') AS phg,
  (SELECT value_num FROM member_feature f WHERE f.member_id = m.member_id AND f.feature_key = 'x:Last_HbA1c_Value') AS a1
FROM member m WHERE {where} ORDER BY m.member_id"""


def _profile(con, where, params):
    """Who matched: age, sex, plan and PHG-network mix plus a few example members (pseudonyms)."""
    from . import views
    ms = [dict(r) for r in con.execute(PROFILE_SQL.format(where=where), params).fetchall()]
    n = len(ms) or 1
    share = lambda pred: sum(1 for m in ms if pred(m)) / n
    plan = lambda m: (m['plan_name'] or '').split(' ')[0]
    prof = {'age': [[b, share(lambda m, lo=lo, hi=hi: lo <= (m['age'] or 0) <= hi)] for b, lo, hi in AGE_BANDS],
            'sex': [['Women', share(lambda m: m['gender'] == 'F')], ['Men', share(lambda m: m['gender'] == 'M')]],
            'plan': [['Enhanced', share(lambda m: plan(m) == 'Enhanced')], ['Basic', share(lambda m: plan(m) in ('Core', 'Basic'))],
                     ['Thiqa', share(lambda m: plan(m) == 'Thiqa')], ['Other', share(lambda m: plan(m) not in ('Enhanced', 'Core', 'Basic', 'Thiqa'))]],
            'region': [['Not in the extract', 1]],
            'net': [['Any PHG encounter', share(lambda m: (m['phg'] or 0) > 0)], ['No PHG encounter', share(lambda m: not (m['phg'] or 0) > 0)]]}
    sample = []
    for m in ms[:12]:
        grp = 'arab' if (m['nationality'] or '') in views.ARAB else 'other'
        first = views.NAMES[(m['gender'] or 'M', grp)][views.h(m['member_id'] + 'f', 12)]
        last = views.LAST[grp][views.h(m['member_id'] + 'l', 10)]
        facts = ([f"HbA1c {m['a1']:.1f}%"] if m['a1'] is not None else []) + ([m['plan_name']] if m['plan_name'] else [])
        sample.append({'id': m['member_id'], 'name': f'{first} {last[0]}.', 'ini': first[0] + last[0], 'age': m['age'], 'sex': m['gender'], 'facts': facts[:3]})
    return prof, sample
