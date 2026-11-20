"""Nightly run (rulebook §2–§5): outcomes → cohorts → campaign members → assessment → signals → care plans → actions.

  python3 -m backend.engine            # seed (if empty) + run
"""
import json, sys
from datetime import date, timedelta
from . import store, cohorts
from .reference import RUN_DATE, TRIGGERS, TRIG, CLASS_ORDER, CLASS_DUE_DAYS, TIERS, SLA_DAYS, NURSES, RULES



def day(offset=0, base=RUN_DATE):
    return (date.fromisoformat(base) + timedelta(days=offset)).isoformat()


# ───────────── seed: builder cohorts + campaigns (same as the Studio's seed list) ─────────────
OPTOUT = [{'f': 'optout'}]
SEED_COHORTS = [   # same definitions as the Studio's seed library, plus one programme-wide cohort
    ('COH-0101', 'Diabetes · above goal', [{'f': 'dx', 'vs': ['E11']}, {'f': 'lab', 'l': 'hba1c', 'op': '≥', 'v': 8}], OPTOUT),
    ('COH-0102', 'Hypertension · drifting from care', [{'f': 'dx', 'vs': ['I10']}, {'f': 'nofu', 'op': '≥', 'v': 180}], OPTOUT),
    ('COH-0103', 'Post-discharge chronic', [{'f': 'ncc', 'op': '≥', 'v': 1}, {'f': 'ip', 'op': '≥', 'v': 1}], OPTOUT),
    ('COH-0104', 'Diabetes · eye and foot gaps', [{'f': 'dx', 'vs': ['E11']}, {'f': 'eye'}, {'f': 'foot'}], OPTOUT),
    ('COH-0105', 'Chronic care loop · T2D or hypertension', [{'f': 'dx', 'vs': ['E11', 'I10']}], OPTOUT),
]
SEED_CAMPAIGNS = [  # id, name, goal, mode, triggers, channels, nurses, calls/day, status, priority, include, exclude, holdout, start, weeks
    ('CMP-0101', 'Diabetes control', 'Bring HbA1c to goal', 'automated', None, 'Voice', 8, 25, 'Live', 1, ['COH-0101'], [], 10, '2026-11-16', 8),
    ('CMP-0102', 'Back into care', 'Re-engage members without follow-up', 'business', ['Trig9', 'Trig4'], 'Voice, WhatsApp', 6, 25, 'Scheduled', 2, ['COH-0102', 'COH-0103'], [], 10, '2026-12-01', 6),
    ('CMP-0103', 'Eye and foot catch-up', 'Close annual screening gaps', 'business', ['Trig12', 'Trig13'], 'WhatsApp, SMS', 3, 30, 'Draft', 3, ['COH-0104'], ['COH-0101'], 10, '2027-01-04', 6),
    ('CMP-0104', 'Chronic care loop', 'Every rulebook trigger for T2D and hypertension members', 'automated', None, 'Voice, WhatsApp', 6, 25, 'Live', 4, ['COH-0105'], [], 10, '2026-11-16', 12),
]


def save_cohort(con, cid, name, inc, exc, base='daman', logic='all', refresh='Nightly', owner='U-0201', definition_type='builder'):
    old = store.one(con, 'SELECT version FROM cohort WHERE cohort_id = ?', (cid,))
    ver = (old['version'] + 1) if old else 1
    for i, r in enumerate(inc + exc):
        r.setdefault('id', i + 1)
    if old:
        con.execute('UPDATE cohort SET version=?, name=?, base=?, logic=?, refresh=? WHERE cohort_id=?', (ver, name, base, logic, refresh, cid))
    else:
        con.execute('INSERT INTO cohort VALUES (?,?,?,?,?,?,?,?,?,?)', (cid, ver, name, base, logic, refresh, definition_type, None, owner, store.now()))
    con.executemany('INSERT INTO cohort_rule VALUES (?,?,?,?,?,?,?,?,?,?)', cohorts.rule_rows(cid, ver, inc, exc))
    n = cohorts.run_cohort(con, cid)
    store.log(con, 'WRITE', 'cohort', f'{cid} v{ver} "{name}" → {n} members', owner, '/api/cohorts')
    return {'cohort_id': cid, 'version': ver, 'row_count': n}


