-- ════════════════════════════════════════════════════════════════════════════════════
-- Setup data: run dates, the care team, and two demo campaigns. Edit freely.
-- ════════════════════════════════════════════════════════════════════════════════════
USE ccl;

REPLACE INTO run_config (id, as_of, run_date) VALUES (1, '2026-10-31', '2026-11-20');   -- API sets run_date = today in production

DELETE FROM nurse;
INSERT INTO nurse (nurse_id, name, role, daily_capacity) VALUES
  ('U-0142', 'Nadia Rahman', 'Registered nurse', 25),
  ('U-0150', 'Omar Khalid',  'Care coordinator', 25),
  ('U-0161', 'Sara Mansour', 'Registered nurse', 25),
  ('U-0310', 'Dr. Rana K.',  'Clinical lead',     0);    -- receives escalations, not calls
DELETE FROM nurse_language;
INSERT INTO nurse_language (nurse_id, language, lang_idx) VALUES
  ('U-0150', 'Arabic', 1), ('U-0161', 'Arabic', 2),
  ('U-0142', 'English', 1), ('U-0150', 'English', 2), ('U-0161', 'English', 3);

-- Campaigns. where_sql is built by the API from the builder's rules (whitelisted member columns only).
DELETE FROM campaign;
INSERT INTO campaign (campaign_id, name, status, priority, trigger_mode, trigger_list, rules_json, where_sql, holdout_pct, created_at) VALUES
  ('CMP-0101', 'Diabetes control', 'Live', 1, 'all', NULL,
   '[{"f":"dx","vs":["E11"]},{"f":"lab","l":"hba1c","op":">=","v":8}]',
   'm.has_t2d = 1 AND m.last_hba1c_value >= 8', 10, '2026-11-16 08:00:00'),
  ('CMP-0104', 'Chronic care loop', 'Live', 4, 'all', NULL,
   '[{"f":"dx","vs":["E11","I10"]}]',
   '(m.has_t2d = 1 OR m.has_htn = 1)', 10, '2026-11-16 08:00:00');
