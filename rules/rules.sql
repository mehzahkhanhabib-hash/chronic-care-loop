-- Chronic Care Loop · rule database (from the CCC Rulebook, T2D and Hypertension, 20 Nov 2026)
-- Source of truth: rules/*.csv. raw extract column → condition → trigger → care-plan need (class, slot, due) → action → outcome → write-back.
CREATE TABLE IF NOT EXISTS rule_need_class (
  class       TEXT PRIMARY KEY,          -- safety | acute | unctl | barrier | gap | goal
  sort_order  INTEGER NOT NULL,          -- order inside a care plan (safety first)
  label       TEXT NOT NULL,
  due_days    INTEGER NOT NULL,          -- a need of this class is due this many days after it opens
  meaning     TEXT
);
CREATE TABLE IF NOT EXISTS rule_trigger (
  trigger_code         TEXT PRIMARY KEY, -- Trig1 … Trig13, BPU
  name                 TEXT NOT NULL,
  pathway              TEXT NOT NULL,
  class                TEXT NOT NULL REFERENCES rule_need_class(class),
  sort_order           INTEGER NOT NULL,
  raw_data_rulebook    TEXT,
  fires_when_rulebook  TEXT,
  extract_flag         TEXT,             -- extract column that already computes the trigger
  use_variant          TEXT NOT NULL CHECK (use_variant IN ('extract', 'rulebook')),
  status               TEXT
);
CREATE TABLE IF NOT EXISTS rule_condition (
  rule_id      TEXT NOT NULL,            -- <rule_type>:<target>:<variant>
  rule_type    TEXT NOT NULL,            -- trigger | cannot_tell | alert
  target       TEXT NOT NULL,            -- trigger code or alert colour
  variant      TEXT NOT NULL,            -- extract | rulebook | any
  group_no     INTEGER NOT NULL,         -- groups are OR-ed; conditions inside a group are AND-ed
  column_name  TEXT NOT NULL,            -- extract column (dates = days before the as-of date)
  op           TEXT NOT NULL CHECK (op IN ('=', '>=', '<=', '>', '<', 'is_null', 'not_null', 'missing_or_gt')),
  value        TEXT,
  note         TEXT,
  PRIMARY KEY (rule_id, group_no, column_name, op)
);
CREATE TABLE IF NOT EXISTS rule_action (
  action_code   TEXT PRIMARY KEY,
  trigger_code  TEXT NOT NULL UNIQUE REFERENCES rule_trigger(trigger_code),   -- one next best action per trigger
  title         TEXT NOT NULL,
  owner_role    TEXT NOT NULL,
  channel       TEXT NOT NULL,
  done_when     TEXT NOT NULL,           -- verified in claims
  evidence      TEXT,
  prerequisite  TEXT REFERENCES rule_trigger(trigger_code),                  -- G7: waits for this trigger's need to close
  escalate_to   TEXT
);
CREATE TABLE IF NOT EXISTS rule_slot (
  slot       TEXT PRIMARY KEY,           -- CURRENT | NEXT | FUTURE | CLOSED
  from_rank  INTEGER,
  to_rank    INTEGER,
  meaning    TEXT
);
CREATE TABLE IF NOT EXISTS rule_risk_band (
  component       TEXT NOT NULL,         -- C | M | K | U | A
  input           TEXT NOT NULL,
  band            TEXT NOT NULL,
  points          TEXT NOT NULL,
  cap             INTEGER NOT NULL,
  extract_column  TEXT,
  PRIMARY KEY (component, input, band)
);
CREATE TABLE IF NOT EXISTS rule_tier (
  tier           INTEGER PRIMARY KEY,
  label          TEXT NOT NULL,
  r_min          INTEGER NOT NULL,
  r_max          INTEGER NOT NULL,
  campaign_does  TEXT,
  cadence        TEXT NOT NULL,
  cadence_days   TEXT NOT NULL           -- contact days after baseline
);
CREATE TABLE IF NOT EXISTS rule_alert (
  colour      TEXT PRIMARY KEY,          -- RED | AMBER | YELLOW | GREEN
  sort_order  INTEGER NOT NULL,
  criteria    TEXT NOT NULL,
  response    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rule_contact_priority (
  priority               TEXT NOT NULL,  -- P1 … P4
  alert                  TEXT NOT NULL REFERENCES rule_alert(colour),
  also_requires_trigger  TEXT NOT NULL DEFAULT '',
  sla_days               INTEGER,        -- NULL = no call (digital nudge)
  channel                TEXT NOT NULL,
  meaning                TEXT,
  PRIMARY KEY (priority, alert, also_requires_trigger)
);
CREATE TABLE IF NOT EXISTS rule_queue_order (
  rank       INTEGER PRIMARY KEY,
  sort_key   TEXT NOT NULL,
  direction  TEXT NOT NULL,
  meaning    TEXT
);
CREATE TABLE IF NOT EXISTS rule_gap_state (
  state       TEXT PRIMARY KEY,          -- Potential → Verified → Scheduled → Reported → Closed
  sort_order  INTEGER NOT NULL,
  moved_by    TEXT NOT NULL,
  evidence    TEXT
);
CREATE TABLE IF NOT EXISTS rule_writeback (
  outcome            TEXT PRIMARY KEY,   -- what the nurse (or the claims) record
  need_status        TEXT,
  need_slot          TEXT,
  action_status      TEXT,
  gap_state          TEXT REFERENCES rule_gap_state(state),
  hold_days          INTEGER,
  max_attempts       INTEGER,
  retry_after_days   INTEGER,
  promote_next       INTEGER NOT NULL,
  new_calendar_item  TEXT,
  guardrail          TEXT
);
CREATE TABLE IF NOT EXISTS rule_guardrail (
  code         TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  rule         TEXT NOT NULL,
  enforced_in  TEXT
);
CREATE TABLE IF NOT EXISTS rule_decision_step (
  step          TEXT PRIMARY KEY,        -- A … J
  name          TEXT NOT NULL,
  what_happens  TEXT
);

INSERT INTO rule_need_class ("class", "sort_order", "label", "due_days", "meaning") VALUES
  ('safety', 1, 'Safety', 0, 'Same day; event pathway, not the cadence'),
  ('acute', 2, 'Acute event', 3, 'Due in 3 days'),
  ('unctl', 3, 'Uncontrolled', 7, 'Due in 7 days'),
  ('barrier', 4, 'Barrier', 7, 'Due in 7 days'),
  ('gap', 5, 'Verified gap', 30, 'Due in 30 days'),
  ('goal', 6, 'Patient goal', 14, 'Due in 14 days (not set in the rulebook; working default)');

INSERT INTO rule_trigger ("trigger_code", "name", "pathway", "class", "sort_order", "raw_data_rulebook", "fires_when_rulebook", "extract_flag", "use_variant", "status") VALUES
  ('Trig3', 'Hypoglycaemia', 'T2D', 'safety', 1, 'ICD E16.0–E16.2, E11.64; CGM < 3.9 mmol/L', 'Any event in 12 months', 'Trig3_hypoglycemia_tx', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('BPU', 'BP urgent', 'HTN', 'safety', 2, 'Home or claim BP', 'BP ≥ 180/110', NULL, 'rulebook', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig4', 'Post-discharge care', 'T2D · HTN', 'acute', 3, 'IP or ED encounter, discharge date', 'Discharge in the last 14 days, or 2 or more ED visits in 90 days', 'Trig4_post_discharge_care', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig1', 'HbA1c above target', 'T2D', 'unctl', 4, 'LOINC 4548-4', 'Last value ≥ individual goal (around 8%)', 'Trig1_HbA1c_above_target', 'extract', 'Draft: needs clinical sign-off (rulebook §8). Extract flag fires at 6.5%: decide which variant to use'),
  ('Trig2', 'BP treatment review', 'HTN', 'unctl', 5, 'SBP/DBP observations', '≥ 130/80 (DM or CKD) or ≥ 140/90', 'Trig2_HTN_tx_review', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig5', 'Kidney check', 'T2D · HTN', 'unctl', 6, 'eGFR 69405-9, UACR 9318-7', 'eGFR < 60, or no eGFR/UACR in 12 months', 'Trig5_Kidney_check', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig9', 'Medication adherence', 'T2D · HTN', 'barrier', 7, 'Pharmacy fills, days supply', 'PDC < 80% over 180 days, or a gap of more than 30 days', 'Trig9_medication_adherence', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig6', 'HbA1c test due', 'T2D', 'gap', 8, 'Last HbA1c date', '> 6 months (or > 3 months if off target)', 'Trig6_HbA1c_due', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig12', 'Eye exam due', 'T2D', 'gap', 9, 'Retinal CPT 92250/92227', 'None in 24 months', 'Trig12_eyeexam_due', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig13', 'High-risk foot', 'T2D', 'gap', 10, 'Foot CPT 2028F/G0245; ulcer, neuropathy, PAD', 'No exam in 12 months, or a high-risk code', 'Trig13_highriskfoot_monitor', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig7', 'Potassium due', 'HTN', 'gap', 11, 'K+ result, ACE/ARB/diuretic fills', 'On an RAAS inhibitor or diuretic with no K+ in 12 months', 'Trig7_Renal_Potassium_due', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig11', 'Annual labs', 'T2D · HTN', 'gap', 12, 'Lipids, creatinine', 'None in 12 months', 'Trig11_annual_labs_due', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig10', 'New diagnosis', 'T2D · HTN', 'goal', 13, 'First E11 / I10 claim', 'First code in the last 90 days', 'Trig10_new_diagnosis', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig8', 'Nutrition and education', 'T2D', 'goal', 14, 'No dietitian or DSMES claim', 'None in 12 months', 'Trig8_nutrition_due', 'extract', 'Draft: needs clinical sign-off (rulebook §8)');

INSERT INTO rule_condition ("rule_id", "rule_type", "target", "variant", "group_no", "column_name", "op", "value", "note") VALUES
  ('trigger:Trig1:extract', 'trigger', 'Trig1', 'extract', 1, 'Trig1_HbA1c_above_target', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig2:extract', 'trigger', 'Trig2', 'extract', 1, 'Trig2_HTN_tx_review', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig3:extract', 'trigger', 'Trig3', 'extract', 1, 'Trig3_hypoglycemia_tx', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig4:extract', 'trigger', 'Trig4', 'extract', 1, 'Trig4_post_discharge_care', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig5:extract', 'trigger', 'Trig5', 'extract', 1, 'Trig5_Kidney_check', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig6:extract', 'trigger', 'Trig6', 'extract', 1, 'Trig6_HbA1c_due', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig7:extract', 'trigger', 'Trig7', 'extract', 1, 'Trig7_Renal_Potassium_due', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig8:extract', 'trigger', 'Trig8', 'extract', 1, 'Trig8_nutrition_due', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig9:extract', 'trigger', 'Trig9', 'extract', 1, 'Trig9_medication_adherence', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig10:extract', 'trigger', 'Trig10', 'extract', 1, 'Trig10_new_diagnosis', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig11:extract', 'trigger', 'Trig11', 'extract', 1, 'Trig11_annual_labs_due', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig12:extract', 'trigger', 'Trig12', 'extract', 1, 'Trig12_eyeexam_due', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig13:extract', 'trigger', 'Trig13', 'extract', 1, 'Trig13_highriskfoot_monitor', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig1:rulebook', 'trigger', 'Trig1', 'rulebook', 1, 'cohort_t2d_l12m', '=', '1', 'Individual goal defaults to 8%'),
  ('trigger:Trig1:rulebook', 'trigger', 'Trig1', 'rulebook', 1, 'Last_HbA1c_Value', '>=', '8', 'Individual goal defaults to 8%'),
  ('trigger:BPU:rulebook', 'trigger', 'BPU', 'rulebook', 1, 'Last_SystolicPressure_Value', '>=', '180', NULL),
  ('trigger:BPU:rulebook', 'trigger', 'BPU', 'rulebook', 2, 'Last_DiastolicPressure_Value', '>=', '110', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 1, 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 1, 'Last_SystolicPressure_Value', '>=', '140', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 2, 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 2, 'Last_DiastolicPressure_Value', '>=', '90', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 3, 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 3, 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 3, 'Last_SystolicPressure_Value', '>=', '130', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 4, 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 4, 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 4, 'Last_DiastolicPressure_Value', '>=', '80', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 5, 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 5, 'flag_ckd', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 5, 'Last_SystolicPressure_Value', '>=', '130', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 6, 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 6, 'flag_ckd', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', 6, 'Last_DiastolicPressure_Value', '>=', '80', NULL),
  ('trigger:Trig3:rulebook', 'trigger', 'Trig3', 'rulebook', 1, 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig3:rulebook', 'trigger', 'Trig3', 'rulebook', 1, 'flag_dm_hypoglycaemia_l12m', '=', '1', NULL),
  ('trigger:Trig4:rulebook', 'trigger', 'Trig4', 'rulebook', 1, 'last_ip_discharge_date', '<=', '14', 'ED visits in 90 days approximated by 2+ in 12 months with the latest in 90 days'),
  ('trigger:Trig4:rulebook', 'trigger', 'Trig4', 'rulebook', 2, 'ed_visits_l12m', '>=', '2', 'ED visits in 90 days approximated by 2+ in 12 months with the latest in 90 days'),
  ('trigger:Trig4:rulebook', 'trigger', 'Trig4', 'rulebook', 2, 'last_ed_visit_date', '<=', '90', 'ED visits in 90 days approximated by 2+ in 12 months with the latest in 90 days'),
  ('trigger:Trig5:rulebook', 'trigger', 'Trig5', 'rulebook', 1, 'Last_eGFR_Value', '<', '60', NULL),
  ('trigger:Trig5:rulebook', 'trigger', 'Trig5', 'rulebook', 2, 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig5:rulebook', 'trigger', 'Trig5', 'rulebook', 2, 'last_egfr_test_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig5:rulebook', 'trigger', 'Trig5', 'rulebook', 3, 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig5:rulebook', 'trigger', 'Trig5', 'rulebook', 3, 'last_urine_albumin_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig9:rulebook', 'trigger', 'Trig9', 'rulebook', 1, 'pdc_any_t2d_noninsulin', '<', '0.8', NULL),
  ('trigger:Trig9:rulebook', 'trigger', 'Trig9', 'rulebook', 2, 'pdc_any_htn', '<', '0.8', NULL),
  ('trigger:Trig9:rulebook', 'trigger', 'Trig9', 'rulebook', 3, 'days_since_t2d_supply_ran_out', '>', '30', NULL),
  ('trigger:Trig9:rulebook', 'trigger', 'Trig9', 'rulebook', 4, 'days_since_htn_supply_ran_out', '>', '30', NULL),
  ('trigger:Trig6:rulebook', 'trigger', 'Trig6', 'rulebook', 1, 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig6:rulebook', 'trigger', 'Trig6', 'rulebook', 1, 'last_hba1c_date2', 'missing_or_gt', '180', NULL),
  ('trigger:Trig6:rulebook', 'trigger', 'Trig6', 'rulebook', 2, 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig6:rulebook', 'trigger', 'Trig6', 'rulebook', 2, 'Last_HbA1c_Value', '>=', '8', NULL),
  ('trigger:Trig6:rulebook', 'trigger', 'Trig6', 'rulebook', 2, 'last_hba1c_date2', 'missing_or_gt', '90', NULL),
  ('trigger:Trig12:rulebook', 'trigger', 'Trig12', 'rulebook', 1, 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig12:rulebook', 'trigger', 'Trig12', 'rulebook', 1, 'last_retinal_screen_date', 'missing_or_gt', '730', NULL),
  ('trigger:Trig12:rulebook', 'trigger', 'Trig12', 'rulebook', 1, 'last_ophthalmology_visit', 'missing_or_gt', '730', NULL),
  ('trigger:Trig13:rulebook', 'trigger', 'Trig13', 'rulebook', 1, 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig13:rulebook', 'trigger', 'Trig13', 'rulebook', 1, 'last_foot_exam', 'missing_or_gt', '365', NULL),
  ('trigger:Trig13:rulebook', 'trigger', 'Trig13', 'rulebook', 2, 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig13:rulebook', 'trigger', 'Trig13', 'rulebook', 2, 'flag_dm_foot_ulcer_l12m', '=', '1', NULL),
  ('trigger:Trig13:rulebook', 'trigger', 'Trig13', 'rulebook', 3, 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig13:rulebook', 'trigger', 'Trig13', 'rulebook', 3, 'flag_amputation', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', 1, 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', 1, 'flag_active_ACEinhibitor', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', 1, 'last_potassium_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', 2, 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', 2, 'flag_active_ARBinhibitor', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', 2, 'last_potassium_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', 3, 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', 3, 'pdc_mra', 'not_null', NULL, NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', 3, 'last_potassium_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', 4, 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', 4, 'pdc_thiazide', 'not_null', NULL, NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', 4, 'last_potassium_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig11:rulebook', 'trigger', 'Trig11', 'rulebook', 1, 'last_lipid_panel_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig11:rulebook', 'trigger', 'Trig11', 'rulebook', 2, 'last_renal_panel_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig10:rulebook', 'trigger', 'Trig10', 'rulebook', 1, 'first_e11_date', '<=', '90', NULL),
  ('trigger:Trig10:rulebook', 'trigger', 'Trig10', 'rulebook', 2, 'first_htn_date', '<=', '90', NULL),
  ('trigger:Trig8:rulebook', 'trigger', 'Trig8', 'rulebook', 1, 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig8:rulebook', 'trigger', 'Trig8', 'rulebook', 1, 'last_dietitian_visit', 'missing_or_gt', '365', NULL),
  ('trigger:Trig8:rulebook', 'trigger', 'Trig8', 'rulebook', 1, 'last_diabeducator_visit', 'missing_or_gt', '365', NULL),
  ('cannot_tell:Trig2:any', 'cannot_tell', 'Trig2', 'any', 1, 'cohort_htn_l12m', '=', '1', 'No usable BP reading (missing or a placeholder)'),
  ('cannot_tell:Trig2:any', 'cannot_tell', 'Trig2', 'any', 1, 'Last_SystolicPressure_Value', 'is_null', NULL, 'No usable BP reading (missing or a placeholder)'),
  ('cannot_tell:Trig6:any', 'cannot_tell', 'Trig6', 'any', 1, 'cohort_t2d_l12m', '=', '1', 'No usable HbA1c result'),
  ('cannot_tell:Trig6:any', 'cannot_tell', 'Trig6', 'any', 1, 'Last_HbA1c_Value', 'is_null', NULL, 'No usable HbA1c result'),
  ('cannot_tell:Trig5:any', 'cannot_tell', 'Trig5', 'any', 1, 'cohort_t2d_l12m', '=', '1', 'No eGFR or UACR result'),
  ('cannot_tell:Trig5:any', 'cannot_tell', 'Trig5', 'any', 1, 'Last_eGFR_Value', 'is_null', NULL, 'No eGFR or UACR result'),
  ('cannot_tell:Trig5:any', 'cannot_tell', 'Trig5', 'any', 1, 'Last_UACR_Value', 'is_null', NULL, 'No eGFR or UACR result'),
  ('alert:RED:any', 'alert', 'RED', 'any', 1, 'Priority_clinical_review', '=', '1', 'Red-flag symptoms are captured on the call, not from data'),
  ('alert:RED:any', 'alert', 'RED', 'any', 2, 'flag_dka_l12m', '=', '1', 'Red-flag symptoms are captured on the call, not from data'),
  ('alert:RED:any', 'alert', 'RED', 'any', 3, 'flag_dm_hypoglycaemia_l12m', '=', '1', 'Red-flag symptoms are captured on the call, not from data'),
  ('alert:RED:any', 'alert', 'RED', 'any', 4, 'Last_SystolicPressure_Value', '>=', '180', 'Red-flag symptoms are captured on the call, not from data'),
  ('alert:RED:any', 'alert', 'RED', 'any', 5, 'Last_DiastolicPressure_Value', '>=', '110', 'Red-flag symptoms are captured on the call, not from data'),
  ('alert:RED:any', 'alert', 'RED', 'any', 6, 'Last_eGFR_Value', '<', '15', 'Red-flag symptoms are captured on the call, not from data'),
  ('alert:AMBER:any', 'alert', 'AMBER', 'any', 1, 'Trig4_post_discharge_care', '=', '1', '"eGFR falling" needs two results; the extract has only the latest'),
  ('alert:AMBER:any', 'alert', 'AMBER', 'any', 2, 'Last_HbA1c_Value', '>=', '9', '"eGFR falling" needs two results; the extract has only the latest'),
  ('alert:AMBER:any', 'alert', 'AMBER', 'any', 3, 'Last_SystolicPressure_Value', '>=', '160', '"eGFR falling" needs two results; the extract has only the latest'),
  ('alert:AMBER:any', 'alert', 'AMBER', 'any', 4, 'Last_DiastolicPressure_Value', '>=', '100', '"eGFR falling" needs two results; the extract has only the latest'),
  ('alert:AMBER:any', 'alert', 'AMBER', 'any', 5, 'pdc_any_t2d_noninsulin', '<', '0.5', '"eGFR falling" needs two results; the extract has only the latest'),
  ('alert:AMBER:any', 'alert', 'AMBER', 'any', 6, 'pdc_any_htn', '<', '0.5', '"eGFR falling" needs two results; the extract has only the latest'),
  ('alert:YELLOW:any', 'alert', 'YELLOW', 'any', 1, '_fired_triggers', '>=', '1', 'Off target or an overdue test: any trigger fired');

INSERT INTO rule_action ("action_code", "trigger_code", "title", "owner_role", "channel", "done_when", "evidence", "prerequisite", "escalate_to") VALUES
  ('ACT-HYPO', 'Trig3', 'Same-day clinician review, hypo plan, glucagon check', 'Doctor', 'Call', 'Review note and medicine change logged', 'Clinician note; glucagon fill', NULL, 'Clinical lead'),
  ('ACT-BPU', 'BPU', 'Stop the script and escalate the same day', 'Nurse → doctor', 'Call', 'Escalation closed', 'Escalation outcome', NULL, 'Clinical lead'),
  ('ACT-POSTDC', 'Trig4', 'GP follow-up within 72 h; medicine reconciliation', 'Coordinator', 'Call', 'GP outpatient claim within 7 days', 'GP outpatient claim', NULL, NULL),
  ('ACT-A1C-REV', 'Trig1', 'Glycaemic treatment review', 'Doctor', 'Call', 'Goal, decision and next test date recorded', 'Outpatient claim + recorded goal', NULL, NULL),
  ('ACT-BP-REV', 'Trig2', 'Home BP recheck and clinician review', 'Nurse', 'Call', 'Readings reviewed, next BP date set', 'BP observation', NULL, NULL),
  ('ACT-KIDNEY', 'Trig5', 'Book eGFR and UACR; nephrology if eGFR < 30', 'Coordinator', 'Call', 'Lab claim with a result', 'eGFR / UACR lab claim', NULL, NULL),
  ('ACT-ADH', 'Trig9', 'Refill and barrier check; pharmacist if 3 or more classes', 'Coordinator / pharmacist', 'Call', 'Next fill dispensed within 14 days', 'Pharmacy fill', NULL, NULL),
  ('ACT-A1C-LAB', 'Trig6', 'Book HbA1c at an in-network lab', 'Coordinator', 'Call or WhatsApp', 'Lab claim', 'HbA1c lab claim', NULL, NULL),
  ('ACT-EYE', 'Trig12', 'Confirm the last exam or refer', 'Nurse', 'Call', 'Report or referral claim', 'Retinal CPT 92250/92227 or referral', NULL, NULL),
  ('ACT-FOOT', 'Trig13', 'Foot exam; podiatry if high risk', 'Nurse', 'Call', 'Exam claim', 'Foot CPT 2028F/G0245', NULL, NULL),
  ('ACT-K', 'Trig7', 'Add K+ to the next lab order', 'Coordinator', 'Call or WhatsApp', 'Lab claim', 'Potassium lab claim', NULL, NULL),
  ('ACT-LABS', 'Trig11', 'One bundled lab visit', 'Coordinator', 'Call or WhatsApp', 'Lab claims', 'Lipid and creatinine lab claims', NULL, NULL),
  ('ACT-NEWDX', 'Trig10', 'Baseline assessment and DSMES referral', 'Nurse', 'Call', 'Assessment documented', 'Assessment note; DSMES referral', NULL, NULL),
  ('ACT-DSMES', 'Trig8', 'Self-management goal, dietitian', 'Nurse', 'Call', 'Goal set and reviewed', 'Dietitian / DSMES claim', 'Trig1', NULL);

INSERT INTO rule_slot ("slot", "from_rank", "to_rank", "meaning") VALUES
  ('CURRENT', 1, 3, 'Active needs. A nurse never carries more than three (tree step I). Each has one action.'),
  ('NEXT', 4, 6, 'Due after the first three close; promoted when one closes.'),
  ('FUTURE', 7, 99, 'Scheduled on the cadence.'),
  ('CLOSED', NULL, NULL, 'Done or declined; kept for the record (G9).');

INSERT INTO rule_risk_band ("component", "input", "band", "points", "cap", "extract_column") VALUES
  ('C', 'HbA1c (T2D only)', '< 7', '0', 5, 'HbA1c_score'),
  ('C', 'HbA1c (T2D only)', '7–7.9', '1', 5, 'HbA1c_score'),
  ('C', 'HbA1c (T2D only)', '8–8.9', '2', 5, 'HbA1c_score'),
  ('C', 'HbA1c (T2D only)', '9–9.9', '3', 5, 'HbA1c_score'),
  ('C', 'HbA1c (T2D only)', '≥ 10', '4', 5, 'HbA1c_score'),
  ('C', 'HTN diagnosis', 'yes', '2', 5, 'Clinical_score'),
  ('C', 'Hypoglycaemia in 12 months', 'each', '2', 5, 'Clinical_score'),
  ('C', 'DKA in 12 months', 'each', '3', 5, 'Clinical_score'),
  ('M', 'Dyslipidaemia', 'yes', '1', 6, 'Comorbid_complication_score'),
  ('M', 'BMI ≥ 30', 'yes', '1', 6, 'Comorbid_complication_score'),
  ('M', 'Smoking', 'yes', '1', 6, 'Comorbid_complication_score'),
  ('M', 'CAD/MI', 'yes', '3', 6, 'Comorbid_complication_score'),
  ('M', 'Stroke/TIA', 'yes', '3', 6, 'Comorbid_complication_score'),
  ('M', 'Heart failure', 'yes', '3', 6, 'Comorbid_complication_score'),
  ('M', 'PAD', 'yes', '3', 6, 'Comorbid_complication_score'),
  ('M', 'Retinopathy', 'yes', '2', 6, 'Comorbid_complication_score'),
  ('M', 'Neuropathy', 'yes', '1', 6, 'Comorbid_complication_score'),
  ('M', 'Foot ulcer', 'yes', '4', 6, 'Comorbid_complication_score'),
  ('M', 'Major amputation', 'yes', '4', 6, 'Comorbid_complication_score'),
  ('K', 'eGFR', '≥ 60', '0', 5, 'Kidney_score'),
  ('K', 'eGFR', '45–59', '1', 5, 'Kidney_score'),
  ('K', 'eGFR', '30–44', '2', 5, 'Kidney_score'),
  ('K', 'eGFR', '15–29', '3', 5, 'Kidney_score'),
  ('K', 'eGFR', '< 15 or dialysis', '4', 5, 'Kidney_score'),
  ('K', 'UACR', '30–299', '1', 5, 'Kidney_score'),
  ('K', 'UACR', '≥ 300', '2', 5, 'Kidney_score'),
  ('K', 'CKD stage (both labs missing: provisional)', 'stage 3a / 3b / 4 / 5', '1 / 2 / 3 / 4', 5, 'Kidney_score'),
  ('U', 'ED visits not admitted', '0–3', '0–3', 5, 'Utilization_score'),
  ('U', 'Unplanned admissions', '1', '3', 5, 'Utilization_score'),
  ('U', 'Unplanned admissions', '≥ 2', '4', 5, 'Utilization_score'),
  ('A', 'Men', '< 40 / 40–59 / ≥ 60', '0 / 1 / 2', 2, 'Age_sex_score'),
  ('A', 'Women', '< 45 / 45–69 / ≥ 70', '0 / 1 / 2', 2, 'Age_sex_score');

INSERT INTO rule_tier ("tier", "label", "r_min", "r_max", "campaign_does", "cadence", "cadence_days") VALUES
  (1, 'Low', 0, 3, 'Routine monitoring, mostly digital nudges', 'Baseline, M3, M6, M12', '0,90,180,365'),
  (2, 'Moderate', 4, 7, 'Scheduled outreach and risk-factor management', 'Baseline, W6, M3, M5, M7, M9, M12', '0,42,90,150,210,270,365'),
  (3, 'High', 8, 12, 'Active case management and clinical coordination', 'Baseline, W2, M1, M2, M3, M4, M6, M9, M12', '0,14,30,60,90,120,180,270,365'),
  (4, 'Very high', 13, 23, 'Intensive follow-up and priority clinical coordination', 'Weekly, then every 2–4 weeks', '0,7,14,21,28,56,84,112,180');

INSERT INTO rule_alert ("colour", "sort_order", "criteria", "response") VALUES
  ('RED', 1, 'Safety flag, BP ≥ 180/110, eGFR < 15, a hypoglycaemia event, or red-flag symptoms on the call', 'Same-day clinician; the script stops'),
  ('AMBER', 2, 'Post-discharge, HbA1c ≥ 9, BP ≥ 160/100, eGFR falling, PDC < 50%', 'Clinician review within 72 h'),
  ('YELLOW', 3, 'Off target but below AMBER; an overdue test or screening', 'Next touchpoint'),
  ('GREEN', 4, 'At target, nothing open', 'Routine cadence');

INSERT INTO rule_contact_priority ("priority", "alert", "also_requires_trigger", "sla_days", "channel", "meaning") VALUES
  ('P1', 'RED', '', 0, 'Call', 'Same day'),
  ('P1', 'AMBER', 'Trig4', 0, 'Call', 'Same day: post-discharge (rulebook scenario 6.2)'),
  ('P2', 'AMBER', '', 1, 'Call', 'Next working day'),
  ('P3', 'YELLOW', '', 3, 'Call', 'Within 3 working days'),
  ('P4', 'GREEN', '', NULL, 'Digital nudge', 'No call; a digital nudge only');

INSERT INTO rule_queue_order ("rank", "sort_key", "direction", "meaning") VALUES
  (1, 'safety_or_red', 'desc', 'Safety flag or a RED alert first'),
  (2, 'tier', 'desc', 'Tier 4 down to 1'),
  (3, 'campaign_priority', 'asc', 'Campaign priority (1 first)'),
  (4, 'hours_past_sla', 'desc', 'Most overdue against the contact SLA');

INSERT INTO rule_gap_state ("state", "sort_order", "moved_by", "evidence") VALUES
  ('Potential', 1, 'Nightly run', 'Trigger fired'),
  ('Verified', 2, 'Nurse', 'Confirmed with the member on the call (member assertion)'),
  ('Scheduled', 3, 'Nurse', 'Action agreed or booked'),
  ('Reported', 4, 'Nurse', 'Nurse marked it done; not yet seen in claims'),
  ('Closed', 5, 'Nightly run', 'Success criterion appears in claims (the trigger stops firing)');

INSERT INTO rule_writeback ("outcome", "need_status", "need_slot", "action_status", "gap_state", "hold_days", "max_attempts", "retry_after_days", "promote_next", "new_calendar_item", "guardrail") VALUES
  ('done', 'done', 'CLOSED', 'done', 'Reported', NULL, NULL, NULL, 1, 'Next need, due by its class', 'G7'),
  ('declined', 'declined', 'CLOSED', 'declined', NULL, 90, NULL, NULL, 1, 'Re-offer at day 90', 'G4'),
  ('not_reached', NULL, NULL, NULL, NULL, NULL, 3, 1, 0, 'Retry the next working day; P1 escalates to the lead after 3 attempts', 'G3'),
  ('carried', 'open', 'CURRENT', 'open', NULL, NULL, NULL, NULL, 0, 'None: stays CURRENT with its due date', 'G9'),
  ('agreed', 'open', NULL, 'open', 'Scheduled', NULL, NULL, NULL, 0, 'None: the action is agreed with the member', NULL),
  ('member_assertion', NULL, NULL, NULL, 'Verified', NULL, NULL, NULL, 0, 'Matched again tonight; depends on whether the trigger still fires', 'G8'),
  ('consent_granted', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0, 'Member 360 and the care plan unlock', 'G2'),
  ('consent_declined', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0, 'Suppression written; no further contact', 'G2'),
  ('claim_evidence', 'done', 'CLOSED', 'done', 'Closed', NULL, NULL, NULL, 1, 'Trigger no longer fires on the next extract', 'G1');

INSERT INTO rule_guardrail ("code", "name", "rule", "enforced_in") VALUES
  ('G0', 'Plausibility', 'Impossible or placeholder values (for example 999, BP 1/1) are emptied before any rule reads them', 'backend/ingest.py (PLAUSIBLE)'),
  ('G1', 'Only fired triggers', 'Only fired triggers become needs; cannot-tell becomes a question', 'backend/engine.py run()'),
  ('G1b', 'Red flags', 'A RED alert stops the script and escalates the same day', 'rule_alert; portal call screen'),
  ('G1c', 'Gates', 'Exclusion = 1 in the extract and declined consent remove a member from every campaign', 'backend/engine.py campaign_members()'),
  ('G2', 'Consent', 'Nothing below the consent card is rendered until consent is logged', 'portal LOCKED(); member.consent_status'),
  ('G3', 'Contact cap', 'No new outreach call within 14 days of a reached call; max 3 attempts', 'backend/engine.py run(), process_outcomes()'),
  ('G4', 'Declines held', 'A declined need is not re-offered for 90 days', 'rule_writeback.hold_days'),
  ('G5', 'A deadline wins', 'A due date inside the contact cap still gets a call', 'backend/engine.py (due date by class)'),
  ('G7', 'Prerequisites', 'An action waiting on another is released when it closes', 'rule_action.prerequisite'),
  ('G8', 'Ask once', 'A cannot-tell question is asked once', 'rule_condition rule_type = cannot_tell'),
  ('G9', 'Dispositions survive a re-run', 'Done and declined needs are never reopened by the same extract', 'backend/engine.py run()'),
  ('G10', 'Staff work', 'Work is assigned by language, then skill, within daily capacity', 'care_team_user.daily_capacity');

INSERT INTO rule_decision_step ("step", "name", "what_happens") VALUES
  ('A', 'Assigned', 'Member assigned to a nurse'),
  ('B', 'Urgent?', 'Urgent flag checked first'),
  ('C', 'Contact', 'Contact made'),
  ('D', 'Consent', 'No consent: close or pause; nothing below D is readable'),
  ('E', 'New problem?', 'A new serious problem goes to the event pathway'),
  ('F', 'Pathway', 'DM, HTN or both; shared questions asked once'),
  ('G', 'Alert', 'Alert colour'),
  ('H', 'Prioritise', 'Order the needs'),
  ('I', '≤ 3 needs', 'At most three CURRENT needs'),
  ('J', 'Document', 'Purpose and finding, actions, owner and due date, alert, next contact, CURRENT / NEXT / FUTURE');