def save_campaign(con, cid, name, goal, mode, trig, channels, nurses, cpd, status, prio, inc, exc, holdout=10, start=RUN_DATE, weeks=12):
    con.execute('INSERT OR REPLACE INTO campaign VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (cid, name, goal, mode, json.dumps(trig) if trig else None, channels, nurses, cpd, holdout, start, weeks, prio, status, store.now()))
    con.execute('DELETE FROM campaign_cohort WHERE campaign_id = ?', (cid,))
    con.executemany('INSERT INTO campaign_cohort VALUES (?,?,?)', [(cid, c, 'include') for c in inc] + [(cid, c, 'exclude') for c in exc])
    store.log(con, 'WRITE', 'campaign', f'{cid} "{name}" ({status})', 'U-0201', '/api/campaigns')
    return cid


def seed(con):
    if con.execute('SELECT count(*) FROM cohort').fetchone()[0]:
        return False
    for cid, name, inc, exc in SEED_COHORTS:
        save_cohort(con, cid, name, inc, exc)
    for c in SEED_CAMPAIGNS:
        save_campaign(con, *c)
    # demo consent states: ~70% already consented (PURA app or a recorded call), the rest are asked on the first call
    for (mid,) in con.execute("SELECT member_id FROM member WHERE consent_status = 'pending'").fetchall():
        if cohorts.holdout('consent', mid, 70):
            con.execute("UPDATE member SET consent_status = 'granted' WHERE member_id = ?", (mid,))
    con.commit()
    return True


# ───────────── step 1: outcomes recorded in the portal since the last run ─────────────
def process_outcomes(con):
    """Apply unprocessed outcomes with the rule_writeback table (rulebook §5)."""
    done, touched = 0, set()
    WB = RULES.writeback
    for o in store.rows(con, 'SELECT * FROM outcome WHERE processed_at IS NULL ORDER BY recorded_at'):
        res, need, act, mid = o['result'], o['need_id'], o['action_id'], o['member_id']
        rule = WB.get(res, {})
        if need and rule:
            sets, args = [], []
            if rule['need_status']: sets.append('status=?'); args.append(rule['need_status'])
            if rule['need_slot']: sets.append('slot=?'); args.append(rule['need_slot'])
            if rule['gap_state']: sets.append('gap_state=?'); args.append(rule['gap_state'])
            if rule['hold_days']: sets.append('hold_until=?'); args.append(day(int(rule['hold_days'])))
            if sets:
                con.execute(f"UPDATE care_plan_need SET {', '.join(sets)} WHERE need_id=?", (*args, need))
            if not act:
                r = con.execute("SELECT action_id FROM action WHERE need_id=? AND kind='care_plan'", (need,)).fetchone()
                act = r and r[0]
        if act and rule.get('action_status') and rule['action_status'] != 'open':
            con.execute('UPDATE action SET status=?, closed_at=? WHERE action_id=?', (rule['action_status'], o['recorded_at'], act))
        if res == 'agreed' and act:
            con.execute('UPDATE action SET agreed=1 WHERE action_id=?', (act,))
        elif res in ('consent_granted', 'consent_declined'):
            con.execute('UPDATE member SET consent_status=? WHERE member_id=?', (res.split('_')[1], mid))
        elif res == 'not_reached':
            cap, after = int(rule.get('max_attempts') or 3), int(rule.get('retry_after_days') or 1)
            tries = con.execute("SELECT count(*) FROM outcome WHERE member_id=? AND result='not_reached'", (mid,)).fetchone()[0]
            if tries < cap and not con.execute("SELECT 1 FROM action WHERE member_id=? AND kind='retry' AND status='open'", (mid,)).fetchone():
                con.execute('INSERT INTO action VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (store.next_id(con, 'action', 'action_id', 'ACT-', 5), mid, None, 'retry',
                            f'Retry call (attempt {tries + 1} of {cap})', 0, day(after), o['recorded_by'], 'open', None, 'call', store.now(), None))
            elif tries >= cap:
                p1 = con.execute("SELECT 1 FROM assessment WHERE member_id=? AND contact_priority='P1' ORDER BY run_id DESC LIMIT 1", (mid,)).fetchone()
                if p1 and not con.execute("SELECT 1 FROM action WHERE member_id=? AND kind='escalation' AND status='open'", (mid,)).fetchone():
                    con.execute('INSERT INTO action VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (store.next_id(con, 'action', 'action_id', 'ACT-', 5), mid, None, 'escalation',
                                f'P1 member not reached after {cap} attempts: clinical lead to decide', 0, day(0), 'U-0310', 'open', None, 'call', store.now(), None))
        con.execute('UPDATE outcome SET processed_at=? WHERE outcome_id=?', (store.now(), o['outcome_id']))
        if need and rule and int(rule.get('promote_next') or 0):
            touched.add(need)
        done += 1
    for need in touched:   # promote the next need into CURRENT
        r = con.execute('SELECT n.care_plan_id, p.member_id FROM care_plan_need n JOIN care_plan p USING (care_plan_id) WHERE n.need_id=?', (need,)).fetchone()
        if r:
            reslot(con, r[0], r[1])
    return done


