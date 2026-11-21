"""Run the kit's .sql files against SingleStore (or MySQL for local testing).

  split(text)                 → list of statements (respects quotes and -- comments)
  run_file(con, path, params) → executes every statement; :name placeholders are bound from params
  for_mysql(sql)              → strips SingleStore-only keywords so the same files run on MySQL 8 for tests
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_DIR = os.path.join(os.path.dirname(HERE), 'sql')
MYSQL = os.environ.get('CCL_DIALECT', 'singlestore') == 'mysql'


def split(text):
    out, buf, q, i = [], [], None, 0
    while i < len(text):
        ch = text[i]
        if q:
            buf.append(ch)
            if ch == '\\':
                buf.append(text[i + 1]); i += 2; continue
            if ch == q:
                q = None
        elif ch in ("'", '"', '`'):
            q = ch; buf.append(ch)
        elif ch == '-' and text[i:i + 2] == '--':
            j = text.find('\n', i)
            i = len(text) if j < 0 else j
            continue
        elif ch == ';':
            s = ''.join(buf).strip()
            if s:
                out.append(s)
            buf = []
        else:
            buf.append(ch)
        i += 1
    s = ''.join(buf).strip()
    if s:
        out.append(s)
    return out


def for_mysql(sql):
    sql = re.sub(r'CREATE (REFERENCE|ROWSTORE) TABLE', 'CREATE TABLE', sql)
    sql = re.sub(r',\s*SHARD KEY \([^)]*\)', '', sql)
    sql = re.sub(r'^\s*CREATE DATABASE.*$|^\s*USE ccl\s*$', '', sql, flags=re.M)
    return sql


def bind(stmt, params):
    """:name → %(name)s for pymysql; literal % is escaped."""
    if not params:
        return stmt, None
    stmt = stmt.replace('%', '%%')
    return re.sub(r'(?<![:\w]):([a-z_]+)\b', lambda m: f'%({m.group(1)})s', stmt), params


def run_file(con, name, params=None, replace=None):
    text = open(os.path.join(SQL_DIR, name), encoding='utf-8').read()
    for k, v in (replace or {}).items():
        text = text.replace(k, v)
    if MYSQL:
        text = for_mysql(text)
    results = []
    with con.cursor() as cur:
        for stmt in split(text):
            if stmt.upper().startswith(('USE ', 'CREATE DATABASE')):
                continue
            s, p = bind(stmt, params)
            cur.execute(s, p)
            if cur.description:
                results.append(cur.fetchall())
    return results
