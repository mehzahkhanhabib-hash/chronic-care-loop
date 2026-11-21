-- ════════════════════════════════════════════════════════════════════════════════════
-- Read models for the screens. The API is mostly "SELECT * FROM <view> WHERE …".
-- ════════════════════════════════════════════════════════════════════════════════════
USE ccl;

-- ── Nurse worklist: today's list, in order, with why we're calling ──
DROP VIEW IF EXISTS v_worklist;
CREATE VIEW v_worklist AS
SELECT w.work_date, w.nurse_id, nu.name AS nurse_name, w.nurse_rank, w.rank_no, w.status AS list_status,
       w.member_id, m.age, m.gender, m.language, m.plan_name, m.consent,
       w.priority, w.alert, w.tier, m.r_total,
       w.action_id, a.kind AS action_kind, a.title AS action_title, a.attempt, w.due_by,
       CASE WHEN w.due_by < rc.run_date THEN 1 ELSE 0 END AS overdue,
       (SELECT GROUP_CONCAT(t.name ORDER BY n.class_order, n.trigger_order SEPARATOR ' · ')
          FROM care_plan_need n JOIN rule_trigger t ON t.trigger_code = n.trigger_code
         WHERE n.member_id = w.member_id AND n.slot = 'CURRENT') AS current_needs
FROM worklist w
JOIN run_config rc
JOIN member m ON m.member_id = w.member_id
JOIN action a ON a.member_id = w.member_id AND a.action_id = w.action_id
LEFT JOIN nurse nu ON nu.nurse_id = w.nurse_id;

-- ── Care plan: each need with its one care-plan action and the last thing that happened ──
DROP VIEW IF EXISTS v_care_plan;
CREATE VIEW v_care_plan AS
SELECT n.member_id, n.trigger_code, t.name AS need, t.dm_module, n.class, n.slot, n.status AS need_status, n.gap_state,
       n.due_date, n.hold_until, n.evidence, t.action_title, t.owner_role, t.done_when,
       a.action_id, a.kind AS action_kind, a.title AS action_title_now, a.status AS action_status, a.assignee, a.due_date AS action_due,
       o.result AS last_outcome, o.recorded_at AS last_outcome_at,
       CASE WHEN n.status = 'open' AND n.due_date < rc.run_date THEN 1 ELSE 0 END AS overdue,
       CASE WHEN n.status = 'open' AND n.slot = 'CURRENT' AND (a.action_id IS NULL OR a.status <> 'open') THEN 1 ELSE 0 END AS missing_action
FROM care_plan_need n
JOIN run_config rc
JOIN rule_trigger t ON t.trigger_code = n.trigger_code
LEFT JOIN action a ON a.member_id = n.member_id AND a.trigger_code = n.trigger_code
     AND a.action_id = (SELECT MAX(a2.action_id) FROM action a2                     -- the need's live action: its care-plan action or the follow-up it became
                         WHERE a2.member_id = n.member_id AND a2.trigger_code = n.trigger_code AND a2.kind IN ('care_plan', 'follow_up'))
LEFT JOIN outcome o ON o.member_id = n.member_id
     AND o.outcome_id = (SELECT MAX(o2.outcome_id) FROM outcome o2 WHERE o2.member_id = n.member_id AND o2.trigger_code = n.trigger_code);

-- ── How a nurse's action became a follow-up: action → outcome → next action ──
DROP VIEW IF EXISTS v_action_chain;
CREATE VIEW v_action_chain AS
SELECT a.member_id, a.action_id, a.kind, a.title, a.status, a.due_date, a.assignee, a.attempt,
       a.parent_action_id, p.title AS came_from, po.result AS because_outcome, po.nurse_id AS recorded_by, po.recorded_at
FROM action a
LEFT JOIN action p ON p.member_id = a.member_id AND p.action_id = a.parent_action_id
LEFT JOIN outcome po ON po.member_id = a.member_id AND po.action_id = a.parent_action_id
     AND po.outcome_id = (SELECT MAX(o2.outcome_id) FROM outcome o2 WHERE o2.member_id = a.member_id AND o2.action_id = a.parent_action_id);

