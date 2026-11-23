#!/usr/bin/env python3
"""250_members_longitudinal_data.xlsx → rule_source_column.csv, column_catalogue_250.csv, CCC_Rulebook_Tables_250_longitudinal.xlsx,
sql/01b_member_longitudinal.sql and data/raw/member_features_250_longitudinal.tsv.
Run from a folder that holds long.xlsx and cols.json (see the first block of the script for how cols.json is made)."""
import json, csv, re, os, datetime, collections
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
REPO='/home/user/chronic-care-loop'
J=json.load(open('cols.json')); HDR=J['hdr']; T=J['types']
def col(c): return {'mask_id':'member_id','# of triggers':'n_triggers','Risk Premium':'risk_premium','eGFR + UACR points':'egfr_uacr_points','GWP':'gwp'}.get(c, re.sub(r'[^a-z0-9_]','_',c.lower()))

# ── 1. rule input → source column, from the rulebook ──
M=[]  # (rule_table, rule_key, input, columns, note)
def add(t,k,i,cols,note=''): M.append((t,k,i,cols,note))
# §2 risk score
add('rule_risk_band','C','HbA1c band (T2D only)','Last_HbA1c_Value; HbA1c_score','HbA1c_score is the band already computed in the extract')
add('rule_risk_band','C','HTN diagnosis +2','cohort_htn_l12m; htn_identified_by')
add('rule_risk_band','C','Hypoglycaemia in 12 months ×2','flag_dm_hypoglycaemia_l12m; flag_dm_hypoglycaemia_last90days')
add('rule_risk_band','C','DKA in 12 months ×3','flag_dka_l12m; flag_dm_hyperglycaemic_crisis_l12m')
add('rule_risk_band','C','C total (cap 5)','Clinical_score','Computed in the extract; the kit trusts it')
add('rule_risk_band','M','Dyslipidaemia 1','flag_dyslipidemia_l12m; first_dyslipidemia_date')
add('rule_risk_band','M','BMI ≥ 30 1','flag_obesity; Last_MeasuredBMI_Value')
add('rule_risk_band','M','Smoking 1','flag_current_smoker_l12m; flag_former_smoker_code; last_smoking_evidence_date')
add('rule_risk_band','M','CAD / MI 3','flag_cad_mi_l12m; flag_ischemic_heart_disease_l12m; flag_mi_l12m')
add('rule_risk_band','M','Stroke / TIA 3','flag_stroke_tia_l12m; flag_stroke_l12m')
add('rule_risk_band','M','Heart failure 3','flag_heart_failure_l12m')
add('rule_risk_band','M','PAD 3','flag_pad_l12m; flag_dm_circulatory_l12m')
add('rule_risk_band','M','Retinopathy 2','flag_dm_retinopathy_l12m; flag_dm_eye_l12m')
add('rule_risk_band','M','Neuropathy 1','flag_peripheral_neuropathy_l12m; flag_dm_neuropathy_l12m')
add('rule_risk_band','M','Foot ulcer 4','flag_dm_foot_ulcer_l12m; flag_dm_foot_l12m')
add('rule_risk_band','M','Major amputation 4','flag_major_amputation_l12m; flag_amputation_l12m')
add('rule_risk_band','M','M total (cap 6)','Comorbid_complication_score; dm_complications; dm_complication_count')
add('rule_risk_band','K','eGFR band','Last_eGFR_Value; Last_eGFR_Date')
add('rule_risk_band','K','UACR band','Last_UACR_Value; Last_UACR_Date')
add('rule_risk_band','K','< 15 or dialysis → 4','flag_dialysis_l12m; flag_kidney_failure_l12m')
add('rule_risk_band','K','CKD-stage fallback (provisional)','ckd_stage_l12m; flag_ckd_l12m; flag_any_kidney_disease_l12m')
add('rule_risk_band','K','K total (cap 5)','eGFR + UACR points; Kidney_score')
add('rule_risk_band','U','ED visits not admitted 0–3','ed_visits_l12m; er_visits_6m')
add('rule_risk_band','U','Unplanned admissions 1 → 3, ≥ 2 → 4','ip_admissions_l12m; ip_admissions_6m')
add('rule_risk_band','U','U total (cap 5)','Utilization_score')
add('rule_risk_band','A','Age and sex band','AGE; GENDER')
add('rule_risk_band','A','A total (cap 2)','Age_sex_score')
add('rule_tier','R','R = C + M + K + U + A','Total_risk_Score')
add('rule_tier','tier','Tier 1–4 from R','Risk_tier','Extract labels are reverse-numbered: "1. Very High" = rulebook tier 4; "4. Low" = tier 1. Re-derive from Total_risk_Score with rule_tier bands')
add('rule_safety_flag','safety','Priority clinical review','Priority_clinical_review; flag_dka_l12m; flag_dm_hypoglycaemia_l12m; flag_EDorIP_with_hypoglycaemia_last90days')
# §3 triggers: extract flag + raw data the rulebook names
TR=[('Trig3','Trig3_hypoglycemia_tx; Trig3a_hypoglycemia_rev; Trig3b_glucagon_not_dispensed','flag_dm_hypoglycaemia_l12m; flag_dm_hypoglycaemia_last90days; flag_EDorIP_with_hypoglycaemia_last90days; flag_hypo_hyper_glycemia_last6months; flag_active_insulin; flag_active_sulfonylurea; flag_glucagon_last12months; flag_no_glucagon_last12months'),
 ('BPU','(no extract flag)','Last_SystolicPressure_Value; Last_DiastolicPressure_Value; Last_SystolicPressure_Date'),
 ('Trig4','Trig4_post_discharge_care; Trig4a_NoFollowup_post_discharge; Trig4b_postdischarge_medsgap','last_ip_discharge_date; last_ip_admit_date; second_last_ip_discharge_date; ed_visits_l12m; er_visits_6m; last_ed_visit_date; flag_no_visit_after_discharge; first_visit_after_discharge; days_discharge_to_first_visit; flag_missing_T2Drefill_post_last_discharge; flag_missing_HTNrefill_post_last_discharge; last_ip_discharge_type'),
 ('Trig1','Trig1_HbA1c_above_target','Last_HbA1c_Value; Last_HbA1c_Date; last_hba1c_date2'),
 ('Trig2','Trig2_HTN_tx_review; Trig2a_NoACEiARB_KidneyOrCAD; Trig2b_ACEi_plus_ARB','Last_SystolicPressure_Value; Last_DiastolicPressure_Value; flag_ckd_l12m; flag_cad_mi_l12m; flag_active_ACEinhibitor; flag_active_ARBinhibitor; flag_overlap_ACE_ARB_more_than_30days; htn_drug_classes_l12m'),
 ('Trig5','Trig5_Kidney_check; Trig5a_Kidney_screen_due; Trig5b_CKD_monitoring; Trig5c_Neph_due','Last_eGFR_Value; last_egfr_test_date; Last_UACR_Value; Last_UACR_Date; last_urine_albumin_date; last_renal_panel_date; last_nephrology_visit; ckd_stage_l12m; flag_ckd_l12m'),
 ('Trig9','Trig9_medication_adherence','pdc_any_t2d_noninsulin; pdc_any_htn; pdc_metformin; pdc_sglt2; pdc_dpp4; pdc_glp1; pdc_sulfonylurea; pdc_tzd; pdc_acei; pdc_arb; pdc_ccb; pdc_beta_blocker; pdc_thiazide; pdc_mra; days_since_t2d_supply_ran_out; days_since_htn_supply_ran_out; flag_t2d_rx_gap_over_30d; flag_htn_rx_gap_over_30d; active_drug_class_count; last_t2d_fill_date; last_htn_fill_date'),
 ('Trig6','Trig6_HbA1c_due','last_hba1c_date2; Last_HbA1c_Date; Last_HbA1c_Value'),
 ('Trig12','Trig12_eyeexam_due','last_retinal_screen_date; last_ophthalmology_visit'),
 ('Trig13','Trig13_highriskfoot_monitor','last_foot_exam; last_podiatry_visit; flag_dm_foot_ulcer_l12m; flag_peripheral_neuropathy_l12m; flag_pad_l12m; flag_amputation_l12m; flag_dm_foot_l12m'),
 ('Trig7','Trig7_Renal_Potassium_due','last_potassium_date; flag_active_ACEinhibitor; flag_active_ARBinhibitor; pdc_mra; pdc_thiazide; first_ACE_ARB_MRA_thiazide_fill_date; htn_drug_classes_l12m'),
 ('Trig11','Trig11_annual_labs_due','last_lipid_panel_date; last_renal_panel_date; last_liver_function_date; last_cbc_date'),
 ('Trig10','Trig10_new_diagnosis','first_e11_date; first_htn_date; latest_new_t2d_class_start_date; latest_new_htn_class_start_date'),
 ('Trig8','Trig8_nutrition_due','last_dietitian_visit; last_diabeducator_visit')]
