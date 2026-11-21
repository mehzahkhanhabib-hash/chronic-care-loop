# Chronic Care Loop · 2-day build kit (SingleStore)

Start with **`PLAN.md`**: it explains the model, the nurse rules, the worklist, the follow-ups, the rulebook view, the API and the 3-developer plan.

```
sql/
  01_schema.sql       tables (SingleStore: REFERENCE rules, ROWSTORE member tables sharded by member_id)
  02_rules.sql        the rulebook as rows (generated from rules/*.csv)
  02b_setup.sql       run dates, nurses and languages, demo campaigns (edit freely)
  03_load.sql         raw TSV → stg_extract → typed, cleaned member (G0)
  04_nightly.sql      triggers → score → needs → slots → actions → nudges/calls → worklist
  05_followup.sql     nurse outcome → follow-up action (POST /actions/{id}/outcome)
  06_views.sql        v_worklist · v_care_plan · v_action_chain · v_rulebook_member · v_member_summary · v_rulebook_programme · v_kpis
  07_reset_member.sql demo only: forget one member's nurse work, then run the rules again (POST /members/{id}/reset)
api/
  server.py           thin JSON API (Python + pymysql); every endpoint is one SQL file or one view
  sqlkit.py           runs the .sql files statement by statement
  examples/           a real response from every endpoint
  app-shapes/         the records the three existing apps render today (for the adapters)
apps/                 the three apps: care portal, cohort & campaign builder, care studio
data/                 the 24-row sample extract and the glossary (real, masked rows: keep inside the approved workspace)
rules/                the rule database as CSV (source of 02_rules.sql and of the trigger SQL in 04_nightly.sql)
tests/test_kit.py     end-to-end checks (run against MySQL 8 or SingleStore)
tools/gen_sql.py      regenerates 01–04 after a rule CSV changes (run it from the repository)
```

## Run it on SingleStore

```bash
export S2_HOST=<host> S2_PORT=3306 S2_USER=<user> S2_PASSWORD=<password>
alias s2='mysql -h $S2_HOST -P $S2_PORT -u $S2_USER -p$S2_PASSWORD --local-infile=1'   # SingleStore speaks the MySQL protocol

s2 < sql/01_schema.sql
s2 ccl < sql/02_rules.sql
s2 ccl < sql/02b_setup.sql
s2 ccl < sql/06_views.sql
cp data/member_features_sample.tsv data/member_features.tsv   # or put the full extract there
cd data && s2 ccl < ../sql/03_load.sql && cd ..          # reads member_features.tsv from the current folder

pip install pymysql
cd api && S2_DB=ccl python3 server.py --port 8080 &
curl -X POST localhost:8080/runs/nightly                # refreshes campaign members, runs 04_nightly.sql
curl "localhost:8080/worklist?nurse=U-0150"
```

On a clean run with the sample, `curl localhost:8080/kpis` shows 24 members, 152 triggers fired, 21 care plans, 63 current needs, `current_needs_without_action: 0` and 21 members on today's list.

## Test it without SingleStore (MySQL 8 in Docker)

```bash
docker run -d --name cclmysql -e MYSQL_ROOT_PASSWORD=pw -e MYSQL_DATABASE=ccl -p 3307:3306 mysql:8.4 --local-infile=1
CCL_DIALECT=mysql S2_PORT=3307 S2_PASSWORD=pw python3 -m unittest two-day-build/tests/test_kit.py   # from the repository root
```

`CCL_DIALECT=mysql` strips the three SingleStore-only keywords (`REFERENCE`, `ROWSTORE`, `SHARD KEY`). Nothing else changes.