def record(con, ev, actor='U-0142'):
    """Portal write-back. ev = {member_id, kind: need|call|consent, need (trigger code), result, reached, consent, response, notes, campaign_id}.
    Applied straight away (the nurse sees the next need promoted); the nightly run re-scores on top."""
    mid = ev['member_id']
    if not store.one(con, 'SELECT 1 AS x FROM member WHERE member_id=?', (mid,)):
        raise KeyError(mid)
    user = ev.get('user') or actor
    contact_id = None
    if ev.get('kind') == 'call' or 'reached' in ev:
        contact_id = store.next_id(con, 'contact', 'contact_id', 'C-', 5)
        con.execute('INSERT INTO contact VALUES (?,?,?,?,?,?,?,?,?,?)', (contact_id, mid, ev.get('campaign_id'), user, store.now(), store.now(),
                    int(bool(ev.get('reached', True))), ev.get('consent'), ev.get('response'), ev.get('notes')))
    results = []
    if ev.get('kind') == 'need' and ev.get('need'):
        n = store.one(con, 'SELECT n.need_id FROM care_plan_need n JOIN care_plan p USING (care_plan_id) WHERE p.member_id=? AND n.need_key=?', (mid, ev['need']))
        if not n:
            raise KeyError(ev['need'])
        act = store.one(con, "SELECT action_id FROM action WHERE need_id=? AND kind='care_plan'", (n['need_id'],))
        results.append((ev['result'], n['need_id'], act and act['action_id']))
    if ev.get('consent') in ('granted', 'declined'):
        results.append(('consent_' + ev['consent'], None, None))
    if 'reached' in ev and not ev['reached']:
        results.append(('not_reached', None, None))
    if contact_id and ev.get('reached'):   # a reached call closes the open worklist call
        w = store.one(con, "SELECT action_id FROM action WHERE member_id=? AND kind IN ('call','retry','check_in') AND status='open' ORDER BY due_date LIMIT 1", (mid,))
        if w:
            results.append(('done', None, w['action_id']))
    ids = []
    for res, need, act in results:
        oid = store.next_id(con, 'outcome', 'outcome_id', 'O-', 6)
        con.execute('INSERT INTO outcome VALUES (?,?,?,?,?,?,?,?,?)', (oid, contact_id, mid, need, act, res, user, store.now(), None))
        ids.append(oid)
    process_outcomes(con)
    store.log(con, 'WRITE', 'outcome', f'{mid}: ' + ', '.join(r[0] for r in results), user, '/api/portal/event')
    con.commit()
    return {'contact_id': contact_id, 'outcomes': ids}


