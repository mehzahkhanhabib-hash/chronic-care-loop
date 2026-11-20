"""Chronic Care Loop API + static host (Python standard library only).

  python3 -m backend.server [--port 8000]      → http://localhost:8000/
"""
import json, os, re, sys, traceback
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from . import store, cohorts, engine, views
from .reference import TRIGGERS, TIERS, CARE_TEAM, RUN_DATE, AS_OF, PORTAL_CODE

DIST = os.path.join(store.ROOT, 'dist')
ROUTES = []


def route(method, pattern):
    def deco(fn):
        ROUTES.append((method, re.compile('^' + pattern + '$'), fn))
        return fn
    return deco


class ApiError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status = status


# ───────────── reference & health ─────────────
@route('GET', '/api/health')
def health(con, q, body):
    run = views.latest_run(con)
    return {'ok': True, 'run_id': run, 'as_of': AS_OF, 'run_date': RUN_DATE,
            'members': con.execute('SELECT count(*) FROM member').fetchone()[0],
            'care_plans': con.execute('SELECT count(*) FROM care_plan').fetchone()[0]}


@route('GET', '/api/meta')
def meta(con, q, body):
    return {'triggers': store.rows(con, 'SELECT * FROM trigger_def ORDER BY sort_order'), 'portal_codes': PORTAL_CODE,
            'tiers': {k: {'label': v[0], 'cadence': v[1]} for k, v in TIERS.items()},
            'care_team': store.rows(con, 'SELECT * FROM care_team_user'), 'ingest_runs': store.rows(con, 'SELECT * FROM ingest_run ORDER BY loaded_at DESC')}


@route('GET', '/api/features')
def features(con, q, body):
    term = (q.get('q') or [''])[0].lower()
    rows = store.rows(con, '''SELECT f.feature_key, f.label, f.category, f.description, f.source, f.value_type, f.unit, f.cohort_selectable,
               (SELECT count(*) FROM member_feature mf WHERE mf.feature_key = f.feature_key AND (f.value_type <> 'flag' OR mf.value_num = 1)) AS members
               FROM feature f WHERE f.cohort_selectable = 1 ORDER BY f.category, f.feature_key''')
    if term:
        words = term.split()
        rows = [r for r in rows if all(w in (r['feature_key'] + ' ' + r['label'] + ' ' + (r['description'] or '')).lower() for w in words)]
    store.log(con, 'READ', 'feature', f'search "{term}" → {len(rows)}', 'builder', '/api/features')
    return {'features': rows[:int((q.get('limit') or ['60'])[0])], 'total': len(rows)}


# ───────────── cohort & campaign builder ─────────────
@route('POST', '/api/cohorts/estimate')
def estimate(con, q, body):
    return cohorts.estimate(con, body)


def cohort_out(con, c):
    d = cohorts.definition(con, c['cohort_id'])
    return {'id': c['cohort_id'], 'name': c['name'], 'base': c['base'], 'n': c['row_count'] or 0, 'refresh': c['refresh'], 'owner': c['owner'], 'ver': c['version'],
            'src': 'nGQL' if c['definition_type'] == 'ngql' else 'Builder', 'rules': {'logic': d['logic'], 'inc': d['inc'], 'exc': d['exc']},
            'holdout': con.execute('SELECT count(*) FROM cohort_member WHERE cohort_id=? AND holdout=1', (c['cohort_id'],)).fetchone()[0],
            'versions': [{'v': c['version'], 'date': c['created_at'][:10], 'n': c['row_count'] or 0, 'note': 'Saved in builder'}]}


@route('GET', '/api/cohorts')
def list_cohorts(con, q, body):
    store.log(con, 'READ', 'cohort', 'library', 'builder', '/api/cohorts')
    return {'cohorts': [cohort_out(con, c) for c in store.rows(con, 'SELECT * FROM cohort ORDER BY cohort_id')]}


