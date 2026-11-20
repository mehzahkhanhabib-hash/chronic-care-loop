"""The rule database: rules/*.csv (the source of truth, editable in Excel) → rule_* tables, plus the evaluator.

  python3 -m backend.rules            # writes rules/rules.db and rules/rules.sql, prints a summary

The nightly engine reads every threshold, trigger, action, slot, alert, priority and write-back rule from here.
Change a CSV, restart the server (or run the nightly), and the loop follows the new rule.
"""
import csv, json, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_DIR = os.environ.get('CCL_RULES', os.path.join(ROOT, 'rules'))

DDL = """
-- Chronic Care Loop · rule database (from the CCC Rulebook, T2D and Hypertension, 20 Nov 2026)
-- Source of truth: rules/*.csv. raw extract column → condition → trigger → care-plan need (class, slot, due) → action → outcome → write-back.
CREATE TABLE IF NOT EXISTS rule_need_class (
  class       TEXT PRIMARY KEY,          -- safety | acute | unctl | barrier | gap | goal
  sort_order  INTEGER NOT NULL,          -- order inside a care plan (safety first)
  label       TEXT NOT NULL,
  due_days    INTEGER NOT NULL,          -- a need of this class is due this many days after it opens
  meaning     TEXT
);
CREATE TABLE IF NOT EXISTS rule_trigger (
  trigger_code         TEXT PRIMARY KEY, -- Trig1 … Trig13, BPU
  name                 TEXT NOT NULL,
  pathway              TEXT NOT NULL,
  class                TEXT NOT NULL REFERENCES rule_need_class(class),
  sort_order           INTEGER NOT NULL,
  raw_data_rulebook    TEXT,
  fires_when_rulebook  TEXT,
  extract_flag         TEXT,             -- extract column that already computes the trigger
  use_variant          TEXT NOT NULL CHECK (use_variant IN ('extract', 'rulebook')),
  status               TEXT
);
CREATE TABLE IF NOT EXISTS rule_condition (
  rule_id      TEXT NOT NULL,            -- <rule_type>:<target>:<variant>
  rule_type    TEXT NOT NULL,            -- trigger | cannot_tell | alert
  target       TEXT NOT NULL,            -- trigger code or alert colour
  variant      TEXT NOT NULL,            -- extract | rulebook | any
  group_no     INTEGER NOT NULL,         -- groups are OR-ed; conditions inside a group are AND-ed
  column_name  TEXT NOT NULL,            -- extract column (dates = days before the as-of date)
  op           TEXT NOT NULL CHECK (op IN ('=', '>=', '<=', '>', '<', 'is_null', 'not_null', 'missing_or_gt')),
  value        TEXT,
  note         TEXT,
  PRIMARY KEY (rule_id, group_no, column_name, op)
);
CREATE TABLE IF NOT EXISTS rule_action (
  action_code   TEXT PRIMARY KEY,
  trigger_code  TEXT NOT NULL UNIQUE REFERENCES rule_trigger(trigger_code),   -- one next best action per trigger
  title         TEXT NOT NULL,
  owner_role    TEXT NOT NULL,
  channel       TEXT NOT NULL,
  done_when     TEXT NOT NULL,           -- verified in claims
  evidence      TEXT,
  prerequisite  TEXT REFERENCES rule_trigger(trigger_code),                  -- G7: waits for this trigger's need to close
  escalate_to   TEXT
);
CREATE TABLE IF NOT EXISTS rule_slot (
  slot       TEXT PRIMARY KEY,           -- CURRENT | NEXT | FUTURE | CLOSED
  from_rank  INTEGER,
  to_rank    INTEGER,
  meaning    TEXT
);
CREATE TABLE IF NOT EXISTS rule_risk_band (
  component       TEXT NOT NULL,         -- C | M | K | U | A
  input           TEXT NOT NULL,
  band            TEXT NOT NULL,
  points          TEXT NOT NULL,
  cap             INTEGER NOT NULL,
  extract_column  TEXT,
  PRIMARY KEY (component, input, band)
);
CREATE TABLE IF NOT EXISTS rule_tier (
  tier           INTEGER PRIMARY KEY,
  label          TEXT NOT NULL,
  r_min          INTEGER NOT NULL,
  r_max          INTEGER NOT NULL,
  campaign_does  TEXT,
  cadence        TEXT NOT NULL,
  cadence_days   TEXT NOT NULL           -- contact days after baseline
);
CREATE TABLE IF NOT EXISTS rule_alert (
  colour      TEXT PRIMARY KEY,          -- RED | AMBER | YELLOW | GREEN
  sort_order  INTEGER NOT NULL,
  criteria    TEXT NOT NULL,
  response    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rule_contact_priority (
  priority               TEXT NOT NULL,  -- P1 … P4
  alert                  TEXT NOT NULL REFERENCES rule_alert(colour),
  also_requires_trigger  TEXT NOT NULL DEFAULT '',
  sla_days               INTEGER,        -- NULL = no call (digital nudge)
  channel                TEXT NOT NULL,
  meaning                TEXT,
  PRIMARY KEY (priority, alert, also_requires_trigger)
);
CREATE TABLE IF NOT EXISTS rule_queue_order (
  rank       INTEGER PRIMARY KEY,
  sort_key   TEXT NOT NULL,
  direction  TEXT NOT NULL,
  meaning    TEXT
);
CREATE TABLE IF NOT EXISTS rule_gap_state (
  state       TEXT PRIMARY KEY,          -- Potential → Verified → Scheduled → Reported → Closed
  sort_order  INTEGER NOT NULL,
  moved_by    TEXT NOT NULL,
  evidence    TEXT
);
CREATE TABLE IF NOT EXISTS rule_writeback (
  outcome            TEXT PRIMARY KEY,   -- what the nurse (or the claims) record
  need_status        TEXT,
  need_slot          TEXT,
  action_status      TEXT,
  gap_state          TEXT REFERENCES rule_gap_state(state),
  hold_days          INTEGER,
  max_attempts       INTEGER,
  retry_after_days   INTEGER,
  promote_next       INTEGER NOT NULL,
  new_calendar_item  TEXT,
  guardrail          TEXT
);
CREATE TABLE IF NOT EXISTS rule_guardrail (
  code         TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  rule         TEXT NOT NULL,
  enforced_in  TEXT
);
CREATE TABLE IF NOT EXISTS rule_decision_step (
  step          TEXT PRIMARY KEY,        -- A … J
  name          TEXT NOT NULL,
  what_happens  TEXT
);
"""
ORDER = ['rule_need_class', 'rule_trigger', 'rule_condition', 'rule_action', 'rule_slot', 'rule_risk_band', 'rule_tier', 'rule_alert',
         'rule_contact_priority', 'rule_queue_order', 'rule_gap_state', 'rule_writeback', 'rule_guardrail', 'rule_decision_step']