# ───────────── step 3: who each live campaign reaches ─────────────
def campaign_members(con, campaign_id):
    """Include cohorts − exclude cohorts − 10% holdout − extract Exclusion = 1 − consent declined (G1, G2)."""
    return [r[0] for r in con.execute('''
        SELECT DISTINCT cm.member_id FROM campaign_cohort cc JOIN cohort_member cm ON cm.cohort_id = cc.cohort_id
        JOIN member m ON m.member_id = cm.member_id
        WHERE cc.campaign_id = ? AND cc.role = 'include' AND cm.holdout = 0 AND m.consent_status <> 'declined'
          AND NOT EXISTS (SELECT 1 FROM campaign_cohort x JOIN cohort_member xm ON xm.cohort_id = x.cohort_id
                          WHERE x.campaign_id = cc.campaign_id AND x.role = 'exclude' AND xm.member_id = cm.member_id)
          AND NOT EXISTS (SELECT 1 FROM member_feature f WHERE f.member_id = cm.member_id AND f.feature_key = 'x:Exclusion' AND f.value_num = 1)''',
        (campaign_id,)).fetchall()]


def features(con, member_id):
    return {r[0][2:]: (r[1] if r[1] is not None else r[2]) for r in
            con.execute('SELECT feature_key, value_num, value_text FROM member_feature WHERE member_id = ?', (member_id,)).fetchall()}


# ───────────── step 4: assessment (rulebook §2) ─────────────
def assess(v, fired_codes=()):
    """Risk parts come from the extract's score columns; tier, alert colour and contact priority from the rule tables."""
    g = lambda c: int(v.get(c) or 0)
    parts = dict(clinical=g('Clinical_score'), comorbid=g('Comorbid_complication_score'), kidney=g('Kidney_score'),
                 utilisation=g('Utilization_score'), age_sex=g('Age_sex_score'))
    R = sum(parts.values())
    tier = RULES.tier(R)
    prov = int(v.get('Last_eGFR_Value') is None and v.get('Last_UACR_Value') is None)   # K from documented CKD stage only
    review = int(g('Priority_clinical_review') == 1 or g('flag_dka_l12m') == 1 or g('flag_dm_hypoglycaemia_l12m') == 1)
    alert = RULES.alert(v, list(fired_codes))
    return dict(parts, kidney_provisional=prov, r_total=R, tier=tier, tier_label=TIERS[tier][0], persona=v.get('Persona'),
                allocation='PREVHEALTH' if tier >= 3 else 'PURECS', priority_review=review, excluded=g('Exclusion'),
                alert=alert, contact_priority=RULES.contact_priority(alert, set(fired_codes)))


# ───────────── step 5: signals (rulebook §3) ─────────────
def fired(v):
    """[(code, state, evidence)]: rule_condition rows evaluated against one member's extract values."""
    out = []
    for code, state, conds in RULES.fired(v):
        if state == 'cannot_tell':
            out.append((code, state, (conds[-1].get('note') if conds else None) or 'Value missing in the extract'))
        elif code in EVIDENCE_FROM_FLAG and RULES.triggers and conds and conds[0]['column_name'].startswith('Trig'):
            out.append((code, state, _evidence(code, v)))
        else:
            out.append((code, state, _explain(conds, v)))
    return out


def _explain(conds, v):
    parts = []
    for c in conds or []:
        x = v.get(c['column_name'])
        if c['column_name'].startswith('cohort_'):
            continue
        shown = 'none on record' if x is None else (f'{x:g}' if isinstance(x, float) else str(x))
        parts.append(f"{c['column_name']} = {shown} ({c['op']} {c['value'] or ''})".replace(' ()', ''))
    return '; '.join(parts) or 'Rule matched'


