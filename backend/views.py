"""Read models: database rows → the record shapes the Studio and the portal already render."""
import hashlib
from datetime import date
from . import store
from .reference import (AS_OF, RUN_DATE, TRIG, TRIGGERS, PORTAL_CODE, CONDITIONS, PDC_COLUMNS, TIERS, SLA_DAYS, CLASS_ORDER)

GAP = (date.fromisoformat(RUN_DATE) - date.fromisoformat(AS_OF)).days   # extract dates are days before AS_OF
ARAB = {'EMIRATI', 'EGYPTIAN', 'JORDANIAN', 'LEBANESE', 'MAURITANIAN', 'MOROCCAN', 'PALESTINIAN', 'SUDANESE', 'SYRIAN', 'IRAQI', 'YEMENI',
        'OMANI', 'SAUDI', 'TUNISIAN', 'ALGERIAN', 'BAHRAINI', 'KUWAITI', 'QATARI', 'LIBYAN'}
NAMES = {  # pseudonyms: the extract is masked, the portal needs something to call people by
    ('M', 'arab'): ['Ahmed', 'Khalid', 'Saeed', 'Omar', 'Yousef', 'Hamad', 'Salem', 'Faisal', 'Majid', 'Rashid', 'Tariq', 'Nasser'],
    ('F', 'arab'): ['Fatima', 'Mariam', 'Aisha', 'Hessa', 'Noura', 'Shaikha', 'Amna', 'Latifa', 'Reem', 'Huda', 'Salma', 'Maha'],
    ('M', 'other'): ['Rajesh', 'Imran', 'Joseph', 'Vikram', 'Arjun', 'Bilal', 'Jose', 'Daniel', 'Suresh', 'Kamal', 'Ravi', 'Anil'],
    ('F', 'other'): ['Priya', 'Maria', 'Anita', 'Sana', 'Grace', 'Divya', 'Ayesha', 'Rosa', 'Meera', 'Farah', 'Lakshmi', 'Joy']}
LAST = {'arab': ['Al Mansoori', 'Al Hammadi', 'Al Kaabi', 'Haddad', 'Al Nuaimi', 'Khalil', 'Al Suwaidi', 'Mansour', 'Al Mazrouei', 'Saleh'],
        'other': ['Nair', 'Kumar', 'Sheikh', 'Santos', 'Mathew', 'Shetty', 'Khan', 'Reyes', 'Menon', 'Iqbal']}
PREF = ['Mornings', 'After 4 pm', 'Evenings after 6 pm', 'Weekdays 12–2 pm']
CLS_LABEL = {'safety': 'Safety', 'acute': 'Acute event', 'unctl': 'Uncontrolled', 'barrier': 'Barrier', 'gap': 'Care gap', 'goal': 'Goal'}


def h(s, n):
    return int(hashlib.md5(s.encode()).hexdigest(), 16) % n


def ago(days_before_asof):
    if days_before_asof is None:
        return 'not on record'
    d = int(days_before_asof) + GAP
    return f'{d} days ago' if d < 14 else f'{d // 7} wks ago' if d < 60 else f'{round(d / 30.4)} mo ago'


def features(con, mid):
    out = {}
    for k, vn, vt in con.execute('SELECT feature_key, value_num, value_text FROM member_feature WHERE member_id = ?', (mid,)).fetchall():
        out[k[2:]] = vn if vn is not None else vt
    return out


def latest_run(con):
    r = con.execute('SELECT run_id FROM ingest_run ORDER BY loaded_at DESC LIMIT 1').fetchone()
    return r[0] if r else None


