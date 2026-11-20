"""Reference data from the CCC Rulebook (T2D and Hypertension) and the extract glossary."""

RUN_DATE = '2026-11-20'      # demo "today"
AS_OF = '2026-10-31'         # review date the extract was computed for

# Rulebook §3 — trigger → next best action. flag = extract column that fires it.
TRIGGERS = [
    # code, flag column, name, pathway, raw columns, fires when, action, owner, done when, class
    ('Trig3', 'Trig3_hypoglycemia_tx', 'Hypoglycaemia', 'T2D', 'flag_dm_hypoglycaemia_last90days, flag_no_glucagon_last12months, flag_active_insulin',
     'Hypoglycaemia event in the last 90 days, or on insulin / sulfonylurea without rescue glucagon',
     'Same-day clinician review, hypo plan, glucagon check', 'Doctor', 'Review note and medicine change logged', 'safety'),
    ('BPU', None, 'BP urgent', 'HTN', 'Last_SystolicPressure_Value, Last_DiastolicPressure_Value',
     'Latest BP ≥ 180/110', 'Stop the script and escalate the same day', 'Nurse → doctor', 'Escalation closed', 'safety'),
    ('Trig4', 'Trig4_post_discharge_care', 'Post-discharge care', 'T2D · HTN', 'last_ip_discharge_date, flag_no_visit_after_discharge, flag_missing_*refill_post_last_discharge',
     'Discharged with no clinic visit since, or a medicine not refilled within 30 days of discharge',
     'GP follow-up within 72 h; medicine reconciliation', 'Coordinator', 'GP outpatient claim within 7 days', 'acute'),
    ('Trig1', 'Trig1_HbA1c_above_target', 'HbA1c above target', 'T2D', 'Last_HbA1c_Value, Last_HbA1c_Date',
     'Latest HbA1c ≥ 6.5% (extract); rulebook: ≥ individual goal (around 8%)', 'Glycaemic treatment review', 'Doctor', 'Goal, decision and next test date recorded', 'unctl'),
    ('Trig2', 'Trig2_HTN_tx_review', 'BP treatment review', 'HTN', 'flag_active_ACEinhibitor, flag_active_ARBinhibitor, flag_overlap_ACE_ARB_more_than_30days',
     'DM + HTN with kidney disease or CAD and no ACEi/ARB, or ACEi + ARB overlapping', 'Home BP recheck and clinician review', 'Nurse', 'Readings reviewed, next BP date set', 'unctl'),
    ('Trig5', 'Trig5_Kidney_check', 'Kidney check', 'T2D · HTN', 'Last_eGFR_Value, Last_UACR_Value, last_egfr_test_date, last_urine_albumin_date, last_nephrology_visit',
     'eGFR or UACR missing / older than 12 months (90 days with CKD), or eGFR < 30 with no nephrology visit', 'Book eGFR and UACR; nephrology if eGFR < 30', 'Coordinator', 'Lab claim with a result', 'unctl'),
    ('Trig9', 'Trig9_medication_adherence', 'Medication adherence', 'T2D · HTN', 'pdc_any_t2d_noninsulin, pdc_any_htn, days_since_*_supply_ran_out',
     'PDC < 80%, or supply ran out more than 30 days ago', 'Refill and barrier check; pharmacist if 3 or more classes', 'Coordinator', 'Next fill dispensed within 14 days', 'barrier'),
    ('Trig6', 'Trig6_HbA1c_due', 'HbA1c test due', 'T2D', 'last_hba1c_date2, Last_HbA1c_Value',
     'No HbA1c in 180 days (90 days if off target or after a glycaemic event)', 'Book HbA1c at an in-network lab', 'Coordinator', 'Lab claim', 'gap'),
    ('Trig12', 'Trig12_eyeexam_due', 'Eye exam due', 'T2D', 'last_retinal_screen_date, last_ophthalmology_visit, flag_dm_eye',
     'No retinal screen or eye-doctor visit in 365 / 730 days', 'Confirm the last exam or refer', 'Nurse', 'Report or referral claim', 'gap'),
    ('Trig13', 'Trig13_highriskfoot_monitor', 'High-risk foot', 'T2D', 'flag_dm_foot, flag_dm_neuropathy, flag_amputation, last_podiatry_visit',
     'Diabetic foot, neuropathy, amputation or dialysis, and no podiatry visit in 180 days', 'Foot exam; podiatry if high risk', 'Nurse', 'Exam claim', 'gap'),
    ('Trig7', 'Trig7_Renal_Potassium_due', 'Potassium due', 'HTN', 'last_potassium_date, first_ACE_ARB_MRA_thiazide_fill_date',
     'On ACEi / ARB / MRA / thiazide with no potassium test since starting or in 365 days', 'Add K+ to the next lab order', 'Coordinator', 'Lab claim', 'gap'),
    ('Trig11', 'Trig11_annual_labs_due', 'Annual labs', 'T2D · HTN', 'last_lipid_panel_date, last_urine_albumin_date, last_liver_function_date, last_cbc_date, last_vitb12_date',
     'An annual lab missing or older than 365 days', 'One bundled lab visit', 'Coordinator', 'Lab claims', 'gap'),
    ('Trig10', 'Trig10_new_diagnosis', 'New diagnosis', 'T2D · HTN', 'first_e11_date, first_htn_date, glucose and HbA1c values',
     'First diabetes / hypertension claim in the last 180 days, or diagnostic-range glucose', 'Baseline assessment and DSMES referral', 'Nurse', 'Assessment documented', 'goal'),
    ('Trig8', 'Trig8_nutrition_due', 'Nutrition and education', 'T2D', 'last_dietitian_visit, last_diabeducator_visit',
     'No dietitian or diabetes-educator visit in 365 days', 'Self-management goal, dietitian', 'Nurse', 'Goal set and reviewed', 'goal'),
]
TRIG = {t[0]: t for t in TRIGGERS}
CLASS_ORDER = ['safety', 'acute', 'unctl', 'barrier', 'gap', 'goal']
CLASS_DUE_DAYS = {'safety': 0, 'acute': 3, 'unctl': 7, 'barrier': 7, 'gap': 30, 'goal': 14}