def read(name):
    with open(os.path.join(RULES_DIR, name + '.csv'), encoding='utf-8-sig', newline='') as f:
        return [{k: (None if v == '' else v) for k, v in r.items()} for r in csv.DictReader(f)]


def install(con):
    """(Re)load every rule table from the CSVs. Safe to run on every start."""
    for t in reversed(ORDER):
        con.execute(f'DROP TABLE IF EXISTS {t}')
    con.executescript(DDL)
    for t in ORDER:
        rows = read(t)
        if t == 'rule_contact_priority':
            for r in rows:
                r['also_requires_trigger'] = r['also_requires_trigger'] or ''
        cols = list(rows[0].keys())
        con.executemany(f'INSERT INTO {t} ({",".join(chr(34) + c + chr(34) for c in cols)}) VALUES ({",".join("?" * len(cols))})',
                        [tuple(r[c] for c in cols) for r in rows])
    con.commit()


class Rules:
    """In-memory view of the rule tables, with the condition evaluator."""

    def __init__(self):
        self.triggers = read('rule_trigger')
        self.triggers.sort(key=lambda r: int(r['sort_order']))
        self.actions = {r['trigger_code']: r for r in read('rule_action')}
        self.classes = sorted(read('rule_need_class'), key=lambda r: int(r['sort_order']))
        self.tiers = {int(r['tier']): r for r in read('rule_tier')}
        self.priority = read('rule_contact_priority')
        self.writeback = {r['outcome']: r for r in read('rule_writeback')}
        self.conditions = {}
        for r in read('rule_condition'):
            self.conditions.setdefault((r['rule_type'], r['target'], r['variant']), {}).setdefault(int(r['group_no']), []).append(r)

    @staticmethod
    def test(c, v):
        x, op = v.get(c['column_name']), c['op']
        if op == 'is_null':
            return x is None
        if op == 'not_null':
            return x is not None
        if op == 'missing_or_gt':
            return x is None or (isinstance(x, (int, float)) and x > float(c['value']))
        if x is None or not isinstance(x, (int, float)):
            return False
        y = float(c['value'])
        return {'=': x == y, '>=': x >= y, '<=': x <= y, '>': x > y, '<': x < y}[op]

    def match(self, rule_type, target, variant, v):
        groups = self.conditions.get((rule_type, target, variant))
        if not groups:
            return False, None
        for g, conds in groups.items():
            if all(self.test(c, v) for c in conds):
                return True, conds
        return False, None

    def fired(self, v):
        """[(trigger_code, 'fired' | 'cannot_tell', matched conditions)]"""
        out = []
        for t in self.triggers:
            ok, conds = self.match('trigger', t['trigger_code'], t['use_variant'], v)
            if ok:
                out.append((t['trigger_code'], 'fired', conds))
                continue
            ok, conds = self.match('cannot_tell', t['trigger_code'], 'any', v)
            if ok:
                out.append((t['trigger_code'], 'cannot_tell', conds))
        return out

    def alert(self, v, fired_codes):
        w = dict(v, _fired_triggers=float(len(fired_codes)))
        for colour in ('RED', 'AMBER', 'YELLOW'):
            if self.match('alert', colour, 'any', w)[0]:
                return colour
        return 'GREEN'

    def contact_priority(self, alert, fired_codes):
        for r in self.priority:
            if r['alert'] == alert and (not r['also_requires_trigger'] or r['also_requires_trigger'] in fired_codes):
                return r['priority']
        return 'P4'

    def tier(self, R):
        for t, r in self.tiers.items():
            if int(r['r_min']) <= R <= int(r['r_max']):
                return t
        return 4 if R > 23 else 1