def portal_record(con, m, v, a, sigs, needs, acts, contacts):
    mid, sex = m['member_id'], m['gender'] or 'M'
    grp = 'arab' if (m['nationality'] or '') in ARAB else 'other'
    first, last = NAMES[(sex, grp)][h(mid + 'f', 12)], LAST[grp][h(mid + 'l', 10)]
    conds = [{'code': code, 'short': short, 'name': name} for col, code, short, name in CONDITIONS if int(v.get(col) or 0) == 1]
    labs = []
    for k, col, dcol, unit, target, d in [('HbA1c', 'Last_HbA1c_Value', 'Last_HbA1c_Date', '%', 7, 'down'), ('eGFR', 'Last_eGFR_Value', 'Last_eGFR_Date', 'mL/min', 60, 'up'),
                                          ('UACR', 'Last_UACR_Value', 'Last_UACR_Date', 'mg/g', 30, 'down'), ('BMI', 'Last_MeasuredBMI_Value', 'Last_MeasuredBMI_Date', 'kg/m²', 30, 'down')]:
        if isinstance(v.get(col), float):
            labs.append({'k': k, 'name': {'HbA1c': 'HbA1c', 'eGFR': 'eGFR', 'UACR': 'Urine albumin (UACR)', 'BMI': 'Body mass index'}[k], 'unit': unit, 'target': target,
                         'dir': d, 'series': [round(v[col], 1)], 'last': ago(v.get(dcol))})
    meds = [{'drug': name, 'cls': cls, 'pdc': round(v[col] * 100), 'brand': False} for col, name, cls in PDC_COLUMNS if isinstance(v.get(col), float)]
    meds.sort(key=lambda x: x['pdc'])
    specs = [s for c, s in [('last_endocrinology_visit', 'Endocrinology'), ('last_cardiology_visit', 'Cardiology'), ('last_nephrology_visit', 'Nephrology'),
                            ('last_ophthalmology_visit', 'Ophthalmology'), ('last_podiatry_visit', 'Podiatry'), ('last_dietitian_visit', 'Dietetics')]
             if isinstance(v.get(c), float) and v[c] <= 365]
    fired = [s for s in sigs if s['state'] == 'fired']
    top = min(fired, key=lambda s: (CLASS_ORDER.index(TRIG[s['trigger_code']][9]), [t[0] for t in TRIGGERS].index(s['trigger_code']))) if fired else None
    open_n = [n for n in needs if n['status'] == 'open']
    last_c = contacts[0] if contacts else None
    status = 'new'
    if m['consent_status'] == 'declined':
        status = 'declined'
    elif last_c and last_c['reached'] == 0:
        status = 'noreach'
    elif m['consent_status'] == 'granted' and needs:
        status = 'enrolled'
    sbp, dbp = v.get('Last_SystolicPressure_Value'), v.get('Last_DiastolicPressure_Value')
    pdcs = [x for x in (v.get('pdc_any_t2d_noninsulin'), v.get('pdc_any_htn')) if isinstance(x, float)]
    dm, htn = int(v.get('cohort_t2d_l12m') or 0), int(v.get('cohort_htn_l12m') or 0)
    prog = 'Diabetes and hypertension' if dm and htn else 'Diabetes management' if dm else 'Hypertension management'
    a1 = v.get('Last_HbA1c_Value')
    sla = SLA_DAYS.get(a['contact_priority']) if a else None
    rec = {
        'id': 'DMN-' + mid, 'mask': mid, 'name': f'{first} {last}', 'source': 'extract', 'pseudonym': True,
        'age': m['age'], 'sex': 'Female' if sex == 'F' else 'Male', 'plan': m['plan_name'], 'nat': (m['nationality'] or '').title(),
        'lang': 'Arabic' if grp == 'arab' else 'English', 'conds': conds, 'risk': round(a['r_total'] / 23 * 100) if a else 0,
        'trigger': {'reason': TRIG[top['trigger_code']][2] if top else 'Routine review', 'detail': top['evidence'] if top else 'No open trigger in this extract',
                    'kpi': CLS_LABEL[TRIG[top['trigger_code']][9]] if top else 'Routine', 'nudge': 'sms' if sla is None else 'call', 'slaH': 24 * (sla if sla is not None else 7) or 2},
        'labs': labs, 'meds': meds, 'adm12': int(v.get('ip_admissions_l12m') or 0), 'er12': int(v.get('ed_visits_l12m') or 0),
        'cost12': round(v.get('l12m_payable_DiaborHTNrelated') or 0), 'specs': specs, 'wear': None, 'det': None, 'status': status,
        'next': (sorted(open_n, key=lambda n: n['slot'] != 'CURRENT')[0]['title'] if open_n else 'Routine check-in'),
        'phone': f'+971 5{h(mid, 9)} ••• {1000 + h(mid + "p", 9000)}', 'pref': PREF[h(mid + 'pref', 4)],
        'lastContact': ('Reached · ' + (last_c['response'] or 'call logged') if last_c['reached'] else 'No answer') if last_c else 'No prior contact',
        'cp': {'prog': prog, 'next': next((n['due_date'] for n in open_n if n['slot'] == 'CURRENT'), 'none open'), 'adh': round(min(pdcs) * 100) if pdcs else None,
               'goals': [{'k': 'HbA1c', 'from': round(a1, 1), 'now': round(a1, 1), 'target': 7, 'dir': 'down'}] if isinstance(a1, float) else []}
              if m['consent_status'] == 'granted' and needs else None,
        'live': {
            'consent': m['consent_status'], 'phg': v.get('phg_share_l12m_encounters'), 'bp': [sbp, dbp] if isinstance(sbp, float) else None,
            'sig': [{'code': PORTAL_CODE[s['trigger_code']], 'trig': s['trigger_code'], 'state': s['state'], 'evidence': s['evidence'], 'name': TRIG[s['trigger_code']][2],
                     'cls': TRIG[s['trigger_code']][9], 'campaign': s['campaign_id']} for s in sigs],
            'risk': None if not a else {'C': a['clinical'], 'M': a['comorbid'], 'K': a['kidney'], 'U': a['utilisation'], 'A': a['age_sex'], 'R': a['r_total'], 'tier': a['tier'],
                                        'tierL': a['tier_label'], 'safety': 'Priority clinical review' if a['priority_review'] else '', 'prov': bool(a['kidney_provisional']),
                                        'mh': [c['short'] for c in conds if c['short'] not in ('DM', 'HTN')], 'H': int(v.get('HbA1c_score') or 0), 'a1': a1, 'eg': v.get('Last_eGFR_Value'),
                                        'alert': a['alert'], 'priority': a['contact_priority'], 'persona': a['persona'], 'allocation': a['allocation'], 'cadence': TIERS[a['tier']][1]},
            'needs': [{'k': PORTAL_CODE[n['need_key']], 'trig': n['need_key'], 'need_id': n['need_id'], 'cls': n['class'], 't': n['title'], 'o': n['owner_role'], 'w': n['done_when'],
                       'gl': n['need_key'] + ' · ' + TRIG[n['need_key']][3], 'ev': next((s['evidence'] for s in sigs if s['trigger_code'] == n['need_key']), ''),
                       'slot': n['slot'], 'status': n['status'], 'due': n['due_date'], 'hold': n['hold_until'],
                       'action': next(({'id': x['action_id'], 'status': x['status'], 'assignee': x['assignee'], 'due': x['due_date']} for x in acts if x['need_id'] == n['need_id']), None)}
                      for n in needs],
            'actions': [{'id': x['action_id'], 'kind': x['kind'], 'title': x['title'], 'due': x['due_date'], 'assignee': x['assignee'], 'status': x['status'],
                         'need': x['need_id'], 'source': x['source']} for x in acts],
        }}
    return rec


