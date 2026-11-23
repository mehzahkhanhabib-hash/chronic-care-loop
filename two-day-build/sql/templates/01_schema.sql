-- ════════════════════════════════════════════════════════════════════════════════════
-- Chronic Care Loop · lean schema for SingleStore (MySQL-compatible)
-- Run once:  singlestore -h <host> -u <user> -p < 01_schema.sql
--
-- 8 working tables + 1 staging table + 10 rule/reference tables.
-- SingleStore notes baked in:
--   · REFERENCE tables (rules, nurses, campaigns) are copied to every node, so joins to them are free.
--   · Member-level tables are ROWSTORE and sharded by member_id; every primary key contains member_id.
--   · SingleStore does not enforce foreign keys. The relationships are listed in comments and
--     kept by the SQL itself (anti-joins in 04_nightly.sql, member-scoped writes in 05_followup.sql).
-- Relationships:
--   member 1─* member_signal · member 1─* care_plan_need · care_plan_need 1─1 action(kind='care_plan', open)
--   action 1─* outcome · action 1─* action (parent_action_id: the follow-up chain) · member 1─1 worklist (per day)
--   care_plan_need.trigger_code → rule_trigger (one row per rulebook rule)
-- ════════════════════════════════════════════════════════════════════════════════════
CREATE DATABASE IF NOT EXISTS ccl;
USE ccl;

