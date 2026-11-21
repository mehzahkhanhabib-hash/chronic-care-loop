import os, sys, json, datetime, decimal
sys.path[:0]=['two-day-build/api','two-day-build/tests','.']
os.environ.update(CCL_DIALECT='mysql', S2_PORT='3307', S2_PASSWORD='pw')
import test_kit, server
con=test_kit.fresh(); load,k0=test_kit.build(con)
R=lambda s,*a: server.rows(con,s,a or None)
M='m26'; S={}
S['raw']=R("""SELECT member_id, age, gender, language, has_t2d, has_htn, last_hba1c_value, last_hba1c_date2, last_systolicpressure_value, last_diastolicpressure_value,
  last_egfr_value, last_uacr_value, pdc_any_t2d_noninsulin, pdc_any_htn, ip_admissions_l12m, last_ip_discharge_date, last_retinal_screen_date, last_foot_exam, last_dietitian_visit,
  clinical_score, comorbid_complication_score, kidney_score, utilization_score, age_sex_score FROM member WHERE member_id=%s""",M)
S['signals']=R("SELECT s.trigger_code, t.name, t.class, t.dm_module, s.state, s.evidence FROM member_signal s JOIN rule_trigger t USING (trigger_code) WHERE member_id=%s ORDER BY t.class_order, t.trigger_order",M)
S['summary0']=R("SELECT * FROM v_dm_member_summary WHERE member_id=%s",M)
S['needs0']=R("SELECT trigger_code, need, class, slot, need_status, gap_state, due_date, action_id, action_title, owner_role, done_when FROM v_care_plan WHERE member_id=%s ORDER BY FIELD(slot,'CURRENT','NEXT','FUTURE','CLOSED'), due_date",M)
S['actions0']=R("SELECT action_id, kind, title, due_date, assignee, status FROM action WHERE member_id=%s ORDER BY action_id",M)
S['worklist']=R("SELECT * FROM v_worklist WHERE member_id=%s",M)
S['nurse_list']=R("SELECT nurse_rank, member_id, priority, alert, tier, action_title, due_by, language, list_status FROM v_worklist WHERE nurse_id=%s ORDER BY nurse_rank", S['worklist'][0]['nurse_id'])
nurse=S['worklist'][0]['nurse_id']
steps=[]
def do(aid, result, **kw):
    r=server.outcome(con,{},dict(member_id=M,result=result,nurse_id=nurse,**kw),aid)
    steps.append({'action_id':aid,'result':result,**kw,'new':[{k:a[k] for k in ('action_id','kind','title','due_date','parent_action_id')} for a in r['new_actions']]})
call=[a for a in S['actions0'] if a['kind']=='call'][0]['action_id']
do(call,'reached',reached=1,consent='granted',notes='Spoke in Arabic; consent recorded')
cps=[a for a in R("SELECT action_id, trigger_code, title FROM action WHERE member_id=%s AND kind='care_plan' AND status='open' ORDER BY action_id",M)]
do(cps[0]['action_id'],'agreed',notes='GP visit booked for Monday')
do(cps[1]['action_id'],'done',notes='Clinician reviewed; plan updated')
do(cps[2]['action_id'],'declined',notes='Prefers to wait')
S['steps']=steps
S['chain']=R("SELECT action_id, kind, title, status, due_date, parent_action_id, came_from, because_outcome FROM v_action_chain WHERE member_id=%s ORDER BY action_id",M)
S['needs1']=R("SELECT trigger_code, need, class, slot, need_status, gap_state, due_date, hold_until, action_id, action_status, last_outcome FROM v_care_plan WHERE member_id=%s ORDER BY FIELD(slot,'CURRENT','NEXT','FUTURE','CLOSED'), due_date",M)
S['dm']=R("SELECT programme, module_code, module, target, latest, status, open_needs, slots, gap_states, next_due, next_action, next_action_due, owner FROM v_dm_member_module WHERE member_id=%s ORDER BY sort_order",M)
S['summary1']=R("SELECT * FROM v_dm_member_summary WHERE member_id=%s",M)
S['programme']=R("SELECT * FROM v_dm_programme ORDER BY sort_order")
S['kpis']=R("SELECT * FROM v_kpis")[0]
S['kpis0']=k0
S['triggers']=R("SELECT t.trigger_code, t.name, SUM(s.state='fired') fired, SUM(s.state='cannot_tell') cannot_tell FROM rule_trigger t LEFT JOIN member_signal s USING (trigger_code) GROUP BY t.trigger_code, t.name, t.class_order, t.trigger_order ORDER BY t.class_order, t.trigger_order")
S['team']=R("SELECT nurse_id, nurse_name, COUNT(*) n, SUM(list_status='today') today FROM v_worklist GROUP BY nurse_id, nurse_name")
def enc(o):
    if isinstance(o,(datetime.date,datetime.datetime)): return o.isoformat()[:10]
    if isinstance(o,decimal.Decimal): return float(o)
    return str(o)
json.dump(S,open(sys.argv[1],'w'),default=enc,indent=1)
print('steps', json.dumps(steps,default=enc)[:1500])
print('dm', json.dumps(S['dm'],default=enc)[:1200])