for code,flag,raw in TR:
    add('rule_trigger',code,'extract flag (use_variant = extract)',flag)
    add('rule_trigger',code,'raw data the rulebook reads (use_variant = rulebook)',raw)
add('rule_trigger','all','number of triggers fired in the extract','# of triggers')
add('rule_trigger','pathway','T2D / HTN pathway','cohort_t2d_l12m; cohort_htn_l12m; t2d_identified_by; htn_identified_by; t2d_category; htn_category')
# §4 alert
add('rule_alert','RED','Safety flag, BP ≥ 180/110, eGFR < 15, hypoglycaemia event','Priority_clinical_review; Last_SystolicPressure_Value; Last_DiastolicPressure_Value; Last_eGFR_Value; flag_dm_hypoglycaemia_l12m; flag_dka_l12m')
add('rule_alert','AMBER','Post-discharge, HbA1c ≥ 9, BP ≥ 160/100, eGFR falling, PDC < 50%','Trig4_post_discharge_care; Last_HbA1c_Value; Last_SystolicPressure_Value; Last_DiastolicPressure_Value; Last_eGFR_Value; pdc_any_t2d_noninsulin; pdc_any_htn')
add('rule_alert','YELLOW','Off target below AMBER; overdue test or screening','Trig6_HbA1c_due; Trig11_annual_labs_due; Trig12_eyeexam_due; Trig13_highriskfoot_monitor; Trig7_Renal_Potassium_due; Trig5_Kidney_check')
add('rule_alert','GREEN','At target, nothing open','# of triggers = 0')
add('rule_contact_priority','P1–P4','From alert colour (+ Trig4 for P1 on AMBER)','derived: alert; Trig4_post_discharge_care')
add('rule_queue_order','1–4','Safety/RED, tier, campaign priority, hours past SLA','Priority_clinical_review; Total_risk_Score; (campaign.priority); (worklist.due_by)')
# gates
add('rule_guardrail','G1c','Exclusions and gates','Exclusion; Exclusion_nonactiveaccounts; Exclusion_op_consultations_encounter; Exclusion_alreadyenrolled; flag_excl_palliative_hospice_ltc_l12m; flag_excl_transplant_l24m; flag_excl_adv_neuro_congenital_l12m; flag_excl_psych_sud_dementia_l12m; flag_excl_ventilator_tpn_homenursing_l12m; flag_excl_pregnant_postpartum; flag_excl_single_episode_gt60pct; flag_excl_specialty_rx_gt60pct; flag_oncology_l12m; flag_oncology_l24m; flag_dialysis_l12m; home_nursing_days_l12m','Exclusion is the roll-up; the three Exclusion_* columns are new in this file (all 0 in the 250)')
add('rule_guardrail','G0','Plausibility','Last_SystolicPressure_Value; Last_DiastolicPressure_Value; Last_MeasuredBMI_Value','999 and 1/1 placeholders to NULL before any rule reads them')
add('rule_guardrail','G10','Staff work: language match','NATIONALITY','Arabic for the Arab nationalities, else English (working rule until a language field exists)')
# builder / persona
add('rule_builder_field_group','Who they are','Age, gender, nationality, plan, region','AGE; GENDER; NATIONALITY; policy_group; policy_type; GWP; Risk Premium','plan_name is not in this file; region never was')
add('rule_builder_field_group','Health','ICD-10 family, new diagnosis, chronic count','cohort_t2d_l12m; cohort_htn_l12m; flag_* condition columns; dm_complications; dm_complication_count; first_e11_date; first_htn_date; first_dyslipidemia_date')
add('rule_builder_field_group','Tests & results','Latest result / overdue test','Last_HbA1c_Value; Last_eGFR_Value; Last_UACR_Value; Last_SystolicPressure_Value; Last_DiastolicPressure_Value; Last_MeasuredBMI_Value; last_fastingplasmaglucose_value; last_*_date')
add('rule_builder_field_group','Visits & admissions','ED, admissions, no visit, specialist seen','ed_visits_l12m; ip_admissions_l12m; er_visits_6m; ip_admissions_6m; last_visit_date; gp_claims_6m; specialist_claims_6m; encounters_l12m; encounters_l12m_op; encounters_l12m_ed; encounters_l12m_ip; last_*_visit')
add('rule_builder_field_group','Medicines','ATC class, PDC, number of classes','active_drug_classes; active_drug_class_count; t2d_drug_classes_l12m; htn_drug_classes_l12m; pdc_*; distinct_medicines_90d')
add('rule_builder_field_group','Other','Screenings, network share and cost, engagement, consent, exclusions','last_retinal_screen_date; last_foot_exam; phg_share_l12m_encounters; *_share_l12m_encounters; l12m_payable_allcause; l12m_payable_DiaborHTNrelated; l12m_payable_DiaborHTNrelated_inside; l12m_payable_DiaborHTNrelated_outside; Exclusion')
add('rule_loop_step','Cohort','Persona and target cohort already set in the extract','Persona; P1_Complication; P2_Recurrent_ED_IP; P3_slipping; P3_offradar; P4_uncontrolled; P5_newlydiagnosed; Cohort_allocation; Initial_target_cohort','Persona is a targeting input the builder may use; it is not a score')
add('rule_event_type','MEMBER_FEATURE','Member 360 display fields (not read by a rule)','last_ip_facility; last_ip_dx; last_ip_dx_desc; last_ip_drg_desc; last_ed_facility; last_ed_dx; last_ed_dx_desc; last_claim_date; last_claim_costblocks; last_claim_facilities; last_claim_specialties; last_claim_dx_codes; last_claim_dx_desc; last_claim_medicines; last_claim_activities; last_claim_payable; top_groupownerlevel_*')