-- ───────── Rules and reference (REFERENCE = replicated; edit rows, not code) ─────────
CREATE REFERENCE TABLE IF NOT EXISTS run_config (
  id        INT PRIMARY KEY,                -- always 1
  as_of     DATE NOT NULL,                  -- date the extract was computed for (31 Oct 2026)
  run_date  DATE NOT NULL                   -- "today" for the nightly run and the worklist
);
CREATE REFERENCE TABLE IF NOT EXISTS rule_trigger (       -- rulebook §3: trigger → next best action
  trigger_code   VARCHAR(10) PRIMARY KEY,   -- Trig1 … Trig13, BPU
  name           VARCHAR(60) NOT NULL,
  pathway        VARCHAR(20) NOT NULL,
  class          VARCHAR(10) NOT NULL,      -- safety | acute | unctl | barrier | gap | goal
  class_label    VARCHAR(20) NOT NULL,
  class_order    INT NOT NULL,              -- care-plan order (safety first)
  trigger_order  INT NOT NULL,
  due_days       INT NOT NULL,              -- a new need is due this many days after it opens
  raw_data       VARCHAR(200),              -- rulebook §3: the raw data the rule reads
  fires_when     VARCHAR(200),              -- rulebook §3: the condition, in words (the SQL is in 04_nightly.sql)
  extract_flag   VARCHAR(60),               -- the extract column that carries the same flag, if any
  action_code    VARCHAR(12) NOT NULL,      -- ACT-… (rules/rule_action.csv)
  action_title   VARCHAR(120) NOT NULL,     -- the next best action
  owner_role     VARCHAR(40) NOT NULL,
  channel        VARCHAR(30) NOT NULL,
  done_when      VARCHAR(120) NOT NULL,     -- verified in claims
  evidence       VARCHAR(120),
  escalate_to    VARCHAR(40),
  use_variant    VARCHAR(10) NOT NULL,      -- extract (the Trig flag) | rulebook (the thresholds)
  status         VARCHAR(120)               -- clinical sign-off state
);
CREATE REFERENCE TABLE IF NOT EXISTS rule_priority (      -- rulebook §4: alert → P1–P4 and SLA
  priority       VARCHAR(2) NOT NULL,
  alert          VARCHAR(6) NOT NULL,
  needs_trigger  VARCHAR(10) NOT NULL DEFAULT '',   -- e.g. AMBER + Trig4 (post-discharge) is P1
  sla_days       INT,                               -- NULL = digital nudge, no call
  channel        VARCHAR(20) NOT NULL,
  match_order    INT NOT NULL,                      -- first match wins
  PRIMARY KEY (priority, alert, needs_trigger)
);
CREATE REFERENCE TABLE IF NOT EXISTS rule_tier (
  tier   INT PRIMARY KEY, label VARCHAR(20) NOT NULL, r_min INT NOT NULL, r_max INT NOT NULL
);
CREATE REFERENCE TABLE IF NOT EXISTS rule_cadence (       -- contact cadence by tier (days after baseline)
  tier INT NOT NULL, step INT NOT NULL, day_offset INT NOT NULL, PRIMARY KEY (tier, step)
);
CREATE REFERENCE TABLE IF NOT EXISTS rule_field (       -- the extract field catalogue (rules/rule_field.csv): what each column is and who reads it
  field          VARCHAR(80) PRIMARY KEY,   -- column name in the extract
  sql_name       VARCHAR(80) NOT NULL,      -- column name in member
  type           VARCHAR(10) NOT NULL,      -- flag | num | share | date | money | text
  field_group    VARCHAR(40) NOT NULL,
  is_loaded      TINYINT NOT NULL,          -- 1 = loaded into member
  in_layout      VARCHAR(40),               -- which extract layouts carry it, e.g. '341,377'
  read_by_rules  TEXT,                      -- rule_table:rule_key list (from rule_input)
  description    TEXT
);
CREATE REFERENCE TABLE IF NOT EXISTS rule_input (       -- rulebook input → extract field (rules/rule_input.csv): the mapping the team edits
  rule_table     VARCHAR(40) NOT NULL,      -- rule_risk_band, rule_trigger, rule_alert, rule_guardrail, …
  rule_key       VARCHAR(40) NOT NULL,      -- C/M/K/U/A, Trig1 … BPU, RED … GREEN, G0 …
  input          VARCHAR(160) NOT NULL,     -- the rulebook's words for the input
  field          VARCHAR(80) NOT NULL,      -- → rule_field.field
  role           VARCHAR(20) NOT NULL,      -- extract_flag | raw | score_input | score | safety | alert | gate | builder | targeting | display | derived
  note           TEXT,
  PRIMARY KEY (rule_table, rule_key, input, field)
);
CREATE REFERENCE TABLE IF NOT EXISTS rule_followup (      -- rulebook §5: nurse outcome → what happens next
  outcome            VARCHAR(20) PRIMARY KEY,
  action_status      VARCHAR(10),           -- the action the nurse worked
  need_status        VARCHAR(10),           -- its care-plan need
  gap_state          VARCHAR(10),           -- Potential → Verified → Scheduled → Reported → Closed
  hold_days          INT,
  followup_kind      VARCHAR(12),           -- the new action it creates (NULL = none)
  followup_title     VARCHAR(120),          -- {done_when} {action} {attempt} are filled in
  followup_due_days  INT,
  max_attempts       INT,
  promote_next       TINYINT NOT NULL,
  note               VARCHAR(200)
);
CREATE REFERENCE TABLE IF NOT EXISTS nurse (
  nurse_id VARCHAR(10) PRIMARY KEY, name VARCHAR(60) NOT NULL, role VARCHAR(40) NOT NULL, daily_capacity INT NOT NULL
);
CREATE REFERENCE TABLE IF NOT EXISTS nurse_language (     -- worklist matching: language first (rulebook §4)
  nurse_id VARCHAR(10) NOT NULL, language VARCHAR(20) NOT NULL, lang_idx INT NOT NULL,   -- 1..n within the language
  PRIMARY KEY (language, lang_idx)
);
CREATE REFERENCE TABLE IF NOT EXISTS campaign (
  campaign_id   VARCHAR(12) PRIMARY KEY,
  name          VARCHAR(80) NOT NULL,
  status        VARCHAR(10) NOT NULL,       -- Draft | Live | Paused
  priority      INT NOT NULL,               -- 1 = first; a member belongs to the highest-priority live campaign
  trigger_mode  VARCHAR(4) NOT NULL,        -- all | list
  trigger_list  VARCHAR(200),               -- 'Trig9,Trig4' when trigger_mode = list
  rules_json    TEXT,                       -- the builder's rules, as saved
  where_sql     TEXT NOT NULL,              -- the compiled cohort filter over member (built by the API, whitelisted columns only)
  holdout_pct   INT NOT NULL DEFAULT 10,
  created_at    DATETIME NOT NULL
);