# Portal signal codes each trigger is shown as (keeps the portal's pathways and action library working)
PORTAL_CODE = {'Trig1': 'HBA1C_ABOVE_GOAL', 'Trig2': 'BP_ABOVE_TARGET', 'Trig3': 'HYPO', 'BPU': 'BP_URGENT', 'Trig4': 'POST_DISCHARGE',
               'Trig5': 'KIDNEY_DUE', 'Trig6': 'HBA1C_OVERDUE', 'Trig7': 'POTASSIUM_DUE', 'Trig8': 'NUTRITION_DUE', 'Trig9': 'REFILL_GAP',
               'Trig10': 'NEW_DX', 'Trig11': 'ANNUAL_LABS', 'Trig12': 'EYE_UNKNOWN', 'Trig13': 'FOOT_UNKNOWN'}

# Rulebook §2 tiers (note: the extract's Risk_tier uses the reverse numbering: "1. Very High" … "4. Low")
TIERS = {1: ('Low', 'Baseline, M3, M6, M12'), 2: ('Moderate', 'Baseline, W6, M3, M5, M7, M9, M12'),
         3: ('High', 'Baseline, W2, M1, M2, M3, M4, M6, M9, M12'), 4: ('Very high', 'Weekly, then every 2–4 weeks')}
SLA_DAYS = {'P1': 0, 'P2': 1, 'P3': 3, 'P4': None}   # P4 = digital nudge only

# Categories that are care-intelligence outputs: never cohort filters (rulebook §2)
NOT_SELECTABLE = {'Risk score', 'Trigger', 'Persona'}

CARE_TEAM = [
    ('U-0142', 'Nadia Rahman', 'Registered nurse', 'English, Hindi', 25),
    ('U-0150', 'Omar Khalid', 'Care coordinator', 'Arabic, English', 25),
    ('U-0161', 'Sara Mansour', 'Registered nurse', 'Arabic, English', 25),
    ('U-0201', 'Layla M.', 'Population health', 'English, Arabic', None),
    ('U-0310', 'Dr. Rana K.', 'Clinical lead', 'Arabic, English', None),
]
NURSES = ['U-0142', 'U-0161', 'U-0150']

# Condition flags → portal condition records (short codes the portal understands)
CONDITIONS = [
    ('cohort_t2d_l12m', 'E11', 'DM', 'Type 2 diabetes'), ('cohort_htn_l12m', 'I10', 'HTN', 'Hypertension'),
    ('flag_dyslipidemia_l12m', 'E78', 'LIPID', 'Dyslipidaemia'), ('flag_obesity', 'E66', 'OBESITY', 'Obesity'),
    ('flag_ckd', 'N18', 'CKD', 'Chronic kidney disease'), ('flag_ischemic_heart_disease', 'I25', 'IHD', 'Ischaemic heart disease'),
    ('flag_heart_failure', 'I50', 'HF', 'Heart failure'), ('flag_stroke', 'I63', 'STROKE', 'Stroke'),
    ('flag_pad_l12m', 'I73.9', 'PAD', 'Peripheral arterial disease'), ('flag_dm_retinopathy_l12m', 'E11.3', 'RETINO', 'Diabetic retinopathy'),
    ('flag_dm_neuropathy', 'E11.4', 'NEURO', 'Diabetic neuropathy'), ('flag_dm_foot_ulcer_l12m', 'E11.621', 'ULCER', 'Diabetic foot ulcer'),
]
PDC_COLUMNS = [('pdc_metformin', 'Metformin', 'Biguanide'), ('pdc_sglt2', 'SGLT2 inhibitor', 'SGLT2'), ('pdc_dpp4', 'DPP-4 inhibitor', 'DPP-4'),
               ('pdc_glp1', 'GLP-1 agonist', 'GLP-1'), ('pdc_sulfonylurea', 'Sulfonylurea', 'Sulfonylurea'), ('pdc_tzd', 'Pioglitazone', 'TZD'),
               ('pdc_acei', 'ACE inhibitor', 'ACE inhibitor'), ('pdc_arb', 'ARB', 'ARB'), ('pdc_ccb', 'Calcium-channel blocker', 'CCB'),
               ('pdc_beta_blocker', 'Beta blocker', 'Beta blocker'), ('pdc_thiazide', 'Thiazide', 'Thiazide diuretic'), ('pdc_mra', 'MRA', 'MRA')]