# ── 2. column catalogue with group and users ──
used=collections.defaultdict(list)
for t,k,i,cols,n in M:
    for c in [x.strip() for x in cols.split(';')]:
        if c in HDR: used[c].append(f'{t}:{k}')
def group(c):
    cl=c.lower()
    if c in ('mask_id',): return 'Identity'
    if c in ('GENDER','AGE','NATIONALITY','policy_group','policy_type','GWP','Risk Premium'): return 'Who they are'
    if c.startswith('Trig'): return 'Trigger flags (extract-computed)'
    if c in ('HbA1c_score','Clinical_score','Comorbid_complication_score','eGFR + UACR points','Kidney_score','Utilization_score','Age_sex_score','Total_risk_Score','Risk_tier','Priority_clinical_review','# of triggers'): return 'Risk score (extract-computed)'
    if c.startswith(('P1_','P2_','P3_','P4_','P5_')) or c in ('Persona','Cohort_allocation','Initial_target_cohort'): return 'Persona and targeting'
    if c.startswith('Exclusion') or 'excl' in cl or c.startswith(('flag_oncology','oncology','flag_benign','home_nursing','max_episode','specialty_rx','flag_av_access','last_av_access')): return 'Exclusions and gates'
    if c.startswith(('cohort_','t2d_identified','htn_identified','t2d_category','htn_category')): return 'Pathway'
    if c.startswith('Last_') or cl.startswith('last_') and any(k in cl for k in ('glucose','hba1c_date2','panel','albumin','egfr_test','retinal','liver','cbc','vitb12','potassium','smoking')): return 'Labs and readings'
    if cl.startswith('last_') and cl.endswith(('_visit','foot_exam')): return 'Visits by specialty'
    if cl.startswith('first_') and not 'fill' in cl and not 'visit' in cl and 'ace' not in cl: return 'Diagnosis dates'
    if c.startswith('flag_') or cl.startswith('last_') and ('_date' in cl) or c in ('dm_complications','dm_complication_count','ckd_stage_l12m'): return 'Conditions and complications'
    if 'pdc' in cl or 'drug' in cl or 'fill' in cl or 'supply' in cl or 'medicin' in cl or 'rx_gap' in cl or 'glucagon' in cl or 'ace' in cl and 'flag' in cl or 'class_start' in cl: return 'Medicines and adherence'
    if any(k in cl for k in ('ip_','ed_','er_visits','discharge','visit','gp_claims','specialist_claims','encounter')) and 'payable' not in cl: return 'Visits and admissions'
    if 'payable' in cl or 'share' in cl or 'provider' in cl or 'groupowner' in cl: return 'Cost and network'
    if c.startswith('last_claim'): return 'Last claim (display)'
    return 'Other'