EVIDENCE_FROM_FLAG = {'Trig1', 'Trig2', 'Trig3', 'Trig4', 'Trig5', 'Trig6', 'Trig7', 'Trig8', 'Trig9', 'Trig10', 'Trig11', 'Trig12', 'Trig13'}


def _evidence(code, v):
    f = lambda c, d=1: (f'{v[c]:.{d}f}' if isinstance(v.get(c), float) else str(v.get(c))) if v.get(c) is not None else '—'
    ago = lambda c: f'{int(v[c])} days ago' if isinstance(v.get(c), float) else 'none on record'
    return {'Trig1': f'HbA1c {f("Last_HbA1c_Value")}%', 'Trig2': f'BP {f("Last_SystolicPressure_Value", 0)}/{f("Last_DiastolicPressure_Value", 0)}; ACEi/ARB gap',
            'Trig3': 'Hypo in 90 days' if int(v.get('flag_dm_hypoglycaemia_last90days') or 0) else 'Insulin / SU without rescue glucagon',
            'Trig4': f'Discharged {ago("last_ip_discharge_date")}', 'Trig5': f'eGFR {f("Last_eGFR_Value", 0)}, UACR {f("Last_UACR_Value", 0)}; last eGFR test: {ago("last_egfr_test_date")}',
            'Trig6': f'Last HbA1c test: {ago("last_hba1c_date2")}', 'Trig7': f'Last potassium test: {ago("last_potassium_date")}',
            'Trig8': f'Last dietitian visit: {ago("last_dietitian_visit")}', 'Trig9': f'PDC {f("pdc_any_t2d_noninsulin", 2)} (DM) / {f("pdc_any_htn", 2)} (BP)',
            'Trig10': 'First claim in the last 180 days', 'Trig11': f'Last lipid panel: {ago("last_lipid_panel_date")}',
            'Trig12': f'Last retinal screen: {ago("last_retinal_screen_date")}', 'Trig13': f'Last podiatry visit: {ago("last_podiatry_visit")}'}.get(code, '')


def reslot(con, cpid, mid, nurse=None):
    """Rulebook §4: CURRENT = top 3 open needs by class order, NEXT = 4–6, FUTURE = rest; one care-plan action per CURRENT need (G7)."""
    open_needs = store.rows(con, "SELECT need_id, class, need_key FROM care_plan_need WHERE care_plan_id=? AND status='open'", (cpid,))
    open_needs.sort(key=lambda n: (CLASS_ORDER.index(n['class']), [t[0] for t in TRIGGERS].index(n['need_key'])))
    for i, n in enumerate(open_needs):
        con.execute('UPDATE care_plan_need SET slot=? WHERE need_id=?', ('CURRENT' if i < 3 else 'NEXT' if i < 6 else 'FUTURE', n['need_id']))
    con.execute("UPDATE care_plan_need SET slot='CLOSED' WHERE care_plan_id=? AND status <> 'open'", (cpid,))
    if nurse is None:   # keep the member with the nurse who already has their actions
        r = con.execute("SELECT assignee FROM action WHERE member_id=? AND assignee IS NOT NULL ORDER BY created_at DESC LIMIT 1", (mid,)).fetchone()
        nurse = r[0] if r else NURSES[0]
    made = 0
    for n in store.rows(con, "SELECT * FROM care_plan_need WHERE care_plan_id=? AND slot='CURRENT' AND status='open'", (cpid,)):
        if not con.execute("SELECT 1 FROM action WHERE need_id=? AND kind='care_plan'", (n['need_id'],)).fetchone():
            ra = RULES.actions.get(n['need_key'])
            con.execute('INSERT INTO action VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (f'A-{n["need_id"][2:]}', mid, n['need_id'], 'care_plan', n['title'], 0,
                        n['due_date'], nurse, 'open', None, 'care_plan', store.now(), ra and ra['action_code']))
            made += 1
        else:   # a re-opened need (hold expired) re-opens its action
            con.execute("UPDATE action SET status='open', closed_at=NULL, due_date=? WHERE need_id=? AND kind='care_plan' AND status<>'open'", (n['due_date'], n['need_id']))
    return made


