-- ════════════════════════════════════════════════════════════════════════════════════
-- Nurse action → outcome → follow-up action (rulebook §5 write-back)
-- Called by  POST /actions/{action_id}/outcome  inside one transaction.
-- Parameters: :member_id :action_id :result :reached :consent :notes :nurse_id
-- :result is one of rule_followup.outcome:
--   reached · done · agreed · declined · not_reached · callback · carried · escalated
-- Every statement is scoped to one member (the shard key), so it is cheap on SingleStore.
-- ════════════════════════════════════════════════════════════════════════════════════

-- F1 · record what the nurse did
INSERT INTO outcome (member_id, action_id, trigger_code, result, reached, consent, notes, nurse_id, recorded_at)
SELECT a.member_id, a.action_id, a.trigger_code, :result, :reached, :consent, :notes, :nurse_id, NOW()
FROM action a
WHERE a.member_id = :member_id AND a.action_id = :action_id;

-- F2 · close (or keep) the action that was worked
UPDATE action a JOIN rule_followup f ON f.outcome = :result
SET a.status = f.action_status,
    a.closed_at = CASE WHEN f.action_status = 'open' THEN NULL ELSE NOW() END
WHERE a.member_id = :member_id AND a.action_id = :action_id;

-- F3 · move its care-plan need: done → Reported (claims close it later), declined → 90-day hold, agreed → Scheduled
UPDATE care_plan_need n
JOIN action a ON a.member_id = n.member_id AND a.trigger_code = n.trigger_code
JOIN rule_followup f ON f.outcome = :result
JOIN run_config rc
SET n.status     = COALESCE(f.need_status, n.status),
    n.gap_state  = COALESCE(f.gap_state, n.gap_state),
    n.hold_until = CASE WHEN f.hold_days IS NULL THEN n.hold_until ELSE DATE_ADD(rc.run_date, INTERVAL f.hold_days DAY) END,
    n.closed_on  = CASE WHEN f.need_status IN ('done', 'declined') THEN rc.run_date ELSE n.closed_on END
WHERE a.member_id = :member_id AND a.action_id = :action_id;

-- F4 · consent captured on the call (G2). Declined: stop every open action for this member.
UPDATE member SET consent = :consent
WHERE member_id = :member_id AND :consent IN ('granted', 'declined');
UPDATE action SET status = 'declined', closed_at = NOW()
WHERE member_id = :member_id AND status = 'open' AND :consent = 'declined';

-- F5 · the follow-up: the nurse's action turns into the next action, linked by parent_action_id
INSERT INTO action (member_id, trigger_code, kind, title, channel, owner_role, assignee, due_date, status,
                    parent_action_id, attempt, created_by, created_at)
SELECT a.member_id, a.trigger_code, f.followup_kind,
       REPLACE(REPLACE(REPLACE(f.followup_title,
               '{done_when}', COALESCE(t.done_when, 'next step')),
               '{action}',    a.title),
               '{attempt}',   CAST(a.attempt + 1 AS CHAR)),
       a.channel, COALESCE(t.owner_role, 'Nurse'), a.assignee,
       CASE
         WHEN f.outcome = 'agreed'  THEN COALESCE(n.due_date, DATE_ADD(rc.run_date, INTERVAL 7 DAY))   -- check on the agreed date
         WHEN f.outcome = 'reached' THEN DATE_ADD(rc.run_date, INTERVAL COALESCE(cad.next_days, 30) DAY) -- next touchpoint on the tier's cadence
         ELSE DATE_ADD(rc.run_date, INTERVAL COALESCE(f.followup_due_days, 7) DAY)
       END,
       'open', a.action_id,
       CASE WHEN f.followup_kind = 'retry' THEN a.attempt + 1 ELSE 1 END,
       :nurse_id, NOW()
FROM action a
JOIN rule_followup f ON f.outcome = :result
JOIN run_config rc
JOIN member m ON m.member_id = a.member_id
LEFT JOIN rule_trigger t ON t.trigger_code = a.trigger_code
LEFT JOIN care_plan_need n ON n.member_id = a.member_id AND n.trigger_code = a.trigger_code
LEFT JOIN (SELECT tier, MIN(day_offset) AS next_days FROM rule_cadence WHERE day_offset > 0 GROUP BY tier) cad ON cad.tier = m.tier
WHERE a.member_id = :member_id AND a.action_id = :action_id
  AND f.followup_kind IS NOT NULL
  AND m.consent <> 'declined'
  AND (f.max_attempts IS NULL OR a.attempt < f.max_attempts)                       -- retries stop after 3
  AND (f.outcome <> 'reached' OR a.trigger_code IS NULL)                          -- cadence check-in follows a contact call
  AND NOT (a.kind = 'follow_up' AND f.outcome = 'done')                           -- a finished follow-up ends the chain
  AND (a.trigger_code IS NOT NULL OR f.outcome IN ('reached', 'not_reached', 'callback', 'escalated'));

-- F6 · P1 member not reached after 3 attempts → the clinical lead (rulebook §5)
INSERT INTO action (member_id, trigger_code, kind, title, channel, owner_role, assignee, due_date, status,
                    parent_action_id, attempt, created_by, created_at)
SELECT a.member_id, a.trigger_code, 'escalation', 'P1 member not reached after 3 attempts: clinical lead to decide',
       'Call', 'Clinical lead', 'U-0310', rc.run_date, 'open', a.action_id, 1, :nurse_id, NOW()
FROM action a JOIN member m ON m.member_id = a.member_id JOIN run_config rc
WHERE a.member_id = :member_id AND a.action_id = :action_id
  AND :result = 'not_reached' AND a.attempt >= 3 AND m.contact_priority = 'P1';

-- F7 · re-slot this member's needs: the next need moves up into CURRENT ...
DELETE FROM work_rank WHERE member_id = :member_id;
INSERT INTO work_rank (member_id, trigger_code, rn)
SELECT member_id, trigger_code, ROW_NUMBER() OVER (PARTITION BY member_id ORDER BY class_order, trigger_order)
FROM care_plan_need WHERE member_id = :member_id AND status = 'open';
UPDATE care_plan_need n JOIN work_rank r ON r.member_id = n.member_id AND r.trigger_code = n.trigger_code
SET n.slot = CASE WHEN r.rn <= 3 THEN 'CURRENT' WHEN r.rn <= 6 THEN 'NEXT' ELSE 'FUTURE' END
WHERE n.member_id = :member_id;
UPDATE care_plan_need SET slot = 'CLOSED' WHERE member_id = :member_id AND status <> 'open';

-- F8 · ... and gets its one care-plan action straight away (G7)
INSERT INTO action (member_id, trigger_code, kind, title, channel, owner_role, assignee, due_date, status, created_by, created_at)
SELECT n.member_id, n.trigger_code, 'care_plan', t.action_title, t.channel, t.owner_role, :nurse_id, n.due_date, 'open', :nurse_id, NOW()
FROM care_plan_need n
JOIN rule_trigger t ON t.trigger_code = n.trigger_code
JOIN member m ON m.member_id = n.member_id
LEFT JOIN action a ON a.member_id = n.member_id AND a.trigger_code = n.trigger_code AND a.kind IN ('care_plan', 'follow_up') AND a.status = 'open'
WHERE n.member_id = :member_id AND n.slot = 'CURRENT' AND n.status = 'open' AND a.action_id IS NULL AND m.consent <> 'declined';