CAT=[]
for c in HDR:
    CAT.append((c, col(c), group(c), T[c], 'new in this file' if c not in [r['column'] for r in csv.DictReader(open(REPO+'/data/raw/glossary.tsv',encoding='utf-8'),delimiter='\t')] else '', '; '.join(used.get(c,[])) or 'builder / Member 360 only'))
rule_cols=sum(1 for r in CAT if r[5]!='builder / Member 360 only')
print('columns read by a rule:', rule_cols, 'of', len(HDR))

# ── 3. typed DDL for the 377 columns ──
LONG={'last_claim_activities','last_claim_medicines','last_claim_dx_desc','last_claim_facilities','last_claim_specialties','last_claim_dx_codes','oncology_dx_codes','specialty_rx_areas','active_drug_classes','t2d_drug_classes_l12m','htn_drug_classes_l12m','dm_complications','last_ip_drg_desc','last_ip_dx_desc','last_ed_dx_desc','last_claim_costblocks'}
def sqlt(c):
    t=T[c]
    if c=='mask_id': return 'VARCHAR(20) NOT NULL'
    if c in LONG: return 'TEXT'
    return {'flag':'TINYINT','int':'INT','num':'DECIMAL(14,4)','date':'DATE','text':'VARCHAR(200)','empty':'VARCHAR(120)'}[t]