def portal_members(con, member_ids=None, only_active=True):
    run_id = latest_run(con)
    ms = store.rows(con, 'SELECT * FROM member ORDER BY member_id')
    if member_ids:
        ms = [m for m in ms if m['member_id'] in member_ids]
    A = {r['member_id']: r for r in store.rows(con, 'SELECT * FROM assessment WHERE run_id = ?', (run_id,))}
    S, N, X, C = {}, {}, {}, {}
    for r in store.rows(con, "SELECT * FROM signal WHERE status = 'open'"):
        S.setdefault(r['member_id'], []).append(r)
    for r in store.rows(con, 'SELECT n.*, p.member_id FROM care_plan_need n JOIN care_plan p USING (care_plan_id) ORDER BY n.need_id'):
        N.setdefault(r['member_id'], []).append(r)
    for r in store.rows(con, 'SELECT * FROM action ORDER BY due_date'):
        X.setdefault(r['member_id'], []).append(r)
    for r in store.rows(con, 'SELECT * FROM contact ORDER BY started_at DESC'):
        C.setdefault(r['member_id'], []).append(r)
    out = []
    for m in ms:
        mid = m['member_id']
        if only_active and mid not in S:
            continue
        out.append(portal_record(con, m, features(con, mid), A.get(mid), S.get(mid, []), N.get(mid, []), X.get(mid, []), C.get(mid, [])))
    # rule_queue_order: safety or RED first, tier 4 → 1, campaign priority, most overdue against the contact SLA
    prio = {c: p for c, p in con.execute('SELECT campaign_id, priority FROM campaign')}
    def key(r):
        k = r['live']['risk'] or {}
        camp = min([prio.get(s['campaign'], 99) for s in r['live']['sig']] or [99])
        due = min([a['due'] for a in r['live']['actions'] if a['status'] == 'open' and a['kind'] in ('call', 'retry', 'check_in', 'escalation')] or ['9999'])
        return (0 if k.get('alert') == 'RED' or k.get('safety') else 1, -(k.get('tier') or 0), camp, due, -r['risk'])
    out.sort(key=key)
    return out