-- ── Bhawani's disease-management view: one row per member per programme module ──
-- status: Off target (an open safety / acute / uncontrolled need) · Due (an open barrier, gap or goal need)
--         Awaiting claims (nurse reported it done; the claim hasn't arrived) · Declined · on hold (90 days, G4) · Unknown (a value the rule needs is missing) · On track (no open need)
DROP VIEW IF EXISTS v_dm_member_module;
CREATE VIEW v_dm_member_module AS
SELECT m.member_id, d.programme, d.module_code, d.name AS module, d.sort_order, d.target, d.metric,
       CASE d.module_code
         WHEN 'DM-GLY'   THEN CONCAT('HbA1c ', COALESCE(CONCAT(CAST(ROUND(m.last_hba1c_value, 1) AS CHAR), '%'), 'not on record'),
                                     ' · tested ', COALESCE(CONCAT(DATEDIFF(rc.as_of, m.last_hba1c_date2), ' days ago'), 'never'))
         WHEN 'DM-HYPO'  THEN CASE WHEN m.flag_dm_hypoglycaemia_l12m = 1 THEN 'Hypoglycaemia in the last 12 months'
                                   WHEN m.flag_no_glucagon_last12months = 1 THEN 'On insulin / SU, no rescue glucagon'
                                   ELSE 'No event recorded' END
         WHEN 'DM-EYE'   THEN CONCAT('Retinal screen ', COALESCE(CONCAT(DATEDIFF(rc.as_of, m.last_retinal_screen_date), ' days ago'), 'not on record'))
         WHEN 'DM-FOOT'  THEN CONCAT('Foot exam ', COALESCE(CONCAT(DATEDIFF(rc.as_of, m.last_foot_exam), ' days ago'), 'not on record'))
         WHEN 'DM-EDU'   THEN CONCAT('Dietitian ', COALESCE(CONCAT(DATEDIFF(rc.as_of, m.last_dietitian_visit), ' days ago'), 'never'),
                                     ' · educator ', COALESCE(CONCAT(DATEDIFF(rc.as_of, m.last_diabeducator_visit), ' days ago'), 'never'))
         WHEN 'HTN-BP'   THEN COALESCE(CONCAT('BP ', CAST(ROUND(m.last_systolicpressure_value) AS CHAR), '/', CAST(ROUND(m.last_diastolicpressure_value) AS CHAR)), 'No usable BP reading')
         WHEN 'HTN-K'    THEN CONCAT('Potassium ', COALESCE(CONCAT(DATEDIFF(rc.as_of, m.last_potassium_date), ' days ago'), 'not on record'))
         WHEN 'SH-KID'   THEN CONCAT('eGFR ', COALESCE(CAST(ROUND(m.last_egfr_value) AS CHAR), '—'), ' · UACR ', COALESCE(CAST(ROUND(m.last_uacr_value) AS CHAR), '—'))
         WHEN 'SH-MEDS'  THEN CONCAT('Lowest PDC ', COALESCE(CONCAT(CAST(ROUND(100 * LEAST(COALESCE(m.pdc_any_t2d_noninsulin, 1), COALESCE(m.pdc_any_htn, 1))) AS CHAR), '%'), '—'))
         WHEN 'SH-LABS'  THEN CONCAT('Lipid panel ', COALESCE(CONCAT(DATEDIFF(rc.as_of, m.last_lipid_panel_date), ' days ago'), 'not on record'))
         WHEN 'SH-TOC'   THEN CONCAT('Last discharge ', COALESCE(CONCAT(DATEDIFF(rc.as_of, m.last_ip_discharge_date), ' days ago'), 'none'))
         WHEN 'SH-START' THEN CONCAT('First diagnosis ', COALESCE(CONCAT(DATEDIFF(rc.as_of, LEAST(COALESCE(m.first_e11_date, m.first_htn_date), COALESCE(m.first_htn_date, m.first_e11_date))), ' days ago'), '—'))
       END AS latest,
       CASE WHEN COALESCE(nx.n_red, 0) > 0 THEN 'Off target'
            WHEN COALESCE(nx.n_open, 0) > 0 THEN 'Due'
            WHEN COALESCE(nx.n_reported, 0) > 0 THEN 'Awaiting claims'
            WHEN COALESCE(nx.n_declined, 0) > 0 THEN 'Declined · on hold'
            WHEN COALESCE(ct.n_unknown, 0) > 0 THEN 'Unknown'
            ELSE 'On track' END AS status,
       nx.open_needs, nx.slots, nx.gap_states, nx.next_due,
       ax.next_action, ax.next_action_due, ax.owner
FROM member m
JOIN run_config rc
JOIN rule_dm_module d
  ON (d.applies_when = 'has_t2d' AND m.has_t2d = 1) OR (d.applies_when = 'has_htn' AND m.has_htn = 1)
  OR (d.applies_when = 'either' AND (m.has_t2d = 1 OR m.has_htn = 1))
LEFT JOIN (SELECT member_id, dm_module,
                  SUM(status = 'open' AND class IN ('safety', 'acute', 'unctl')) AS n_red,
                  SUM(status = 'open') AS n_open,
                  SUM(gap_state = 'Reported') AS n_reported,
                  SUM(status = 'declined') AS n_declined,
                  GROUP_CONCAT(CASE WHEN status = 'open' THEN trigger_code END ORDER BY class_order SEPARATOR ', ') AS open_needs,
                  GROUP_CONCAT(CASE WHEN status = 'open' THEN slot END ORDER BY class_order SEPARATOR ', ') AS slots,
                  GROUP_CONCAT(gap_state ORDER BY class_order SEPARATOR ', ') AS gap_states,
                  MIN(CASE WHEN status = 'open' THEN due_date END) AS next_due
             FROM care_plan_need GROUP BY member_id, dm_module) nx
  ON nx.member_id = m.member_id AND nx.dm_module = d.module_code
LEFT JOIN (SELECT s.member_id, t.dm_module, COUNT(*) AS n_unknown
             FROM member_signal s JOIN run_config rc2 ON rc2.run_date = s.run_date JOIN rule_trigger t ON t.trigger_code = s.trigger_code
            WHERE s.state = 'cannot_tell' GROUP BY s.member_id, t.dm_module) ct
  ON ct.member_id = m.member_id AND ct.dm_module = d.module_code
LEFT JOIN (SELECT a.member_id, t.dm_module,
                  SUBSTRING_INDEX(GROUP_CONCAT(a.title ORDER BY a.due_date SEPARATOR '||'), '||', 1) AS next_action,
                  MIN(a.due_date) AS next_action_due,
                  SUBSTRING_INDEX(GROUP_CONCAT(COALESCE(a.owner_role, '') ORDER BY a.due_date SEPARATOR '||'), '||', 1) AS owner
             FROM action a JOIN rule_trigger t ON t.trigger_code = a.trigger_code
            WHERE a.status = 'open' GROUP BY a.member_id, t.dm_module) ax
  ON ax.member_id = m.member_id AND ax.dm_module = d.module_code;

-- ── One line per member: the programme header Bhawani and the nurse see above the modules ──
DROP VIEW IF EXISTS v_dm_member_summary;
CREATE VIEW v_dm_member_summary AS
SELECT m.member_id, m.age, m.gender, m.language, m.consent,
       CASE WHEN m.has_t2d = 1 AND m.has_htn = 1 THEN 'Diabetes + Hypertension' WHEN m.has_t2d = 1 THEN 'Diabetes' ELSE 'Hypertension' END AS programme,
       m.r_total, m.tier, t.label AS tier_label, m.alert, m.contact_priority,
       m.clinical_score AS c, m.comorbid_complication_score AS mm, m.kidney_score AS k, m.utilization_score AS u, m.age_sex_score AS a,
       base.baseline,
       (SELECT MIN(DATE_ADD(base.baseline, INTERVAL c.day_offset DAY)) FROM rule_cadence c
         WHERE c.tier = m.tier AND DATE_ADD(base.baseline, INTERVAL c.day_offset DAY) > rc.run_date) AS next_touchpoint,
       (SELECT COUNT(*) FROM care_plan_need n WHERE n.member_id = m.member_id AND n.slot = 'CURRENT') AS current_needs,
       (SELECT COUNT(*) FROM care_plan_need n WHERE n.member_id = m.member_id AND n.status = 'open') AS open_needs
FROM member m
JOIN run_config rc
LEFT JOIN rule_tier t ON t.tier = m.tier
LEFT JOIN (SELECT member_id, MIN(opened_on) AS baseline FROM care_plan_need GROUP BY member_id) base ON base.member_id = m.member_id;

-- ── Bhawani's programme dashboard: every module across all members ──
DROP VIEW IF EXISTS v_dm_programme;
CREATE VIEW v_dm_programme AS
SELECT v.programme, v.module_code, v.module, v.sort_order, v.target,
       COUNT(*) AS members,
       SUM(v.status = 'On track') AS on_track,
       SUM(v.status = 'Due') AS due,
       SUM(v.status = 'Off target') AS off_target,
       SUM(v.status = 'Awaiting claims') AS awaiting_claims,
       SUM(v.status = 'Declined · on hold') AS declined_on_hold,
       SUM(v.status = 'Unknown') AS unknown,
       ROUND(100 * SUM(v.status = 'On track') / COUNT(*)) AS pct_on_track,
       COALESCE(g.reported, 0) AS reported_by_nurse, COALESCE(g.closed, 0) AS closed_in_claims
FROM v_dm_member_module v
LEFT JOIN (SELECT dm_module, SUM(gap_state = 'Reported') AS reported, SUM(gap_state = 'Closed') AS closed
             FROM care_plan_need GROUP BY dm_module) g ON g.dm_module = v.module_code
GROUP BY v.programme, v.module_code, v.module, v.sort_order, v.target, g.reported, g.closed;

-- ── Is the loop closing? ──
DROP VIEW IF EXISTS v_kpis;
CREATE VIEW v_kpis AS
SELECT
  (SELECT COUNT(*) FROM member)                                                        AS members,
  (SELECT COUNT(DISTINCT member_id) FROM care_plan_need)                               AS members_with_plan,
  (SELECT COUNT(*) FROM member_signal s JOIN run_config rc ON rc.run_date = s.run_date WHERE s.state = 'fired') AS triggers_fired_today,
  (SELECT COUNT(*) FROM care_plan_need WHERE status = 'open')                          AS open_needs,
  (SELECT COUNT(*) FROM care_plan_need WHERE slot = 'CURRENT')                         AS current_needs,
  (SELECT COUNT(*) FROM v_care_plan WHERE missing_action = 1)                          AS current_needs_without_action,   -- must be 0
  (SELECT COUNT(*) FROM worklist WHERE status = 'today')                               AS on_todays_list,
  (SELECT COUNT(*) FROM worklist WHERE status = 'queued')                              AS queued_over_capacity,
  (SELECT COUNT(*) FROM action WHERE status = 'open' AND kind = 'nudge')               AS digital_nudges,
  (SELECT COUNT(*) FROM action WHERE status = 'open' AND kind = 'follow_up')           AS open_follow_ups,
  (SELECT COUNT(*) FROM action WHERE status = 'open' AND kind = 'escalation')          AS open_escalations,
  (SELECT COUNT(*) FROM care_plan_need WHERE gap_state = 'Reported')                   AS reported_not_yet_in_claims,
  (SELECT COUNT(*) FROM care_plan_need WHERE gap_state = 'Closed')                     AS closed_in_claims,
  (SELECT COUNT(*) FROM member WHERE consent = 'granted')                              AS consented;
