"""End-to-end test of the SQL kit on MySQL 8 (SingleStore speaks the same dialect; SingleStore-only keywords are stripped).

  docker run -d --name cclmysql -e MYSQL_ROOT_PASSWORD=pw -e MYSQL_DATABASE=ccl -p 3307:3306 mysql:8.4 --local-infile=1
  CCL_DIALECT=mysql S2_PORT=3307 S2_PASSWORD=pw python3 -m unittest two-day-build/tests/test_kit.py

Checks the whole chain on the 24-member sample: load → triggers → needs → actions → worklist → nurse outcome → follow-up,
and that the triggers match the reference engine (backend/rules.py) member by member.
"""
import os, sys, unittest
os.environ.setdefault('CCL_DIALECT', 'mysql')
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
REPO = os.path.dirname(KIT)
sys.path[:0] = [os.path.join(KIT, 'api'), REPO]
import pymysql  # noqa: E402
import sqlkit, server  # noqa: E402

SAMPLE = os.environ.get('CCL_EXTRACT') or os.path.join(REPO, 'data', 'raw', 'member_features_sample.tsv')   # CCL_EXTRACT=… runs the checks on another file


def fresh():
    root = pymysql.connect(host=os.environ.get('S2_HOST', '127.0.0.1'), port=int(os.environ.get('S2_PORT', 3307)), user='root',
                           password=os.environ.get('S2_PASSWORD', 'pw'), autocommit=True)
    with root.cursor() as c:
        c.execute('DROP DATABASE IF EXISTS ccl')
        c.execute('CREATE DATABASE ccl')
        c.execute('SET GLOBAL innodb_strict_mode = OFF')   # MySQL-only: 341 TEXT columns in staging (SingleStore has no such limit)
    root.close()
    os.environ.setdefault('S2_PORT', '3307'); os.environ.setdefault('S2_PASSWORD', 'pw')
    return server.connect()


def build(con):
    for f in ('01_schema.sql', '02_rules.sql', '02b_setup.sql', '06_views.sql'):
        sqlkit.run_file(con, f)
    load = sqlkit.run_file(con, '03_load.sql', replace={"'member_features.tsv'": repr(SAMPLE)})
    con.commit()
    kpis = server.nightly(con, {}, {})
    return load, kpis


