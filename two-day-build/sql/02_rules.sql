-- Rule data: the CCC Rulebook (T2D and Hypertension, 20 Nov 2026). Generated from rules/*.csv by tools/gen_sql.py.

DELETE FROM rule_trigger;
INSERT INTO rule_trigger (trigger_code, name, pathway, dm_module, class, class_order, trigger_order, due_days, action_title, owner_role, channel, done_when, evidence, use_variant, status) VALUES
  ('Trig3', 'Hypoglycaemia', 'T2D', 'DM-HYPO', 'safety', 1, 1, 0, 'Same-day clinician review, hypo plan, glucagon check', 'Doctor', 'Call', 'Review note and medicine change logged', 'Clinician note; glucagon fill', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('BPU', 'BP urgent', 'HTN', 'HTN-BP', 'safety', 1, 2, 0, 'Stop the script and escalate the same day', 'Nurse → doctor', 'Call', 'Escalation closed', 'Escalation outcome', 'rulebook', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig4', 'Post-discharge care', 'T2D · HTN', 'SH-TOC', 'acute', 2, 3, 3, 'GP follow-up within 72 h; medicine reconciliation', 'Coordinator', 'Call', 'GP outpatient claim within 7 days', 'GP outpatient claim', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig1', 'HbA1c above target', 'T2D', 'DM-GLY', 'unctl', 3, 4, 7, 'Glycaemic treatment review', 'Doctor', 'Call', 'Goal, decision and next test date recorded', 'Outpatient claim + recorded goal', 'extract', 'Draft: needs clinical sign-off (rulebook §8). Extract flag fires at 6.5%: decide which variant to use'),
  ('Trig2', 'BP treatment review', 'HTN', 'HTN-BP', 'unctl', 3, 5, 7, 'Home BP recheck and clinician review', 'Nurse', 'Call', 'Readings reviewed, next BP date set', 'BP observation', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig5', 'Kidney check', 'T2D · HTN', 'SH-KID', 'unctl', 3, 6, 7, 'Book eGFR and UACR; nephrology if eGFR < 30', 'Coordinator', 'Call', 'Lab claim with a result', 'eGFR / UACR lab claim', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig9', 'Medication adherence', 'T2D · HTN', 'SH-MEDS', 'barrier', 4, 7, 7, 'Refill and barrier check; pharmacist if 3 or more classes', 'Coordinator / pharmacist', 'Call', 'Next fill dispensed within 14 days', 'Pharmacy fill', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig6', 'HbA1c test due', 'T2D', 'DM-GLY', 'gap', 5, 8, 30, 'Book HbA1c at an in-network lab', 'Coordinator', 'Call or WhatsApp', 'Lab claim', 'HbA1c lab claim', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig12', 'Eye exam due', 'T2D', 'DM-EYE', 'gap', 5, 9, 30, 'Confirm the last exam or refer', 'Nurse', 'Call', 'Report or referral claim', 'Retinal CPT 92250/92227 or referral', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig13', 'High-risk foot', 'T2D', 'DM-FOOT', 'gap', 5, 10, 30, 'Foot exam; podiatry if high risk', 'Nurse', 'Call', 'Exam claim', 'Foot CPT 2028F/G0245', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig7', 'Potassium due', 'HTN', 'HTN-K', 'gap', 5, 11, 30, 'Add K+ to the next lab order', 'Coordinator', 'Call or WhatsApp', 'Lab claim', 'Potassium lab claim', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig11', 'Annual labs', 'T2D · HTN', 'SH-LABS', 'gap', 5, 12, 30, 'One bundled lab visit', 'Coordinator', 'Call or WhatsApp', 'Lab claims', 'Lipid and creatinine lab claims', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig10', 'New diagnosis', 'T2D · HTN', 'SH-START', 'goal', 6, 13, 14, 'Baseline assessment and DSMES referral', 'Nurse', 'Call', 'Assessment documented', 'Assessment note; DSMES referral', 'extract', 'Draft: needs clinical sign-off (rulebook §8)'),
  ('Trig8', 'Nutrition and education', 'T2D', 'DM-EDU', 'goal', 6, 14, 14, 'Self-management goal, dietitian', 'Nurse', 'Call', 'Goal set and reviewed', 'Dietitian / DSMES claim', 'extract', 'Draft: needs clinical sign-off (rulebook §8)');

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

DELETE FROM rule_dm_module;
INSERT INTO rule_dm_module (module_code, programme, name, sort_order, target, metric, applies_when) VALUES
  ('DM-GLY', 'Diabetes', 'Glycaemic control', 1, 'HbA1c < 7% (individual goal up to 8%); tested every 6 months', 'HbA1c', 'has_t2d'),
  ('DM-HYPO', 'Diabetes', 'Hypoglycaemia safety', 2, 'No hypoglycaemia; rescue glucagon if on insulin or a sulfonylurea', 'Hypo events', 'has_t2d'),
  ('DM-EYE', 'Diabetes', 'Eye screening', 3, 'Retinal screen within 24 months', 'Last retinal screen', 'has_t2d'),
  ('DM-FOOT', 'Diabetes', 'Foot care', 4, 'Foot exam within 12 months; podiatry if high risk', 'Last foot exam', 'has_t2d'),
  ('DM-EDU', 'Diabetes', 'Self-management and nutrition', 5, 'Dietitian or DSMES contact within 12 months; a self-management goal', 'Last dietitian visit', 'has_t2d'),
  ('HTN-BP', 'Hypertension', 'Blood pressure control', 6, 'BP < 140/90 (< 130/80 with diabetes or CKD); BP ≥ 180/110 same day', 'Latest BP', 'has_htn'),
  ('HTN-K', 'Hypertension', 'Potassium monitoring', 7, 'K+ within 12 months on an ACEi, ARB, MRA or thiazide', 'Last potassium test', 'has_htn'),
  ('SH-KID', 'Shared', 'Kidney protection', 8, 'eGFR and UACR within 12 months; nephrology if eGFR < 30', 'eGFR / UACR', 'either'),
  ('SH-MEDS', 'Shared', 'Medicine adherence', 9, 'PDC ≥ 80%; no supply gap over 30 days', 'Lowest PDC', 'either'),
  ('SH-LABS', 'Shared', 'Annual labs', 10, 'Lipids and creatinine within 12 months', 'Last lipid panel', 'either'),
  ('SH-TOC', 'Shared', 'Transitions of care', 11, 'GP follow-up within 72 h of discharge; medicines reconciled', 'Last discharge', 'either'),
  ('SH-START', 'Shared', 'New diagnosis start', 12, 'Baseline assessment and DSMES referral within 90 days of diagnosis', 'First diagnosis', 'either');

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