def build_standalone(db_path=None, sql_path=None):
    db_path = db_path or os.path.join(RULES_DIR, 'rules.db')
    sql_path = sql_path or os.path.join(RULES_DIR, 'rules.sql')
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.execute('PRAGMA foreign_keys = ON')
    install(con)
    q = lambda v: 'NULL' if v is None else (str(v) if isinstance(v, (int, float)) else "'" + str(v).replace("'", "''") + "'")
    out = [DDL.strip(), '']
    for t in ORDER:
        cols = [c[1] for c in con.execute(f'PRAGMA table_info({t})')]
        rows = con.execute(f'SELECT * FROM {t}').fetchall()
        out.append(f'INSERT INTO {t} ({", ".join(chr(34) + c + chr(34) for c in cols)}) VALUES\n' + ',\n'.join('  (' + ', '.join(q(v) for v in r) + ')' for r in rows) + ';\n')
    open(sql_path, 'w', encoding='utf-8').write('\n'.join(out))
    bad = con.execute('PRAGMA foreign_key_check').fetchall()
    counts = {t: con.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ORDER}
    con.close()
    return {'db': db_path, 'sql': sql_path, 'tables': counts, 'foreign_key_errors': bad}


if __name__ == '__main__':
    print(json.dumps(build_standalone(), indent=1))
