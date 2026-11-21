-- ════════════════════════════════════════════════════════════════════════════════════
-- Reset one member between demo rehearsals: forget what the nurse recorded, keep the extract and the rules.
-- Parameters: :member_id      Then POST /runs/rules to rebuild their plan, actions and worklist row.
-- Scoped to one member (the shard key). Never run this on a live programme.
-- ════════════════════════════════════════════════════════════════════════════════════
DELETE FROM outcome WHERE member_id = :member_id;
DELETE FROM action  WHERE member_id = :member_id;
DELETE FROM care_plan_need WHERE member_id = :member_id;
DELETE FROM worklist WHERE member_id = :member_id;
UPDATE member SET consent = 'pending' WHERE member_id = :member_id;
