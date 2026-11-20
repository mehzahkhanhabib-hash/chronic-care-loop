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
    with open(os.path.join(ROOT, 'backend', 'schema.sql'), encoding='utf-8') as f:
        con.executescript(f.read())


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
