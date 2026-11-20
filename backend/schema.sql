-- Chronic Care Loop · relational backend (SQLite; PostgreSQL-compatible types and keys)
-- Groups: Ingest & reference · Population · Targeting · Care intelligence · Care operations
PRAGMA foreign_keys = ON;

-- ───────────── Ingest & reference ─────────────
-- One row per load of the member-level extract (the wide "member features" file).
CREATE TABLE IF NOT EXISTS ingest_run (
  run_id        TEXT PRIMARY KEY,
  source_file   TEXT NOT NULL,
  as_of_date    TEXT NOT NULL,          -- review date the extract was computed for (31 Oct 2026)
  row_count     INTEGER NOT NULL,
  column_count  INTEGER NOT NULL,
  loaded_at     TEXT NOT NULL
);
-- The extract row exactly as received (all 341 columns), so nothing is lost in typing.
CREATE TABLE IF NOT EXISTS src_member_row (
  run_id     TEXT NOT NULL REFERENCES ingest_run(run_id),
  member_id  TEXT NOT NULL,
  raw_json   TEXT NOT NULL,
  PRIMARY KEY (run_id, member_id)
);
-- Data-quality findings from ingest (sentinels, implausible values, score mismatches).
CREATE TABLE IF NOT EXISTS data_issue (
  issue_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id       TEXT NOT NULL REFERENCES ingest_run(run_id),
  member_id    TEXT,                    -- NULL = applies to the whole file
  column_name  TEXT,
  raw_value    TEXT,
  rule         TEXT NOT NULL,
  severity     TEXT NOT NULL            -- info | warn | error
);
-- The rule tables (rule_trigger, rule_action, rule_writeback …) are created by backend/rules.py from rules/*.csv.

-- ───────────── Population ─────────────
CREATE TABLE IF NOT EXISTS member (
  member_id       TEXT PRIMARY KEY,     -- mask_id from the extract
  gender          TEXT,
  age             INTEGER,
  nationality     TEXT,
  plan_name       TEXT,
  policy_group    TEXT,
  policy_type     TEXT,
  gwp             REAL,
  risk_premium    REAL,
  language        TEXT,                 -- not in the extract; captured on the call
  consent_status  TEXT NOT NULL DEFAULT 'pending'   -- pending | granted | declined
);
-- Feature catalogue = the extract glossary (one row per column) + builder fields + graph features.
CREATE TABLE IF NOT EXISTS feature (
  feature_key        TEXT PRIMARY KEY,
  label              TEXT NOT NULL,
  category           TEXT NOT NULL,
  description        TEXT,
  source             TEXT NOT NULL,     -- extract | derived | graph
  value_type         TEXT NOT NULL,     -- flag | num | date | text | money | share
  unit               TEXT,
  cohort_selectable  INTEGER NOT NULL,  -- 0 for intelligence outputs (risk, tier, triggers, persona): rulebook §2
  definition         TEXT,
  created_by         TEXT REFERENCES care_team_user(user_id),
  created_at         TEXT
);
-- Typed long form of every extract value (and derived values), refreshed each load.
CREATE TABLE IF NOT EXISTS member_feature (
  member_id    TEXT NOT NULL REFERENCES member(member_id),
  feature_key  TEXT NOT NULL REFERENCES feature(feature_key),
  value_num    REAL,                    -- numbers, flags, money; for dates: days before as_of
  value_text   TEXT,                    -- text; for dates: ISO yyyy-mm-dd
  as_of        TEXT NOT NULL,
  PRIMARY KEY (member_id, feature_key)
);

-- ───────────── Targeting ─────────────
CREATE TABLE IF NOT EXISTS cohort (
  cohort_id        TEXT PRIMARY KEY,
  version          INTEGER NOT NULL,
  name             TEXT NOT NULL,
  base             TEXT NOT NULL,
  logic            TEXT NOT NULL,       -- all | any
  refresh          TEXT NOT NULL,
  definition_type  TEXT NOT NULL,       -- builder | ngql
  row_count        INTEGER,
  owner            TEXT REFERENCES care_team_user(user_id),
  created_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cohort_rule (
  rule_id       TEXT PRIMARY KEY,
  cohort_id     TEXT NOT NULL REFERENCES cohort(cohort_id),
  version       INTEGER NOT NULL,
  field         TEXT NOT NULL,          -- builder field (age, dx, lab …) or x:<extract column>
  operator      TEXT,
  value         TEXT,
  value2        TEXT,
  codes         TEXT,                   -- JSON list for code / enum fields
  lab           TEXT,
  is_exclusion  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cohort_member (
  cohort_id  TEXT NOT NULL REFERENCES cohort(cohort_id),
  member_id  TEXT NOT NULL REFERENCES member(member_id),
  version    INTEGER NOT NULL,
  holdout    INTEGER NOT NULL,          -- stable-hash 10% control group
  run_at     TEXT NOT NULL,
  PRIMARY KEY (cohort_id, member_id)
);
CREATE TABLE IF NOT EXISTS campaign (
  campaign_id    TEXT PRIMARY KEY,
  name           TEXT NOT NULL,
  goal           TEXT,
  trigger_mode   TEXT NOT NULL,         -- automated | business
  triggers_json  TEXT,                  -- business mode: trigger codes kept
  channels       TEXT NOT NULL,
  nurses         INTEGER NOT NULL,
  calls_per_day  INTEGER NOT NULL,
  holdout_pct    INTEGER NOT NULL,
  start_date     TEXT NOT NULL,
  weeks          INTEGER NOT NULL,
  priority       INTEGER NOT NULL,
  status         TEXT NOT NULL,         -- Draft | Scheduled | Live
  created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS campaign_cohort (
  campaign_id  TEXT NOT NULL REFERENCES campaign(campaign_id),
  cohort_id    TEXT NOT NULL REFERENCES cohort(cohort_id),
  role         TEXT NOT NULL,           -- include | exclude
  PRIMARY KEY (campaign_id, cohort_id)
);

-- ───────────── Care intelligence (nightly) ─────────────
CREATE TABLE IF NOT EXISTS assessment (
  member_id           TEXT NOT NULL REFERENCES member(member_id),
  run_id              TEXT NOT NULL REFERENCES ingest_run(run_id),
  clinical            INTEGER, comorbid INTEGER, kidney INTEGER, utilisation INTEGER, age_sex INTEGER,
  kidney_provisional  INTEGER NOT NULL,
  r_total             INTEGER NOT NULL,
  tier                INTEGER NOT NULL, -- rulebook numbering: 1 Low … 4 Very high
  tier_label          TEXT NOT NULL,
  persona             TEXT,
  allocation          TEXT,
  priority_review     INTEGER NOT NULL, -- safety flag (DKA / hypoglycaemia)
  excluded            INTEGER NOT NULL,
  alert               TEXT NOT NULL,    -- RED | AMBER | YELLOW | GREEN
  contact_priority    TEXT NOT NULL,    -- P1 … P4
  PRIMARY KEY (member_id, run_id)
);
CREATE TABLE IF NOT EXISTS signal (
  signal_id     TEXT PRIMARY KEY,
  member_id     TEXT NOT NULL REFERENCES member(member_id),
  campaign_id   TEXT NOT NULL REFERENCES campaign(campaign_id),
  run_id        TEXT NOT NULL REFERENCES ingest_run(run_id),
  trigger_code  TEXT NOT NULL REFERENCES rule_trigger(trigger_code),
  state         TEXT NOT NULL,          -- fired | cannot_tell
  evidence      TEXT,
  status        TEXT NOT NULL           -- open | closed
);
CREATE TABLE IF NOT EXISTS care_plan (
  care_plan_id  TEXT PRIMARY KEY,
  member_id     TEXT NOT NULL UNIQUE REFERENCES member(member_id),
  pathway       TEXT NOT NULL,          -- DM | HTN | DM + HTN
  tier          INTEGER NOT NULL,
  cadence       TEXT NOT NULL,
  status        TEXT NOT NULL,
  opened_at     TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS care_plan_need (
  need_id       TEXT PRIMARY KEY,
  care_plan_id  TEXT NOT NULL REFERENCES care_plan(care_plan_id),
  signal_id     TEXT REFERENCES signal(signal_id),
  need_key      TEXT NOT NULL REFERENCES rule_trigger(trigger_code),
  class         TEXT NOT NULL,
  slot          TEXT NOT NULL,          -- CURRENT | NEXT | FUTURE | CLOSED
  title         TEXT NOT NULL,
  owner_role    TEXT NOT NULL,
  done_when     TEXT NOT NULL,
  due_date      TEXT,
  status        TEXT NOT NULL,          -- open | done | declined
  hold_until    TEXT,                   -- declined: not re-offered for 90 days (G4)
  gap_state     TEXT NOT NULL DEFAULT 'Potential' REFERENCES rule_gap_state(state),  -- Potential → Verified → Scheduled → Reported → Closed
  UNIQUE (care_plan_id, need_key)
);

-- ───────────── Care operations ─────────────
CREATE TABLE IF NOT EXISTS care_team_user (
  user_id         TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  role            TEXT NOT NULL,
  languages       TEXT,
  daily_capacity  INTEGER
);
CREATE TABLE IF NOT EXISTS action (
  action_id   TEXT PRIMARY KEY,
  member_id   TEXT NOT NULL REFERENCES member(member_id),
  need_id     TEXT REFERENCES care_plan_need(need_id),
  kind        TEXT NOT NULL,            -- call | care_plan | agreed | callback | retry | check_in
  title       TEXT NOT NULL,
  agreed      INTEGER NOT NULL DEFAULT 0,
  due_date    TEXT NOT NULL,
  assignee    TEXT REFERENCES care_team_user(user_id),
  status      TEXT NOT NULL,            -- open | done | declined
  closed_at   TEXT,
  source      TEXT NOT NULL,            -- worklist | care_intelligence | call | care_plan | portal
  created_at  TEXT NOT NULL,
  action_code TEXT REFERENCES rule_action(action_code)    -- which rulebook action this is (NULL for calls and retries)
);
CREATE UNIQUE INDEX IF NOT EXISTS action_one_per_need ON action (need_id) WHERE kind = 'care_plan';
CREATE TABLE IF NOT EXISTS contact (
  contact_id   TEXT PRIMARY KEY,
  member_id    TEXT NOT NULL REFERENCES member(member_id),
  campaign_id  TEXT REFERENCES campaign(campaign_id),
  user_id      TEXT REFERENCES care_team_user(user_id),
  started_at   TEXT NOT NULL,
  ended_at     TEXT,
  reached      INTEGER,
  consent      TEXT,                    -- granted | declined | not_asked
  response     TEXT,
  notes        TEXT
);
CREATE TABLE IF NOT EXISTS outcome (
  outcome_id    TEXT PRIMARY KEY,
  contact_id    TEXT REFERENCES contact(contact_id),
  member_id     TEXT NOT NULL REFERENCES member(member_id),
  need_id       TEXT REFERENCES care_plan_need(need_id),
  action_id     TEXT REFERENCES action(action_id),
  result        TEXT NOT NULL,          -- done | declined | not_reached | agreed | consent_granted | consent_declined
  recorded_by   TEXT REFERENCES care_team_user(user_id),
  recorded_at   TEXT NOT NULL,
  processed_at  TEXT                    -- set by the next nightly run
);
CREATE INDEX IF NOT EXISTS outcome_unprocessed ON outcome (recorded_at) WHERE processed_at IS NULL;
-- Every read and write the API makes (the "data lens").
CREATE TABLE IF NOT EXISTS event_log (
  event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  at          TEXT NOT NULL,
  actor       TEXT,
  endpoint    TEXT,
  op          TEXT NOT NULL,            -- READ | WRITE
  table_name  TEXT NOT NULL,
  detail      TEXT
);

-- ───────────── Tracking: care plan ⇄ action ⇄ outcome, one row per need ─────────────
DROP VIEW IF EXISTS v_need_tracking;
CREATE VIEW v_need_tracking AS
SELECT p.member_id, n.need_id, n.need_key AS trigger_code, t.name AS trigger_name, n.class, c.sort_order AS class_order,
       n.slot, n.status AS need_status, n.gap_state, n.due_date, n.hold_until,
       ra.action_code, ra.owner_role, ra.done_when, ra.evidence,
       a.action_id, a.assignee, a.status AS action_status, a.closed_at,
       (SELECT o.result FROM outcome o WHERE o.need_id = n.need_id ORDER BY o.recorded_at DESC LIMIT 1) AS last_outcome,
       (SELECT o.recorded_at FROM outcome o WHERE o.need_id = n.need_id ORDER BY o.recorded_at DESC LIMIT 1) AS last_outcome_at,
       CASE WHEN n.status = 'open' AND n.due_date < date('now') THEN 1 ELSE 0 END AS overdue,
       CASE WHEN n.status = 'open' AND n.slot = 'CURRENT' AND a.action_id IS NULL THEN 1 ELSE 0 END AS missing_action
FROM care_plan_need n
JOIN care_plan p USING (care_plan_id)
JOIN rule_trigger t ON t.trigger_code = n.need_key
JOIN rule_need_class c ON c.class = n.class
LEFT JOIN rule_action ra ON ra.trigger_code = n.need_key
LEFT JOIN action a ON a.need_id = n.need_id AND a.kind = 'care_plan';

DROP VIEW IF EXISTS v_loop_kpis;
CREATE VIEW v_loop_kpis AS
SELECT
  (SELECT count(*) FROM care_plan)                                                   AS care_plans,
  (SELECT count(*) FROM care_plan_need WHERE status = 'open')                        AS open_needs,
  (SELECT count(*) FROM care_plan_need WHERE status = 'open' AND slot = 'CURRENT')   AS current_needs,
  (SELECT count(*) FROM v_need_tracking WHERE missing_action = 1)                    AS current_needs_without_action,
  (SELECT count(*) FROM v_need_tracking WHERE overdue = 1)                           AS overdue_needs,
  (SELECT count(*) FROM care_plan_need WHERE gap_state = 'Reported')                 AS reported_not_yet_in_claims,
  (SELECT count(*) FROM care_plan_need WHERE gap_state = 'Closed')                   AS closed_in_claims,
  (SELECT count(*) FROM care_plan_need WHERE status = 'declined')                    AS declined_on_hold,
  (SELECT count(*) FROM contact)                                                     AS calls,
  (SELECT count(*) FROM contact WHERE reached = 1)                                   AS reached,
  (SELECT count(*) FROM member WHERE consent_status = 'granted')                     AS consented;
