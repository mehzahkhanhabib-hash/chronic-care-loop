"""Chronic Care Loop · thin API over SingleStore. All logic lives in the SQL files; this file only routes.

  pip install pymysql
  export S2_HOST=... S2_USER=... S2_PASSWORD=... S2_DB=ccl      (S2_PORT defaults to 3306)
  python3 server.py --port 8080

Endpoints (JSON):
  GET  /health
  POST /cohorts/estimate         {"rules": [...]}                          → live count
  POST /campaigns                {"name", "priority", "trigger_mode", "trigger_list", "rules"}  → saves + fills campaign_member
  POST /runs/nightly                                                       → 04_nightly.sql, returns KPIs
  GET  /worklist?nurse=U-0142                                              → today's list (v_worklist)
  GET  /members/{id}                                                       → header: tier, alert, priority, cadence (v_member_summary)
  GET  /members/{id}/care-plan                                             → needs + their actions (v_care_plan)
  GET  /members/{id}/rulebook                                               → the rulebook applied to this member: every rule, state, need, action (v_rulebook_member)
  GET  /members/{id}/actions                                               → action → outcome → follow-up chain (v_action_chain)
  POST /actions/{action_id}/outcome  {"member_id", "result", "reached", "consent", "notes", "nurse_id"}  → 05_followup.sql
  GET  /rulebook/programme                                                 → every rule across all members: fired, open, done, closed in claims (v_rulebook_programme)
  GET  /kpis                                                               → v_kpis
  GET  /rules                                                              → every rule table
"""
import datetime, decimal, json, os, re, sys, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import pymysql
import sqlkit


def connect():
    return pymysql.connect(host=os.environ.get('S2_HOST', '127.0.0.1'), port=int(os.environ.get('S2_PORT', 3306)),
                           user=os.environ.get('S2_USER', 'root'), password=os.environ.get('S2_PASSWORD', ''),
                           database=os.environ.get('S2_DB', 'ccl'), autocommit=False, local_infile=True,
                           cursorclass=pymysql.cursors.DictCursor)


def rows(con, sql, args=None):
    with con.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


# ───────── cohort rules → SQL (whitelisted columns and operators only) ─────────
DX = {'E11': 'm.has_t2d = 1', 'I10': 'm.has_htn = 1', 'N18': 'm.flag_ckd = 1', 'E78': 'm.flag_dyslipidemia_l12m = 1', 'E66': 'm.flag_obesity = 1',
      'I25': 'm.flag_ischemic_heart_disease = 1', 'I50': 'm.flag_heart_failure = 1', 'I63': 'm.flag_stroke = 1'}
NUM = {'age': 'm.age', 'ip': 'm.ip_admissions_l12m', 'ed': 'm.ed_visits_l12m', 'cost': 'm.l12m_payable_diaborhtnrelated',
       'pdc': '100 * LEAST(COALESCE(m.pdc_any_t2d_noninsulin, 1), COALESCE(m.pdc_any_htn, 1))'}
LAB = {'hba1c': 'm.last_hba1c_value', 'egfr': 'm.last_egfr_value', 'uacr': 'm.last_uacr_value', 'sbp': 'm.last_systolicpressure_value', 'bmi': 'm.last_measuredbmi_value'}
OPS = {'≥': '>=', '>=': '>=', '≤': '<=', '<=': '<=', '=': '=', '>': '>', '<': '<'}


def compile_rule(r):
    f, op = r.get('f'), OPS.get(r.get('op', '>='))
    if f == 'dx':
        parts = [DX[c] for c in r.get('vs', []) if c in DX]
        return '(' + ' OR '.join(parts) + ')' if parts else None
    if f == 'gender' and r.get('vs'):
        return "m.gender IN (" + ', '.join("'F'" if v == 'F' else "'M'" for v in r['vs']) + ')'
    if f == 'optout':
        return "m.consent = 'declined'"
    col = NUM.get(f) or (LAB.get(r.get('l')) if f == 'lab' else None)
    if not col or not op:
        return None
    if r.get('op') == 'between':
        return f'{col} BETWEEN {float(r["v"])} AND {float(r["v2"])}'
    return f'{col} {op} {float(r["v"])}'        # float() rejects anything that is not a number