def run(con=None, actor='scheduler'):
    con = con or store.connect()
    with store._lock:
        run_row = store.one(con, 'SELECT * FROM ingest_run ORDER BY loaded_at DESC LIMIT 1')
        if not run_row:
            raise RuntimeError('Load an extract first: python3 -m backend.ingest <file>')
        run_id = run_row['run_id']
        seed(con)
        stats = {'run_id': run_id, 'outcomes': process_outcomes(con)}

        # step 2: refresh every cohort (rules re-evaluated against the latest extract)
        stats['cohorts'] = {c: cohorts.run_cohort(con, c) for (c,) in con.execute('SELECT cohort_id FROM cohort').fetchall()}

        # step 3: campaign membership; a member belongs to the highest-priority live campaign (G3: one owner)
        owner = {}
        for c in store.rows(con, "SELECT * FROM campaign WHERE status = 'Live' ORDER BY priority"):
            keep = set(json.loads(c['triggers_json'])) if c['trigger_mode'] == 'business' and c['triggers_json'] else None
            for m in campaign_members(con, c['campaign_id']):
                owner.setdefault(m, (c['campaign_id'], keep))
        stats['campaign_members'] = len(owner)

        # step 4: assessment for everyone in the extract
        con.execute('DELETE FROM assessment WHERE run_id = ?', (run_id,))
        feats = {}
        for (mid,) in con.execute('SELECT member_id FROM member').fetchall():
            feats[mid] = v = features(con, mid)
            a = assess(v, [c for c, st, _ in fired(v) if st == 'fired'])
            con.execute('INSERT INTO assessment VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (mid, run_id, a['clinical'], a['comorbid'], a['kidney'], a['utilisation'],
                        a['age_sex'], a['kidney_provisional'], a['r_total'], a['tier'], a['tier_label'], a['persona'], a['allocation'], a['priority_review'],
                        a['excluded'], a['alert'], a['contact_priority']))

        # step 5–6: signals → care plan needs
        n_sig = n_need = n_act = 0
        con.execute("UPDATE signal SET status = 'closed' WHERE status = 'open'")
        load = {u: con.execute("SELECT count(*) FROM action WHERE assignee=? AND status='open'", (u,)).fetchone()[0] for u in NURSES}
        for mid, (cmp, keep) in sorted(owner.items()):
            v = feats[mid]
            sigs = [s for s in fired(v) if keep is None or s[0] in keep]
            if not sigs:
                continue
            a = store.one(con, 'SELECT * FROM assessment WHERE member_id=? AND run_id=?', (mid, run_id))
            dm, htn = int(v.get('cohort_t2d_l12m') or 0), int(v.get('cohort_htn_l12m') or 0)
            pathway = 'DM + HTN' if dm and htn else 'DM' if dm else 'HTN'
            cp = store.one(con, 'SELECT * FROM care_plan WHERE member_id=?', (mid,))
            if cp:
                con.execute('UPDATE care_plan SET pathway=?, tier=?, cadence=?, updated_at=? WHERE care_plan_id=?', (pathway, a['tier'], TIERS[a['tier']][1], store.now(), cp['care_plan_id']))
                cpid = cp['care_plan_id']
            else:
                cpid = 'CP-' + mid
                con.execute('INSERT INTO care_plan VALUES (?,?,?,?,?,?,?,?)', (cpid, mid, pathway, a['tier'], TIERS[a['tier']][1], 'active', store.now(), store.now()))
            fired_codes = set()
            for code, state, ev in sigs:
                sid = f'SIG-{mid}-{code}'
                con.execute('INSERT OR REPLACE INTO signal VALUES (?,?,?,?,?,?,?,?)', (sid, mid, cmp, run_id, code, state, ev, 'open'))
                n_sig += 1
                if state != 'fired':
                    continue
                fired_codes.add(code)
                t = TRIG[code]
                need = store.one(con, 'SELECT * FROM care_plan_need WHERE care_plan_id=? AND need_key=?', (cpid, code))
                if not need:
                    con.execute('INSERT INTO care_plan_need VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (f'N-{mid}-{code}', cpid, sid, code, t[9], 'FUTURE', t[6], t[7], t[8],
                                day(CLASS_DUE_DAYS[t[9]]), 'open', None, 'Potential'))
                    n_need += 1
                elif need['status'] == 'declined' and (need['hold_until'] or '') <= RUN_DATE:
                    con.execute("UPDATE care_plan_need SET status='open', hold_until=NULL, gap_state='Potential', signal_id=?, due_date=? WHERE need_id=?", (sid, day(CLASS_DUE_DAYS[t[9]]), need['need_id']))
                elif need['status'] == 'open':
                    con.execute('UPDATE care_plan_need SET signal_id=? WHERE need_id=?', (sid, need['need_id']))
                # done needs stay done (G9: verified completions are not reopened by the same extract)
            # open needs whose trigger no longer fires were closed in claims
            gone = f"care_plan_id=? AND need_key NOT IN ({','.join('?' * len(fired_codes)) or "''"})"
            con.execute(f"UPDATE care_plan_need SET status='done', slot='CLOSED', gap_state='Closed' WHERE status='open' AND {gone}", (cpid, *fired_codes))
            con.execute(f"UPDATE care_plan_need SET gap_state='Closed' WHERE status='done' AND gap_state='Reported' AND {gone}", (cpid, *fired_codes))
            con.execute(f"UPDATE action SET status='done', closed_at=? WHERE kind='care_plan' AND status='open' AND need_id IN (SELECT need_id FROM care_plan_need WHERE gap_state='Closed' AND {gone})",
                        (store.now(), cpid, *fired_codes))
            nurse = min(NURSES, key=lambda u: load[u])
            made = reslot(con, cpid, mid, nurse)
            recent = con.execute("SELECT 1 FROM contact WHERE member_id=? AND reached=1 AND julianday('now') - julianday(started_at) < 14", (mid,)).fetchone()
            if not recent and not con.execute("SELECT 1 FROM action WHERE member_id=? AND kind IN ('call','check_in','retry') AND status='open'", (mid,)).fetchone():
                sla = SLA_DAYS[a['contact_priority']]
                kind, title = ('check_in', 'Digital nudge (app / WhatsApp)') if sla is None else ('call', f'{a["contact_priority"]} outreach call')
                n_prev = con.execute("SELECT count(*) FROM action WHERE member_id=? AND source='worklist'", (mid,)).fetchone()[0]
                con.execute('INSERT INTO action VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (f'W-{mid}-{n_prev + 1}', mid, None, kind, title, 0, day(sla) if sla is not None else day(7),
                            nurse, 'open', None, 'worklist', store.now(), None))
                made += 1
            load[nurse] += made; n_act += made
        stats.update(signals=n_sig, new_needs=n_need, new_actions=n_act,
                     care_plans=con.execute('SELECT count(*) FROM care_plan').fetchone()[0])
        store.log(con, 'WRITE', 'assessment', f'{len(feats)} members assessed', actor, '/api/runs/nightly')
        store.log(con, 'WRITE', 'signal', f'{n_sig} open signals', actor, '/api/runs/nightly')
        store.log(con, 'WRITE', 'care_plan_need', f'{n_need} new needs', actor, '/api/runs/nightly')
        store.log(con, 'WRITE', 'action', f'{n_act} new actions', actor, '/api/runs/nightly')
        con.commit()
    return stats


if __name__ == '__main__':
    print(json.dumps(run(), indent=1))