-- ───────── Raw extract (staging: every column as text, exactly as received) ─────────
-- @@STAGING@@
-- ───────── Member: typed, cleaned values the rules read, plus scores ─────────
-- @@MEMBER@@
-- ───────── The loop ─────────
CREATE ROWSTORE TABLE IF NOT EXISTS campaign_member (
  member_id    VARCHAR(20) NOT NULL,
  campaign_id  VARCHAR(12) NOT NULL,
  holdout      TINYINT NOT NULL,              -- stable 10% control group: CRC32(campaign:member) % 100 < holdout_pct
  added_on     DATE NOT NULL,
  PRIMARY KEY (member_id, campaign_id)
);
CREATE ROWSTORE TABLE IF NOT EXISTS member_signal (     -- raw member → trigger, one row per trigger per run
  member_id     VARCHAR(20) NOT NULL,
  trigger_code  VARCHAR(10) NOT NULL,
  state         VARCHAR(12) NOT NULL,          -- fired | cannot_tell
  evidence      VARCHAR(400),
  run_date      DATE NOT NULL,
  PRIMARY KEY (member_id, trigger_code, run_date)
);
CREATE ROWSTORE TABLE IF NOT EXISTS care_plan_need (   -- trigger → care-plan need (one per member per trigger)
  member_id      VARCHAR(20) NOT NULL,
  trigger_code   VARCHAR(10) NOT NULL,
  class          VARCHAR(10) NOT NULL,
  class_order    INT NOT NULL,
  trigger_order  INT NOT NULL,
  slot           VARCHAR(8) NOT NULL,          -- CURRENT (top 3) | NEXT (4–6) | FUTURE | CLOSED
  status         VARCHAR(10) NOT NULL,         -- open | done | declined
  gap_state      VARCHAR(10) NOT NULL,         -- Potential | Verified | Scheduled | Reported | Closed
  due_date       DATE NOT NULL,
  hold_until     DATE,
  evidence       VARCHAR(400),
  opened_on      DATE NOT NULL,
  closed_on      DATE,
  PRIMARY KEY (member_id, trigger_code)
);
CREATE ROWSTORE TABLE IF NOT EXISTS action (    -- every piece of work: nudge, call, care-plan action, follow-up, retry, escalation
  action_id         BIGINT AUTO_INCREMENT,
  member_id         VARCHAR(20) NOT NULL,
  trigger_code      VARCHAR(10),               -- set for care-plan actions and their follow-ups
  kind              VARCHAR(12) NOT NULL,      -- nudge | call | care_plan | follow_up | retry | escalation
  title             VARCHAR(160) NOT NULL,
  channel           VARCHAR(30),
  owner_role        VARCHAR(40),
  assignee          VARCHAR(10),               -- nurse_id
  due_date          DATE NOT NULL,
  status            VARCHAR(10) NOT NULL,      -- open | done | declined
  parent_action_id  BIGINT,                    -- the action whose outcome created this one
  attempt           INT NOT NULL DEFAULT 1,
  created_by        VARCHAR(10) NOT NULL,      -- nightly | a nurse_id
  created_at        DATETIME NOT NULL,
  closed_at         DATETIME,
  PRIMARY KEY (action_id, member_id),
  SHARD KEY (member_id)
);
CREATE ROWSTORE TABLE IF NOT EXISTS outcome (   -- what the nurse recorded
  outcome_id    BIGINT AUTO_INCREMENT,
  member_id     VARCHAR(20) NOT NULL,
  action_id     BIGINT NOT NULL,
  trigger_code  VARCHAR(10),
  result        VARCHAR(20) NOT NULL,          -- a rule_followup.outcome
  reached       TINYINT,
  consent       VARCHAR(10),
  notes         VARCHAR(400),
  nurse_id      VARCHAR(10) NOT NULL,
  recorded_at   DATETIME NOT NULL,
  PRIMARY KEY (outcome_id, member_id),
  SHARD KEY (member_id)
);
CREATE ROWSTORE TABLE IF NOT EXISTS worklist (  -- today's call list, one row per member, rebuilt each run
  work_date    DATE NOT NULL,
  member_id    VARCHAR(20) NOT NULL,
  nurse_id     VARCHAR(10),
  rank_no      INT NOT NULL,                   -- order across the whole team
  nurse_rank   INT NOT NULL,                   -- order in this nurse's list
  action_id    BIGINT NOT NULL,                -- the lead action for the call
  priority     VARCHAR(2), alert VARCHAR(6), tier INT,
  reason       VARCHAR(160),
  due_by       DATE NOT NULL,
  status       VARCHAR(8) NOT NULL,            -- today | queued (over capacity: rolls to tomorrow)
  PRIMARY KEY (member_id, work_date)
);

-- ───────── Work tables used inside one run (keep UPDATEs to simple joins on member_id) ─────────
CREATE ROWSTORE TABLE IF NOT EXISTS work_member (
  member_id VARCHAR(20) PRIMARY KEY, n_fired INT DEFAULT 0, has_trig4 TINYINT DEFAULT 0, match_order INT,
  owner_campaign VARCHAR(12), owner_priority INT, trigger_mode VARCHAR(4), trigger_list VARCHAR(200),
  has_open_contact TINYINT DEFAULT 0, reached_14d TINYINT DEFAULT 0, top_need VARCHAR(160)
);
CREATE ROWSTORE TABLE IF NOT EXISTS work_rank (
  member_id VARCHAR(20) NOT NULL, trigger_code VARCHAR(10) NOT NULL, rn INT NOT NULL, PRIMARY KEY (member_id, trigger_code)
);