@route('POST', '/api/cohorts')
def save_cohort(con, q, body):
    if not body.get('inc'):
        raise ApiError(400, 'A cohort needs at least one include rule')
    cid = body.get('id') or store.next_id(con, 'cohort', 'cohort_id', 'COH-0', 3)
    with store._lock:
        r = engine.save_cohort(con, cid, body.get('name') or 'Untitled cohort', body.get('inc', []), body.get('exc', []), body.get('base', 'daman'),
                               body.get('logic', 'all'), body.get('refresh', 'Nightly'), definition_type='ngql' if body.get('src') == 'nGQL' else 'builder')
        con.commit()
    return dict(r, cohort=cohort_out(con, store.one(con, 'SELECT * FROM cohort WHERE cohort_id=?', (cid,))))


def campaign_out(con, c):
    cc = store.rows(con, 'SELECT * FROM campaign_cohort WHERE campaign_id=?', (c['campaign_id'],))
    reach = len(engine.campaign_members(con, c['campaign_id']))
    return {'id': c['campaign_id'], 'name': c['name'], 'goal': c['goal'], 'inc': [x['cohort_id'] for x in cc if x['role'] == 'include'],
            'exc': [x['cohort_id'] for x in cc if x['role'] == 'exclude'], 'start': c['start_date'], 'weeks': c['weeks'], 'prio': c['priority'],
            'mode': c['trigger_mode'], 'trig': json.loads(c['triggers_json'] or '[]'), 'ch': [x.strip() for x in c['channels'].split(',') if x.strip()],
            'nurses': c['nurses'], 'calls': c['calls_per_day'], 'hold': c['holdout_pct'], 'status': c['status'], 'reach': reach,
            'signals': con.execute("SELECT count(*) FROM signal WHERE campaign_id=? AND status='open'", (c['campaign_id'],)).fetchone()[0]}


@route('GET', '/api/campaigns')
def list_campaigns(con, q, body):
    store.log(con, 'READ', 'campaign', 'list', 'builder', '/api/campaigns')
    return {'campaigns': [campaign_out(con, c) for c in store.rows(con, 'SELECT * FROM campaign ORDER BY priority, campaign_id')]}


@route('POST', '/api/campaigns')
def save_campaign(con, q, body):
    if not body.get('inc'):
        raise ApiError(400, 'A campaign needs at least one cohort')
    cid = body.get('id') or store.next_id(con, 'campaign', 'campaign_id', 'CMP-0', 3)
    status = body.get('status') or ('Live' if (body.get('start') or RUN_DATE) <= RUN_DATE else 'Scheduled')
    with store._lock:
        engine.save_campaign(con, cid, body.get('name') or cid, body.get('goal'), body.get('mode', 'automated'), body.get('trig') if body.get('mode') == 'business' else None,
                             ', '.join(body.get('ch') or ['Voice']), int(body.get('nurses') or 1), int(body.get('calls') or 25), status, int(body.get('prio') or 9),
                             body['inc'], body.get('exc', []), int(body.get('hold', 10)), body.get('start') or RUN_DATE, int(body.get('weeks') or 8))
        con.commit()
    return {'campaign': campaign_out(con, store.one(con, 'SELECT * FROM campaign WHERE campaign_id=?', (cid,)))}


# ───────────── care intelligence ─────────────
@route('POST', '/api/runs/nightly')
def nightly(con, q, body):
    return engine.run(con, actor=body.get('actor', 'U-0310'))


@route('GET', '/api/intel')
def intel(con, q, body):
    camp = (q.get('campaign') or [None])[0]
    recs = views.portal_members(con)
    if camp:
        recs = [r for r in recs if any(s['campaign'] == camp for s in r['live']['sig'])]
    store.log(con, 'READ', 'assessment', f'{len(recs)} members (signals, needs)', 'U-0310', '/api/intel')
    return {'members': [views.intel_record(r, i) for i, r in enumerate(recs)]}


# ───────────── care coordinator portal ─────────────
@route('GET', '/api/portal/members')
def portal_members(con, q, body):
    recs = views.portal_members(con)
    store.log(con, 'READ', 'care_plan_need', f'{len(recs)} members for the worklist', 'U-0142', '/api/portal/members')
    return {'members': recs}


