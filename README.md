# Chronic Care Loop

Three connected prototypes for the Daman × HICC chronic care programme, plus a relational backend that runs them on the member-level extract:

| # | Artefact | Built file | Source |
|---|----------|------------|--------|
| 1 | Executive briefing | `dist/Chronic-Care-Loop-Briefing.html` | `src/briefing/` |
| 2 | Cohort & care studio: ① Cohort & campaign builder → ② Care intelligence → ③ Care portal | `dist/Chronic-Care-Studio.html` | `src/studio/` |
| 3 | Care coordinator portal (standalone) | `dist/Care-Coordinator-Portal.html` | `src/portal/` |
| – | Data model: tables, sample rows, every read and write | `dist/database.html` | `src/hub/database.html` |

## Run with the backend (live data)

```bash
python3 -m backend.server
```

Then open http://localhost:8000/. On first start the server loads `data/raw/member_features_sample.tsv` (24 rows of the extract, all 341 columns) and runs the nightly engine once. The database is `data/ccl.db` (set `CCL_DB` to move it).

Served this way, the Studio and the portal switch to **live mode**:

- The builder's counts, funnel, profile and "who matches" come from SQL over the extract. Rules the extract cannot answer (for example LDL) are listed under the estimate.
- Saving a cohort or campaign writes it. Hand-off runs care intelligence straight away.
- Care intelligence and the portal show the members, scores, triggers and care plans in the database.
- In the portal, call outcomes and care-plan decisions are written back. Done promotes the next need, declined holds it for 90 days, and not reached schedules a retry (up to 3).

Opened as files (`file://`), every page falls back to its built-in synthetic data.

### Load the full extract

```bash
python3 -m backend.ingest path/to/member_features.tsv --glossary data/raw/glossary.tsv
python3 -m backend.engine
```

The file must be tab-separated with the 341 glossary columns as its header. Loading checks the file and logs problems in `data_issue`: placeholders such as 999, impossible readings, score totals and tier labels that do not match, and columns missing from the glossary. Members are upserted, so consent recorded by the loop survives a reload.

### API

| Method | Path | Used by |
|--------|------|---------|
| GET | `/api/health`, `/api/meta`, `/api/schema` | all |
| GET | `/api/features?q=` | builder search |
| POST | `/api/cohorts/estimate` | builder: live count, funnel, profile, sample |
| GET / POST | `/api/cohorts`, `/api/campaigns` | builder: library and save |
| POST | `/api/runs/nightly` | hand-off, scheduler |
| GET | `/api/intel?campaign=` | care intelligence |
| GET | `/api/portal/members` | portal worklist |
| POST | `/api/portal/event` | portal write-back: `{member_id, kind: call\|need, need, result, reached, consent}` |
| GET | `/api/actions`, `/api/care-plans`, `/api/members/{id}` | portal, Member 360 |
| GET | `/api/analytics`, `/api/data-quality`, `/api/events` | analytics, data lens |

### Tests

```bash
python3 -m unittest discover tests
```

## Backend layout

| File | What it does |
|------|--------------|
| `backend/schema.sql` | 21 SQLite tables in five groups (PostgreSQL-compatible keys and types) |
| `backend/reference.py` | Rulebook constants: triggers and actions, tiers and cadence, contact priority SLAs, care team |
| `backend/ingest.py` | Extract + glossary → `src_member_row`, `member`, `feature`, `member_feature`, `data_issue` |
| `backend/cohorts.py` | Builder rule JSON → SQL (`EXISTS` over `member_feature`), estimate, stable-hash holdout |
| `backend/engine.py` | Nightly run: outcomes → cohorts → campaign members → assessment → signals → care plans → actions. Also `record()` for portal write-back |
| `backend/views.py` | Database rows → the record shapes the Studio and the portal render |
| `backend/server.py` | Standard-library HTTP server for `/api` and `dist/` |
| `src/studio/lib/ccl-live.js`, the live-mode block in `src/portal/index.template.html` | Frontend live mode with fallback |

## Data model

- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md): the entities, the loop, and the rulebook mapping.
- `dist/database.html`: interactive page. It is generated from the running backend by `python3 tools/gen_model.py`, which scripts one demo day and reads the schema and rows back.
- [`docs/schema.sql`](docs/schema.sql): PostgreSQL DDL plus those sample rows (`node tools/gen_schema.js`, which also checks every step, column and foreign key).
- [`docs/DATA_FINDINGS.md`](docs/DATA_FINDINGS.md): what the loader found in the extract.

## Build the frontends

```bash
python3 tools/build_all.py
```

Each `src/<app>/` folder holds a bundle's parts: `shell.html` (the loader), `index.template.html` (the page, assets referenced by uuid) and `bundle.json` (uuid → readable file). The Studio's screen 3 embeds the freshly built portal through the `bundle.json` entry `{"build": "../portal"}`.

To pull in a new export from the design tool:

```bash
python3 tools/bundle.py unpack <file.html> src/<app> [name=uuid ...]
```

Member names shown for extract rows are pseudonyms generated from the masked id. The built-in fallback data is synthetic.