class Kit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = fresh()
        cls.load, cls.kpis = build(cls.con)

    def q(self, sql, *a):
        return server.rows(self.con, sql, a or None)

    def test_load_and_g0_cleaning(self):
        self.assertEqual(self.q('SELECT COUNT(*) AS n FROM member')[0]['n'], 24)
        self.assertIsNone(self.q("SELECT last_systolicpressure_value AS v FROM member WHERE member_id = 'm44'")[0]['v'])   # 999 → NULL
        self.assertIsNone(self.q("SELECT last_systolicpressure_value AS v FROM member WHERE member_id = 'm75'")[0]['v'])   # BP 1/1 → NULL
        flagged = {r['member_id'] for r in self.load[-1]}
        self.assertTrue({'m44', 'm75', 'm147'} <= flagged)

    def test_triggers_match_reference_engine(self):
        from backend.rules import Rules
        from backend import store, ingest, engine
        import tempfile
        ref = store.connect(os.path.join(tempfile.mkdtemp(), 'ref.db'))
        ingest.load(SAMPLE, con=ref)
        R = Rules()
        expect = set()
        for (mid,) in ref.execute('SELECT member_id FROM member').fetchall():
            for code, state, _ in R.fired(engine.features(ref, mid)):
                expect.add((mid, code, state))
        got = {(r['member_id'], r['trigger_code'], r['state']) for r in self.q('SELECT member_id, trigger_code, state FROM member_signal')}
        self.assertEqual(got, expect)

    def test_every_current_need_has_one_action(self):
        self.assertEqual(self.kpis['current_needs_without_action'], 0)
        self.assertEqual(self.q("""SELECT COUNT(*) AS n FROM (SELECT member_id, trigger_code FROM action WHERE kind = 'care_plan' AND status = 'open'
                                   GROUP BY member_id, trigger_code HAVING COUNT(*) > 1) x""")[0]['n'], 0)
        self.assertEqual(self.q("SELECT COUNT(*) AS n FROM (SELECT member_id FROM care_plan_need WHERE slot = 'CURRENT' GROUP BY member_id HAVING COUNT(*) > 3) x")[0]['n'], 0)

    def test_holdout_and_exclusions_get_no_needs(self):
        self.assertEqual(self.q("""SELECT COUNT(*) AS n FROM care_plan_need n WHERE NOT EXISTS
                                   (SELECT 1 FROM campaign_member cm WHERE cm.member_id = n.member_id AND cm.holdout = 0)""")[0]['n'], 0)

    def test_worklist_rules(self):
        wl = self.q("SELECT * FROM v_worklist ORDER BY rank_no")
        self.assertTrue(wl)
        urgent = [r['alert'] == 'RED' for r in wl]
        self.assertEqual(urgent, sorted(urgent, reverse=True))      # RED first
        for r in wl:                                                  # language match
            langs = {x['language'] for x in self.q('SELECT language FROM nurse_language WHERE nurse_id = %s', r['nurse_id'])}
            self.assertIn(r['language'] if r['language'] in ('Arabic', 'English') else 'English', langs)

    def test_rerun_is_idempotent(self):
        before = self.q('SELECT COUNT(*) AS n FROM action')[0]['n']
        server.nightly(self.con, {}, {})
        self.assertEqual(self.q('SELECT COUNT(*) AS n FROM action')[0]['n'], before)

    def test_z_nurse_outcomes_create_follow_ups(self):
        cp = self.q("""SELECT a.member_id, a.action_id, a.trigger_code FROM action a JOIN care_plan_need n USING (member_id, trigger_code)
                       WHERE a.kind = 'care_plan' AND a.status = 'open' AND n.slot = 'CURRENT' ORDER BY a.member_id, n.class_order LIMIT 1""")[0]
        mid = cp['member_id']
        nxt = self.q("SELECT trigger_code FROM care_plan_need WHERE member_id = %s AND slot = 'NEXT' ORDER BY class_order, trigger_order LIMIT 1", mid)
        r = server.outcome(self.con, {}, {'member_id': mid, 'result': 'done', 'nurse_id': 'U-0142'}, cp['action_id'])
        need = self.q('SELECT status, gap_state, slot FROM care_plan_need WHERE member_id = %s AND trigger_code = %s', mid, cp['trigger_code'])[0]
        self.assertEqual((need['status'], need['gap_state'], need['slot']), ('done', 'Reported', 'CLOSED'))
        kinds = [a['kind'] for a in r['new_actions']]
        self.assertIn('follow_up', kinds)                                       # "Verify in claims: …"
        self.assertEqual([a['parent_action_id'] for a in r['new_actions'] if a['kind'] == 'follow_up'], [cp['action_id']])
        if nxt:                                                                 # NEXT promoted to CURRENT with its own action
            self.assertEqual(self.q('SELECT slot FROM care_plan_need WHERE member_id = %s AND trigger_code = %s', mid, nxt[0]['trigger_code'])[0]['slot'], 'CURRENT')
            self.assertIn('care_plan', kinds)
        # declined → 90-day hold + re-offer follow-up
        d = self.q("SELECT action_id, trigger_code FROM action WHERE member_id = %s AND kind = 'care_plan' AND status = 'open' LIMIT 1", mid)[0]
        r = server.outcome(self.con, {}, {'member_id': mid, 'result': 'declined', 'nurse_id': 'U-0142'}, d['action_id'])
        self.assertEqual(str(self.q('SELECT hold_until FROM care_plan_need WHERE member_id = %s AND trigger_code = %s', mid, d['trigger_code'])[0]['hold_until']), '2027-02-18')
        self.assertTrue(any(a['title'].startswith('Re-offer') for a in r['new_actions']))
        # not reached three times → retries, then a P1 escalation
        call = self.q("SELECT a.action_id, a.member_id FROM action a JOIN member m USING (member_id) WHERE a.kind = 'call' AND a.status = 'open' AND m.contact_priority = 'P1' LIMIT 1")[0]
        aid = call['action_id']
        for _ in range(3):
            r = server.outcome(self.con, {}, {'member_id': call['member_id'], 'result': 'not_reached', 'reached': 0, 'nurse_id': 'U-0142'}, aid)
            nxt_ = [a for a in r['new_actions'] if a['kind'] in ('retry', 'escalation')]
            if not nxt_:
                break
            aid = nxt_[0]['action_id']
        kinds = [a['kind'] for a in self.q('SELECT kind FROM action WHERE member_id = %s', call['member_id'])]
        self.assertEqual(kinds.count('retry'), 2)
        self.assertEqual(kinds.count('escalation'), 1)

    def test_zz_gap_closes_only_in_claims(self):
        n = self.q("SELECT a.member_id, a.action_id FROM action a WHERE a.kind = 'care_plan' AND a.status = 'open' AND a.trigger_code = 'Trig1' LIMIT 1")[0]
        server.outcome(self.con, {}, {'member_id': n['member_id'], 'result': 'done', 'nurse_id': 'U-0142'}, n['action_id'])
        self.assertEqual(self.q("SELECT gap_state FROM care_plan_need WHERE member_id = %s AND trigger_code = 'Trig1'", n['member_id'])[0]['gap_state'], 'Reported')
        server.nightly(self.con, {}, {})        # still fires: stays Reported, not reopened (G9)
        self.assertEqual(self.q("SELECT gap_state, status FROM care_plan_need WHERE member_id = %s AND trigger_code = 'Trig1'", n['member_id'])[0],
                         {'gap_state': 'Reported', 'status': 'done'})
        with self.con.cursor() as c:            # next extract: the HbA1c claim arrived, the flag is off
            c.execute("UPDATE member SET trig1_hba1c_above_target = 0 WHERE member_id = %s", (n['member_id'],))
        server.nightly(self.con, {}, {})
        self.assertEqual(self.q("SELECT gap_state FROM care_plan_need WHERE member_id = %s AND trigger_code = 'Trig1'", n['member_id'])[0]['gap_state'], 'Closed')


if __name__ == '__main__':
    unittest.main()