def where_of(rules, exclude=()):
    inc = [w for w in (compile_rule(r) for r in rules) if w]
    exc = [w for w in (compile_rule(r) for r in exclude) if w]
    return ' AND '.join(inc + [f'NOT ({w})' for w in exc]) or '1 = 1'


# ───────── routes ─────────
def health(con, q, b):
    return rows(con, 'SELECT (SELECT COUNT(*) FROM member) AS members, run_date, as_of FROM run_config WHERE id = 1')[0]


def estimate(con, q, b):
    where = where_of(b.get('rules', []), b.get('exclude', []))
    total = rows(con, 'SELECT COUNT(*) AS n FROM member m')[0]['n']
    n = rows(con, f'SELECT COUNT(*) AS n FROM member m WHERE {where}')[0]['n']
    return {'base': total, 'n': n, 'where_sql': where}


def refresh_campaign(con, c):
    with con.cursor() as cur:
        cur.execute('DELETE FROM campaign_member WHERE campaign_id = %s', (c['campaign_id'],))
        cur.execute(f"""INSERT INTO campaign_member (member_id, campaign_id, holdout, added_on)
                        SELECT m.member_id, %s, CASE WHEN CRC32(CONCAT(%s, ':', m.member_id)) %% 100 < %s THEN 1 ELSE 0 END, rc.run_date
                        FROM member m JOIN run_config rc WHERE {c['where_sql']}""", (c['campaign_id'], c['campaign_id'], c['holdout_pct']))


def save_campaign(con, q, b):
    cid = b.get('campaign_id') or 'CMP-%04d' % (rows(con, 'SELECT COUNT(*) AS n FROM campaign')[0]['n'] + 101)
    c = {'campaign_id': cid, 'name': b.get('name') or cid, 'status': b.get('status', 'Live'), 'priority': int(b.get('priority', 9)),
         'trigger_mode': 'list' if b.get('trigger_list') else 'all', 'trigger_list': ','.join(b.get('trigger_list') or []) or None,
         'rules_json': json.dumps(b.get('rules', [])), 'where_sql': where_of(b.get('rules', []), b.get('exclude', [])), 'holdout_pct': int(b.get('holdout_pct', 10))}
    with con.cursor() as cur:
        cur.execute('REPLACE INTO campaign (campaign_id, name, status, priority, trigger_mode, trigger_list, rules_json, where_sql, holdout_pct, created_at) '
                    'VALUES (%(campaign_id)s, %(name)s, %(status)s, %(priority)s, %(trigger_mode)s, %(trigger_list)s, %(rules_json)s, %(where_sql)s, %(holdout_pct)s, NOW())', c)
    refresh_campaign(con, c)
    con.commit()
    return dict(c, members=rows(con, 'SELECT COUNT(*) AS n FROM campaign_member WHERE campaign_id = %s AND holdout = 0', (cid,))[0]['n'])


def nightly(con, q, b):
    for c in rows(con, "SELECT * FROM campaign WHERE status = 'Live'"):
        refresh_campaign(con, c)
    sqlkit.run_file(con, '04_nightly.sql')
    con.commit()
    return rows(con, 'SELECT * FROM v_kpis')[0]


def worklist(con, q, b):
    nurse = (q.get('nurse') or [None])[0]
    return rows(con, 'SELECT * FROM v_worklist' + (' WHERE nurse_id = %s' if nurse else '') + ' ORDER BY nurse_id, nurse_rank', (nurse,) if nurse else None)


def member(con, q, b, mid):
    s = rows(con, 'SELECT * FROM v_member_summary WHERE member_id = %s', (mid,))
    if not s:
        raise KeyError(mid)
    return dict(s[0], signals=rows(con, 'SELECT s.trigger_code, t.name, s.state, s.evidence FROM member_signal s JOIN run_config rc ON rc.run_date = s.run_date '
                                        'JOIN rule_trigger t ON t.trigger_code = s.trigger_code WHERE s.member_id = %s ORDER BY t.class_order, t.trigger_order', (mid,)))