@route('POST', '/api/portal/event')
def portal_event(con, q, body):
    if not body.get('member_id'):
        raise ApiError(400, 'member_id is required')
    with store._lock:
        try:
            r = engine.record(con, body)
        except KeyError as e:
            raise ApiError(404, f'unknown {e}')
    return dict(r, member=views.portal_members(con, [body['member_id']], only_active=False)[0])


@route('GET', '/api/actions')
def actions(con, q, body):
    who = (q.get('assignee') or [None])[0]
    sql = 'SELECT a.*, u.name AS assignee_name FROM action a LEFT JOIN care_team_user u ON u.user_id = a.assignee'
    rows = store.rows(con, sql + (' WHERE a.assignee = ?' if who else '') + ' ORDER BY a.status, a.due_date', (who,) if who else ())
    return {'actions': rows}


@route('GET', '/api/care-plans')
def care_plans(con, q, body):
    plans = store.rows(con, 'SELECT * FROM care_plan ORDER BY care_plan_id')
    needs = store.rows(con, 'SELECT * FROM care_plan_need ORDER BY care_plan_id, slot, need_id')
    for p in plans:
        p['needs'] = [n for n in needs if n['care_plan_id'] == p['care_plan_id']]
    return {'care_plans': plans}


@route('GET', r'/api/members/(?P<mid>[\w-]+)')
def member(con, q, body, mid):
    m = store.one(con, 'SELECT * FROM member WHERE member_id = ?', (mid,))
    if not m:
        raise ApiError(404, 'unknown member')
    raw = store.one(con, 'SELECT raw_json FROM src_member_row WHERE member_id=? ORDER BY run_id DESC LIMIT 1', (mid,))
    store.log(con, 'READ', 'member_feature', mid, 'U-0142', '/api/members/' + mid)
    return {'member': m, 'raw': json.loads(raw['raw_json']) if raw else None, 'features': views.features(con, mid),
            'assessment': store.one(con, 'SELECT * FROM assessment WHERE member_id=? ORDER BY run_id DESC LIMIT 1', (mid,)),
            'issues': store.rows(con, 'SELECT * FROM data_issue WHERE member_id=?', (mid,)),
            'record': (views.portal_members(con, [mid], only_active=False) or [None])[0]}


# ───────────── analytics, data quality, data lens ─────────────
@route('GET', '/api/analytics')
def analytics(con, q, body):
    run = views.latest_run(con)
    g = lambda sql, *a: [dict(r) for r in con.execute(sql, a).fetchall()]
    return {'run_id': run,
            'alerts': g('SELECT alert, contact_priority, count(*) n FROM assessment WHERE run_id=? GROUP BY 1, 2 ORDER BY 2', run),
            'tiers': g('SELECT tier, tier_label, count(*) n FROM assessment WHERE run_id=? GROUP BY 1, 2 ORDER BY 1', run),
            'personas': g('SELECT persona, count(*) n FROM assessment WHERE run_id=? GROUP BY 1 ORDER BY 1', run),
            'triggers': g("SELECT trigger_code, state, count(*) n FROM signal WHERE status='open' GROUP BY 1, 2 ORDER BY 3 DESC"),
            'needs': g('SELECT slot, status, count(*) n FROM care_plan_need GROUP BY 1, 2'),
            'actions': g('SELECT kind, status, count(*) n FROM action GROUP BY 1, 2'),
            'outcomes': g('SELECT result, count(*) n FROM outcome GROUP BY 1'),
            'funnel': [{'campaign': c['campaign_id'], 'name': c['name'], 'status': c['status'],
                        'cohort': con.execute("SELECT count(DISTINCT cm.member_id) FROM campaign_cohort cc JOIN cohort_member cm USING (cohort_id) WHERE cc.campaign_id=? AND cc.role='include'", (c['campaign_id'],)).fetchone()[0],
                        'holdout': con.execute("SELECT count(DISTINCT cm.member_id) FROM campaign_cohort cc JOIN cohort_member cm USING (cohort_id) WHERE cc.campaign_id=? AND cc.role='include' AND cm.holdout=1", (c['campaign_id'],)).fetchone()[0],
                        'reach': len(engine.campaign_members(con, c['campaign_id'])),
                        'with_signals': con.execute("SELECT count(DISTINCT member_id) FROM signal WHERE campaign_id=? AND status='open'", (c['campaign_id'],)).fetchone()[0]}
                       for c in store.rows(con, 'SELECT * FROM campaign ORDER BY priority')]}