# Studio "care intelligence" screen: the portal record plus the fields ccc-logic's enrich() adds
STUDIO_ALERT = {'RED': 'urgent', 'AMBER': 'priority', 'YELLOW': 'routine', 'GREEN': 'routine'}
SLOTS = ['09:30', '10:15', '11:00', '12:30', '14:00', '15:15', '16:30', '17:30', '18:15']
ASK = {'safety': 'Could one of our clinicians call you back later today to check in?', 'acute': 'Can I book you a GP visit in the next three days?',
       'unctl': 'Would you like a review with your doctor to look at this?', 'barrier': 'Is anything making it hard to keep your medicines going? I can arrange a refill.',
       'gap': 'Shall I book this for you at an in-network clinic?', 'goal': 'Would you like to set one small goal with our nurse educator?'}


def intel_record(r, i=0):
    L = r['live']
    risk = L['risk'] or {'C': 0, 'M': 0, 'K': 0, 'U': 0, 'A': 0, 'R': 0, 'tier': 1, 'prov': True, 'alert': 'GREEN'}
    alert = STUDIO_ALERT[risk['alert']]
    pref = r['pref'].lower()
    slot = '09:00' if alert == 'urgent' else SLOTS[6 + i % 3] if ('after 4' in pref or 'evening' in pref) else SLOTS[i % 3] if 'morning' in pref else SLOTS[3 + i % 3]
    parts = r['name'].split(' ')
    open_needs = sorted([n for n in L['needs'] if n['status'] == 'open'], key=lambda n: (['CURRENT', 'NEXT', 'FUTURE', 'CLOSED'].index(n['slot']), CLASS_ORDER.index(n['cls']), [t[0] for t in TRIGGERS].index(n['trig'])))
    bp = L['bp']
    return dict(r, id=r['mask'], first=parts[0], initials=parts[0][0] + parts[-1][0], slot=slot, alert=alert, consent=L['consent'],
                condTxt=', '.join(c['name'] for c in r['conds']),
                needs=[{'id': n['trig'], 'cls': n['cls'], 'title': n['t'], 'why': n['ev'] or TRIG[n['trig']][5], 'ref': n['gl'],
                        'book': {'d': max(0, (date.fromisoformat(n['due']) - date.fromisoformat(RUN_DATE)).days) if n['due'] else 7, 'label': n['t'].split(';')[0][:28]},
                        'why2': TRIG[n['trig']][5] + '.', 'ask': ASK[n['cls']], 'slot': n['slot']} for n in open_needs],
                risk2={'R': risk['R'], 'tier': risk['tier'], 'prov': risk['prov'], 'parts': [['Clinical', risk['C'], 5], ['Comorbidity', risk['M'], 6], ['Kidney', risk['K'], 5],
                                                                                         ['Hospital use', risk['U'], 5], ['Age and sex', risk['A'], 2]]},
                det={'band': 'Not in extract', 'score': '—', 'pred': risk.get('persona') or '—', 'win': '—', 'drivers': ['No wearable feed in the claims extract']},
                wear={'dev': 'None', 'bp': [int(bp[0]), int(bp[1] or 0)] if bp else ['—', '—'], 'steps': 0, 'sleep': '—', 'sync': 'from claims extract'})