def care_plan(con, q, b, mid):
    return rows(con, "SELECT * FROM v_care_plan WHERE member_id = %s ORDER BY FIELD(slot, 'CURRENT', 'NEXT', 'FUTURE', 'CLOSED'), due_date", (mid,))


def rulebook_member(con, q, b, mid):
    return {'summary': member(con, q, b, mid), 'rules': rows(con, 'SELECT * FROM v_rulebook_member WHERE member_id = %s ORDER BY class_order, trigger_order', (mid,))}


def actions(con, q, b, mid):
    return rows(con, 'SELECT * FROM v_action_chain WHERE member_id = %s ORDER BY action_id', (mid,))


def outcome(con, q, b, action_id):
    p = {'action_id': int(action_id), 'member_id': b['member_id'], 'result': b['result'], 'reached': b.get('reached'),
         'consent': b.get('consent'), 'notes': b.get('notes'), 'nurse_id': b.get('nurse_id', 'U-0142')}
    if not rows(con, 'SELECT 1 FROM rule_followup WHERE outcome = %s', (p['result'],)):
        raise ValueError('result must be one of rule_followup.outcome')
    before = rows(con, 'SELECT COALESCE(MAX(action_id), 0) AS m FROM action WHERE member_id = %s', (p['member_id'],))[0]['m']
    try:
        sqlkit.run_file(con, '05_followup.sql', p)
        con.commit()
    except Exception:
        con.rollback()
        raise
    return {'new_actions': rows(con, 'SELECT * FROM v_action_chain WHERE member_id = %s AND action_id > %s', (p['member_id'], before)),
            'care_plan': care_plan(con, q, b, p['member_id'])}


ROUTES = [
    ('GET', r'/health', health), ('POST', r'/cohorts/estimate', estimate), ('POST', r'/campaigns', save_campaign),
    ('POST', r'/runs/nightly', nightly), ('GET', r'/worklist', worklist),
    ('GET', r'/members/(?P<mid>[\w-]+)', member), ('GET', r'/members/(?P<mid>[\w-]+)/care-plan', care_plan),
    ('GET', r'/members/(?P<mid>[\w-]+)/rulebook', rulebook_member), ('GET', r'/members/(?P<mid>[\w-]+)/actions', actions),
    ('POST', r'/actions/(?P<action_id>\d+)/outcome', outcome),
    ('GET', r'/rulebook/programme', lambda con, q, b: rows(con, 'SELECT * FROM v_rulebook_programme ORDER BY class_order, trigger_order')),
    ('GET', r'/kpis', lambda con, q, b: rows(con, 'SELECT * FROM v_kpis')[0]),
    ('GET', r'/rules', lambda con, q, b: {t: rows(con, f'SELECT * FROM {t}') for t in
                                         ('rule_trigger', 'rule_priority', 'rule_tier', 'rule_cadence', 'rule_followup')}),
]


def jsonable(o):
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    if isinstance(o, decimal.Decimal):
        return float(o)
    return str(o)


class Handler(BaseHTTPRequestHandler):
    def _go(self, method):
        u = urlparse(self.path)
        body = {}
        if method == 'POST':
            n = int(self.headers.get('Content-Length') or 0)
            body = json.loads(self.rfile.read(n) or b'{}')
        for m, rx, fn in ROUTES:
            hit = re.fullmatch(rx, u.path)
            if m == method and hit:
                con = connect()
                try:
                    return self._send(200, fn(con, parse_qs(u.query), body, **hit.groupdict()))
                except KeyError as e:
                    return self._send(404, {'error': f'not found: {e}'})
                except ValueError as e:
                    return self._send(400, {'error': str(e)})
                except Exception as e:
                    traceback.print_exc()
                    return self._send(500, {'error': f'{type(e).__name__}: {e}'})
                finally:
                    con.close()
        self._send(404, {'error': 'no such endpoint'})

    def _send(self, status, obj):
        data = json.dumps(obj, default=jsonable).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')       # the HTML apps call this from another origin in the demo
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        self._go('GET')

    def do_POST(self):
        self._go('POST')


if __name__ == '__main__':
    port = int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else 8080
    print(f'CCL API on http://localhost:{port}/')
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
