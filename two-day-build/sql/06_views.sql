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
SELECT n.member_id, n.trigger_code, t.name AS need, n.class, t.class_label, n.slot, n.status AS need_status, n.gap_state,
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

-- ── The rulebook applied to one member: one row per rule (rule_trigger) the member is in scope for ──
-- Reads left to right exactly as the rulebook does: raw data → fires when → fired? → need (slot, status, gap) → next best action → done when.
-- state:  fired · cannot tell (a needed value is missing, G8) · not fired
-- status: Open · Awaiting claims (nurse reported done, claim not yet seen) · Declined · on hold (90 days, G4) · Closed in claims · Unknown · Not triggered
DROP VIEW IF EXISTS v_rulebook_member;
CREATE VIEW v_rulebook_member AS
SELECT m.member_id, t.trigger_code, t.name AS rule_name, t.pathway, t.class, t.class_label, t.class_order, t.trigger_order,
       t.raw_data, t.fires_when, t.use_variant,
       COALESCE(s.state, 'not fired') AS state, s.evidence,
       n.slot, n.status AS need_status, n.gap_state, n.due_date AS need_due, n.hold_until,
       CASE WHEN n.status = 'open' AND n.class IN ('safety', 'acute', 'unctl') THEN 'Open · off target'
            WHEN n.status = 'open'                                               THEN 'Open'
            WHEN n.gap_state = 'Reported'                                        THEN 'Awaiting claims'
            WHEN n.status = 'declined'                                           THEN 'Declined · on hold'
            WHEN n.gap_state = 'Closed'                                          THEN 'Closed in claims'
            WHEN s.state = 'cannot_tell'                                         THEN 'Unknown'
            ELSE 'Not triggered' END AS status,
       t.action_code, t.action_title AS next_best_action, t.owner_role, t.channel, t.done_when, t.escalate_to,
       a.action_id, a.kind AS action_kind, a.title AS action_now, a.status AS action_status, a.due_date AS action_due, a.assignee,
       t.status AS rule_status
FROM member m
JOIN run_config rc
JOIN rule_trigger t
  ON (t.pathway = 'T2D' AND m.has_t2d = 1) OR (t.pathway = 'HTN' AND m.has_htn = 1)
  OR (t.pathway NOT IN ('T2D', 'HTN') AND (m.has_t2d = 1 OR m.has_htn = 1))
LEFT JOIN member_signal s ON s.member_id = m.member_id AND s.trigger_code = t.trigger_code AND s.run_date = rc.run_date
LEFT JOIN care_plan_need n ON n.member_id = m.member_id AND n.trigger_code = t.trigger_code
LEFT JOIN action a ON a.member_id = m.member_id AND a.trigger_code = t.trigger_code AND a.status = 'open'
     AND a.action_id = (SELECT MAX(a2.action_id) FROM action a2
                         WHERE a2.member_id = m.member_id AND a2.trigger_code = t.trigger_code AND a2.status = 'open' AND a2.kind IN ('care_plan', 'follow_up'));

-- ── One line per member: the header above the rulebook and the care plan ──
DROP VIEW IF EXISTS v_member_summary;
CREATE VIEW v_member_summary AS
SELECT m.member_id, m.age, m.gender, m.language, m.consent,
       CASE WHEN m.has_t2d = 1 AND m.has_htn = 1 THEN 'T2D + HTN' WHEN m.has_t2d = 1 THEN 'T2D' ELSE 'HTN' END AS pathway,
       m.r_total, m.tier, t.label AS tier_label, m.alert, m.contact_priority,
       m.clinical_score AS c, m.comorbid_complication_score AS mm, m.kidney_score AS k, m.utilization_score AS u, m.age_sex_score AS a,
       base.baseline,
       (SELECT MIN(DATE_ADD(base.baseline, INTERVAL c.day_offset DAY)) FROM rule_cadence c
         WHERE c.tier = m.tier AND DATE_ADD(base.baseline, INTERVAL c.day_offset DAY) > rc.run_date) AS next_touchpoint,
       (SELECT COUNT(*) FROM care_plan_need n WHERE n.member_id = m.member_id AND n.slot = 'CURRENT') AS current_needs,
       (SELECT COUNT(*) FROM care_plan_need n WHERE n.member_id = m.member_id AND n.status = 'open') AS open_needs,
       (SELECT COUNT(*) FROM member_signal s WHERE s.member_id = m.member_id AND s.run_date = rc.run_date AND s.state = 'fired') AS rules_fired
FROM member m
JOIN run_config rc
LEFT JOIN rule_tier t ON t.tier = m.tier
LEFT JOIN (SELECT member_id, MIN(opened_on) AS baseline FROM care_plan_need GROUP BY member_id) base ON base.member_id = m.member_id;

-- ── The rulebook across all members: one row per rule. Nurse-reported vs closed in claims is the measure of impact. ──
DROP VIEW IF EXISTS v_rulebook_programme;
CREATE VIEW v_rulebook_programme AS
SELECT v.trigger_code, v.rule_name, v.pathway, v.class, v.class_label, v.class_order, v.trigger_order, v.fires_when, v.next_best_action, v.owner_role, v.done_when,
       COUNT(*) AS in_scope,
       SUM(v.state = 'fired') AS fired,
       SUM(v.state = 'cannot_tell') AS cannot_tell,
       SUM(v.need_status = 'open') AS open_needs,
       SUM(v.slot = 'CURRENT') AS in_current,
       SUM(v.gap_state = 'Reported') AS reported_by_nurse,
       SUM(v.gap_state = 'Closed') AS closed_in_claims,
       SUM(v.need_status = 'declined') AS declined,
       ROUND(100 * SUM(v.state = 'fired') / COUNT(*)) AS pct_fired,
       v.rule_status
FROM v_rulebook_member v
GROUP BY v.trigger_code, v.rule_name, v.pathway, v.class, v.class_label, v.class_order, v.trigger_order, v.fires_when, v.next_best_action, v.owner_role, v.done_when, v.rule_status;

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

-- ── Care intelligence: which extract fields feed each rule (metadata, from rule_input ⋈ rule_field). The screen reads it instead of a hard-coded list. ──
DROP VIEW IF EXISTS v_rule_input;
CREATE VIEW v_rule_input AS
SELECT i.rule_table, i.rule_key, i.input, i.role, f.field, f.sql_name, f.type, f.field_group, f.is_loaded, f.in_layout, f.description
FROM rule_input i
JOIN rule_field f ON f.field = i.field;
