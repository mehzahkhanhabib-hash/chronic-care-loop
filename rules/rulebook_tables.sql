-- CCC Rulebook (T2D and Hypertension, 20 Nov 2026) as tables. Generated from rules/*.csv by rules/make_workbook.py.
-- Every column is text here so the file loads on SingleStore, MySQL, PostgreSQL and SQLite unchanged; the kit's typed copies are in two-day-build/sql/02_rules.sql.

-- §1 How to use this rulebook: The five steps of the loop and what each writes
DROP TABLE IF EXISTS rule_loop_step;
CREATE TABLE rule_loop_step (`step_no` TEXT, `step` TEXT, `owner_component` TEXT, `what_happens` TEXT, `data_written` TEXT);
INSERT INTO rule_loop_step VALUES
  ('1', 'Cohort', 'Cohort & Campaign Builder', 'Selects members on raw inputs only; hands off a campaign', 'COHORT, COHORT_MEMBER (holdout by stable hash)'),
  ('2', 'Intelligence', 'Care intelligence', 'Scores R = C+M+K+U+A nightly; triggers fire with evidence; the planner ranks needs and actions; scripts are filled', 'MEMBER_FEATURE, MemberRisk, MEMBER_SIGNAL, NUDGE_PLAN, CLINICAL_ALERT'),
  ('3', 'Portal', 'Care Coordinator Portal', 'The nurse sees the worklist, Member 360 (after consent) and the care plan', 'CONSENT_EVENT, CASE_ACTION'),
  ('4', 'Write-back', 'Portal → care intelligence', 'Every outcome is recorded as an event', 'DISPOSITION_EVENT, MEMBER_ASSERTION, CARE_GAP_EVENT'),
  ('5', 'Next iteration', 'Care intelligence', 'Write-backs change features, triggers, rank and the next due date; closed needs drop out', 'Next nightly run');

-- §2 Targeting: The five risk components, formula and cap
DROP TABLE IF EXISTS rule_risk_component;
CREATE TABLE rule_risk_component (`component` TEXT, `name` TEXT, `inputs` TEXT, `formula` TEXT, `cap` TEXT, `extract_column` TEXT);
INSERT INTO rule_risk_component VALUES
  ('C', 'Clinical', 'HbA1c band (T2D only); HTN diagnosis; hypoglycaemia in 12 months; DKA in 12 months', 'H + Y + 2X + 3D', '5', 'Clinical_score'),
  ('M', 'Comorbidity', 'Dyslipidaemia, BMI ≥ 30, smoking (1 each); CAD/MI, stroke/TIA, HF, PAD (3 each); retinopathy 2; neuropathy 1; foot ulcer, major amputation (4 each)', 'sum', '6', 'Comorbid_complication_score'),
  ('K', 'Kidney', 'eGFR band plus UACR band; CKD-stage fallback when both labs are missing (provisional)', 'eGFR + UACR', '5', 'Kidney_score'),
  ('U', 'Utilisation', 'ED visits not admitted (0–3); unplanned admissions (1 → 3, ≥ 2 → 4)', 'ED + IP', '5', 'Utilization_score'),
  ('A', 'Age/sex', 'Men: < 40 → 0, 40–59 → 1, ≥ 60 → 2. Women: < 45 → 0, 45–69 → 1, ≥ 70 → 2', 'band', '2', 'Age_sex_score');

-- §2 Targeting: Every scoring band: input → points
DROP TABLE IF EXISTS rule_risk_band;
CREATE TABLE rule_risk_band (`component` TEXT, `input` TEXT, `band` TEXT, `points` TEXT, `cap` TEXT, `extract_column` TEXT);
INSERT INTO rule_risk_band VALUES
  ('C', 'HbA1c (T2D only)', '< 7', '0', '5', 'HbA1c_score'),
  ('C', 'HbA1c (T2D only)', '7–7.9', '1', '5', 'HbA1c_score'),
  ('C', 'HbA1c (T2D only)', '8–8.9', '2', '5', 'HbA1c_score'),
  ('C', 'HbA1c (T2D only)', '9–9.9', '3', '5', 'HbA1c_score'),
  ('C', 'HbA1c (T2D only)', '≥ 10', '4', '5', 'HbA1c_score'),
  ('C', 'HTN diagnosis', 'yes', '2', '5', 'Clinical_score'),
  ('C', 'Hypoglycaemia in 12 months', 'each', '2', '5', 'Clinical_score'),
  ('C', 'DKA in 12 months', 'each', '3', '5', 'Clinical_score'),
  ('M', 'Dyslipidaemia', 'yes', '1', '6', 'Comorbid_complication_score'),
  ('M', 'BMI ≥ 30', 'yes', '1', '6', 'Comorbid_complication_score'),
  ('M', 'Smoking', 'yes', '1', '6', 'Comorbid_complication_score'),
  ('M', 'CAD/MI', 'yes', '3', '6', 'Comorbid_complication_score'),
  ('M', 'Stroke/TIA', 'yes', '3', '6', 'Comorbid_complication_score'),
  ('M', 'Heart failure', 'yes', '3', '6', 'Comorbid_complication_score'),
  ('M', 'PAD', 'yes', '3', '6', 'Comorbid_complication_score'),
  ('M', 'Retinopathy', 'yes', '2', '6', 'Comorbid_complication_score'),
  ('M', 'Neuropathy', 'yes', '1', '6', 'Comorbid_complication_score'),
  ('M', 'Foot ulcer', 'yes', '4', '6', 'Comorbid_complication_score'),
  ('M', 'Major amputation', 'yes', '4', '6', 'Comorbid_complication_score'),
  ('K', 'eGFR', '≥ 60', '0', '5', 'Kidney_score'),
  ('K', 'eGFR', '45–59', '1', '5', 'Kidney_score'),
  ('K', 'eGFR', '30–44', '2', '5', 'Kidney_score'),
  ('K', 'eGFR', '15–29', '3', '5', 'Kidney_score'),
  ('K', 'eGFR', '< 15 or dialysis', '4', '5', 'Kidney_score'),
  ('K', 'UACR', '30–299', '1', '5', 'Kidney_score'),
  ('K', 'UACR', '≥ 300', '2', '5', 'Kidney_score'),
  ('K', 'CKD stage (both labs missing: provisional)', 'stage 3a / 3b / 4 / 5', '1 / 2 / 3 / 4', '5', 'Kidney_score'),
  ('U', 'ED visits not admitted', '0–3', '0–3', '5', 'Utilization_score'),
  ('U', 'Unplanned admissions', '1', '3', '5', 'Utilization_score'),
  ('U', 'Unplanned admissions', '≥ 2', '4', '5', 'Utilization_score'),
  ('A', 'Men', '< 40 / 40–59 / ≥ 60', '0 / 1 / 2', '2', 'Age_sex_score'),
  ('A', 'Women', '< 45 / 45–69 / ≥ 70', '0 / 1 / 2', '2', 'Age_sex_score');

-- §2 Targeting: Tier bands 1–4, what the campaign does, cadence
DROP TABLE IF EXISTS rule_tier;
CREATE TABLE rule_tier (`tier` TEXT, `label` TEXT, `r_min` TEXT, `r_max` TEXT, `campaign_does` TEXT, `cadence` TEXT, `cadence_days` TEXT);
INSERT INTO rule_tier VALUES
  ('1', 'Low', '0', '3', 'Routine monitoring, mostly digital nudges', 'Baseline, M3, M6, M12', '0,90,180,365'),
  ('2', 'Moderate', '4', '7', 'Scheduled outreach and risk-factor management', 'Baseline, W6, M3, M5, M7, M9, M12', '0,42,90,150,210,270,365'),
  ('3', 'High', '8', '12', 'Active case management and clinical coordination', 'Baseline, W2, M1, M2, M3, M4, M6, M9, M12', '0,14,30,60,90,120,180,270,365'),
  ('4', 'Very high', '13', '23', 'Intensive follow-up and priority clinical coordination', 'Weekly, then every 2–4 weeks', '0,7,14,21,28,56,84,112,180');

-- §2 Targeting: Cadence steps per tier with the rulebook labels (Baseline, W2, M1 …)
DROP TABLE IF EXISTS rule_cadence;
CREATE TABLE rule_cadence (`tier` TEXT, `step` TEXT, `label` TEXT, `day_offset` TEXT, `note` TEXT);
INSERT INTO rule_cadence VALUES
  ('1', '1', 'Baseline', '0', NULL),
  ('1', '2', 'M3', '90', NULL),
  ('1', '3', 'M6', '180', NULL),
  ('1', '4', 'M12', '365', NULL),
  ('2', '1', 'Baseline', '0', NULL),
  ('2', '2', 'W6', '42', NULL),
  ('2', '3', 'M3', '90', NULL),
  ('2', '4', 'M5', '150', NULL),
  ('2', '5', 'M7', '210', NULL),
  ('2', '6', 'M9', '270', NULL),
  ('2', '7', 'M12', '365', NULL),
  ('3', '1', 'Baseline', '0', NULL),
  ('3', '2', 'W2', '14', NULL),
  ('3', '3', 'M1', '30', NULL),
  ('3', '4', 'M2', '60', NULL),
  ('3', '5', 'M3', '90', NULL),
  ('3', '6', 'M4', '120', NULL),
  ('3', '7', 'M6', '180', NULL),
  ('3', '8', 'M9', '270', NULL),
  ('3', '9', 'M12', '365', NULL),
  ('4', '1', 'Baseline', '0', 'Weekly, then every 2–4 weeks (working schedule)'),
  ('4', '2', 'W1', '7', 'Weekly, then every 2–4 weeks (working schedule)'),
  ('4', '3', 'W2', '14', 'Weekly, then every 2–4 weeks (working schedule)'),
  ('4', '4', 'W3', '21', 'Weekly, then every 2–4 weeks (working schedule)'),
  ('4', '5', 'W4', '28', 'Weekly, then every 2–4 weeks (working schedule)'),
  ('4', '6', 'W8', '56', 'Weekly, then every 2–4 weeks (working schedule)'),
  ('4', '7', 'W12', '84', 'Weekly, then every 2–4 weeks (working schedule)'),
  ('4', '8', 'W16', '112', 'Weekly, then every 2–4 weeks (working schedule)'),
  ('4', '9', 'M6', '180', 'Weekly, then every 2–4 weeks (working schedule)');

-- §2 Targeting / §6.3: Safety flag: raised by, effect, event pathway
DROP TABLE IF EXISTS rule_safety_flag;
CREATE TABLE rule_safety_flag (`flag` TEXT, `raised_by` TEXT, `extract_columns` TEXT, `effect` TEXT, `event_pathway` TEXT, `note` TEXT);
INSERT INTO rule_safety_flag VALUES
  ('Priority clinical review', 'A coded DKA or hypoglycaemia event', 'flag_dka_l12m, flag_dm_hypoglycaemia_l12m, flag_dm_hyperglycaemic_crisis_l12m, Priority_clinical_review', 'Raises a Priority clinical review whatever the tier; RED alert; first in the queue', 'Clinician review the same day; check-in at D3, D7, D14; then the Tier 4 cadence', 'On the event pathway, not the cadence (rulebook §2, §6.3)');

-- §2 Builder inputs: The six field groups the builder offers
DROP TABLE IF EXISTS rule_builder_field_group;
CREATE TABLE rule_builder_field_group (`group_no` TEXT, `field_group` TEXT, `examples` TEXT, `extract_columns_today` TEXT);
INSERT INTO rule_builder_field_group VALUES
  ('1', 'Who they are', 'Age, gender, nationality, plan, region', 'AGE, GENDER, NATIONALITY, plan_name (region: not in extract)'),
  ('2', 'Health', 'Any ICD-10 family, new diagnosis, number of chronic conditions', 'cohort_t2d_l12m, cohort_htn_l12m, flag_* condition flags, first_e11_date, first_htn_date'),
  ('3', 'Tests & results', 'Latest result or overdue test: HbA1c, eGFR, UACR, LDL, BP, BMI, TSH', 'Last_*_Value, last_*_date (LDL, TSH: not in extract)'),
  ('4', 'Visits & admissions', 'ED visits, admissions, readmission, no outpatient visit, specialist seen', 'ed_visits_l12m, ip_admissions_l12m, last_visit_date, specialist_claims_6m'),
  ('5', 'Medicines', 'ATC class, adherence (PDC), number of medicine classes', 'active_drug_classes, pdc_*, active_drug_class_count'),
  ('6', 'Other', 'Screenings, network share and cost, engagement, consent and exclusions', 'last_retinal_screen_date, last_foot_exam, phg_share_l12m_encounters, l12m_payable_DiaborHTNrelated, Exclusion');

-- §2 Written nGQL: The seven checks before a query can load
DROP TABLE IF EXISTS rule_ngql_guardrail;
CREATE TABLE rule_ngql_guardrail (`check_no` TEXT, `check` TEXT, `sql_equivalent_in_kit` TEXT);
INSERT INTO rule_ngql_guardrail VALUES
  ('1', 'It is read-only', 'compile_rule only builds a SELECT'),
  ('2', 'It uses the daman_kg or seha_kg space', 'base = member (Daman extract)'),
  ('3', 'It starts from (m:Member)', 'FROM member m'),
  ('4', 'It returns id(m) AS member_vid', 'SELECT member_id'),
  ('5', 'It uses only known tags and edges', 'field whitelist in compile_rule'),
  ('6', 'Any variable-length path is bounded', 'no joins beyond member'),
  ('7', 'It does not read risk, tier or other intelligence outputs', 'r_total, tier, alert, contact_priority are refused as builder fields');

-- §3 Rule table: The 14 triggers: pathway, raw data, fires when, class, variant switch, sign-off status
DROP TABLE IF EXISTS rule_trigger;
CREATE TABLE rule_trigger (`trigger_code` TEXT, `name` TEXT, `pathway` TEXT, `class` TEXT, `sort_order` TEXT, `raw_data_rulebook` TEXT, `fires_when_rulebook` TEXT, `extract_flag` TEXT, `use_variant` TEXT, `status` TEXT);
INSERT INTO rule_trigger VALUES
  ('Trig3', 'Hypoglycaemia', 'T2D', 'safety', '1', 'ICD E16.0–E16.2, E11.64; CGM < 3.9 mmol/L', 'Any event in 12 months', 'Trig3_hypoglycemia_tx', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('BPU', 'BP urgent', 'HTN', 'safety', '2', 'Home or claim BP', 'BP ≥ 180/110', NULL, 'rulebook', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig4', 'Post-discharge care', 'T2D · HTN', 'acute', '3', 'IP or ED encounter, discharge date', 'Discharge in the last 14 days, or 2 or more ED visits in 90 days', 'Trig4_post_discharge_care', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig1', 'HbA1c above target', 'T2D', 'unctl', '4', 'LOINC 4548-4', 'Last value ≥ individual goal (around 8%)', 'Trig1_HbA1c_above_target', 'extract', 'Draft: needs clinical sign-off (rulebook §8). Extract flag fires at 6.5%: decide which variant to use'),
  ('Trig2', 'BP treatment review', 'HTN', 'unctl', '5', 'SBP/DBP observations', '≥ 130/80 (DM or CKD) or ≥ 140/90', 'Trig2_HTN_tx_review', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig5', 'Kidney check', 'T2D · HTN', 'unctl', '6', 'eGFR 69405-9, UACR 9318-7', 'eGFR < 60, or no eGFR/UACR in 12 months', 'Trig5_Kidney_check', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig9', 'Medication adherence', 'T2D · HTN', 'barrier', '7', 'Pharmacy fills, days supply', 'PDC < 80% over 180 days, or a gap of more than 30 days', 'Trig9_medication_adherence', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig6', 'HbA1c test due', 'T2D', 'gap', '8', 'Last HbA1c date', '> 6 months (or > 3 months if off target)', 'Trig6_HbA1c_due', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig12', 'Eye exam due', 'T2D', 'gap', '9', 'Retinal CPT 92250/92227', 'None in 24 months', 'Trig12_eyeexam_due', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig13', 'High-risk foot', 'T2D', 'gap', '10', 'Foot CPT 2028F/G0245; ulcer, neuropathy, PAD', 'No exam in 12 months, or a high-risk code', 'Trig13_highriskfoot_monitor', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig7', 'Potassium due', 'HTN', 'gap', '11', 'K+ result, ACE/ARB/diuretic fills', 'On an RAAS inhibitor or diuretic with no K+ in 12 months', 'Trig7_Renal_Potassium_due', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig11', 'Annual labs', 'T2D · HTN', 'gap', '12', 'Lipids, creatinine', 'None in 12 months', 'Trig11_annual_labs_due', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig10', 'New diagnosis', 'T2D · HTN', 'goal', '13', 'First E11 / I10 claim', 'First code in the last 90 days', 'Trig10_new_diagnosis', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig8', 'Nutrition and education', 'T2D', 'goal', '14', 'No dietitian or DSMES claim', 'None in 12 months', 'Trig8_nutrition_due', 'extract', 'Draft: needs clinical sign-off (rulebook §8)');

-- §3 Rule table: Each trigger's condition as column, operator, value (extract flag and rulebook threshold variants; cannot-tell; RED/AMBER)
DROP TABLE IF EXISTS rule_condition;
CREATE TABLE rule_condition (`rule_id` TEXT, `rule_type` TEXT, `target` TEXT, `variant` TEXT, `group_no` TEXT, `column_name` TEXT, `op` TEXT, `value` TEXT, `note` TEXT);
INSERT INTO rule_condition VALUES
  ('trigger:Trig1:extract', 'trigger', 'Trig1', 'extract', '1', 'Trig1_HbA1c_above_target', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig2:extract', 'trigger', 'Trig2', 'extract', '1', 'Trig2_HTN_tx_review', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig3:extract', 'trigger', 'Trig3', 'extract', '1', 'Trig3_hypoglycemia_tx', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig4:extract', 'trigger', 'Trig4', 'extract', '1', 'Trig4_post_discharge_care', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig5:extract', 'trigger', 'Trig5', 'extract', '1', 'Trig5_Kidney_check', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig6:extract', 'trigger', 'Trig6', 'extract', '1', 'Trig6_HbA1c_due', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig7:extract', 'trigger', 'Trig7', 'extract', '1', 'Trig7_Renal_Potassium_due', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig8:extract', 'trigger', 'Trig8', 'extract', '1', 'Trig8_nutrition_due', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig9:extract', 'trigger', 'Trig9', 'extract', '1', 'Trig9_medication_adherence', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig10:extract', 'trigger', 'Trig10', 'extract', '1', 'Trig10_new_diagnosis', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig11:extract', 'trigger', 'Trig11', 'extract', '1', 'Trig11_annual_labs_due', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig12:extract', 'trigger', 'Trig12', 'extract', '1', 'Trig12_eyeexam_due', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig13:extract', 'trigger', 'Trig13', 'extract', '1', 'Trig13_highriskfoot_monitor', '=', '1', 'Flag computed in the extract (see glossary)'),
  ('trigger:Trig1:rulebook', 'trigger', 'Trig1', 'rulebook', '1', 'cohort_t2d_l12m', '=', '1', 'Individual goal defaults to 8%'),
  ('trigger:Trig1:rulebook', 'trigger', 'Trig1', 'rulebook', '1', 'Last_HbA1c_Value', '>=', '8', 'Individual goal defaults to 8%'),
  ('trigger:BPU:rulebook', 'trigger', 'BPU', 'rulebook', '1', 'Last_SystolicPressure_Value', '>=', '180', NULL),
  ('trigger:BPU:rulebook', 'trigger', 'BPU', 'rulebook', '2', 'Last_DiastolicPressure_Value', '>=', '110', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '1', 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '1', 'Last_SystolicPressure_Value', '>=', '140', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '2', 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '2', 'Last_DiastolicPressure_Value', '>=', '90', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '3', 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '3', 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '3', 'Last_SystolicPressure_Value', '>=', '130', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '4', 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '4', 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '4', 'Last_DiastolicPressure_Value', '>=', '80', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '5', 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '5', 'flag_ckd', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '5', 'Last_SystolicPressure_Value', '>=', '130', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '6', 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '6', 'flag_ckd', '=', '1', NULL),
  ('trigger:Trig2:rulebook', 'trigger', 'Trig2', 'rulebook', '6', 'Last_DiastolicPressure_Value', '>=', '80', NULL),
  ('trigger:Trig3:rulebook', 'trigger', 'Trig3', 'rulebook', '1', 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig3:rulebook', 'trigger', 'Trig3', 'rulebook', '1', 'flag_dm_hypoglycaemia_l12m', '=', '1', NULL),
  ('trigger:Trig4:rulebook', 'trigger', 'Trig4', 'rulebook', '1', 'last_ip_discharge_date', '<=', '14', 'ED visits in 90 days approximated by 2+ in 12 months with the latest in 90 days'),
  ('trigger:Trig4:rulebook', 'trigger', 'Trig4', 'rulebook', '2', 'ed_visits_l12m', '>=', '2', 'ED visits in 90 days approximated by 2+ in 12 months with the latest in 90 days'),
  ('trigger:Trig4:rulebook', 'trigger', 'Trig4', 'rulebook', '2', 'last_ed_visit_date', '<=', '90', 'ED visits in 90 days approximated by 2+ in 12 months with the latest in 90 days'),
  ('trigger:Trig5:rulebook', 'trigger', 'Trig5', 'rulebook', '1', 'Last_eGFR_Value', '<', '60', NULL),
  ('trigger:Trig5:rulebook', 'trigger', 'Trig5', 'rulebook', '2', 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig5:rulebook', 'trigger', 'Trig5', 'rulebook', '2', 'last_egfr_test_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig5:rulebook', 'trigger', 'Trig5', 'rulebook', '3', 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig5:rulebook', 'trigger', 'Trig5', 'rulebook', '3', 'last_urine_albumin_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig9:rulebook', 'trigger', 'Trig9', 'rulebook', '1', 'pdc_any_t2d_noninsulin', '<', '0.8', NULL),
  ('trigger:Trig9:rulebook', 'trigger', 'Trig9', 'rulebook', '2', 'pdc_any_htn', '<', '0.8', NULL),
  ('trigger:Trig9:rulebook', 'trigger', 'Trig9', 'rulebook', '3', 'days_since_t2d_supply_ran_out', '>', '30', NULL),
  ('trigger:Trig9:rulebook', 'trigger', 'Trig9', 'rulebook', '4', 'days_since_htn_supply_ran_out', '>', '30', NULL),
  ('trigger:Trig6:rulebook', 'trigger', 'Trig6', 'rulebook', '1', 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig6:rulebook', 'trigger', 'Trig6', 'rulebook', '1', 'last_hba1c_date2', 'missing_or_gt', '180', NULL),
  ('trigger:Trig6:rulebook', 'trigger', 'Trig6', 'rulebook', '2', 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig6:rulebook', 'trigger', 'Trig6', 'rulebook', '2', 'Last_HbA1c_Value', '>=', '8', NULL),
  ('trigger:Trig6:rulebook', 'trigger', 'Trig6', 'rulebook', '2', 'last_hba1c_date2', 'missing_or_gt', '90', NULL),
  ('trigger:Trig12:rulebook', 'trigger', 'Trig12', 'rulebook', '1', 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig12:rulebook', 'trigger', 'Trig12', 'rulebook', '1', 'last_retinal_screen_date', 'missing_or_gt', '730', NULL),
  ('trigger:Trig12:rulebook', 'trigger', 'Trig12', 'rulebook', '1', 'last_ophthalmology_visit', 'missing_or_gt', '730', NULL),
  ('trigger:Trig13:rulebook', 'trigger', 'Trig13', 'rulebook', '1', 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig13:rulebook', 'trigger', 'Trig13', 'rulebook', '1', 'last_foot_exam', 'missing_or_gt', '365', NULL),
  ('trigger:Trig13:rulebook', 'trigger', 'Trig13', 'rulebook', '2', 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig13:rulebook', 'trigger', 'Trig13', 'rulebook', '2', 'flag_dm_foot_ulcer_l12m', '=', '1', NULL),
  ('trigger:Trig13:rulebook', 'trigger', 'Trig13', 'rulebook', '3', 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig13:rulebook', 'trigger', 'Trig13', 'rulebook', '3', 'flag_amputation', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', '1', 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', '1', 'flag_active_ACEinhibitor', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', '1', 'last_potassium_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', '2', 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', '2', 'flag_active_ARBinhibitor', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', '2', 'last_potassium_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', '3', 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', '3', 'pdc_mra', 'not_null', NULL, NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', '3', 'last_potassium_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', '4', 'cohort_htn_l12m', '=', '1', NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', '4', 'pdc_thiazide', 'not_null', NULL, NULL),
  ('trigger:Trig7:rulebook', 'trigger', 'Trig7', 'rulebook', '4', 'last_potassium_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig11:rulebook', 'trigger', 'Trig11', 'rulebook', '1', 'last_lipid_panel_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig11:rulebook', 'trigger', 'Trig11', 'rulebook', '2', 'last_renal_panel_date', 'missing_or_gt', '365', NULL),
  ('trigger:Trig10:rulebook', 'trigger', 'Trig10', 'rulebook', '1', 'first_e11_date', '<=', '90', NULL),
  ('trigger:Trig10:rulebook', 'trigger', 'Trig10', 'rulebook', '2', 'first_htn_date', '<=', '90', NULL),
  ('trigger:Trig8:rulebook', 'trigger', 'Trig8', 'rulebook', '1', 'cohort_t2d_l12m', '=', '1', NULL),
  ('trigger:Trig8:rulebook', 'trigger', 'Trig8', 'rulebook', '1', 'last_dietitian_visit', 'missing_or_gt', '365', NULL),
  ('trigger:Trig8:rulebook', 'trigger', 'Trig8', 'rulebook', '1', 'last_diabeducator_visit', 'missing_or_gt', '365', NULL),
  ('cannot_tell:Trig2:any', 'cannot_tell', 'Trig2', 'any', '1', 'cohort_htn_l12m', '=', '1', 'No usable BP reading (missing or a placeholder)'),
  ('cannot_tell:Trig2:any', 'cannot_tell', 'Trig2', 'any', '1', 'Last_SystolicPressure_Value', 'is_null', NULL, 'No usable BP reading (missing or a placeholder)'),
  ('cannot_tell:Trig6:any', 'cannot_tell', 'Trig6', 'any', '1', 'cohort_t2d_l12m', '=', '1', 'No usable HbA1c result'),
  ('cannot_tell:Trig6:any', 'cannot_tell', 'Trig6', 'any', '1', 'Last_HbA1c_Value', 'is_null', NULL, 'No usable HbA1c result'),
  ('cannot_tell:Trig5:any', 'cannot_tell', 'Trig5', 'any', '1', 'cohort_t2d_l12m', '=', '1', 'No eGFR or UACR result'),
  ('cannot_tell:Trig5:any', 'cannot_tell', 'Trig5', 'any', '1', 'Last_eGFR_Value', 'is_null', NULL, 'No eGFR or UACR result'),
  ('cannot_tell:Trig5:any', 'cannot_tell', 'Trig5', 'any', '1', 'Last_UACR_Value', 'is_null', NULL, 'No eGFR or UACR result'),
  ('alert:RED:any', 'alert', 'RED', 'any', '1', 'Priority_clinical_review', '=', '1', 'Red-flag symptoms are captured on the call, not from data'),
  ('alert:RED:any', 'alert', 'RED', 'any', '2', 'flag_dka_l12m', '=', '1', 'Red-flag symptoms are captured on the call, not from data'),
  ('alert:RED:any', 'alert', 'RED', 'any', '3', 'flag_dm_hypoglycaemia_l12m', '=', '1', 'Red-flag symptoms are captured on the call, not from data'),
  ('alert:RED:any', 'alert', 'RED', 'any', '4', 'Last_SystolicPressure_Value', '>=', '180', 'Red-flag symptoms are captured on the call, not from data'),
  ('alert:RED:any', 'alert', 'RED', 'any', '5', 'Last_DiastolicPressure_Value', '>=', '110', 'Red-flag symptoms are captured on the call, not from data'),
  ('alert:RED:any', 'alert', 'RED', 'any', '6', 'Last_eGFR_Value', '<', '15', 'Red-flag symptoms are captured on the call, not from data'),
  ('alert:AMBER:any', 'alert', 'AMBER', 'any', '1', 'Trig4_post_discharge_care', '=', '1', '"eGFR falling" needs two results; the extract has only the latest'),
  ('alert:AMBER:any', 'alert', 'AMBER', 'any', '2', 'Last_HbA1c_Value', '>=', '9', '"eGFR falling" needs two results; the extract has only the latest'),
  ('alert:AMBER:any', 'alert', 'AMBER', 'any', '3', 'Last_SystolicPressure_Value', '>=', '160', '"eGFR falling" needs two results; the extract has only the latest'),
  ('alert:AMBER:any', 'alert', 'AMBER', 'any', '4', 'Last_DiastolicPressure_Value', '>=', '100', '"eGFR falling" needs two results; the extract has only the latest'),
  ('alert:AMBER:any', 'alert', 'AMBER', 'any', '5', 'pdc_any_t2d_noninsulin', '<', '0.5', '"eGFR falling" needs two results; the extract has only the latest'),
  ('alert:AMBER:any', 'alert', 'AMBER', 'any', '6', 'pdc_any_htn', '<', '0.5', '"eGFR falling" needs two results; the extract has only the latest'),
  ('alert:YELLOW:any', 'alert', 'YELLOW', 'any', '1', '_fired_triggers', '>=', '1', 'Off target or an overdue test: any trigger fired');

-- §3 Rule table: Next best action per trigger: owner, channel, done when, evidence, prerequisite, escalation
DROP TABLE IF EXISTS rule_action;
CREATE TABLE rule_action (`action_code` TEXT, `trigger_code` TEXT, `title` TEXT, `owner_role` TEXT, `channel` TEXT, `done_when` TEXT, `evidence` TEXT, `prerequisite` TEXT, `escalate_to` TEXT);
INSERT INTO rule_action VALUES
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

-- §3 Trigger states: fired / cannot tell / not fired
DROP TABLE IF EXISTS rule_trigger_state;
CREATE TABLE rule_trigger_state (`state` TEXT, `meaning` TEXT, `what_happens` TEXT, `guardrail` TEXT);
INSERT INTO rule_trigger_state VALUES
  ('fired', 'The condition is met on the raw data', 'Goes to the planner: becomes a care-plan need', 'G1'),
  ('cannot_tell', 'A value the rule needs is missing', 'Becomes a question for the nurse, asked once', 'G8'),
  ('not_fired', 'The condition is not met', 'Nothing', NULL);

-- §3 Campaign modes: automated vs business
DROP TABLE IF EXISTS rule_campaign_mode;
CREATE TABLE rule_campaign_mode (`mode` TEXT, `trigger_mode_in_kit` TEXT, `meaning` TEXT);
INSERT INTO rule_campaign_mode VALUES
  ('automated', 'all', 'Keeps every approved trigger tagged with the cohort''s diagnoses'),
  ('business', 'list', 'Keeps only the triggers listed in triggers_json');

-- §4 Within a member: Class order safety → acute → uncontrolled → barrier → verified gap → patient goal, with due days
DROP TABLE IF EXISTS rule_need_class;
CREATE TABLE rule_need_class (`class` TEXT, `sort_order` TEXT, `label` TEXT, `due_days` TEXT, `meaning` TEXT);
INSERT INTO rule_need_class VALUES
  ('safety', '1', 'Safety', '0', 'Same day; event pathway, not the cadence'),
  ('acute', '2', 'Acute event', '3', 'Due in 3 days'),
  ('unctl', '3', 'Uncontrolled', '7', 'Due in 7 days'),
  ('barrier', '4', 'Barrier', '7', 'Due in 7 days'),
  ('gap', '5', 'Verified gap', '30', 'Due in 30 days'),
  ('goal', '6', 'Patient goal', '14', 'Due in 14 days (not set in the rulebook; working default)');

-- §4 Within a member: CURRENT 1–3, NEXT 4–6, FUTURE
DROP TABLE IF EXISTS rule_slot;
CREATE TABLE rule_slot (`slot` TEXT, `from_rank` TEXT, `to_rank` TEXT, `meaning` TEXT);
INSERT INTO rule_slot VALUES
  ('CURRENT', '1', '3', 'Active needs. A nurse never carries more than three (tree step I). Each has one action.'),
  ('NEXT', '4', '6', 'Due after the first three close; promoted when one closes.'),
  ('FUTURE', '7', '99', 'Scheduled on the cadence.'),
  ('CLOSED', NULL, NULL, 'Done or declined; kept for the record (G9).');

-- §4 Across members: Queue order: safety/RED → tier → campaign priority → hours past SLA
DROP TABLE IF EXISTS rule_queue_order;
CREATE TABLE rule_queue_order (`rank` TEXT, `sort_key` TEXT, `direction` TEXT, `meaning` TEXT);
INSERT INTO rule_queue_order VALUES
  ('1', 'safety_or_red', 'desc', 'Safety flag or a RED alert first'),
  ('2', 'tier', 'desc', 'Tier 4 down to 1'),
  ('3', 'campaign_priority', 'asc', 'Campaign priority (1 first)'),
  ('4', 'hours_past_sla', 'desc', 'Most overdue against the contact SLA');

-- §4 Contact SLA: P1–P4 from alert colour, SLA days, channel
DROP TABLE IF EXISTS rule_contact_priority;
CREATE TABLE rule_contact_priority (`priority` TEXT, `alert` TEXT, `also_requires_trigger` TEXT, `sla_days` TEXT, `channel` TEXT, `meaning` TEXT);
INSERT INTO rule_contact_priority VALUES
  ('P1', 'RED', NULL, '0', 'Call', 'Same day'),
  ('P1', 'AMBER', 'Trig4', '0', 'Call', 'Same day: post-discharge (rulebook scenario 6.2)'),
  ('P2', 'AMBER', NULL, '1', 'Call', 'Next working day'),
  ('P3', 'YELLOW', NULL, '3', 'Call', 'Within 3 working days'),
  ('P4', 'GREEN', NULL, NULL, 'Digital nudge', 'No call; a digital nudge only');

-- §4 Alert colour: RED / AMBER / YELLOW / GREEN: when and response
DROP TABLE IF EXISTS rule_alert;
CREATE TABLE rule_alert (`colour` TEXT, `sort_order` TEXT, `criteria` TEXT, `response` TEXT);
INSERT INTO rule_alert VALUES
  ('RED', '1', 'Safety flag, BP ≥ 180/110, eGFR < 15, a hypoglycaemia event, or red-flag symptoms on the call', 'Same-day clinician; the script stops'),
  ('AMBER', '2', 'Post-discharge, HbA1c ≥ 9, BP ≥ 160/100, eGFR falling, PDC < 50%', 'Clinician review within 72 h'),
  ('YELLOW', '3', 'Off target but below AMBER; an overdue test or screening', 'Next touchpoint'),
  ('GREEN', '4', 'At target, nothing open', 'Routine cadence');

-- §4 Decision tree: Steps A–J as the portal shows them
DROP TABLE IF EXISTS rule_decision_step;
CREATE TABLE rule_decision_step (`step` TEXT, `name` TEXT, `what_happens` TEXT);
INSERT INTO rule_decision_step VALUES
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

-- §5 Consent gate: What is shown before consent and what is not rendered
DROP TABLE IF EXISTS rule_consent_gate;
CREATE TABLE rule_consent_gate (`item` TEXT, `before_consent` TEXT, `note` TEXT);
INSERT INTO rule_consent_gate VALUES
  ('Member header', 'shown', NULL),
  ('Why we''re calling', 'shown', NULL),
  ('Consent card', 'shown', 'Consent is logged on a recorded call only'),
  ('Member 360', 'not rendered', 'Not rendered at all, rather than hidden'),
  ('Profile review, actions and care gaps', 'not rendered', NULL),
  ('Outcome form', 'not rendered', NULL),
  ('Tasks and Timeline tabs', 'not rendered', NULL),
  ('Care plan', 'not rendered', NULL),
  ('After-consent lines of the script', 'not rendered', NULL),
  ('Any further contact after a decline', 'suppressed', 'A suppression is written; no further contact');

-- §5 The call: The ten stages of the call and the portal step for each
DROP TABLE IF EXISTS rule_call_stage;
CREATE TABLE rule_call_stage (`stage_no` TEXT, `stage` TEXT, `what_the_nurse_does` TEXT, `portal_step` TEXT);
INSERT INTO rule_call_stage VALUES
  ('1', 'Prepare', 'Reads why now; the script order is why → do → done-when', 'Queue card: why we''re calling'),
  ('2', 'Connect', 'Places the call', 'Call bar'),
  ('3', 'Screen safety', 'A red flag stops the script', 'Urgent banner; RED alert'),
  ('4', 'Consent', 'Logs consent on the recorded call', 'Consent card'),
  ('5', 'Assess', 'Asks only the cannot-tell questions', 'Review for this call'),
  ('6', 'Synthesize', 'Confirms the picture with the member', 'Review complete'),
  ('7', 'Plan', 'Agrees up to three CURRENT needs', 'Care plan actions to agree'),
  ('8', 'Close', 'Agrees the owner and the date', 'Booking; member agrees'),
  ('9', 'Follow up', 'Records the outcome; follow-ups are created', 'Outcome; next steps'),
  ('10', 'Transition', 'Hands over to the coordinator tasks', 'Actions page');

-- §5 Write-back: Outcome → engine reaction → new calendar item
DROP TABLE IF EXISTS rule_writeback;
CREATE TABLE rule_writeback (`outcome` TEXT, `need_status` TEXT, `need_slot` TEXT, `action_status` TEXT, `gap_state` TEXT, `hold_days` TEXT, `max_attempts` TEXT, `retry_after_days` TEXT, `promote_next` TEXT, `new_calendar_item` TEXT, `guardrail` TEXT);
INSERT INTO rule_writeback VALUES
  ('done', 'done', 'CLOSED', 'done', 'Reported', NULL, NULL, NULL, '1', 'Next need, due by its class', 'G7'),
  ('declined', 'declined', 'CLOSED', 'declined', NULL, '90', NULL, NULL, '1', 'Re-offer at day 90', 'G4'),
  ('not_reached', NULL, NULL, NULL, NULL, NULL, '3', '1', '0', 'Retry the next working day; P1 escalates to the lead after 3 attempts', 'G3'),
  ('carried', 'open', 'CURRENT', 'open', NULL, NULL, NULL, NULL, '0', 'None: stays CURRENT with its due date', 'G9'),
  ('agreed', 'open', NULL, 'open', 'Scheduled', NULL, NULL, NULL, '0', 'None: the action is agreed with the member', NULL),
  ('member_assertion', NULL, NULL, NULL, 'Verified', NULL, NULL, NULL, '0', 'Matched again tonight; depends on whether the trigger still fires', 'G8'),
  ('consent_granted', NULL, NULL, NULL, NULL, NULL, NULL, NULL, '0', 'Member 360 and the care plan unlock', 'G2'),
  ('consent_declined', NULL, NULL, NULL, NULL, NULL, NULL, NULL, '0', 'Suppression written; no further contact', 'G2'),
  ('claim_evidence', 'done', 'CLOSED', 'done', 'Closed', NULL, NULL, NULL, '1', 'Trigger no longer fires on the next extract', 'G1');

-- §5 Write-back: Potential → Verified → Scheduled → Reported → Closed; who moves it
DROP TABLE IF EXISTS rule_gap_state;
CREATE TABLE rule_gap_state (`state` TEXT, `sort_order` TEXT, `moved_by` TEXT, `evidence` TEXT);
INSERT INTO rule_gap_state VALUES
  ('Potential', '1', 'Nightly run', 'Trigger fired'),
  ('Verified', '2', 'Nurse', 'Confirmed with the member on the call (member assertion)'),
  ('Scheduled', '3', 'Nurse', 'Action agreed or booked'),
  ('Reported', '4', 'Nurse', 'Nurse marked it done; not yet seen in claims'),
  ('Closed', '5', 'Nightly run', 'Success criterion appears in claims (the trigger stops firing)');

-- §5 Minimum documentation: The six items of step J
DROP TABLE IF EXISTS rule_documentation;
CREATE TABLE rule_documentation (`item_no` TEXT, `item` TEXT, `kit_column` TEXT);
INSERT INTO rule_documentation VALUES
  ('1', 'Purpose and finding', 'outcome.notes; care_plan_need.evidence'),
  ('2', 'Nurse, patient and professional actions', 'action.title, action.owner_role'),
  ('3', 'Owner and due date', 'action.assignee, action.due_date'),
  ('4', 'Alert colour', 'member.alert'),
  ('5', 'Next contact', 'v_member_summary.next_touchpoint'),
  ('6', 'CURRENT / NEXT / FUTURE', 'care_plan_need.slot');

-- §1 and §6: The twelve event types the loop writes
DROP TABLE IF EXISTS rule_event_type;
CREATE TABLE rule_event_type (`event_type` TEXT, `written_by` TEXT, `when` TEXT, `kit_table` TEXT);
INSERT INTO rule_event_type VALUES
  ('COHORT', 'Builder', 'A cohort is saved or an nGQL query is loaded', 'campaign (rules_json, where_sql)'),
  ('COHORT_MEMBER', 'Cohort engine', 'Nightly, with the stable-hash holdout', 'campaign_member'),
  ('MEMBER_FEATURE', 'Nightly scan', 'Features computed from claims and labs', 'member'),
  ('MemberRisk', 'Care intelligence', 'R, tier and safety flag', 'member.r_total, tier, alert, contact_priority'),
  ('MEMBER_SIGNAL', 'Care intelligence', 'A trigger fired, cannot tell or not fired, with evidence', 'member_signal'),
  ('NUDGE_PLAN', 'Planner', 'Needs classed and ordered; NBA set', 'care_plan_need, action (care_plan)'),
  ('CLINICAL_ALERT', 'Planner', 'Alert colour and contact priority', 'member.alert, worklist'),
  ('CONSENT_EVENT', 'Portal', 'Consent logged or declined', 'member.consent, outcome.consent'),
  ('CASE_ACTION', 'Portal', 'An action agreed, done or declined on the call', 'outcome, action'),
  ('MEMBER_ASSERTION', 'Portal', 'What the member said that differs from the record', 'outcome.notes (post-demo: member_assertion table)'),
  ('DISPOSITION_EVENT', 'Portal', 'The outcome of each need on the call', 'outcome'),
  ('CARE_GAP_EVENT', 'Care intelligence', 'A gap moves state; Closed only when the claim arrives', 'care_plan_need.gap_state');

-- §8 Guardrails: G0–G10 and where each is enforced
DROP TABLE IF EXISTS rule_guardrail;
CREATE TABLE rule_guardrail (`code` TEXT, `name` TEXT, `rule` TEXT, `enforced_in` TEXT);
INSERT INTO rule_guardrail VALUES
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

-- §8 Open decisions: The five open decisions
DROP TABLE IF EXISTS rule_open_decision;
CREATE TABLE rule_open_decision (`item_no` TEXT, `decision` TEXT, `status` TEXT, `who_decides` TEXT);
INSERT INTO rule_open_decision VALUES
  ('1', 'MemberFeature tag on the graph, or features in ClickHouse with nGQL limited to claim traversals', 'Open', 'Data platform'),
  ('2', 'Clinical sign-off on tier cut-offs, AMBER/RED rules and trigger thresholds', 'Open: every rule carries status Draft', 'Clinical lead'),
  ('3', 'A separate acute red-flag pathway with an owned SLA after escalation', 'Open', 'Clinical lead'),
  ('4', 'Member crosswalk: E_LIFE_ID (claims) to PERSONID (graph)', 'Open', 'Data platform'),
  ('5', 'nGQL load limits: 60 s timeout, 250k rows, nightly only, preview 8 rows', 'Proposed', 'Data platform');
