"""SQLite connection, event log and small helpers."""
import json, os, sqlite3, threading
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get('CCL_DB', os.path.join(ROOT, 'data', 'ccl.db'))
_lock = threading.RLock()


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def connect(path=None):
    con = sqlite3.connect(path or DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


def create_schema(con):
    from . import rules
    con.execute('PRAGMA foreign_keys = OFF')   # rule tables are reloaded from rules/*.csv on every start
    rules.install(con)
    with open(os.path.join(ROOT, 'backend', 'schema.sql'), encoding='utf-8') as f:
        con.executescript(f.read())
    for table, col, ddl in [('care_plan_need', 'gap_state', "TEXT NOT NULL DEFAULT 'Potential'"), ('action', 'action_code', 'TEXT')]:   # older databases
        if col not in [c[1] for c in con.execute(f'PRAGMA table_info({table})')]:
            con.execute(f'ALTER TABLE {table} ADD COLUMN {col} {ddl}')
    con.execute('PRAGMA foreign_keys = ON')


def rows(con, sql, args=()):
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def one(con, sql, args=()):
    r = con.execute(sql, args).fetchone()
    return dict(r) if r else None


def log(con, op, table, detail='', actor=None, endpoint=None):
    con.execute('INSERT INTO event_log (at, actor, endpoint, op, table_name, detail) VALUES (?,?,?,?,?,?)',
                (now(), actor, endpoint, op, table, detail if isinstance(detail, str) else json.dumps(detail)))


def next_id(con, table, col, prefix, width=4):
    r = con.execute(f"SELECT {col} FROM {table} WHERE {col} LIKE ? ORDER BY length({col}) DESC, {col} DESC LIMIT 1", (prefix + '%',)).fetchone()
    n = 0
    if r:
        try:
            n = int(r[0][len(prefix):])
        except ValueError:
            n = con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
    return f'{prefix}{n + 1:0{width}d}'
