"""Reference data from the CCC Rulebook (T2D and Hypertension) and the extract glossary."""

RUN_DATE = '2026-11-20'      # demo "today"
AS_OF = '2026-10-31'         # review date the extract was computed for

# Rulebook §3–5 come from the rule database (rules/*.csv): trigger → next best action → class, due days, tiers, SLAs.
from .rules import Rules
RULES = Rules()
# code, extract flag, name, pathway, raw columns, fires when, action, owner, done when, class
TRIGGERS = [(t['trigger_code'], t['extract_flag'], t['name'], t['pathway'], t['raw_data_rulebook'], t['fires_when_rulebook'],
             RULES.actions[t['trigger_code']]['title'], RULES.actions[t['trigger_code']]['owner_role'], RULES.actions[t['trigger_code']]['done_when'], t['class'])
            for t in RULES.triggers]
TRIG = {t[0]: t for t in TRIGGERS}
CLASS_ORDER = [c['class'] for c in RULES.classes]
CLASS_DUE_DAYS = {c['class']: int(c['due_days']) for c in RULES.classes}

# Portal signal codes each trigger is shown as (keeps the portal's pathways and action library working)
PORTAL_CODE = {'Trig1': 'HBA1C_ABOVE_GOAL', 'Trig2': 'BP_ABOVE_TARGET', 'Trig3': 'HYPO', 'BPU': 'BP_URGENT', 'Trig4': 'POST_DISCHARGE',
               'Trig5': 'KIDNEY_DUE', 'Trig6': 'HBA1C_OVERDUE', 'Trig7': 'POTASSIUM_DUE', 'Trig8': 'NUTRITION_DUE', 'Trig9': 'REFILL_GAP',
               'Trig10': 'NEW_DX', 'Trig11': 'ANNUAL_LABS', 'Trig12': 'EYE_UNKNOWN', 'Trig13': 'FOOT_UNKNOWN'}

TIERS = {t: (r['label'], r['cadence']) for t, r in RULES.tiers.items()}
SLA_DAYS = {r['priority']: (None if r['sla_days'] is None else int(r['sla_days'])) for r in RULES.priority}   # P4 = digital nudge only

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