@route('GET', '/api/data-quality')
def data_quality(con, q, body):
    run = views.latest_run(con)
    return {'run': store.one(con, 'SELECT * FROM ingest_run WHERE run_id=?', (run,)),
            'issues': store.rows(con, "SELECT * FROM data_issue WHERE run_id=? ORDER BY CASE severity WHEN 'error' THEN 0 WHEN 'warn' THEN 1 ELSE 2 END, member_id", (run,))}


@route('GET', '/api/events')
def events(con, q, body):
    n = int((q.get('limit') or ['50'])[0])
    return {'events': store.rows(con, 'SELECT * FROM event_log ORDER BY event_id DESC LIMIT ?', (n,))}


@route('GET', '/api/schema')
def schema(con, q, body):
    tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
    return {'tables': [{'name': t, 'rows': con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0],
                        'columns': [c[1] for c in con.execute(f'PRAGMA table_info("{t}")')]} for t in tabs]}


# ───────────── HTTP plumbing ─────────────
class Handler(SimpleHTTPRequestHandler):
    con = None

    def __init__(self, *a, **k):
        super().__init__(*a, directory=DIST, **k)

    def log_message(self, fmt, *args):
        if os.environ.get('CCL_QUIET') != '1':
            sys.stderr.write('%s %s\n' % (self.command, self.path))

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def _api(self, method):
        u = urlparse(self.path)
        body = {}
        if method == 'POST':
            n = int(self.headers.get('Content-Length') or 0)
            try:
                body = json.loads(self.rfile.read(n) or b'{}')
            except json.JSONDecodeError:
                return self._send(400, {'error': 'body is not JSON'})
        for m, rx, fn in ROUTES:
            hit = rx.match(u.path)
            if m == method and hit:
                try:
                    with store._lock:
                        out = fn(self.con, parse_qs(u.query), body, **hit.groupdict())
                        self.con.commit()
                    return self._send(200, out)
                except ApiError as e:
                    return self._send(e.status, {'error': str(e)})
                except Exception as e:   # surface the error to the caller; the demo has no secrets in tracebacks
                    traceback.print_exc()
                    return self._send(500, {'error': f'{type(e).__name__}: {e}'})
        return self._send(404, {'error': 'no such endpoint', 'endpoints': sorted({f'{m} {rx.pattern[1:-1]}' for m, rx, _ in ROUTES})})

    def _send(self, status, obj):
        data = json.dumps(obj, default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith('/api/'):
            return self._api('GET')
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api/'):
            return self._api('POST')
        self._send(405, {'error': 'POST only on /api'})


def make_server(port=8000, con=None):
    Handler.con = con or store.connect()
    store.create_schema(Handler.con)
    return ThreadingHTTPServer(('0.0.0.0', port), Handler)


def bootstrap(con, extract=None):
    """First start: load the bundled sample extract and run the nightly once."""
    if not con.execute('SELECT count(*) FROM ingest_run').fetchone()[0]:
        from . import ingest
        ingest.load(extract or os.path.join(store.ROOT, 'data', 'raw', 'member_features_sample.tsv'), con=con)
    if not con.execute('SELECT count(*) FROM assessment').fetchone()[0]:
        engine.run(con)


if __name__ == '__main__':
    port = int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else int(os.environ.get('PORT', 8000))
    os.makedirs(os.path.dirname(store.DB_PATH), exist_ok=True)
    con = store.connect()
    store.create_schema(con)
    bootstrap(con)
    srv = make_server(port, con)
    print(f'Chronic Care Loop API on http://localhost:{port}/  (db: {store.DB_PATH})')
    srv.serve_forever()
