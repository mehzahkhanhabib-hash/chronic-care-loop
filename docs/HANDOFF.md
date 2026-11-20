# Developer handoff

This guide is for the engineers who will take the Chronic Care Loop to production. It covers:

- what exists today
- what can be reused as is
- what needs rebuilding
- where everything lives

## 1. How to hand it over

There are two ways. Use both.

| Give them | When | How |
|-----------|------|-----|
| **The Git repository** | Engineers who will change code. This is the source of truth: sources, build tools, tests and history. | Add them as collaborators on GitHub: repository **Settings → Collaborators → Add people**. The repository is `mehzahkhanhabib-hash/chronic-care-loop`. Keep it private. |
| **The delivery folder** (`Chronic-Care-Loop.zip`) | Anyone who needs to run, review or demo it: product, clinical, QA, infrastructure. | Build it with `python3 tools/build_all.py && python3 tools/package.py`, then send `release/Chronic-Care-Loop.zip` through an approved internal channel. |

Both contain 24 real (masked) rows of the member extract in `data/raw/`. Agree with information governance where they may be stored before sharing.

Ask the engineers to start with:

1. `START-HERE.md`, to run it.
2. This file.
3. `4-data-model/rules/README.md`, for the rules.
4. `4-data-model/database.html`, to see every table and every read and write.

## 2. Architecture

```
member extract (TSV, 341 cols) ─▶ ingest ─▶ SQLite / PostgreSQL ◀── rule database (rules/*.csv)
                                              │      ▲
                         nightly engine ──────┘      │ write-back (outcomes)
                                              ▼      │
     HTTP API (/api/…) ─▶ Cohort & campaign builder · Care intelligence · Care portal
```

| Layer | Today | Files |
|-------|-------|-------|
| Data | SQLite file: 20 operational tables and 14 rule tables. The data-model page and the PostgreSQL DDL cover the 29 that carry the loop; they are generated and checked against PostgreSQL 16. | `backend/schema.sql`, `docs/schema.sql` |
| Rules | 14 rule tables loaded from CSV at start-up. No rule is hard-coded. | `rules/*.csv`, `backend/rules.py` |
| Ingest | Reads the extract and glossary, types every value, and logs quality issues. | `backend/ingest.py` |
| Engine | Nightly run, in order: outcomes → cohorts → campaign members → assessment → signals → care plans → actions. Also applies portal write-backs as they arrive. | `backend/engine.py`, `backend/cohorts.py` |
| API | Python standard library HTTP server. JSON in and out, no framework, no third-party packages. | `backend/server.py`, `backend/views.py` |
| Frontends | Four single-file web apps, exported from a design tool and patched. In "live mode" they call the API; opened as files, they use built-in demo data. | `src/portal`, `src/builder`, `src/studio`, `src/hub` |

Run it locally:

```bash
python3 -m backend.server
```

Run the tests (23, all passing):

```bash
python3 -m unittest discover tests
```

## 3. What to reuse and what to rebuild

| Part | Keep as is | Rebuild |
|------|------------|---------|
| **Rule database** (`rules/`) | ✅ This is the contract with the clinical team. Load it into your own rules store, or keep the CSVs under change control. | – |
| **Data model** (`docs/schema.sql`) | ✅ Tables, keys and the two tracking views (`v_need_tracking`, `v_loop_kpis`) are designed to carry over to PostgreSQL. | Add audit columns and row-level security to suit your platform. |
| **Engine logic** (`engine.py`, `cohorts.py`, `rules.py`) | ✅ As the reference implementation and test oracle. The tests pin the rulebook behaviour. | Port it to your job framework (Airflow, Azure Functions, dbt + Python) if you don't run Python services. |
| **API** (`server.py`) | The endpoint list is the contract the UIs need (see the README). | Re-implement it on your API stack with authentication, roles and rate limits. The stdlib server is for demos and pilots only. |
| **Frontends** | Use them as the functional and visual specification, or for a pilot. | The production UI should be rebuilt in your component library. The bundled HTML is hard to maintain: each app is one large template, editable only through `tools/bundle.py`. |

## 4. Where to change things

| To change | Edit |
|-----------|------|
| A trigger threshold, an alert rule, a priority or SLA, a write-back rule | `rules/*.csv` (no code change) |
| Use the rulebook's thresholds instead of the extract's flags for a trigger | `rule_trigger.csv`, `use_variant` column |
| What the builder can filter on | `backend/cohorts.py` (`compile_rule`) and the field list in `src/studio/lib/cohort-engine-v2.js` |
| How the extract is typed or checked | `backend/ingest.py` (`PLAUSIBLE`, `infer_type`) |
| The records the screens receive | `backend/views.py` |
| Portal live-mode behaviour | The "Chronic Care Loop · live mode" blocks in `src/portal/index.template.html` |
| Studio and builder live-mode behaviour | `src/studio/lib/ccl-live.js` |

After a frontend change:

```bash
python3 tools/build_all.py
```

After a schema or rule change:

```bash
python3 tools/gen_model.py && node tools/gen_schema.js && python3 -m backend.rules
```

This regenerates the data-model page, the PostgreSQL DDL and the rule database.

## 5. Production checklist

| # | Item | Why |
|---|------|-----|
| 1 | **Clinical sign-off** on every rule (`status` column in `rule_trigger.csv`) and the Trig1 decision (6.5% vs ~8%). | Rulebook §8: the thresholds are not yet validated. |
| 2 | **PostgreSQL** instead of SQLite. Load `docs/schema.sql` and `rules/rules.sql`. | Concurrency, backups, access control. |
| 3 | **Single sign-on and roles** (population health, clinical lead, nurse), mapped to `care_team_user`. | The demo has no login. |
| 4 | **Scheduled nightly run** after the extract lands (`python3 -m backend.engine`, or the ported job). | Today it runs on hand-off or on demand. |
| 5 | **Extract pipeline** from the warehouse straight into `ingest`, plus the E_LIFE_ID ↔ PERSONID crosswalk. | Rulebook §8 open decision. |
| 6 | **Hosting in an approved UAE region**, with encryption at rest and in transit. | Health data. See `HOSTING.md`. |
| 7 | **Telephony and consent capture** (Genesys) writing to `contact` and `outcome`. | Today the portal records the outcome by hand. |
| 8 | **Monitoring**: `v_loop_kpis` on a dashboard; alert if `current_needs_without_action > 0`. | Proves the loop is closing. |
| 9 | **CI**: run the tests, `gen_schema.js` (checks every key) and a PostgreSQL load on every change. | All three already run locally. |

## 6. Known limits of the prototype

- Member names are pseudonyms generated from `mask_id`. The extract has no names or phone numbers.
- The extract has no wearables, LDL, region or PURA users. The builder reports those rules as unanswerable rather than ignoring them.
- About 70% of members are seeded as already consented so the demo isn't fully locked. In production, consent comes only from `contact` and `outcome`.
- The knowledge-graph "Describe" in the builder still uses the simulated graph, not your NebulaGraph.
