-- Rule data: the CCC Rulebook (T2D and Hypertension, 20 Nov 2026). Generated from rules/*.csv by tools/gen_sql.py.

DELETE FROM rule_trigger;
INSERT INTO rule_trigger (trigger_code, name, pathway, class, class_label, class_order, trigger_order, due_days, raw_data, fires_when, extract_flag, action_code, action_title, owner_role, channel, done_when, evidence, escalate_to, use_variant, status) VALUES
  ('Trig3', 'Hypoglycaemia', 'T2D', 'safety', 'Safety', 1, 1, 0, 'ICD E16.0–E16.2, E11.64; CGM < 3.9 mmol/L', 'Any event in 12 months', 'Trig3_hypoglycemia_tx', 'ACT-HYPO', 'Same-day clinician review, hypo plan, glucagon check', 'Doctor', 'Call', 'Review note and medicine change logged', 'Clinician note; glucagon fill', 'Clinical lead', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('BPU', 'BP urgent', 'HTN', 'safety', 'Safety', 1, 2, 0, 'Home or claim BP', 'BP ≥ 180/110', NULL, 'ACT-BPU', 'Stop the script and escalate the same day', 'Nurse → doctor', 'Call', 'Escalation closed', 'Escalation outcome', 'Clinical lead', 'rulebook', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig4', 'Post-discharge care', 'T2D · HTN', 'acute', 'Acute event', 2, 3, 3, 'IP or ED encounter, discharge date', 'Discharge in the last 14 days, or 2 or more ED visits in 90 days', 'Trig4_post_discharge_care', 'ACT-POSTDC', 'GP follow-up within 72 h; medicine reconciliation', 'Coordinator', 'Call', 'GP outpatient claim within 7 days', 'GP outpatient claim', NULL, 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig1', 'HbA1c above target', 'T2D', 'unctl', 'Uncontrolled', 3, 4, 7, 'LOINC 4548-4', 'Last value ≥ individual goal (around 8%)', 'Trig1_HbA1c_above_target', 'ACT-A1C-REV', 'Glycaemic treatment review', 'Doctor', 'Call', 'Goal, decision and next test date recorded', 'Outpatient claim + recorded goal', NULL, 'extract', 'Draft: needs clinical sign-off (rulebook §8). Extract flag fires at 6.5%: decide which variant to use'),
  ('Trig2', 'BP treatment review', 'HTN', 'unctl', 'Uncontrolled', 3, 5, 7, 'SBP/DBP observations', '≥ 130/80 (DM or CKD) or ≥ 140/90', 'Trig2_HTN_tx_review', 'ACT-BP-REV', 'Home BP recheck and clinician review', 'Nurse', 'Call', 'Readings reviewed, next BP date set', 'BP observation', NULL, 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig5', 'Kidney check', 'T2D · HTN', 'unctl', 'Uncontrolled', 3, 6, 7, 'eGFR 69405-9, UACR 9318-7', 'eGFR < 60, or no eGFR/UACR in 12 months', 'Trig5_Kidney_check', 'ACT-KIDNEY', 'Book eGFR and UACR; nephrology if eGFR < 30', 'Coordinator', 'Call', 'Lab claim with a result', 'eGFR / UACR lab claim', NULL, 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig9', 'Medication adherence', 'T2D · HTN', 'barrier', 'Barrier', 4, 7, 7, 'Pharmacy fills, days supply', 'PDC < 80% over 180 days, or a gap of more than 30 days', 'Trig9_medication_adherence', 'ACT-ADH', 'Refill and barrier check; pharmacist if 3 or more classes', 'Coordinator / pharmacist', 'Call', 'Next fill dispensed within 14 days', 'Pharmacy fill', NULL, 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig6', 'HbA1c test due', 'T2D', 'gap', 'Verified gap', 5, 8, 30, 'Last HbA1c date', '> 6 months (or > 3 months if off target)', 'Trig6_HbA1c_due', 'ACT-A1C-LAB', 'Book HbA1c at an in-network lab', 'Coordinator', 'Call or WhatsApp', 'Lab claim', 'HbA1c lab claim', NULL, 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig12', 'Eye exam due', 'T2D', 'gap', 'Verified gap', 5, 9, 30, 'Retinal CPT 92250/92227', 'None in 24 months', 'Trig12_eyeexam_due', 'ACT-EYE', 'Confirm the last exam or refer', 'Nurse', 'Call', 'Report or referral claim', 'Retinal CPT 92250/92227 or referral', NULL, 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig13', 'High-risk foot', 'T2D', 'gap', 'Verified gap', 5, 10, 30, 'Foot CPT 2028F/G0245; ulcer, neuropathy, PAD', 'No exam in 12 months, or a high-risk code', 'Trig13_highriskfoot_monitor', 'ACT-FOOT', 'Foot exam; podiatry if high risk', 'Nurse', 'Call', 'Exam claim', 'Foot CPT 2028F/G0245', NULL, 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig7', 'Potassium due', 'HTN', 'gap', 'Verified gap', 5, 11, 30, 'K+ result, ACE/ARB/diuretic fills', 'On an RAAS inhibitor or diuretic with no K+ in 12 months', 'Trig7_Renal_Potassium_due', 'ACT-K', 'Add K+ to the next lab order', 'Coordinator', 'Call or WhatsApp', 'Lab claim', 'Potassium lab claim', NULL, 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig11', 'Annual labs', 'T2D · HTN', 'gap', 'Verified gap', 5, 12, 30, 'Lipids, creatinine', 'None in 12 months', 'Trig11_annual_labs_due', 'ACT-LABS', 'One bundled lab visit', 'Coordinator', 'Call or WhatsApp', 'Lab claims', 'Lipid and creatinine lab claims', NULL, 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig10', 'New diagnosis', 'T2D · HTN', 'goal', 'Patient goal', 6, 13, 14, 'First E11 / I10 claim', 'First code in the last 90 days', 'Trig10_new_diagnosis', 'ACT-NEWDX', 'Baseline assessment and DSMES referral', 'Nurse', 'Call', 'Assessment documented', 'Assessment note; DSMES referral', NULL, 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig8', 'Nutrition and education', 'T2D', 'goal', 'Patient goal', 6, 14, 14, 'No dietitian or DSMES claim', 'None in 12 months', 'Trig8_nutrition_due', 'ACT-DSMES', 'Self-management goal, dietitian', 'Nurse', 'Call', 'Goal set and reviewed', 'Dietitian / DSMES claim', NULL, 'extract', 'Draft: needs clinical sign-off (rulebook §8)');

DELETE FROM rule_priority;
INSERT INTO rule_priority (priority, alert, needs_trigger, sla_days, channel, match_order) VALUES
  ('P1', 'RED', '', '0', 'Call', 1),
  ('P1', 'AMBER', 'Trig4', '0', 'Call', 2),
  ('P2', 'AMBER', '', '1', 'Call', 3),
  ('P3', 'YELLOW', '', '3', 'Call', 4),
  ('P4', 'GREEN', '', NULL, 'Digital nudge', 5);

DELETE FROM rule_tier;
INSERT INTO rule_tier (tier, label, r_min, r_max) VALUES
  (1, 'Low', 0, 3),
  (2, 'Moderate', 4, 7),
  (3, 'High', 8, 12),
  (4, 'Very high', 13, 23);

DELETE FROM rule_cadence;
INSERT INTO rule_cadence (tier, step, day_offset) VALUES
  (1, 1, 0),
  (1, 2, 90),
  (1, 3, 180),
  (1, 4, 365),
  (2, 1, 0),
  (2, 2, 42),
  (2, 3, 90),
  (2, 4, 150),
  (2, 5, 210),
  (2, 6, 270),
  (2, 7, 365),
  (3, 1, 0),
  (3, 2, 14),
  (3, 3, 30),
  (3, 4, 60),
  (3, 5, 90),
  (3, 6, 120),
  (3, 7, 180),
  (3, 8, 270),
  (3, 9, 365),
  (4, 1, 0),
  (4, 2, 7),
  (4, 3, 14),
  (4, 4, 21),
  (4, 5, 28),
  (4, 6, 56),
  (4, 7, 84),
  (4, 8, 112),
  (4, 9, 180);

DELETE FROM rule_followup;
INSERT INTO rule_followup (outcome, action_status, need_status, gap_state, hold_days, followup_kind, followup_title, followup_due_days, max_attempts, promote_next, note) VALUES
  ('reached', 'done', NULL, NULL, NULL, 'follow_up', 'Cadence check-in', NULL, NULL, 0, 'Call completed. Next touchpoint on the tier cadence (Tier 4: 7 days, 3: 14, 2: 42, 1: 90).'),
  ('done', 'done', 'done', 'Reported', NULL, 'follow_up', 'Verify in claims: {done_when}', 14, NULL, 1, 'Need closes; next need promoted (G7). The gap closes only when the claim arrives.'),
  ('agreed', 'done', 'open', 'Scheduled', NULL, 'follow_up', 'Check it happened: {done_when}', NULL, NULL, 0, 'Member agreed. Follow-up falls on the need due date.'),
  ('declined', 'declined', 'declined', NULL, 90, 'follow_up', 'Re-offer: {action}', 90, NULL, 1, 'Held 90 days, never re-offered sooner (G4).'),
  ('not_reached', 'done', NULL, NULL, NULL, 'retry', 'Retry call (attempt {attempt} of 3)', 1, 3, 0, 'Up to 3 attempts in 5 working days; then P1 escalates to the clinical lead.'),
  ('callback', 'done', NULL, NULL, NULL, 'follow_up', 'Callback requested', 1, NULL, 0, 'Member asked to be called back.'),
  ('carried', 'open', 'open', NULL, NULL, NULL, NULL, NULL, NULL, 0, 'Stays CURRENT with its due date (G9). No new action.'),
  ('escalated', 'done', 'open', NULL, NULL, 'escalation', 'Clinician review: {action}', 0, NULL, 0, 'Red flag on the call: same-day clinician (G1b).');