ddl=['-- member_longitudinal: the 250-member longitudinal extract (377 columns) typed for SingleStore / MySQL.',
     '-- Generated from 250_members_longitudinal_data.xlsx by the mapping build. mask_id → member_id. Column names lower-cased; spaces and symbols → _.',
     '-- Placeholders (999, BP 1/1, text NULL, #VALUE!) are cleaned by 03_load.sql rules (G0) when loaded through stg_extract.',
     'CREATE ROWSTORE TABLE IF NOT EXISTS member_longitudinal (']
w=max(len(col(c)) for c in HDR)
for c in HDR: ddl.append(f'  {col(c):<{w}} {sqlt(c)},   -- {c}'+(' · new' if c in [r[0] for r in CAT if r[4]] else ''))
ddl.append(f'  PRIMARY KEY (member_id),\n  SHARD KEY (member_id)\n);')
open(REPO+'/two-day-build/sql/01b_member_longitudinal.sql','w',encoding='utf-8').write('\n'.join(ddl)+'\n')

# ── 4. CSVs + workbook ──
os.makedirs(REPO+'/rules',exist_ok=True)
with open(REPO+'/rules/rule_source_column.csv','w',newline='',encoding='utf-8') as f:
    cw=csv.writer(f); cw.writerow(['rule_table','rule_key','input','source_columns','note']); cw.writerows(M)
with open(REPO+'/rules/column_catalogue_250.csv','w',newline='',encoding='utf-8') as f:
    cw=csv.writer(f); cw.writerow(['column','sql_name','group','type','new_in_this_file','read_by_rule']); cw.writerows(CAT)
H=Font(bold=True,color='FFFFFF'); HF=PatternFill('solid',fgColor='13223A'); WR=Alignment(wrap_text=True,vertical='top')
wb=Workbook(); ws=wb.active; ws.title='Index'
ws.append(['CCC Rulebook tables, sourced from 250_members_longitudinal_data.xlsx (377 columns)']); ws['A1'].font=Font(bold=True,size=13)
ws.append(['Each rulebook input is tied to the column(s) in this file that feed it. Column catalogue: every column, its type, whether it is new, and which rule reads it.'])
ws.append([]); ws.append(['Sheet','What it holds','Rows'])
for c in ws[4]: c.font=H; c.fill=HF
def sheet(name,hdr,rows,what):
    s=wb.create_sheet(name[:31]); s.append(hdr)
    for c in s[1]: c.font=H; c.fill=HF
    for r in rows: s.append(list(r))
    for i,h in enumerate(hdr,1): s.column_dimensions[get_column_letter(i)].width=min(70,max(12,max(len(str(x[i-1])) for x in [hdr]+[list(r) for r in rows])+2))
    for r in s.iter_rows(min_row=2):
        for c in r: c.alignment=WR
    s.freeze_panes='A2'; ws.append([name,what,len(rows)])
