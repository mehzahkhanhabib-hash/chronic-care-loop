# Chronic Care Loop

Three connected prototypes for the Daman × HICC chronic care programme:

| # | Artefact | Built file | Source |
|---|----------|------------|--------|
| 1 | Executive briefing | `dist/Chronic-Care-Loop-Briefing.html` | `src/briefing/` |
| 2 | Cohort & care studio (Cohorts → Care intelligence → Care portal) | `dist/Chronic-Care-Studio.html` | `src/studio/` |
| 3 | Care coordinator portal (standalone) | `dist/Care-Coordinator-Portal.html` | `src/portal/` |

`dist/index.html` is the overview page. It links all three and shows the data model. Every artefact also has a link bar or rail section that points to the other two.

The data model is in [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md).

The relational backend is 16 PostgreSQL tables:

- `dist/database.html`: interactive page with a high-level model, sample rows, and every read and write per step.
- [`docs/schema.sql`](docs/schema.sql): DDL plus the sample rows. It is generated from the page by `node tools/gen_schema.js`, which also checks every step, column and foreign key. Load it with `psql -f docs/schema.sql`.

## Run

Open `dist/index.html` in a browser. Each file is self-contained and works from `file://` or any static host.

## Build

```bash
python3 tools/build_all.py
```

Each `src/<app>/` folder holds a bundle's parts:

- `shell.html`: the loader page.
- `index.template.html`: the page itself. Assets are referenced by uuid.
- `bundle.json`: maps each uuid to a readable file.

The Studio's screen 3 is not a copy. Its `bundle.json` entry `{"build": "../portal"}` embeds the freshly built portal.

To pull in a new export from the design tool:

```bash
python3 tools/bundle.py unpack <file.html> src/<app> [name=uuid ...]
```

## Where things live

| What | File |
|------|------|
| Cohort builder UI, including Describe (catalogue first, then graph) | `src/studio/CohortStudioV2.dc.html` |
| Field catalogue, search, parse, estimates | `src/studio/lib/cohort-engine-v2.js` |
| Knowledge-graph traversal and `resolve()` (feature exists, else new) | `src/studio/lib/kg-engine.js` |
| Studio shell, care intelligence screen, portal bridge | `src/studio/index.template.html` |
| Portal (vanilla JS). The v8 integration patch is at the end of the script | `src/portal/index.template.html` |

All member data is synthetic.
