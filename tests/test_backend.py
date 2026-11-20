"""Backend tests: ingest → cohorts → nightly run → portal write-back. Run: python3 -m unittest discover tests"""
import os, tempfile, unittest
os.environ['CCL_DB'] = os.path.join(tempfile.mkdtemp(), 'test.db')
from backend import store, ingest, engine, cohorts, views  # noqa: E402

SAMPLE = os.path.join(store.ROOT, 'data', 'raw', 'member_features_sample.tsv')


class Backend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = store.connect()
        cls.load = ingest.load(SAMPLE, con=cls.con)
        cls.first = engine.run(cls.con)

    def q(self, sql, *a):
        return self.con.execute(sql, a).fetchone()[0]

    def test_ingest_keeps_every_column(self):
        self.assertEqual(self.load['columns'], 341)
        self.assertEqual(self.q('SELECT count(*) FROM src_member_row'), self.load['rows'])

    def test_sentinels_are_nulled_and_reported(self):
        self.assertIsNone(self.con.execute("SELECT value_num FROM member_feature WHERE member_id='m44' AND feature_key='x:Last_SystolicPressure_Value'").fetchone())
        self.assertGreater(self.q("SELECT count(*) FROM data_issue WHERE member_id='m44' AND rule='999 placeholder'"), 0)

    def test_intelligence_outputs_are_not_cohort_filters(self):
        self.assertEqual(self.q("SELECT count(*) FROM feature WHERE category IN ('Risk score','Trigger','Persona') AND cohort_selectable=1"), 0)

    def test_estimate_matches_saved_cohort(self):
        d = cohorts.definition(self.con, 'COH-0101')
        self.assertEqual(cohorts.estimate(self.con, d)['n'], self.q("SELECT row_count FROM cohort WHERE cohort_id='COH-0101'"))

    def test_unsupported_rule_is_reported_not_silently_dropped(self):
        e = cohorts.estimate(self.con, {'base': 'daman', 'inc': [{'id': 1, 'f': 'lab', 'l': 'ldl', 'op': '≥', 'v': 3}], 'exc': []})
        self.assertEqual(e['unsupported'][0]['id'], 1)

    def test_holdout_is_stable(self):
        self.assertEqual(cohorts.holdout('COH-0101', 'm1'), cohorts.holdout('COH-0101', 'm1'))

    def test_tiers_follow_rulebook(self):
        for R, t in self.con.execute('SELECT r_total, tier FROM assessment'):
            self.assertEqual(t, 4 if R >= 13 else 3 if R >= 8 else 2 if R >= 4 else 1)

    def test_at_most_three_current_needs(self):
        self.assertEqual(self.q("SELECT count(*) FROM (SELECT care_plan_id FROM care_plan_need WHERE slot='CURRENT' GROUP BY 1 HAVING count(*) > 3)"), 0)

    def test_one_action_per_current_need(self):
        self.assertEqual(self.q("""SELECT count(*) FROM care_plan_need n WHERE slot='CURRENT' AND status='open'
                                   AND NOT EXISTS (SELECT 1 FROM action a WHERE a.need_id=n.need_id AND a.kind='care_plan')"""), 0)

    def test_nightly_is_idempotent(self):
        before = engine.run(self.con)
        again = engine.run(self.con)
        self.assertEqual((again['new_needs'], again['new_actions']), (0, 0))
        self.assertEqual(again['signals'], before['signals'])

    def test_holdout_and_declined_get_no_signals(self):
        self.assertEqual(self.q("""SELECT count(*) FROM signal s JOIN cohort_member cm ON cm.member_id=s.member_id
                                   JOIN campaign_cohort cc ON cc.cohort_id=cm.cohort_id AND cc.campaign_id=s.campaign_id
                                   WHERE cm.holdout=1 AND s.status='open'
                                   AND NOT EXISTS (SELECT 1 FROM campaign_cohort c2 JOIN cohort_member m2 USING (cohort_id)
                                                   WHERE c2.campaign_id=s.campaign_id AND m2.member_id=s.member_id AND m2.holdout=0)"""), 0)

    def test_writeback_done_promotes_next_need(self):
        cp = self.con.execute("SELECT care_plan_id, member_id FROM care_plan_need JOIN care_plan USING (care_plan_id) WHERE slot='NEXT' LIMIT 1").fetchone()
        cur = self.con.execute("SELECT need_key FROM care_plan_need WHERE care_plan_id=? AND slot='CURRENT' LIMIT 1", (cp[0],)).fetchone()[0]
        before = self.q("SELECT count(*) FROM care_plan_need WHERE care_plan_id=? AND slot='CURRENT'", cp[0])
        engine.record(self.con, {'member_id': cp[1], 'kind': 'need', 'need': cur, 'result': 'done'})
        self.assertEqual(self.q("SELECT status FROM care_plan_need WHERE care_plan_id=? AND need_key=?", cp[0], cur), 'done')
        self.assertEqual(self.q("SELECT count(*) FROM care_plan_need WHERE care_plan_id=? AND slot='CURRENT'", cp[0]), before)
        self.assertEqual(self.q("SELECT status FROM action WHERE need_id=(SELECT need_id FROM care_plan_need WHERE care_plan_id=? AND need_key=?)", cp[0], cur), 'done')

    def test_writeback_declined_holds_90_days(self):
        n = self.con.execute("SELECT p.member_id, n.need_key FROM care_plan_need n JOIN care_plan p USING (care_plan_id) WHERE n.status='open' ORDER BY n.need_id DESC LIMIT 1").fetchone()
        engine.record(self.con, {'member_id': n[0], 'kind': 'need', 'need': n[1], 'result': 'declined'})
        self.assertEqual(self.q("SELECT hold_until FROM care_plan_need n JOIN care_plan p USING (care_plan_id) WHERE p.member_id=? AND need_key=?", *n), '2027-02-18')
        engine.run(self.con)   # still held after the next run
        self.assertEqual(self.q("SELECT n.status FROM care_plan_need n JOIN care_plan p USING (care_plan_id) WHERE p.member_id=? AND need_key=?", *n), 'declined')

    def test_not_reached_retries_up_to_three(self):
        mid = self.con.execute('SELECT member_id FROM care_plan ORDER BY member_id DESC LIMIT 1').fetchone()[0]
        for _ in range(4):
            engine.record(self.con, {'member_id': mid, 'kind': 'call', 'reached': False})
            self.con.execute("UPDATE action SET status='done' WHERE member_id=? AND kind='retry'", (mid,))
        self.assertLessEqual(self.q("SELECT count(*) FROM action WHERE member_id=? AND kind='retry'", mid), 2)

    def test_consent_declined_leaves_the_campaign(self):
        mid = self.con.execute("SELECT member_id FROM signal WHERE status='open' ORDER BY member_id LIMIT 1").fetchone()[0]
        engine.record(self.con, {'member_id': mid, 'kind': 'call', 'reached': True, 'consent': 'declined'})
        engine.run(self.con)
        self.assertEqual(self.q("SELECT count(*) FROM signal WHERE member_id=? AND status='open'", mid), 0)

    def test_portal_record_shape(self):
        r = views.portal_members(self.con)[0]
        for k in ('id', 'mask', 'name', 'conds', 'labs', 'meds', 'trigger', 'live'):
            self.assertIn(k, r)
        self.assertTrue(all(n['k'] for n in r['live']['needs']))


if __name__ == '__main__':
    unittest.main()