sheet('rule_source_column',['rule_table','rule_key','input','source_columns','note'],M,'Every rulebook input → the columns in this file')
sheet('column_catalogue',['column','sql_name','group','type','new_in_this_file','read_by_rule'],CAT,'All 377 columns: group, type, new?, which rule reads it')
# rulebook tables with a source column joined in
def rd(n): return list(csv.DictReader(open(f'{REPO}/rules/{n}.csv',encoding='utf-8-sig')))
src=collections.defaultdict(list)
for t,k,i,cols,n in M: src[(t,k)].append(cols)
rb=rd('rule_risk_band'); sheet('risk_band_sourced',['component','input','band','points','cap','source_columns'],[(r['component'],r['input'],r['band'],r['points'],r['cap'],' | '.join(src[('rule_risk_band',r['component'])])) for r in rb],'§2 scoring bands with source columns')
tr=rd('rule_trigger'); ac={a['trigger_code']:a for a in rd('rule_action')}; cls={c['class']:c for c in rd('rule_need_class')}
sheet('trigger_sourced',['trigger_code','name','pathway','class','class_order','raw_data_rulebook','fires_when_rulebook','extract_flag_columns','raw_data_columns','next_best_action','owner','done_when','use_variant','status'],
      [(r['trigger_code'],r['name'],r['pathway'],cls[r['class']]['label'],cls[r['class']]['sort_order'],r['raw_data_rulebook'],r['fires_when_rulebook'],src[('rule_trigger',r['trigger_code'])][0],src[('rule_trigger',r['trigger_code'])][1],ac[r['trigger_code']]['title'],ac[r['trigger_code']]['owner_role'],ac[r['trigger_code']]['done_when'],r['use_variant'],r['status']) for r in sorted(tr,key=lambda r:(int(cls[r['class']]['sort_order']),int(r['sort_order'])))],'§3 the 14 triggers in class order, with the extract flag and raw columns')
al=rd('rule_alert'); sheet('alert_sourced',['colour','criteria','response','source_columns'],[(r['colour'],r['criteria'],r['response'],' | '.join(src[('rule_alert',r['colour'])])) for r in al],'§4 alert colours with source columns')
sheet('tier_and_safety',['tier','label','r_min','r_max','campaign_does','cadence','source'],[(r['tier'],r['label'],r['r_min'],r['r_max'],r['campaign_does'],r['cadence'],'Total_risk_Score (Risk_tier label is reverse-numbered)') for r in rd('rule_tier')]+[('safety','Priority clinical review','','','Event pathway: same day, D3, D7, D14, then tier 4 cadence','','Priority_clinical_review; flag_dka_l12m; flag_dm_hypoglycaemia_l12m')],'§2 tiers and the safety flag')
gates=[r for r in CAT if r[2]=='Exclusions and gates']; sheet('gates_sourced',['column','type','note'],[(r[0],r[3],'new in this file' if r[4] else '') for r in gates],'G1c: every exclusion / gate column')
for col_,wd in zip('ABC',[28,80,8]): ws.column_dimensions[col_].width=wd
for r in ws.iter_rows(min_row=5):
    for c in r: c.alignment=WR
ws.freeze_panes='A5'
wb.save(REPO+'/rules/CCC_Rulebook_Tables_250_longitudinal.xlsx')

# ── 5. TSV of the file in the loader's text format ──
wbx=load_workbook('long.xlsx',read_only=True,data_only=True); rows=list(wbx.worksheets[0].iter_rows(values_only=True))
def fmt(v):
    if v is None or v=='NULL': return 'NULL'
    if isinstance(v,datetime.datetime): return f'{v.month}/{v.day}/{v.year}'
    if isinstance(v,float) and v.is_integer(): return str(int(v))
    return str(v).replace('\t',' ').replace('\n',' ')
with open(REPO+'/data/raw/member_features_250_longitudinal.tsv','w',encoding='utf-8',newline='') as f:
    f.write('\t'.join(rows[0])+'\n')
    for r in rows[1:]: f.write('\t'.join(fmt(v) for v in r)+'\n')
print('mapping rows',len(M),'catalogue',len(CAT),'new cols',sum(1 for r in CAT if r[4]))
